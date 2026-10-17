from __future__ import annotations

import json
from copy import deepcopy
from math import ceil, sqrt
from pathlib import Path

import pytest

from worldguard import (
    GuardContract,
    SemanticStatus,
    derive_required_guards,
    run_model_mesh,
)
from worldguard.status import GuardStatus
from tests.helpers import attach_task_purpose_declarations


ROOT = Path(__file__).resolve().parents[1]


def _event_axis_dispositions() -> list[dict[str, str]]:
    return [
        {
            "axis_id": "state",
            "disposition": "not_applicable",
            "reason": "the static EventGuard rollout does not execute a state-machine",
            "claim_boundary": "no state-machine state execution is claimed",
        },
        {
            "axis_id": "transition",
            "disposition": "not_applicable",
            "reason": "the static EventGuard rollout does not execute transition specifications",
            "claim_boundary": "no state-machine transition execution is claimed",
        },
        {
            "axis_id": "event",
            "disposition": "required",
            "observation_field": "executed_event_ids",
            "claim_boundary": "exact event identities executed by EventGuard",
        },
        {
            "axis_id": "fluent",
            "disposition": "required",
            "observation_field": "reached_fluent_ids",
            "claim_boundary": "exact fluent identities reached by EventGuard",
        },
        {
            "axis_id": "branch",
            "disposition": "required",
            "observation_field": "executed_branch_ids",
            "claim_boundary": "exact branch identities exercised",
        },
        {
            "axis_id": "perturbation",
            "disposition": "required",
            "observation_field": "executed_perturbation_ids",
            "claim_boundary": "exact perturbation identities exercised",
        },
        {
            "axis_id": "intervention",
            "disposition": "required",
            "observation_field": "executed_intervention_ids",
            "claim_boundary": "exact intervention identities evaluated",
        },
        {
            "axis_id": "counterfactual",
            "disposition": "required",
            "observation_field": "executed_counterfactual_ids",
            "claim_boundary": "exact counterfactual identities evaluated",
        },
    ]


def test_worldguard_prompt_requires_exact_per_obligation_evidence() -> None:
    raw_prompt = (ROOT / "skills/worldguard/SKILL.md").read_text(encoding="utf-8")
    contracts = (ROOT / "skills/worldguard/references/worldguard-contracts.md").read_text(encoding="utf-8")
    assert "\n+Keep only" not in raw_prompt
    assert "[references/worldguard-contracts.md](references/worldguard-contracts.md)" in raw_prompt
    prompt = " ".join(contracts.split())
    assert "not proof of an individual WorldGuard obligation" in prompt
    assert "`evidence_ref`" in prompt
    assert "lowercase content hash" in prompt


