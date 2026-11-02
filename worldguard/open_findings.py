"""Contradictions stay on record, with the chapters that established them, until a check finds them fixed.

Every `check`, `mesh-check`, `timeline` and `lifeline` of a file keeps the FAIL rows it found in a record,
`.worldguard/open.json`: the nearest one in the checked file's folder or a folder above it, or a new one in the
file's folder. An entry belongs to the file the contradiction lives in (a chapter's world file, or the tree file for a
hand-over between chapters), and every later command whose files lie under a record's folder prints the entries
that record holds.

An entry closes only when a later run re-checks its file and the check that found it asked the same question again
there and got a pass. For the relation check that question is one fact just before one event ("Lena holds key before
e_unlock"), for the conflict check one person's places or one thing's holders, for a hand-over one fact across one edge;
the same derivation the check runs says which questions this run asked and why it asked nothing at a place
(`relations.relation_coverage`, `relations.conflict_coverage`, `mesh.handoff_fluents`). An entry stays open while that
check does not reach its place (no relation declared, no actor, no time, `actor_state_free`, a Guard that no longer
runs, any other problem row there) and says why. It closes, saying exactly what changed, when its chapter, hand-over
or event is gone from its file, or when the check still runs there but the world no longer asks that question (the
event no longer uses the thing, the chapters no longer both name the fact).

A file that is renamed, moved or deleted closes nothing. Its entries stay open and say the file is gone, naming the
path it was last seen at. A run that finds the same contradiction in exactly one file of the same world (the file's
`contract_id`, or the tree's `mesh_id`) under the same record moves the entry there with its history; found in two or
more, the entry follows none of them and names them. A pass in such a file closes nothing, since it may be another
draft of the world: the entry says the world passed there and names the command that settles it, `check --contract NEW
--takes-over OLD` (`mesh-check --mesh` for a tree file), with which the person says NEW is OLD under a new path; that
run gives OLD's entries to NEW and judges them there like any entry of NEW. A record that cannot be read or written stops the command (RecordError); nothing falls back to a run without it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from .errors import WorldInputError
from .relations import conflict_coverage, parse_relations, relation_coverage
from .semantic import event_replay, precondition_coverage

STORE = Path(".worldguard") / "open.json"
_SUBJECT_KEYS = ("fluent", "color", "variable", "relation", "subject", "object", "claim_row", "variant_id", "scenario_id")
_ITEM_FIELDS = ("unit", "code", "summary", "first_seen")


class RecordError(Exception):
    """The record of open contradictions cannot be read or written."""

    def __init__(self, path: Path, message: str):
        super().__init__(f"{path}: {message}")
        self.path = path


@dataclass
class Unit:
    """One file (or one inline chapter of a tree file) that a run checked completely."""

    path: Path                      # absolute path of the file
    node: str = ""                  # an inline chapter of a tree file; empty for a file of its own
    rows: list[dict[str, Any]] = field(default_factory=list)   # every problem row found in it
    guards: frozenset[str] = frozenset()                        # the Guards that ran on it
    events: dict[str, Mapping[str, Any]] = field(default_factory=dict)
    edges: frozenset[str] = frozenset()                         # tree file only
    nodes: frozenset[str] = frozenset()                         # tree file only
    chapter: dict[str, Any] = field(default_factory=dict)       # chapter id and source, for established_by
    mesh: Any = None                                             # the tree, for the hand-over's established_by
    tree: bool = False                                           # the unit is the tree file itself
    relation_questions: dict[tuple[str, str], tuple[frozenset, tuple[str, ...]]] = field(default_factory=dict)
    conflict_questions: dict[str, tuple[frozenset, str]] = field(default_factory=dict)
    handoff_questions: dict[str, tuple[frozenset, str]] = field(default_factory=dict)   # tree file only
    precondition_questions: dict[tuple[str, str], tuple[frozenset, str]] = field(default_factory=dict)
    claim_rows: dict[str, tuple[str, str]] = field(default_factory=dict)  # index -> (assertion, status)
    world: str | None = None   # "world <contract_id>" or "tree <mesh_id>"; None when the file declares no id

    def name(self, folder: Path) -> str:
        relative = Path(os.path.relpath(self.path, folder)).as_posix()
        return f"{relative}#{self.node}" if self.node else relative


def store_path(folder: str | Path) -> Path:
    return Path(folder) / STORE


def _load(folder: Path) -> dict[str, Any]:
    path = store_path(folder)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RecordError(path, f"could not read: {exc}") from exc
    except ValueError as exc:
        raise RecordError(path, f"is not a WorldGuard record of open contradictions ({exc})") from exc
    if (not isinstance(data, dict) or not isinstance(data.get("open"), list) or not isinstance(data.get("resolved"), list)
            or any(not isinstance(item, dict) or any(not isinstance(item.get(key), str) for key in _ITEM_FIELDS)
                   for item in data["open"])):
        raise RecordError(path, "is not a WorldGuard record of open contradictions")
    return data


def records_above(folder: Path) -> list[Path]:
    """Folders holding a record, from `folder` up to the file system root, nearest first."""
    folder = folder.resolve()
    return [candidate for candidate in (folder, *folder.parents) if store_path(candidate).is_file()]


def _event_of(row: Mapping[str, Any]) -> str:
    counterexample = row.get("counterexample") if isinstance(row.get("counterexample"), Mapping) else {}
    return str(row.get("event_id") or counterexample.get("event_id") or "")


def _subject(row: Mapping[str, Any]) -> str:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), Mapping) else {}
    parts = [f"{key}={row[key]}" for key in _SUBJECT_KEYS if key in row]
    parts += [f"{key}={evidence[key]}" for key in _SUBJECT_KEYS if key in evidence]
    return ",".join(parts)


def _question(row: Mapping[str, Any]) -> list[str] | None:
    """The question a check answers for this row, in the check's own terms; None for rows judged by place and Guard."""
    code, scenario = row.get("code"), str(row.get("scenario_id") or "")
    if code == "EVENT_RELATION_UNMET":
        return ["relation", scenario, str(row.get("event_id") or ""), str(row.get("relation")), str(row.get("subject")),
                str(row.get("object"))]
    if code == "WORLD_RELATION_CONFLICT":
        who = row.get("subject") if row.get("relation") == "at" else row.get("object")
        return ["relation_conflict", scenario, str(row.get("relation")), str(who)]
    evidence = row.get("evidence") if isinstance(row.get("evidence"), Mapping) else {}
    if code == "MESH_HANDOFF_STATE_MISMATCH" and "fluent" in evidence:
        return ["handoff", str(row.get("edge_id") or ""), str(evidence["fluent"])]
    counterexample = row.get("counterexample") if isinstance(row.get("counterexample"), Mapping) else {}
    if code == "EVENT_PRECONDITION_UNMET" and counterexample:
        steps = counterexample.get("steps") if "steps" in counterexample else [counterexample]
        return ["precondition", *sorted(f"{step.get('scenario_id') or ''}|{step.get('event_id')}|"
                                        f"{','.join(sorted(map(str, step.get('missing_fluents', []))))}"
                                        for step in steps if isinstance(step, Mapping))]
    if code == "CLAIM_ASSERTION_FALSE" and "claim_row" in row:
        return ["claim", str(row["claim_row"]), _assertion(row.get("assertion"))]
    return None


