"""One route per check: an error is reported where it happens, never swallowed into a quieter result."""
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from worldguard import GuardContract
from worldguard.cli import main
from worldguard.kernel import run_worldguard

ROOT = Path(__file__).resolve().parents[1]


def _token_world():
    """A traveler token that ends in `other` while the fluent says `out`: WORLD_EVENT_TOKEN_MISMATCH."""
    return {"claim": {"requested_semantics": ["event"], "asserts": [{"holds": "out", "at": "t2"}]},
            "inputs": {"event_model": {"initial_states": ["start"]},
                       "events": [{"event_id": "move", "at": "t1", "requires": "start", "initiates": "out", "terminates": "start"}],
                       "resources": {"places": {"start": [{"color": "traveler", "qty": 1}], "out": [], "other": []},
                                     "transitions": [{"id": "move", "event": "move",
                                                      "consumes": [{"place": "start", "color": "traveler", "qty": 1}],
                                                      "produces": [{"place": "other", "color": "traveler", "qty": 1}]}]}}}


def _space_world():
    """The single traveler token sits in `out` while a same-time row puts it in `home`, declared apart from `out`."""
    world = _token_world()
    world["claim"]["requested_semantics"] = ["event", "resource", "spatial"]
    transition = world["inputs"]["resources"]["transitions"][0]
    transition["produces"][0]["place"] = "out"
    world["inputs"]["events"][0]["actor"] = "traveler"
    world["inputs"]["events"][0]["actor_state_free"] = "a token moves; nobody holds or uses anything"
    world["inputs"]["resources"]["unique"] = ["traveler"]
    world["inputs"]["spatial_relations"] = [{"at": "t2", "x": "traveler", "y": "home", "relation": "NTPP"},
                                            {"at": "t2", "x": "home", "y": "out", "relation": "DC"}]
    return world


def test_space_token_mismatch_is_found_before_any_edit():
    report = run_worldguard(_space_world())
    assert report.status.value == "FAIL"
    assert "WORLD_SPACE_TOKEN_MISMATCH" in {row["code"] for row in report.gaps}


def test_an_unrelated_spatial_row_with_a_bad_time_is_an_input_error_not_a_hidden_check(tmp_path):
    world = _space_world()
    world["inputs"]["spatial_relations"].append({"at": "evening", "x": "lamp", "y": "tower", "relation": "NTPP"})
    with pytest.raises(ValueError, match=r"inputs\.spatial_relations\[2\].*evening"):
        GuardContract.from_dict(world)
    path = tmp_path / "world.yaml"
    path.write_text(yaml.safe_dump(world))
    assert main(["check", "--contract", str(path)]) == 2


def test_a_timeless_spatial_row_keeps_the_same_time_check():
    world = _space_world()
    world["inputs"]["spatial_relations"].append({"x": "lamp", "y": "tower", "relation": "NTPP"})
    report = run_worldguard(world)
    assert report.status.value == "FAIL"
    assert "WORLD_SPACE_TOKEN_MISMATCH" in {row["code"] for row in report.gaps}


def test_a_malformed_event_beside_good_ones_is_the_typed_gap_not_a_crash():
    world = _token_world()
    world["inputs"]["events"].append("e_unlock at t0")
    report = run_worldguard(world)
    assert {"EVENT_MISSING_INITIATION_AXIOM", "WORLD_EVENT_TOKEN_MISMATCH"} <= {row["code"] for row in report.gaps}


def test_a_spatial_row_that_is_not_a_mapping_is_the_typed_space_gap():
    world = _space_world()
    world["inputs"]["spatial_relations"].append("cat at mat")
    report = run_worldguard(world)
    assert {"SPACE_UNEVALUABLE_RCC8", "WORLD_SPACE_TOKEN_MISMATCH"} <= {row["code"] for row in report.gaps}


def test_an_unrelated_broken_token_does_not_hide_the_event_token_check():
    assert {row["code"] for row in run_worldguard(_token_world()).gaps} == {"WORLD_EVENT_TOKEN_MISMATCH"}
    world = _token_world()
    world["inputs"]["resources"]["places"]["spare"] = [{"color": "coin", "qty": -1}]
    report = run_worldguard(world)
    assert report.status.value == "GAP"
    (row,) = [row for row in report.gaps if row["code"] == "WORLD_TOKEN_CHECK_NOT_RUN"]
    assert row["check"] == "event_token" and row["problem"]["kind"] == "bad_token"


