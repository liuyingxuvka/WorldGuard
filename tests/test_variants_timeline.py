from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from worldguard.cli import main
from worldguard.kernel import run_worldguard
from worldguard.mesh import run_model_mesh
from worldguard.timeline import timeline
from worldguard.variants import apply_variant

EXAMPLES = Path(__file__).parents[1] / "skills/worldguard/assets/examples"


def _scene():
    return yaml.safe_load((EXAMPLES / "scene_locked_door.yaml").read_text())


def test_examples_check_their_known_bad_variants_and_catch_a_missing_rule():
    for name in ("scene_locked_door.yaml", "trip_ferry.yaml"):
        report = run_worldguard(yaml.safe_load((EXAMPLES / name).read_text()))
        assert report.status.value == "PASS"
        assert report.checked["variants"] >= 2
    scene = _scene()
    next(row for row in scene["inputs"]["events"] if row["event_id"] == "e_mara_unlock").pop("requires")
    report = run_worldguard(scene)
    assert report.status.value == "GAP"
    row = next(row for row in report.gaps if row["code"] == "VARIANT_NOT_CAUGHT")
    assert row["variant_id"] == "key_given_too_late"
    assert row["actual"] == "FAIL"  # the claim still fails, but the missing Guard rule is caught
    assert "EVENT_PRECONDITION_UNMET" not in row["codes"]


def test_variant_patches_support_indices_ids_removal_and_append_without_mutation():
    world = {"inputs": {"events": [{"event_id": "first", "at": 1, "requires": "ready"}],
        "objects": [{"custom_id": "item", "value": 2}]}, "variants": []}
    before = deepcopy(world)
    revised = apply_variant(world, {"id": "patch", "set": {"inputs.events[0].at": 2, "inputs.objects[item].value": 3},
        "remove": ["inputs.events[first].requires"], "add": {"inputs.events": [{"event_id": "second", "at": 3}]}})
    assert world == before
    assert "variants" not in revised
    assert revised["inputs"]["events"] == [{"event_id": "first", "at": 2}, {"event_id": "second", "at": 3}]
    assert revised["inputs"]["objects"][0]["value"] == 3
    removed = apply_variant(world, {"id": "remove", "remove": ["inputs.events[first]"]})
    assert removed["inputs"]["events"] == []
    revised = apply_variant({"items": [{"event_id": "chapter.3", "at": 1}]},
                            {"id": "dotted-id", "set": {"items[chapter.3].at": 2}})
    assert revised["items"][0]["at"] == 2


@pytest.mark.parametrize("variant", [
    {"id": "bad", "set": {"inputs.events[absent].at": "t3"}},
    {"id": "bad", "set": {"inputs.events[999].at": "t3"}},
    {"id": "bad", "set": {"inputs..events": []}},
    {"id": "bad", "add": {"inputs.event_model": []}},
    {"id": "bad", "expect": "PASS"},
    {"id": "bad", "expect": []},
    {"id": "bad", "remove": "inputs.events"},
    {"id": "bad", "sett": {}},
])
def test_bad_variant_inputs_are_typed_errors_naming_the_variant(tmp_path, capsys, variant):
    world = _scene()
    world["variants"] = [variant]
    path = tmp_path / "world.json"
    path.write_text(json.dumps(world))
    before = path.read_bytes()
    assert main(["check", "--contract", str(path)]) == 2
    error = json.loads(capsys.readouterr().out)["error"]
    assert error["code"] == "WORLDGUARD_INPUT_INVALID"
    assert "bad" in error["message"]
    assert path.read_bytes() == before


def test_duplicate_variant_ids_and_ambiguous_selector_are_errors():
    world = _scene()
    world["variants"].append(deepcopy(world["variants"][0]))
    with pytest.raises(ValueError, match="unique"):
        run_worldguard(world)
    with pytest.raises(ValueError, match="variant ambiguous"):
        apply_variant({"items": [{"id": "same"}, {"other_id": "same"}]}, {"id": "ambiguous", "remove": ["items[same]"]})


