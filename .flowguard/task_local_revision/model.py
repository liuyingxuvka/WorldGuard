"""Executable FlowGuard model for WorldGuard strict task-local revision."""

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
    action: str = "evaluate"
    task_shape_current: bool = True
    coverage_independent: bool = True
    predictive_licensed: bool = True
    holdout_independent: bool = True
    has_native_gap: bool = False
    gap_changed: bool = True
    iteration: int = 0
    max_iterations: int = 4
    external_boundary_exact: bool = False
    fact_activation: bool = False
    caller_self_reports_closed: bool = False
    unsafe_fact_activation_close: bool = False


@dataclass(frozen=True)
class RevisionState:
    phase: str = "planned"
    task_shape_current: bool = False
    coverage_independent: bool = False
    predictive_licensed: bool = False
    holdout_independent: bool = False
    open_native_gap: bool = False
    fact_candidate_activated: bool = False
    task_closed: bool = False
    terminal_reason: str = ""


class ValidateRevisionEvidence:
    name = "ValidateRevisionEvidence"
    accepted_input_type = RevisionRequest
    reads = (
        "task_shape_current",
        "coverage_independent",
        "holdout_independent",
    )
    writes = (
        "phase",
        "task_shape_current",
        "coverage_independent",
        "holdout_independent",
        "terminal_reason",
    )
    input_description = "one current task/candidate, one fresh candidate mesh run and two revalidations"
    output_description = "validated evidence boundary or one visible block"
    idempotency = "the same inputs produce the same validation state"

    def apply(self, request: RevisionRequest, state: RevisionState):
        if request.action != "evaluate":
            yield FunctionResult(request, state, label="evaluation_not_requested")
            return
        checks = (
            (request.task_shape_current, "legacy_or_shallow_task_shape"),
            (request.coverage_independent, "coverage_not_independent"),
            (request.holdout_independent, "holdout_not_independent"),
        )
        for passed, reason in checks:
            if not passed:
                yield FunctionResult(
                    request,
                    replace(state, phase="blocked", terminal_reason=reason),
                    label=f"{reason}_blocked",
                )
                return
        yield FunctionResult(
            request,
            replace(
                state,
                phase="evidence_current",
                task_shape_current=True,
                coverage_independent=True,
                holdout_independent=True,
            ),
            label="current_evidence_admitted",
        )


class DecideTaskLocalTerminal:
    name = "DecideTaskLocalTerminal"
    accepted_input_type = RevisionRequest
    reads = (
        "predictive_licensed",
        "has_native_gap",
        "gap_changed",
        "iteration",
        "max_iterations",
        "external_boundary_exact",
        "fact_activation",
        "caller_self_reports_closed",
        "unsafe_fact_activation_close",
    )
    writes = (
        "phase",
        "predictive_licensed",
        "open_native_gap",
        "fact_candidate_activated",
        "task_closed",
        "terminal_reason",
    )
    input_description = "current evidence x native gaps x finite task-local iteration state"
    output_description = "one derived continuation, block, handoff, or closure terminal"
    idempotency = "the same current receipts and gap set derive the same terminal"

    def apply(self, request: RevisionRequest, state: RevisionState):
        if request.action != "evaluate" or state.phase != "evidence_current":
            yield FunctionResult(request, state, label="terminal_not_ready")
            return
        if request.unsafe_fact_activation_close:
            yield FunctionResult(
                request,
                replace(
                    state,
                    phase="terminal",
                    predictive_licensed=True,
                    fact_candidate_activated=True,
                    task_closed=True,
                    terminal_reason="unsafe_fact_activation_close",
                ),
                label="unsafe_fact_activation_close_attempted",
            )
            return
        if request.caller_self_reports_closed:
            yield FunctionResult(
                request,
                replace(state, phase="terminal", task_closed=True, terminal_reason="caller_self_report"),
                label="unsafe_self_report_close_attempted",
            )
            return
        if request.fact_activation:
            yield FunctionResult(
                request,
                replace(
                    state,
                    phase="terminal",
                    fact_candidate_activated=True,
                    terminal_reason="task_local_revalidation_required",
                ),
                label="fact_candidate_returns_to_same_owner",
            )
            return
        open_gap = request.has_native_gap or not request.predictive_licensed
        if open_gap:
            if request.external_boundary_exact:
                reason = "external_input_required"
                label = "exact_external_input_required"
            elif request.iteration + 1 >= request.max_iterations:
                reason = "iteration_limit"
                label = "finite_iteration_limit_blocks"
            elif not request.gap_changed:
                reason = "progress_stalled"
                label = "unchanged_gap_stalls"
            else:
                reason = "continue_iteration"
                label = "native_gap_continues"
            yield FunctionResult(
                request,
                replace(
                    state,
                    phase="terminal",
                    predictive_licensed=request.predictive_licensed,
                    open_native_gap=True,
                    terminal_reason=reason,
                ),
                label=label,
            )
            return
        yield FunctionResult(
            request,
            replace(
                state,
                phase="terminal",
                predictive_licensed=True,
                task_closed=True,
                terminal_reason="model_closed_for_task",
            ),
            label="strict_task_model_closed",
        )


