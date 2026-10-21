"""Executable FlowGuard model for WorldGuard task-local fact revision."""

from __future__ import annotations

from dataclasses import dataclass, replace

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    Scenario,
    ScenarioExpectation,
    Workflow,
)


FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"


@dataclass(frozen=True)
class RevisionRequest:
    action: str
    base_current: bool = True
    preservation_ok: bool = True
    has_contradiction: bool = False
    contradiction_acknowledged: bool = False
    regression_current: bool = True
    holdout_current: bool = True
    evidence_cardinality_exact: bool = True
    task_owner_current: bool = True


@dataclass(frozen=True)
class RevisionState:
    phase: str = "planned"
    preview_frozen: bool = False
    base_current: bool = True
    preservation_ok: bool = True
    contradiction_visible: bool = False
    contradiction_acknowledged: bool = False
    regression_current: bool = False
    holdout_current: bool = False
    evidence_cardinality_exact: bool = False
    activated: bool = False
    task_owner_current: bool = False
    revalidation_required: bool = False
    task_closed: bool = False
    terminal_status: str = ""


class BuildFactRevisionPreview:
    """Map one preview request and current state to every allowed next state."""

    name = "BuildFactRevisionPreview"
    accepted_input_type = RevisionRequest
    reads = ("action", "base_current", "preservation_ok", "has_contradiction")
    writes = (
        "phase",
        "preview_frozen",
        "base_current",
        "preservation_ok",
        "contradiction_visible",
        "terminal_status",
    )
    input_description = "one immutable task-local fact-revision preview request"
    output_description = "one frozen preview or a visible typed block"
    idempotency = "the same base and transaction produce the same preview state"

    def apply(self, request: RevisionRequest, state: RevisionState):
        if request.action != "preview":
            yield FunctionResult(request, state, label="preview_not_requested")
            return
        if state.phase != "planned":
            yield FunctionResult(
                request,
                replace(state, phase="blocked", terminal_status="order"),
                label="preview_order_blocked",
            )
            return
        if not request.base_current:
            yield FunctionResult(
                request,
                replace(
                    state,
                    phase="blocked",
                    base_current=False,
                    terminal_status="stale_base",
                ),
                label="stale_base_blocked",
            )
            return
        if not request.preservation_ok:
            yield FunctionResult(
                request,
                replace(
                    state,
                    phase="blocked",
                    preservation_ok=False,
                    terminal_status="preservation",
                ),
                label="preservation_change_blocked",
            )
            return
        yield FunctionResult(
            request,
            replace(
                state,
                phase="previewed",
                preview_frozen=True,
                base_current=True,
                preservation_ok=True,
                contradiction_visible=request.has_contradiction,
            ),
            label=(
                "contradiction_visible_in_preview"
                if request.has_contradiction
                else "preview_frozen"
            ),
        )


class ActivateFactRevision:
    """Map one activation request and current preview to every allowed terminal."""

    name = "ActivateFactRevision"
    accepted_input_type = RevisionRequest
    reads = (
        "action",
        "contradiction_acknowledged",
        "regression_current",
        "holdout_current",
        "evidence_cardinality_exact",
        "task_owner_current",
    )
    writes = (
        "phase",
        "contradiction_acknowledged",
        "regression_current",
        "holdout_current",
        "evidence_cardinality_exact",
        "activated",
        "task_owner_current",
        "revalidation_required",
        "terminal_status",
    )
    input_description = "one activation request bound to the exact preview"
    output_description = "activated or one visible evidence/acknowledgement block"
    idempotency = "one transaction id may produce at most one activation receipt"

    def apply(self, request: RevisionRequest, state: RevisionState):
        if request.action == "unsafe_activate":
            yield FunctionResult(
                request,
                replace(
                    state,
                    phase="terminal",
                    activated=True,
                    terminal_status="unsafe",
                ),
                label="unsafe_activation_attempted",
            )
            return
        if request.action != "activate":
            yield FunctionResult(request, state, label="activation_not_requested")
            return
        if state.phase != "previewed" or not state.preview_frozen:
            yield FunctionResult(
                request,
                replace(state, phase="blocked", terminal_status="missing_preview"),
                label="missing_preview_blocked",
            )
            return
        if state.contradiction_visible and not request.contradiction_acknowledged:
            yield FunctionResult(
                request,
                replace(
                    state,
                    phase="blocked",
                    contradiction_acknowledged=False,
                    terminal_status="contradiction_acknowledgement",
                ),
                label="unacknowledged_contradiction_blocked",
            )
            return
        if (
            not request.regression_current
            or not request.holdout_current
            or not request.evidence_cardinality_exact
            or not request.task_owner_current
        ):
            yield FunctionResult(
                request,
                replace(
                    state,
                    phase="blocked",
                    contradiction_acknowledged=request.contradiction_acknowledged,
                    regression_current=request.regression_current,
                    holdout_current=request.holdout_current,
                    evidence_cardinality_exact=request.evidence_cardinality_exact,
                    task_owner_current=request.task_owner_current,
                    terminal_status="evidence",
                ),
                label="activation_evidence_blocked",
            )
            return
        yield FunctionResult(
            request,
            replace(
                state,
                phase="terminal",
                contradiction_acknowledged=request.contradiction_acknowledged,
                regression_current=True,
                holdout_current=True,
                evidence_cardinality_exact=True,
                task_owner_current=True,
                activated=True,
                revalidation_required=True,
                terminal_status="task_local_revalidation_required",
            ),
            label="revision_activated_for_task_local_revalidation",
        )