def _predictive_mesh() -> dict:
    mesh = {
        "mesh_id": "predictive-mesh",
        "run_id": "predictive-test",
        "semantic_coverage": {
            "profile": "predictive",
            "expected_model_node_ids": ["world"],
            "scenario_ids": ["s-base"],
            "holdout_scenario_ids": ["s-hold"],
            "state_ids": [],
            "transition_ids": [],
            "event_ids": ["e0", "e1", "e2"],
            "fluent_ids": ["ready", "running"],
            "branch_ids": ["b0"],
            "perturbation_ids": ["p0"],
            "intervention_ids": ["do-y"],
            "counterfactual_ids": ["cf-y"],
            "horizon": {"start": "t0", "end": "t2", "steps": 3},
            "axis_dispositions": _event_axis_dispositions(),
        },
        "nodes": [
            {
                "model_id": "world",
                "authority": {"owns": ["event", "causal"]},
                "contract": {
                    "contract_id": "predictive-contract",
                    "run_id": "predictive-test",
                    "claim": {
                        "claim_id": "forecast-claim",
                        "text": "forecast state under declared scenarios",
                        "target_guards": ["EventGuard", "CausalGuard"],
                        "atoms": [
                            {
                                "atom_id": "forecast-atom",
                                "text": "state changes under intervention",
                                "requested_semantics": ["event", "causal"],
                                "predictive_intent": True,
                            }
                        ],
                    },
                    "world_model": {"model_id": "world-model", "model_version": "v1"},
                    "inputs": {
                        "variable_observations": {"y": ["t0", "t1", "t2"]},
                        "events": [
                            {
                                "event_id": "e0",
                                "at": "t0",
                                "initiates": "ready",
                                "branch_id": "b0",
                                "perturbation_id": "p0",
                            },
                            {
                                "event_id": "e1",
                                "at": "t1",
                                "terminates": "ready",
                                "initiates": "running",
                            },
                            {"event_id": "e2", "at": "t2", "initiates": "running"},
                        ],
                        "causal_model": {
                            "variables": ["y"],
                            "equations": {"y": "x * 2"},
                            "exogenous": ["x"],
                            "graph": [],
                            "scenarios": {"s-base": {"x": 1}},
                            "holdout_scenarios": {"s-hold": {"x": 3}},
                            "interventions": [
                                {
                                    "intervention_id": "do-y",
                                    "scenario_id": "s-base",
                                    "set": {"y": 10},
                                }
                            ],
                            "counterfactuals": [
                                {
                                    "counterfactual_id": "cf-y",
                                    "intervention_id": "do-y",
                                    "query": "y",
                                }
                            ],
                        },
                    },
                },
            }
        ],
    }
    attach_task_purpose_declarations(
        mesh["nodes"][0]["contract"],
        guards=["EventGuard", "CausalGuard"],
    )
    return mesh


def _long_horizon_mesh(
    timepoint_ids: list[str],
    *,
    steps: int = 1000,
) -> dict:
    mesh = _predictive_mesh()
    events = []
    for index, timepoint_id in enumerate(timepoint_ids):
        event = {
            "event_id": f"e{index}",
            "at": timepoint_id,
            "initiates": "ready" if index == 0 else "running",
        }
        if index == 0:
            event.update({"branch_id": "b0", "perturbation_id": "p0"})
        if index == 1:
            event["terminates"] = "ready"
        events.append(event)
    mesh["nodes"][0]["contract"]["inputs"]["events"] = events
    mesh["nodes"][0]["contract"]["inputs"]["variable_observations"] = {
        "y": list(timepoint_ids)
    }
    mesh["semantic_coverage"].update(
        {
            "event_ids": [event["event_id"] for event in events],
            "timepoint_ids": timepoint_ids,
            "horizon": {"start": "t0", "end": f"t{steps - 1}", "steps": steps},
        }
    )
    return mesh


def _distributed_timepoints(steps: int) -> list[str]:
    count = min(steps, max(3, ceil(sqrt(steps))))
    return [
        f"t{round(index * (steps - 1) / (count - 1))}"
        for index in range(count)
    ]


def test_structured_claim_atoms_derive_required_guards() -> None:
    contract = GuardContract.from_dict(_predictive_mesh()["nodes"][0]["contract"])

    assert derive_required_guards(contract.claim) == ("EventGuard", "CausalGuard")
    assert contract.claim.atoms[0].atom_id == "forecast-atom"
    assert contract.to_dict()["claim"]["atoms"][0]["predictive_intent"] is True


def test_omitted_claim_derived_guard_fails_closed() -> None:
    mesh = _predictive_mesh()
    mesh["nodes"][0]["contract"]["claim"]["target_guards"] = ["EventGuard"]

    report = run_model_mesh(mesh)

    assert report.semantic_status == SemanticStatus.PASS
    assert report.rollout_status == SemanticStatus.GAP
    assert report.status == GuardStatus.GAP
    assert any(
        finding.code == "MESH_CLAIM_DERIVED_GUARD_MISSING"
        for finding in report.findings
    )
    assert report.depth_receipt is not None
    assert report.depth_receipt.missing_guards == {"world": ["CausalGuard"]}
    assert any(
        item["reason"] == "claim_derived_guard_missing"
        for item in report.depth_receipt.skipped_children
    )


