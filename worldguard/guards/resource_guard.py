from __future__ import annotations

import math

from worldguard.contracts import GuardContract
from worldguard.status import GuardStatus

from ._helpers import error, requested_semantic_ids, result


def run(contract: GuardContract):
    """Check the declared finite ordered CPN firing trace; no scheduler is inferred."""
    guard = "ResourceGuard"
    requested = requested_semantic_ids(contract)
    resources = contract.inputs.get("resources", {})
    places = resources.get("places", {}) if isinstance(resources, dict) else {}
    transitions = resources.get("transitions", []) if isinstance(resources, dict) else []
    capacities = resources.get("capacities", {}) if isinstance(resources, dict) else {}
    inventory = resources.get("inventory", []) if isinstance(resources, dict) else []

    if requested & {"permission", "authorization", "obligation"}:
        return result(
            contract,
            guard,
            GuardStatus.BOUNDARY_EXCEEDED,
            channel="boundary",
            impact="marks_boundary",
            boundary={"owner": guard, "unsupported_claim_parts": ["norm_authorization"]},
            errors=[error("RESOURCE_BOUNDARY_NORM_AUTHORIZATION", "ResourceGuard does not own permission.")],
        )

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
            GuardStatus.FAIL,
            channel="resource",
            impact="supports_fail",
            errors=[
                error(
                    "RESOURCE_CAPACITY_OVERFLOW",
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

    marking: dict[tuple[str, str], float] = {}
    malformed_tokens = []
    for place, tokens in places.items():
        if not isinstance(tokens, list):
            malformed_tokens.append({"place": place, "tokens": tokens})
            continue
        for token in tokens:
            if (
                not isinstance(token, dict)
                or not token.get("color")
                or isinstance(token.get("qty"), bool)
                or not isinstance(token.get("qty"), (int, float))
                or not math.isfinite(float(token.get("qty", 0)))
                or float(token.get("qty", 0)) < 0
            ):
                malformed_tokens.append({"place": place, "token": token})
                continue
            key = (str(place), str(token["color"]))
            marking[key] = marking.get(key, 0.0) + float(token["qty"])
    if malformed_tokens:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=malformed_tokens,
            errors=[error("RESOURCE_UNEVALUABLE_TOKEN", "Resource tokens need color and finite non-negative quantity.")],
        )

    for transition_index, transition in enumerate(transitions):
        if not isinstance(transition, dict) or not transition.get("id"):
            return result(
                contract,
                guard,
                GuardStatus.GAP,
                channel="gap",
                impact="creates_gap",
                missing_slots=[{"needed": "stable transition id"}],
                errors=[error("RESOURCE_UNEVALUABLE_TRANSITION", "Every resource transition needs a stable id.")],
            )
        for need in transition.get("consumes", []):
            place = str(need.get("place", "")) if isinstance(need, dict) else ""
            color = str(need.get("color", "")) if isinstance(need, dict) else ""
            qty = need.get("qty") if isinstance(need, dict) else None
            if (
                place not in places
                or not color
                or isinstance(qty, bool)
                or not isinstance(qty, (int, float))
                or not math.isfinite(float(qty))
                or float(qty) < 0
            ):
                return result(
                    contract,
                    guard,
                    GuardStatus.GAP,
                    channel="gap",
                    impact="creates_gap",
                    missing_slots=[{"transition": transition["id"], "need": need}],
                    errors=[error("RESOURCE_UNEVALUABLE_TRANSITION", "A consumption arc is malformed or references an unknown place.")],
                )
            key = (place, color)
            available = marking.get(key, 0.0)
            if available < float(qty):
                if transition_index == 0:
                    return result(
                        contract,
                        guard,
                        GuardStatus.GAP,
                        channel="gap",
                        impact="creates_gap",
                        missing_slots=[{"transition": transition["id"], "place": place, "color": color, "required_qty": qty, "available_qty": available}],
                        errors=[error("RESOURCE_MISSING_TOKEN", "Required colored token is missing.")],
                    )
                return result(
                    contract,
                    guard,
                    GuardStatus.FAIL,
                    channel="resource",
                    impact="supports_fail",
                    errors=[error("RESOURCE_CUMULATIVE_OVERCONSUMPTION", "The ordered transition set consumes more resource than remains available.")],
                    counterexamples=[{"kind": "trace", "steps": [{"transition": transition["id"], "place": place, "color": color, "required_qty": qty, "available_qty": available}]}],
                )
            marking[key] = available - float(qty)
        for produced in transition.get("produces", []):
            place = str(produced.get("place", "")) if isinstance(produced, dict) else ""
            color = str(produced.get("color", "")) if isinstance(produced, dict) else ""
            qty = produced.get("qty") if isinstance(produced, dict) else None
            if (
                not place
                or not color
                or isinstance(qty, bool)
                or not isinstance(qty, (int, float))
                or not math.isfinite(float(qty))
                or float(qty) < 0
            ):
                return result(
                    contract,
                    guard,
                    GuardStatus.GAP,
                    channel="gap",
                    impact="creates_gap",
                    missing_slots=[{"transition": transition["id"], "produces": produced}],
                    errors=[error("RESOURCE_UNEVALUABLE_TRANSITION", "A production arc is malformed.")],
                )
            key = (place, color)
            marking[key] = marking.get(key, 0.0) + float(qty)
            capacity = capacities.get(place)
            place_total = sum(value for (marked_place, _), value in marking.items() if marked_place == place)
            if capacity is not None and place_total > float(capacity):
                return result(
                    contract,
                    guard,
                    GuardStatus.FAIL,
                    channel="resource",
                    impact="supports_fail",
                    errors=[error("RESOURCE_CAPACITY_OVERFLOW", "Produced tokens exceed place capacity.")],
                    counterexamples=[{"kind": "trace", "steps": [{"transition": transition["id"], "produced": produced, "place_total": place_total, "capacity": capacity}]}],
                )

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
