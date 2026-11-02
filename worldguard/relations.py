"""Declared relations: which fluent says who holds which thing and who is at which place.

`world_model.relations` maps a fluent id to one relation, `{holds: [holder, thing]}` or `{at: [who, place]}`.
An event with an `actor` says where it happens (`place`) and what the actor uses (`uses`). From these
declarations the tool derives what must hold just before the event (the actor holds each used thing; the
actor and every `with` participant are at the place) and replays the world to check it. The event's own
`requires` and the spelling of fluent names play no part. The same replay finds two declared facts that
cannot both hold: one person at two places, or one thing with two holders. Once a world declares any relation,
every event names its actor (or says `actor_state_free: <reason>`). What the declarations cannot reach is said
in `scope_limits`: a world that names no actor and declares nothing, and an event that changes facts no
relation ties to anyone or anything.
"""

from __future__ import annotations

from collections.abc import Mapping
from itertools import groupby
from typing import Any

from .clock import time_key
from .semantic import event_precondition_failures, event_replay, fluent_values
from .errors import WorldInputError

RELATION_KINDS = ("holds", "at")
NOTHING_DECLARED = ("who holds what and who is where are not checked: no event names an actor and "
                    "world_model.relations declares nothing")
_SHAPE = "{holds: [holder, thing]} or {at: [who, place]}"


def parse_relations(raw: Any) -> dict[str, tuple[str, str, str]]:
    """{fluent: (kind, subject, object)} from world_model.relations; anything else is an input error."""
    if not isinstance(raw, Mapping):
        raise WorldInputError(f"world_model.relations must map fluent ids to {_SHAPE}")
    parsed: dict[str, tuple[str, str, str]] = {}
    declared_by: dict[tuple[str, str, str], str] = {}
    for fluent, spec in raw.items():
        where = f"world_model.relations.{fluent}"
        if not isinstance(fluent, str) or not fluent.strip():
            raise WorldInputError("world_model.relations keys must be fluent ids")
        if not isinstance(spec, Mapping) or len(spec) != 1 or next(iter(spec)) not in RELATION_KINDS:
            raise WorldInputError(f"{where} must be {_SHAPE}")
        kind, pair = next(iter(spec.items()))
        if not isinstance(pair, (list, tuple)) or len(pair) != 2 or any(not isinstance(item, str) or not item.strip() for item in pair):
            raise WorldInputError(f"{where}.{kind} must name two ids, for example [Lena, key] or [Lena, island]")
        key = (kind, pair[0], pair[1])
        if key in declared_by:
            raise WorldInputError(f"{where} repeats {kind} {pair[0]} {pair[1]}, which {declared_by[key]} already declares")
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


def _scenarios(events):
    """{scenario: (applicable events, untimed event ids)} exactly as the replays below order them."""
    names = sorted({str(event["scenario_id"]) for event in events if event.get("scenario_id")}) or [""]
    result = {}
    for scenario in names:
        applicable = [event for event in events if not event.get("scenario_id") or str(event["scenario_id"]) == scenario]
        result[scenario] = (applicable, [str(event.get("event_id", "")) for event in applicable if "at" not in event])
    return result