def _assertion(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _claim_text(value: Any) -> str:
    """A claim row as a person reads it: `holds: door_unlocked, at: 21:00`."""
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, Mapping):
        return str(value)
    return ", ".join(f"{key}: {item}" for key, item in value.items())


def _fact(kind: str, subject: str, obj: str) -> str:
    return f"{subject} holds {obj}" if kind == "holds" else f"{subject} is at {obj}"


def _place(row: Mapping[str, Any], tree: bool) -> dict[str, str]:
    """Where in its file a row was found; a tree's own rows also name their chapter."""
    return {"edge_id": str(row.get("edge_id") or ""), "event_id": _event_of(row),
            "node_id": str(row.get("node_id") or "") if tree else "", "subject": _subject(row)}


def _key(unit_path: str, code: Any, place: Mapping[str, str]) -> tuple[str, ...]:
    """Kind, file and place; never times, messages or report order."""
    return (unit_path, str(code), place["edge_id"], place["event_id"], place["node_id"], place["subject"])


def _item_key(folder: Path, item: Mapping[str, Any], unit_key: str | None = None) -> tuple[str, ...]:
    """The entry's key in its own file, or, with `unit_key`, the key the same contradiction has in that file."""
    if unit_key is None:
        unit, _, node = item["unit"].partition("#")
        unit_key = str((folder / unit).resolve()) + (f"#{node}" if node else "")
    return _key(unit_key, item["code"], {name: str(item.get(name) or "") for name in ("edge_id", "event_id", "node_id", "subject")})


