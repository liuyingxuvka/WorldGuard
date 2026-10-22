"""Contract model for WorldGuard template-pack selection, composition and native validation.

Each FunctionBlock has the form Input x State -> Set(Output x State). The model
keeps template mechanics separate from WorldGuard-owned semantic authority;
conformance() replays every model input on worldguard/template_packs.py.
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
    guard_routes_complete: bool = True


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
    route_missing: bool = False


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
            route_missing=False,
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
                Blocked("template_selected_base_missing"),
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
                Blocked("template_fragment_field_ownership_mismatch"), state, "field_ownership_mismatch_blocked"
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
        if not composed.request.guard_routes_complete:
            yield FunctionResult(
                Blocked("template_native_validation_failed:missing_guard_ids"),
                replace(state, route_missing=True),
                "guard_route_missing_blocked",
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


def ready_requires_every_claim_derived_guard_route(state: State, trace: object) -> InvariantResult:
    if state.native_validated and state.route_missing:
        return InvariantResult.fail("A Guard contract became ready although it misses a claim-derived Guard route")
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
    BuildRequest(guard_routes_complete=False),
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
    Invariant(
        "ready_requires_every_claim_derived_guard_route",
        "A ready Guard contract routes every Guard its claim derives; a pack that misses one is rejected.",
        ready_requires_every_claim_derived_guard_route,
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


class _AmbiguousSelectsFirst(SelectTemplatePack):
    """Known bad: several matching candidates still select one of them."""

    def apply(self, request: BuildRequest, state: State) -> Iterable[FunctionResult]:
        for result in super().apply(request, state):
            if result.new_state.selection_outcome == "ambiguous":
                result = FunctionResult(
                    SelectionReady(request, "selected"),
                    replace(result.new_state, base_selected=True, candidate_selected=True),
                    "multiple_candidates_blocked",
                )
            yield result


class _AcceptsMissingGuardRoute(ValidateTemplateInstance):
    """Known bad: native validation ignores a claim-derived Guard route the pack does not list."""

    def apply(self, composed: CompositionReady, state: State) -> Iterable[FunctionResult]:
        routed = replace(composed, request=replace(composed.request, guard_routes_complete=True))
        for result in super().apply(routed, state):
            yield replace(result, new_state=replace(result.new_state, route_missing=not composed.request.guard_routes_complete))


class _NoMatchActivatesBase(SelectTemplatePack):
    """Known bad: a request with no matching candidate still activates the shared base."""

    def apply(self, request: BuildRequest, state: State) -> Iterable[FunctionResult]:
        for result in super().apply(request, state):
            if result.new_state.selection_outcome == "no_match":
                result = replace(result, new_state=replace(result.new_state, base_selected=True))
            yield result


# Contract: what this model is about in the real code, its known-bad variants, and the replay on that code.

from pathlib import Path  # noqa: E402
import sys  # noqa: E402

MODEL_ID = "template_selection"
COMPONENTS = ["worldguard.templates"]
ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTED_BY = {
    "SelectTemplatePack": "worldguard/template_packs.py:TemplatePackRegistry.select",
    "ComposeTemplatePack": "worldguard/template_packs.py:compose_template_packs",
    "ValidateTemplateInstance": "worldguard/template_packs.py:run_native_template_validators",
}
TESTED_BY = {
    "ambiguity_never_constructs": ["tests/test_template_packs.py:test_many_matching_candidates_are_visible_and_never_ranked"],
    "no_match_never_constructs": ["tests/test_template_packs.py:test_no_candidate_blocks_instead_of_activating_the_shared_scaffold"],
    "ready_requires_worldguard_native_validation": ["tests/test_template_packs.py:test_builtin_guard_pack_selects_and_validates_deterministically"],
    "ready_requires_every_claim_derived_guard_route": ["tests/test_template_packs.py:test_pack_missing_a_claim_derived_guard_route_is_rejected"],
}
REQUIRED_LABELS = (
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
    "guard_route_missing_blocked",
)


def _explorer(blocks, invariant_names=None, labels=REQUIRED_LABELS) -> Explorer:
    return Explorer(
        workflow=Workflow(tuple(blocks), name="worldguard_template_pack_builder"),
        initial_states=(State(),),
        external_inputs=EXTERNAL_INPUTS,
        invariants=tuple(item for item in INVARIANTS if invariant_names is None or item.name in invariant_names),
        max_sequence_length=MAX_SEQUENCE_LENGTH,
        terminal_predicate=terminal_predicate,
        required_labels=tuple(labels),
    )


def build_explorer() -> Explorer:
    """Every sequence of up to three build requests; every selection, composition and validation label is reached."""
    return _explorer(build_workflow().blocks)


def broken_variants() -> dict[str, Explorer]:
    """Known-bad variants, each explored with only the invariant that must catch it."""
    def swapped(broken):
        return tuple(broken if isinstance(broken, type(block)) else block for block in build_workflow().blocks)

    return {
        "ambiguous_selects_first": _explorer(
            swapped(_AmbiguousSelectsFirst()), invariant_names={"ambiguity_never_constructs"}, labels=()),
        "no_match_activates_base": _explorer(
            swapped(_NoMatchActivatesBase()), invariant_names={"no_match_never_constructs"}, labels=()),
        "accepts_missing_guard_route": _explorer(
            swapped(_AcceptsMissingGuardRoute()), invariant_names={"ready_requires_every_claim_derived_guard_route"}, labels=()),
    }


class ReplayReport:
    """Conformance result: how many model inputs ran on the real code, and the mismatches."""

    def __init__(self, checked: int, mismatches: list[str]) -> None:
        self.checked = checked
        self.mismatches = tuple(mismatches)
        self.ok = not self.mismatches

    def format_text(self, max_examples: int | None = None) -> str:
        lines = [f"conformance: {self.checked - len(self.mismatches)}/{self.checked} model inputs match the real code"]
        return "\n".join(lines + [f"  mismatch: {line}" for line in self.mismatches[:max_examples]])


def _model_outcome(request: BuildRequest) -> str:
    """Run the three model blocks for one request and return its terminal outcome."""
    current: object = request
    state = State()
    for block in build_workflow().blocks:
        if isinstance(current, (Blocked, TemplateInstanceReady)):
            break
        step = next(iter(block.apply(current, state)))
        current, state = step.output, step.new_state
    return current.reason if isinstance(current, Blocked) else "ready"


def conformance() -> ReplayReport:
    """Replay every model input on the real worldguard.template_packs code; the error code must be the model's."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from dataclasses import replace as replace_manifest

    from worldguard.template_packs import (
        GUARD_CONTRACT_KIND,
        VALIDATOR_GUARD_SHAPE,
        TemplateFragment,
        TemplatePackError,
        TemplatePackManifest,
        TemplatePackRegistry,
        build_template_instance,
        builtin_template_registry,
        compose_template_packs,
        template_slot,
    )

    registry = builtin_template_registry()
    event = {
        "contract_id": "conformance:event", "run_id": "conformance:run", "claim_id": "claim:event",
        "claim_text": "a declared event initiates readiness", "target_guards": ["EventGuard"],
        "requested_semantics": ["event"], "claim_atoms": [], "claim_asserts": [{"holds": "ready", "at": "t0"}],
        "model_id": "conformance:model", "model_version": "v1",
        "event_inputs": [{"event_id": "event:ready", "at": "t0", "initiates": "ready"}],
    }
    candidate = TemplatePackManifest.build(
        pack_id="conformance.candidate", pack_version="1", contract_kind=GUARD_CONTRACT_KIND, is_base=False,
        required_fact_ids=("candidate:yes",), fragments=(TemplateFragment.build("fragment:candidate", {"inputs": {"events": []}}),),
        native_validator_ids=(VALIDATOR_GUARD_SHAPE,), claim_boundary="conformance only",
    )
    test_base = TemplatePackManifest.build(
        pack_id="conformance.base", pack_version="1", contract_kind=GUARD_CONTRACT_KIND, is_base=True,
        fragments=(TemplateFragment.build("fragment:base", {"contract_id": template_slot("contract_id")}),),
        native_validator_ids=(VALIDATOR_GUARD_SHAPE,), claim_boundary="conformance only",
    )
    overlap = TemplatePackManifest.build(
        pack_id="conformance.overlap", pack_version="1", contract_kind=GUARD_CONTRACT_KIND, is_base=False,
        required_fact_ids=("overlap",), fragments=(TemplateFragment.build("fragment:overlap", {"contract_id": "wrong"}),),
        native_validator_ids=(VALIDATOR_GUARD_SHAPE,), claim_boundary="conformance only",
    )
    builtin_base = registry.by_id("worldguard.guard-contract.base")

    def build(fact_ids, bindings, source=registry):
        return lambda: build_template_instance(source, contract_kind=GUARD_CONTRACT_KIND, fact_ids=fact_ids, slot_bindings=bindings)

    real_calls = {
        BuildRequest(candidate_count=0): build(["unmatched:fact"], event),
        BuildRequest(candidate_count=1): build(["guard:EventGuard"], event),
        BuildRequest(candidate_count=2): build(["guard:EventGuard", "guard:CausalGuard"], event),
        BuildRequest(candidate_count=0, base_present=False): build([], {}, TemplatePackRegistry.build((candidate,))),
        BuildRequest(candidate_count=1, base_present=False): build(["candidate:yes"], {}, TemplatePackRegistry.build((candidate,))),
        BuildRequest(field_ownership_exact=False): lambda: TemplateFragment.from_dict(
            {"fragment_id": "fragment:mismatch", "owned_field_ids": ["claim.text"], "payload": {"claim": {"claim_id": "claim:one"}}}
        ).validate(),
        BuildRequest(field_conflict=True): lambda: compose_template_packs((test_base, overlap)),
        BuildRequest(native_validators_bound=False): lambda: TemplatePackRegistry.build(
            (replace_manifest(builtin_base, native_validator_ids=("worldguard.unknown.v1",)),)
        ),
        BuildRequest(native_validation_passes=False): build(["guard:EventGuard"], {**event, "run_id": ""}),
        # The event pack routes EventGuard only; a claim that also asks for causal semantics derives CausalGuard.
        BuildRequest(guard_routes_complete=False): build(["guard:EventGuard"], {**event, "requested_semantics": ["event", "causal"]}),
    }
    mismatches = []
    for request in EXTERNAL_INPUTS:
        call = real_calls.get(request)
        if call is None:
            mismatches.append(f"{request!r}: declared only, no real call replays it")
            continue
        try:
            call()
            real = "ready"
        except TemplatePackError as exc:
            real = exc.code.lower() + (":missing_guard_ids" if "missing_guard_ids" in exc.details else "")
        expected = _model_outcome(request)
        if real != expected:
            mismatches.append(f"{request!r}: model {expected!r}, real code {real!r}")
    return ReplayReport(len(EXTERNAL_INPUTS), mismatches)


if __name__ == "__main__":
    print(build_explorer().explore().format_text())
    for name, variant in broken_variants().items():
        print(f"known-bad {name}: {'caught' if not variant.explore().ok else 'MISSED'}")
    print(conformance().format_text())
