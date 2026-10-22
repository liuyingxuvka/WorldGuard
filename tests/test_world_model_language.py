"""The two small example worlds: each consistent version passes, each contradiction is caught by the model."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml
import pytest

from worldguard.kernel import run_worldguard

EXAMPLES = Path(__file__).resolve().parents[1] / "skills" / "worldguard" / "assets" / "examples"


def _world(name: str) -> dict:
    return yaml.safe_load((EXAMPLES / name).read_text(encoding="utf-8"))


def _codes(report) -> set[str]:
    return {error["code"] for result in report.child_results for error in result.errors}


def test_locked_door_scene_passes_and_a_key_handed_over_too_late_fails() -> None:
    scene = _world("scene_locked_door.yaml")
    assert run_worldguard(scene).status.value == "PASS"

    late_key = copy.deepcopy(scene)
    late_key["inputs"]["events"][0]["at"] = "t3"  # Jonas gives the key only after Mara unlocked the door at t2
    report = run_worldguard(late_key)
    assert report.status.value == "FAIL"
    assert "EVENT_PRECONDITION_UNMET" in _codes(report)
    event = next(result for result in report.child_results if result.guard == "EventGuard")
    assert event.counterexamples[0]["steps"][0]["event_id"] == "e_mara_unlock"
    assert event.counterexamples[0]["steps"][0]["missing_fluents"] == ["mara_has_key"]


def test_ferry_trip_passes_and_the_0930_ferry_fails_on_time_and_on_slack() -> None:
    trip = _world("trip_ferry.yaml")
    assert run_worldguard(trip).status.value == "PASS"

    early_ferry = copy.deepcopy(trip)
    early_ferry["inputs"]["events"][2]["at"] = "2026-11-02T09:30"  # the 09:30 ferry leaves before the train arrives at 10:05
    early_ferry["inputs"]["causal_model"]["equations"]["ferry_out_h"] = "9.5"
    report = run_worldguard(early_ferry)
    assert report.status.value == "FAIL"
    assert {"EVENT_PRECONDITION_UNMET", "CAUSAL_CONSTRAINT_VIOLATED"} <= _codes(report)
    causal = next(result for result in report.child_results if result.guard == "CausalGuard")
    assert causal.counterexamples[0]["steps"][0]["constraint"] == "slack_out_h >= 0"

    late_return = copy.deepcopy(trip)
    late_return["inputs"]["causal_model"]["equations"]["ferry_back_arrival_h"] = "16.75"  # 16:00 ferry lands after the 16:30 train
    report = run_worldguard(late_return)
    assert report.status.value == "FAIL"
    assert _codes(report) == {"CAUSAL_CONSTRAINT_VIOLATED"}


@pytest.mark.parametrize("constraint,exogenous", [
    ("slack_h / 0 >= 0", []),
    ("slack_h >= 'text'", []),
    ("slack_h >= missing", ["missing"]),
])
def test_unevaluable_causal_constraints_report_native_gaps(constraint, exogenous):
    report = run_worldguard({
        "claim": {"claim_id": "claim:constraint", "requested_semantics": ["causal"]},
        "inputs": {"causal_model": {"variables": ["slack_h"], "exogenous": exogenous,
            "equations": {"slack_h": "0.5"}, "scenarios": {"plan": {}},
            "constraints": [constraint]}},
    })
    assert report.status.value == "GAP"
    causal = next(result for result in report.child_results if result.guard == "CausalGuard")
    assert [error["code"] for error in causal.errors] == ["CAUSAL_CONSTRAINT_UNEVALUABLE"]
    semantic = next(receipt for receipt in report.semantic_receipts if receipt.guard == "CausalGuard")
    assert [finding["code"] for finding in semantic.findings] == ["SEM_CAUSAL_UNEVALUABLE_CONSTRAINT"]


def _gap_codes(report) -> list[str]:
    return [gap["code"] for gap in report.gaps]


def test_the_claim_is_checked_against_the_model_not_its_sentence() -> None:
    scene = _world("scene_locked_door.yaml")
    wrong_order = copy.deepcopy(scene)  # the world is consistent, but the claim says Iris got in before Mara unlocked
    wrong_order["claim"]["asserts"] = [{"event": "e_iris_enter", "before": "e_mara_unlock"}]
    report = run_worldguard(wrong_order)
    assert report.status.value == "FAIL"
    assert report.structural_status.value == "PASS"
    assert _gap_codes(report) == ["CLAIM_ASSERTION_FALSE"]
    assert report.gaps[0]["observed"] == {"e_iris_enter": "t3", "e_mara_unlock": "t2"}

    unknown = copy.deepcopy(scene)
    unknown["claim"]["asserts"] = [{"holds": "window_open", "at": "t3"}]
    report = run_worldguard(unknown)
    assert report.status.value == "GAP"
    assert _gap_codes(report) == ["CLAIM_ASSERTION_UNRESOLVED"]


def test_trip_claims_are_checked_against_the_timetable_model() -> None:
    trip = _world("trip_ferry.yaml")
    island_too_early = copy.deepcopy(trip)
    island_too_early["claim"]["asserts"] = [{"holds": "on_island", "at": "2026-11-02T10:30"}]  # still at the port
    report = run_worldguard(island_too_early)
    assert report.status.value == "FAIL"
    assert report.gaps[0]["observed"]["holding_fluents"] == ["at_port"]

    hour_of_slack = copy.deepcopy(trip)
    hour_of_slack["claim"]["asserts"] = [{"variable": "slack_back_h", "op": ">=", "value": 1}]  # 45 minutes, not an hour
    report = run_worldguard(hour_of_slack)
    assert report.status.value == "FAIL"
    assert report.gaps[0]["observed"] == {"published_timetable": 0.75}


def test_a_claim_without_assertions_is_not_bound_to_the_world_model() -> None:
    scene = _world("scene_locked_door.yaml")
    del scene["claim"]["asserts"]
    report = run_worldguard(scene)
    assert report.structural_status.value == "PASS"
    assert report.status.value == "GAP"
    assert _gap_codes(report) == ["CLAIM_NOT_BOUND"]
    assert report.gaps[0]["message"] == "claim not bound to the world model: add claim.asserts"


def test_scenario_overrides_reach_constraints_and_claim_rows():
    path = Path(__file__).parent / "fixtures/trials/trip_scen.yaml"
    report = run_worldguard(yaml.safe_load(path.read_text()))
    assert report.status.value == "FAIL"
    assert "CAUSAL_CONSTRAINT_VIOLATED" in _codes(report)
    row = next(gap for gap in report.gaps if gap["code"] == "CLAIM_ASSERTION_FALSE")
    assert row["observed"]["bus_back_30min_late"] == pytest.approx(-0.05)
    result = next(child for child in report.child_results if child.guard == "CausalGuard")
    assert any(step["scenario_id"] == "bus_back_30min_late" for item in result.counterexamples for step in item["steps"])


def test_interventions_on_empty_scenarios_reach_constraints_and_claim_rows():
    path = Path(__file__).parent / "fixtures/trials/new/trip_interv_list.yaml"
    report = run_worldguard(yaml.safe_load(path.read_text()))
    assert report.status.value == "FAIL"
    assert "CAUSAL_CONSTRAINT_VIOLATED" in _codes(report)
    row = next(gap for gap in report.gaps if gap["code"] == "CLAIM_ASSERTION_FALSE")
    assert row["observed"]["bus_30min_late"] == pytest.approx(-0.05)
    result = next(child for child in report.child_results if child.guard == "CausalGuard")
    assert any(step["scenario_id"] == "bus_30min_late" for item in result.counterexamples for step in item["steps"])


def test_intervention_can_override_exogenous_input_on_a_holdout():
    report = run_worldguard({"claim": {"claim_id": "holdout-do", "asserts": [
        {"variable": "x", "scenario": "holdout-do", "op": "==", "value": 5}]}, "inputs": {"causal_model": {
            "variables": ["x"], "exogenous": ["z"], "equations": {"x": "z + 1"},
            "scenarios": {"plan": {"z": 1}}, "holdout_scenarios": {"holdout": {"z": 2}},
            "interventions": [{"intervention_id": "holdout-do", "scenario_id": "holdout", "set": {"z": 4}}],
            "counterfactuals": [{"counterfactual_id": "cf-x", "intervention_id": "holdout-do", "query": "x"}]}}})
    assert report.status.value == "PASS"
    assert report.semantic_receipts[0].outputs["intervention_results"]["holdout-do"] == {"z": 4, "x": 5}
    assert report.semantic_receipts[0].outputs["counterfactual_results"]["cf-x"] == 5


def test_mapping_intervention_is_a_typed_cli_input_error(capsys):
    import json
    from worldguard.cli import main
    path = Path(__file__).parent / "fixtures/trials/trip_interv.yaml"
    assert main(["check", "--contract", str(path)]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["error"]["code"] == "WORLDGUARD_INPUT_INVALID"
    assert "interventions must be a list" in result["error"]["message"]


@pytest.mark.parametrize("actual,expected", [(-2, "FAIL"), (2, "GAP")])
def test_completed_causal_runs_survive_another_incomplete_run(actual, expected):
    report = run_worldguard({"claim": {"claim_id": "partial-runs", "asserts": [
        {"variable": "x", "op": ">=", "value": 0, "scenario": "actual_bad"}]}, "inputs": {"causal_model": {
            "variables": ["x", "y"], "exogenous": ["u"], "equations": {"x": "u", "y": "x + 1"},
            "scenarios": {"bad_missing": {}, "actual_bad": {"u": actual}}, "constraints": ["x >= 0"]}}})
    assert report.status.value == expected
    causal = next(child for child in report.child_results if child.guard == "CausalGuard")
    assert causal.status.value == ("FAIL" if actual < 0 else "PASS")
    assert report.claim_binding["status"] == ("FAIL" if actual < 0 else "PASS")
    assert report.claim_binding["assertions"][0]["observed"]["actual_bad"] == actual
    semantic = next(receipt for receipt in report.semantic_receipts if receipt.guard == "CausalGuard")
    assert semantic.status.value == "GAP"
    assert semantic.findings[0]["code"] == "SEM_CAUSAL_ROLLOUT_ERROR"
    assert semantic.findings[0]["evidence"]["errors"][0]["scenario_id"] == "bad_missing"