def _file_of(item: Mapping[str, Any]) -> str:
    """The entry's file as the record names it, relative to the record's folder (without an inline chapter)."""
    return item["unit"].partition("#")[0]


def _world(kind: str, identity: str) -> str | None:
    return f"{kind} {identity}" if identity.strip() else None


def _unit_key(unit: Unit) -> str:
    return str(unit.path) + (f"#{unit.node}" if unit.node else "")


def _last_change(contract, fluent):
    """The event of a chapter that last started or ended a fact, or None when the chapter starts with it."""
    events = [event for event in contract.inputs.get("events", []) if isinstance(event, Mapping)]
    if any("at" not in event for event in events):
        return None
    model = contract.inputs.get("event_model", {})
    initial = model.get("initial_states", []) if isinstance(model, Mapping) else []
    found = None
    for event, before, after in event_replay(events, initial, skip_illegal=True):
        if (fluent in before) != (fluent in after):
            found = event
    return found


def _chapter(mesh, node_id):
    node = next((n for n in mesh.nodes if n.model_id == node_id), None)
    return {"chapter": node_id, **({"source": node.source} if node is not None and node.source else {})}


def established_by(row: Mapping[str, Any], unit: Unit) -> list[dict[str, Any]]:
    """Which chapters, and where in them, set up the facts that disagree."""
    mesh = unit.mesh
    edges = {edge.edge_id: edge for edge in mesh.edges} if mesh is not None and unit.tree else {}
    edge = edges.get(row.get("edge_id"))
    if edge is not None:
        contracts = {n.model_id: n.contract for n in mesh.nodes if n.contract is not None}
        result = []
        evidence = row.get("evidence") or {}
        fluent = evidence.get("fluent")
        for side, node_id in (("end of", edge.from_id), ("start of", edge.to_id)):
            entry = {**_chapter(mesh, node_id), "where": f"{side} {node_id}"}
            if fluent and side == "end of" and node_id in contracts:
                event = _last_change(contracts[node_id], fluent)
                if event is not None:
                    entry["event_id"] = event.get("event_id")
                    if event.get("source"):
                        entry["where"] = f"{event['source']} ({event.get('event_id')})"
            elif fluent and side == "start of":
                entry["where"] = f"start of {node_id}: {fluent} " + ("holds" if evidence.get("to_initial") else "does not hold")
            result.append(entry)
        return result
    entry = dict(unit.chapter)
    start = f"start of {entry.get('chapter')}"
    if row.get("code") == "EVENT_RELATION_UNMET":
        need = _fact(str(row.get("relation")), str(row.get("subject")), str(row.get("object")))
        own = f"{row['source']} ({row.get('event_id')})" if row.get("source") else str(row.get("event_id"))
        result = [{**entry, "event_id": row.get("event_id"), "where": f"{own} needs: {need}"}]
        for fluent, info in sorted((row.get("established_by") or {}).items()):
            where = f"{start}: {info['fact']}" if info.get("event_id") is None else f"{info['where']} makes: {info['fact']}"
            result.append({**entry, "fact": fluent, **({"event_id": info["event_id"]} if info.get("event_id") else {}),
                           "where": where})
        ended = row.get("ended_by")
        if ended:
            result.append({**entry, "event_id": ended.get("event_id"), "where": f"{ended['where']} ends: {ended['fact']}"})
        return result
    if row.get("established_by"):
        return [{**entry, "fact": fact, **({"event_id": info["event_id"]} if info.get("event_id") else {}),
                 "where": start if info.get("event_id") is None else
                 (f"{info['source']} ({info['event_id']})" if info.get("source") else str(info["event_id"]))}
                for fact, info in row["established_by"].items()]
    counterexample = row.get("counterexample") if isinstance(row.get("counterexample"), Mapping) else {}
    source = row.get("source") or counterexample.get("source")
    return [{**entry, **({"where": source} if source else {})}]


def summary(row: Mapping[str, Any]) -> str:
    """One line in the report's own words."""
    evidence = row.get("evidence") if isinstance(row.get("evidence"), Mapping) else {}
    if row.get("code") == "MESH_HANDOFF_STATE_MISMATCH" and "fluent" in evidence:
        return (f"{evidence['fluent']} is {'true' if evidence.get('from_end') else 'false'} at the end of the earlier "
                f"chapter but {'true' if evidence.get('to_initial') else 'false'} at the start of the next")
    if row.get("code") == "CLAIM_ASSERTION_FALSE" and "claim_row" in row:
        return f"claim row {row['claim_row']} is false: {_claim_text(_assertion(row.get('assertion')))}"
    counterexample = row.get("counterexample") if isinstance(row.get("counterexample"), Mapping) else {}
    if row.get("code") == "EVENT_PRECONDITION_UNMET" and counterexample.get("missing_fluents"):
        return f"{counterexample.get('event_id')} at {counterexample.get('at')} needs {', '.join(counterexample['missing_fluents'])}"
    return str(row.get("message") or row.get("reason") or row.get("code"))


