"""Possession and place come from declared relations and the replay, never from fluent names or `requires`."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from worldguard import GuardContract
from worldguard.cli import main
from worldguard.kernel import run_worldguard

LIGHTHOUSE = Path(__file__).parent / "fixtures/trials/lighthouse_key"


def _load(name):
    return yaml.safe_load((LIGHTHOUSE / name).read_text())


def _event(contract, event_id):
    return next(row for row in contract["inputs"]["events"] if row["event_id"] == event_id)


def _rows(report, code):
    return [row for row in report.gaps if row["code"] == code]


def _declared(name):
    """A declared chapter whose events list no declared relation in `requires`: place and uses carry them."""
    contract = _load(name)
    relations = contract["world_model"]["relations"]
    for event in contract["inputs"]["events"]:
        event["requires"] = [fluent for fluent in event.get("requires", []) if fluent not in relations]
    for variant in contract.get("variants", []):
        if variant.get("code") == "EVENT_PRECONDITION_UNMET":
            variant["code"] = "EVENT_RELATION_UNMET"  # the derived check now catches the handover slip
    return contract


def _declared_slip():
    """The round-11 mistake in a declared world: Lena turns the key at the lighthouse at 21:00."""
    contract = _declared("ch2_fixed.yaml")
    _event(contract, "e_unlock")["actor"] = "Lena"
    return contract


@pytest.mark.parametrize("name", ["w3c_partial_require.yaml", "w3d_camel.yaml", "w3e_initials.yaml", "w3f_no_actor.yaml"])
def test_the_round12_cheap_variants_are_caught_on_the_unlock(name):
    report = run_worldguard(_load(f"w3/{name}"))
    assert report.status.value == "GAP"
    (row,) = [row for row in _rows(report, "EVENT_ACTOR_STATE_UNCHECKED") if row["event_id"] == "e_unlock"]
    assert row["missing"] == (["actor"] if name == "w3f_no_actor.yaml" else ["place", "uses"])
    assert row["source"] == "ch2 p3"


def test_a_stated_exemption_still_works_and_its_reason_is_shown(tmp_path, capsys):
    path = LIGHTHOUSE / "w3/w3b_free_reason.yaml"
    report = run_worldguard(_load("w3/w3b_free_reason.yaml"))
    assert not [row for row in report.gaps if row.get("event_id") == "e_unlock"]
    reason = "actor_state_free e_unlock (Lena): turning the key is all that is needed"
    assert reason in report.scope_limits
    main(["check", "--contract", str(path)])
    assert reason in json.loads(capsys.readouterr().out)["scope_limits"]
    main(["timeline", "--contract", str(path)])
    unlock_line = next(line for line in capsys.readouterr().out.splitlines() if "  e_unlock  " in line)
    assert unlock_line.endswith("~ actor_state_free: turning the key is all that is needed")


def test_a_declared_world_catches_the_slip_without_any_requires():
    report = run_worldguard(_declared_slip())
    assert report.status.value == "FAIL"
    rows = _rows(report, "EVENT_RELATION_UNMET")
    assert [(row["event_id"], row["relation"], row["subject"], row["object"], row["found"], row["message"]) for row in rows] == [
        ("e_unlock", "at", "Lena", "island", ["mainland"], "Lena is not at island at 21:00 (at mainland)."),
        ("e_unlock", "holds", "Lena", "key", ["Tom"], "Lena does not hold key at 21:00 (held by Tom)."),
    ]
    assert all(row["source"] == "ch2 p3" for row in rows)


def test_requires_play_no_part():
    contract = _declared_slip()
    _event(contract, "e_unlock")["requires"] = ["door_locked", "lena_on_mainland"]  # w3c's partial guess
    report = run_worldguard(contract)
    assert report.status.value == "FAIL"
    assert {(row["relation"], row["object"]) for row in _rows(report, "EVENT_RELATION_UNMET")} == {("at", "island"), ("holds", "key")}


@pytest.mark.parametrize("rename", [
    {"lena_has_key": "key_held_by_L", "tom_has_key": "key_held_by_T", "lena_on_mainland": "L_on_mainland",
     "lena_on_island": "L_on_island", "tom_on_mainland": "T_on_mainland", "tom_on_island": "T_on_island"},
    {"lena_has_key": "LenaHasKey", "tom_has_key": "TomHasKey", "lena_on_mainland": "LenaOnMainland",
     "lena_on_island": "LenaOnIsland", "tom_on_mainland": "TomOnMainland", "tom_on_island": "TomOnIsland"},
])
def test_fluent_spelling_does_not_change_the_verdict(rename):
    text = json.dumps(_declared_slip())
    for old, new in rename.items():
        text = text.replace(f'"{old}"', f'"{new}"')
    report = run_worldguard(json.loads(text))
    assert report.status.value == "FAIL"
    assert [(row["relation"], row["object"], row["found"], row["fluent"]) for row in _rows(report, "EVENT_RELATION_UNMET")] == [
        ("at", "island", ["mainland"], rename["lena_on_island"]), ("holds", "key", ["Tom"], rename["lena_has_key"])]


def test_the_fixed_world_passes_and_moving_the_handover_fails():
    assert run_worldguard(_declared("ch2_fixed.yaml")).status.value == "PASS"
    early = _declared("ch2_fixed.yaml")
    _event(early, "e_unlock")["at"] = "17:00"
    report = run_worldguard(early)
    assert {(row["subject"], row["relation"], row["object"]) for row in _rows(report, "EVENT_RELATION_UNMET")} == {
        ("Tom", "holds", "key"), ("Tom", "at", "island")}


def test_every_participant_must_be_at_the_place():
    contract = _declared("ch2_fixed.yaml")
    initial = contract["inputs"]["event_model"]["initial_states"]
    initial[initial.index("tom_on_mainland")] = "tom_on_island"
    report = run_worldguard(contract)
    rows = [(row["event_id"], row["subject"], row["object"], row["found"]) for row in _rows(report, "EVENT_RELATION_UNMET")]
    assert ("e_give_key", "Tom", "mainland", ["island"]) in rows
    assert report.status.value == "FAIL"


def test_a_used_thing_without_a_declared_holder_is_a_gap():
    contract = _load("ch2_fixed.yaml")
    _event(contract, "e_unlock")["uses"] = ["key", "lamp"]
    report = run_worldguard(contract)
    (row,) = _rows(report, "EVENT_RELATION_UNDECLARED")
    assert (row["event_id"], row["relation"], row["subject"], row["object"]) == ("e_unlock", "holds", "Tom", "lamp")
    assert report.status.value == "GAP"


def test_two_places_at_once_names_the_facts_that_established_them():
    contract = _load("ch1_fixed.yaml")
    _event(contract, "e_ferry_out")["terminates"] = []  # Lena reaches the mainland but never leaves the island
    report = run_worldguard(contract)
    (row,) = _rows(report, "WORLD_RELATION_CONFLICT")
    assert (row["subject"], row["fluents"], row["event_id"], row["at"]) == (
        "Lena", ["lena_on_island", "lena_on_mainland"], "e_ferry_out", "14:00")
    assert row["established_by"] == {"lena_on_island": {"event_id": None, "at": None},
                                     "lena_on_mainland": {"event_id": "e_ferry_out", "at": "14:00", "source": "ch1 p3"}}
    assert report.status.value == "FAIL"


def test_a_fact_already_in_requires_is_reported_once():
    contract = _declared_slip()
    _event(contract, "e_unlock")["requires"] = ["lena_has_key", "lena_on_island", "door_locked"]
    report = run_worldguard(contract)
    (native,) = _rows(report, "EVENT_PRECONDITION_UNMET")
    assert native["counterexample"]["missing_fluents"] == ["lena_has_key", "lena_on_island"]
    assert not _rows(report, "EVENT_RELATION_UNMET")
    # Without EventGuard nothing reads `requires`, so the derived check reports the same facts.
    contract["claim"] = {"asserts": [{"variable": "x", "op": ">=", "value": 0}]}
    contract["inputs"]["causal_model"] = {"variables": ["x"], "equations": {"x": "1"}, "scenarios": {"base": {}}}
    contract.pop("variants", None)
    report = run_worldguard(contract)
    assert {row["fluent"] for row in _rows(report, "EVENT_RELATION_UNMET")} == {"lena_has_key", "lena_on_island"}


@pytest.mark.parametrize("relations,message", [
    ({"lena_has_key": {"owns": ["Lena", "key"]}}, "must be {holds"),
    ({"lena_has_key": {"holds": ["Lena"]}}, "must name two ids"),
    ({"lena_has_key": {"holds": ["Lena", "key"]}, "lena_key": {"holds": ["Lena", "key"]}}, "repeats holds Lena key"),
    (["lena_has_key"], "must map fluent ids"),
])
def test_relation_declarations_are_validated(relations, message):
    contract = _load("ch2_fixed.yaml")
    contract["world_model"]["relations"] = relations
    with pytest.raises(ValueError, match=message):
        GuardContract.from_dict(contract)


@pytest.mark.parametrize("field,value,message", [
    ("place", "", "place must be a nonempty place id"),
    ("uses", [""], "uses must be a thing id or a list"),
])
def test_event_place_and_uses_are_validated(field, value, message):
    contract = _load("ch2_fixed.yaml")
    _event(contract, "e_unlock")[field] = value
    with pytest.raises(ValueError, match=message):
        GuardContract.from_dict(contract)
    contract = _load("ch2_fixed.yaml")
    del _event(contract, "e_unlock")["actor"]
    with pytest.raises(ValueError, match="names place or uses but no actor"):
        GuardContract.from_dict(contract)
