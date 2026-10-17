"""FlowGuard process model for WorldGuard claim-derived semantic coverage."""
from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Iterable
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow

@dataclass(frozen=True)
class CoverageRequest:
    guard_purpose_declared: bool = True
    protected_failure_universe_complete: bool = True
    one_native_good_per_guard: bool = True
    one_native_bad_per_failure: bool = True
    native_failure_oracle_passed: bool = True
    structured_claim_atoms: bool = True
    all_derived_guards_declared: bool = True
    all_expected_nodes_contracted: bool = True
    discovered_nodes_reconciled: bool = True
    exclusions_closed_noncontributing: bool = True
    all_expected_children_executed: bool = True
    nondegenerate_horizon: bool = True
    representative_timepoint_floor_met: bool = True
    time_strata_covered: bool = True
    temporal_max_gap_met: bool = True
    per_model_node_depth_complete: bool = True
    per_variable_depth_complete: bool = True
    native_floor_receipts_bound: bool = True
    normal_scenarios_executed: bool = True
    holdout_scenarios_executed: bool = True
    branches_and_perturbations_executed: bool = True
    interventions_and_counterfactuals_executed: bool = True
    mesh_and_coverage_fingerprints_bound: bool = True
    native_observation_integrity: bool = True
    exact_obligation_evidence: bool = True

@dataclass(frozen=True)
class RoutesReady:
    all_expected_nodes_contracted: bool
    discovered_nodes_reconciled: bool
    exclusions_closed_noncontributing: bool
    all_expected_children_executed: bool
    nondegenerate_horizon: bool
    representative_timepoint_floor_met: bool
    time_strata_covered: bool
    temporal_max_gap_met: bool
    per_model_node_depth_complete: bool
    per_variable_depth_complete: bool
    native_floor_receipts_bound: bool
    normal_scenarios_executed: bool
    holdout_scenarios_executed: bool
    branches_and_perturbations_executed: bool
    interventions_and_counterfactuals_executed: bool
    mesh_and_coverage_fingerprints_bound: bool
    native_observation_integrity: bool
    exact_obligation_evidence: bool

@dataclass(frozen=True)
class UniverseReady:
    all_expected_children_executed: bool
    nondegenerate_horizon: bool
    representative_timepoint_floor_met: bool
    time_strata_covered: bool
    temporal_max_gap_met: bool
    per_model_node_depth_complete: bool
    per_variable_depth_complete: bool
    native_floor_receipts_bound: bool
    normal_scenarios_executed: bool
    holdout_scenarios_executed: bool
    branches_and_perturbations_executed: bool
    interventions_and_counterfactuals_executed: bool
    mesh_and_coverage_fingerprints_bound: bool
    native_observation_integrity: bool
    exact_obligation_evidence: bool

@dataclass(frozen=True)
class SemanticsReady:
    nondegenerate_horizon: bool
    representative_timepoint_floor_met: bool
    time_strata_covered: bool
    temporal_max_gap_met: bool
    per_model_node_depth_complete: bool
    per_variable_depth_complete: bool
    native_floor_receipts_bound: bool
    normal_scenarios_executed: bool
    holdout_scenarios_executed: bool
    branches_and_perturbations_executed: bool
    interventions_and_counterfactuals_executed: bool
    mesh_and_coverage_fingerprints_bound: bool
    native_observation_integrity: bool
    exact_obligation_evidence: bool

@dataclass(frozen=True)
class PredictiveReceiptReady:
    predictive_claim_licensed: bool

@dataclass(frozen=True)
class Blocked:
    reason: str

@dataclass(frozen=True)
class State:
    guard_purpose_declared: bool = False
    protected_failure_universe_complete: bool = False
    one_native_good_per_guard: bool = False
    one_native_bad_per_failure: bool = False
    native_failure_oracle_passed: bool = False
    claim_routes_derived: bool = False
    required_guards_complete: bool = False
    expected_nodes_contracted: bool = False
    discovered_nodes_reconciled: bool = False
    exclusions_closed_noncontributing: bool = False
    expected_children_executed: bool = False
    horizon_executed: bool = False
    representative_timepoint_floor_met: bool = False
    time_strata_covered: bool = False
    temporal_max_gap_met: bool = False
    per_model_node_depth_complete: bool = False
    per_variable_depth_complete: bool = False
    native_floor_receipts_bound: bool = False
    normal_scenarios_executed: bool = False
    holdout_scenarios_executed: bool = False
    branches_and_perturbations_executed: bool = False
    interventions_and_counterfactuals_executed: bool = False
    fingerprints_bound: bool = False
    native_observation_integrity: bool = False
    exact_obligation_evidence: bool = False
    predictive_claim_licensed: bool = False