def _where(item: Mapping[str, Any]) -> str:
    if item.get("edge_id"):
        return f"hand-over {item['edge_id']}"
    if item.get("event_id"):
        return f"event {item['event_id']}"
    if item.get("node_id"):
        return f"chapter {item['node_id']}"
    return item.get("subject") or "the file"


def _judge(item: Mapping[str, Any], unit: Unit, unit_name: str, run: str) -> tuple[bool, str]:
    """(closed, how) for an entry whose file this run re-checked without finding the same row."""
    edge, event, node = item.get("edge_id") or "", item.get("event_id") or "", item.get("node_id") or ""
    question = list(item.get("question") or [])
    if question:
        again = sorted({str(row.get("event_id") or row.get("edge_id") or "") for row in unit.rows
                        if row.get("status") == "FAIL" and _question(row) == question})
        if again:
            return False, f"still failing: {item['code']} at {', '.join(name or 'the start' for name in again)}"
    if unit.tree and edge and edge not in unit.edges:
        return True, f"hand-over {edge} is no longer in {unit_name}"
    if unit.tree and node and node not in unit.nodes:
        return True, f"chapter {node} is no longer in {unit_name}"
    if event and event not in unit.events and question[:1] != ["relation_conflict"]:
        return True, f"event {event} is no longer in {unit_name}"
    place = {name: str(item.get(name) or "") for name in ("edge_id", "event_id", "node_id", "subject")}
    blockers = []
    for row in unit.rows:
        found = _place(row, unit.tree)
        if question[:1] == ["relation_conflict"]:
            same = False  # the conflict question is answered below, wherever it is found
        elif edge:
            same = found["edge_id"] == edge
        elif event:
            same = found["event_id"] == event
        elif place["subject"]:
            same = found["subject"] == place["subject"] and found["node_id"] == node
        else:
            same = str(row.get("code")) == item["code"] and found["node_id"] == node
        if same:
            blockers.append(row)
    if blockers:
        failing = sorted({str(row["code"]) for row in blockers if row.get("status") == "FAIL"})
        if failing:
            return False, f"still failing on {_where(item)}: {', '.join(failing)}"
        return False, (f"not re-checked: {' and '.join(sorted({str(row.get('status')) for row in blockers}))} "
                       f"{', '.join(sorted({str(row['code']) for row in blockers}))} on {_where(item)}")
    if item.get("guard") and item["guard"] not in unit.guards:
        return False, f"not re-checked: {item['guard']} does not run on {unit_name} now"
    if question:
        return _answer(question, unit, run)
    if item.get("guard"):
        return True, f"re-checked by {run}: {item['guard']} ran on {unit_name} and found no problem on {_where(item)}"
    return True, f"re-checked by {run}: no problem on {_where(item)} now"


