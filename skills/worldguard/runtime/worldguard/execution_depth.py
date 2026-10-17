"""Execute the native mesh depth evaluator without author-tool transport."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping
from .mesh import ModelMeshContract, run_model_mesh
from .semantic import SemanticStatus
EVIDENCE_SCHEMA = "worldguard.execution_depth_evidence.v3"
TARGET_SKILL_ID = "worldguard"
NATIVE_OWNER_ID = "worldguard.mesh.predictive_coverage"
NATIVE_ROUTE_ID = "route:worldguard-claim-derived-depth"


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest().upper()


def _object_result(object_id: str, valid: bool) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "eligible_count": 1,
        "selected_count": 1,
        "evaluated_count": 1,
        "validated_count": int(valid),
    }


def _primary_blocker(receipt: Any) -> str:
    if receipt.missing_guards:
        return "claim_derived_guard_missing"
    if receipt.skipped_model_nodes:
        return "expected_semantic_node_missing"
    gaps = list(receipt.predictive_gaps)
    if any(
        "timepoint" in item or "time_stratum" in item or "horizon" in item
        for item in gaps
    ):
        return "time_horizon_depth_incomplete"
    if any("intervention" in item or "counterfactual" in item for item in gaps):
        return "intervention_counterfactual_depth_incomplete"
    if any("holdout" in item or "scenario" in item for item in gaps):
        return "scenario_holdout_depth_incomplete"
    if any("branch" in item or "perturbation" in item for item in gaps):
        return "branch_perturbation_depth_incomplete"
    if any("state" in item or "transition" in item for item in gaps):
        return "state_transition_depth_incomplete"
    return "predictive_depth_incomplete"


def build_native_depth_evidence(
    fixture_path: str | Path,
    *,
    expected_status: str | None = None,
    expected_blocker_code: str | None = None,
) -> dict[str, Any]:
    """Execute WorldGuard's native mesh route and project immutable bridge evidence."""

    fixture_reference = Path(fixture_path).as_posix()
    path = Path(fixture_path).resolve()
    raw = path.read_bytes()
    fixture = json.loads(raw.decode("utf-8"))
    if not isinstance(fixture, Mapping) or not isinstance(fixture.get("mesh"), Mapping):
        raise ValueError("fixture must contain a mesh object")
    mesh = ModelMeshContract.from_dict(dict(fixture["mesh"]))
    report = run_model_mesh(mesh)
    receipt = report.depth_receipt
    if receipt is None:
        raise ValueError("native WorldGuard mesh report omitted its depth receipt")
    receipt_payload = receipt.to_dict()
    quantitative = receipt.quantitative_coverage

    routes_complete = bool(not receipt.missing_guards)
    semantic_universe_complete = bool(
        set(receipt.expected_model_nodes) == set(receipt.executed_model_nodes)
        and not receipt.skipped_model_nodes
        and quantitative.get("expected_semantic_child_count")
        == quantitative.get("executed_semantic_child_count")
        and not receipt.skipped_children
    )
    time_scenario_complete = bool(
        quantitative.get("expected_scenario_count")
        == quantitative.get("executed_scenario_count")
        and quantitative.get("expected_holdout_scenario_count")
        == quantitative.get("executed_holdout_scenario_count")
        and not any(
            "horizon" in item
            or "timepoint" in item
            or "time_stratum" in item
            or "scenario" in item
            or "holdout" in item
            for item in receipt.predictive_gaps
        )
    )
    axis_results = {
        str(row.get("axis_id", "")): row
        for row in quantitative.get("predictive_axis_results", [])
        if isinstance(row, Mapping) and str(row.get("axis_id", ""))
    }

    def axes_complete(*axis_ids: str) -> bool:
        return all(
            axis_id in axis_results and axis_results[axis_id].get("passed") is True
            for axis_id in axis_ids
        )

    state_transition_complete = axes_complete("state", "transition")
    event_fluent_complete = axes_complete("event", "fluent")
    branch_perturbation_complete = axes_complete("branch", "perturbation")
    intervention_counterfactual_complete = axes_complete(
        "intervention",
        "counterfactual",
    )
    per_object = [
        _object_result("worldguard:claim-derived-routes", routes_complete),
        _object_result("worldguard:semantic-universe", semantic_universe_complete),
        _object_result("worldguard:time-scenario-holdout", time_scenario_complete),
        _object_result("worldguard:state-transition", state_transition_complete),
        _object_result("worldguard:event-fluent", event_fluent_complete),
        _object_result("worldguard:branch-perturbation", branch_perturbation_complete),
        _object_result(
            "worldguard:intervention-counterfactual",
            intervention_counterfactual_complete,
        ),
    ]
    status = (
        "EXECUTION_DEPTH_PASS"
        if receipt.predictive_claim_licensed
        else (
            "BOUNDED_PARTIAL"
            if mesh.semantic_coverage.profile == "bounded"
            and report.rollout_status == SemanticStatus.PASS
            else "SHALLOW_BLOCKED"
        )
    )
    blocker_code = "none" if status == "EXECUTION_DEPTH_PASS" else _primary_blocker(receipt)
    coverage_result = {
        "universe_id": "universe:worldguard-claim-derived-depth",
        "owner_id": NATIVE_OWNER_ID,
        "universe_fingerprint": receipt.coverage_fingerprint.upper(),
        "eligible_count": len(per_object),
        "selected_count": len(per_object),
        "evaluated_count": len(per_object),
        "validated_count": sum(row["validated_count"] for row in per_object),
        "covered_claim_scope": [atom["atom_id"] for atom in receipt.claim_atoms],
        "strata_results": [
            {
                "stratum_id": row["object_id"],
                "selected_count": row["selected_count"],
                "evaluated_count": row["evaluated_count"],
                "validated_count": row["validated_count"],
            }
            for row in per_object
        ],
        "per_object_results": per_object,
        "critical_uncovered_ids": list(receipt.predictive_gaps),
        "current": True,
    }
    evidence = {
        "schema_version": EVIDENCE_SCHEMA,
        "target_skill_id": TARGET_SKILL_ID,
        "native_owner_id": NATIVE_OWNER_ID,
        "native_route_id": NATIVE_ROUTE_ID,
        "case_id": str(fixture.get("case_id", path.stem)),
        "status": status,
        "primary_blocker_code": blocker_code,
        "blocker_codes": [blocker_code] if blocker_code != "none" else [],
        "input_path": fixture_reference,
        "input_sha256": hashlib.sha256(raw).hexdigest().upper(),
        "input_fingerprint": _sha256(fixture),
        "native_receipt_id": receipt.receipt_id,
        "native_receipt_hash": _sha256(receipt_payload),
        "native_receipt_schema": receipt.receipt_version,
        "native_receipt_created_at": receipt.generated_at,
        "native_receipt": receipt_payload,
        "native_obligation_evidence": list(
            receipt_payload.get("native_obligation_evidence", [])
        ),
        "coverage_universe_results": [coverage_result],
        "target_owned_universe": mesh.semantic_coverage.to_dict(),
        "claim_boundary": receipt.claim_boundary,
    }
    evidence["evidence_payload_hash"] = _sha256(evidence)
    if expected_status and status != expected_status:
        raise ValueError(f"expected status {expected_status}, observed {status}")
    if expected_blocker_code and blocker_code != expected_blocker_code:
        raise ValueError(
            f"expected blocker {expected_blocker_code}, observed {blocker_code}"
        )
    return evidence