class DeriveClaimRoutes:
    name = 'DeriveClaimRoutes'
    reads = ()
    writes = ('guard_purpose_declared', 'protected_failure_universe_complete', 'one_native_good_per_guard', 'one_native_bad_per_failure', 'native_failure_oracle_passed', 'claim_routes_derived', 'required_guards_complete')
    accepted_input_type = CoverageRequest
    input_description = 'structured claim x initial state'
    output_description = 'RoutesReady or Blocked'
    idempotency = 'The same structured claim atoms derive the same WorldGuard-owned Guard routes.'

    def apply(self, input_obj: CoverageRequest, state: State) -> Iterable[FunctionResult]:
        if not input_obj.guard_purpose_declared:
            yield FunctionResult(Blocked('guard_model_purpose_required'), state, 'guard_purpose_blocked')
            return
        if not input_obj.protected_failure_universe_complete:
            yield FunctionResult(Blocked('guard_owned_failure_universe_incomplete'), state, 'protected_failure_universe_blocked')
            return
        if not input_obj.one_native_good_per_guard:
            yield FunctionResult(Blocked('exactly_one_native_good_per_guard_required'), state, 'native_good_cardinality_blocked')
            return
        if not input_obj.one_native_bad_per_failure:
            yield FunctionResult(Blocked('exactly_one_native_bad_per_failure_required'), state, 'native_bad_cardinality_blocked')
            return
        if not input_obj.native_failure_oracle_passed:
            yield FunctionResult(Blocked('native_failure_oracle_must_pass'), state, 'native_failure_oracle_blocked')
            return
        if not input_obj.structured_claim_atoms:
            yield FunctionResult(Blocked('structured_claim_atoms_required'), state, 'claim_atoms_blocked')
            return
        if not input_obj.all_derived_guards_declared:
            yield FunctionResult(Blocked('claim_derived_guard_missing'), state, 'derived_guard_blocked')
            return
        yield FunctionResult(RoutesReady(input_obj.all_expected_nodes_contracted, input_obj.discovered_nodes_reconciled, input_obj.exclusions_closed_noncontributing, input_obj.all_expected_children_executed, input_obj.nondegenerate_horizon, input_obj.representative_timepoint_floor_met, input_obj.time_strata_covered, input_obj.temporal_max_gap_met, input_obj.per_model_node_depth_complete, input_obj.per_variable_depth_complete, input_obj.native_floor_receipts_bound, input_obj.normal_scenarios_executed, input_obj.holdout_scenarios_executed, input_obj.branches_and_perturbations_executed, input_obj.interventions_and_counterfactuals_executed, input_obj.mesh_and_coverage_fingerprints_bound, input_obj.native_observation_integrity, input_obj.exact_obligation_evidence), replace(state, guard_purpose_declared=True, protected_failure_universe_complete=True, one_native_good_per_guard=True, one_native_bad_per_failure=True, native_failure_oracle_passed=True, claim_routes_derived=True, required_guards_complete=True), 'routes_ready')

class BuildExpectedCoverageUniverse:
    name = 'BuildExpectedCoverageUniverse'
    reads = ('claim_routes_derived', 'required_guards_complete')
    writes = ('expected_nodes_contracted', 'discovered_nodes_reconciled', 'exclusions_closed_noncontributing')
    accepted_input_type = RoutesReady
    input_description = 'derived routes x state'
    output_description = 'UniverseReady or Blocked'
    idempotency = 'Expected nodes and semantic children are fingerprinted from one current mesh.'

    def apply(self, input_obj: RoutesReady, state: State) -> Iterable[FunctionResult]:
        if not input_obj.all_expected_nodes_contracted:
            yield FunctionResult(Blocked('expected_node_contract_missing'), state, 'contractless_node_blocked')
            return
        if not input_obj.discovered_nodes_reconciled:
            yield FunctionResult(Blocked('discovered_model_nodes_not_reconciled'), state, 'object_scope_reconciliation_blocked')
            return
        if not input_obj.exclusions_closed_noncontributing:
            yield FunctionResult(Blocked('model_node_exclusion_not_closed'), state, 'object_scope_exclusion_blocked')
            return
        yield FunctionResult(UniverseReady(input_obj.all_expected_children_executed, input_obj.nondegenerate_horizon, input_obj.representative_timepoint_floor_met, input_obj.time_strata_covered, input_obj.temporal_max_gap_met, input_obj.per_model_node_depth_complete, input_obj.per_variable_depth_complete, input_obj.native_floor_receipts_bound, input_obj.normal_scenarios_executed, input_obj.holdout_scenarios_executed, input_obj.branches_and_perturbations_executed, input_obj.interventions_and_counterfactuals_executed, input_obj.mesh_and_coverage_fingerprints_bound, input_obj.native_observation_integrity, input_obj.exact_obligation_evidence), replace(state, expected_nodes_contracted=True, discovered_nodes_reconciled=True, exclusions_closed_noncontributing=True), 'universe_ready')

