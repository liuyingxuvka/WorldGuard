"""Declared relations: which fluent says who holds which thing and who is at which place.

`world_model.relations` maps a fluent id to one relation, `{holds: [holder, thing]}` or `{at: [who, place]}`.
An event with an `actor` says where it happens (`place`) and what the actor uses (`uses`). From these
declarations the tool derives what must hold just before the event (the actor holds each used thing; the
actor and every `with` participant are at the place) and replays the world to check it. The event's own
`requires` and the spelling of fluent names play no part. The same replay finds two declared facts that
cannot both hold: one person at two places, or one thing with two holders.
"""

from __future__ import annotations

from collections.abc import Mapping
from itertools import groupby
from typing import Any

from .clock import time_key
from .semantic import event_precondition_failures, event_replay, fluent_values

RELATION_KINDS = ("holds", "at")
_SHAPE = "{holds: [holder, thing]} or {at: [who, place]}"


def parse_relations(raw: Any) -> dict[str, tuple[str, str, str]]:
    """{fluent: (kind, subject, object)} from world_model.relations; anything else is an input error."""
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ValueError(f"world_model.relations must map fluent ids to {_SHAPE}")
    parsed: dict[str, tuple[str, str, str]] = {}
    declared_by: dict[tuple[str, str, str], str] = {}
    for fluent, spec in raw.items():
        where = f"world_model.relations.{fluent}"
        if not isinstance(fluent, str) or not fluent.strip():
            raise ValueError("world_model.relations keys must be fluent ids")
        if not isinstance(spec, Mapping) or len(spec) != 1 or next(iter(spec)) not in RELATION_KINDS:
            raise ValueError(f"{where} must be {_SHAPE}")
        kind, pair = next(iter(spec.items()))
        if not isinstance(pair, (list, tuple)) or len(pair) != 2 or any(not isinstance(item, str) or not item.strip() for item in pair):
            raise ValueError(f"{where}.{kind} must name two ids, for example [Lena, key] or [Lena, island]")
        key = (kind, pair[0], pair[1])
        if key in declared_by:
            raise ValueError(f"{where} repeats {kind} {pair[0]} {pair[1]}, which {declared_by[key]} already declares")
        declared_by[key] = fluent
        parsed[fluent] = key
    return parsed


def event_things(event: Mapping[str, Any]) -> list[str]:
    value = event.get("uses", [])
    return [value] if isinstance(value, str) else list(value)


def _row(code, status, event, message, **fields):
    row = {"code": code, "status": status, "event_id": event.get("event_id", ""), **fields, "message": message}
    if event.get("source"):
        row["source"] = event["source"]
    if event.get("scenario_id"):
        row["scenario_id"] = event["scenario_id"]
    return row


def _describe(kind, subject, obj):
    return f"{subject} holds {obj}" if kind == "holds" else f"{subject} is at {obj}"


