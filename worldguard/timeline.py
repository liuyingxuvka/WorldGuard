"""Read the same finite event, token and scalar state used by native checks."""
from __future__ import annotations

from .clock import event_time_values, time_kind
from .contracts import GuardContract
from .semantic import _fluent_values, causal_scenario_values, event_replay, token_replay


def _tokens(marking):
    result = {}
    for (place, color), quantity in sorted(marking.items()):
        result.setdefault(place, {})[color] = quantity
    return result


def _event_ids(value):
    if isinstance(value, dict):
        own = {str(value["event_id"])} if value.get("event_id") else set()
        own.update(map(str, value.get("event_ids", [])))
        for key, child in value.items():
            if key != "trace":
                own.update(_event_ids(child))
        return own
    if isinstance(value, list):
        return set().union(*(_event_ids(child) for child in value)) if value else set()
    return set()


def timeline(contract, *, scenario=None, problems=()):
    if not isinstance(contract, GuardContract):
        contract = GuardContract.from_dict(contract)
    inputs = contract.inputs
    events = inputs.get("events", [])
    if scenario is not None and scenario not in {str(event.get("scenario_id")) for event in events if event.get("scenario_id")}:
        raise ValueError(f"timeline scenario {scenario!r} is not declared")
    scenario = scenario or ""
    applicable = [event for event in events if not event.get("scenario_id") or str(event["scenario_id"]) == scenario]
    if any("at" not in event for event in applicable):
        raise ValueError("timeline needs an at time for each applicable event")
    initial = _fluent_values(inputs.get("event_model", {}).get("initial_states", []))
    resources = inputs.get("resources", {})
    transitions = resources.get("transitions", [])
    marking, _ = token_replay({**resources, "transitions": []}, validate=False)
    steps = [{"at": None, "event_id": None, "fluents": sorted(initial), "tokens": _tokens(marking)}]
    linked = any("event" in row for row in transitions)
    for event, _, after in event_replay(applicable, initial, scenario):
        matches = [row for row in transitions if row.get("event") == event["event_id"]]
        if linked and matches:
            marking, _ = token_replay(resources, str(matches[-1]["id"]), validate=False, events=events)
        step = {"at": event["at"], "event_id": event["event_id"], "fluents": sorted(after),
                "tokens": _tokens(marking), "problems": sorted({row["code"] for row in problems if event["event_id"] in _event_ids(row)})}
        if event.get("source"):
            step["source"] = event["source"]
        steps.append(step)
    if not linked and transitions:
        marking, _ = token_replay(resources, validate=False, events=events)
        if not applicable:
            steps.append({"at": None, "event_id": None, "fluents": sorted(initial), "problems": []})
        steps[-1]["tokens"] = _tokens(marking)
    return {"contract_id": contract.contract_id, "clock": time_kind(applicable[0]["at"]) if applicable else "none",
            "steps": steps, "variables": causal_scenario_values(inputs.get("causal_model", {}), event_time_values(events))}
