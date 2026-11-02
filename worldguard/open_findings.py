"""Contradictions stay on record, with the chapters that established them, until a check finds them fixed.

Every `check`, `mesh-check`, `timeline` and `lifeline` of a file keeps the FAIL rows it found in a record,
`.worldguard/open.json`: the nearest one in the checked file's folder or a folder above it, or a new one in the
file's folder. An entry belongs to the file the contradiction lives in (a chapter's world file, or the tree file for a
hand-over between chapters), and every later command whose files lie under a record's folder prints the entries
that record holds.

An entry closes only when a later run re-checks its file and the place it was found (the event, the hand-over, the
claim row) has no problem left, is not exempted and is still checked by the Guard that found it. Otherwise it stays
open and says why it was not re-checked. An entry whose file, chapter, hand-over or event is gone closes and says so.
A record that cannot be read or written stops the command (RecordError); nothing falls back to a run without it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from .semantic import event_replay

STORE = Path(".worldguard") / "open.json"
_SUBJECT_KEYS = ("fluent", "color", "variable", "relation", "subject", "object", "claim_row", "variant_id")
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


def _place(row: Mapping[str, Any], tree: bool) -> dict[str, str]:
    """Where in its file a row was found; a tree's own rows also name their chapter."""
    return {"edge_id": str(row.get("edge_id") or ""), "event_id": _event_of(row),
            "node_id": str(row.get("node_id") or "") if tree else "", "subject": _subject(row)}


def _key(unit_path: str, code: Any, place: Mapping[str, str]) -> tuple[str, ...]:
    """Kind, file and place; never times, messages or report order."""
    return (unit_path, str(code), place["edge_id"], place["event_id"], place["node_id"], place["subject"])