def _answer(question: list[str], unit: Unit, run: str) -> tuple[bool, str]:
    """Close only on the check's own answer to the same question; stay open while the check does not reach it."""
    kind = question[0]
    if kind == "relation":
        scenario, event, relation, subject, obj = question[1:]
        fact = _fact(relation, subject, obj)
        asked, unchecked = unit.relation_questions.get((scenario, event), (frozenset(), ("the relation check did not reach it",)))
        if (relation, subject, obj) in asked:
            return True, f"re-checked by {run}: {fact} just before event {event} now"
        if unchecked:
            return False, f"not re-checked: whether {fact} before event {event}: {'; '.join(unchecked)}"
        now = ", ".join(sorted(_fact(*other) for other in asked)) or "nothing"
        return True, f"re-checked by {run}: event {event} no longer needs {fact} (it now needs: {now})"
    if kind == "relation_conflict":
        scenario, relation, who = question[1:]
        what = f"{who}'s {'places' if relation == 'at' else 'holders'}"
        asked, why = unit.conflict_questions.get(scenario, (frozenset(), "the conflict check did not reach it"))
        if why:
            return False, f"not re-checked: {what}: {why}"
        if (relation, who) in asked:
            return True, f"re-checked by {run}: {what} never overlap now"
        return True, f"re-checked by {run}: world_model.relations no longer gives {who} two {'places' if relation == 'at' else 'holders'}"
    if kind == "precondition":
        held, gone, waiting = [], [], []
        for step in question[1:]:
            scenario, event, missing = step.split("|", 2)
            needed = [name for name in missing.split(",") if name]
            asked, why = unit.precondition_questions.get((scenario, event), (frozenset(), "the event is no longer there"))
            if why:
                waiting.append(f"{event}: {why}")
            elif set(needed) <= asked:
                held.append(f"{event} has {', '.join(needed)}")
            else:
                gone.append(f"{event} no longer requires {', '.join(name for name in needed if name not in asked)}")
        if waiting:
            return False, f"not re-checked: {'; '.join(waiting)}"
        return True, f"re-checked by {run}: " + "; ".join([*(f"{text} now" for text in held), *gone])
    if kind == "claim":
        index, assertion = question[1:]
        now, _status = unit.claim_rows.get(index, ("", ""))
        if now != assertion:
            return True, (f"claim row {index} ({_claim_text(assertion)}) is no longer in the claim"
                          + (f"; row {index} is now ({_claim_text(now)})" if now else ""))
        return True, f"re-checked by {run}: claim row {index} ({_claim_text(assertion)}) holds now"
    edge, fluent = question[1:]
    compared, why = unit.handoff_questions.get(edge, (frozenset(), "it is no longer a continues edge between two chapters"))
    if why:
        return False, f"not re-checked: hand-over {edge}: {why}"
    if fluent in compared:
        return True, f"re-checked by {run}: {fluent} agrees across hand-over {edge} now"
    return True, f"re-checked by {run}: the chapters of hand-over {edge} no longer both name {fluent}"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write(folder: Path, data: Mapping[str, Any]) -> None:
    path = store_path(folder)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise RecordError(path, f"could not write: {exc}") from exc


def update(units: list[Unit], *, checked: Path, run: str, takes_over: Path | None = None) -> dict[str, Any]:
    """Keep this run's contradictions and re-check the open ones of the files it covered; return what to print.

    `checked` is the file the command was given; `run` names the command for the closing lines; `takes_over` is a gone
    file whose entries the person gives to `checked` (`--takes-over`)."""
    folders: list[Path] = []
    for start in [checked.resolve().parent, *[unit.path.parent for unit in units]]:
        folders.extend(folder for folder in records_above(start) if folder not in folders)
    records = {folder: _load(folder) for folder in folders}
    covered = {_unit_key(unit): unit for unit in units}
    taken = _take_over(records, takes_over, checked, covered) if takes_over is not None else []
    found: dict[tuple[str, ...], tuple[Unit, dict[str, Any]]] = {}
    for unit in units:
        for row in unit.rows:
            if row.get("status") == "FAIL":
                found.setdefault(_key(_unit_key(unit), row.get("code"), _place(row, unit.tree)), (unit, row))
    now = _now()
    seen: dict[tuple[str, ...], dict[str, Any]] = {}   # a key this run found -> the open entry that holds it
    changed: set[Path] = set()
    closed: list[dict[str, Any]] = []
    moved: list[dict[str, Any]] = []
    gone: list[tuple[Path, dict[str, Any]]] = []
    dropped: set[int] = set()
    for folder, data in records.items():
        for item in data["open"]:
            key = _item_key(folder, item)
            if key[0] in covered:
                unit = covered[key[0]]
                item.pop("gone_since", None)  # the file is back under its last path
                changed.add(folder)
                if key in found:
                    seen[key] = item
                    item.update(last_seen=now, runs=item.get("runs", 1) + 1)
                    item.pop("held", None)
                    continue
                is_closed, how = _judge(item, unit, unit.name(folder), run)
                if is_closed:
                    closed.append({**item, "closed": now, "how": how, "folder": str(folder)})
                    dropped.add(id(item))
                else:
                    item.update(held=how, last_checked=now)
            elif not (folder / _file_of(item)).is_file():
                gone.append((folder, item))  # judged below, once every entry still in its own file is matched
            elif "gone_since" in item:  # back under its last path, but this run did not check it
                item.pop("gone_since")
                item.pop("held", None)
                changed.add(folder)
    for folder, item in gone:
        _follow(folder, item, units, found, seen, run, now, moved, dropped, changed)
    for folder, data in records.items():
        data["open"] = [item for item in data["open"] if id(item) not in dropped]
        data["resolved"] = (data["resolved"] + [{k: v for k, v in item.items() if k != "folder"}
                                                for item in closed if item["folder"] == str(folder)])[-50:]
    opened = []
    fresh = [(key, unit, row) for key, (unit, row) in found.items() if key not in seen]
    if fresh:
        nearest = records_above(checked.resolve().parent)
        target = nearest[0] if nearest else checked.resolve().parent
        data = records.setdefault(target, {"open": [], "resolved": []})
        for _key_value, unit, row in fresh:
            place = _place(row, unit.tree)
            item = {"unit": unit.name(target), "code": str(row.get("code")), **{k: v for k, v in place.items() if v},
                    "summary": summary(row), "established_by": established_by(row, unit), "found_by": run,
                    "first_seen": now, "last_seen": now, "runs": 1}
            if row.get("guard"):
                item["guard"] = row["guard"]
            if _question(row):
                item["question"] = _question(row)
            if unit.world is not None:
                item["world"] = unit.world
            data["open"].append(item)
            opened.append(item)
        changed.add(target)
    for folder in records:
        if folder in changed:
            _write(folder, records[folder])
    still_open = [{**item, "folder": str(folder)} for folder, data in records.items() for item in data["open"]]
    return {"opened": opened, "closed": closed, "moved": moved, "taken": taken, "open": still_open}