def test_a_broken_space_replay_is_reported_not_skipped():
    world = _space_world()
    world["inputs"]["resources"]["places"]["spare"] = [{"color": "coin", "qty": -1}]
    report = run_worldguard(world)
    checks = {row["check"] for row in report.gaps if row["code"] == "WORLD_TOKEN_CHECK_NOT_RUN"}
    assert checks == {"event_token", "space_token"}


def test_an_injected_evaluator_bug_fails_instead_of_becoming_a_gap(monkeypatch):
    from worldguard import claim_binding

    def broken(inputs, row):
        raise KeyError("injected")

    monkeypatch.setitem(claim_binding._EVALUATORS, "holds", broken)
    with pytest.raises(KeyError, match="injected"):
        run_worldguard(_token_world())


@pytest.mark.parametrize("row,inputs,reason", [
    ({"player": "a", "state": "s", "reward": 1},
     {"game_model": {"players": ["a"], "actions": {"a": ["hold"]}, "states": ["s"],
                     "transitions": [{"from": "s", "to": "s", "probabilities": [1.0]}],
                     "payoffs": [{"state": "s", "reward": {"a": "lots"}}]}},
     "the declared payoff of 'a' in state 's' is not a number: 'lots'"),
    ({"place": "p", "qty": "two"}, {"resources": {"places": {"p": [{"color": "c", "qty": 1}]}}},
     "a place assertion needs a numeric qty, not 'two'"),
    ({"agent": "a", "believes": "x"}, {"beliefs": {"a": {"beliefs": 3, "desires": ["d"], "intentions": []}}},
     "agent 'a' beliefs must be a list"),
])
def test_a_bad_value_in_a_claim_row_or_model_is_a_named_gap(row, inputs, reason):
    """The evaluators check the values they read; the reason names the value, not a Python error."""
    report = run_worldguard({"claim": {"asserts": [row]}, "inputs": inputs})
    (gap,) = [gap for gap in report.gaps if gap["code"] == "CLAIM_ASSERTION_UNRESOLVED"]
    assert gap["reason"] == reason


ASSERTION_ROWS = {
    "holds": {"holds": "out", "at": "t2"}, "before": {"event": "move", "before": "move"},
    "place": {"place": "start", "qty": 1}, "variable": {"variable": "x", "op": ">=", "value": 0},
    "agent": {"agent": "a", "believes": "b"}, "relation": {"relation": "NTPP", "x": "a", "y": "b", "at": "t1"},
    "modality": {"actor": "a", "action": "b", "modality": "permitted"}, "player": {"player": "a", "state": "s", "reward": 1},
}
FAULTS = [KeyError, TypeError, ValueError, AttributeError, IndexError, RuntimeError, ZeroDivisionError]


@pytest.mark.parametrize("kind", sorted(ASSERTION_ROWS))
@pytest.mark.parametrize("fault", FAULTS, ids=lambda fault: fault.__name__)
def test_an_injected_evaluator_error_of_any_type_is_raised(monkeypatch, kind, fault):
    """No error inside an evaluator becomes a GAP, a PASS or a skip: it reaches the caller."""
    from worldguard import claim_binding

    def broken(inputs, row):
        raise fault("injected")

    monkeypatch.setitem(claim_binding._EVALUATORS, kind, broken)
    world = _token_world()
    world["claim"]["asserts"] = [ASSERTION_ROWS[kind]]
    with pytest.raises(fault, match="injected"):
        run_worldguard(world)


def _write(tmp_path, world, name="world.yaml"):
    path = tmp_path / name
    path.write_text(yaml.safe_dump(world))
    return path


@pytest.mark.parametrize("command", ["check", "timeline", "lifeline", "mesh-check"])
@pytest.mark.parametrize("fault", [ValueError, TypeError, KeyError], ids=lambda fault: fault.__name__)
def test_an_internal_error_in_a_check_is_raised_not_called_an_input_error(monkeypatch, tmp_path, capsys, command, fault):
    from worldguard import qualification

    def broken(*args, **kwargs):
        raise fault("injected internal failure")

    monkeypatch.setattr(qualification, "actor_relation_rows", broken)
    world = deepcopy(_token_world())
    world["inputs"]["events"][0]["actor"] = "traveler"
    path = _write(tmp_path, world)
    if command == "mesh-check":
        args = ["mesh-check", "--mesh", str(_write(tmp_path, {"mesh_id": "m", "nodes": [{"model_id": "n", "contract": "world.yaml"}]},
                                                    "tree.yaml"))]
    else:
        args = [command, "--contract", str(path)] + (["--of", "traveler"] if command == "lifeline" else [])
    with pytest.raises(fault, match="injected internal failure"):
        main(args)
    assert "WORLDGUARD_INPUT_INVALID" not in capsys.readouterr().out