def revision_invariants() -> tuple[Invariant, ...]:
    def no_stale_activation(state: RevisionState, _trace):
        if state.activated and not state.base_current:
            return InvariantResult.fail("stale base reached activation")
        return InvariantResult.pass_()

    def preservation(state: RevisionState, _trace):
        if state.activated and not state.preservation_ok:
            return InvariantResult.fail("preserved fact changed during activation")
        return InvariantResult.pass_()

    def contradiction_visible(state: RevisionState, _trace):
        if state.activated and state.contradiction_visible and not state.contradiction_acknowledged:
            return InvariantResult.fail("contradiction was activated without acknowledgement")
        return InvariantResult.pass_()

    def evidence_bound(state: RevisionState, _trace):
        if state.activated and not (
            state.preview_frozen
            and state.regression_current
            and state.holdout_current
            and state.evidence_cardinality_exact
        ):
            return InvariantResult.fail(
                "activation is not bound to a frozen preview and current regression/holdout evidence"
            )
        return InvariantResult.pass_()

    def activation_returns_to_same_owner(state: RevisionState, _trace):
        if state.activated and not (
            state.task_owner_current
            and state.revalidation_required
            and not state.task_closed
            and state.terminal_status == "task_local_revalidation_required"
        ):
            return InvariantResult.fail(
                "fact activation bypassed same-owner task-local revalidation"
            )
        return InvariantResult.pass_()

    return (
        Invariant(
            "fact_revision_requires_current_base",
            "A stale base cannot reach activation.",
            no_stale_activation,
        ),
        Invariant(
            "fact_revision_preserves_declared_facts",
            "Declared preserved facts cannot change.",
            preservation,
        ),
        Invariant(
            "fact_revision_surfaces_contradictions",
            "A visible contradiction requires explicit activation acknowledgement.",
            contradiction_visible,
        ),
        Invariant(
            "fact_revision_activation_is_evidence_bound",
            "Activation requires the frozen preview plus current regression and holdout evidence.",
            evidence_bound,
        ),
        Invariant(
            "fact_revision_activation_returns_to_same_task_owner",
            "Activation is an intermediate candidate handoff and never task closure.",
            activation_returns_to_same_owner,
        ),
    )


INVARIANTS = revision_invariants()


def build_workflow() -> Workflow:
    return Workflow(
        (BuildFactRevisionPreview(), ActivateFactRevision()),
        name="worldguard_fact_revision",
    )