def _take_over(records, old: Path, checked: Path, covered: Mapping[str, Unit]) -> list[dict[str, Any]]:
    """`--takes-over OLD`: the person says the checked file is the gone file OLD under a new path. Every open entry of
    OLD (and of its inline chapters) moves to the checked file, keeping its history, before this run judges it like any
    entry of that file; one that file already holds for the same contradiction keeps both histories. Anything that
    cannot be done so is an input error, raised before the record changes."""
    old, new = old.resolve(), checked.resolve()
    if old.exists():
        raise WorldInputError(f"--takes-over {old}: that file still exists; only the entries of a file that is gone can "
                              "be taken over")
    planned = []
    for folder, data in records.items():
        if not new.is_relative_to(folder):
            continue
        for item in data["open"]:
            unit, _, node = item["unit"].partition("#")
            if (folder / unit).resolve() != old:
                continue
            target = covered.get(str(new) + (f"#{node}" if node else ""))
            if target is None:
                raise WorldInputError(f"--takes-over {old}: its entry {item['unit']} is about inline chapter {node}, "
                                      f"which {new.name} does not have")
            if "world" in item and item["world"] != target.world:
                raise WorldInputError(f"--takes-over {old}: its entries were recorded for "
                                      f"{item['world'] or 'a world without an id'}, but {target.name(folder)} checks "
                                      f"{target.world or 'a world without an id'}")
            planned.append((folder, item, target))
    if not planned:
        raise WorldInputError(f"--takes-over {old}: no open contradiction recorded for {new.name}'s folder or a folder "
                              "above it belongs to that file")
    taken = []
    for folder, item, target in planned:
        last = item["unit"]
        item.update(unit=target.name(folder), moved_from=[*item.get("moved_from", []), last])
        item.pop("held", None)
        item.pop("gone_since", None)
        data = records[folder]
        key = _item_key(folder, item)
        keeper = next((other for other in data["open"] if other is not item and _item_key(folder, other) == key), None)
        if keeper is not None:  # the checked file already has this contradiction on record: one entry keeps both
            keeper.update(first_seen=min(keeper["first_seen"], item["first_seen"]), runs=keeper["runs"] + item["runs"],
                          moved_from=[*item["moved_from"], *keeper.get("moved_from", [])])
            data["open"].remove(item)
        taken.append({**(keeper or item), "from": _file_of({"unit": last})})
    return taken


def _takes_over(unit: Unit, path: str, last: str) -> str:
    """The command with which the person says the file at `path` (`unit`'s file, or one like it) is the gone file
    `last` under a new path."""
    check = f"mesh-check --mesh {path}" if unit.tree or unit.node else f"check --contract {path}"
    return f"`worldguard {check} --takes-over {last}` in the record's folder"


