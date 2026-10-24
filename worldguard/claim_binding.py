"""Claim binding: evaluate each `claim.asserts` row against the world model.

A claim is bound to its world model only through structured assertions. Each assertion names model elements
(a fluent at a time, two events, a place, a variable, an agent, a spatial pair, a norm or a payoff) and is
evaluated on the same inputs the Guards check. The claim text is never read. No assertion: GAP.
"""

from __future__ import annotations

import math
import operator
from collections import defaultdict
from typing import Any, Callable

from .contracts import CLAIM_ASSERTION_KINDS, SEMANTIC_GUARD_ROUTES, GuardContract, claim_assertion_kind
from .clock import event_time_values
from .semantic import _RCC8_CONVERSE, _event_time_key, _fluent_values, causal_scenario_values, event_replay, norm_activity, token_replay
from .status import GuardStatus, aggregate_statuses

_COMPARE: dict[str, Callable[[float, float], bool]] = {
    "==": lambda left, right: math.isclose(left, right, abs_tol=1e-9),
    "!=": lambda left, right: not math.isclose(left, right, abs_tol=1e-9),
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}
_OPPOSITE = {"permitted": {"forbidden"}, "obligatory": {"forbidden"}, "forbidden": {"permitted", "obligatory"}}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _gap(reason: str) -> tuple[str, Any]:
    return "GAP", reason


def _verdict(holds: bool, observed: Any) -> tuple[str, Any]:
    return ("PASS" if holds else "FAIL"), observed


def _scoped_events(inputs: dict[str, Any], row: dict[str, Any]) -> list[dict[str, Any]] | None:
    events = [event for event in inputs.get("events", []) if isinstance(event, dict)]
    scenario = str(row.get("scenario") or "")
    if scenario and scenario not in {str(event.get("scenario_id") or "") for event in events}:
        return None
    return [event for event in events if not event.get("scenario_id") or str(event["scenario_id"]) == scenario]


def _holds(inputs: dict[str, Any], row: dict[str, Any]) -> tuple[str, Any]:
    """{holds: fluent, at: time, value: false}: the fluent after every event at or before `at`."""
    events = _scoped_events(inputs, row)
    if events is None:
        return _gap("scenario is not declared by the event model")
    initial = _mapping(inputs.get("event_model")).get("initial_states", [])
    fluent = str(row["holds"])
    known = set(_fluent_values(initial)) | {
        name for event in events for key in ("initiates", "terminates", "releases", "requires")
        for name in _fluent_values(event.get(key))
    }
    if fluent not in known:
        return _gap(f"fluent {fluent!r} is not in the world model")
    if "at" not in row:
        return _gap("a holds assertion needs at")
    if any("at" not in event for event in events):
        return _gap("event times are missing; fluent state cannot be ordered")
    holding = frozenset(_fluent_values(initial))
    for event, _, after in event_replay(events, initial, str(row.get("scenario", ""))):
        if _event_time_key(event.get("at", "")) > _event_time_key(row["at"]):
            break
        holding = after
    expected = row.get("value", True) is not False
    return _verdict((fluent in holding) == expected, {"holds": fluent in holding, "holding_fluents": sorted(holding)})


def _before(inputs: dict[str, Any], row: dict[str, Any]) -> tuple[str, Any]:
    """{event: event_id, before: event_id}: the first event happens strictly earlier."""
    first, second = str(row.get("event", "")), str(row["before"])
    events = _scoped_events(inputs, row)
    if events is None:
        return _gap("scenario is not declared by the event model")
    if not row.get("scenario"):
        all_events = [event for event in inputs.get("events", []) if isinstance(event, dict)]
        if any(sum(str(event.get("event_id")) == destination for event in all_events) > 1 for destination in (first, second)):
            return _gap("event ids are ambiguous across scenarios; specify scenario")
        events = all_events
    matches = {destination: [event for event in events if str(event.get("event_id")) == destination] for destination in (first, second)}
    if any(len(rows) > 1 for rows in matches.values()):
        return _gap("event ids are ambiguous in this scenario")
    if any(rows and "at" not in rows[0] for rows in matches.values()):
        return _gap("event times are missing; before cannot be evaluated")
    times = {destination: rows[0]["at"] for destination, rows in matches.items() if rows}
    unknown = [event_id for event_id in (first, second) if event_id not in times]
    if unknown:
        return _gap("events not in the world model: " + ", ".join(unknown))
    return _verdict(_event_time_key(times[first]) < _event_time_key(times[second]), {first: times[first], second: times[second]})