def scenarios() -> tuple[Scenario, ...]:
    workflow = build_workflow()
    return (
        Scenario(
            name="WFR01_current_revision_activates",
            description="A current preview with complete evidence activates.",
            initial_state=RevisionState(),
            external_input_sequence=(
                RevisionRequest("preview"),
                RevisionRequest("activate"),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=(
                    "preview_frozen",
                    "revision_activated_for_task_local_revalidation",
                ),
                summary="current evidence-bound fact candidate returns for task-local revalidation",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WFR02_contradiction_needs_acknowledgement",
            description="A contradiction stays visible and blocks unacknowledged activation.",
            initial_state=RevisionState(),
            external_input_sequence=(
                RevisionRequest("preview", has_contradiction=True),
                RevisionRequest("activate", contradiction_acknowledged=False),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=(
                    "contradiction_visible_in_preview",
                    "unacknowledged_contradiction_blocked",
                ),
                summary="visible contradiction blocks until acknowledged",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WFR03_stale_base_blocks",
            description="A stale base cannot produce an activatable preview.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest("preview", base_current=False),),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("stale_base_blocked",),
                summary="stale base is a visible block",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WFR04_preservation_change_blocks",
            description="A requested change to a preserved fact is rejected.",
            initial_state=RevisionState(),
            external_input_sequence=(
                RevisionRequest("preview", preservation_ok=False),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("preservation_change_blocked",),
                summary="preservation violation is a visible block",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WFR05_missing_holdout_blocks",
            description="Activation requires current holdout evidence.",
            initial_state=RevisionState(),
            external_input_sequence=(
                RevisionRequest("preview"),
                RevisionRequest("activate", holdout_current=False),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("preview_frozen", "activation_evidence_blocked"),
                summary="missing holdout evidence blocks activation",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WFR06_unsafe_activation_is_counterexample",
            description="A bypass that activates without preview or evidence violates the hard invariant.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest("unsafe_activate"),),
            expected=ScenarioExpectation(
                expected_status="violation",
                expected_violation_names=(
                    "fact_revision_activation_is_evidence_bound",
                    "fact_revision_activation_returns_to_same_task_owner",
                ),
                required_trace_labels=("unsafe_activation_attempted",),
                summary="unsafe activation is rejected by the model",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WFR07_duplicate_evidence_kind_blocks",
            description="Duplicate regression or holdout evidence cannot replace the exact pair.",
            initial_state=RevisionState(),
            external_input_sequence=(
                RevisionRequest("preview"),
                RevisionRequest("activate", evidence_cardinality_exact=False),
            ),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("preview_frozen", "activation_evidence_blocked"),
                summary="duplicate evidence cardinality blocks activation",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
    )


__all__ = ["INVARIANTS", "build_workflow", "scenarios"]


# Contract: what this model is about in the real code, its known-bad variants, and the replay on that code.

from pathlib import Path  # noqa: E402
import sys  # noqa: E402

from flowguard.explorer import Explorer  # noqa: E402

MODEL_ID = "fact_revision"
COMPONENTS = ["worldguard.revision"]
ROOT = Path(__file__).resolve().parents[2]
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
SAFE = tuple(scenario for scenario in scenarios() if scenario.expected.expected_status == "ok")
SAFE_INPUTS = tuple(dict.fromkeys(request for scenario in SAFE for request in scenario.external_input_sequence))
REQUIRED_LABELS = tuple(dict.fromkeys(label for scenario in SAFE for label in scenario.expected.required_trace_labels))


def _explorer(blocks, inputs=SAFE_INPUTS, invariant_names=None, labels=REQUIRED_LABELS) -> Explorer:
    return Explorer(
        workflow=Workflow(tuple(blocks), name="worldguard_fact_revision"),
        initial_states=(RevisionState(),),
        external_inputs=tuple(inputs),
        invariants=tuple(item for item in INVARIANTS if invariant_names is None or item.name in invariant_names),
        max_sequence_length=2,
        required_labels=tuple(labels),
    )


def build_explorer() -> Explorer:
    """Every ordered pair of the safe scenario inputs (preview, then activate, and every other order)."""
    return _explorer(build_workflow().blocks)


class _ActivatesWithoutHoldout(ActivateFactRevision):
    """Known bad: activation goes ahead without current holdout evidence."""

    def apply(self, request, state):
        for result in super().apply(replace(request, holdout_current=True), state):
            yield replace(result, new_state=replace(result.new_state, holdout_current=request.holdout_current))


class _ActivatesUnacknowledgedContradiction(ActivateFactRevision):
    """Known bad: activation goes ahead although the visible contradiction was not acknowledged."""

    def apply(self, request, state):
        for result in super().apply(replace(request, contradiction_acknowledged=True), state):
            yield replace(result, new_state=replace(result.new_state, contradiction_acknowledged=request.contradiction_acknowledged))


def broken_variants() -> dict[str, Explorer]:
    """Known-bad variants, each explored with only the invariants that must catch it.

    Two replace the activation block; the scenario that expects a violation (an activation without preview or
    evidence) is a known-bad input to the design itself.
    """
    def swapped(broken):
        return tuple(broken if isinstance(broken, type(block)) else block for block in build_workflow().blocks)

    variants = {
        "activates_without_holdout": _explorer(
            swapped(_ActivatesWithoutHoldout()), invariant_names={"fact_revision_activation_is_evidence_bound"}, labels=()),
        "activates_unacknowledged_contradiction": _explorer(
            swapped(_ActivatesUnacknowledgedContradiction()), invariant_names={"fact_revision_surfaces_contradictions"}, labels=()),
    }
    for scenario in scenarios():
        if scenario.expected.expected_status == "violation":
            variants[scenario.name] = _explorer(
                build_workflow().blocks, inputs=scenario.external_input_sequence,
                invariant_names=set(scenario.expected.expected_violation_names), labels=())
    return variants


class ReplayReport:
    """Conformance result: how many model cases ran on the real code, and the mismatches."""

    def __init__(self, checked: int, mismatches: list[str]) -> None:
        self.checked = checked
        self.mismatches = tuple(mismatches)
        self.ok = not self.mismatches

    def format_text(self, max_examples: int | None = None) -> str:
        lines = [f"conformance: {self.checked - len(self.mismatches)}/{self.checked} model cases match the real code"]
        return "\n".join(lines + [f"  mismatch: {line}" for line in self.mismatches[:max_examples]])


def _four_valued_findings() -> list[str]:
    """The preview keeps a contradiction as 'both', leaves unrelated facts alone and does not change the base."""
    from worldguard.fact_revision import (
        FactPolarity,
        FactRevisionTransaction,
        FactSupport,
        FactWorldSnapshot,
        SignedFact,
        StrictFactRule,
        WorldFact,
        preview_fact_revision,
    )

    rain, wet, unrelated = WorldFact("rain"), WorldFact("wet"), WorldFact("unrelated")
    positive_rain = FactSupport("support:rain", rain.fact_id, FactPolarity.POSITIVE, "source:observation", "evidence:rain")
    negative_rain = FactSupport("support:not-rain", rain.fact_id, FactPolarity.NEGATIVE, "source:counterevidence", "evidence:not-rain")
    rule = StrictFactRule("rule:rain-wet", (SignedFact(rain.fact_id, FactPolarity.POSITIVE),),
                          SignedFact(wet.fact_id, FactPolarity.POSITIVE), "source:strict-rule", "evidence:rain-wet")
    base = FactWorldSnapshot(snapshot_id="base", facts=(rain, wet, unrelated), supports=(positive_rain,), rules=(rule,))
    transaction = FactRevisionTransaction(
        transaction_id="tx", base_fingerprint=base.fingerprint, additions=(negative_rain,),
        task_id="task:flowguard-fact-revision", task_local_owner_id="worldguard.task_local_world_revision",
        iteration=0, predecessor_iteration_fingerprint="root",
    )
    preview = preview_fact_revision(base, transaction)
    findings = []
    states = {item.fact_id: item.state.value for item in preview.after_states}
    if not preview.contradiction_fact_ids:
        findings.append("the preview did not expose the rain contradiction")
    if states.get(rain.fact_id) != "both":
        findings.append("the preview collapsed 'both' into a binary state")
    if states.get(unrelated.fact_id) != "neither":
        findings.append("the preview exploded a contradiction into an unrelated fact")
    if {item.fact_id: item.state.value for item in preview.before_states}.get(rain.fact_id) != "true":
        findings.append("the preview mutated the base snapshot")
    return findings


def _model_terminal(scenario) -> str:
    state = scenario.initial_state
    for request in scenario.external_input_sequence:
        for block in build_workflow().blocks:
            state = next(iter(block.apply(request, state))).new_state
    return state.terminal_status or state.phase


def conformance() -> ReplayReport:
    """Replay every model scenario once on the real preview and activation code, plus the four-valued sample."""
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

    four_valued = _four_valued_findings()
    mismatches = ["four-valued sample: " + "; ".join(four_valued)] if four_valued else []
    for scenario in scenarios():
        steps = {request.action: request for request in scenario.external_input_sequence}
        observed = real(steps.get("preview"), steps.get("activate") or steps.get("unsafe_activate"))
        expected = _model_terminal(scenario)
        if scenario.expected.expected_status == "violation":
            agrees = observed != "task_local_revalidation_required"
        else:
            agrees = observed == expected
        if not agrees:
            mismatches.append(f"{scenario.name}: model {expected!r}, real code {observed!r}")
    return ReplayReport(len(scenarios()) + 1, mismatches)


if __name__ == "__main__":
    print(build_explorer().explore().format_text())
    for name, variant in broken_variants().items():
        print(f"known-bad {name}: {'caught' if not variant.explore().ok else 'MISSED'}")
    print(conformance().format_text())