def _plan(inputs, relations, requires_checked):
    """The one derivation behind the relation check and its coverage.

    Returns (gap rows, needed, coverage). `needed` maps (scenario id, event id) to {fluent: (kind, subject, object)}
    for the derived facts the replay must check. `coverage` maps the same key to (questions, unchecked): the
    (kind, subject, object) facts this run checks just before the event, and why anything else there is not checked."""
    events = [event for event in inputs.get("events", []) if isinstance(event, Mapping)]
    actors_named = any(event.get("actor") for event in events)
    fluent_of = {key: fluent for fluent, key in relations.items()}
    scenarios = _scenarios(events)
    everywhere = sorted({name for _applicable, names in scenarios.values() for name in names})
    rows: list[dict[str, Any]] = []
    needed: dict[tuple[str, str], dict[str, tuple[str, str, str]]] = {}
    coverage: dict[tuple[str, str], tuple[frozenset, tuple[str, ...]]] = {}
    for event in events:
        key = (str(event.get("scenario_id") or ""), str(event.get("event_id")))
        unchecked: list[str] = []
        questions: set[tuple[str, str, str]] = set()
        untimed = sorted(scenarios[str(event["scenario_id"])][1]) if event.get("scenario_id") else everywhere
        if untimed:
            unchecked.append(f"{', '.join(untimed)} {'has' if len(untimed) == 1 else 'have'} no at time, so the world "
                             "was not replayed")
        if not relations:
            unchecked.append("world_model.relations declares nothing")
        if "actor_state_free" in event:
            coverage[key] = (frozenset(), (*unchecked, f"the event is marked actor_state_free ({event['actor_state_free']})"))
            continue
        actor = event.get("actor")
        if not actor:
            if relations or actors_named:
                why = ("This world declares who holds what or who is where" if relations
                       else "Events in this world name their actors")
                rows.append(_row("EVENT_ACTOR_STATE_UNCHECKED", "GAP", event,
                                 f"{why}, but this event names no actor; name its actor, "
                                 "or give actor_state_free: <reason> when nobody acts.", actor=None, missing=["actor"]))
            coverage[key] = (frozenset(), (*unchecked, "the event names no actor"))
            continue
        missing = [name for name in ("place", "uses") if name not in event]
        if missing:
            rows.append(_row("EVENT_ACTOR_STATE_UNCHECKED", "GAP", event,
                             "Say where the event happens (place) and what the actor uses (uses; [] when nothing), "
                             "declared in world_model.relations, or give actor_state_free: <reason>.",
                             actor=actor, missing=missing))
            unchecked.append(f"the event does not say {' or '.join(missing)}")
        wanted = [("holds", actor, thing) for thing in event_things(event)]
        if "place" in event:
            wanted.extend(("at", person, event["place"]) for person in [actor, *event.get("with", [])])
        own = set(fluent_values(event.get("requires"))) if requires_checked else set()
        for fact in wanted:
            fluent = fluent_of.get(fact)
            if fluent is None:
                rows.append(_row("EVENT_RELATION_UNDECLARED", "GAP", event,
                                 f"No fluent in world_model.relations says that {_describe(*fact)}, so the event cannot be checked.",
                                 actor=actor, relation=fact[0], subject=fact[1], object=fact[2]))
                unchecked.append(f"no relation says that {_describe(*fact)}")
                continue
            if not untimed:
                questions.add(fact)  # replayed below, or by EventGuard when the event's own requires lists it
            if fluent not in own:
                needed.setdefault(key, {})[fluent] = fact
        coverage[key] = (frozenset(questions), tuple(unchecked))
    return rows, needed, coverage


def relation_coverage(inputs: Mapping[str, Any], relations: Mapping[str, tuple[str, str, str]], *,
                      requires_checked: bool = False) -> dict[tuple[str, str], tuple[frozenset, tuple[str, ...]]]:
    """What the relation check asks of this world: {(scenario id, event id): (facts checked just before the event,
    why anything else there is not checked)}. Computed by the same derivation as the check itself."""
    return _plan(inputs, relations, requires_checked)[2]


def _origins(applicable, initial, scenario):
    """{(event id, at): (fluent -> event that started it or None for the start state, fluent -> event that last ended it)},
    as things stand at the start of each event's instant (the replay's own view)."""
    started: dict[str, Any] = {fluent: None for fluent in fluent_values(initial)}
    ended: dict[str, Any] = {}
    result = {}
    for _instant, group in groupby(event_replay(applicable, initial, scenario), key=lambda row: time_key(row[0]["at"])):
        group = list(group)
        snapshot = (dict(started), dict(ended))
        for event, before, after in group:
            result[(event.get("event_id"), event.get("at"))] = snapshot
            for fluent in set(after) - set(before):
                started[fluent] = event
                ended.pop(fluent, None)
            for fluent in set(before) - set(after):
                ended[fluent] = event
                started.pop(fluent, None)
    return result


def _origin(event):
    if event is None:
        return {"event_id": None, "at": None, "where": "start"}
    return {"event_id": event.get("event_id"), "at": event.get("at"),
            "where": f"{event['source']} ({event.get('event_id')})" if event.get("source") else str(event.get("event_id")),
            **({"source": event["source"]} if event.get("source") else {})}


