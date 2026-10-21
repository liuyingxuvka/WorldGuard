"""The two small example worlds: each consistent version passes, each contradiction is caught by the model."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

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
