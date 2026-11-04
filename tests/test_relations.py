"""Possession and place come from declared relations and the replay, never from fluent names or `requires`."""
from copy import deepcopy
import json
from pathlib import Path

import pytest
import yaml

from worldguard import GuardContract
from worldguard.cli import main
from worldguard.kernel import run_worldguard
from worldguard.relations import NOTHING_DECLARED

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


def test_a_conflict_is_found_at_the_events_that_start_the_clashing_facts():
    # At 18:00 Tom grabs the key Lena still holds, and Lena waves at the same time: the grab makes the key's second holder.
    contract = yaml.safe_load((LIGHTHOUSE.parent / "conflict_same_time.yaml").read_text())
    (row,) = _rows(run_worldguard(contract), "WORLD_RELATION_CONFLICT")
    assert (row["event_id"], row["event_ids"], row["at"]) == ("e_grab", ["e_grab"], "18:00")
    # Two events of the same instant start one holder each: both cause the conflict, the wave still does not.
    contract["inputs"]["event_model"]["initial_states"].remove("lena_has_key")
    contract["inputs"]["events"].insert(0, {"event_id": "e_take", "at": "18:00", "actor": "Lena", "place": "mainland",
                                            "uses": [], "initiates": ["lena_has_key"]})
    (row,) = _rows(run_worldguard(contract), "WORLD_RELATION_CONFLICT")
    assert (row["event_id"], row["event_ids"]) == ("e_grab", ["e_take", "e_grab"])


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


def _without_actors(contract):
    for event in contract["inputs"]["events"]:
        for field in ("actor", "with", "place", "uses"):
            event.pop(field, None)
    return contract


def test_a_world_with_relations_needs_every_event_to_name_its_actor():
    # The round-12 review's escape: the declared world, with no event naming anyone, used to pass.
    report = run_worldguard(_without_actors(_load("ch2_declared.yaml")))
    rows = _rows(report, "EVENT_ACTOR_STATE_UNCHECKED")
    assert [(row["event_id"], row["missing"]) for row in rows] == [
        ("e_give_key", ["actor"]), ("e_tom_ferry", ["actor"]), ("e_unlock", ["actor"])]
    assert all("declares who holds what or who is where" in row["message"] for row in rows)
    assert report.status.value == "GAP"


def test_a_world_that_names_no_actor_and_declares_no_relation_says_what_is_not_checked(capsys):
    # w3a with every actor field removed: nothing ties a fact to a person, so nothing can be checked; the report says so.
    contract = _without_actors(_load("w3/w3a_naive.yaml"))
    report = run_worldguard(contract)
    assert ("who holds what and who is where are not checked: no event names an actor and "
            "world_model.relations declares nothing") in report.scope_limits
    assert report.status.value == "PASS"


@pytest.mark.parametrize("ending", ["terminates", "releases"])
def test_an_event_whose_changed_facts_no_relation_ties_to_anything_is_listed(ending):
    # The review's second escape: Lena turns the key on the mainland, using nothing. The door has no declared place,
    # so only Lena's own place can be checked; the report names the event and the facts.
    contract = _load("ch2_declared.yaml")
    unlock = _event(contract, "e_unlock")
    unlock[ending] = unlock.pop("terminates")
    unlock["uses"], unlock["place"] = [], "mainland"
    report = run_worldguard(contract)
    assert report.status.value == "PASS"
    (line,) = [line for line in report.scope_limits if line.startswith("place checked only")]
    assert line == ("place checked only for the people and things an event names: e_unlock (Lena at mainland) changes "
                    "door_locked, door_unlocked, which world_model.relations ties to no one and nothing; declare where "
                    "a thing is ({at: [thing, place]}) and name it in with to check it")
    # Declaring where the door is and naming it catches the wrong place.
    contract["world_model"]["relations"]["door_on_island"] = {"at": ["door", "island"]}
    contract["inputs"]["event_model"]["initial_states"].append("door_on_island")
    unlock["with"] = ["door"]
    report = run_worldguard(contract)
    (row,) = _rows(report, "EVENT_RELATION_UNDECLARED")
    assert (row["event_id"], row["subject"], row["object"]) == ("e_unlock", "door", "mainland")
    assert report.status.value == "GAP"


def test_untimed_events_say_the_relation_replay_did_not_run():
    # A causal-only world (EventGuard not requested) used to drop the relation replay without a word.
    contract = _declared_slip()
    del _event(contract, "e_give_key")["at"]
    contract["claim"] = {"asserts": [{"variable": "x", "op": ">=", "value": 0}]}
    contract["inputs"]["causal_model"] = {"variables": ["x"], "equations": {"x": "1"}, "scenarios": {"base": {}}}
    contract.pop("variants", None)
    report = run_worldguard(contract)
    (row,) = _rows(report, "WORLD_RELATION_CHECK_NOT_RUN")
    assert row["status"] == "GAP" and row["untimed_events"] == ["e_give_key"]
    assert report.status.value != "PASS"


def test_a_null_relations_block_is_an_input_error():
    contract = _load("ch2_fixed.yaml")
    contract["world_model"]["relations"] = None
    with pytest.raises(ValueError, match="must map fluent ids"):
        GuardContract.from_dict(contract)


def _blank_relations(text):
    """The world file with `relations:` left without a value (the block's entries removed)."""
    lines, kept, inside = text.splitlines(), [], False
    for line in lines:
        if line == "  relations:":
            inside = True
            kept.append(line)
            continue
        if inside and line.startswith("    "):
            continue
        inside = False
        kept.append(line)
    return "\n".join(kept) + "\n"


def test_a_blank_relations_block_is_an_input_error_but_an_empty_mapping_declares_nothing():
    """What CHANGELOG says: no value (blank or null) is an input error; `relations: {}` is accepted and declares nothing."""
    blank = yaml.safe_load(_blank_relations((LIGHTHOUSE / "ch2_fixed.yaml").read_text()))
    assert "relations" in blank["world_model"] and blank["world_model"]["relations"] is None
    with pytest.raises(ValueError, match="must map fluent ids"):
        GuardContract.from_dict(blank)
    empty = _load("ch2_fixed.yaml")
    empty["world_model"]["relations"] = {}
    report = run_worldguard(empty)
    assert "EVENT_RELATION_UNDECLARED" in {row["code"] for row in report.gaps} and report.status.value == "GAP"
    for event in empty["inputs"]["events"]:
        for key in ("actor", "with", "place", "uses"):
            event.pop(key, None)
    assert NOTHING_DECLARED in run_worldguard(empty).scope_limits
