from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

from worldguard import __version__ as WORLDGUARD_VERSION
from worldguard.execution_depth import (
    UNIVERSE_CLAIM_SCOPE,
    UNIVERSE_NATIVE_POLICY,
    UNIVERSE_PREDICTIVE_AXES,
    UNIVERSE_SCENARIO_PORTFOLIO,
    UNIVERSE_SEMANTIC_CHILDREN,
    UNIVERSE_TIMEPOINTS,
    build_dynamic_depth_universes,
    build_native_depth_evidence,
    build_target_native_depth_envelope,
)


ROOT = Path(__file__).resolve().parents[1]


def _release_gate_binding() -> dict:
    return {
        "schema_version": "worldguard.release_gate_binding.v1",
        "target_skill_id": "worldguard",
        "release_version": "0.7.5",
        "gate_id": "skillguard-final-validation",
        "execution_owner_id": "owner:worldguard:native-depth",
    }


def _capability_evidence_context(case_id: str) -> dict:
    return {
        "domain": "capability_validation",
        "identity": {"validation_case_id": case_id},
    }


FIXTURES = ROOT / "tests" / "fixtures" / "skillguard_depth"
POLICY_FINGERPRINTS = {
    universe_id: "A" * 64
    for universe_id in (
        UNIVERSE_SEMANTIC_CHILDREN,
        UNIVERSE_TIMEPOINTS,
        UNIVERSE_SCENARIO_PORTFOLIO,
        UNIVERSE_PREDICTIVE_AXES,
        UNIVERSE_NATIVE_POLICY,
        UNIVERSE_CLAIM_SCOPE,
    )
}


def test_author_release_gate_fixture_tracks_current_worldguard_version() -> None:
    payload = json.loads(
        (ROOT / "skills" / "worldguard" / ".skillguard" / "fixtures" / "deep.json")
        .read_text(encoding="utf-8")
    )

    assert payload["release_gate_binding"]["release_version"] == WORLDGUARD_VERSION


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


def _dynamic_universe(name: str, universe_id: str) -> dict[str, object]:
    _, universes = build_dynamic_depth_universes(
        FIXTURES / name,
        policy_fingerprints=POLICY_FINGERPRINTS,
    )
    return next(row for row in universes if row["universe_id"] == universe_id)


def test_dynamic_time_universe_counts_all_thousand_steps() -> None:
    deep = _dynamic_universe("deep.json", UNIVERSE_TIMEPOINTS)
    shallow = _dynamic_universe("shallow.json", UNIVERSE_TIMEPOINTS)

    assert len(deep["inventory_items"]) == 2000
    assert len(deep["validated_item_ids"]) == 64
    assert len(shallow["inventory_items"]) == 2000
    assert len(shallow["validated_item_ids"]) == 4
    assert {
        item["object_class_id"] for item in deep["inventory_items"]
    } == {"predictive_horizon", "predictive_variable_or_signal"}
    assert shallow["covered_claim_scope"] == ["predictive_time_horizon:incomplete"]


def test_dynamic_time_universe_cannot_relabel_early_points_as_middle() -> None:
    concentrated = _dynamic_universe("concentrated.json", UNIVERSE_TIMEPOINTS)
    by_id = {item["item_id"]: item for item in concentrated["inventory_items"]}
    selected_phases = {
        phase
        for item_id in concentrated["validated_item_ids"]
        for phase in by_id[item_id]["stratum_ids"]
    }

    assert len(concentrated["validated_item_ids"]) == 64
    assert "middle" not in selected_phases
    assert concentrated["covered_claim_scope"] == [
        "predictive_time_horizon:incomplete"
    ]


def test_shallow_dynamic_bridge_never_invents_transport_health_evidence() -> None:
    _, universes = build_dynamic_depth_universes(
        FIXTURES / "shallow.json",
        policy_fingerprints=POLICY_FINGERPRINTS,
    )
    assert not any(
        "bridge-health" in str(item.get("item_id", ""))
        for universe in universes
        for item in universe["inventory_items"]
    )
    incomplete = [
        universe
        for universe in universes
        if any(str(scope).endswith(":incomplete") for scope in universe["covered_claim_scope"])
    ]
    assert incomplete
    assert any(not universe["validated_item_ids"] for universe in incomplete)


def test_dynamic_axis_inventory_uses_real_native_object_classes() -> None:
    axes = _dynamic_universe("deep.json", UNIVERSE_PREDICTIVE_AXES)
    classes = {item["object_class_id"] for item in axes["inventory_items"]}

    assert {
        "state_axis_disposition",
        "transition_axis_disposition",
        "event_axis",
        "fluent_axis",
        "intervention_axis",
    } <= classes
    not_applicable = [
        item
        for item in axes["inventory_items"]
        if item.get("disposition") == "not_applicable"
    ]
    assert {item["object_class_id"] for item in not_applicable} == {
        "state_axis_disposition",
        "transition_axis_disposition",
    }
    assert all(
        item["reason"]
        and item["claim_boundary"]
        and not item["observation_field"]
        for item in not_applicable
    )
    assert len(axes["validated_item_ids"]) == len(axes["inventory_items"])