def actor_relation_rows(inputs: Mapping[str, Any], relations: Mapping[str, tuple[str, str, str]], *,
                        requires_checked: bool = False) -> list[dict[str, Any]]:
    """GAP rows for actor events whose state the declarations cannot check; FAIL rows where the replay contradicts them.

    With `requires_checked` (EventGuard runs), a derived fluent the event already lists in `requires` is left to
    EventGuard's EVENT_PRECONDITION_UNMET, so one missing fact is reported once. A FAIL row names, in
    `established_by`, the event (or the start state) that set up each fact holding instead, and in `ended_by` the
    event that ended the needed fact."""
    rows, needed, _coverage = _plan(inputs, relations, requires_checked)
    if not needed:
        return rows
    events = [event for event in inputs.get("events", []) if isinstance(event, Mapping)]
    # A scenario with an untimed event is not replayed here; relation_conflicts reports it once.
    derived = [{**event, "requires": sorted(needed.get((str(event.get("scenario_id") or ""), str(event.get("event_id"))), {}))}
               for event in events]
    initial = inputs.get("event_model", {}).get("initial_states", []) if isinstance(inputs.get("event_model"), Mapping) else []
    by_id = {(str(event.get("scenario_id") or ""), str(event.get("event_id"))): event for event in events}
    scenarios = _scenarios(events)
    origins = {}
    for failure in event_precondition_failures(derived, initial):
        identity = (str(failure.get("scenario_id") or ""), str(failure["event_id"]))
        event = by_id.get(identity) or by_id[("", identity[1])]
        if identity[0] not in origins:
            origins[identity[0]] = _origins(scenarios[identity[0]][0], initial, identity[0])
        started, ended = origins[identity[0]][(event.get("event_id"), event.get("at"))]
        holding = set(failure["holding_fluents"])
        wanted = needed[(str(event.get("scenario_id") or ""), identity[1])]
        # Order by the declared relation, never by how the fluents are spelled.
        for fluent in sorted(failure["missing_fluents"], key=lambda name: wanted[name]):
            kind, subject, obj = wanted[fluent]
            if kind == "holds":
                instead = sorted(f for f in holding if f in relations and relations[f][0] == "holds" and relations[f][2] == obj)
                found = sorted(relations[f][1] for f in instead)
                where = f"held by {', '.join(found)}" if found else "nobody holds it"
                message = f"{subject} does not hold {obj} at {event['at']} ({where})."
            else:
                instead = sorted(f for f in holding if f in relations and relations[f][0] == "at" and relations[f][1] == subject)
                found = sorted(relations[f][2] for f in instead)
                where = f"at {', '.join(found)}" if found else "no declared place holds"
                message = f"{subject} is not at {obj} at {event['at']} ({where})."
            extra = {"established_by": {f: {"fact": _describe(*relations[f]), **_origin(started.get(f))} for f in instead}}
            if fluent in ended:
                extra["ended_by"] = {"fact": _describe(kind, subject, obj), **_origin(ended[fluent])}
            rows.append(_row("EVENT_RELATION_UNMET", "FAIL", event, message, actor=event.get("actor"), relation=kind,
                             subject=subject, object=obj, fluent=fluent, at=event["at"], found=found, **extra))
    return rows


