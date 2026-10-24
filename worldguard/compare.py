"""Compare declared world values with supplied observations, without modifying either."""
from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from math import isfinite
from typing import Any

from .clock import event_time_values, time_key, time_kind, validate_times
from .contracts import GuardContract
from .semantic import causal_scenario_values


def _number(value: Any, name: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (nonnegative and value < 0):
        raise ValueError(f"{name} must be a finite {'nonnegative ' if nonnegative else ''}number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _compare_world(contract: GuardContract | Mapping[str, Any], observed: Mapping[str, Any]) -> dict[str, Any]:
    """Derive expected times and scenario values from the world and compare only observed ids."""
    if not isinstance(contract, GuardContract):
        contract = GuardContract.from_dict(dict(contract))
    if not isinstance(observed, Mapping):
        raise ValueError("observed world must be a mapping")
    if "nodes" in observed:
        raise ValueError("node observations need --mesh, not --contract")
    time_tolerance = _number(observed.get("time_tolerance", 0), "time_tolerance", nonnegative=True)
    tolerance = _number(observed.get("tolerance", 0), "tolerance", nonnegative=True)
    events, variables = observed.get("events", {}), observed.get("variables", {})
    if not isinstance(events, Mapping) or not isinstance(variables, Mapping):
        raise ValueError("observed events and variables must be id-to-value mappings")
    native_events = contract.inputs.get("events", [])
    causal = contract.inputs.get("causal_model", {})
    values = causal_scenario_values(causal, event_time_values(native_events))
    scenario = observed.get("scenario")
    known_scenarios = set(values) | {str(row["scenario_id"]) for row in native_events if row.get("scenario_id")}
    if "scenario" in observed and (not isinstance(scenario, str) or not scenario or scenario not in known_scenarios):
        raise ValueError(f"unknown scenario: {scenario!r}")
    if scenario is None and len(values) == 1:
        scenario = next(iter(values))
    if variables and scenario is None and len(values) != 1:
        raise ValueError("observed variables require an explicit evaluable causal scenario")
    selected_events = [row for row in native_events if not row.get("scenario_id") or row["scenario_id"] == scenario]
    known_variables = set(causal.get("variables", [])) | set(causal.get("exogenous", []))
    matches, mismatches = [], []
    selected_occurrences = {}
    def record(identity, kind, expected, actual, difference, bound):
        row = {"id": identity, "kind": kind, "expected_value": expected,
               "actual_value": actual, "difference": difference, "tolerance": bound}
        if abs(difference) <= bound:
            matches.append(row)
        else:
            row["mismatch_code"] = "value_outside_tolerance"
            mismatches.append(row)
    for event_id, actual in events.items():
        candidates = [row for row in selected_events if row.get("event_id") == event_id]
        if len(candidates) != 1:
            raise ValueError(f"event {event_id!r} is unknown or ambiguous in the selected scenario")
        selected_occurrences[event_id] = next(i for i, row in enumerate(native_events) if row is candidates[0])
        expected = candidates[0].get("at")
        validate_times([(f"expected event {event_id}", expected), (f"observed event {event_id}", actual)])
        divisor = 60 if time_kind(expected) in {"clock", "ISO date-time"} else 1
        record(event_id, "event", expected, actual, (time_key(actual) - time_key(expected)) / divisor, time_tolerance)
    for variable_id, actual in variables.items():
        if variable_id not in known_variables or variable_id not in values.get(scenario, {}):
            raise ValueError(f"variable {variable_id!r} is unknown or unavailable in scenario {scenario!r}")
        actual_number = _number(actual, f"observed variable {variable_id}")
        expected = _number(values[scenario][variable_id], f"expected variable {variable_id}")
        record(variable_id, "variable", expected, actual, actual_number - expected, tolerance)
    result = {"status": "FAIL" if mismatches else "PASS", "contract_id": contract.contract_id,
            "matches": matches, "mismatches": mismatches,
            **({"source": observed["source"]} if "source" in observed else {})}

    return result, contract, selected_occurrences


def compare_world(contract: GuardContract | Mapping[str, Any], observed: Mapping[str, Any]) -> dict[str, Any]:
    """Compare through the one native world comparator without writing values."""
    return _compare_world(contract, observed)[0]


def compare_with_observed_copy(world, observed):
    """Compare once, returning a deep copy changing only the selected event times."""
    result, contract, selected = _compare_world(world, observed)
    copied = deepcopy(dict(world) if isinstance(world, Mapping) else contract.to_dict())
    for event_id, index in selected.items():
        copied["inputs"]["events"][index]["at"] = deepcopy(observed["events"][event_id])
    return result, copied