def test_dynamic_scenarios_are_separate_for_each_required_guard() -> None:
    scenarios = _dynamic_universe("deep.json", UNIVERSE_SCENARIO_PORTFOLIO)
    counts: dict[str, int] = {}
    for item in scenarios["inventory_items"]:
        object_id = item["object_id"]
        counts[object_id] = counts.get(object_id, 0) + 1

    assert counts == {"world:CausalGuard": 2, "world:EventGuard": 2}
    assert len(scenarios["validated_item_ids"]) == 4


def test_dynamic_projection_has_exact_identity_without_mechanical_ranges() -> None:
    envelope = build_target_native_depth_envelope(
        FIXTURES / "deep.json",
        run_binding={
            "run_id": "worldguard-test-run",
            "contract_hash": "B" * 64,
            "request_fingerprint": "C" * 64,
            "target_input_fingerprint": "D" * 64,
            "evidence_context": _capability_evidence_context(
                "worldguard-test-run"
            ),
        },
        check_id="check:worldguard:native-depth",
        policy_fingerprints=POLICY_FINGERPRINTS,
    )
    assert envelope["target_skill_id"] == "worldguard"
    assert envelope["native_route_id"] == "route:worldguard-claim-derived-depth"
    assert "depth_contribution_ranges" not in envelope
    assert envelope["native_obligation_evidence"]
    assert all(
        row["target_obligation_ids"]
        and row["evidence_ref"].startswith("worldguard:")
        and len(row["evidence_sha256"]) == 64
        for row in envelope["native_obligation_evidence"]
    )

    time_universe = next(
        row for row in envelope["universes"]
        if row["universe_id"] == UNIVERSE_TIMEPOINTS
    )
    assert time_universe["object_scope_attestation"][
        "discovery_input_fingerprint"
    ] == "D" * 64
    floors = {
        row["object_id"]: row
        for row in time_universe["object_native_floor_receipts"]
    }
    assert set(floors) == {"world", "world:variable:y"}
    assert all(row["minimum_validated_count"] == 32 for row in floors.values())
    assert all(row["minimum_coverage"] == 0.032 for row in floors.values())
    assert all(
        row["required_strata_ids"] == ["early", "late", "middle"]
        for row in floors.values()
    )
    assert all(
        "object_scope_attestation" in row for row in envelope["universes"]
    )
    assert all(
        "native_floor_receipt" in row
        for row in envelope["universes"]
        if row["universe_id"] != UNIVERSE_TIMEPOINTS
    )


def test_ten_thousand_step_envelope_carries_native_hundred_point_floor(
    tmp_path: Path,
) -> None:
    payload = json.loads((FIXTURES / "deep.json").read_text(encoding="utf-8"))
    payload["mesh"]["semantic_coverage"]["horizon"] = {
        "start": "t0",
        "end": "t9999",
        "steps": 10_000,
    }
    fixture = tmp_path / "ten-thousand.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")

    envelope = build_target_native_depth_envelope(
        fixture,
        run_binding={
            "run_id": "worldguard-ten-thousand",
            "contract_hash": "B" * 64,
            "request_fingerprint": "C" * 64,
            "target_input_fingerprint": "D" * 64,
            "evidence_context": _capability_evidence_context(
                "worldguard-ten-thousand"
            ),
        },
        check_id="check:worldguard:native-depth",
        policy_fingerprints=POLICY_FINGERPRINTS,
    )
    time_universe = next(
        row for row in envelope["universes"]
        if row["universe_id"] == UNIVERSE_TIMEPOINTS
    )

    assert len(time_universe["inventory_items"]) == 20_000
    assert all(
        row["minimum_validated_count"] == 100
        for row in time_universe["object_native_floor_receipts"]
    )
    assert all(
        row["minimum_coverage"] == 0.01
        for row in time_universe["object_native_floor_receipts"]
    )


