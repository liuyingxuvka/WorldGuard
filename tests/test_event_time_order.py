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

    from worldguard.semantic import event_replay
    contract.claim.asserts.append({"holds": "door_locked", "at": "t10", "value": False})
    report = run_worldguard(contract)
    assert report.status.value == "PASS"
    replay = list(event_replay(contract.inputs["events"]))
    assert replay[-1][2] == frozenset()
    assert [row[0]["at"] for row in replay] == ["t9", "t10"]


import json
from datetime import date, datetime
from pathlib import Path

import pytest

from worldguard.clock import time_key, time_kind, validate_times
from worldguard.cli import main
from worldguard.contracts import GuardContract


@pytest.mark.parametrize("earlier,later,kind", [
    (0, 2.5, "number"),
    ("t-1", "t2.5", "label"),
    ("day2", "day10", "label"),
    ("9:40", "10:20", "clock"),
    ("17:12:29", "17:12:30", "clock"),
    (date(2026, 1, 1), date(2026, 1, 2), "ISO date-time"),
    (datetime(2026, 1, 1, 9), "2026-01-01T10:00", "ISO date-time"),
    ("2026-01-01T10:00+01:00", "2026-01-01T09:30Z", "ISO date-time"),
])
def test_clock_orders_supported_time_kinds(earlier, later, kind):
    validate_times([("first", earlier), ("second", later)])
    assert time_kind(earlier) == kind
    assert time_key(earlier) < time_key(later)


@pytest.mark.parametrize("file,exit_code,status,codes", [
    ("time_hhmm.yaml", 1, "FAIL", {"EVENT_PRECONDITION_UNMET", "CLAIM_ASSERTION_FALSE"}),
    ("trip_mut2_out/hhmm_false_pass.yaml", 1, "FAIL", {"CLAIM_ASSERTION_FALSE"}),
    ("story_mut_out/bad_time.yaml", 2, "error", {"WORLDGUARD_INPUT_INVALID"}),
    ("story_mut_out/mixed_time.yaml", 2, "error", {"WORLDGUARD_INPUT_INVALID"}),
    ("trip_mut2_out/word_time.yaml", 2, "error", {"WORLDGUARD_INPUT_INVALID"}),
    ("trip_mut_out/hhmm.yaml", 2, "error", {"WORLDGUARD_INPUT_INVALID"}),
    ("trip_mut_out/hhmm_padded.yaml", 2, "error", {"WORLDGUARD_INPUT_INVALID"}),
    ("story_mut_out/dup_event_id.yaml", 2, "error", {"WORLDGUARD_INPUT_INVALID"}),
    ("trip_v1.yaml", 0, "PASS", set()),
    ("story_v1.yaml", 0, "PASS", set()),
])
def test_trial_time_contracts_are_checked_natively(file, exit_code, status, codes, capsys):
    path = Path(__file__).parent / "fixtures/trials" / file
    assert main(["check", "--contract", str(path)]) == exit_code
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == status
    def collect(value):
        if isinstance(value, dict):
            return ({value["code"]} if "code" in value else set()).union(*(collect(v) for v in value.values()))
        if isinstance(value, list):
            return set().union(*(collect(v) for v in value))
        return set()
    assert codes <= collect(result)
    if file.endswith("dup_event_id.yaml"):
        assert "e_lamp_lit" in result["error"]["message"]


def _scenario_contract(assertion):
    return GuardContract.from_dict({"claim": {"claim_id": "scoped", "asserts": [assertion]}, "inputs": {"events": [
        {"event_id": "first", "scenario_id": "A", "at": "t1", "initiates": "only_a"},
        {"event_id": "second", "scenario_id": "A", "at": "t2", "initiates": "done"},
        {"event_id": "first", "scenario_id": "B", "at": "t3", "initiates": "other"},
        {"event_id": "second", "scenario_id": "B", "at": "t2", "initiates": "done"},
        {"event_id": "shared", "at": "t0", "initiates": "shared_ready"},
    ]}})


@pytest.mark.parametrize("assertion,status", [
    ({"event": "first", "before": "second", "scenario": "A"}, "PASS"),
    ({"event": "first", "before": "second", "scenario": "B"}, "FAIL"),
    ({"event": "first", "before": "second"}, "GAP"),
    ({"event": "shared", "before": "second", "scenario": "unknown"}, "GAP"),
    ({"holds": "only_a", "at": "t4", "scenario": "A"}, "PASS"),
    ({"holds": "only_a", "at": "t4", "scenario": "B"}, "GAP"),
    ({"holds": "shared_ready", "at": "t4", "scenario": "unknown"}, "GAP"),
])
def test_event_assertions_obey_their_scenario(assertion, status):
    report = run_worldguard(_scenario_contract(assertion))
    assert report.status.value == status
    assert report.claim_binding["status"] == status


def test_unique_event_ids_preserve_unscoped_order_assertions():
    contract = GuardContract.from_dict({"claim": {"claim_id": "unique-events", "asserts": [{"event": "first", "before": "second"}]},
        "inputs": {"events": [
            {"event_id": "first", "scenario_id": "A", "at": 1, "initiates": "ready"},
            {"event_id": "second", "scenario_id": "B", "at": 2, "initiates": "done"},
        ]}})
    assert run_worldguard(contract).status.value == "PASS"


@pytest.mark.parametrize("assertions", [[], [{"holds": "ready", "at": "t2"}], [{"event": "first", "before": "second"}]])
def test_absent_event_time_remains_a_native_gap(assertions):
    contract = GuardContract.from_dict({"claim": {"claim_id": "missing-time", "requested_semantics": ["event"],
        "asserts": assertions}, "inputs": {"events": [
            {"event_id": "first", "initiates": "ready"},
            {"event_id": "second", "at": "t2", "initiates": "done"},
        ]}})
    report = run_worldguard(contract)
    assert report.status.value == "GAP"
    assert report.guard_results[0].status.value == "GAP"
    assert [row["code"] for row in report.guard_results[0].errors] == ["EVENT_MISSING_INITIATION_AXIOM"]
    assert report.claim_binding["status"] == "GAP"