def test_expected_contractless_node_is_counted_and_blocks_aggregate_pass() -> None:
    report = run_model_mesh(
        {
            "mesh_id": "contractless",
            "run_id": "coverage-test",
            "semantic_coverage": {
                "profile": "bounded",
                "expected_model_node_ids": ["missing-contract"],
            },
            "nodes": [{"model_id": "missing-contract"}],
        }
    )

    assert report.status == GuardStatus.GAP
    assert report.rollout_status == SemanticStatus.GAP
    assert any(
        finding.code == "MESH_EXPECTED_NODE_CONTRACT_MISSING"
        for finding in report.findings
    )
    assert report.depth_receipt is not None
    assert report.depth_receipt.expected_model_nodes == ["missing-contract"]
    assert report.depth_receipt.executed_model_nodes == []
    assert report.depth_receipt.skipped_model_nodes[0]["reason"] == "missing_guard_contract"


def test_single_event_can_pass_locally_but_cannot_license_prediction() -> None:
    mesh = _predictive_mesh()
    mesh["nodes"][0]["contract"]["inputs"]["events"] = [
        mesh["nodes"][0]["contract"]["inputs"]["events"][0]
    ]

    report = run_model_mesh(mesh)

    assert report.semantic_status == SemanticStatus.PASS
    assert report.rollout_status == SemanticStatus.GAP
    assert report.depth_receipt is not None
    assert report.depth_receipt.predictive_claim_licensed is False
    assert "predictive_timepoint_depth_insufficient" in report.depth_receipt.predictive_gaps


def test_single_equation_without_intervention_or_counterfactual_stays_bounded() -> None:
    mesh = _predictive_mesh()
    causal = mesh["nodes"][0]["contract"]["inputs"]["causal_model"]
    causal["interventions"] = []
    causal["counterfactuals"] = []

    report = run_model_mesh(mesh)

    causal_receipt = next(
        receipt for receipt in report.semantic_receipts if receipt.guard == "CausalGuard"
    )
    assert causal_receipt.status == SemanticStatus.PASS
    assert report.rollout_status == SemanticStatus.GAP
    assert report.depth_receipt is not None
    assert report.depth_receipt.predictive_claim_licensed is False
    assert "predictive_intervention_ids_not_executed:do-y" in report.depth_receipt.predictive_gaps
    assert "predictive_counterfactual_ids_not_executed:cf-y" in report.depth_receipt.predictive_gaps


def test_rich_prediction_still_blocks_when_one_guard_skips_holdout_scenario() -> None:
    mesh = _predictive_mesh()
    mesh["nodes"][0]["contract"]["inputs"]["causal_model"][
        "holdout_scenarios"
    ] = {}

    report = run_model_mesh(mesh)

    assert report.depth_receipt is not None
    assert report.depth_receipt.predictive_claim_licensed is False
    assert "CausalGuard:holdout_rollout_incomplete" in report.depth_receipt.predictive_gaps
    object_row = report.depth_receipt.quantitative_coverage[
        "per_model_node_results"
    ][0]
    assert object_row["passed"] is False
    assert "CausalGuard:holdout_rollout_incomplete" in object_row["gaps"]


def test_rich_prediction_still_blocks_when_structured_claim_atom_is_missing() -> None:
    mesh = _predictive_mesh()
    mesh["nodes"][0]["contract"]["claim"]["atoms"] = []

    with pytest.raises(
        ValueError,
        match="claim requires current requested_semantics or structured atoms",
    ):
        run_model_mesh(mesh)


