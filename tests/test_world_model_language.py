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
    return {error["code"] for result in report.guard_results for error in result.errors}


def test_locked_door_scene_passes_and_a_key_handed_over_too_late_fails() -> None:
    scene = _world("scene_locked_door.yaml")
    assert run_worldguard(scene).status.value == "PASS"

    late_key = copy.deepcopy(scene)
    late_key["inputs"]["events"][0]["at"] = "t3"  # Jonas gives the key only after Mara unlocked the door at t2
    report = run_worldguard(late_key)
    assert report.status.value == "FAIL"
    assert "EVENT_PRECONDITION_UNMET" in _codes(report)
    event = next(result for result in report.guard_results if result.guard == "EventGuard")
    assert event.counterexamples[0]["steps"][0]["event_id"] == "e_mara_unlock"
    assert event.counterexamples[0]["steps"][0]["missing_fluents"] == ["mara_has_key"]


def test_ferry_trip_passes_and_the_0930_ferry_fails_on_time_and_on_slack() -> None:
    trip = _world("trip_ferry.yaml")
    assert run_worldguard(trip).status.value == "PASS"

    early_ferry = copy.deepcopy(trip)
    early_ferry["inputs"]["events"][2]["at"] = "2026-11-02T09:30"  # the 09:30 ferry leaves before the train arrives at 10:05
    report = run_worldguard(early_ferry)
    assert report.status.value == "FAIL"
    assert {"EVENT_PRECONDITION_UNMET", "CAUSAL_CONSTRAINT_VIOLATED"} <= _codes(report)
    causal = next(result for result in report.guard_results if result.guard == "CausalGuard")
    assert causal.counterexamples[0]["steps"][0]["constraint"] == "slack_out_h >= 0"

    late_return = copy.deepcopy(trip)
    late_return["inputs"]["events"][4]["at"] = "2026-11-03T16:45"  # 16:00 ferry lands after the 16:30 train
    report = run_worldguard(late_return)
    assert report.status.value == "FAIL"
    assert _codes(report) == {"CAUSAL_CONSTRAINT_VIOLATED", "EVENT_PRECONDITION_UNMET", "RESOURCE_CUMULATIVE_OVERCONSUMPTION"}


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
    causal = next(result for result in report.guard_results if result.guard == "CausalGuard")
    assert [error["code"] for error in causal.errors] == ["CAUSAL_CONSTRAINT_UNEVALUABLE"]
    assert len([gap for gap in report.gaps if gap["code"] == "CAUSAL_CONSTRAINT_UNEVALUABLE"]) == 1


def _gap_codes(report) -> list[str]:
    return [gap["code"] for gap in report.gaps]


def test_the_claim_is_checked_against_the_model_not_its_sentence() -> None:
    scene = _world("scene_locked_door.yaml")
    wrong_order = copy.deepcopy(scene)  # the world is consistent, but the claim says Iris got in before Mara unlocked
    wrong_order["claim"]["asserts"] = [{"event": "e_iris_enter", "before": "e_mara_unlock"}]
    report = run_worldguard(wrong_order)
    assert report.status.value == "FAIL"
    assert all(result.status.value == "PASS" for result in report.guard_results)
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
    assert all(result.status.value == "PASS" for result in report.guard_results)
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
    result = next(child for child in report.guard_results if child.guard == "CausalGuard")
    assert any(step["scenario_id"] == "bus_back_30min_late" for item in result.counterexamples for step in item["steps"])


def test_interventions_on_empty_scenarios_reach_constraints_and_claim_rows():
    path = Path(__file__).parent / "fixtures/trials/new/trip_interv_list.yaml"
    report = run_worldguard(yaml.safe_load(path.read_text()))
    assert report.status.value == "FAIL"
    assert "CAUSAL_CONSTRAINT_VIOLATED" in _codes(report)
    row = next(gap for gap in report.gaps if gap["code"] == "CLAIM_ASSERTION_FALSE")
    assert row["observed"]["bus_30min_late"] == pytest.approx(-0.05)
    result = next(child for child in report.guard_results if child.guard == "CausalGuard")
    assert any(step["scenario_id"] == "bus_30min_late" for item in result.counterexamples for step in item["steps"])


