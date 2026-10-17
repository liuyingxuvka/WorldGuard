"""Run WorldGuard claim-derived coverage FlowGuard and model-test alignment checks."""

from __future__ import annotations

from pathlib import Path

from flowguard.explorer import Explorer

import claim_derived_coverage_process as model
import guard_model_contract_exhaustion as guard_model_mesh
from worldguard.guard_model_contract import (
    PROTECTED_FAILURE_CLASSES,
    run_guard_model_contract,
)


ROOT = Path(__file__).resolve().parents[1]

ALIGNMENT = {
    "native_depth": ("worldguard/execution_depth.py", "def build_native_depth_evidence", "test_deep_fixture_emits_dynamic_target_owned_execution_depth"),
    "claim_routes": (
        "worldguard/contracts.py",
        "def derive_required_guards",
        "test_omitted_claim_derived_guard_fails_closed",
    ),
    "expected_nodes": (
        "worldguard/mesh.py",
        "def _coverage_route_state",
        "test_expected_contractless_node_is_counted_and_blocks_aggregate_pass",
    ),
    "discovered_node_reconciliation": (
        "worldguard/mesh.py",
        "discovered_model_node_undeclared",
        "test_expected_node_list_cannot_hide_a_discovered_predictive_node",
    ),
    "closed_noncontributing_exclusions": (
        "worldguard/mesh.py",
        "model_node_exclusion_invalid",
        "test_closed_structural_exclusion_is_visible_and_never_contributes",
    ),
    "single_event": (
        "worldguard/semantic.py",
        "def _event",
        "test_single_event_can_pass_locally_but_cannot_license_prediction",
    ),
    "single_equation": (
        "worldguard/semantic.py",
        "def _causal",
        "test_single_equation_without_intervention_or_counterfactual_stays_bounded",
    ),
    "predictive_adequacy": (
        "worldguard/mesh.py",
        "def _predictive_assessment",
        "test_complete_supported_predictive_fixture_gets_mesh_bound_license",
    ),
    "long_horizon_floor": (
        "worldguard/mesh.py",
        "def _timepoint_depth_assessment",
        "test_thousand_step_horizon_with_two_points_cannot_license_prediction",
    ),
    "native_time_strata": (
        "worldguard/mesh.py",
        "worldguard_native_early_middle_late",
        "test_caller_named_strata_cannot_replace_native_early_middle_late_phases",
    ),
    "native_temporal_max_gap": (
        "worldguard/mesh.py",
        "predictive_timepoint_max_gap_exceeded",
        "test_floor_and_all_phases_still_fail_when_one_temporal_hole_is_too_large",
    ),
    "per_model_node_depth": (
        "worldguard/mesh.py",
        "per_model_node_results",
        "test_rich_aggregate_cannot_hide_one_shallow_predictive_model_node",
    ),
    "per_variable_time_depth": (
        "worldguard/mesh.py",
        "per_variable_timepoint_results",
        "test_node_level_time_depth_cannot_hide_one_shallow_variable_series",
    ),
    "ten_thousand_dynamic_floor": (
        "worldguard/mesh.py",
        "effective_minimum_timepoint_count",
        "test_ten_thousand_step_horizon_raises_native_floor_per_series",
    ),
    "exact_obligation_evidence": (
        "worldguard/mesh.py",
        "def _native_obligation_observations",
        "test_native_obligation_hash_tracks_exact_semantic_input",
    ),
    "guard_model_contract": (
        "worldguard/guard_model_contract.py",
        "def run_guard_model_contract",
        "test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure",
    ),
    "causal_partial_equation": (
        "worldguard/guards/causal_guard.py",
        "if not variables or not equations or missing_equations",
        "test_causal_guard_rejects_partially_defined_structural_equations",
    ),
    "guard_model_contract_exhaustion": (
        ".flowguard/guard_model_contract_exhaustion.py",
        "def build_guard_model_contract_exhaustion_plan",
        "test_guard_model_contract_exhaustion_is_exact_and_oracle_bound",
    ),
}


def _alignment_ok() -> bool:
    tests = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "tests" / "test_claim_derived_coverage.py",
            ROOT / "tests" / "test_execution_depth.py",
            ROOT / "tests" / "test_runtime_identity.py",
            ROOT / "tests" / "test_guard_model_contract.py",
        )
    )
    for source_path, source_marker, test_marker in ALIGNMENT.values():
        source = (ROOT / source_path).read_text(encoding="utf-8")
        if source_marker not in source or test_marker not in tests:
            return False
    return True


def _guard_model_contract_ok() -> bool:
    native_report = run_guard_model_contract()
    mesh_report = guard_model_mesh.review_guard_model_contract_exhaustion()
    expected_ids = {case.failure_id for case in PROTECTED_FAILURE_CLASSES}
    generated_ids = {case.case_id for case in mesh_report.generated_cases}
    return bool(
        native_report["ok"]
        and mesh_report.ok
        and len(mesh_report.generated_cases) == len(expected_ids)
        and generated_ids == expected_ids
    )




def main() -> int:
    report = Explorer(
        workflow=model.build_workflow(),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=(
            "routes_ready",
            "universe_ready",
            "semantic_children_ready",
            "predictive_receipt_ready",
            "claim_atoms_blocked",
            "derived_guard_blocked",
            "contractless_node_blocked",
            "object_scope_reconciliation_blocked",
            "object_scope_exclusion_blocked",
            "semantic_child_blocked",
            "horizon_blocked",
            "timepoint_floor_blocked",
            "time_strata_blocked",
            "temporal_max_gap_blocked",
            "per_object_depth_blocked",
            "per_variable_depth_blocked",
            "native_floor_receipt_blocked",
            "scenario_blocked",
            "holdout_blocked",
            "branch_perturbation_blocked",
            "intervention_counterfactual_blocked",
            "fingerprint_blocked",
            "native_observation_integrity_blocked",
            "exact_obligation_evidence_blocked",
        ),
    ).explore()
    print(report.format_text())
    alignment_ok = _alignment_ok()
    print(f"model_test_alignment_ok={alignment_ok}")
    guard_model_contract_ok = _guard_model_contract_ok()
    print(f"guard_model_contract_ok={guard_model_contract_ok}")
    return 0 if report.ok and alignment_ok and guard_model_contract_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
