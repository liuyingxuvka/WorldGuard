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
