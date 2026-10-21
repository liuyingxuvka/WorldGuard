"""Run the fact-revision model and replay every scenario on the real preview and activation code."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from flowguard.review import review_scenarios


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(__file__).with_name("model.py")

IMPLEMENTED_BY = {
    "BuildFactRevisionPreview": "worldguard/fact_revision.py:preview_fact_revision",
    "ActivateFactRevision": "worldguard/fact_revision.py:activate_fact_revision",
}
TESTED_BY = {
    "fact_revision_requires_current_base": ["tests/test_fact_revision.py:test_stale_base_fingerprint_blocks_preview"],
    "fact_revision_preserves_declared_facts": ["tests/test_fact_revision.py:test_preserved_fact_change_blocks_with_support_delta"],
    "fact_revision_surfaces_contradictions": ["tests/test_fact_revision.py:test_positive_and_negative_support_yield_both_without_explosion"],
    "fact_revision_activation_is_evidence_bound": [
        "tests/test_fact_revision.py:test_activation_requires_current_regression_and_holdout_evidence",
        "tests/test_fact_revision.py:test_missing_holdout_evidence_keeps_activation_blocked",
    ],
    "fact_revision_activation_returns_to_same_task_owner": ["tests/test_fact_revision.py:test_fact_activation_cannot_claim_model_closed_for_task"],
}


def _load_model():
    spec = importlib.util.spec_from_file_location(
        "worldguard_fact_revision_flowguard_model",
        MODEL_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load model from {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _native_findings() -> list[str]:
    sys.path.insert(0, str(ROOT))
    from worldguard.fact_revision import (  # noqa: PLC0415
        FactPolarity,
        FactRevisionTransaction,
        FactSupport,
        FactWorldSnapshot,
        SignedFact,
        StrictFactRule,
        WorldFact,
        preview_fact_revision,
    )

    rain = WorldFact("rain")
    wet = WorldFact("wet")
    unrelated = WorldFact("unrelated")
    positive_rain = FactSupport(
        "support:rain",
        rain.fact_id,
        FactPolarity.POSITIVE,
        "source:observation",
        "evidence:rain",
    )
    negative_rain = FactSupport(
        "support:not-rain",
        rain.fact_id,
        FactPolarity.NEGATIVE,
        "source:counterevidence",
        "evidence:not-rain",
    )
    rule = StrictFactRule(
        "rule:rain-wet",
        (SignedFact(rain.fact_id, FactPolarity.POSITIVE),),
        SignedFact(wet.fact_id, FactPolarity.POSITIVE),
        "source:strict-rule",
        "evidence:rain-wet",
    )
    base = FactWorldSnapshot(
        snapshot_id="base",
        facts=(rain, wet, unrelated),
        supports=(positive_rain,),
        rules=(rule,),
    )
    transaction = FactRevisionTransaction(
        transaction_id="tx",
        base_fingerprint=base.fingerprint,
        additions=(negative_rain,),
        task_id="task:flowguard-fact-revision",
        task_local_owner_id="worldguard.task_local_world_revision",
        iteration=0,
        predecessor_iteration_fingerprint="root",
    )
    preview = preview_fact_revision(base, transaction)
    findings: list[str] = []
    states = {item.fact_id: item.state.value for item in preview.after_states}
    if not preview.contradiction_fact_ids:
        findings.append("native preview did not expose the rain contradiction")
    if states.get(rain.fact_id) != "both":
        findings.append("native preview collapsed four-valued both into a binary state")
    if states.get(unrelated.fact_id) != "neither":
        findings.append("native preview exploded a contradiction into an unrelated fact")
    base_states = {item.fact_id: item.state.value for item in preview.before_states}
    if base_states.get(rain.fact_id) != "true":
        findings.append("native preview mutated the base snapshot")
    return findings


def _model_terminal(model, scenario) -> str:
    state = scenario.initial_state
    for request in scenario.external_input_sequence:
        for block in model.build_workflow().blocks:
            state = next(iter(block.apply(request, state))).new_state
    return state.terminal_status or state.phase


def native_conformance(model) -> dict:
    """Replay every model scenario once on the real preview and activation code."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.test_fact_revision import _base, _transaction
    from worldguard.fact_revision import (
        FactPolarity,
        FactRevisionActivationRequest,
        FactRevisionEvidenceBinding,
        FactRevisionEvidenceKind,
        FactSupport,
        FactWorldSnapshot,
        activate_fact_revision,
        preview_fact_revision,
    )
    from worldguard.task_local_revision import TASK_LOCAL_REVISION_OWNER_ID

    def negative(fact_id: str) -> FactSupport:
        return FactSupport(f"support:{fact_id}-negative", fact_id, FactPolarity.NEGATIVE, "source:counterevidence", f"evidence:{fact_id}")

    def real(preview, activate) -> str:
        base = _base()
        additions = (negative("fact:a"),) if preview is not None and preview.has_contradiction else ()
        if preview is not None and not preview.preservation_ok:
            additions = (negative("fact:b"),)
        transaction = _transaction(transaction_id="revision:conformance", base_fingerprint=base.fingerprint,
                                   additions=additions, preserved_fact_ids=("fact:b",))
        current = base
        if preview is not None and not preview.base_current:
            extra = FactSupport("support:unrelated-positive", "fact:unrelated", FactPolarity.POSITIVE, "source:new", "evidence:new")
            current = FactWorldSnapshot(snapshot_id="world:changed", facts=base.facts, supports=(*base.supports, extra), rules=base.rules)
        frozen = preview_fact_revision(current, transaction)
        if "stale_base_fingerprint" in frozen.finding_codes:
            return "stale_base"
        if "preserved_fact_changed" in frozen.finding_codes:
            return "preservation"
        if activate is None:
            return "previewed" if preview is not None else "not_run"

        def binding(kind, name: str, current: bool = True):
            return FactRevisionEvidenceBinding(f"evidence:{name}", kind, "pass", current, frozen.fingerprint)

        evidence = [binding(FactRevisionEvidenceKind.REGRESSION, "regression", activate.regression_current)]
        if activate.holdout_current:
            evidence.append(binding(FactRevisionEvidenceKind.HOLDOUT, "holdout"))
        if not activate.evidence_cardinality_exact:
            evidence.append(binding(FactRevisionEvidenceKind.REGRESSION, "regression-two"))
        if preview is None:
            evidence = []
        receipt = activate_fact_revision(current, transaction, FactRevisionActivationRequest(
            activation_id="activation:conformance",
            task_id="task-1" if activate.task_owner_current else "task-other",
            task_local_owner_id=TASK_LOCAL_REVISION_OWNER_ID,
            expected_preview_fingerprint=frozen.fingerprint,
            expected_candidate_model_fingerprint=frozen.candidate_snapshot.fingerprint,
            acknowledged_contradiction_fact_ids=frozen.contradiction_fact_ids if activate.contradiction_acknowledged else (),
            evidence=tuple(evidence),
        )).receipt
        if receipt.activated:
            return receipt.terminal_reason
        if "contradiction_visibility_not_acknowledged" in receipt.finding_codes:
            return "contradiction_acknowledgement"
        return "evidence"

    findings = []
    for scenario in model.scenarios():
        steps = {request.action: request for request in scenario.external_input_sequence}
        activate = steps.get("activate") or steps.get("unsafe_activate")
        observed = real(steps.get("preview"), activate)
        expected = _model_terminal(model, scenario)
        if scenario.expected.expected_status == "violation":
            agrees = observed != "task_local_revalidation_required"
        else:
            agrees = observed == expected
        if not agrees:
            findings.append({"scenario": scenario.name, "model": expected, "code": observed})
    return {"ok": not findings, "cases": len(model.scenarios()), "findings": findings}


def main() -> int:
    model = _load_model()
    report = review_scenarios(model.scenarios())
    findings = _native_findings()
    conformance = native_conformance(model)
    print(report.format_text(max_counterexamples=8))
    print(
        json.dumps(
            {
                "artifact_kind": "worldguard_fact_revision_flowguard_report",
                "status": "pass" if report.ok and not findings and conformance["ok"] else "blocked",
                "scenario_count": len(model.scenarios()),
                "findings": findings,
                "conformance": conformance,
                "claim_boundary": (
                    "The finite fact-revision workflow, with each scenario replayed once on the real preview and "
                    "activation code; it does not prove source truth."
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.ok and not findings and conformance["ok"] else 1


if __name__ == "__main__":
    from flowguard.map.runner import run_owner
    raise SystemExit(run_owner(main))
