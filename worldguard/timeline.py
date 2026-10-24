"""Read the same finite event, token and scalar state used by native checks."""
from __future__ import annotations

from collections.abc import Mapping

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
    events = [event for event in inputs.get("events", []) if isinstance(event, Mapping)]
    if scenario is not None and scenario not in {str(event.get("scenario_id")) for event in events if event.get("scenario_id")}:
        raise ValueError(f"timeline scenario {scenario!r} is not declared")
    scenario = scenario or ""
    applicable = [event for event in events if not event.get("scenario_id") or str(event["scenario_id"]) == scenario]
    if any("at" not in event for event in applicable):
        raise ValueError("timeline needs an at time for each applicable event")
    initial = _fluent_values(inputs.get("event_model", {}).get("initial_states", []))
    resources = inputs.get("resources", {})
    transitions = [row for row in resources.get("transitions", []) if isinstance(row, Mapping)]
    marking, _ = token_replay({**resources, "transitions": []}, validate=False)
    initial_problems = sorted({row["code"] for row in problems
                               if row.get("counterexample", {}).get("event_id", "not-initial") is None})
    steps = [{"at": None, "event_id": None, "fluents": sorted(initial), "tokens": _tokens(marking)}]
    if initial_problems:
        steps[0]["problems"] = initial_problems
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


def render_timeline_text(view):
    """Render the native timeline without changing or recomputing its checks."""
    lines = [f"world {view['contract_id']} (clock: {view['clock']})"]
    for step in view['steps']:
        tokens = ', '.join(f"{place}=" + '+'.join(f"{color}×{quantity:g}" for color, quantity in colors.items())
                           for place, colors in step.get('tokens', {}).items() if any(colors.values())) or '-'
        line = (f"{step['at'] if step['at'] is not None else 'start'}  {step.get('event_id') or '-'}  "
                f"fluents: {', '.join(step['fluents']) or '-'} | tokens: {tokens}")
        if step.get('source'):
            line += f" (source: {step['source']})"
        if step.get('problems'):
            line += '  !! ' + ', '.join(step['problems'])
        lines.append(line)
    for scenario, values in view.get('variables', {}).items():
        rendered = ', '.join(f"{name}={value:.3g}" if isinstance(value, (int, float)) else f"{name}={value}"
                             for name, value in values.items())
        lines.append(f"variables [{scenario}]: {rendered}")
    return '\n'.join(lines)
