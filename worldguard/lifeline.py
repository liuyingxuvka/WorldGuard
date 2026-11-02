"""One character's or one thing's life, drawn from the world model for a discussion with the owner.

The picture is computed, never drawn by hand: the facts `world_model.relations` declares about the entity, replayed
event by event through each chapter in reading order, and only the events the entity takes part in, whose effects
change those facts, or where a problem about the entity is found. A problem of the native reports is marked where it
happens (a conflict at the events that started the clashing facts), on the picture of each entity it is about: the
people, things and places of the declared facts it names (the fact an event needs, the facts that clash, the facts an
event lacks). A problem that names no declared fact is about the event itself and is marked on every picture that
draws the event. Everything else is left out, and the text under the picture says what was left out, including the
problems at drawn steps that are about others.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .relations import event_things, parse_relations
from .semantic import event_replay, fluent_values
from .errors import WorldInputError

DEFAULT_LIMIT = 12  # boxes a person can read at a glance; more are folded, never dropped silently


def _describe(relation, entity):
    kind, subject, obj = relation
    if kind == "holds":
        return f"holds {obj}" if subject == entity else f"held by {subject}"
    return f"at {obj}" if subject == entity else f"{subject} here"


def _facts(relations, entity):
    return {fluent: relation for fluent, relation in relations.items() if entity in relation[1:]}


def _involves(event, entity, facts):
    # For the picture an event also involves the entity when it needs one of its facts; only checks distrust requires.
    changed = {name for key in ("initiates", "terminates", "requires") for name in fluent_values(event.get(key))}
    return (event.get("actor") == entity or entity in event.get("with", []) or entity in event_things(event)
            or event.get("place") == entity or bool(changed & set(facts)))


def _about(row, relations):
    """The entities of the declared facts a problem row names; empty when it names none."""
    counterexample = row.get("counterexample") or {}
    evidence = row.get("evidence") or {}
    fluents = [*row.get("fluents", []), row.get("fluent"), *counterexample.get("missing_fluents", []), evidence.get("fluent")]
    named = {entity for fluent in fluents if fluent in relations for entity in relations[fluent][1:]}
    return named | {row[key] for key in ("subject", "object") if row.get(key)}


def _found_at(row):
    """The events a problem row is found at: its event, every event that caused it (a conflict started by two events
    of one instant names both), or its counterexample's event."""
    return {row.get("event_id"), *row.get("event_ids", []), (row.get("counterexample") or {}).get("event_id")} - {None}


def _state(holding, facts, entity):
    return sorted(_describe(facts[fluent], entity) for fluent in holding if fluent in facts)


def _chapters(contract=None, mesh=None):
    """(chapter id, chapter source, contract) in reading order: continues edges first, then the remaining nodes."""
    if contract is not None:
        return [(None, "", contract)]
    nodes = {node.model_id: node for node in mesh.nodes if node.contract is not None}
    following = {edge.from_id: edge.to_id for edge in mesh.edges if edge.relation == "continues"}
    preceded = set(following.values())
    order = []
    for start in [node.model_id for node in mesh.nodes if node.model_id in following and node.model_id not in preceded]:
        current = start
        while current is not None and current not in order:
            order.append(current)
            current = following.get(current)
    order += [node.model_id for node in mesh.nodes if node.model_id not in order]
    return [(node_id, nodes[node_id].source, nodes[node_id].contract) for node_id in order if node_id in nodes]


