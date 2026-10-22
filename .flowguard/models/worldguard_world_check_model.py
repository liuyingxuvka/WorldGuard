"""Finite outcome model of one native world check, replayed on the real CLI.

Inputs are declared semantic features, never a second clock/SCM/Guard engine.
The six typed stages model the check lifecycle; conformance runs its concrete
worlds through worldguard.cli.main and compares exact exit/status terminals.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass, replace
import io
import json
from pathlib import Path
import sys
import tempfile
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer

MODEL_ID = "world_check"
PARENT = "system"
COMPONENTS = ["worldguard.qualification"]
IMPLEMENTED_BY = {
    "ParseContract": "worldguard/contracts.py:GuardContract.from_dict",
    "EvaluateScenarios": "worldguard/semantic.py:causal_scenario_values",
    "RunGuards": "worldguard/qualification.py:qualify_guard_contract",
    "EvaluateClaimRows": "worldguard/claim_binding.py:evaluate_claim_binding",
    "Aggregate": "worldguard/status.py:aggregate_statuses",
    "ReportExit": "worldguard/cli.py:main",
}
TESTED_BY = {
    "bad_time_is_input_error": ["tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively"],
    "clock_times_order_events": ["tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively"],
    "duplicate_event_id_is_input_error": ["tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively"],
    "scenario_values_reach_constraints": [
        "tests/test_world_model_language.py:test_scenario_overrides_reach_constraints_and_claim_rows",
        "tests/test_world_model_language.py:test_interventions_on_empty_scenarios_reach_constraints_and_claim_rows",
        "tests/test_world_model_language.py:test_completed_causal_runs_survive_another_incomplete_run",
    ],
    "declared_boundary_is_boundary_exceeded": [
        "tests/test_qualification.py:test_declared_boundary_trials_keep_their_native_status",
        "tests/test_qualification.py:test_each_derived_guard_boundary_is_a_final_boundary",
    ],
    "pass_needs_bound_true_rows": ["tests/test_world_model_language.py:test_a_claim_without_assertions_is_not_bound_to_the_world_model"],
}
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class CheckRequest:
    case_id: str
    time_form: str = "label"
    event_order_correct: bool = True
    duplicate_ids: bool = False
    scm_mode: str = "none"
    boundary: str = "none"
    rows: str = "order"


@dataclass(frozen=True)
class Parsed:
    request: CheckRequest


@dataclass(frozen=True)
class ScenariosEvaluated:
    request: CheckRequest


@dataclass(frozen=True)
class GuardsRun:
    request: CheckRequest


@dataclass(frozen=True)
class ClaimRowsEvaluated:
    request: CheckRequest


@dataclass(frozen=True)
class Aggregated:
    request: CheckRequest


@dataclass(frozen=True)
class Terminal:
    exit_code: int
    status: str


@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    event_order_correct: bool = True
    scenario_failed: bool = False
    intervention_failed: bool = False
    inputs_missing: bool = False
    guard_status: str = "NOT_RUN"
    row_status: str = "NOT_RUN"
    aggregate_status: str = "NOT_RUN"
    exit_code: int | None = None
    status: str = ""
    terminal: bool = False


class ParseContract:
    name = "ParseContract"
    reads = ()
    writes = ("request", "event_order_correct", "inputs_missing", "exit_code", "status", "terminal")
    accepted_input_type = CheckRequest
    input_description = "Declared time kind, identity and scenario/claim features for one world"
    output_description = "Parsed request or the genuine input-error terminal"
    idempotency = "Each request starts fresh; no prior world result is reused."

    def invalid_time(self, request):
        return request.time_form in {"word", "mixed"}

    def duplicate(self, request):
        return request.duplicate_ids

    def event_order(self, request):
        return request.event_order_correct

    def apply(self, request: CheckRequest, state: State) -> Iterable[FunctionResult]:
        state = State(request=request, event_order_correct=self.event_order(request), inputs_missing=request.time_form == "missing")
        if self.invalid_time(request) or self.duplicate(request):
            yield FunctionResult(Terminal(2, "error"), replace(state, exit_code=2, status="error", terminal=True), "input_error")
        else:
            yield FunctionResult(Parsed(request), state, "contract_parsed")


class EvaluateScenarios:
    name = "EvaluateScenarios"
    reads = ("request", "inputs_missing")
    writes = ("scenario_failed", "intervention_failed", "inputs_missing")
    accepted_input_type = Parsed
    input_description = "Which declared numerical run contradicts the constraint, if any"
    output_description = "Scenario facts passed to native world checking"
    idempotency = "Identical declared run features have identical finite outcomes."

    def scenario_fails(self, request):
        return request.scm_mode in {"scenario", "partial_fail"}

    def intervention_fails(self, request):
        return request.scm_mode == "intervention"

    def apply(self, parsed: Parsed, state: State) -> Iterable[FunctionResult]:
        request = parsed.request
        yield FunctionResult(ScenariosEvaluated(request), replace(state,
            scenario_failed=self.scenario_fails(request), intervention_failed=self.intervention_fails(request),
            inputs_missing=state.inputs_missing or request.scm_mode in {"partial_fail", "partial_gap"}), "scenarios_evaluated")


class RunGuards:
    name = "RunGuards"
    reads = ("event_order_correct", "scenario_failed", "intervention_failed", "inputs_missing")
    writes = ("guard_status",)
    accepted_input_type = ScenariosEvaluated
    input_description = "Finite declared world contradictions, missing inputs and boundary ownership"
    output_description = "World-check status before the claim rows"
    idempotency = "A check preserves its real contradictions and missing inputs."

    def apply(self, evaluated: ScenariosEvaluated, state: State) -> Iterable[FunctionResult]:
        if not state.event_order_correct or state.scenario_failed or state.intervention_failed:
            status = "FAIL"
        elif state.inputs_missing or evaluated.request.boundary == "unselected":
            status = "GAP"
        elif evaluated.request.boundary == "owned":
            status = "BOUNDARY_EXCEEDED"
        else:
            status = "PASS"
        yield FunctionResult(GuardsRun(evaluated.request), replace(state, guard_status=status), "guards_run")


class EvaluateClaimRows:
    name = "EvaluateClaimRows"
    reads = ("event_order_correct", "scenario_failed", "intervention_failed", "inputs_missing")
    writes = ("row_status",)
    accepted_input_type = GuardsRun
    input_description = "Absent, false, unknown, event-order or numerical claim rows"
    output_description = "Bound true, false or unresolved claim outcome"
    idempotency = "Claim text has no role; the declared rows keep the same outcome."

    def row_status(self, request, state):
        if request.rows in {"none", "unknown"} or request.time_form == "missing":
            return "GAP"
        if request.rows == "false":
            return "FAIL"
        if request.rows == "order":
            return "PASS" if state.event_order_correct else "FAIL"
        if request.rows == "variable":
            return "FAIL" if state.scenario_failed or state.intervention_failed else "PASS"
        return "PASS"

    def apply(self, guarded: GuardsRun, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(ClaimRowsEvaluated(guarded.request), replace(state, row_status=self.row_status(guarded.request, state)), "claim_rows_evaluated")


class Aggregate:
    name = "Aggregate"
    reads = ("guard_status", "row_status")
    writes = ("aggregate_status",)
    accepted_input_type = ClaimRowsEvaluated
    input_description = "World status and evaluated claim status"
    output_description = "Conservative four-status outcome"
    idempotency = "FAIL precedes GAP, then boundary, then PASS."

    def status(self, state):
        outcomes = {state.guard_status, state.row_status}
        return next(status for status in ("FAIL", "GAP", "BOUNDARY_EXCEEDED", "PASS") if status in outcomes)

    def apply(self, claimed: ClaimRowsEvaluated, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(Aggregated(claimed.request), replace(state, aggregate_status=self.status(state)), "statuses_aggregated")


class ReportExit:
    name = "ReportExit"
    reads = ("aggregate_status",)
    writes = ("exit_code", "status", "terminal")
    accepted_input_type = Aggregated
    input_description = "Final native status"
    output_description = "Actual exit/status terminal, not a reachability-only label"
    idempotency = "PASS exits 0; a completed non-pass exits 1."

    def apply(self, aggregate: Aggregated, state: State) -> Iterable[FunctionResult]:
        status = state.aggregate_status
        exit_code = 0 if status == "PASS" else 1
        label = {"FAIL": "failed", "GAP": "gap", "BOUNDARY_EXCEEDED": "boundary_exceeded", "PASS": "passed"}[status]
        yield FunctionResult(Terminal(exit_code, status), replace(state, exit_code=exit_code, status=status, terminal=True), label)


def _terminal_check(state, applies, expected, message):
    if state.terminal and state.request is not None and applies(state.request) and (state.exit_code, state.status) != expected:
        return InvariantResult.fail(message)
    return InvariantResult.pass_()


def bad_time_is_input_error(state, trace):
    return _terminal_check(state, lambda request: request.time_form in {"word", "mixed"}, (2, "error"), "Unknown or mixed time escaped the input-error boundary")


def clock_times_order_events(state, trace):
    return _terminal_check(state, lambda request: request.time_form == "clock" and not request.event_order_correct, (1, "FAIL"), "A reversed clock-order precondition/claim did not fail")


def duplicate_event_id_is_input_error(state, trace):
    return _terminal_check(state, lambda request: request.duplicate_ids, (2, "error"), "A duplicate event identity was accepted")


def scenario_values_reach_constraints(state, trace):
    return _terminal_check(state, lambda request: request.scm_mode in {"scenario", "intervention", "partial_fail"}, (1, "FAIL"), "A real numerical contradiction disappeared from constraints/claim rows")


def declared_boundary_is_boundary_exceeded(state, trace):
    return _terminal_check(state, lambda request: request.case_id == "owned_boundary", (1, "BOUNDARY_EXCEEDED"), "An owned boundary was misclassified")


def pass_needs_bound_true_rows(state, trace):
    if state.terminal and state.request is not None and state.status == "PASS":
        if state.request.rows in {"none", "false", "unknown"} or state.row_status != "PASS" or state.guard_status != "PASS":
            return InvariantResult.fail("PASS lacks bound true rows and a passing world")
    return _terminal_check(state, lambda request: request.rows == "none", (1, "GAP"), "An unbound claim did not remain a gap")


EXTERNAL_INPUTS = (
    CheckRequest("number", time_form="number"),
    CheckRequest("label"),
    CheckRequest("iso", time_form="iso"),
    CheckRequest("clock_reversed", time_form="clock", event_order_correct=False),
    CheckRequest("clock_good", time_form="clock"),
    CheckRequest("word_time", time_form="word"),
    CheckRequest("mixed_time", time_form="mixed"),
    CheckRequest("duplicate_ids", duplicate_ids=True),
    CheckRequest("scenario_late", scm_mode="scenario", rows="variable"),
    CheckRequest("intervention_late", scm_mode="intervention", rows="variable"),
    CheckRequest("owned_boundary", boundary="owned"),
    CheckRequest("foreign_boundary", boundary="unselected"),
    CheckRequest("unbound", rows="none"),
    CheckRequest("false_row", rows="false"),
    CheckRequest("unknown_row", rows="unknown"),
    CheckRequest("missing_event_time", time_form="missing"),
    CheckRequest("partial_run_fail", scm_mode="partial_fail", rows="variable"),
    CheckRequest("partial_run_gap", scm_mode="partial_gap", rows="variable"),
    CheckRequest("boundary_with_fail", time_form="clock", event_order_correct=False, boundary="owned"),
    CheckRequest("boundary_with_gap", time_form="missing", boundary="owned"),
)
INVARIANTS = tuple(Invariant(name, description, check) for name, description, check in (
    ("bad_time_is_input_error", "Unknown/mixed time exits 2", bad_time_is_input_error),
    ("clock_times_order_events", "A reversed clock order fails", clock_times_order_events),
    ("duplicate_event_id_is_input_error", "Duplicate scenario-local ids exit 2", duplicate_event_id_is_input_error),
    ("scenario_values_reach_constraints", "Scenario/do contradictions reach constraints and assertions", scenario_values_reach_constraints),
    ("declared_boundary_is_boundary_exceeded", "An owned boundary has its own final status", declared_boundary_is_boundary_exceeded),
    ("pass_needs_bound_true_rows", "Only bound true rows in a passing world can pass", pass_needs_bound_true_rows),
))
REQUIRED_LABELS = ("input_error", "failed", "gap", "boundary_exceeded", "passed")
MAX_SEQUENCE_LENGTH = 1


def build_workflow():
    return Workflow((ParseContract(), EvaluateScenarios(), RunGuards(), EvaluateClaimRows(), Aggregate(), ReportExit()), name="worldguard_world_check")


def terminal_predicate(current_input, state, trace):
    return isinstance(current_input, Terminal)


def _explorer(blocks, invariant_names=None, labels=REQUIRED_LABELS):
    return Explorer(workflow=Workflow(tuple(blocks), name="worldguard_world_check"), initial_states=(State(),),
        external_inputs=EXTERNAL_INPUTS, invariants=tuple(invariant for invariant in INVARIANTS if invariant_names is None or invariant.name in invariant_names),
        max_sequence_length=MAX_SEQUENCE_LENGTH, terminal_predicate=terminal_predicate, required_labels=tuple(labels))


def build_explorer():
    return _explorer(build_workflow().blocks)


class _StringSortedTimes(ParseContract):
    def event_order(self, request):
        return True if request.time_form == "clock" else super().event_order(request)


class _WordTimesAccepted(ParseContract):
    def invalid_time(self, request):
        return False


class _DuplicateIdsAccepted(ParseContract):
    def duplicate(self, request):
        return False


class _EndogenousSeedDropped(EvaluateScenarios):
    def scenario_fails(self, request):
        return False if request.scm_mode == "scenario" else super().scenario_fails(request)


class _InterventionsIgnored(EvaluateScenarios):
    def intervention_fails(self, request):
        return False


class _BoundaryRankedAsGap(Aggregate):
    def status(self, state):
        value = super().status(state)
        return "GAP" if value == "BOUNDARY_EXCEEDED" else value


class _UnboundClaimPasses(EvaluateClaimRows):
    def row_status(self, request, state):
        return "PASS" if request.rows == "none" else super().row_status(request, state)


def broken_variants():
    def variant(broken, invariant):
        blocks = tuple(broken if isinstance(broken, type(block)) else block for block in build_workflow().blocks)
        return _explorer(blocks, invariant_names={invariant}, labels=())
    return {
        "string_sorted_times": variant(_StringSortedTimes(), "clock_times_order_events"),
        "word_times_accepted": variant(_WordTimesAccepted(), "bad_time_is_input_error"),
        "duplicate_ids_accepted": variant(_DuplicateIdsAccepted(), "duplicate_event_id_is_input_error"),
        "endogenous_seed_dropped": variant(_EndogenousSeedDropped(), "scenario_values_reach_constraints"),
        "interventions_ignored": variant(_InterventionsIgnored(), "scenario_values_reach_constraints"),
        "boundary_ranked_as_gap": variant(_BoundaryRankedAsGap(), "declared_boundary_is_boundary_exceeded"),
        "unbound_claim_passes": variant(_UnboundClaimPasses(), "pass_needs_bound_true_rows"),
    }


class ReplayReport:
    def __init__(self, checked, mismatches):
        self.checked = checked
        self.mismatches = tuple(mismatches)
        self.ok = not self.mismatches

    def format_text(self, max_examples=None):
        return "\n".join([f"conformance: {self.checked - len(self.mismatches)}/{self.checked} model inputs match the real code",
                          *["  mismatch: " + mismatch for mismatch in self.mismatches[:max_examples]]])


def _model_outcome(request):
    current, state = request, State()
    for block in build_workflow().blocks:
        if isinstance(current, Terminal):
            break
        result = next(iter(block.apply(current, state)))
        current, state = result.output, result.new_state
    assert isinstance(current, Terminal)
    return current.exit_code, current.status


def _real_contract(request):
    if request.scm_mode != "none":
        if request.scm_mode.startswith("partial_"):
            value = -2 if request.scm_mode == "partial_fail" else 2
            causal = {"variables": ["x", "y"], "exogenous": ["u"], "equations": {"x": "u", "y": "x + 1"},
                      "scenarios": {"bad_missing": {}, "actual": {"u": value}}, "constraints": ["x >= 0"]}
            rows = [{"variable": "x", "op": ">=", "value": 0, "scenario": "actual"}]
        else:
            causal = {"variables": ["x", "y"], "equations": {"x": "1", "y": "x + 1"}, "scenarios": {"base": {}}, "constraints": ["y >= 0"]}
            if request.scm_mode == "scenario":
                causal["scenarios"]["late"] = {"x": -2}
            else:
                causal["interventions"] = [{"intervention_id": "late", "scenario_id": "base", "set": {"x": -2}}]
            rows = [{"variable": "y", "op": ">=", "value": 0}]
        return {"claim": {"claim_id": request.case_id, "asserts": rows}, "inputs": {"causal_model": causal}}
    first, second = {
        "number": (0, 2.5), "label": ("t9", "t10"), "iso": ("2026-11-02T09:40", "2026-11-02T10:20"),
        "clock": (("9:40", "10:20") if request.event_order_correct else ("10:20", "9:40")),
        "word": ("evening", "t10"), "mixed": ("t9", "2026-11-02T10:20"), "missing": (None, "t10"),
    }[request.time_form]
    events = [{"event_id": "first", "at": first, "initiates": "ready"},
              {"event_id": "first" if request.duplicate_ids else "second", "at": second, "requires": "ready", "initiates": "done"}]
    if request.time_form == "missing":
        del events[0]["at"]
    rows = [{"event": "first", "before": "second"}]
    if request.rows == "none":
        rows = []
    elif request.rows == "false":
        rows = [{"event": "second", "before": "first"}]
    elif request.rows == "unknown":
        rows = [{"holds": "not_in_the_world", "at": second}]
    semantics = ["event"]
    if request.boundary != "none":
        semantics.append("numeric_dynamics" if request.boundary == "owned" else "geometry")
    return {"claim": {"claim_id": request.case_id, "requested_semantics": semantics, "asserts": rows}, "inputs": {"events": events}}


def conformance():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from worldguard.cli import main
    mismatches = []
    with tempfile.TemporaryDirectory(prefix="world-check-replay-") as folder:
        for index, request in enumerate(EXTERNAL_INPUTS):
            path = Path(folder) / f"{index}-{request.case_id}.json"
            path.write_text(json.dumps(_real_contract(request)), encoding="utf-8")
            output = io.StringIO()
            expected = _model_outcome(request)
            try:
                with redirect_stdout(output):
                    code = main(["check", "--contract", str(path)])
                actual = (code, json.loads(output.getvalue())["status"])
            except Exception as exc:
                mismatches.append(f"{request.case_id}: native replay raised {type(exc).__name__}: {exc}")
                continue
            if actual != expected:
                invariant = "clock_times_order_events" if request.case_id == "clock_reversed" else request.case_id
                mismatches.append(f"{invariant}: model {expected!r}, real code {actual!r}")
    return ReplayReport(len(EXTERNAL_INPUTS), mismatches)


if __name__ == "__main__":
    good = build_explorer().explore()
    print(good.format_text())
    outcomes = {(trace.final_state.exit_code, trace.final_state.status) for trace in good.traces if trace.final_state.terminal}
    expected_outcomes = {(2, "error"), (1, "FAIL"), (1, "GAP"), (1, "BOUNDARY_EXCEEDED"), (0, "PASS")}
    print("terminal outcomes:", sorted(outcomes))
    caught = []
    for name, variant in broken_variants().items():
        found = not variant.explore().ok
        caught.append(found)
        print(f"known-bad {name}: {'caught' if found else 'MISSED'}")
    replay = conformance()
    print(replay.format_text())
    raise SystemExit(0 if good.ok and outcomes == expected_outcomes and all(caught) and replay.ok else 1)