def test_intervention_can_override_exogenous_input_on_a_holdout():
    report = run_worldguard({"claim": {"claim_id": "holdout-do", "asserts": [
        {"variable": "x", "scenario": "holdout-do", "op": "==", "value": 5}]}, "inputs": {"causal_model": {
            "variables": ["x"], "exogenous": ["z"], "equations": {"x": "z + 1"},
            "scenarios": {"plan": {"z": 1}}, "holdout_scenarios": {"holdout": {"z": 2}},
            "interventions": [{"intervention_id": "holdout-do", "scenario_id": "holdout", "set": {"z": 4}}],
            "counterfactuals": [{"counterfactual_id": "cf-x", "intervention_id": "holdout-do", "query": "x"}]}}})
    assert report.status.value == "PASS"
    assert report.claim_binding["assertions"][0]["observed"] == {"holdout-do": 5}


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
    causal = next(child for child in report.guard_results if child.guard == "CausalGuard")
    assert causal.status.value == expected
    assert report.claim_binding["status"] == ("FAIL" if actual < 0 else "PASS")
    assert report.claim_binding["assertions"][0]["observed"]["actual_bad"] == actual
    if actual >= 0:
        assert causal.errors[0]["code"] == "CAUSAL_SCENARIO_UNEVALUABLE"
        assert causal.missing_slots[0]["scenario_id"] == "bad_missing"


def test_event_times_drive_causal_constraints_without_another_timetable():
    trip = _world("trip_ferry.yaml")
    trip["inputs"]["events"][2]["at"] = "2026-11-02T10:00"
    report = run_worldguard(trip)
    assert report.status.value == "FAIL"
    assert "CAUSAL_CONSTRAINT_VIOLATED" in _codes(report)


@pytest.mark.parametrize("first,second,expected", [("t1", "t2", 2), ("9:40", "10:20", 10 + 20/60),
    ("2026-11-02T09:00", "2026-11-03T10:05", 34 + 5/60)])
def test_event_clock_hours_and_scenario_overrides(first, second, expected):
    from worldguard.clock import event_time_values
    from worldguard.semantic import causal_scenario_values
    events = [{"event_id": "arrive", "at": first}, {"event_id": "leave", "at": second}]
    times = event_time_values(events)
    assert times["t_leave"] == pytest.approx(expected)
    causal = {"variables": ["slack"], "equations": {"slack": "t_leave - t_arrive"},
        "scenarios": {"plan": {}, "late": {"t_arrive": expected + 1}},
        "interventions": [{"intervention_id": "later", "scenario_id": "plan", "set": {"t_leave": expected + 2}}]}
    runs = causal_scenario_values(causal, times)
    assert runs["late"]["slack"] == -1
    assert runs["later"]["slack"] == pytest.approx(expected + 2 - times["t_arrive"])


@pytest.mark.parametrize("step", [0, 3])
def test_unique_traveler_duplication_fails_and_a_foreign_actor_is_a_gap(step):
    trip = _world("trip_ferry.yaml")
    trip["inputs"]["resources"]["transitions"][step]["produces"][0]["qty"] = 2
    report = run_worldguard(trip)
    assert report.status.value == "FAIL"
    assert "RESOURCE_UNIQUE_TOKEN_DUPLICATED" in _codes(report)
    trip = _world("trip_ferry.yaml")
    trip["inputs"]["events"][0]["actor"] = "ben"
    report = run_worldguard(trip)
    assert report.status.value == "GAP"
    assert "RESOURCE_EVENT_PARTICIPANT_UNNAMED" in _codes(report)
    trip["inputs"]["events"][0]["with"] = ["traveler"]
    assert run_worldguard(trip).status.value == "PASS"


@pytest.mark.parametrize("broken", ["unknown", "mixed", "collision"])
def test_event_link_input_errors_are_rejected_before_execution(broken):
    trip = _world("trip_ferry.yaml")
    if broken == "unknown":
        trip["inputs"]["resources"]["transitions"][0]["event"] = "absent"
    elif broken == "mixed":
        del trip["inputs"]["resources"]["transitions"][0]["event"]
    else:
        trip["inputs"]["causal_model"]["variables"].append("t_d1_train_arr")
    with pytest.raises(ValueError, match="event"):
        run_worldguard(trip)


