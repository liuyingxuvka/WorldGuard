"""Contradictions a tree check found stay on record, with the chapters that established them, until resolved.

`mesh-check` records every FAIL row of the tree in `.worldguard/open.json` next to the mesh file. Every later
`check`, `mesh-check` or `timeline` on a file in that folder shows the open ones. A contradiction closes only when a
`mesh-check` of the same tree no longer finds it; that run says once how it closed. Runs on other files never close it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from .semantic import event_replay, fluent_values

STORE = Path(".worldguard") / "open.json"
_SUBJECT_KEYS = ("fluent", "color", "variable", "relation", "subject", "object", "claim_row", "variant_id")


def store_path(folder: str | Path) -> Path:
    return Path(folder) / STORE


def load(folder: str | Path) -> dict[str, Any]:
    """The folder's record; a folder without one has nothing open. A record that cannot be read is an error."""
    path = store_path(folder)
    if not path.exists():
        return {"open": [], "resolved": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("open"), list) or not isinstance(data.get("resolved"), list):
        raise ValueError(f"{path} is not a WorldGuard record of open contradictions")
    return data


def _subject(row: Mapping[str, Any]) -> str:
    evidence = row.get("evidence") if isinstance(row.get("evidence"), Mapping) else {}
    parts = [f"{key}={row[key]}" for key in _SUBJECT_KEYS if key in row]
    parts += [f"{key}={evidence[key]}" for key in _SUBJECT_KEYS if key in evidence]
    counterexample = row.get("counterexample") if isinstance(row.get("counterexample"), Mapping) else {}
    if counterexample.get("event_id"):
        parts.append(f"event={counterexample['event_id']}")
    return ",".join(parts)


def fingerprint(scope: str, row: Mapping[str, Any]) -> str:
    """Kind, place in the tree and subject; never times, messages or report order."""
    return "|".join([scope, str(row.get("code")), str(row.get("node_id") or ""), str(row.get("edge_id") or ""),
                     str(row.get("event_id") or ""), _subject(row)])


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
    node = next((n for n in mesh.nodes if n.model_id == node_id), None) if mesh is not None else None
    return {"chapter": node_id, **({"source": node.source} if node is not None and node.source else {})}


def established_by(row: Mapping[str, Any], mesh=None) -> list[dict[str, Any]]:
    """Which chapters, and where in them, set up the facts that disagree."""
    edges = {edge.edge_id: edge for edge in mesh.edges} if mesh is not None else {}
    contracts = {n.model_id: n.contract for n in mesh.nodes if n.contract is not None} if mesh is not None else {}
    edge = edges.get(row.get("edge_id"))
    if edge is not None:
        result = []
        fluent = (row.get("evidence") or {}).get("fluent")
        for side, node_id in (("end of", edge.from_id), ("start of", edge.to_id)):
            entry = {**_chapter(mesh, node_id), "where": f"{side} {node_id}"}
            if fluent and side == "end of" and node_id in contracts:
                event = _last_change(contracts[node_id], fluent)
                if event is not None:
                    entry["event_id"] = event.get("event_id")
                    if event.get("source"):
                        entry["where"] = f"{event['source']} ({event.get('event_id')})"
            elif fluent and side == "start of":
                entry["where"] = f"start of {node_id}: {fluent} " + ("holds" if (row.get("evidence") or {}).get("to_initial") else "does not hold")
            result.append(entry)
        return result
    node_id = row.get("node_id")
    entry = _chapter(mesh, node_id) if node_id else {"chapter": None}
    if row.get("established_by"):
        return [{**entry, "fact": fact, "where": (info.get("source") or info.get("event_id") or "start")}
                for fact, info in row["established_by"].items()]
    source = row.get("source") or ((row.get("counterexample") or {}).get("source") if isinstance(row.get("counterexample"), Mapping) else None)
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


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record(folder: str | Path, scope: str, rows: list[Mapping[str, Any]], *, mesh=None, exists=None) -> dict[str, Any]:
    """Update the folder's record from one complete tree check of `scope`; return what changed."""
    data = load(folder)
    now = _now()
    found = {}
    for row in rows:
        if row.get("status") == "FAIL":
            found.setdefault(fingerprint(scope, row), row)
    kept, closed = [], []
    for item in data["open"]:
        if item["scope"] != scope or item["id"] in found:
            if item["id"] in found:
                item.update(last_seen=now, runs=item.get("runs", 1) + 1)
            kept.append(item)
            continue
        gone = exists is not None and not exists(item)
        closed.append({**item, "closed": now, "how": "its chapter or event is no longer in the tree" if gone else "no longer found"})
    known = {item["id"] for item in kept}
    opened = []
    for key, row in found.items():
        if key in known:
            continue
        counterexample = row.get("counterexample") if isinstance(row.get("counterexample"), Mapping) else {}
        item = {"id": key, "scope": scope, "code": row.get("code"), "node_id": row.get("node_id") or None,
                "edge_id": row.get("edge_id") or None, "event_id": row.get("event_id") or counterexample.get("event_id") or None,
                "summary": summary(row), "established_by": established_by(row, mesh), "first_seen": now, "last_seen": now, "runs": 1}
        kept.append(item)
        opened.append(item)
    data["open"] = kept
    data["resolved"] = (data["resolved"] + closed)[-50:]
    if data["open"] or closed or store_path(folder).exists():
        path = store_path(folder)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"opened": opened, "closed": closed, "open": kept}


def render(open_items: list[Mapping[str, Any]], closed: list[Mapping[str, Any]] = (), *, where: str = "") -> str:
    """Lines a person reads first: what is still open, and what this run closed."""
    lines = []
    if open_items:
        lines.append(f"open contradictions ({len(open_items)}, recorded by mesh-check{' in ' + where if where else ''}; "
                     "shown until a mesh-check of the same tree no longer finds them):")
        for item in open_items:
            origin = "; ".join(
                " ".join(str(part) for part in (entry.get("chapter"), f"({entry['source']})" if entry.get("source") else "",
                                                entry.get("where", "")) if part)
                for entry in item.get("established_by", []))
            lines.append(f"  {item['code']} [{item['scope']}] {item['summary']}" + (f" -- established by {origin}" if origin else "")
                         + f" (open since {item['first_seen']})")
    for item in closed:
        lines.append(f"closed: {item['code']} [{item['scope']}] {item['summary']} -- {item['how']}")
    return "\n".join(lines)


__all__ = ["STORE", "store_path", "load", "fingerprint", "established_by", "summary", "record", "render"]
