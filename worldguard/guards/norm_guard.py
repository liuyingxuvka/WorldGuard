from __future__ import annotations

from worldguard.contracts import GUARD_BOUNDARY_SEMANTICS, GuardContract
from worldguard.semantic import NORM_MODALITIES, active_norm_conflicts
from worldguard.status import GuardStatus

from ._helpers import error, requested_semantic_ids, result


def _condition_expectation(condition):
    if isinstance(condition, str) and condition:
        return condition, True
    if isinstance(condition, dict):
        fact_id = str(condition.get("fact_id", ""))
        expected = condition.get("equals", condition.get("value", True))
        if fact_id and isinstance(expected, bool):
            return fact_id, expected
    return "", None


def run(contract: GuardContract):
    guard = "NormGuard"
    requested = requested_semantic_ids(contract)
    norm_model = {
        "norms": contract.inputs.get("norms", []),
        "facts": contract.inputs.get("facts", []),
    }
    norms = norm_model.get("norms", [])

    if requested & GUARD_BOUNDARY_SEMANTICS[guard]:
        return result(
            contract,
            guard,
            GuardStatus.BOUNDARY_EXCEEDED,
            channel="boundary",
            impact="marks_boundary",
            boundary={"owner": guard, "unsupported_claim_parts": ["physical_enablement"]},
            errors=[error("NORM_BOUNDARY_PHYSICAL_ENABLEMENT", "NormGuard does not own resource enablement.")],
        )

    invalid_modalities = sorted(
        {
            str(norm.get("modality", ""))
            for norm in norms
            if isinstance(norm, dict)
            and str(norm.get("modality", "")) not in NORM_MODALITIES
        }
    )
    if invalid_modalities:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="norm",
            impact="supports_fail",
            errors=[
                error(
                    "NORM_MODALITY_UNKNOWN",
                    "Norm modality is outside the current deontic enumeration.",
                )
            ],
            counterexamples=[
                {"kind": "model_conflict", "steps": invalid_modalities}
            ],
        )

    if not norms:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"needed": "norms"}],
            errors=[error("NORM_MISSING_NORM_MODEL", "No norm model was supplied.")],
        )

    facts = norm_model["facts"]
    malformed_facts = [
        {"index": index, "fact": fact}
        for index, fact in enumerate(facts)
        if not isinstance(fact, dict)
        or not fact.get("fact_id")
        or not isinstance(fact.get("value"), bool)
    ]
    if malformed_facts:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"needed": "fact_id plus boolean fact value"}],
            errors=[
                error(
                    "NORM_UNEVALUABLE_FACT",
                    "Norm conditions require facts with stable ids and explicit boolean values.",
                )
            ],
        )

    fact_ids = [str(fact["fact_id"]) for fact in facts]
    duplicate_fact_ids = sorted(
        {fact_id for fact_id in fact_ids if fact_ids.count(fact_id) > 1}
    )
    if duplicate_fact_ids:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="norm",
            impact="supports_fail",
            errors=[
                error(
                    "NORM_DUPLICATE_FACT_ID",
                    "A norm model cannot give one fact identity multiple truth values.",
                )
            ],
            counterexamples=[
                {"kind": "model_conflict", "steps": duplicate_fact_ids}
            ],
        )

    fact_values = {str(fact["fact_id"]): fact["value"] for fact in facts}
    unevaluable_conditions = []
    active_norms = []
    for index, norm in enumerate(norms):
        condition = norm.get("condition") if isinstance(norm, dict) else None
        fact_id, expected = _condition_expectation(condition)
        if not fact_id or expected is None or fact_id not in fact_values:
            unevaluable_conditions.append(
                {"norm": index, "condition": condition, "needed_fact": fact_id}
            )
            continue
        if fact_values[fact_id] is expected:
            active_norms.append(norm)
    if unevaluable_conditions:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=unevaluable_conditions,
            errors=[
                error(
                    "NORM_MISSING_CONDITION_FACT",
                    "Norm applicability cannot be evaluated from the declared facts.",
                )
            ],
        )
    conflicts = active_norm_conflicts(active_norms)
    if conflicts:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="norm",
            impact="supports_fail",
            errors=[
                error(
                    "NORM_ACTIVE_CONFLICT",
                    "Active norms both forbid and permit or require the same action of the same actor.",
                )
            ],
            counterexamples=[{"kind": "model_conflict", "steps": conflicts}],
        )

    return result(
        contract,
        guard,
        GuardStatus.PASS,
        channel="norm",
        impact="supports_pass",
        payload={"norm_count": len(norms), "evaluated_fact_count": len(facts)},
        supported=True,
        consumed_inputs={"norm_model": norm_model},
    )