def test_complete_supported_predictive_fixture_gets_mesh_bound_license() -> None:
    report = run_model_mesh(_predictive_mesh())

    assert report.status == GuardStatus.PASS
    assert report.structural_status == GuardStatus.PASS
    assert report.semantic_status == SemanticStatus.PASS
    assert report.rollout_status == SemanticStatus.PASS
    assert report.depth_receipt is not None
    assert report.depth_receipt.predictive_claim_licensed is True
    assert report.depth_receipt.predictive_gaps == []
    assert len(report.depth_receipt.mesh_fingerprint) == 64
    assert len(report.depth_receipt.coverage_fingerprint) == 64
    assert report.depth_receipt.quantitative_coverage["expected_scenario_count"] == 1
    assert report.depth_receipt.quantitative_coverage["executed_scenario_count"] == 1
    assert report.depth_receipt.quantitative_coverage["expected_holdout_scenario_count"] == 1
    assert report.depth_receipt.quantitative_coverage["executed_holdout_scenario_count"] == 1
    observations = report.depth_receipt.native_obligation_evidence
    assert observations
    assert {
        "obligation:worldguard-semantic-universe",
        "obligation:worldguard-timepoint-strata-depth",
        "obligation:worldguard-scenario-holdout-depth",
        "obligation:worldguard-predictive-axes",
        "obligation:worldguard-receipt-freshness",
        "obligation:worldguard-claim-routes",
    } <= {
        obligation_id
        for observation in observations
        for obligation_id in observation["target_obligation_ids"]
    }
    for observation in observations:
        assert observation["native_object_id"]
        assert str(observation["evidence_ref"]).startswith("worldguard:")
        assert len(observation["evidence_sha256"]) == 64
        assert observation["evidence_sha256"] == observation["evidence_sha256"].lower()


def _axis_disposition(mesh: dict, axis_id: str) -> dict:
    return next(
        row
        for row in mesh["semantic_coverage"]["axis_dispositions"]
        if row["axis_id"] == axis_id
    )


@pytest.mark.parametrize(
    ("mutation", "expected_fragment"),
    [
        ("missing", "missing=['state']"),
        ("duplicate", "duplicates=['state']"),
        ("unknown", "extra=['weather']"),
    ],
)
def test_predictive_axis_dispositions_require_exactly_one_current_row_per_axis(
    mutation: str,
    expected_fragment: str,
) -> None:
    mesh = _predictive_mesh()
    dispositions = mesh["semantic_coverage"]["axis_dispositions"]
    state = deepcopy(_axis_disposition(mesh, "state"))
    if mutation == "missing":
        dispositions.remove(_axis_disposition(mesh, "state"))
    elif mutation == "duplicate":
        dispositions.append(state)
    else:
        state["axis_id"] = "weather"
        dispositions.append(state)

    with pytest.raises(
        ValueError,
        match=r"predictive axis dispositions must contain exactly one current row per axis",
    ) as exc_info:
        run_model_mesh(mesh)

    assert expected_fragment in str(exc_info.value)


def test_not_applicable_axis_requires_reason() -> None:
    mesh = _predictive_mesh()
    _axis_disposition(mesh, "state").pop("reason")

    with pytest.raises(
        ValueError,
        match="not_applicable predictive axis state requires reason",
    ):
        run_model_mesh(mesh)


def test_required_axis_requires_claim_boundary() -> None:
    mesh = _predictive_mesh()
    _axis_disposition(mesh, "event").pop("claim_boundary")

    with pytest.raises(
        ValueError,
        match="predictive axis event requires claim_boundary",
    ):
        run_model_mesh(mesh)


def test_not_applicable_axis_cannot_carry_observation_field() -> None:
    mesh = _predictive_mesh()
    _axis_disposition(mesh, "state")["observation_field"] = "executed_state_ids"

    with pytest.raises(
        ValueError,
        match=(
            "not_applicable predictive axis state must not carry observation_field"
        ),
    ):
        run_model_mesh(mesh)


def test_required_axis_cannot_carry_reason() -> None:
    mesh = _predictive_mesh()
    _axis_disposition(mesh, "event")["reason"] = "required axes need evidence"

    with pytest.raises(
        ValueError,
        match="required predictive axis event must not carry reason",
    ):
        run_model_mesh(mesh)


@pytest.mark.parametrize(
    ("observation_field", "expected_fluent_ids"),
    [
        ("reached_fluent_ids", ["ready", "running"]),
        ("active_fluent_ids", ["running"]),
        ("final_fluent_ids_by_scenario", ["running"]),
    ],
)
def test_fluent_axis_accepts_each_native_observation_domain(
    observation_field: str,
    expected_fluent_ids: list[str],
) -> None:
    mesh = _predictive_mesh()
    mesh["semantic_coverage"]["fluent_ids"] = expected_fluent_ids
    _axis_disposition(mesh, "fluent")["observation_field"] = observation_field

    report = run_model_mesh(mesh)

    assert report.status == GuardStatus.PASS
    assert report.depth_receipt is not None
    assert report.depth_receipt.predictive_claim_licensed is True