def _follow(folder, item, units, found, seen, run, now, moved, dropped, changed) -> None:
    """An entry whose file is gone stays open, saying so with the path it was last seen at. A run that finds the same
    contradiction in exactly one file of its world (the file's contract_id, or the tree's mesh_id) under the same
    record moves the entry there; found in two or more, it follows none and names them. A pass in such a file closes
    nothing (it may be another draft of the world): the entry says so and names the `--takes-over` command with which
    the person makes that file the new path."""
    last, world = _file_of(item), item.get("world")
    node = item["unit"].partition("#")[2]
    candidates = sorted((unit for unit in units if world is not None and unit.world == world and unit.node == node
                         and unit.path.is_relative_to(folder)), key=_unit_key)
    hits = [(unit, key) for unit in candidates for key in [_item_key(folder, item, _unit_key(unit))] if key in found]
    if len(hits) == 1:  # found in exactly one file of its world: that file is the new path
        (unit, key), = hits
        new = unit.name(folder)
        history = [*item.get("moved_from", []), item["unit"]]
        if key in seen:  # the new path already has this contradiction on record: one entry keeps both histories
            keeper = seen[key]
            keeper.update(first_seen=min(keeper["first_seen"], item["first_seen"]), runs=keeper["runs"] + item["runs"],
                          moved_from=[*history, *keeper.get("moved_from", [])])
            dropped.add(id(item))
        else:
            keeper = item
            item.update(unit=new, moved_from=history, last_seen=now, runs=item["runs"] + 1,
                        established_by=established_by(found[key][1], unit))
            item.pop("held", None)
            item.pop("gone_since", None)
            seen[key] = item
        moved.append({**keeper, "from": last})
        changed.add(folder)
        return
    if hits:
        held = (f"file gone: {last} no longer exists; the same contradiction is found in more than one file of {world} "
                f"this run checked ({', '.join(unit.name(folder) for unit, _key in hits)}), so it is not followed to any of "
                f"them; if one of them is {last} under a new path, run {_takes_over(hits[0][0], '<that file>', last)}")
    elif len(candidates) == 1:
        unit = candidates[0]
        new = unit.name(folder)
        passed, how = _judge(item, unit, new, run)
        found_there = f"passed in {new} ({how}), but a pass in another file does not close it" if passed else f"is in {new}, {how}"
        held = (f"file gone: {last} no longer exists; {world} {found_there}; if {new} is {last} under a new path, run "
                + _takes_over(unit, Path(os.path.relpath(unit.path, folder)).as_posix(), last))
    elif candidates:
        held = (f"file gone: {last} no longer exists; {world} is in more than one file this run checked "
                f"({', '.join(unit.name(folder) for unit in candidates)}), so it is not followed to any of them; if one "
                f"of them is {last} under a new path, run {_takes_over(candidates[0], '<that file>', last)}")
    elif world is not None:
        held = f"file gone: {last} no longer exists; it stays open until {world} is checked again under its new path"
    else:
        held = (f"file gone: {last} no longer exists; its world declared no contract_id or mesh_id, so it cannot be "
                "followed to a new path")
    if item.get("held") != held or "gone_since" not in item:
        item["held"] = held
        item.setdefault("gone_since", now)
        changed.add(folder)


def render(change: Mapping[str, Any]) -> str:
    """Lines a person reads first: what is still open, and what this run closed."""
    lines = []
    open_items = change["open"]
    if open_items:
        folders = sorted({item["folder"] for item in open_items})
        lines.append(f"open contradictions ({len(open_items)}; kept in "
                     + ", ".join(str(store_path(folder)) for folder in folders)
                     + " until a check of their file finds them fixed):")
        for item in open_items:
            origin = "; ".join(
                " ".join(str(part) for part in (entry.get("chapter"), f"({entry['source']})" if entry.get("source") else "",
                                                entry.get("where", "")) if part)
                for entry in item.get("established_by", []))
            note = f"; {item['held']}" if item.get("held") else ""
            lines.append(f"  {item['code']} [{item['unit']}] {item['summary']}" + (f" -- established by {origin}" if origin else "")
                         + f" (open since {item['first_seen']}{note})")
    for item in change["moved"]:
        lines.append(f"moved: {item['code']} [{item['unit']}] {item['summary']} -- {item['from']} is gone; the same "
                     f"contradiction is in {item['unit']}")
    for item in change["taken"]:
        lines.append(f"taken over: {item['code']} [{item['unit']}] {item['summary']} -- {item['from']} is gone; "
                     f"{_file_of(item)} takes over its entries, as --takes-over asked")
    for item in change["closed"]:
        lines.append(f"closed: {item['code']} [{item['unit']}] {item['summary']} -- {item['how']}")
    return "\n".join(lines)