def revision_invariants() -> tuple[Invariant, ...]:
    def closure_requires_current_evidence(state: RevisionState, _trace):
        if state.task_closed and not all(
            (
                state.task_shape_current,
                state.coverage_independent,
                state.predictive_licensed,
                state.holdout_independent,
            )
        ):
            return InvariantResult.fail("task closed without complete current evidence")
        return InvariantResult.pass_()

    def open_gap_never_closes(state: RevisionState, _trace):
        if state.task_closed and state.open_native_gap:
            return InvariantResult.fail("open native predictive gap reached task closure")
        return InvariantResult.pass_()

    def fact_activation_is_not_closure(state: RevisionState, _trace):
        if state.fact_candidate_activated and state.task_closed:
            return InvariantResult.fail("fact activation became a second task-closure owner")
        return InvariantResult.pass_()

    return (
        Invariant(
            "task_local_closure_requires_current_typed_evidence",
            "Only current task, coverage, native depth, and independent typed revalidation evidence may close.",
            closure_requires_current_evidence,
        ),
        Invariant(
            "task_local_open_native_gap_never_closes",
            "A native predictive gap or unlicensed prediction cannot reach closure.",
            open_gap_never_closes,
        ),
        Invariant(
            "fact_activation_returns_to_same_task_owner",
            "Fact activation is an intermediate candidate and never a closure owner.",
            fact_activation_is_not_closure,
        ),
    )


INVARIANTS = revision_invariants()


def build_workflow() -> Workflow:
    return Workflow((ValidateRevisionEvidence(), DecideTaskLocalTerminal()), name="worldguard_task_local_revision")


def scenarios() -> tuple[Scenario, ...]:
    workflow = build_workflow()
    return (
        Scenario(
            name="WTL01_strict_current_candidate_closes",
            description="Current typed native and independent revalidation evidence closes with zero gaps.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest(),),
            expected=ScenarioExpectation(expected_status="ok", required_trace_labels=("current_evidence_admitted", "strict_task_model_closed"), summary="strict current task closes"),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WTL02_legacy_shape_blocks",
            description="A former shallow task shape is rejected.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest(task_shape_current=False),),
            expected=ScenarioExpectation(expected_status="ok", required_trace_labels=("legacy_or_shallow_task_shape_blocked",), summary="legacy task shape blocks"),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WTL03_native_gap_continues",
            description="A newly exposed native gap requires another iteration.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest(has_native_gap=True),),
            expected=ScenarioExpectation(expected_status="ok", required_trace_labels=("native_gap_continues",), summary="native gap remains open"),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WTL04_unchanged_gap_stalls",
            description="An unchanged gap fingerprint is not caller-authored progress.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest(has_native_gap=True, gap_changed=False),),
            expected=ScenarioExpectation(expected_status="ok", required_trace_labels=("unchanged_gap_stalls",), summary="no-progress iteration stalls"),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WTL05_iteration_limit_blocks",
            description="An open gap at the finite budget stops visibly.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest(has_native_gap=True, iteration=3, max_iterations=4),),
            expected=ScenarioExpectation(expected_status="ok", required_trace_labels=("finite_iteration_limit_blocks",), summary="finite limit blocks"),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WTL06_exact_external_boundary_stops",
            description="An exact external gap boundary stops without claiming closure.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest(has_native_gap=True, external_boundary_exact=True),),
            expected=ScenarioExpectation(expected_status="ok", required_trace_labels=("exact_external_input_required",), summary="exact external input is visible"),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WTL07_fact_activation_revalidates",
            description="Fact activation returns to the same task-local owner.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest(fact_activation=True),),
            expected=ScenarioExpectation(expected_status="ok", required_trace_labels=("fact_candidate_returns_to_same_owner",), summary="fact activation is intermediate"),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WTL08_self_report_close_is_counterexample",
            description="A caller self-report cannot become task closure.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest(caller_self_reports_closed=True),),
            expected=ScenarioExpectation(
                expected_status="violation",
                expected_violation_names=("task_local_closure_requires_current_typed_evidence",),
                required_trace_labels=("unsafe_self_report_close_attempted",),
                summary="self-report closure violates the current evidence invariant",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WTL09_fact_activation_close_is_counterexample",
            description="Fact activation cannot become a second task-closure owner.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest(unsafe_fact_activation_close=True),),
            expected=ScenarioExpectation(
                expected_status="violation",
                expected_violation_names=("fact_activation_returns_to_same_task_owner",),
                required_trace_labels=("unsafe_fact_activation_close_attempted",),
                summary="fact activation closure violates the sole-owner invariant",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WTL10_holdout_reuse_blocks",
            description="Candidate-construction evidence cannot be reused as holdout evidence.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest(holdout_independent=False),),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("holdout_not_independent_blocked",),
                summary="non-independent holdout blocks",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
        Scenario(
            name="WTL11_unlicensed_prediction_continues",
            description="A candidate without a native predictive license remains open even without a named gap.",
            initial_state=RevisionState(),
            external_input_sequence=(RevisionRequest(predictive_licensed=False),),
            expected=ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("native_gap_continues",),
                summary="unlicensed prediction remains open",
            ),
            workflow=workflow,
            invariants=INVARIANTS,
        ),
    )


__all__ = ["INVARIANTS", "build_workflow", "scenarios"]