def test_not_applicable_axis_cannot_be_changed_to_required_with_empty_ids() -> None:
    mesh = _predictive_mesh()
    state = _axis_disposition(mesh, "state")
    state.update(
        {
            "disposition": "required",
            "observation_field": "executed_state_ids",
        }
    )
    state.pop("reason")

    with pytest.raises(
        ValueError,
        match="required predictive axis state has empty state_ids",
    ):
        run_model_mesh(mesh)


def test_not_applicable_axis_cannot_carry_expected_ids() -> None:
    mesh = _predictive_mesh()
    mesh["semantic_coverage"]["state_ids"] = ["state:invented"]

    with pytest.raises(
        ValueError,
        match="not_applicable predictive axis state must not carry state_ids",
    ):
        run_model_mesh(mesh)


@pytest.mark.parametrize(
    ("axis_id", "wrong_observation_field"),
    [
        ("event", "reached_fluent_ids"),
        ("fluent", "executed_event_ids"),
    ],
)
def test_event_and_fluent_axes_cannot_use_each_others_identity_domain(
    axis_id: str,
    wrong_observation_field: str,
) -> None:
    mesh = _predictive_mesh()
    _axis_disposition(mesh, axis_id)[
        "observation_field"
    ] = wrong_observation_field

    with pytest.raises(
        ValueError,
        match=rf"predictive axis {axis_id} observation_field must be one of",
    ):
        run_model_mesh(mesh)


def test_required_axis_empty_array_cannot_bypass_predictive_depth() -> None:
    mesh = _predictive_mesh()
    mesh["semantic_coverage"]["event_ids"] = []

    with pytest.raises(
        ValueError,
        match="required predictive axis event has empty event_ids",
    ):
        run_model_mesh(mesh)


def test_not_applicable_axis_blocks_when_runtime_still_observes_that_domain() -> None:
    mesh = _predictive_mesh()
    event = _axis_disposition(mesh, "event")
    event.update(
        {
            "disposition": "not_applicable",
            "reason": "caller claims no event execution applies",
        }
    )
    event.pop("observation_field")
    mesh["semantic_coverage"]["event_ids"] = []

    report = run_model_mesh(mesh)

    assert report.depth_receipt is not None
    assert report.depth_receipt.predictive_claim_licensed is False
    assert {
        "predictive_event_not_applicable_observed:e0",
        "predictive_event_not_applicable_observed:e1",
        "predictive_event_not_applicable_observed:e2",
    } <= set(report.depth_receipt.predictive_gaps)


def test_native_obligation_hash_tracks_exact_semantic_input() -> None:
    baseline = run_model_mesh(_predictive_mesh()).depth_receipt
    changed_mesh = deepcopy(_predictive_mesh())
    changed_mesh["nodes"][0]["contract"]["inputs"]["events"][0]["action"] = (
        "changed exact event action"
    )
    changed = run_model_mesh(changed_mesh).depth_receipt

    assert baseline is not None and changed is not None
    native_object_id = "semantic-child:world:EventGuard"
    baseline_row = next(
        item for item in baseline.native_obligation_evidence
        if item["native_object_id"] == native_object_id
    )
    changed_row = next(
        item for item in changed.native_obligation_evidence
        if item["native_object_id"] == native_object_id
    )
    assert baseline_row["evidence_ref"] == changed_row["evidence_ref"]
    assert baseline_row["evidence_sha256"] != changed_row["evidence_sha256"]


def test_long_horizon_representative_timepoints_cover_floor_ratio_and_phases() -> None:
    timepoints = _distributed_timepoints(1000)
    report = run_model_mesh(_long_horizon_mesh(timepoints))

    assert report.depth_receipt is not None
    assert report.depth_receipt.predictive_claim_licensed is True
    coverage = report.depth_receipt.quantitative_coverage
    assert coverage["horizon_step_count"] == 1000
    assert coverage["effective_minimum_timepoint_count"] == 32
    assert coverage["executed_timepoint_count"] == 32
    assert coverage["observed_timepoint_coverage"] == 0.032
    assert coverage["max_normalized_timepoint_gap"] <= coverage["allowed_max_normalized_timepoint_gap"]
    assert all(row["passed"] for row in coverage["time_strata_results"])


