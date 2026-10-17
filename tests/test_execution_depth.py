"""Native predictive depth regression; no author framework is required."""
from pathlib import Path
from worldguard.execution_depth import build_native_depth_evidence
ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "execution_depth"


def test_deep_fixture_emits_dynamic_target_owned_execution_depth() -> None:
    evidence = build_native_depth_evidence(
        FIXTURES / "deep.json",
        expected_status="EXECUTION_DEPTH_PASS",
    )

    assert evidence["status"] == "EXECUTION_DEPTH_PASS"
    assert evidence["primary_blocker_code"] == "none"
    assert len(evidence["input_sha256"]) == 64
    assert len(evidence["native_receipt_hash"]) == 64
    assert len(evidence["evidence_payload_hash"]) == 64
    coverage = evidence["coverage_universe_results"][0]
    assert coverage["validated_count"] == coverage["eligible_count"]
    assert all(row["validated_count"] == 1 for row in coverage["per_object_results"])
    assert "depth_contribution_ranges" not in evidence
    assert evidence["native_obligation_evidence"] == evidence["native_receipt"][
        "native_obligation_evidence"
    ]
    assert all(
        row["target_obligation_ids"]
        and row["evidence_ref"].startswith("worldguard:")
        and len(row["evidence_sha256"]) == 64
        for row in evidence["native_obligation_evidence"]
    )


def test_thousand_step_two_point_fixture_is_shallow_blocked() -> None:
    evidence = build_native_depth_evidence(
        FIXTURES / "shallow.json",
        expected_status="SHALLOW_BLOCKED",
        expected_blocker_code="time_horizon_depth_incomplete",
    )

    assert evidence["status"] == "SHALLOW_BLOCKED"
    assert evidence["native_receipt"]["predictive_claim_licensed"] is False
    assert evidence["primary_blocker_code"] == "time_horizon_depth_incomplete"
    time_depth = next(
        row
        for row in evidence["coverage_universe_results"][0]["per_object_results"]
        if row["object_id"] == "worldguard:time-scenario-holdout"
    )
    assert time_depth["validated_count"] == 0


def test_enough_points_without_middle_phase_are_shallow_blocked() -> None:
    evidence = build_native_depth_evidence(
        FIXTURES / "concentrated.json",
        expected_status="SHALLOW_BLOCKED",
        expected_blocker_code="time_horizon_depth_incomplete",
    )

    gaps = evidence["native_receipt"]["predictive_gaps"]
    assert "predictive_time_stratum_uncovered:middle" in gaps
    assert not any(gap.startswith("predictive_timepoint_sample_floor_not_met") for gap in gaps)


def test_native_receipt_and_input_hashes_change_with_fixture() -> None:
    deep = build_native_depth_evidence(FIXTURES / "deep.json")
    shallow = build_native_depth_evidence(FIXTURES / "shallow.json")

    assert deep["input_sha256"] != shallow["input_sha256"]
    assert deep["native_receipt_hash"] != shallow["native_receipt_hash"]
    assert (
        deep["coverage_universe_results"][0]["universe_fingerprint"]
        != shallow["coverage_universe_results"][0]["universe_fingerprint"]
    )