@pytest.mark.parametrize("module,name", [("worldguard.lifeline", "lifeline"), ("worldguard.timeline", "timeline"),
                                         ("worldguard.compare", "compare_world")])
def test_an_internal_value_error_in_a_view_is_raised(monkeypatch, tmp_path, module, name):
    import importlib

    def broken(*args, **kwargs):
        raise ValueError("injected view failure")

    monkeypatch.setattr(importlib.import_module(module), name, broken)
    path = _write(tmp_path, _token_world())
    args = {"lifeline": ["lifeline", "--contract", str(path), "--of", "traveler"],
            "timeline": ["timeline", "--contract", str(path)],
            "compare_world": ["compare", "--contract", str(path), "--observed", str(_write(tmp_path, {"events": {}}, "seen.yaml"))]}[name]
    with pytest.raises(ValueError, match="injected view failure"):
        main(args)


@pytest.mark.parametrize("text,needle", [("{not json", "is not valid JSON"), ("[1, 2]", "did not contain a mapping")])
def test_an_unreadable_world_is_still_an_input_error(tmp_path, capsys, text, needle):
    path = tmp_path / "world.json"
    path.write_text(text)
    assert main(["check", "--contract", str(path)]) == 2
    error = json.loads(capsys.readouterr().out)["error"]
    assert error["code"] == "WORLDGUARD_INPUT_INVALID" and needle in error["message"]


def _trace_only_world():
    """A failed precondition and no tokens: only the counterexample trace reads the timeline."""
    return {"claim": {"requested_semantics": ["event"], "asserts": [{"holds": "out", "at": "t2"}]},
            "inputs": {"event_model": {"initial_states": ["start"]},
                       "events": [{"event_id": "move", "at": "t1", "requires": "never", "initiates": "out"}]}}


def _space_only_world():
    """Fluent names differ from place names: only the space/token check reads the timeline."""
    world = _space_world()
    world["claim"]["asserts"] = [{"holds": "at_out", "at": "t2"}]
    world["inputs"]["event_model"]["initial_states"] = ["at_start"]
    world["inputs"]["events"][0].update(requires="at_start", initiates="at_out", terminates="at_start")
    return world


@pytest.mark.parametrize("world,code", [(_trace_only_world, "EVENT_PRECONDITION_UNMET"),
                                        (_space_only_world, "WORLD_SPACE_TOKEN_MISMATCH")])
def test_an_injected_timeline_error_propagates(monkeypatch, world, code):
    from worldguard import qualification

    assert code in {row["code"] for row in run_worldguard(world()).gaps}

    def broken(*args, **kwargs):
        raise ValueError("injected timeline failure")

    monkeypatch.setattr(qualification, "timeline", broken)
    with pytest.raises(ValueError, match="injected timeline failure"):
        run_worldguard(world())


def test_a_missing_equation_is_not_called_an_unresolved_dependency():
    from worldguard.semantic import _evaluate_equations

    with pytest.raises(KeyError):
        _evaluate_equations(["x"], {}, {})
    values, errors = _evaluate_equations(["y", "x"], {"x": "1", "y": "x + 1"}, {})
    assert (values["y"], errors) == (2.0, [])


def test_the_module_entry_point_shows_a_crash_as_a_crash():
    code = ("import runpy, worldguard.cli as cli\n"
            "def broken(argv=None):\n    raise ZeroDivisionError('injected')\n"
            "cli.main = broken\n"
            "runpy.run_module('worldguard', run_name='__main__')\n")
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, text=True, capture_output=True)
    assert result.returncode == 1
    assert result.stdout == ""
    assert "ZeroDivisionError: injected" in result.stderr


def test_a_closed_reader_is_reported_once_and_not_as_an_input_error():
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        result = subprocess.run([sys.executable, "-m", "worldguard", "timeline", "--example", "story"],
                                cwd=ROOT, stdout=write_end, stderr=subprocess.PIPE, text=True)
    finally:
        os.close(write_end)
    assert result.returncode == 141
    assert "WORLDGUARD_INPUT_INVALID" not in result.stderr and "Traceback" not in result.stderr
    assert result.stderr.strip() == "worldguard: the reader closed the output early (broken pipe); the output is incomplete"
