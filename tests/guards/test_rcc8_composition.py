from pathlib import Path

import yaml

from worldguard.guards.space_guard import _RCC8, _RCC8_CONVERSE, _RCC8_COMPOSITION
from worldguard.kernel import run_worldguard


def test_full_rcc8_table_preserves_converse_and_identity_for_all_64_entries():
    assert len(_RCC8_COMPOSITION) == 64
    for left in _RCC8:
        for right in _RCC8:
            allowed = _RCC8_COMPOSITION[left, right]
            assert allowed and allowed <= _RCC8
            assert {_RCC8_CONVERSE[value] for value in allowed} == _RCC8_COMPOSITION[_RCC8_CONVERSE[right], _RCC8_CONVERSE[left]]
        assert _RCC8_COMPOSITION["EQ", left] == _RCC8_COMPOSITION[left, "EQ"] == {left}
    assert _RCC8_COMPOSITION["NTPP", "DC"] == {"DC"}
    assert _RCC8_COMPOSITION["EC", "NTPP"] == {"PO", "TPP", "NTPP"}


def test_declared_rcc8_triplet_fails_including_converse_only_paths():
    path = Path(__file__).parents[1] / "fixtures/trials/story_mut_out/rcc_other_comp.yaml"
    world = yaml.safe_load(path.read_text())
    report = run_worldguard(world)
    assert report.status.value == "FAIL"
    space = next(result for result in report.guard_results if result.guard == "SpaceGuard")
    assert space.errors[0]["code"] == "SPACE_RCC8_CONTRADICTION"
    steps = space.counterexamples[0]["steps"]
    assert any(set(step["chain"]) == {"logbook", "lamp_room", "cellar"} and "allowed" in step for step in steps)
    for relation in world["inputs"]["spatial_relations"]:
        relation["x"], relation["y"] = relation["y"], relation["x"]
        relation["relation"] = _RCC8_CONVERSE[relation["relation"]]
    assert run_worldguard(world).status.value == "FAIL"


def test_rcc8_does_not_infer_an_undeclared_third_relation():
    world = {"claim": {"asserts": [{"relation": "NTPP", "x": "a", "y": "b", "at": "t1"}]},
        "inputs": {"spatial_relations": [{"at": "t1", "x": "a", "y": "b", "relation": "NTPP"},
            {"at": "t1", "x": "b", "y": "c", "relation": "DC"}]}}
    assert run_worldguard(world).status.value == "PASS"
    assert len(world["inputs"]["spatial_relations"]) == 2
