from __future__ import annotations

from worldguard.contracts import GUARD_BOUNDARY_SEMANTICS, GuardContract
from worldguard.semantic import NORM_MODALITIES, active_norm_conflicts, norm_activity, event_replay, _fluent_values
from worldguard.status import GuardStatus

from ._helpers import error, requested_semantic_ids, result


def _check(contract: GuardContract):
    guard = "NormGuard"
    requested = requested_semantic_ids(contract)
    norm_model = {
        "norms": contract.inputs.get("norms", []),
        "facts": contract.inputs.get("facts", []),
    }
    norms = norm_model.get("norms", [])


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

    events = contract.inputs.get("events", [])
    initial = _fluent_values(contract.inputs.get("event_model", {}).get("initial_states", []))
    known_fluents = set(initial) | {fluent for event in events for key in ("initiates", "terminates", "requires", "releases") for fluent in _fluent_values(event.get(key))}
    active_norms, unevaluable_conditions = norm_activity(norms, facts, initial, known_fluents)
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
    violations = []
    scenario_ids = sorted({str(event["scenario_id"]) for event in events if event.get("scenario_id")}) or [""]
    for scenario_id in scenario_ids:
        scoped = [event for event in events if not event.get("scenario_id") or event["scenario_id"] == scenario_id]
        if any("at" not in event for event in scoped):
            continue
        for event, before, _ in event_replay(scoped, initial, scenario_id):
            active, _ = norm_activity(norms, facts, before, known_fluents)
            for conflict in active_norm_conflicts(active):
                if conflict not in conflicts:
                    conflicts.append(conflict)
            if event.get("actor") and event.get("action"):
                for norm in active:
                    if norm.get("modality") in {"forbidden", "prohibited"} and (norm.get("actor"), norm.get("action")) == (event["actor"], event["action"]):
                        violations.append({"event_id": event["event_id"], "at": event["at"], "norm": norm, "condition": norm["condition"],
                            **({"scenario_id": scenario_id} if scenario_id else {})})
    if violations:
        return result(contract, guard, GuardStatus.FAIL, channel="norm", impact="supports_fail",
            errors=[error("NORM_VIOLATED_BY_EVENT", "A forbidden action occurs while its norm is active.")],
            counterexamples=[{"kind": "trace", "steps": violations}])
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


def run(contract: GuardContract):
    """Check the complete native NormGuard rules once, then append its boundary."""
    checked = _check(contract)
    if requested_semantic_ids(contract) & GUARD_BOUNDARY_SEMANTICS["NormGuard"]:
        from dataclasses import replace
        from worldguard.status import aggregate_statuses
        checked = replace(checked,
            status=aggregate_statuses([checked.status, GuardStatus.BOUNDARY_EXCEEDED]),
            errors=[*checked.errors, error('NORM_BOUNDARY_PHYSICAL_ENABLEMENT', 'NormGuard does not own resource enablement.')])
    return checked
