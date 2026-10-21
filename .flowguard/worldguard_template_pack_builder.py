"""FlowGuard model for WorldGuard template-pack selection and validation.

Each FunctionBlock has the form Input x State -> Set(Output x State). The model
keeps template mechanics separate from WorldGuard-owned semantic authority.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer


@dataclass(frozen=True)
class BuildRequest:
    candidate_count: int = 1
    base_present: bool = True
    field_ownership_exact: bool = True
    field_conflict: bool = False
    native_validators_bound: bool = True
    native_validation_passes: bool = True


@dataclass(frozen=True)
class SelectionReady:
    request: BuildRequest
    outcome: str


@dataclass(frozen=True)
class CompositionReady:
    request: BuildRequest
    outcome: str


@dataclass(frozen=True)
class TemplateInstanceReady:
    outcome: str
    semantic_authority: str = "worldguard"


@dataclass(frozen=True)
class Blocked:
    reason: str


@dataclass(frozen=True)
class State:
    selection_outcome: str = "not_run"
    base_selected: bool = False
    candidate_selected: bool = False
    composed: bool = False
    native_validated: bool = False
    semantic_authority: str = "worldguard"


class SelectTemplatePack:
    name = "SelectTemplatePack"
    reads = ()
    writes = ("selection_outcome", "base_selected", "candidate_selected")
    accepted_input_type = BuildRequest
    input_description = "Explicit applicability facts and current manifest inventory x initial state"
    output_description = "SelectionReady(selected) or Blocked(no_match|ambiguous)"
    idempotency = "The same normalized facts and registry identity yield the same ordered candidate set and outcome."

    def apply(self, request: BuildRequest, state: State) -> Iterable[FunctionResult]:
        # Every external build request starts a fresh construction generation.
        # Prior terminal state is evidence for the prior request only and must
        # not make a later ambiguous or blocked selection appear composed.
        state = replace(
            state,
            selection_outcome="not_run",
            base_selected=False,
            candidate_selected=False,
            composed=False,
            native_validated=False,
        )
        if request.candidate_count < 0:
            yield FunctionResult(Blocked("candidate_count_invalid"), state, "invalid_candidate_count_blocked")
            return
        if request.candidate_count > 1:
            yield FunctionResult(
                Blocked("template_selection_ambiguous"),
                replace(state, selection_outcome="ambiguous"),
                "multiple_candidates_blocked",
            )
            return
        if request.candidate_count == 0:
            yield FunctionResult(
                Blocked("template_selection_no_match"),
                replace(state, selection_outcome="no_match"),
                "zero_candidates_no_match_blocked",
            )
            return
        if not request.base_present:
            yield FunctionResult(
                Blocked("candidate_base_missing"),
                replace(state, selection_outcome="selected_without_base"),
                "candidate_base_missing_blocked",
            )
            return
        yield FunctionResult(
            SelectionReady(request, "selected"),
            replace(state, selection_outcome="selected", base_selected=True, candidate_selected=True),
            "one_candidate_selected",
        )




class ComposeTemplatePack:
    name = "ComposeTemplatePack"
    reads = ("selection_outcome", "base_selected", "candidate_selected")
    writes = ("composed",)
    accepted_input_type = SelectionReady
    input_description = "Selected base/candidate fragments x current native selection"
    output_description = "CompositionReady or Blocked"
    idempotency = "Canonical disjoint fragments and exact slots yield one composed payload."

    def apply(self, selected: SelectionReady, state: State) -> Iterable[FunctionResult]:
        if (
            selected.outcome != "selected"
            or not state.base_selected
            or not state.candidate_selected
        ):
            yield FunctionResult(Blocked("selection_not_buildable"), state, "selection_not_buildable_blocked")
            return
        if not selected.request.field_ownership_exact:
            yield FunctionResult(
                Blocked("template_field_ownership_mismatch"), state, "field_ownership_mismatch_blocked"
            )
            return
        if selected.request.field_conflict:
            yield FunctionResult(
                Blocked("template_field_ownership_conflict"), state, "field_conflict_blocked"
            )
            return
        yield FunctionResult(
            CompositionReady(selected.request, selected.outcome),
            replace(state, composed=True),
            "template_composed",
        )


class ValidateTemplateInstance:
    name = "ValidateTemplateInstance"
    reads = ("composed", "semantic_authority")
    writes = ("native_validated",)
    accepted_input_type = CompositionReady
    input_description = "Resolved contract payload x WorldGuard native validator registry"
    output_description = "TemplateInstanceReady or Blocked"
    idempotency = "The same payload and validator ids yield the same validation result."

    def apply(self, composed: CompositionReady, state: State) -> Iterable[FunctionResult]:
        if not state.composed:
            yield FunctionResult(Blocked("template_not_composed"), state, "template_not_composed_blocked")
            return
        if not composed.request.native_validators_bound:
            yield FunctionResult(
                Blocked("template_native_validator_unknown"), state, "native_validator_missing_blocked"
            )
            return
        if not composed.request.native_validation_passes:
            yield FunctionResult(
                Blocked("template_native_validation_failed"), state, "native_validation_failed_blocked"
            )
            return
        yield FunctionResult(
            TemplateInstanceReady(composed.outcome),
            replace(state, native_validated=True),
            "template_instance_ready",
        )


def ambiguity_never_constructs(state: State, trace: object) -> InvariantResult:
    if state.selection_outcome == "ambiguous" and (state.composed or state.native_validated):
        return InvariantResult.fail("Ambiguous candidate selection reached composition or validation")
    return InvariantResult.pass_()


def no_match_never_constructs(state: State, trace: object) -> InvariantResult:
    if state.selection_outcome == "no_match" and (
        state.base_selected
        or state.candidate_selected
        or state.composed
        or state.native_validated
    ):
        return InvariantResult.fail(
            "A zero-candidate no-match activated the shared base or reached construction"
        )
    return InvariantResult.pass_()


def ready_requires_worldguard_native_validation(state: State, trace: object) -> InvariantResult:
    if state.native_validated and not (
        state.composed
        and state.base_selected
        and state.candidate_selected
        and state.selection_outcome == "selected"
    ):
        return InvariantResult.fail("A template instance became ready without current native selection and composition")
    if state.semantic_authority != "worldguard":
        return InvariantResult.fail("Template replaced WorldGuard semantic authority")
    return InvariantResult.pass_()




EXTERNAL_INPUTS = (
    BuildRequest(candidate_count=0),
    BuildRequest(candidate_count=1),
    BuildRequest(candidate_count=2),
    BuildRequest(candidate_count=0, base_present=False),
    BuildRequest(candidate_count=1, base_present=False),
    BuildRequest(field_ownership_exact=False),
    BuildRequest(field_conflict=True),
    BuildRequest(native_validators_bound=False),
    BuildRequest(native_validation_passes=False),
)

INVARIANTS = (
    Invariant(
        "ambiguity_never_constructs",
        "More than one matching candidate is a visible blocker and never selects a winner.",
        ambiguity_never_constructs,
    ),
    Invariant(
        "no_match_never_constructs",
        "Zero matching candidates is a visible blocker and never activates the shared base fragment.",
        no_match_never_constructs,
    ),
    Invariant(
        "ready_requires_worldguard_native_validation",
        "A ready instance is selected, composed, and validated by WorldGuard without transferring semantics.",
        ready_requires_worldguard_native_validation,
    ),
)

MAX_SEQUENCE_LENGTH = 3


def build_workflow() -> Workflow:
    return Workflow(
        (
            SelectTemplatePack(),
            ComposeTemplatePack(),
            ValidateTemplateInstance(),
        ),
        name="worldguard_template_pack_builder",
    )


def terminal_predicate(current_input: object, state: State, trace: object) -> bool:
    return isinstance(current_input, (Blocked, TemplateInstanceReady))


def review_template_pack_builder():
    return Explorer(
        workflow=build_workflow(),
        initial_states=(State(),),
        external_inputs=EXTERNAL_INPUTS,
        invariants=INVARIANTS,
        max_sequence_length=MAX_SEQUENCE_LENGTH,
        terminal_predicate=terminal_predicate,
        required_labels=(
            "zero_candidates_no_match_blocked",
            "one_candidate_selected",
            "multiple_candidates_blocked",
            "candidate_base_missing_blocked",
            "field_ownership_mismatch_blocked",
            "field_conflict_blocked",
            "native_validator_missing_blocked",
            "native_validation_failed_blocked",
            "template_composed",
            "template_instance_ready",
        ),
    ).explore()


if __name__ == "__main__":
    report = review_template_pack_builder()
    print(report.format_text())
    raise SystemExit(0 if report.ok else 1)