def _tokens(inputs: dict[str, Any], row: dict[str, Any]) -> tuple[str, Any]:
    """{place: place, qty: n, color: color, after: transition_id}: tokens after the transitions fire in list order."""
    resources = _mapping(inputs.get("resources"))
    places = _mapping(resources.get("places"))
    transitions = [item for item in resources.get("transitions", []) if isinstance(item, dict)]
    place, color, after = str(row["place"]), row.get("color"), row.get("after")
    known = set(map(str, places)) | {
        str(arc.get("place")) for item in transitions for key in ("consumes", "produces") for arc in item.get(key, [])
    }
    if place not in known:
        return _gap(f"place {place!r} is not in the world model")
    if after is not None and str(after) not in {str(item.get("id")) for item in transitions}:
        return _gap(f"transition {after!r} is not in the world model")
    if "qty" not in row:
        return _gap("a place assertion needs qty")
    marking, problem = token_replay(resources, str(after) if after is not None else None, validate=False, events=inputs.get("events", []))
    if problem:
        return _gap("token replay cannot reach the requested marking: " + str(problem))
    count = sum(value for (name, token), value in marking.items() if name == place and (color is None or token == str(color)))
    return _verdict(math.isclose(count, float(row["qty"])), {"qty": count})


def _value(inputs: dict[str, Any], row: dict[str, Any]) -> tuple[str, Any]:
    """{variable: name, op: '>=', value: number, scenario: id}: the value in every (or the named) scenario."""
    causal = _mapping(inputs.get("causal_model"))
    name, op, destination = str(row["variable"]), str(row.get("op", "==")), row.get("value")
    if name not in {str(item) for item in causal.get("variables", [])}:
        return _gap(f"variable {name!r} is not in the world model")
    if op not in _COMPARE or isinstance(destination, bool) or not isinstance(destination, (int, float)):
        return _gap("a variable assertion needs op (==, !=, <, <=, >, >=) and a numeric value")
    runs = causal_scenario_values(causal, event_time_values(inputs.get("events", [])))
    if row.get("scenario") is not None:
        runs = {key: values for key, values in runs.items() if key == str(row["scenario"])}
    if not runs:
        return _gap("no evaluated scenario holds this variable")
    observed = {scenario_id: values.get(name) for scenario_id, values in sorted(runs.items())}
    return _verdict(all(value is not None and _COMPARE[op](value, float(destination)) for value in observed.values()), observed)


def _attitude(inputs: dict[str, Any], row: dict[str, Any]) -> tuple[str, Any]:
    """{agent: agent_id, believes|desires|intends: item}: the item is in that agent's list."""
    record = _mapping(inputs.get("beliefs")).get(str(row["agent"]))
    if not isinstance(record, dict):
        return _gap(f"agent {row['agent']!r} is not in the world model")
    field = next((key for key in ("believes", "desires", "intends") if key in row), "")
    if not field:
        return _gap("an agent assertion needs believes, desires or intends")
    values = [str(item) for item in record.get({"believes": "beliefs", "desires": "desires", "intends": "intentions"}[field]) or []]
    return _verdict(str(row[field]) in values, {field: values})


def _relation(inputs: dict[str, Any], row: dict[str, Any]) -> tuple[str, Any]:
    """{relation: RCC8, x: object, y: object, at: time}: the declared relation (or its converse) of x and y."""
    rows = [item for item in inputs.get("spatial_relations", []) if isinstance(item, dict)]
    x, y, at = row.get("x"), row.get("y"), row.get("at")
    declared = {str(item.get("relation", "")).upper() for item in rows if (item.get("x"), item.get("y"), item.get("at")) == (x, y, at)}
    declared |= {
        _RCC8_CONVERSE.get(str(item.get("relation", "")).upper(), "")
        for item in rows if (item.get("x"), item.get("y"), item.get("at")) == (y, x, at)
    }
    declared.discard("")
    if not declared:
        return _gap(f"no declared relation between {x!r} and {y!r} at {at!r}")
    return _verdict(declared == {str(row["relation"]).upper()}, {"relations": sorted(declared)})