def actor_relation_rows(inputs: Mapping[str, Any], relations: Mapping[str, tuple[str, str, str]], *,
                        requires_checked: bool = False) -> list[dict[str, Any]]:
    """GAP rows for actor events whose state the declarations cannot check; FAIL rows where the replay contradicts them.

    With `requires_checked` (EventGuard runs), a derived fluent the event already lists in `requires` is left to
    EventGuard's EVENT_PRECONDITION_UNMET, so one missing fact is reported once."""
    events = [event for event in inputs.get("events", []) if isinstance(event, Mapping)]
    actors_named = any(event.get("actor") for event in events)
    fluent_of = {key: fluent for fluent, key in relations.items()}
    rows: list[dict[str, Any]] = []
    needed: dict[tuple[str, str], dict[str, tuple[str, str, str]]] = {}
    for event in events:
        if "actor_state_free" in event:
            continue
        actor = event.get("actor")
        if not actor:
            if actors_named:
                rows.append(_row("EVENT_ACTOR_STATE_UNCHECKED", "GAP", event,
                                 "Events in this world name their actors, but this one names none; name its actor, "
                                 "or give actor_state_free: <reason> when nobody acts.", actor=None, missing=["actor"]))
            continue
        missing = [name for name in ("place", "uses") if name not in event]
        if missing:
            rows.append(_row("EVENT_ACTOR_STATE_UNCHECKED", "GAP", event,
                             "Say where the event happens (place) and what the actor uses (uses; [] when nothing), "
                             "declared in world_model.relations, or give actor_state_free: <reason>.",
                             actor=actor, missing=missing))
        wanted = [("holds", actor, thing) for thing in event_things(event)]
        if "place" in event:
            wanted.extend(("at", person, event["place"]) for person in [actor, *event.get("with", [])])
        own = set(fluent_values(event.get("requires"))) if requires_checked else set()
        for key in wanted:
            fluent = fluent_of.get(key)
            if fluent in own:
                continue
            if fluent is None:
                rows.append(_row("EVENT_RELATION_UNDECLARED", "GAP", event,
                                 f"No fluent in world_model.relations says that {_describe(*key)}, so the event cannot be checked.",
                                 actor=actor, relation=key[0], subject=key[1], object=key[2]))
            else:
                needed.setdefault((str(event.get("scenario_id") or ""), str(event.get("event_id"))), {})[fluent] = key
    if not needed:
        return rows
    derived = [{**event, "requires": sorted(needed.get((str(event.get("scenario_id") or ""), str(event.get("event_id"))), {}))}
               for event in events]
    initial = inputs.get("event_model", {}).get("initial_states", []) if isinstance(inputs.get("event_model"), Mapping) else []
    by_id = {(str(event.get("scenario_id") or ""), str(event.get("event_id"))): event for event in events}
    for failure in event_precondition_failures(derived, initial):
        identity = (str(failure.get("scenario_id") or ""), str(failure["event_id"]))
        event = by_id.get(identity) or by_id[("", identity[1])]
        holding = set(failure["holding_fluents"])
        wanted = needed[(str(event.get("scenario_id") or ""), identity[1])]
        # Order by the declared relation, never by how the fluents are spelled.
        for fluent in sorted(failure["missing_fluents"], key=lambda name: wanted[name]):
            kind, subject, obj = wanted[fluent]
            if kind == "holds":
                found = sorted(relations[f][1] for f in holding if f in relations and relations[f][0] == "holds" and relations[f][2] == obj)
                where = f"held by {', '.join(found)}" if found else "nobody holds it"
                message = f"{subject} does not hold {obj} at {event['at']} ({where})."
            else:
                found = sorted(relations[f][2] for f in holding if f in relations and relations[f][0] == "at" and relations[f][1] == subject)
                where = f"at {', '.join(found)}" if found else "no declared place holds"
                message = f"{subject} is not at {obj} at {event['at']} ({where})."
            rows.append(_row("EVENT_RELATION_UNMET", "FAIL", event, message, actor=event.get("actor"), relation=kind,
                             subject=subject, object=obj, fluent=fluent, at=event["at"], found=found))
    return rows


def relation_conflicts(inputs: Mapping[str, Any], relations: Mapping[str, tuple[str, str, str]]) -> list[dict[str, Any]]:
    """FAIL when, after all events of one instant, a person is at two places or a thing has two holders."""
    if not relations:
        return []
    events = [event for event in inputs.get("events", []) if isinstance(event, Mapping)]
    initial = inputs.get("event_model", {}).get("initial_states", []) if isinstance(inputs.get("event_model"), Mapping) else []
    scenarios = sorted({str(event["scenario_id"]) for event in events if event.get("scenario_id")}) or [""]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        applicable = [event for event in events if not event.get("scenario_id") or str(event["scenario_id"]) == scenario]
        if any("at" not in event for event in applicable):
            continue  # untimed events cannot be ordered; EventGuard reports the missing time
        established = {fluent: {"event_id": None, "at": None} for fluent in fluent_values(initial)}
        states = [(None, None, frozenset(fluent_values(initial)))]
        for instant, group in groupby(event_replay(applicable, initial, scenario, skip_illegal=True),
                                      key=lambda row: time_key(row[0]["at"])):
            group = list(group)
            for event, before, after in group:
                for fluent in set(after) - set(before):
                    established[fluent] = {"event_id": event.get("event_id"), "at": event["at"],
                                           **({"source": event["source"]} if event.get("source") else {})}
            states.append((group[-1][0].get("event_id"), group[-1][0]["at"], group[-1][2]))
        reported = set()
        for event_id, at, holding in states:
            groups: dict[tuple[str, str], list[str]] = {}
            for fluent in sorted(holding):
                if fluent in relations:
                    kind, subject, obj = relations[fluent]
                    groups.setdefault(("at", subject) if kind == "at" else ("holds", obj), []).append(fluent)
            for (kind, who), fluents in sorted(groups.items()):
                if len(fluents) < 2 or (kind, who) in reported:
                    continue
                reported.add((kind, who))
                values = [relations[f][2] if kind == "at" else relations[f][1] for f in fluents]
                message = (f"{who} is at {' and '.join(values)} at once" if kind == "at"
                           else f"{who} is held by {' and '.join(values)} at once")
                row = {"code": "WORLD_RELATION_CONFLICT", "status": "FAIL", "relation": kind,
                       "subject" if kind == "at" else "object": who, "fluents": fluents,
                       "event_id": event_id, "at": at,
                       "established_by": {fluent: established.get(fluent, {}) for fluent in fluents},
                       "message": message + "; end one of these facts where the other begins."}
                if scenario:
                    row["scenario_id"] = scenario
                rows.append(row)
    return rows


__all__ = ["RELATION_KINDS", "parse_relations", "event_things", "actor_relation_rows", "relation_conflicts"]