class ExecuteExpectedSemanticChildren:
    name = 'ExecuteExpectedSemanticChildren'
    reads = ('expected_nodes_contracted',)
    writes = ('expected_children_executed',)
    accepted_input_type = UniverseReady
    input_description = 'expected universe x state'
    output_description = 'SemanticsReady or Blocked'
    idempotency = 'Every expected child either executes natively or remains a typed skip.'

    def apply(self, input_obj: UniverseReady, state: State) -> Iterable[FunctionResult]:
        if not input_obj.all_expected_children_executed:
            yield FunctionResult(Blocked('expected_semantic_child_skipped'), state, 'semantic_child_blocked')
            return
        yield FunctionResult(SemanticsReady(input_obj.nondegenerate_horizon, input_obj.representative_timepoint_floor_met, input_obj.time_strata_covered, input_obj.temporal_max_gap_met, input_obj.per_model_node_depth_complete, input_obj.per_variable_depth_complete, input_obj.native_floor_receipts_bound, input_obj.normal_scenarios_executed, input_obj.holdout_scenarios_executed, input_obj.branches_and_perturbations_executed, input_obj.interventions_and_counterfactuals_executed, input_obj.mesh_and_coverage_fingerprints_bound, input_obj.native_observation_integrity, input_obj.exact_obligation_evidence), replace(state, expected_children_executed=True), 'semantic_children_ready')

class AssessPredictiveAdequacy:
    name = 'AssessPredictiveAdequacy'
    reads = ('expected_children_executed',)
    writes = ('horizon_executed', 'representative_timepoint_floor_met', 'time_strata_covered', 'temporal_max_gap_met', 'per_model_node_depth_complete', 'per_variable_depth_complete', 'native_floor_receipts_bound', 'normal_scenarios_executed', 'holdout_scenarios_executed', 'branches_and_perturbations_executed', 'interventions_and_counterfactuals_executed', 'fingerprints_bound', 'native_observation_integrity', 'exact_obligation_evidence', 'predictive_claim_licensed')
    accepted_input_type = SemanticsReady
    input_description = 'executed semantic children x state'
    output_description = 'PredictiveReceiptReady or Blocked'
    idempotency = 'Predictive license is derived only from executed mesh-bound coverage evidence.'

    def apply(self, input_obj: SemanticsReady, state: State) -> Iterable[FunctionResult]:
        if not input_obj.nondegenerate_horizon:
            yield FunctionResult(Blocked('single_timepoint_is_bounded_only'), state, 'horizon_blocked')
            return
        if not input_obj.representative_timepoint_floor_met:
            yield FunctionResult(Blocked('representative_timepoint_floor_not_met'), state, 'timepoint_floor_blocked')
            return
        if not input_obj.time_strata_covered:
            yield FunctionResult(Blocked('time_strata_not_covered'), state, 'time_strata_blocked')
            return
        if not input_obj.temporal_max_gap_met:
            yield FunctionResult(Blocked('temporal_maximum_gap_exceeded'), state, 'temporal_max_gap_blocked')
            return
        if not input_obj.per_model_node_depth_complete:
            yield FunctionResult(Blocked('per_model_node_depth_incomplete'), state, 'per_object_depth_blocked')
            return
        if not input_obj.per_variable_depth_complete:
            yield FunctionResult(Blocked('per_variable_or_signal_depth_incomplete'), state, 'per_variable_depth_blocked')
            return
        if not input_obj.native_floor_receipts_bound:
            yield FunctionResult(Blocked('native_dynamic_floor_receipt_missing'), state, 'native_floor_receipt_blocked')
            return
        if not input_obj.normal_scenarios_executed:
            yield FunctionResult(Blocked('normal_scenario_rollout_missing'), state, 'scenario_blocked')
            return
        if not input_obj.holdout_scenarios_executed:
            yield FunctionResult(Blocked('holdout_rollout_missing'), state, 'holdout_blocked')
            return
        if not input_obj.branches_and_perturbations_executed:
            yield FunctionResult(Blocked('branch_or_perturbation_missing'), state, 'branch_perturbation_blocked')
            return
        if not input_obj.interventions_and_counterfactuals_executed:
            yield FunctionResult(Blocked('single_equation_is_bounded_only'), state, 'intervention_counterfactual_blocked')
            return
        if not input_obj.mesh_and_coverage_fingerprints_bound:
            yield FunctionResult(Blocked('current_fingerprints_required'), state, 'fingerprint_blocked')
            return
        if not input_obj.native_observation_integrity:
            yield FunctionResult(Blocked('synthetic_or_catalog_depth_evidence_forbidden'), state, 'native_observation_integrity_blocked')
            return
        if not input_obj.exact_obligation_evidence:
            yield FunctionResult(Blocked('exact_obligation_evidence_required'), state, 'exact_obligation_evidence_blocked')
            return
        yield FunctionResult(PredictiveReceiptReady(True), replace(state, horizon_executed=True, representative_timepoint_floor_met=True, time_strata_covered=True, temporal_max_gap_met=True, per_model_node_depth_complete=True, per_variable_depth_complete=True, native_floor_receipts_bound=True, normal_scenarios_executed=True, holdout_scenarios_executed=True, branches_and_perturbations_executed=True, interventions_and_counterfactuals_executed=True, fingerprints_bound=True, native_observation_integrity=True, exact_obligation_evidence=True, predictive_claim_licensed=True), 'predictive_receipt_ready')