def test_entity_registry_and_simultaneous_related_events_are_explicit_gaps():
    scene = _world("scene_locked_door.yaml")
    del scene["world_model"]["entities"]["Iris"]
    report = run_worldguard(scene)
    assert report.status.value == "GAP"
    assert next(row for row in report.gaps if row["code"] == "ENTITY_UNDECLARED")["missing_slots"] == ["Iris"]
    world = {"claim": {"requested_semantics": ["event"], "asserts": [{"holds": "done", "at": "t1"}]},
        "inputs": {"events": [{"event_id": "ready", "at": "t1", "initiates": "ready"},
            {"event_id": "use", "at": "t1", "requires": "ready", "initiates": "done"}]}}
    report = run_worldguard(world)
    assert report.status.value == "GAP"
    assert "EVENT_SAME_TIME_ORDER_UNKNOWN" in _codes(report)


def test_event_linked_token_transfers_follow_event_order_and_claims_share_it():
    trip = _world("trip_ferry.yaml")
    trip["inputs"]["resources"]["transitions"].reverse()
    report = run_worldguard(trip)
    assert report.status.value == "PASS"
    assert report.claim_binding["status"] == "PASS"


def test_trial_token_clone_fails_when_the_traveler_is_declared_unique():
    trial = yaml.safe_load((Path(__file__).parent / "fixtures/trials/trip_mut_out/token_clone.yaml").read_text())
    trial["inputs"]["resources"]["unique"] = ["traveler"]
    report = run_worldguard(trial)
    assert report.status.value == "FAIL"
    assert "RESOURCE_UNIQUE_TOKEN_DUPLICATED" in _codes(report)


def test_storm_prohibition_applies_to_the_actual_boat_event():
    world = yaml.safe_load((Path(__file__).parent / "fixtures/trials/trip_mut2_out/storm_consistent.yaml").read_text())
    event = next(row for row in world["inputs"]["events"] if row["event_id"] == "d2_boat")
    event.update(actor="traveler", action="take_boat")
    report = run_worldguard(world)
    assert report.status.value == "FAIL"
    assert "NORM_VIOLATED_BY_EVENT" in _codes(report)
    for fact in world["inputs"]["facts"]:
        if fact["fact_id"] in {"storm_warning", "lake_calm"}:
            fact["value"] = fact["fact_id"] == "lake_calm"
    assert run_worldguard(world).status.value == "PASS"


@pytest.mark.parametrize("storm_time,expected", [("t1", "FAIL"), ("t3", "PASS")])
def test_fluent_norm_conditions_use_the_state_before_the_event(storm_time, expected):
    world = {"claim": {"requested_semantics": ["event", "norm"], "asserts": [{"holds": "aboard", "at": "t4"}]},
        "inputs": {"events": [{"event_id": "storm", "at": storm_time, "initiates": "storm_warning"},
            {"event_id": "boat", "at": "t2", "actor": "traveler", "action": "take_boat", "initiates": "aboard"}],
            "norms": [{"actor": "traveler", "action": "take_boat", "modality": "forbidden", "condition": {"fluent": "storm_warning", "value": True}}]}}
    report = run_worldguard(world)
    assert report.status.value == expected
    if expected == "FAIL":
        assert "NORM_VIOLATED_BY_EVENT" in _codes(report)
        norm = next(result for result in report.guard_results if result.guard == "NormGuard")
        assert norm.counterexamples[0]["steps"][0]["event_id"] == "boat"
    world["claim"]["asserts"] = [{"actor": "traveler", "action": "take_boat", "modality": "forbidden"}]
    report = run_worldguard(world)
    assert report.claim_binding["status"] == "GAP"
    assert "needs at" in report.claim_binding["assertions"][0]["reason"]
    world["claim"]["asserts"][0]["at"] = "t2"
    assert run_worldguard(world).claim_binding["status"] == ("PASS" if storm_time == "t1" else "FAIL")


def test_agent_intentions_require_matching_events_when_actors_are_declared():
    world = yaml.safe_load((Path(__file__).parent / "fixtures/trials/story_mut_out/agent_contradicts.yaml").read_text())
    event = next(row for row in world["inputs"]["events"] if row["event_id"] == "e_lamp_lit")
    event.update(actor="Ada", action="light_lamp")
    report = run_worldguard(world)
    assert report.status.value == "GAP"
    assert "AGENT_INTENTION_UNREALISED" in _codes(report)
    missing = next(result for result in report.guard_results if result.guard == "AgentGuard").missing_slots
    assert {"agent_id": "Ada", "intention": "keep_lamp_dark"} in missing