def test_thousand_step_horizon_with_two_points_cannot_license_prediction() -> None:
    report = run_model_mesh(_long_horizon_mesh(["t0", "t999"]))

    assert report.depth_receipt is not None
    assert report.depth_receipt.predictive_claim_licensed is False
    gaps = report.depth_receipt.predictive_gaps
    assert "predictive_timepoint_sample_floor_not_met:2/32" in gaps
    assert "predictive_timepoint_coverage_ratio_not_met:0.002000/0.032000" in gaps
    assert "predictive_time_stratum_uncovered:middle" in gaps


def test_ten_thousand_step_horizon_raises_native_floor_per_series() -> None:
    report = run_model_mesh(
        _long_horizon_mesh(["t0", "t9999"], steps=10_000)
    )

    assert report.depth_receipt is not None
    assert report.depth_receipt.predictive_claim_licensed is False
    node = report.depth_receipt.quantitative_coverage["per_model_node_results"][0]
    assert node["timepoint_coverage"]["effective_minimum_timepoint_count"] == 100
    assert (
        node["per_variable_timepoint_results"][0]["timepoint_coverage"]
        ["effective_minimum_timepoint_count"]
        == 100
    )
    assert any(
        gap.endswith("predictive_timepoint_sample_floor_not_met:2/100")
        for gap in report.depth_receipt.predictive_gaps
    )


def test_enough_points_concentrated_outside_middle_phase_are_still_shallow() -> None:
    concentrated = [*(f"t{index}" for index in range(31)), "t999"]
    report = run_model_mesh(_long_horizon_mesh(concentrated))

    assert report.depth_receipt is not None
    assert report.depth_receipt.predictive_claim_licensed is False
    coverage = report.depth_receipt.quantitative_coverage
    assert coverage["executed_timepoint_count"] == 32
    assert not any(
        gap.startswith("predictive_timepoint_sample_floor_not_met")
        for gap in report.depth_receipt.predictive_gaps
    )
    assert "predictive_time_stratum_uncovered:middle" in report.depth_receipt.predictive_gaps


def test_floor_and_all_phases_still_fail_when_one_temporal_hole_is_too_large() -> None:
    clustered = [
        *(f"t{index}" for index in range(15)),
        *(f"t{index}" for index in range(500, 516)),
        "t999",
    ]
    report = run_model_mesh(_long_horizon_mesh(clustered))

    assert report.depth_receipt is not None
    coverage = report.depth_receipt.quantitative_coverage
    assert coverage["executed_timepoint_count"] == 32
    assert not any(
        gap.startswith("predictive_timepoint_sample_floor_not_met")
        for gap in report.depth_receipt.predictive_gaps
    )
    assert not any(
        gap.startswith("predictive_time_stratum_uncovered")
        for gap in report.depth_receipt.predictive_gaps
    )
    assert any(
        gap.startswith("predictive_timepoint_max_gap_exceeded")
        for gap in report.depth_receipt.predictive_gaps
    )
    assert coverage["max_normalized_timepoint_gap"] > coverage["allowed_max_normalized_timepoint_gap"]
    assert report.depth_receipt.predictive_claim_licensed is False


def test_caller_named_strata_cannot_replace_native_early_middle_late_phases() -> None:
    concentrated = [*(f"t{index}" for index in range(31)), "t999"]
    mesh = _long_horizon_mesh(concentrated)
    mesh["semantic_coverage"]["time_strata"] = {
        "phase-a": [f"t{index}" for index in range(0, 10)],
        "phase-b": [f"t{index}" for index in range(10, 20)],
        "phase-c": [*(f"t{index}" for index in range(20, 31)), "t999"],
    }

    report = run_model_mesh(mesh)

    assert report.depth_receipt is not None
    assert report.depth_receipt.predictive_claim_licensed is False
    assert "predictive_time_stratum_uncovered:middle" in report.depth_receipt.predictive_gaps
    native_rows = [
        row
        for row in report.depth_receipt.quantitative_coverage["time_strata_results"]
        if row["origin"] == "worldguard_native_early_middle_late"
    ]
    assert {row["stratum_id"] for row in native_rows} == {"early", "middle", "late"}