def _norm(inputs: dict[str, Any], row: dict[str, Any]) -> tuple[str, Any]:
    """{actor: actor, action: action, modality: permitted|obligatory|forbidden}: the active norms for that pair."""
    norms = [item for item in inputs.get("norms", []) if isinstance(item, dict)]
    pair = (str(row.get("actor", "")), str(row.get("action", "")))
    if not any((str(item.get("actor", "")), str(item.get("action", ""))) == pair for item in norms):
        return _gap(f"no norm for actor {pair[0]!r} and action {pair[1]!r} in the world model")
    relevant = [norm for norm in norms if (str(norm.get("actor", "")), str(norm.get("action", ""))) == pair]
    fluent_norms = any(isinstance(norm.get("condition"), dict) and "fluent" in norm["condition"] for norm in relevant)
    fluents = None
    known = None
    if fluent_norms:
        if "at" not in row:
            return _gap("a norm assertion with a fluent condition needs at")
        events = _scoped_events(inputs, row)
        if events is None or any("at" not in event for event in events):
            return _gap("norm applicability needs a declared scenario and event times")
        initial = _fluent_values(_mapping(inputs.get("event_model")).get("initial_states", []))
        known = set(initial) | {fluent for event in events for key in ("initiates", "terminates", "releases", "requires") for fluent in _fluent_values(event.get(key))}
        fluents = frozenset(initial)
        for event, _, after in event_replay(events, initial, str(row.get("scenario", ""))):
            if _event_time_key(event["at"]) >= _event_time_key(row["at"]):
                break
            fluents = after
    active, missing = norm_activity(relevant, inputs.get("facts", []), fluents, known)
    if missing:
        return _gap("a norm condition names an undeclared fact")
    modalities = sorted({
        "forbidden" if str(item.get("modality")) == "prohibited" else str(item.get("modality"))
        for item in active if (str(item.get("actor", "")), str(item.get("action", ""))) == pair
    })
    wanted = "forbidden" if str(row["modality"]) == "prohibited" else str(row["modality"])
    return _verdict(wanted in modalities and not _OPPOSITE.get(wanted, set()) & set(modalities), {"active_modalities": modalities})


def _payoff(inputs: dict[str, Any], row: dict[str, Any]) -> tuple[str, Any]:
    """{player: player, state: state, reward: number}: a declared payoff of that player in that state."""
    payoffs = [item for item in _mapping(inputs.get("game_model")).get("payoffs", []) if isinstance(item, dict)]
    rewards = [_mapping(item.get("reward")) for item in payoffs if str(item.get("state")) == str(row.get("state"))]
    values = [float(reward[str(row["player"])]) for reward in rewards if str(row["player"]) in reward]
    destination = row.get("reward")
    if not values or isinstance(destination, bool) or not isinstance(destination, (int, float)):
        return _gap("a payoff assertion needs a declared state and player and a numeric reward")
    return _verdict(any(math.isclose(value, float(destination)) for value in values), {"rewards": values})


_EVALUATORS = {
    "holds": _holds,
    "before": _before,
    "place": _tokens,
    "variable": _value,
    "agent": _attitude,
    "relation": _relation,
    "modality": _norm,
    "player": _payoff,
}


def evaluate_claim_binding(contract: GuardContract, *, node_contracts=None, descendant_ids=frozenset()) -> dict[str, Any]:
    """Evaluate every claim assertion against the model; a claim without assertions is not bound (GAP)."""
    rows: list[dict[str, Any]] = []
    for index, assertion in enumerate(contract.claim.asserts):
        kind = claim_assertion_kind(assertion)
        row: dict[str, Any] = {"index": index, "assertion": assertion}
        if not kind:
            status, detail = _gap("an assertion needs exactly one of: " + ", ".join(CLAIM_ASSERTION_KINDS))
        else:
            row["guard"] = SEMANTIC_GUARD_ROUTES[CLAIM_ASSERTION_KINDS[kind]][0]
            try:
                destination = assertion.get("node")
                if "node" in assertion and node_contracts is None:
                    status, detail = _gap("node rows need mesh-check")
                elif "node" in assertion and destination not in descendant_ids:
                    status, detail = _gap(f"node {destination!r} is not a parent_child descendant of this node")
                elif "node" in assertion and destination not in node_contracts:
                    status, detail = _gap(f"descendant node {destination!r} has no readable contract")
                else:
                    inputs = node_contracts[destination].inputs if "node" in assertion else contract.inputs
                    status, detail = _EVALUATORS[kind](inputs, assertion)
            except (TypeError, ValueError, KeyError, AttributeError) as exc:
                status, detail = _gap(f"cannot evaluate: {exc}")
        row["status"] = status
        row["reason" if status == "GAP" else "observed"] = detail
        rows.append(row)
    status = aggregate_statuses([row["status"] for row in rows]) if rows else GuardStatus.GAP
    return {"status": status.value, "bound": bool(rows), "assertions": rows}


__all__ = ["evaluate_claim_binding"]