def contract_units(path: str | Path, contract, report) -> list[Unit]:
    """The one file a `check --contract` (or a timeline or lifeline of it) re-checked."""
    path = Path(path).resolve()
    events = {str(event.get("event_id")): event for event in contract.inputs.get("events", [])
              if isinstance(event, Mapping) and event.get("event_id")}
    return [Unit(path=path, rows=list(report.gaps), guards=frozenset(report.checked.get("guards", [])), events=events,
                 chapter={"chapter": path.name}, world=_world("world", contract.contract_id), **_questions(contract, report))]


def _questions(contract, report) -> dict[str, Any]:
    """What this run's checks asked of one world, from the derivations the checks themselves use."""
    relations = parse_relations(contract.world_model.relations)
    events = [event for event in contract.inputs.get("events", []) if isinstance(event, Mapping)]
    return {"relation_questions": relation_coverage(contract.inputs, relations,
                                                    requires_checked="EventGuard" in report.derived_guards),
            "conflict_questions": conflict_coverage(contract.inputs, relations),
            "precondition_questions": precondition_coverage(events),
            "claim_rows": {str(row["index"]): (_assertion(row["assertion"]), str(row["status"]))
                           for row in report.claim_binding.get("assertions", [])}}


def mesh_units(path: str | Path, data: Mapping[str, Any], mesh, report) -> list[Unit]:
    """The tree file and every chapter file a `mesh-check` re-checked."""
    path = Path(path).resolve()
    contract_files = {str(node.get("model_id", "")): (path.parent / node["contract"]).resolve()
                      for node in data.get("nodes", []) if isinstance(node, Mapping) and isinstance(node.get("contract"), str)}
    from .mesh import handoff_fluents

    contracts = {n.model_id: n.contract for n in mesh.nodes if n.contract is not None}
    handoffs = {edge.edge_id: handoff_fluents(contracts[edge.from_id], contracts[edge.to_id]) for edge in mesh.edges
                if edge.relation == "continues" and edge.from_id in contracts and edge.to_id in contracts}
    units = [Unit(path=path, rows=[finding.to_dict() for finding in report.findings], edges=frozenset(e.edge_id for e in mesh.edges),
                  nodes=frozenset(n.model_id for n in mesh.nodes), mesh=mesh, tree=True, handoff_questions=handoffs,
                  world=_world("tree", mesh.mesh_id))]
    for node in mesh.nodes:
        node_report = report.node_reports.get(node.model_id)
        if node.contract is None or node_report is None:
            continue
        events = {str(event.get("event_id")): event for event in node.contract.inputs.get("events", [])
                  if isinstance(event, Mapping) and event.get("event_id")}
        file = contract_files.get(node.model_id)
        units.append(Unit(path=file or path, node="" if file else node.model_id, rows=list(node_report.gaps),
                          guards=frozenset(node_report.checked.get("guards", [])), events=events,
                          chapter={"chapter": node.model_id, **({"source": node.source} if node.source else {})},
                          world=_world("world", node.contract.contract_id), **_questions(node.contract, node_report)))
    merged: dict[str, Unit] = {}
    for unit in units:
        key = _unit_key(unit)
        if key in merged:  # one chapter file used by two nodes: every row of both runs counts, and only what both asked
            first = merged[key]
            merged[key] = Unit(path=first.path, node=first.node, rows=first.rows + unit.rows, guards=first.guards & unit.guards,
                               events=first.events, chapter=first.chapter, world=first.world,
                               relation_questions=_both(first.relation_questions, unit.relation_questions),
                               conflict_questions=_both(first.conflict_questions, unit.conflict_questions),
                               precondition_questions=_both(first.precondition_questions, unit.precondition_questions),
                               claim_rows={key: value for key, value in first.claim_rows.items()
                                           if unit.claim_rows.get(key) == value})
        else:
            merged[key] = unit
    return list(merged.values())


def _both(left: Mapping[Any, Any], right: Mapping[Any, Any]) -> dict[Any, Any]:
    """Questions both runs asked; reasons either run gave for not asking."""
    result = {}
    for key in set(left) | set(right):
        (asked_left, why_left), (asked_right, why_right) = (left.get(key, (frozenset(), "not in one of the runs")),
                                                            right.get(key, (frozenset(), "not in one of the runs")))
        if isinstance(why_left, tuple):
            result[key] = (asked_left & asked_right, tuple(dict.fromkeys((*why_left, *why_right))))
        else:
            result[key] = (asked_left & asked_right, "; ".join(dict.fromkeys(reason for reason in (why_left, why_right) if reason)))
    return result


__all__ = ["STORE", "RecordError", "Unit", "store_path", "records_above", "established_by", "summary", "update", "render",
           "contract_units", "mesh_units"]