def test_timeline_reuses_event_and_token_state_and_marks_the_failure_prefix():
    story = yaml.safe_load((Path(__file__).parent / "fixtures/trials/story_v1.yaml").read_text())
    view = timeline(story)
    assert view["clock"] == "label"
    assert view["steps"][0]["at"] is None
    by_time = {row["at"]: row for row in view["steps"]}
    assert "lamp_lit" not in by_time["t1"]["fluents"]
    assert "lamp_lit" in by_time["t2"]["fluents"]
    assert "cora_on_island" in by_time["t3"]["fluents"]
    scene = _scene()
    scene.pop("variants")
    event = next(row for row in scene["inputs"]["events"] if row["event_id"] == "e_give_key")
    event["at"] = "t3"
    report = run_worldguard(scene)
    step = next(result for result in report.guard_results if result.guard == "EventGuard").counterexamples[0]["steps"][0]
    assert step["trace"] == [{"at": "t2", "event_id": "e_mara_unlock"}]
    assert step["source"] == "scene 3 paragraph 2"
    view = timeline(scene, problems=report.gaps)
    assert "EVENT_PRECONDITION_UNMET" in view["steps"][1]["problems"]
    trip = yaml.safe_load((EXAMPLES / "trip_ferry.yaml").read_text())
    view = timeline(trip)
    assert view["steps"][1]["tokens"]["on_train"]["traveler"] == 1
    assert view["steps"][-1]["tokens"]["home"]["traveler"] == 1
    assert view["variables"]["published_timetable"]["slack_back_h"] == 0.75
    world = {"claim": {"asserts": [{"holds": "done", "at": "t3"}]}, "inputs": {"events": [
        {"event_id": "first", "at": "t1", "initiates": "ready"},
        {"event_id": "second", "at": "t2", "requires": "absent", "initiates": "done"}]}}
    report = run_worldguard(world)
    view = timeline(world, problems=report.gaps)
    assert view["steps"][1]["problems"] == []
    assert view["steps"][2]["problems"] == ["EVENT_PRECONDITION_UNMET"]


def test_timeline_cli_scopes_scenarios_and_full_report_only_has_trace(tmp_path, capsys):
    world = _scene()
    world.pop("variants")
    next(row for row in world["inputs"]["events"] if row["event_id"] == "e_give_key")["at"] = "t3"
    path = tmp_path / "world.json"
    path.write_text(json.dumps(world))
    assert main(["check", "--contract", str(path)]) == 1
    summary = json.loads(capsys.readouterr().out)
    assert "trace" not in json.dumps(summary)
    assert main(["check", "--contract", str(path), "--json"]) == 1
    full = json.loads(capsys.readouterr().out)
    assert "trace" in full["guard_results"][0]["counterexamples"][0]["steps"][0]
    assert main(["timeline", "--contract", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["steps"][1]["event_id"] == "e_mara_unlock"
    assert main(["timeline", "--contract", str(path), "--scenario", "absent"]) == 2
    assert "absent" in json.loads(capsys.readouterr().out)["error"]["message"]


def test_source_references_survive_assertion_transfer_and_mesh_problems():
    scene = _scene()
    scene.pop("variants")
    scene["claim"]["asserts"] = [{"holds": "absent", "at": "t3", "source": "chapter 3 paragraph 8"}]
    report = run_worldguard(scene)
    assert report.gaps[0]["source"] == "chapter 3 paragraph 8"
    mesh = run_model_mesh({"mesh_id": "source", "nodes": [{"model_id": "scene", "contract": scene, "source": "chapter 3"},
        {"model_id": "missing", "source": "chapter 4"}]})
    assert next(row for row in mesh.to_dict()["gaps"] if row.get("node_id") == "missing")["source"] == "chapter 4"
    scene["inputs"]["resources"]["transitions"][0]["source"] = "chapter 3 paragraph 1"
    scene["inputs"]["resources"]["places"]["jonas_key"][0]["qty"] = 0
    report = run_worldguard(scene)
    assert next(row for row in report.gaps if row["code"] == "RESOURCE_MISSING_TOKEN")["source"] == "chapter 3 paragraph 1"


def test_uncaught_variants_in_a_mesh_node_prevent_mesh_pass():
    scene = _scene()
    next(row for row in scene["inputs"]["events"] if row["event_id"] == "e_mara_unlock").pop("requires")
    report = run_model_mesh({"mesh_id": "variants", "nodes": [{"model_id": "scene", "contract": scene}]})
    assert report.status.value == "GAP"
    assert any(row["code"] == "VARIANT_NOT_CAUGHT" and row["node_id"] == "scene" for row in report.to_dict()["gaps"])


def test_reused_event_ids_keep_their_own_scenario_source_and_trace():
    world = {"claim": {"requested_semantics": ["event"], "asserts": [{"holds": "done", "at": "t3", "scenario": "A"}]},
        "inputs": {"events": [{"event_id": "act", "scenario_id": "A", "at": "t1", "requires": "absent", "initiates": "done", "source": "alternative A"},
            {"event_id": "act", "scenario_id": "B", "at": "t2", "initiates": "done", "source": "alternative B"}]}}
    report = run_worldguard(world)
    step = report.guard_results[0].counterexamples[0]["steps"][0]
    assert step["source"] == "alternative A"
    assert step["trace"] == [{"at": "t1", "event_id": "act"}]