def test_rich_aggregate_cannot_hide_one_shallow_predictive_model_node() -> None:
    mesh = _long_horizon_mesh(_distributed_timepoints(1000))
    deep_node = mesh["nodes"][0]
    shallow_node = deepcopy(deep_node)
    shallow_node["model_id"] = "world-shallow"
    shallow_node["contract"]["contract_id"] = "predictive-contract-shallow"
    shallow_node["contract"]["claim"]["claim_id"] = "forecast-claim-shallow"
    shallow_node["contract"]["claim"]["atoms"][0]["atom_id"] = "forecast-atom-shallow"
    shallow_node["contract"]["inputs"]["events"] = [
        deepcopy(deep_node["contract"]["inputs"]["events"][0]),
        deepcopy(deep_node["contract"]["inputs"]["events"][-1]),
    ]
    attach_task_purpose_declarations(
        shallow_node["contract"], guards=["EventGuard", "CausalGuard"]
    )
    mesh["nodes"].append(shallow_node)
    mesh["semantic_coverage"]["expected_model_node_ids"] = [
        "world",
        "world-shallow",
    ]

    report = run_model_mesh(mesh)

    assert report.depth_receipt is not None
    assert report.depth_receipt.quantitative_coverage["executed_timepoint_count"] == 32
    # The aggregate contains more evidence than the shallow child, but the
    # per-node result still exposes its own missing middle phase and floor.
    object_rows = {
        row["model_node_id"]: row
        for row in report.depth_receipt.quantitative_coverage["per_model_node_results"]
    }
    assert object_rows["world"]["passed"] is True
    assert object_rows["world-shallow"]["passed"] is False
    assert any(
        gap.startswith("predictive_object:world-shallow:predictive_timepoint_sample_floor_not_met")
        for gap in report.depth_receipt.predictive_gaps
    )
    assert report.depth_receipt.predictive_claim_licensed is False


def test_coverage_fingerprint_changes_when_expected_universe_changes() -> None:
    first = run_model_mesh(_predictive_mesh()).depth_receipt
    changed = deepcopy(_predictive_mesh())
    changed["semantic_coverage"]["branch_ids"].append("b-new")
    second = run_model_mesh(changed).depth_receipt

    assert first is not None and second is not None
    assert first.coverage_fingerprint != second.coverage_fingerprint
    assert second.predictive_claim_licensed is False




def test_expected_node_list_cannot_hide_a_discovered_predictive_node() -> None:
    mesh = _predictive_mesh()
    omitted = deepcopy(mesh["nodes"][0])
    omitted["model_id"] = "world-omitted"
    omitted["contract"]["contract_id"] = "predictive-contract-omitted"
    omitted["contract"]["claim"]["claim_id"] = "forecast-claim-omitted"
    omitted["contract"]["claim"]["atoms"][0]["atom_id"] = "forecast-atom-omitted"
    attach_task_purpose_declarations(
        omitted["contract"], guards=["EventGuard", "CausalGuard"]
    )
    mesh["nodes"].append(omitted)

    report = run_model_mesh(mesh)

    assert set(report.depth_receipt.discovered_model_nodes) == {
        "world",
        "world-omitted",
    }
    assert report.depth_receipt.declared_model_nodes == ["world"]
    assert set(report.depth_receipt.expected_model_nodes) == {
        "world",
        "world-omitted",
    }
    assert (
        "discovered_model_node_undeclared:world-omitted"
        in report.depth_receipt.predictive_gaps
    )
    assert report.depth_receipt.predictive_claim_licensed is False