def lifeline(entity: str, *, contract=None, mesh=None, report=None, limit: int | None = DEFAULT_LIMIT) -> dict[str, Any]:
    """Boxes (the entity's declared facts), arrows (events and chapter handoffs) and what was left out."""
    rows = report.to_dict()["gaps"] if report is not None else []
    boxes: list[dict[str, Any]] = []
    arrows: list[dict[str, Any]] = []
    left_out = {"events": [], "chapters": [], "undeclared": [], "others": []}
    known = set()
    for chapter, source, world in _chapters(contract, mesh):
        relations = parse_relations(world.world_model.relations)
        facts = _facts(relations, entity)
        events = [event for event in world.inputs.get("events", []) if isinstance(event, Mapping)]
        for event in events:
            known.update(filter(None, [event.get("actor"), event.get("place"), *event.get("with", []), *event_things(event)]))
        for relation in relations.values():
            known.update(relation[1:])
        involved = [event for event in events if _involves(event, entity, facts)]
        model = world.inputs.get("event_model", {})
        initial = model.get("initial_states", []) if isinstance(model, Mapping) else []
        start_state = _state(fluent_values(initial), facts, entity)
        if not involved and not start_state:
            left_out["chapters"].append(chapter or world.contract_id)
            continue
        if involved and not facts:
            left_out["undeclared"].append(chapter or world.contract_id)
        previous = len(boxes)
        boxes.append({"chapter": chapter, "label": "start", "state": start_state, "problem": False})
        if previous:
            handoff = [row for row in rows if row.get("code") == "MESH_HANDOFF_STATE_MISMATCH"
                       and (row.get("evidence") or {}).get("fluent") in facts]
            arrows.append({"from": previous - 1, "to": previous, "label": f"continues into {chapter}",
                           "problems": sorted({row["code"] for row in handoff}), "handoff": True})
        any_untimed = any("at" not in event for event in events)
        replay = [] if any_untimed else event_replay(events, initial, skip_illegal=True)
        for event, _before, after in replay:
            here = [row for row in rows if row.get("status") == "FAIL" and (row.get("node_id") in (chapter, None))
                    and event.get("event_id") in _found_at(row)]
            if not _involves(event, entity, facts) and not any(entity in _about(row, relations) for row in here):
                left_out["events"].append(f"{chapter + ' ' if chapter else ''}{event.get('event_id')}")
                continue
            codes, where = set(), f"{chapter + ' ' if chapter else ''}{event.get('event_id')}"
            for row in here:
                about = _about(row, relations)
                if not about or entity in about:
                    codes.add(row["code"])
                else:
                    left_out["others"].append(f"{row['code']} at {where}, about {', '.join(sorted(about))}")
            codes = sorted(codes)
            state = _state(after, facts, entity)
            label = f"{event['at']} {event.get('event_id')}" + (f" ({event['source']})" if event.get("source") else "")
            if state == boxes[-1]["state"] and not codes:
                arrows.append({"from": len(boxes) - 1, "to": len(boxes) - 1, "label": label, "problems": []})
                continue
            boxes.append({"chapter": chapter, "label": event.get("event_id"), "state": state, "problem": bool(codes)})
            arrows.append({"from": len(boxes) - 2, "to": len(boxes) - 1, "label": label, "problems": codes})
        if any_untimed:
            left_out["events"].extend(f"{chapter + ' ' if chapter else ''}{event.get('event_id')} (no time)" for event in involved)
    if entity not in known:
        raise WorldInputError(f"{entity!r} takes part in no event and no declared relation; known: {', '.join(sorted(known)) or 'none'}")
    folded = 0
    if limit is not None and len(boxes) > limit:
        keep_head, keep_tail = limit // 2, limit - limit // 2 - 1
        folded = len(boxes) - keep_head - keep_tail
        kept = list(range(keep_head)) + list(range(len(boxes) - keep_tail, len(boxes)))
        index = {old: new for new, old in enumerate(kept[:keep_head])}
        index.update({old: keep_head + 1 + position for position, old in enumerate(kept[keep_head:])})
        new_arrows, hidden = [], set()
        for arrow in arrows:
            start = index.get(arrow["from"], keep_head)
            end = index.get(arrow["to"], keep_head)
            if start == end == keep_head:
                hidden.update(arrow["problems"])  # a problem inside the fold is named on the folded box
                continue
            new_arrows.append({**arrow, "from": start, "to": end})
        middle = {"chapter": None, "label": f"{folded} more step{'s' if folded != 1 else ''}", "state": [], "folded": True,
                  "hidden_problems": sorted(hidden), "problem": bool(hidden) or any(
                      box["problem"] for position, box in enumerate(boxes) if keep_head <= position < len(boxes) - keep_tail)}
        new_boxes = [boxes[i] for i in kept[:keep_head]] + [middle] + [boxes[i] for i in kept[keep_head:]]
        boxes, arrows = new_boxes, new_arrows
    return {"entity": entity, "boxes": boxes, "arrows": arrows, "left_out": left_out, "folded": folded}


def _quote(text):
    return str(text).replace('"', "#quot;")


def render_mermaid(view: Mapping[str, Any]) -> str:
    """Markdown: one Mermaid flowchart, then plain lines saying what is shown and what was left out."""
    lines = ["```mermaid", "flowchart LR"]
    for number, box in enumerate(view["boxes"]):
        head = " ".join(part for part in (box["chapter"], box["label"]) if part)
        if box.get("folded"):
            body = "folded" + "".join(f" !! {code}" for code in box.get("hidden_problems", [])) + "; add --all to draw them"
        else:
            body = "<br/>".join(box["state"]) or "(no declared fact)"
        lines.append(f'  n{number}["{_quote(head)}<br/>{_quote(body)}"]')
    red = []
    for number, arrow in enumerate(view["arrows"]):
        label = arrow["label"] + ("".join(f" !! {code}" for code in arrow["problems"]))
        link = "-.->" if arrow.get("handoff") else "-->"
        lines.append(f'  n{arrow["from"]} {link}|"{_quote(label)}"| n{arrow["to"]}')
        if arrow["problems"]:
            red.append(str(number))
    bad = [f"n{number}" for number, box in enumerate(view["boxes"]) if box["problem"]]
    if bad:
        lines.append("  classDef problem stroke:#c00,stroke-width:2px")
        lines.append(f"  class {','.join(bad)} problem")
    if red:
        lines.append(f"  linkStyle {','.join(red)} stroke:#c00,stroke-width:2px")
    lines.append("```")
    events = sum(1 for arrow in view["arrows"] if not arrow.get("handoff"))
    count = len(view["boxes"])
    boxes = f"{count} box{'es' if count != 1 else ''}" + (" (one of them folded)" if view["folded"] else "")
    lines.append(f"Shown: {view['entity']}, {boxes}, {events} event{'s' if events != 1 else ''}; each box lists only "
                 f"the declared facts about {view['entity']}.")
    left = view["left_out"]
    parts = []
    if left["events"]:
        count = len(left["events"])
        parts.append(f"{count} event{'s' if count != 1 else ''} without {view['entity']} ({', '.join(left['events'][:5])}"
                     + (", ..." if len(left["events"]) > 5 else "") + ")")
    if left["chapters"]:
        parts.append(f"nodes without {view['entity']}: {', '.join(map(str, left['chapters']))}")
    if view["folded"]:
        parts.append(f"{view['folded']} middle steps folded into one box (add --all to draw them)")
    if left["others"]:
        count = len(left["others"])
        parts.append(f"{count} problem{'s' if count != 1 else ''} about others at {'a drawn step' if count == 1 else 'drawn steps'} "
                     f"({'; '.join(left['others'])})")
    parts.append(f"every fact not about {view['entity']}")
    lines.append("Left out: " + "; ".join(parts) + ".")
    if left["undeclared"]:
        lines.append(f"No world_model.relations name {view['entity']} in {', '.join(map(str, left['undeclared']))}; "
                     "declare them to see what it holds and where it is.")
    return "\n".join(lines)


__all__ = ["DEFAULT_LIMIT", "lifeline", "render_mermaid"]
