from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from worldguard.cli import main
from worldguard.mesh import ModelMeshContract, run_model_mesh
from worldguard.task_local_revision import (
    TASK_LOCAL_REVISION_OWNER_ID,
    TASK_LOCAL_REVISION_SCHEMA_VERSION,
    CandidateWorldModelRevision,
    ExternalInputRequirement,
    ObservedWorldRelationship,
    ObservedWorldSnapshot,
    PredictionSnapshot,
    RevalidationRole,
    WorldModelIdentity,
    bind_semantic_rollout_receipt,
    bind_task_local_native_depth_receipt,
    bind_world_revalidation_receipt,
    compare_observed_world,
    coverage_universe_fingerprint,
    evaluate_candidate_world_revision,
    freeze_prediction_snapshot,
    observation_evidence_fingerprint,
)

ROOT = Path(__file__).resolve().parents[1]


def _fp(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _model(tmp_path: Path, name: str, text: str) -> dict[str, str]:
    path = tmp_path / name
    fixture = json.loads((ROOT / "tests/fixtures/execution_depth/deep.json").read_text())
    fixture["mesh"]["run_id"] = name + ":" + hashlib.sha256(text.encode()).hexdigest()
    path.write_text(json.dumps(fixture), encoding="utf-8")
    return {
        "model_id": f"model:{name}",
        "model_version": "1",
        "path": name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _prediction(
    model: dict[str, str],
    prediction_id: str = "prediction-1",
    *,
    iteration: int = 0,
    max_iterations: int = 4,
    prior_gap_ids: list[str] | None = None,
    prior_gap_fingerprints: list[str] | None = None,
) -> dict:
    coverage_ids = ["value-voltage", "relation-command-before-response"]
    return {
        "schema_version": TASK_LOCAL_REVISION_SCHEMA_VERSION,
        "prediction_id": prediction_id,
        "task_id": "task-1",
        "purpose": "predict voltage and command-response ordering",
        "coverage_universe_id": "coverage:task-1",
        "coverage_universe_owner_id": "owner:independent-test-inventory",
        "coverage_universe_source_ref": "test://independent-coverage",
        "coverage_universe_fingerprint": coverage_universe_fingerprint(
            universe_id="coverage:task-1",
            owner_id="owner:independent-test-inventory",
            source_ref="test://independent-coverage",
            coverage_ids=coverage_ids,
        ),
        "coverage_ids": coverage_ids,
        "assumptions": ["the voltage sensor uses the declared unit"],
        "unknowns": ["unobserved environmental load may alter the response"],
        "iteration": iteration,
        "max_iterations": max_iterations,
        "predecessor_iteration_fingerprint": "root" if iteration == 0 else "a" * 64,
        "prior_gap_ids": prior_gap_ids or [],
        "prior_gap_fingerprints": prior_gap_fingerprints or [],
        "model": model,
        "prediction_sequence": 10 + iteration * 10,
        "initial_state": {"temperature": 70.0},
        "intervention": {"cooling_command": 0.7},
        "expected_values": [
            {
                "expectation_id": "value-voltage",
                "target_id": "voltage",
                "expected_value": 0.72,
                "tolerance": 0.02,
                "mismatch_category": "causal_relation",
                "weakening_condition": "voltage lies outside the declared tolerance",
            }
        ],
        "expected_relationships": [
            {
                "expectation_id": "relation-command-before-response",
                "relationship_id": "command-before-response",
                "left": "cooling_command",
                "relation": "before",
                "right": "temperature_response",
                "mismatch_category": "transition",
                "weakening_condition": "the response precedes or lacks the command",
            }
        ],
        "weakening_conditions": [
            "voltage misses its tolerance",
            "the declared command-response ordering is absent",
        ],
    }


def _observation(
    prediction_id: str = "prediction-1",
    *,
    observation_id: str = "observation-1",
    sequence: int = 11,
    voltage: float = 0.73,
    include_relationship: bool = True,
    source_ref: str | None = None,
    external_inputs: list[dict] | None = None,
) -> dict:
    relationship_rows: list[dict[str, str]] = []
    relationships: list[ObservedWorldRelationship] = []
    if include_relationship:
        row = {
            "relationship_id": "command-before-response",
            "left": "cooling_command",
            "relation": "before",
            "right": "temperature_response",
        }
        relationship_rows.append(row)
        relationships.append(ObservedWorldRelationship.from_dict(row))
    external_rows = external_inputs or []
    external = [ExternalInputRequirement.from_dict(item) for item in external_rows]
    actual_source = source_ref or f"test://{observation_id}"
    fingerprint = observation_evidence_fingerprint(
        observation_id=observation_id,
        prediction_id=prediction_id,
        observation_sequence=sequence,
        source_ref=actual_source,
        values={"voltage": voltage},
        relationships=relationships,
        external_inputs=external,
    )
    return {
        "schema_version": TASK_LOCAL_REVISION_SCHEMA_VERSION,
        "observation_id": observation_id,
        "prediction_id": prediction_id,
        "observation_sequence": sequence,
        "source_ref": actual_source,
        "values": {"voltage": voltage},
        "relationships": relationship_rows,
        "evidence_id": f"evidence:{observation_id}",
        "evidence_fingerprint": fingerprint,
        "external_inputs": external_rows,
    }


def _comparison(
    tmp_path: Path,
    model: dict[str, str],
    *,
    prediction_id: str,
    observation_id: str,
    voltage: float = 0.73,
    include_relationship: bool = True,
    iteration: int = 0,
    max_iterations: int = 4,
    prior_gap_ids: list[str] | None = None,
    prior_gap_fingerprints: list[str] | None = None,
) -> tuple[PredictionSnapshot, dict]:
    prediction = PredictionSnapshot.from_dict(
        _prediction(
            model,
            prediction_id,
            iteration=iteration,
            max_iterations=max_iterations,
            prior_gap_ids=prior_gap_ids,
            prior_gap_fingerprints=prior_gap_fingerprints,
        )
    )
    observation = ObservedWorldSnapshot.from_dict(
        _observation(
            prediction_id,
            observation_id=observation_id,
            sequence=prediction.prediction_sequence + 1,
            voltage=voltage,
            include_relationship=include_relationship,
        )
    )
    return prediction, compare_observed_world(prediction, observation, base_dir=tmp_path)


def _native_source(tmp_path: Path, candidate: dict[str, str]) -> dict:
    payload = json.loads((tmp_path / candidate["path"]).read_text())
    return run_model_mesh(ModelMeshContract.from_dict(payload["mesh"])).depth_receipt.to_dict()


def _prepare_native_candidate(tmp_path: Path, candidate: dict[str, str], gaps: list[str], licensed: bool) -> None:
    path = tmp_path / candidate["path"]
    payload = json.loads(path.read_text())
    mesh = payload["mesh"]
    mesh["semantic_coverage"]["branch_ids"] = ["b0", *gaps]
    if not licensed:
        mesh["semantic_coverage"]["profile"] = "bounded"
        for node in mesh["nodes"]:
            node["contract"]["claim"]["text"] = "bounded declared state"
            for atom in node["contract"]["claim"]["atoms"]:
                atom["predictive_intent"] = False
    path.write_text(json.dumps(payload))
    candidate["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()


def _revalidation(
    *,
    candidate: dict[str, str],
    role: RevalidationRole,
    comparison: dict,
) -> dict:
    identity = WorldModelIdentity.from_dict(candidate)
    semantic = bind_semantic_rollout_receipt(
        receipt_id=f"semantic:{role.value}",
        task_id="task-1",
        role=role,
        candidate_model=identity,
        semantic_status="pass",
        source_result={
            "artifact_kind": "worldguard.semantic_execution",
            "status": "PASS",
            "scenario": role.value,
            "candidate_sha256": candidate["sha256"],
        },
        evidence_ref=f"test://semantic/{role.value}",
    )
    return bind_world_revalidation_receipt(
        check_id=role.value,
        role=role,
        candidate_model=identity,
        semantic_receipt=semantic,
        empirical_comparison=comparison,
    )


def _revision(
    tmp_path: Path,
    base: dict[str, str],
    candidate: dict[str, str],
    *,
    native_gaps: list[str] | None = None,
    licensed: bool = True,
    iteration: int = 0,
    max_iterations: int = 4,
    prior_gap_ids: list[str] | None = None,
    prior_gap_fingerprints: list[str] | None = None,
    external_inputs: list[dict] | None = None,
    candidate_applied: bool = False,
    rollback_model: dict[str, str] | None = None,
) -> dict:
    _prepare_native_candidate(tmp_path, candidate, native_gaps or [], licensed)
    base_prediction, base_comparison = _comparison(
        tmp_path,
        base,
        prediction_id="prediction-base",
        observation_id="observation-mismatch",
        voltage=0.60,
        iteration=iteration,
        max_iterations=max_iterations,
        prior_gap_ids=prior_gap_ids,
        prior_gap_fingerprints=prior_gap_fingerprints,
    )
    _, original = _comparison(
        tmp_path,
        candidate,
        prediction_id="prediction-original",
        observation_id="observation-original",
        iteration=iteration,
        max_iterations=max_iterations,
        prior_gap_ids=prior_gap_ids,
        prior_gap_fingerprints=prior_gap_fingerprints,
    )
    _, holdout = _comparison(
        tmp_path,
        candidate,
        prediction_id="prediction-holdout",
        observation_id="observation-holdout",
        voltage=0.72,
        iteration=iteration,
        max_iterations=max_iterations,
        prior_gap_ids=prior_gap_ids,
        prior_gap_fingerprints=prior_gap_fingerprints,
    )
    depth = bind_task_local_native_depth_receipt(
        base_prediction,
        WorldModelIdentity.from_dict(candidate),
        _native_source(tmp_path, candidate),
        base_dir=tmp_path,
        binding_id="depth-binding:one",
    )
    return {
        "schema_version": TASK_LOCAL_REVISION_SCHEMA_VERSION,
        "revision_id": "revision-1",
        "prediction_id": base_prediction.prediction_id,
        "base_model": base,
        "candidate_model": candidate,
        "revision_kind": "update_causal_relation",
        "prediction_receipt": freeze_prediction_snapshot(base_prediction, base_dir=tmp_path),
        "comparison_receipt": base_comparison,
        "native_depth_receipt": depth,
        "candidate_build_evidence_fingerprints": [
            base_comparison["observation_evidence_fingerprint"]
        ],
        "required_revalidation_ids": [
            RevalidationRole.ORIGINAL_SCENARIO.value,
            RevalidationRole.REAL_HOLDOUT_OBSERVATION.value,
        ],
        "revalidations": [
            _revalidation(
                candidate=candidate,
                role=RevalidationRole.ORIGINAL_SCENARIO,
                comparison=original,
            ),
            _revalidation(
                candidate=candidate,
                role=RevalidationRole.REAL_HOLDOUT_OBSERVATION,
                comparison=holdout,
            ),
        ],
        "candidate_applied": candidate_applied,
        "rollback_model": rollback_model,
        "external_inputs": external_inputs or [],
    }


def test_current_prediction_snapshot_freezes_independent_task_boundary(tmp_path: Path) -> None:
    prediction = PredictionSnapshot.from_dict(_prediction(_model(tmp_path, "v1.json", "{}")))
    receipt = freeze_prediction_snapshot(prediction, base_dir=tmp_path)
    assert receipt["status"] == "pass"
    assert receipt["owner_id"] == TASK_LOCAL_REVISION_OWNER_ID
    assert receipt["coverage_universe_fingerprint"] == prediction.coverage_universe_fingerprint
    assert receipt["predecessor_iteration_fingerprint"] == "root"


@pytest.mark.parametrize(
    "missing_field",
    [
        "task_id",
        "purpose",
        "coverage_universe_fingerprint",
        "assumptions",
        "unknowns",
        "predecessor_iteration_fingerprint",
        "prior_gap_ids",
    ],
)
def test_legacy_or_shallow_prediction_is_rejected(tmp_path: Path, missing_field: str) -> None:
    row = _prediction(_model(tmp_path, "v1.json", "{}"))
    row.pop(missing_field)
    with pytest.raises(ValueError, match="missing current fields"):
        PredictionSnapshot.from_dict(row)


def test_empty_assumptions_or_unknown_boundary_is_rejected(tmp_path: Path) -> None:
    row = _prediction(_model(tmp_path, "v1.json", "{}"))
    row["unknowns"] = []
    with pytest.raises(ValueError, match="unknowns must be non-empty"):
        PredictionSnapshot.from_dict(row)


def test_tampered_coverage_and_observation_evidence_are_rejected(tmp_path: Path) -> None:
    row = _prediction(_model(tmp_path, "v1.json", "{}"))
    row["coverage_universe_fingerprint"] = "0" * 64
    with pytest.raises(ValueError, match="independent inventory"):
        PredictionSnapshot.from_dict(row)
    observation = _observation()
    observation["values"]["voltage"] = 0.1
    with pytest.raises(ValueError, match="stale or tampered"):
        ObservedWorldSnapshot.from_dict(observation)


def test_observation_must_be_later_than_prediction(tmp_path: Path) -> None:
    prediction = PredictionSnapshot.from_dict(_prediction(_model(tmp_path, "v1.json", "{}")))
    observation = ObservedWorldSnapshot.from_dict(_observation(sequence=10))
    with pytest.raises(ValueError, match="strictly later"):
        compare_observed_world(prediction, observation, base_dir=tmp_path)


def test_compare_retains_native_mismatch_categories_but_never_closes_task(tmp_path: Path) -> None:
    prediction = PredictionSnapshot.from_dict(_prediction(_model(tmp_path, "v1.json", "{}")))
    observation = ObservedWorldSnapshot.from_dict(_observation(voltage=0.61, include_relationship=False))
    receipt = compare_observed_world(prediction, observation, base_dir=tmp_path)
    assert receipt["status"] == "fail"
    assert receipt["terminal_reason"] == "continue_iteration"
    assert {item["mismatch_category"] for item in receipt["mismatches"]} == {"causal_relation", "transition"}


def test_candidate_closes_only_with_current_depth_and_independent_holdout(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    receipt = evaluate_candidate_world_revision(
        CandidateWorldModelRevision.from_dict(_revision(tmp_path, base, candidate)),
        base_dir=tmp_path,
    )
    assert receipt["status"] == "pass"
    assert receipt["disposition"] == "accepted"
    assert receipt["terminal_reason"] == "model_closed_for_task"
    assert receipt["current_gap_ids"] == []
    assert all(item["effective_status"] == "pass" for item in receipt["revalidation_results"])


def test_native_depth_gap_is_derived_and_forces_continuation(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    row = _revision(tmp_path, base, candidate, native_gaps=["branch:new-regime"])
    receipt = evaluate_candidate_world_revision(CandidateWorldModelRevision.from_dict(row), base_dir=tmp_path)
    gaps = row["native_depth_receipt"]["source_receipt"]["predictive_gaps"]
    expected = sorted("native:" + gap for gap in gaps)
    assert receipt["status"] == "blocked"
    assert receipt["terminal_reason"] == "continue_iteration"
    assert receipt["current_gap_ids"] == expected
    assert receipt["predictive_gap_categories"]["branch"] == sorted(gaps)
    assert receipt["introduced_gap_ids"] == expected


def test_no_raw_gap_but_unlicensed_native_receipt_cannot_close(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    receipt = evaluate_candidate_world_revision(
        CandidateWorldModelRevision.from_dict(
            _revision(tmp_path, base, candidate, licensed=False)
        ),
        base_dir=tmp_path,
    )
    assert receipt["terminal_reason"] == "continue_iteration"
    assert "native:predictive_claim_not_licensed" in receipt["current_gap_ids"]


def test_repeated_gap_fingerprint_stalls_without_caller_progress_override(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    first = _revision(tmp_path, base, candidate, native_gaps=["transition:missing-edge"])
    current_gaps = sorted("native:" + gap for gap in first["native_depth_receipt"]["source_receipt"]["predictive_gaps"])
    current_gap_fingerprint = _fp(current_gaps)
    row = _revision(
        tmp_path,
        base,
        candidate,
        native_gaps=["transition:missing-edge"],
        iteration=1,
        prior_gap_ids=current_gaps,
        prior_gap_fingerprints=[current_gap_fingerprint],
    )
    receipt = evaluate_candidate_world_revision(CandidateWorldModelRevision.from_dict(row), base_dir=tmp_path)
    assert receipt["progressed"] is False
    assert receipt["terminal_reason"] == "progress_stalled"


def test_later_iteration_closes_only_after_exact_prior_gap_set_resolves(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    prior_gap_ids = ["native:branch:old-regime"]
    row = _revision(
        tmp_path,
        base,
        candidate,
        iteration=1,
        prior_gap_ids=prior_gap_ids,
        prior_gap_fingerprints=[_fp(prior_gap_ids)],
    )
    receipt = evaluate_candidate_world_revision(
        CandidateWorldModelRevision.from_dict(row),
        base_dir=tmp_path,
    )
    assert receipt["terminal_reason"] == "model_closed_for_task"
    assert receipt["input_gap_ids"] == prior_gap_ids
    assert receipt["resolved_gap_ids"] == prior_gap_ids
    assert receipt["current_gap_ids"] == []


def test_later_iteration_derives_resolved_and_introduced_gap_ids(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    prior_gap_ids = ["native:state:old-state-gap"]
    row = _revision(
        tmp_path,
        base,
        candidate,
        native_gaps=["transition:new-edge-gap"],
        iteration=1,
        prior_gap_ids=prior_gap_ids,
        prior_gap_fingerprints=[_fp(prior_gap_ids)],
    )
    receipt = evaluate_candidate_world_revision(
        CandidateWorldModelRevision.from_dict(row),
        base_dir=tmp_path,
    )
    assert receipt["resolved_gap_ids"] == prior_gap_ids
    assert receipt["introduced_gap_ids"] == sorted("native:" + gap for gap in row["native_depth_receipt"]["source_receipt"]["predictive_gaps"])
    assert receipt["persisted_gap_ids"] == []
    assert receipt["terminal_reason"] == "continue_iteration"


def test_iteration_limit_blocks_instead_of_passing(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    row = _revision(
        tmp_path,
        base,
        candidate,
        native_gaps=["state:unknown"],
        iteration=1,
        max_iterations=2,
        prior_gap_ids=["native:state:previous-gap"],
        prior_gap_fingerprints=[_fp(["native:state:previous-gap"])],
    )
    receipt = evaluate_candidate_world_revision(CandidateWorldModelRevision.from_dict(row), base_dir=tmp_path)
    assert receipt["status"] == "blocked"
    assert receipt["terminal_reason"] == "iteration_limit"


def test_exact_external_input_can_stop_but_incomplete_boundary_blocks(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    exact = [
        {
            "input_id": "external:holdout-observation",
            "owner_id": "owner:lab",
            "reason": "the required regime is not observable with local tools",
            "blocked_gap_ids": ["native:holdout:unseen-regime"],
            "affected_claim_ids": ["claim:future-regime"],
        }
    ]
    row = _revision(tmp_path, base, candidate, native_gaps=["holdout:unseen-regime"])
    exact[0]["blocked_gap_ids"] = sorted("native:" + gap for gap in row["native_depth_receipt"]["source_receipt"]["predictive_gaps"])
    row["external_inputs"] = exact
    receipt = evaluate_candidate_world_revision(CandidateWorldModelRevision.from_dict(row), base_dir=tmp_path)
    assert receipt["terminal_reason"] == "external_input_required"
    bad = json.loads(json.dumps(_revision(tmp_path, base, candidate, native_gaps=["holdout:unseen-regime"], external_inputs=exact)))
    bad["external_inputs"][0]["blocked_gap_ids"] = ["native:other-gap"]
    blocked = evaluate_candidate_world_revision(CandidateWorldModelRevision.from_dict(bad), base_dir=tmp_path)
    assert blocked["terminal_reason"] == "blocked"
    assert "external_input_names_non_open_gap" in blocked["identity_findings"]


def test_legacy_semantic_pass_string_is_rejected(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    row = _revision(tmp_path, base, candidate)
    legacy = {
        "check_id": "original_scenario",
        "role": "original_scenario",
        "candidate_model": candidate,
        "semantic_rollout_status": "PASS",
        "empirical_comparison": row["revalidations"][0]["empirical_comparison"],
        "evidence_ref": "test://legacy",
    }
    row["revalidations"][0] = legacy
    with pytest.raises(ValueError, match="unknown fields"):
        CandidateWorldModelRevision.from_dict(row)


def test_holdout_alias_or_construction_reuse_rejects_candidate(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    row = _revision(tmp_path, base, candidate)
    holdout_fp = row["revalidations"][1]["empirical_comparison"]["observation_evidence_fingerprint"]
    row["candidate_build_evidence_fingerprints"].append(holdout_fp)
    receipt = evaluate_candidate_world_revision(CandidateWorldModelRevision.from_dict(row), base_dir=tmp_path)
    assert receipt["disposition"] == "rejected"
    holdout = next(item for item in receipt["revalidation_results"] if item["role"] == "real_holdout_observation")
    assert "holdout_used_for_candidate_construction" in holdout["issues"]


def test_renamed_holdout_content_alias_is_rejected(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    row = _revision(tmp_path, base, candidate)
    row["revalidations"][1]["empirical_comparison"] = json.loads(
        json.dumps(row["revalidations"][0]["empirical_comparison"])
    )
    holdout_body = {
        key: value
        for key, value in row["revalidations"][1].items()
        if key != "receipt_fingerprint"
    }
    row["revalidations"][1]["receipt_fingerprint"] = _fp(holdout_body)
    receipt = evaluate_candidate_world_revision(
        CandidateWorldModelRevision.from_dict(row),
        base_dir=tmp_path,
    )
    holdout = next(
        item
        for item in receipt["revalidation_results"]
        if item["role"] == "real_holdout_observation"
    )
    assert "holdout_content_alias_not_independent" in holdout["issues"]


def test_noncurrent_native_depth_and_caller_gap_fields_are_rejected(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    row = _revision(tmp_path, base, candidate)
    depth = row["native_depth_receipt"]
    depth["source_receipt"]["receipt_version"] = "worldguard.native_depth.v1"
    depth["source_receipt_fingerprint"] = _fp(depth["source_receipt"])
    binding_body = {key: value for key, value in depth.items() if key != "binding_fingerprint"}
    depth["binding_fingerprint"] = _fp(binding_body)
    with pytest.raises(ValueError, match="receipt_version is not current"):
        CandidateWorldModelRevision.from_dict(row)

    caller_authored = _revision(tmp_path, base, candidate)
    caller_authored["remaining_predictive_gap_ids"] = ["native:state:invented"]
    caller_authored["progressed"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        CandidateWorldModelRevision.from_dict(caller_authored)


def test_failed_applied_candidate_rolls_back_to_exact_current_base(tmp_path: Path) -> None:
    base = _model(tmp_path, "v1.json", '{"version": 1}')
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    row = _revision(tmp_path, base, candidate, candidate_applied=True, rollback_model=base)
    semantic = row["revalidations"][1]["semantic_receipt"]
    semantic["semantic_status"] = "fail"
    semantic["source_result"]["status"] = "FAIL"
    semantic["source_result_fingerprint"] = _fp(semantic["source_result"])
    body = {key: value for key, value in semantic.items() if key != "binding_fingerprint"}
    semantic["binding_fingerprint"] = _fp(body)
    revalidation = row["revalidations"][1]
    revalidation_body = {key: value for key, value in revalidation.items() if key != "receipt_fingerprint"}
    revalidation["receipt_fingerprint"] = _fp(revalidation_body)
    receipt = evaluate_candidate_world_revision(CandidateWorldModelRevision.from_dict(row), base_dir=tmp_path)
    assert receipt["disposition"] == "rolled_back"
    assert receipt["terminal_reason"] == "candidate_rolled_back"
    assert receipt["rollback_model"]["actual_sha256"] == base["sha256"]


def test_task_model_cli_freezes_and_binds_native_depth(tmp_path: Path, capsys) -> None:
    model = _model(tmp_path, "v1.json", "{}")
    candidate = _model(tmp_path, "v2.json", '{"version": 2}')
    prediction_path = tmp_path / "prediction.json"
    candidate_path = tmp_path / "candidate-identity.json"
    native_path = tmp_path / "native-depth.json"
    prediction_path.write_text(json.dumps(_prediction(model)), encoding="utf-8")
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    native_path.write_text(json.dumps(_native_source(tmp_path, candidate)), encoding="utf-8")
    assert main(["task-model", "freeze", str(prediction_path)]) == 0
    assert json.loads(capsys.readouterr().out)["receipt_version"] == "2.0"
    assert main(["task-model", "depth-bind", str(prediction_path), str(candidate_path), str(native_path), "--binding-id", "depth:cli"]) == 0
    bound = json.loads(capsys.readouterr().out)
    assert bound["artifact_kind"] == "worldguard_task_local_native_depth_receipt"


def test_bundled_task_local_runtime_matches_source_and_version() -> None:
    bundled_root = ROOT / "skills" / "worldguard" / "runtime" / "worldguard"
    for relative_path in ("task_local_revision.py", "fact_revision.py", "cli.py", "__init__.py"):
        assert (ROOT / "worldguard" / relative_path).read_bytes() == (bundled_root / relative_path).read_bytes()
    assert '__version__ = "0.7.14"' in (bundled_root / "__init__.py").read_text(encoding="utf-8")


def test_native_depth_reuses_real_producer_without_reexecuting_mesh(tmp_path, monkeypatch):
    import worldguard.mesh as owner
    candidate = _model(tmp_path, "candidate.json", "actual native candidate")
    prediction = PredictionSnapshot.from_dict(_prediction(candidate))
    source = _native_source(tmp_path, candidate)
    def forbid_execution(*args, **kwargs):
        raise AssertionError("binding an existing native receipt must not execute the mesh")
    monkeypatch.setattr(owner, "run_model_mesh", forbid_execution)
    bound = bind_task_local_native_depth_receipt(prediction, WorldModelIdentity.from_dict(candidate), source, base_dir=tmp_path, binding_id="reused")
    assert bound["source_receipt"] == source
    assert bound["task_id"] == prediction.task_id
    assert bound["coverage_universe_fingerprint"] == prediction.coverage_universe_fingerprint


@pytest.mark.parametrize("mutation", ["seven_fields", "mesh_hash", "word_coverage", "bad_count", "false_summary"])
def test_native_depth_rejects_nonproducer_or_inconsistent_sources(tmp_path, mutation):
    candidate = _model(tmp_path, "candidate.json", "native")
    source = _native_source(tmp_path, candidate)
    if mutation == "seven_fields":
        source = {key: source[key] for key in ("receipt_id", "receipt_version", "mesh_fingerprint", "coverage_fingerprint", "predictive_gaps", "quantitative_coverage", "predictive_claim_licensed")}
    elif mutation == "mesh_hash":
        source["mesh_fingerprint"] = "not-a-sha256"
    elif mutation == "word_coverage":
        source["quantitative_coverage"] = {"made_up_no_models": "a word"}
    elif mutation == "bad_count":
        source["quantitative_coverage"]["executed_model_node_count"] = -1
    else:
        source["findings"][-1]["predictive_claim_licensed"] = False
    with pytest.raises(ValueError):
        bind_task_local_native_depth_receipt(PredictionSnapshot.from_dict(_prediction(candidate)), WorldModelIdentity.from_dict(candidate), source, base_dir=tmp_path, binding_id="invalid")


def test_native_depth_other_candidate_cannot_be_rebound_by_outer_self_hash(tmp_path):
    base = _model(tmp_path, "base.json", "base")
    candidate = _model(tmp_path, "candidate.json", "candidate")
    other = _model(tmp_path, "other.json", "other")
    other_source = _native_source(tmp_path, other)
    with pytest.raises(ValueError, match="current candidate"):
        bind_task_local_native_depth_receipt(PredictionSnapshot.from_dict(_prediction(base)), WorldModelIdentity.from_dict(candidate), other_source, base_dir=tmp_path, binding_id="other")
    row = _revision(tmp_path, base, candidate)
    binding = row["native_depth_receipt"]
    binding["source_receipt"] = other_source
    binding["source_receipt_fingerprint"] = _fp(other_source)
    binding["binding_fingerprint"] = _fp({key: value for key, value in binding.items() if key != "binding_fingerprint"})
    result = evaluate_candidate_world_revision(CandidateWorldModelRevision.from_dict(row), base_dir=tmp_path)
    assert result["terminal_reason"] == "blocked"
    assert any("native_depth_source_invalid" in finding for finding in result["identity_findings"])


def test_native_depth_unknown_model_kind_is_explicitly_unsupported(tmp_path):
    candidate = _model(tmp_path, "candidate.json", "native")
    source = _native_source(tmp_path, candidate)
    path = tmp_path / candidate["path"]
    path.write_text('{"arbitrary_model": true}')
    candidate["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="supports a current native mesh candidate only"):
        bind_task_local_native_depth_receipt(PredictionSnapshot.from_dict(_prediction(candidate)), WorldModelIdentity.from_dict(candidate), source, base_dir=tmp_path, binding_id="unsupported")
