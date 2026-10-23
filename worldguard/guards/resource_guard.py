from __future__ import annotations

import math

from worldguard.contracts import GUARD_BOUNDARY_SEMANTICS, GuardContract
from worldguard.status import GuardStatus
from worldguard.semantic import token_replay

from ._helpers import error, requested_semantic_ids, result


def _check(contract: GuardContract):
    """Check the declared finite ordered CPN firing trace; no scheduler is inferred."""
    guard = "ResourceGuard"
    requested = requested_semantic_ids(contract)
    resources = contract.inputs.get("resources", {})
    places = resources.get("places", {}) if isinstance(resources, dict) else {}
    transitions = resources.get("transitions", []) if isinstance(resources, dict) else []
    capacities = resources.get("capacities", {}) if isinstance(resources, dict) else {}
    inventory = resources.get("inventory", []) if isinstance(resources, dict) else []


    malformed_inventory = [
        row
        for row in inventory
        if not isinstance(row, dict)
        or not row.get("resource_id")
        or not row.get("unit")
        or isinstance(row.get("quantity"), bool)
        or not isinstance(row.get("quantity"), (int, float))
        or not math.isfinite(float(row.get("quantity", 0)))
        or row.get("quantity", 0) < 0
    ]
    if malformed_inventory:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="resource",
            impact="creates_gap",
            errors=[
                error(
                    "RESOURCE_UNEVALUABLE_INVENTORY",
                    "Declared inventory quantities must be finite and non-negative.",
                )
            ],
            counterexamples=[{"kind": "model_conflict", "steps": malformed_inventory}],
        )

    if not places and not transitions:
        if inventory:
            return result(
                contract,
                guard,
                GuardStatus.PASS,
                channel="resource",
                impact="supports_pass",
                payload={"inventory_count": len(inventory), "transition_count": 0},
                supported=True,
                consumed_inputs={"resources": resources},
            )
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"needed": "places and transitions"}],
            errors=[error("RESOURCE_MISSING_RESOURCE_MODEL", "No CPN resource model was supplied.")],
        )

    if not places or not transitions:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"needed": "both places and transitions when either is declared"}],
            errors=[error("RESOURCE_MISSING_RESOURCE_MODEL", "The transition model is incomplete.")],
        )

    marking, problem = token_replay(resources, events=contract.inputs.get("events", []))
    if problem:
        kind = problem["kind"]
        errors = {
            "bad_token": error("RESOURCE_UNEVALUABLE_TOKEN", "Tokens need color and finite non-negative quantity."),
            "bad_transition": error("RESOURCE_UNEVALUABLE_TRANSITION", "A transition or arc is incomplete."),
            "missing_initial": error("RESOURCE_MISSING_TOKEN", "The transition requires an unavailable token."),
            "overspend": error("RESOURCE_CUMULATIVE_OVERCONSUMPTION", "The ordered transitions consume more than remains."),
            "capacity": error("RESOURCE_CAPACITY_OVERFLOW", "Produced tokens exceed place capacity."),
            "duplicated": error("RESOURCE_UNIQUE_TOKEN_DUPLICATED", "A unique color exists more than once across places."),
            "participant": error("RESOURCE_EVENT_PARTICIPANT_UNNAMED", "A linked event does not name the unique participant moved by its transition."),
        }
        status = GuardStatus.GAP if kind in {"bad_token", "bad_transition", "participant"} else GuardStatus.FAIL
        return result(contract, guard, status, channel="resource", impact="supports_fail",
            errors=[errors[kind]], missing_slots=[problem] if status == GuardStatus.GAP else [],
            counterexamples=[{"kind": "trace", "steps": [problem]}] if status == GuardStatus.FAIL else [])

    return result(
        contract,
        guard,
        GuardStatus.PASS,
        channel="resource",
        impact="supports_pass",
        payload={"inventory_count": len(inventory), "transition_count": len(transitions)},
        supported=True,
        consumed_inputs={"resources": resources},
    )


def run(contract: GuardContract):
    """Check the complete native ResourceGuard rules once, then append its boundary."""
    checked = _check(contract)
    if requested_semantic_ids(contract) & GUARD_BOUNDARY_SEMANTICS["ResourceGuard"]:
        from dataclasses import replace
        from worldguard.status import aggregate_statuses
        checked = replace(checked,
            status=aggregate_statuses([checked.status, GuardStatus.BOUNDARY_EXCEEDED]),
            errors=[*checked.errors, error('RESOURCE_BOUNDARY_NORM_AUTHORIZATION', 'ResourceGuard does not own permission.')])
    return checked