def test_current_generic_emitter_binds_each_obligation_to_target_native_receipt(
    tmp_path: Path,
) -> None:
    contract = json.loads(
        (ROOT / "skills/worldguard/.skillguard/compiled-contract.json").read_text(
            encoding="utf-8"
        )
    )
    manifest = json.loads(
        (ROOT / "skills/worldguard/.skillguard/check-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    check = next(
        row
        for row in manifest["checks"]
        if row["check_id"] == "check:worldguard:native-depth"
    )
    run_root = tmp_path / "run"
    run_root.mkdir()
    target_root = tmp_path / "target"
    target_root.mkdir()
    target_fixture = target_root / "deep.json"
    target_payload = json.loads(
        (ROOT / "tests/fixtures/skillguard_depth/deep.json").read_text(
            encoding="utf-8"
        )
    )
    target_payload["release_gate_binding"] = _release_gate_binding()
    target_fixture.write_text(json.dumps(target_payload), encoding="utf-8")
    (run_root / "run.json").write_text(
        json.dumps(
            {
                "run_id": "worldguard-current-emitter",
                "contract_hash": contract["contract_hash"],
                "request_fingerprint": "C" * 64,
                "request": {
                    "target_input_fingerprint": "D" * 64,
                    "target_input_paths": ["deep.json"],
                },
            }
        ),
        encoding="utf-8",
    )
    (run_root / "contract.json").write_text(json.dumps(contract), encoding="utf-8")
    (run_root / "check-manifest.json").write_text(
        json.dumps({"checks": [check]}), encoding="utf-8"
    )
    command = [
        sys.executable,
        "skills/worldguard/.skillguard/checks/emit_native_depth_evidence.py",
        "--run-root",
        str(run_root),
        "--repository-root",
        str(ROOT / "skills" / "worldguard"),
        "--target-root",
        str(target_root),
        "--output",
        "depth-evidence/worldguard.json",
        "--check-id",
        "check:worldguard:native-depth",
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    evidence = json.loads(
        (run_root / "depth-evidence/worldguard.json").read_text(encoding="utf-8")
    )
    assert evidence["ok"] is True
    assert evidence["evidence_context"] == {
        "domain": "release_gate",
        "identity": _release_gate_binding(),
    }
    assert evidence["schema_version"] == "worldguard.declared_native_depth_check.v2"
    assert evidence["predictive_claim_licensed"] is True
    assert evidence["target_obligation_ids"] == sorted(check["covers_obligation_ids"])
    projection = evidence["native_projection"]
    assert projection["schema_version"] == "worldguard.native_depth_projection.v3"
    assert projection["evidence_context"] == evidence["evidence_context"]
    assert all(
        row["target_obligation_ids"]
        and row["evidence_ref"].startswith("worldguard:")
        and len(row["evidence_sha256"]) == 64
        for row in projection["native_obligation_evidence"]
    )
    assert {
        obligation_id
        for row in projection["native_obligation_evidence"]
        for obligation_id in row["target_obligation_ids"]
    } == set(check["covers_obligation_ids"])

    target_payload.pop("release_gate_binding")
    target_fixture.write_text(json.dumps(target_payload), encoding="utf-8")
    missing_binding = subprocess.run(
        command, cwd=ROOT, check=False, capture_output=True, text=True
    )
    assert missing_binding.returncode != 0
    assert "exact current field set" in missing_binding.stderr
    misplaced_run = json.loads((run_root / "run.json").read_text(encoding="utf-8"))
    misplaced_run["request"]["release_gate_binding"] = _release_gate_binding()
    (run_root / "run.json").write_text(json.dumps(misplaced_run), encoding="utf-8")
    misplaced = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert misplaced.returncode != 0
    assert "exact current field set" in misplaced.stderr

    target_payload["release_gate_binding"] = _release_gate_binding()
    target_fixture.write_text(json.dumps(target_payload), encoding="utf-8")
    misplaced_run["request"].pop("release_gate_binding")
    (run_root / "run.json").write_text(json.dumps(misplaced_run), encoding="utf-8")

    target_payload["input_origin"] = "target_native_scheduled_execution"
    target_payload["scheduled_production_identity"] = {"legacy": True}
    target_fixture.write_text(json.dumps(target_payload), encoding="utf-8")
    legacy = subprocess.run(
        command, cwd=ROOT, check=False, capture_output=True, text=True
    )
    assert legacy.returncode != 0
    assert "retired native-depth identity fields are forbidden" in legacy.stderr
    target_payload.pop("input_origin")
    target_payload.pop("scheduled_production_identity")
    target_fixture.write_text(json.dumps(target_payload), encoding="utf-8")

    extra_input = target_root / "extra.json"
    extra_input.write_text("{}", encoding="utf-8")
    run_payload = json.loads((run_root / "run.json").read_text(encoding="utf-8"))
    run_payload["request"]["target_input_paths"].append("extra.json")
    (run_root / "run.json").write_text(json.dumps(run_payload), encoding="utf-8")
    rejected = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert rejected.returncode != 0
    assert "exactly one current target input" in rejected.stderr


def test_native_depth_projection_rejects_retired_run_binding_fields() -> None:
    with pytest.raises(ValueError, match="retired native-depth run binding fields"):
        build_target_native_depth_envelope(
            FIXTURES / "deep.json",
            run_binding={
                "run_id": "worldguard-retired-binding",
                "contract_hash": "B" * 64,
                "request_fingerprint": "C" * 64,
                "target_input_fingerprint": "D" * 64,
                "evidence_domain": "capability_validation",
            },
            check_id="check:worldguard:native-depth",
            policy_fingerprints=POLICY_FINGERPRINTS,
        )
