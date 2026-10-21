from tests.helpers import make_contract
from worldguard.kernel import run_worldguard


def test_events_roll_out_in_numeric_time_order() -> None:
    contract = make_contract(
        "EventGuard",
        inputs={
            "events": [
                {"event_id": "lock_up", "at": "t9", "initiates": "door_locked"},
                {"event_id": "unlock", "at": "t10", "terminates": "door_locked"},
            ]
        },
    )

    outputs = run_worldguard(contract).semantic_receipts[0].outputs

    assert outputs["final_fluent_ids_by_scenario"]["default"] == []
    assert outputs["observed_timepoints"] == ["t9", "t10"]
