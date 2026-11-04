"""A past conflict uses the facts' origins at that instant, including in saved records."""
import json

import pytest

from worldguard.cli import main
from worldguard.kernel import run_worldguard
from worldguard.relations import parse_relations, relation_conflicts


def _world(kind="at", *, initially_conflicting=False):
    relations = ({"spot_A": {"at": ["Lena", "A"]}, "spot_B": {"at": ["Lena", "B"]}} if kind == "at" else
                 {"spot_A": {"holds": ["Lena", "key"]}, "spot_B": {"holds": ["Tom", "key"]}})
    initial = ["spot_A", "spot_B"] if initially_conflicting else ["spot_A"]
    events = [] if initially_conflicting else [
        {"event_id": "cause", "at": 1, "initiates": ["spot_B"], "source": "first source",
         "actor_state_free": "the declared change happens automatically"},
        {"event_id": "neighbor", "at": 1, "initiates": ["unrelated"], "source": "neighbor source",
         "actor_state_free": "a separate clock tick"},
    ]
    events.extend([
        {"event_id": "end_B", "at": 2, "terminates": ["spot_B"],
         "actor_state_free": "the declared fact ends automatically"},
        {"event_id": "future_B", "at": 3, "initiates": ["spot_B"], "source": "future source",
         "actor_state_free": "the declared fact is established again"},
        {"event_id": "end_A", "at": 4, "releases": ["spot_A"],
         "actor_state_free": "the other fact ends automatically"},
        {"event_id": "future_A", "at": 5, "initiates": ["spot_A"], "source": "later source",
         "actor_state_free": "the other fact is established again"},
    ])
    return {
        "contract_id": "historical-origins",
        "claim": {"claim_id": "truth", "requested_semantics": ["event"],
                  "asserts": [{"holds": "spot_B", "at": 6}]},
        "world_model": {"model_id": "historical-origins", "relations": relations},
        "inputs": {"event_model": {"initial_states": initial}, "events": events},
    }


@pytest.mark.parametrize("kind", ["at", "holds"])
@pytest.mark.parametrize("initially_conflicting", [False, True])
def test_conflict_uses_origins_at_its_own_instant(kind, initially_conflicting):
    world = _world(kind, initially_conflicting=initially_conflicting)
    row, = relation_conflicts(world["inputs"], parse_relations(world["world_model"]["relations"]))
    expected = {"event_id": None, "at": None} if initially_conflicting else {
        "event_id": "cause", "at": 1, "source": "first source"}
    assert (row["at"], row["event_id"]) == ((None, None) if initially_conflicting else (1, "cause"))
    assert row["established_by"] == {"spot_A": {"event_id": None, "at": None}, "spot_B": expected}
    if not initially_conflicting:
        assert row["event_ids"] == ["cause"]


def test_different_conflict_groups_keep_their_separate_earliest_origins():
    world = _world()
    world["world_model"]["relations"].update(
        key_A={"holds": ["Lena", "key"]}, key_B={"holds": ["Tom", "key"]})
    world["inputs"]["event_model"]["initial_states"].append("key_A")
    world["inputs"]["events"].extend([
        {"event_id": "key_cause", "at": 2, "initiates": ["key_B"], "source": "key first source"},
        {"event_id": "key_end", "at": 4, "terminates": ["key_B"]},
        {"event_id": "key_future", "at": 6, "initiates": ["key_B"], "source": "key future source"},
    ])
    rows = relation_conflicts(world["inputs"], parse_relations(world["world_model"]["relations"]))
    assert len(rows) == 2
    assert {row["relation"]: row["established_by"] for row in rows} == {
        "at": {"spot_A": {"event_id": None, "at": None},
               "spot_B": {"event_id": "cause", "at": 1, "source": "first source"}},
        "holds": {"key_A": {"event_id": None, "at": None},
                  "key_B": {"event_id": "key_cause", "at": 2, "source": "key first source"}},
    }


def test_cli_and_saved_conflict_keep_the_historical_source(tmp_path, capsys):
    world = _world()
    row, = [row for row in run_worldguard(world).gaps if row["code"] == "WORLD_RELATION_CONFLICT"]
    assert row["established_by"]["spot_B"] == {"event_id": "cause", "at": 1, "source": "first source"}
    path = tmp_path / "world.json"
    path.write_text(json.dumps(world))
    assert main(["check", "--contract", str(path), "--json"]) == 1
    captured = capsys.readouterr()
    assert "first source" in captured.err and "future source" not in captured.err
    record = json.loads((tmp_path / ".worldguard/open.json").read_text())
    saved, = [item for item in record["open"] if item["code"] == "WORLD_RELATION_CONFLICT"]
    assert any(origin.get("event_id") == "cause" for origin in saved["established_by"])
    assert not any(origin.get("event_id") in {"future_B", "future_A"} for origin in saved["established_by"])
    # A record written before the provenance fix can already contain the later event. Re-checking the same
    # contradiction refreshes its current explanation, while preserving when it was first seen and its run count.
    original_first_seen, original_runs = saved["first_seen"], saved["runs"]
    for origin in saved["established_by"]:
        if origin.get("event_id") == "cause":
            origin.update(event_id="future_B", source="future source", where="future source (future_B)")
    (tmp_path / ".worldguard/open.json").write_text(json.dumps(record))
    assert main(["check", "--contract", str(path), "--json"]) == 1
    captured = capsys.readouterr()
    assert "first source" in captured.err and "future source" not in captured.err
    refreshed, = json.loads((tmp_path / ".worldguard/open.json").read_text())["open"]
    assert refreshed["first_seen"] == original_first_seen and refreshed["runs"] == original_runs + 1
    assert any(origin.get("event_id") == "cause" for origin in refreshed["established_by"])