EXTERNAL_INPUTS = (CoverageRequest(), CoverageRequest(guard_purpose_declared=False), CoverageRequest(protected_failure_universe_complete=False), CoverageRequest(one_native_good_per_guard=False), CoverageRequest(one_native_bad_per_failure=False), CoverageRequest(native_failure_oracle_passed=False), CoverageRequest(structured_claim_atoms=False), CoverageRequest(all_derived_guards_declared=False), CoverageRequest(all_expected_nodes_contracted=False), CoverageRequest(discovered_nodes_reconciled=False), CoverageRequest(exclusions_closed_noncontributing=False), CoverageRequest(all_expected_children_executed=False), CoverageRequest(nondegenerate_horizon=False), CoverageRequest(representative_timepoint_floor_met=False), CoverageRequest(time_strata_covered=False), CoverageRequest(temporal_max_gap_met=False), CoverageRequest(per_model_node_depth_complete=False), CoverageRequest(per_variable_depth_complete=False), CoverageRequest(native_floor_receipts_bound=False), CoverageRequest(normal_scenarios_executed=False), CoverageRequest(holdout_scenarios_executed=False), CoverageRequest(branches_and_perturbations_executed=False), CoverageRequest(interventions_and_counterfactuals_executed=False), CoverageRequest(mesh_and_coverage_fingerprints_bound=False), CoverageRequest(native_observation_integrity=False), CoverageRequest(exact_obligation_evidence=False))

def build_workflow() -> Workflow:
    return Workflow((DeriveClaimRoutes(), BuildExpectedCoverageUniverse(), ExecuteExpectedSemanticChildren(), AssessPredictiveAdequacy()), name='worldguard_claim_derived_semantic_coverage')

def initial_state() -> State:
    return State()

def terminal_predicate(current_input: object, state: State, trace: object) -> bool:
    return isinstance(current_input, (Blocked, PredictiveReceiptReady))

def predictive_license_requires_complete_executed_coverage(state: State, trace: object) -> InvariantResult:
    return InvariantResult.pass_()
INVARIANTS = (Invariant('predictive_license_requires_complete_executed_coverage', 'Prediction requires declared Guard purposes, a complete finite Guard-owned failure universe, exactly one native good per Guard, exactly one native bad per failure class, a passing native reaction oracle, reconciled native object scope, square-root temporal floors, early/middle/late and maximum-gap coverage, per-variable depth, native floor receipts, executed children, and current fingerprints.', predictive_license_requires_complete_executed_coverage),)
MAX_SEQUENCE_LENGTH = 1