def relation_conflicts(inputs: Mapping[str, Any], relations: Mapping[str, tuple[str, str, str]]) -> list[dict[str, Any]]:
    """FAIL when, after all events of one instant, a person is at two places or a thing has two holders.

    Untimed events cannot be ordered, so that scenario is not replayed: GAP WORLD_RELATION_CHECK_NOT_RUN says so
    (the derived event preconditions are not replayed either), whatever Guards the claim requests."""
    if not relations:
        return []
    events = [event for event in inputs.get("events", []) if isinstance(event, Mapping)]
    initial = inputs.get("event_model", {}).get("initial_states", []) if isinstance(inputs.get("event_model"), Mapping) else []
    scenarios = sorted({str(event["scenario_id"]) for event in events if event.get("scenario_id")}) or [""]
    rows: list[dict[str, Any]] = []
    for scenario in scenarios:
        applicable = [event for event in events if not event.get("scenario_id") or str(event["scenario_id"]) == scenario]
        untimed = [str(event.get("event_id", "")) for event in applicable if "at" not in event]
        if untimed:
            row = {"code": "WORLD_RELATION_CHECK_NOT_RUN", "status": "GAP", "untimed_events": untimed,
                   "message": f"{', '.join(untimed)} {'has' if len(untimed) == 1 else 'have'} no at time, so who holds "
                              "what and who is where were not replayed" + (f" in scenario {scenario}" if scenario else "")}
            if scenario:
                row["scenario_id"] = scenario
            rows.append(row)
            continue
        established = {fluent: {"event_id": None, "at": None} for fluent in fluent_values(initial)}
        # (the instant, what holds after all its events, the events of that instant that started each fact, in order)
        states = [(None, frozenset(fluent_values(initial)), {})]
        for instant, group in groupby(event_replay(applicable, initial, scenario, skip_illegal=True),
                                      key=lambda row: time_key(row[0]["at"])):
            group = list(group)
            started: dict[str, list[str]] = {}
            for event, before, after in group:
                for fluent in set(after) - set(before):
                    established[fluent] = {"event_id": event.get("event_id"), "at": event["at"],
                                           **({"source": event["source"]} if event.get("source") else {})}
                    started.setdefault(fluent, []).append(str(event.get("event_id")))
            states.append((group[-1][0]["at"], group[-1][2], started))
        order = {str(event.get("event_id")): index for index, event in enumerate(applicable)}
        reported = set()
        for at, holding, started in states:
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
                # Found at the events of this instant that started one of the clashing facts, never at a neighbour of
                # the same time; a conflict the chapter starts with is found at no event.
                causes = sorted({event for fluent in fluents for event in started.get(fluent, [])}, key=order.__getitem__)
                row = {"code": "WORLD_RELATION_CONFLICT", "status": "FAIL", "relation": kind,
                       "subject" if kind == "at" else "object": who, "fluents": fluents,
                       "event_id": causes[-1] if causes else None, **({"event_ids": causes} if causes else {}), "at": at,
                       "established_by": {fluent: established.get(fluent, {}) for fluent in fluents},
                       "message": message + "; end one of these facts where the other begins."}
                if scenario:
                    row["scenario_id"] = scenario
                rows.append(row)
    return rows


def conflict_coverage(inputs: Mapping[str, Any], relations: Mapping[str, tuple[str, str, str]]) -> dict[str, tuple[frozenset, str]]:
    """What the conflict check asks of this world: {scenario id: ((kind, who) pairs it can find two facts for, why it did
    not run or "")}. A person with two declared places, or a thing with two declared holders, is asked about."""
    events = [event for event in inputs.get("events", []) if isinstance(event, Mapping)]
    groups: dict[tuple[str, str], int] = {}
    for kind, subject, obj in relations.values():
        key = ("at", subject) if kind == "at" else ("holds", obj)
        groups[key] = groups.get(key, 0) + 1
    asked = frozenset(key for key, count in groups.items() if count >= 2)
    result = {}
    for scenario, (_applicable, untimed) in _scenarios(events).items():
        if not relations:
            result[scenario] = (frozenset(), "world_model.relations declares nothing")
        elif untimed:
            result[scenario] = (frozenset(), f"{', '.join(untimed)} {'has' if len(untimed) == 1 else 'have'} no at time, so "
                                             "the world was not replayed")
        else:
            result[scenario] = (asked, "")
    return result


def relation_scope_limits(inputs: Mapping[str, Any], relations: Mapping[str, tuple[str, str, str]]) -> list[str]:
    """What the declarations cannot check, computed from the world itself; empty when nothing is out of reach."""
    events = [event for event in inputs.get("events", []) if isinstance(event, Mapping)]
    if not events:
        return []
    if not relations:
        if any(event.get("actor") for event in events):
            return []  # actor events without relations are GAP EVENT_RELATION_UNDECLARED
        return [NOTHING_DECLARED]
    loose = []
    for event in events:
        if not event.get("actor") or "actor_state_free" in event:
            continue
        changed = [name for key in ("initiates", "terminates") for name in fluent_values(event.get(key))]
        untied = sorted(dict.fromkeys(name for name in changed if name not in relations))
        if untied:
            where = f" at {event['place']}" if event.get("place") else ""
            loose.append(f"{event.get('event_id')} ({event['actor']}{where}) changes {', '.join(untied)}")
    if not loose:
        return []
    return ["place checked only for the people and things an event names: " + "; ".join(loose)
            + ", which world_model.relations ties to no one and nothing; declare where a thing is "
            "({at: [thing, place]}) and name it in with to check it"]


__all__ = ["RELATION_KINDS", "NOTHING_DECLARED", "parse_relations", "event_things", "actor_relation_rows", "relation_coverage",
           "relation_conflicts", "conflict_coverage", "relation_scope_limits"]