def _item_key(folder: Path, item: Mapping[str, Any]) -> tuple[str, ...]:
    unit, _, node = item["unit"].partition("#")
    absolute = str((folder / unit).resolve()) + (f"#{node}" if node else "")
    return _key(absolute, item["code"], {name: str(item.get(name) or "") for name in ("edge_id", "event_id", "node_id", "subject")})


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
    if row.get("established_by"):
        return [{**entry, "fact": fact, "where": (info.get("source") or info.get("event_id") or "start")}
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
    """(closed, how) for an entry whose file this run re-checked without finding the same contradiction."""
    edge, event, node = item.get("edge_id") or "", item.get("event_id") or "", item.get("node_id") or ""
    if unit.tree and edge and edge not in unit.edges:
        return True, f"hand-over {edge} is no longer in {unit_name}"
    if unit.tree and node and node not in unit.nodes:
        return True, f"chapter {node} is no longer in {unit_name}"
    if event and event not in unit.events:
        return True, f"event {event} is no longer in {unit_name}"
    place = {name: str(item.get(name) or "") for name in ("edge_id", "event_id", "node_id", "subject")}
    blockers = []
    for row in unit.rows:
        found = _place(row, unit.tree)
        if edge:
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
    if event and "actor_state_free" in unit.events[event]:
        return False, f"not re-checked: event {event} is marked actor_state_free ({unit.events[event]['actor_state_free']})"
    if item.get("guard") and item["guard"] not in unit.guards:
        return False, f"not re-checked: {item['guard']} does not run on {unit_name} now"
    return True, f"re-checked by {run}: {_where(item)} passes now"


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write(folder: Path, data: Mapping[str, Any]) -> None:
    path = store_path(folder)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except OSError as exc:
        raise RecordError(path, f"could not write: {exc}") from exc


def update(units: list[Unit], *, checked: Path, run: str) -> dict[str, Any]:
    """Keep this run's contradictions and re-check the open ones of the files it covered; return what to print.

    `checked` is the file the command was given; `run` names the command for the closing lines."""
    folders: list[Path] = []
    for start in [checked.resolve().parent, *[unit.path.parent for unit in units]]:
        folders.extend(folder for folder in records_above(start) if folder not in folders)
    records = {folder: _load(folder) for folder in folders}
    covered = {_unit_key(unit): unit for unit in units}
    found: dict[tuple[str, ...], tuple[Unit, dict[str, Any]]] = {}
    for unit in units:
        for row in unit.rows:
            if row.get("status") == "FAIL":
                found.setdefault(_key(_unit_key(unit), row.get("code"), _place(row, unit.tree)), (unit, row))
    now = _now()
    seen: set[tuple[str, ...]] = set()
    changed: set[Path] = set()
    closed: list[dict[str, Any]] = []
    for folder, data in records.items():
        kept = []
        for item in data["open"]:
            key = _item_key(folder, item)
            unit_file = folder / item["unit"].partition("#")[0]
            if key[0] in covered:
                unit = covered[key[0]]
                if key in found:
                    seen.add(key)
                    item.update(last_seen=now, runs=item.get("runs", 1) + 1)
                    item.pop("held", None)
                    kept.append(item)
                    changed.add(folder)
                    continue
                is_closed, how = _judge(item, unit, unit.name(folder), run)
            elif not unit_file.is_file():
                is_closed, how = True, f"{item['unit'].partition('#')[0]} no longer exists"
            else:
                kept.append(item)  # this run did not check that file
                continue
            changed.add(folder)
            if is_closed:
                closed.append({**item, "closed": now, "how": how, "folder": str(folder)})
            else:
                item.update(held=how, last_checked=now)
                kept.append(item)
        data["open"] = kept
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
            data["open"].append(item)
            opened.append(item)
        changed.add(target)
    for folder in records:
        if folder in changed:
            _write(folder, records[folder])
    still_open = [{**item, "folder": str(folder)} for folder, data in records.items() for item in data["open"]]
    return {"opened": opened, "closed": closed, "open": still_open}


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
    for item in change["closed"]:
        lines.append(f"closed: {item['code']} [{item['unit']}] {item['summary']} -- {item['how']}")
    return "\n".join(lines)


def contract_units(path: str | Path, contract, report) -> list[Unit]:
    """The one file a `check --contract` (or a timeline or lifeline of it) re-checked."""
    path = Path(path).resolve()
    events = {str(event.get("event_id")): event for event in contract.inputs.get("events", [])
              if isinstance(event, Mapping) and event.get("event_id")}
    return [Unit(path=path, rows=list(report.gaps), guards=frozenset(report.checked.get("guards", [])), events=events,
                 chapter={"chapter": path.name})]


def mesh_units(path: str | Path, data: Mapping[str, Any], mesh, report) -> list[Unit]:
    """The tree file and every chapter file a `mesh-check` re-checked."""
    path = Path(path).resolve()
    contract_files = {str(node.get("model_id", "")): (path.parent / node["contract"]).resolve()
                      for node in data.get("nodes", []) if isinstance(node, Mapping) and isinstance(node.get("contract"), str)}
    units = [Unit(path=path, rows=[finding.to_dict() for finding in report.findings], edges=frozenset(e.edge_id for e in mesh.edges),
                  nodes=frozenset(n.model_id for n in mesh.nodes), mesh=mesh, tree=True)]
    for node in mesh.nodes:
        node_report = report.node_reports.get(node.model_id)
        if node.contract is None or node_report is None:
            continue
        events = {str(event.get("event_id")): event for event in node.contract.inputs.get("events", [])
                  if isinstance(event, Mapping) and event.get("event_id")}
        file = contract_files.get(node.model_id)
        units.append(Unit(path=file or path, node="" if file else node.model_id, rows=list(node_report.gaps),
                          guards=frozenset(node_report.checked.get("guards", [])), events=events,
                          chapter={"chapter": node.model_id, **({"source": node.source} if node.source else {})}))
    merged: dict[str, Unit] = {}
    for unit in units:
        key = _unit_key(unit)
        if key in merged:  # one chapter file used by two nodes: every row of both runs counts
            first = merged[key]
            merged[key] = Unit(path=first.path, node=first.node, rows=first.rows + unit.rows, guards=first.guards & unit.guards,
                               events=first.events, chapter=first.chapter)
        else:
            merged[key] = unit
    return list(merged.values())


__all__ = ["STORE", "RecordError", "Unit", "store_path", "records_above", "established_by", "summary", "update", "render",
           "contract_units", "mesh_units"]