def test_model_node_exclusion_requires_closed_reason_and_no_overlap() -> None:
    mesh = _predictive_mesh()
    mesh["nodes"].append({"model_id": "background", "model_kind": "structural"})
    mesh["semantic_coverage"]["excluded_model_nodes"] = [
        {"model_node_id": "background"}
    ]

    report = run_model_mesh(mesh)

    assert any(
        gap.startswith("model_node_exclusion_invalid:background:")
        for gap in report.depth_receipt.predictive_gaps
    )
    assert "background" in report.depth_receipt.expected_model_nodes
    assert report.depth_receipt.predictive_claim_licensed is False


def test_closed_structural_exclusion_is_visible_and_never_contributes() -> None:
    mesh = _predictive_mesh()
    mesh["nodes"].append({"model_id": "background", "model_kind": "structural"})
    mesh["semantic_coverage"]["excluded_model_nodes"] = [
        {
            "model_node_id": "background",
            "reason": "shape-only context outside the predictive claim",
            "disposition": "not_applicable",
        }
    ]

    report = run_model_mesh(mesh)

    assert report.depth_receipt.discovered_model_nodes == ["world", "background"]
    assert report.depth_receipt.expected_model_nodes == ["world"]
    assert report.depth_receipt.excluded_model_nodes == [
        {
            "model_node_id": "background",
            "reason": "shape-only context outside the predictive claim",
            "disposition": "not_applicable",
            "critical": False,
        }
    ]
    assert all(row.node_id != "background" for row in report.semantic_receipts)
    assert all(
        atom["node_id"] != "background" for atom in report.depth_receipt.claim_atoms
    )
    assert report.depth_receipt.predictive_claim_licensed is True


def test_excluded_node_still_connected_to_mesh_blocks_prediction() -> None:
    mesh = _predictive_mesh()
    mesh["nodes"].append({"model_id": "background", "model_kind": "structural"})
    mesh["edges"] = [
        {
            "edge_id": "background-to-world",
            "source_model_id": "background",
            "target_model_id": "world",
            "relation": "depends_on",
        }
    ]
    mesh["semantic_coverage"]["excluded_model_nodes"] = [
        {
            "model_node_id": "background",
            "reason": "claimed outside scope",
            "disposition": "not_applicable",
        }
    ]

    report = run_model_mesh(mesh)

    assert (
        "excluded_model_node_still_connected:background"
        in report.depth_receipt.predictive_gaps
    )
    assert report.depth_receipt.predictive_claim_licensed is False


def test_node_level_time_depth_cannot_hide_one_shallow_variable_series() -> None:
    timepoints = _distributed_timepoints(1000)
    mesh = _long_horizon_mesh(timepoints)
    mesh["nodes"][0]["contract"]["inputs"]["variable_observations"] = {
        "y": ["t0", "t999"]
    }

    report = run_model_mesh(mesh)
    node = report.depth_receipt.quantitative_coverage["per_model_node_results"][0]
    variable = node["per_variable_timepoint_results"][0]

    assert node["timepoint_coverage"]["executed_timepoint_count"] == 32
    assert variable["variable_or_signal_id"] == "y"
    assert variable["timepoint_coverage"]["executed_timepoint_count"] == 2
    assert any(
        gap.startswith(
            "predictive_object:world:variable_timepoint:y:predictive_timepoint_sample_floor_not_met:2/32"
        )
        for gap in report.depth_receipt.predictive_gaps
    )
    assert report.depth_receipt.predictive_claim_licensed is False


def test_variable_series_with_enough_points_in_wrong_phases_is_still_shallow() -> None:
    node_timepoints = _distributed_timepoints(1000)
    mesh = _long_horizon_mesh(node_timepoints)
    mesh["nodes"][0]["contract"]["inputs"]["variable_observations"] = {
        "y": [*(f"t{index}" for index in range(31)), "t999"]
    }

    report = run_model_mesh(mesh)

    assert any(
        gap
        == "predictive_object:world:variable_timepoint:y:predictive_time_stratum_uncovered:middle"
        for gap in report.depth_receipt.predictive_gaps
    )
    assert report.depth_receipt.predictive_claim_licensed is False
