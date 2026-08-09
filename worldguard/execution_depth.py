"""Target-owned WorldGuard execution-depth evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .mesh import (
    ModelMeshContract,
    SemanticCoverageContract,
    _time_position,
    run_model_mesh,
)
from .semantic import SemanticStatus


EVIDENCE_SCHEMA = "worldguard.execution_depth_evidence.v3"
TARGET_SKILL_ID = "worldguard"
NATIVE_OWNER_ID = "worldguard.mesh.predictive_coverage"
NATIVE_ROUTE_ID = "route:worldguard-claim-derived-depth"
TARGET_NATIVE_DEPTH_SCHEMA = "worldguard.native_depth_projection.v3"

UNIVERSE_SEMANTIC_CHILDREN = "universe:worldguard-semantic-children"
UNIVERSE_TIMEPOINTS = "universe:worldguard-timepoints"
UNIVERSE_SCENARIO_PORTFOLIO = "universe:worldguard-scenario-portfolio"
UNIVERSE_PREDICTIVE_AXES = "universe:worldguard-predictive-axes"
UNIVERSE_NATIVE_POLICY = "universe:worldguard-native-predictive-policy"
UNIVERSE_CLAIM_SCOPE = "universe:worldguard-predictive-claim-scope"

TARGET_NATIVE_POLICY_DEFINITIONS = {
    UNIVERSE_SEMANTIC_CHILDREN: {
        "algorithm_id": "worldguard.native-exhaustive-floor.v1",
        "scope": "every claim-derived semantic child",
        "required": "all expected children execute and pass",
    },
    UNIVERSE_TIMEPOINTS: {
        "algorithm_id": "worldguard.native-sqrt-phase-gap-floor.v1",
        "scope": "every model-node and variable/signal temporal child",
        "required": "ceil(sqrt(horizon)), native early/middle/late, and maximum-gap gates",
    },
    UNIVERSE_SCENARIO_PORTFOLIO: {
        "algorithm_id": "worldguard.native-exhaustive-floor.v1",
        "scope": "each required Guard on every expected model node",
        "required": "normal and holdout scenarios",
    },
    UNIVERSE_PREDICTIVE_AXES: {
        "algorithm_id": "worldguard.native-exhaustive-floor.v1",
        "scope": "each expected predictive model node",
        "required": (
            "one closed required or not_applicable disposition for each state, "
            "transition, event, fluent, branch, perturbation, intervention, and "
            "counterfactual axis"
        ),
    },
    UNIVERSE_NATIVE_POLICY: {
        "algorithm_id": "worldguard.native-exhaustive-floor.v1",
        "scope": "each expected predictive model node",
        "required": "the target-owned predictive policy itself passes",
    },
    UNIVERSE_CLAIM_SCOPE: {
        "algorithm_id": "worldguard.native-exhaustive-floor.v1",
        "scope": "each predictive claim atom",
        "required": "the atom remains bound to a model node with native predictive depth",
    },
}


def build_scheduled_production_depth_input(
    *,
    scheduled_production_identity: Mapping[str, Any],
    run_id: str,
    guard_purpose_declarations: list[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a distributed target-native predictive mesh for a declared run."""

    if not run_id.strip():
        raise ValueError("scheduled production requires an exact run_id")
    if not guard_purpose_declarations:
        raise ValueError(
            "scheduled production requires explicit task-model-instance Guard purpose declarations"
        )
    timepoint_ids = [
        "t0", "t32", "t64", "t97", "t129", "t161", "t193", "t226",
        "t258", "t290", "t322", "t354", "t387", "t419", "t451",
        "t483", "t516", "t548", "t580", "t612", "t644", "t677",
        "t709", "t741", "t773", "t806", "t838", "t870", "t902",
        "t934", "t967", "t999",
    ]
    events: list[dict[str, Any]] = []
    for index, timepoint_id in enumerate(timepoint_ids):
        event: dict[str, Any] = {
            "at": timepoint_id,
            "event_id": f"scheduled-event-{index}",
            "initiates": "ready" if index == 0 else "running",
        }
        if index == 0:
            event.update({"branch_id": "b0", "perturbation_id": "p0"})
        if index == 1:
            event["terminates"] = "ready"
        events.append(event)
    mesh_run_id = f"worldguard-scheduled:{run_id}"
    return {
        "case_id": f"scheduled-production:{run_id}",
        "input_origin": "target_native_scheduled_execution",
        "scheduled_production_identity": dict(scheduled_production_identity),
        "mesh": {
            "mesh_id": f"scheduled-predictive-mesh:{run_id}",
            "run_id": mesh_run_id,
            "semantic_coverage": {
                "profile": "predictive",
                "expected_model_node_ids": ["world"],
                "scenario_ids": ["s-base"],
                "holdout_scenario_ids": ["s-hold"],
                "state_ids": [],
                "transition_ids": [],
                "event_ids": [event["event_id"] for event in events],
                "fluent_ids": ["ready", "running"],
                "timepoint_ids": timepoint_ids,
                "branch_ids": ["b0"],
                "perturbation_ids": ["p0"],
                "intervention_ids": ["do-y"],
                "counterfactual_ids": ["cf-y"],
                "horizon": {"start": "t0", "end": "t999", "steps": 1000},
                "axis_dispositions": [
                    {
                        "axis_id": "state",
                        "disposition": "not_applicable",
                        "reason": (
                            "this EventGuard event-calculus rollout does not execute "
                            "a declared state-machine"
                        ),
                        "claim_boundary": (
                            "no state-machine state execution is claimed by this rollout"
                        ),
                    },
                    {
                        "axis_id": "transition",
                        "disposition": "not_applicable",
                        "reason": (
                            "this EventGuard event-calculus rollout does not execute "
                            "declared transition specifications"
                        ),
                        "claim_boundary": (
                            "no state-machine transition execution is claimed by this rollout"
                        ),
                    },
                    {
                        "axis_id": "event",
                        "disposition": "required",
                        "observation_field": "executed_event_ids",
                        "claim_boundary": "exact events executed in the bounded rollout",
                    },
                    {
                        "axis_id": "fluent",
                        "disposition": "required",
                        "observation_field": "reached_fluent_ids",
                        "claim_boundary": "exact fluents reached in the bounded rollout",
                    },
                    {
                        "axis_id": "branch",
                        "disposition": "required",
                        "observation_field": "executed_branch_ids",
                        "claim_boundary": "exact branches exercised in the bounded rollout",
                    },
                    {
                        "axis_id": "perturbation",
                        "disposition": "required",
                        "observation_field": "executed_perturbation_ids",
                        "claim_boundary": "exact perturbations exercised in the bounded rollout",
                    },
                    {
                        "axis_id": "intervention",
                        "disposition": "required",
                        "observation_field": "executed_intervention_ids",
                        "claim_boundary": "exact interventions evaluated in the bounded rollout",
                    },
                    {
                        "axis_id": "counterfactual",
                        "disposition": "required",
                        "observation_field": "executed_counterfactual_ids",
                        "claim_boundary": "exact counterfactuals evaluated in the bounded rollout",
                    },
                ],
            },
            "nodes": [
                {
                    "model_id": "world",
                    "authority": {"owns": ["event", "causal"]},
                    "contract": {
                        "contract_id": f"scheduled-predictive-contract:{run_id}",
                        "run_id": mesh_run_id,
                        "claim": {
                            "claim_id": "forecast-claim",
                            "text": "forecast state under declared scenarios",
                            "target_guards": ["EventGuard", "CausalGuard"],
                            "atoms": [
                                {
                                    "atom_id": "forecast-atom",
                                    "text": "state changes under intervention",
                                    "requested_semantics": ["event", "causal"],
                                    "predictive_intent": True,
                                }
                            ],
                        },
                        "world_model": {
                            "model_id": f"scheduled-world-model:{run_id}",
                            "model_version": "v1",
                        },
                        "guard_purpose_declarations": [
                            dict(item) for item in guard_purpose_declarations
                        ],
                        "inputs": {
                            "variable_observations": {"y": timepoint_ids},
                            "events": events,
                            "causal_model": {
                                "variables": ["y"],
                                "equations": {"y": "x * 2"},
                                "exogenous": ["x"],
                                "graph": [],
                                "scenarios": {"s-base": {"x": 1}},
                                "holdout_scenarios": {"s-hold": {"x": 3}},
                                "interventions": [
                                    {
                                        "intervention_id": "do-y",
                                        "scenario_id": "s-base",
                                        "set": {"y": 10},
                                    }
                                ],
                                "counterfactuals": [
                                    {
                                        "counterfactual_id": "cf-y",
                                        "intervention_id": "do-y",
                                        "query": "y",
                                    }
                                ],
                            },
                        },
                    },
                }
            ],
        },
    }


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest().upper()


def target_native_policy_fingerprints() -> dict[str, str]:
    """Return identities for WorldGuard-owned coverage policies."""

    return {
        universe_id: _sha256(definition)
        for universe_id, definition in TARGET_NATIVE_POLICY_DEFINITIONS.items()
    }


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


def _coverage_scope(complete: bool, scope: str) -> list[str]:
    return [scope] if complete else [f"{scope}:incomplete"]


def _node_coverage(mesh: ModelMeshContract, node_id: str) -> SemanticCoverageContract:
    raw = mesh.semantic_coverage.per_model_node.get(node_id)
    if raw is None:
        return mesh.semantic_coverage
    merged = mesh.semantic_coverage.to_dict()
    merged.pop("per_model_node", None)
    merged.update(raw)
    return SemanticCoverageContract.from_dict(merged, default_model_node_ids=[node_id])


def _output_ids(
    report: Any,
    node_id: str,
    field: str,
    *,
    guard_id: str | None = None,
) -> set[str]:
    result: set[str] = set()
    for receipt in report.semantic_receipts:
        if receipt.node_id != node_id or (
            guard_id is not None and receipt.guard != guard_id
        ):
            continue
        value = receipt.outputs.get(field, [])
        if isinstance(value, Mapping):
            result.update(str(key) for key in value)
        elif isinstance(value, (list, tuple, set)):
            result.update(str(item) for item in value)
        elif value not in (None, ""):
            result.add(str(value))
    return result


def _object_scope_attestation(
    *,
    discovery_algorithm_id: str,
    discovery_input_fingerprint: str,
    discovered_object_ids: list[str],
    declared_object_ids: list[str],
    excluded_objects: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "worldguard.object_scope_attestation.v1",
        "discovery_algorithm_id": discovery_algorithm_id,
        "discovery_input_fingerprint": discovery_input_fingerprint.upper(),
        "discovered_object_ids": sorted(dict.fromkeys(discovered_object_ids)),
        "declared_object_ids": sorted(dict.fromkeys(declared_object_ids)),
        "excluded_objects": sorted(
            (
                {
                    "object_id": str(row.get("object_id", "")),
                    "reason": str(row.get("reason", "")),
                    "disposition": str(row.get("disposition", "")),
                    "critical": bool(row.get("critical", False)),
                }
                for row in (excluded_objects or [])
            ),
            key=lambda row: row["object_id"],
        ),
    }
    payload["attestation_fingerprint"] = _sha256(payload)
    return payload


def _child_universe_fingerprint(
    *,
    universe_id: str,
    object_id: str,
    eligible_item_ids: list[str],
    target_input_fingerprint: str,
) -> str:
    return _sha256(
        {
            "parent_universe_id": universe_id,
            "owner_id": NATIVE_OWNER_ID,
            "object_id": object_id,
            "discovery_input_fingerprint": target_input_fingerprint,
            "eligible_item_ids": sorted(eligible_item_ids),
        }
    )


def _native_floor_receipt(
    *,
    algorithm_id: str,
    algorithm_input_eligible_count: int,
    algorithm_input_fingerprint: str,
    minimum_selected_count: int,
    minimum_evaluated_count: int,
    minimum_validated_count: int,
    minimum_coverage: float,
    required_strata_ids: list[str],
    precommitted_at: str,
    receipt_ref: str,
) -> dict[str, Any]:
    receipt: dict[str, Any] = {
        "schema_version": "worldguard.native_dynamic_floor.v1",
        "algorithm_id": algorithm_id,
        "algorithm_version": "1.0",
        "algorithm_input_eligible_count": algorithm_input_eligible_count,
        "algorithm_input_fingerprint": algorithm_input_fingerprint,
        "minimum_selected_count": minimum_selected_count,
        "minimum_evaluated_count": minimum_evaluated_count,
        "minimum_validated_count": minimum_validated_count,
        "minimum_coverage": minimum_coverage,
        "required_strata_ids": sorted(dict.fromkeys(required_strata_ids)),
        "precommitted_at": precommitted_at,
        "receipt_ref": receipt_ref,
    }
    precommit = {
        key: receipt[key]
        for key in (
            "schema_version",
            "algorithm_id",
            "algorithm_version",
            "algorithm_input_eligible_count",
            "algorithm_input_fingerprint",
            "minimum_selected_count",
            "minimum_evaluated_count",
            "minimum_validated_count",
            "minimum_coverage",
            "required_strata_ids",
            "precommitted_at",
        )
    }
    receipt["precommit_fingerprint"] = _sha256(precommit)
    receipt["receipt_hash"] = _sha256(
        {
            **precommit,
            "precommit_fingerprint": receipt["precommit_fingerprint"],
            "receipt_ref": receipt["receipt_ref"],
        }
    )
    return receipt


def _time_floor_specs(receipt_payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    quantitative = receipt_payload.get("quantitative_coverage", {})
    if not isinstance(quantitative, Mapping):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for raw_node in quantitative.get("per_model_node_results", []):
        if not isinstance(raw_node, Mapping):
            continue
        node_id = str(raw_node.get("model_node_id", ""))
        raw_time = raw_node.get("timepoint_coverage", {})
        if node_id and isinstance(raw_time, Mapping):
            result[node_id] = dict(raw_time)
        for raw_variable in raw_node.get("per_variable_timepoint_results", []):
            if not isinstance(raw_variable, Mapping):
                continue
            variable_id = str(raw_variable.get("variable_or_signal_id", ""))
            raw_variable_time = raw_variable.get("timepoint_coverage", {})
            if node_id and variable_id and isinstance(raw_variable_time, Mapping):
                result[f"{node_id}:variable:{variable_id}"] = dict(raw_variable_time)
    return result


def _finalize_dynamic_runtime_contracts(
    universes: list[dict[str, Any]],
    *,
    receipt_payload: Mapping[str, Any],
    target_input_fingerprint: str,
    precommitted_at: str,
) -> None:
    actual_input = target_input_fingerprint.upper()
    time_specs = _time_floor_specs(receipt_payload)
    for row in universes:
        prior = dict(row["object_scope_attestation"])
        attestation = _object_scope_attestation(
            discovery_algorithm_id=str(prior["discovery_algorithm_id"]),
            discovery_input_fingerprint=actual_input,
            discovered_object_ids=list(prior["discovered_object_ids"]),
            declared_object_ids=list(prior["declared_object_ids"]),
            excluded_objects=list(prior.get("excluded_objects", [])),
        )
        row["object_scope_attestation"] = attestation
        normalized_items = sorted(
            (
                {
                    "item_id": str(item["item_id"]),
                    "object_id": str(item["object_id"]),
                    "object_class_id": str(item.get("object_class_id", "")).strip(),
                    "stratum_ids": sorted(str(value) for value in item["stratum_ids"]),
                    "critical": bool(item["critical"]),
                    "disposition": str(item.get("disposition", "")).strip(),
                    "reason": str(item.get("reason", "")).strip(),
                    "observation_field": str(
                        item.get("observation_field", "")
                    ).strip(),
                    "claim_boundary": str(item.get("claim_boundary", "")).strip(),
                }
                for item in row["inventory_items"]
            ),
            key=lambda item: item["item_id"],
        )
        if row["universe_id"] == UNIVERSE_TIMEPOINTS:
            object_floor_rows: list[dict[str, Any]] = []
            object_ids = sorted({item["object_id"] for item in normalized_items})
            for object_id in object_ids:
                eligible_ids = [
                    item["item_id"]
                    for item in normalized_items
                    if item["object_id"] == object_id
                ]
                spec = time_specs.get(object_id, {})
                minimum_count = int(spec["effective_minimum_timepoint_count"])
                minimum_count = max(1, min(len(eligible_ids), minimum_count))
                minimum_coverage = float(
                    spec.get(
                        "effective_minimum_timepoint_coverage",
                        minimum_count / len(eligible_ids),
                    )
                )
                required_strata = (
                    ["early", "middle", "late"]
                    if object_id in time_specs
                    else []
                )
                child_fingerprint = _child_universe_fingerprint(
                    universe_id=str(row["universe_id"]),
                    object_id=object_id,
                    eligible_item_ids=eligible_ids,
                    target_input_fingerprint=actual_input,
                )
                object_floor_rows.append(
                    {
                        "object_id": object_id,
                        **_native_floor_receipt(
                            algorithm_id="worldguard.native-sqrt-phase-gap-floor.v1",
                            algorithm_input_eligible_count=len(eligible_ids),
                            algorithm_input_fingerprint=child_fingerprint,
                            minimum_selected_count=minimum_count,
                            minimum_evaluated_count=minimum_count,
                            minimum_validated_count=minimum_count,
                            minimum_coverage=minimum_coverage,
                            required_strata_ids=required_strata,
                            precommitted_at=precommitted_at,
                            receipt_ref=(
                                "native-receipt://worldguard/timepoints/"
                                f"{object_id}"
                            ),
                        ),
                    }
                )
            row["object_native_floor_receipts"] = object_floor_rows
            continue

        inventory_hash = _sha256(
            {
                "items": normalized_items,
                "object_scope_attestation_fingerprint": attestation[
                    "attestation_fingerprint"
                ],
            }
        )
        universe_fingerprint = _sha256(
            {
                "universe_id": row["universe_id"],
                "owner_id": NATIVE_OWNER_ID,
                "target_input_fingerprint": actual_input,
                "target_inventory_hash": inventory_hash,
                "object_scope_attestation_fingerprint": attestation[
                    "attestation_fingerprint"
                ],
            }
        )
        required_strata = sorted(
            {
                stratum_id
                for item in normalized_items
                for stratum_id in item["stratum_ids"]
            }
        )
        row["native_floor_receipt"] = _native_floor_receipt(
            algorithm_id="worldguard.native-exhaustive-floor.v1",
            algorithm_input_eligible_count=len(normalized_items),
            algorithm_input_fingerprint=universe_fingerprint,
            minimum_selected_count=len(normalized_items),
            minimum_evaluated_count=len(normalized_items),
            minimum_validated_count=len(normalized_items),
            minimum_coverage=1.0,
            required_strata_ids=required_strata,
            precommitted_at=precommitted_at,
            receipt_ref=f"native-receipt://worldguard/{row['universe_id']}",
        )


def build_dynamic_depth_universes(
    fixture_path: str | Path,
    *,
    policy_fingerprints: Mapping[str, str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run WorldGuard and expose current per-object predictive coverage items.

    The inventory contains every eligible horizon step for each expected model
    node.  Consequently a 1,000-step object has 1,000 eligible items and one or
    two observations remain visibly shallow even when another object is rich.
    """

    path = Path(fixture_path).resolve()
    fixture = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(fixture, Mapping) or not isinstance(fixture.get("mesh"), Mapping):
        raise ValueError("fixture must contain a mesh object")
    mesh = ModelMeshContract.from_dict(dict(fixture["mesh"]))
    report = run_model_mesh(mesh)
    receipt = report.depth_receipt
    if receipt is None:
        raise ValueError("native WorldGuard mesh report omitted its depth receipt")
    receipt_payload = receipt.to_dict()
    quantitative = receipt.quantitative_coverage

    def policy(universe_id: str) -> str:
        value = str(policy_fingerprints.get(universe_id, "")).upper()
        if len(value) != 64:
            raise ValueError(f"policy fingerprint missing for {universe_id}")
        return value

    expected_children = set(receipt.expected_semantic_children)
    executed_children = set(receipt.executed_semantic_children)
    passed_children = {
        f"{row.node_id}:{row.guard}"
        for row in report.semantic_receipts
        if row.status == SemanticStatus.PASS
    }
    semantic_items = []
    for child_id in sorted(expected_children):
        node_id, guard_id = (
            child_id.rsplit(":", 1) if ":" in child_id else (child_id, "missing")
        )
        semantic_items.append(
            {
                "item_id": f"semantic-child:{child_id}",
                "object_id": node_id or "missing-model-node",
                "object_class_id": "semantic_model_node",
                "stratum_ids": ["semantic-child", f"guard:{guard_id or 'missing'}"],
                "critical": True,
            }
        )
    if not semantic_items:
        semantic_items.append(
            {
                "item_id": "semantic-child:<missing>",
                "object_id": "missing-model-node",
                "object_class_id": "missing_semantic_model_node",
                "stratum_ids": ["semantic-child"],
                "critical": True,
            }
        )
    semantic_selected = [row["item_id"] for row in semantic_items]
    semantic_evaluated = [
        f"semantic-child:{child_id}"
        for child_id in sorted(expected_children.intersection(executed_children))
    ]
    semantic_validated = [
        f"semantic-child:{child_id}"
        for child_id in sorted(expected_children.intersection(passed_children))
    ]

    node_results = {
        str(row.get("model_node_id", "")): row
        for row in quantitative.get("per_model_node_results", [])
        if isinstance(row, Mapping) and str(row.get("model_node_id", ""))
    }
    time_items: list[dict[str, Any]] = []
    time_selected: list[str] = []
    native_policy_items: list[dict[str, Any]] = []
    native_policy_validated: list[str] = []

    def append_time_object(
        *,
        object_id: str,
        object_class_id: str,
        time_result: Mapping[str, Any],
        horizon: Mapping[str, Any],
    ) -> None:
        try:
            steps = int(time_result.get("horizon_step_count", 0))
        except (TypeError, ValueError):
            steps = 0
        steps = max(0, steps)
        start = str(horizon.get("start", ""))
        end = str(horizon.get("end", ""))
        for index in range(steps):
            fraction = index / (steps - 1) if steps > 1 else 0.0
            phase = (
                "early"
                if fraction < (1 / 3)
                else ("middle" if fraction < (2 / 3) else "late")
            )
            time_items.append(
                {
                    "item_id": f"horizon-step:{object_id}:{index}",
                    "object_id": object_id,
                    "object_class_id": object_class_id,
                    "stratum_ids": [phase],
                    "critical": index in {0, steps - 1},
                }
            )
        observed = time_result.get("observed_timepoint_ids", [])
        if isinstance(observed, (list, tuple, set)) and steps > 1 and start and end:
            for raw in observed:
                position = _time_position(str(raw), start, end)
                if position is None or not 0 <= position <= 1:
                    continue
                index = min(steps - 1, max(0, round(position * (steps - 1))))
                time_selected.append(f"horizon-step:{object_id}:{index}")

    for node_id in receipt.expected_model_nodes:
        node_result = node_results.get(node_id, {})
        time_result = node_result.get("timepoint_coverage", {})
        if not isinstance(time_result, Mapping):
            time_result = {}
        coverage = _node_coverage(mesh, node_id)
        horizon = coverage.horizon
        append_time_object(
            object_id=node_id,
            object_class_id="predictive_horizon",
            time_result=time_result,
            horizon=horizon,
        )
        for raw_variable in node_result.get("per_variable_timepoint_results", []):
            if not isinstance(raw_variable, Mapping):
                continue
            variable_id = str(raw_variable.get("variable_or_signal_id", ""))
            variable_time = raw_variable.get("timepoint_coverage", {})
            if not variable_id or not isinstance(variable_time, Mapping):
                continue
            append_time_object(
                object_id=f"{node_id}:variable:{variable_id}",
                object_class_id="predictive_variable_or_signal",
                time_result=variable_time,
                horizon=horizon,
            )
        policy_item_id = f"native-policy:{node_id}"
        native_policy_items.append(
            {
                "item_id": policy_item_id,
                "object_id": node_id,
                "object_class_id": "predictive_model_node",
                "stratum_ids": ["native-policy"],
                "critical": True,
            }
        )
        if node_result.get("passed") is True:
            native_policy_validated.append(policy_item_id)
    time_selected = list(dict.fromkeys(time_selected))
    if not time_items:
        time_items.append(
            {
                "item_id": "horizon-step:<missing>:0",
                "object_id": "missing-predictive-horizon",
                "object_class_id": "missing_predictive_horizon",
                "stratum_ids": ["early"],
                "critical": True,
            }
        )
    if not native_policy_items:
        native_policy_items.append(
            {
                "item_id": "native-policy:<missing>",
                "object_id": "missing-model-node",
                "object_class_id": "missing_predictive_model_node",
                "stratum_ids": ["native-policy"],
                "critical": True,
            }
        )

    scenario_items: list[dict[str, Any]] = []
    scenario_observed: list[str] = []
    axis_items: list[dict[str, Any]] = []
    axis_evaluated: list[str] = []
    axis_validated: list[str] = []
    for node_id in receipt.expected_model_nodes:
        coverage = _node_coverage(mesh, node_id)
        required_guards = list(receipt.required_guards.get(node_id, []))
        if not required_guards:
            required_guards = ["<missing-guard>"]
        for guard_id in required_guards:
            scenarios = {
                "scenario": (
                    coverage.scenario_ids,
                    _output_ids(
                        report,
                        node_id,
                        "executed_scenario_ids",
                        guard_id=guard_id,
                    ),
                ),
                "holdout": (
                    coverage.holdout_scenario_ids,
                    _output_ids(
                        report,
                        node_id,
                        "executed_holdout_scenario_ids",
                        guard_id=guard_id,
                    ),
                ),
            }
            for kind, (expected_ids, observed_ids) in scenarios.items():
                for value in expected_ids:
                    item_id = f"{kind}:{node_id}:{guard_id}:{value}"
                    scenario_items.append(
                        {
                            "item_id": item_id,
                            "object_id": f"{node_id}:{guard_id}",
                            "object_class_id": "scenario_portfolio",
                            "stratum_ids": [kind],
                            "critical": True,
                        }
                    )
                    if value in observed_ids:
                        scenario_observed.append(item_id)
        raw_axis_results = node_results.get(node_id, {}).get("axis_results", [])
        if not isinstance(raw_axis_results, list) or not raw_axis_results:
            item_id = f"axis-contract:{node_id}:unavailable"
            axis_items.append(
                {
                    "item_id": item_id,
                    "object_id": f"{node_id}:axis-contract",
                    "object_class_id": "unavailable_predictive_axis_contract",
                    "stratum_ids": ["axis:contract"],
                    "critical": True,
                    "disposition": "invalid",
                    "reason": "predictive axis results were unavailable",
                    "observation_field": "",
                    "claim_boundary": "no predictive-axis claim is licensed",
                }
            )
            axis_evaluated.append(item_id)
            continue
        for raw_axis_result in raw_axis_results:
            if not isinstance(raw_axis_result, Mapping):
                continue
            axis = str(raw_axis_result.get("axis_id", ""))
            disposition = str(raw_axis_result.get("disposition", ""))
            reason = str(raw_axis_result.get("reason", ""))
            observation_field = str(
                raw_axis_result.get("observation_field", "")
            )
            claim_boundary = str(raw_axis_result.get("claim_boundary", ""))
            expected_ids = {
                str(value) for value in raw_axis_result.get("expected_ids", [])
            }
            observed_ids = {
                str(value) for value in raw_axis_result.get("observed_ids", [])
            }
            passed = raw_axis_result.get("passed") is True
            if disposition == "not_applicable":
                item_id = f"axis:{axis}:{node_id}:not_applicable"
                axis_items.append(
                    {
                        "item_id": item_id,
                        "object_id": f"{node_id}:{axis}",
                        "object_class_id": f"{axis}_axis_disposition",
                        "stratum_ids": [f"axis:{axis}", "not_applicable"],
                        "critical": True,
                        "disposition": disposition,
                        "reason": reason,
                        "observation_field": "",
                        "claim_boundary": claim_boundary,
                    }
                )
                axis_evaluated.append(item_id)
                if passed and not expected_ids and not observed_ids:
                    axis_validated.append(item_id)
                continue
            if disposition != "required":
                item_id = f"axis-contract:{axis}:{node_id}:invalid"
                axis_items.append(
                    {
                        "item_id": item_id,
                        "object_id": f"{node_id}:{axis}",
                        "object_class_id": "invalid_predictive_axis_disposition",
                        "stratum_ids": [f"axis:{axis}", "invalid"],
                        "critical": True,
                        "disposition": disposition or "invalid",
                        "reason": reason or "predictive axis disposition is invalid",
                        "observation_field": observation_field,
                        "claim_boundary": claim_boundary,
                    }
                )
                axis_evaluated.append(item_id)
                continue
            for value in sorted(expected_ids):
                item_id = f"axis:{axis}:{node_id}:{value}"
                axis_items.append(
                    {
                        "item_id": item_id,
                        "object_id": f"{node_id}:{axis}",
                        "object_class_id": f"{axis}_axis",
                        "stratum_ids": [f"axis:{axis}", "required"],
                        "critical": True,
                        "disposition": disposition,
                        "reason": "",
                        "observation_field": observation_field,
                        "claim_boundary": claim_boundary,
                    }
                )
                axis_evaluated.append(item_id)
                if passed and value in observed_ids:
                    axis_validated.append(item_id)
    if not scenario_items:
        scenario_items.append(
            {
                "item_id": "scenario:<missing>",
                "object_id": "missing-model-node",
                "object_class_id": "missing_scenario_portfolio",
                "stratum_ids": ["scenario"],
                "critical": True,
            }
        )
    if not axis_items:
        axis_items.append(
            {
                "item_id": "axis-contract:no-model-node:unavailable",
                "object_id": "no-model-node:axis-contract",
                "object_class_id": "unavailable_predictive_axis_contract",
                "stratum_ids": ["axis:contract"],
                "critical": True,
                "disposition": "invalid",
                "reason": "no model node produced predictive axis results",
                "observation_field": "",
                "claim_boundary": "no predictive-axis claim is licensed",
            }
        )
        axis_evaluated.append("axis-contract:no-model-node:unavailable")

    claim_items: list[dict[str, Any]] = []
    claim_validated: list[str] = []
    for atom in receipt.claim_atoms:
        node_id = str(atom.get("node_id", "missing-model-node"))
        atom_id = str(atom.get("atom_id", "<missing>"))
        item_id = f"claim-atom:{node_id}:{atom_id}"
        claim_items.append(
            {
                "item_id": item_id,
                "object_id": node_id,
                "object_class_id": "predictive_claim",
                "stratum_ids": ["claim-scope"],
                "critical": True,
            }
        )
        if node_results.get(node_id, {}).get("passed") is True:
            claim_validated.append(item_id)
    if not claim_items:
        claim_items.append(
            {
                "item_id": "claim-atom:<missing>",
                "object_id": "missing-model-node",
                "object_class_id": "missing_predictive_claim",
                "stratum_ids": ["claim-scope"],
                "critical": True,
            }
        )

    time_gap_markers = ("horizon", "timepoint", "time_stratum")
    time_complete = bool(node_results) and all(
        not any(
            marker in str(gap)
            for gap in row.get("gaps", [])
            for marker in time_gap_markers
        )
        for row in node_results.values()
    )

    universes = [
        {
            "universe_id": UNIVERSE_SEMANTIC_CHILDREN,
            "inventory_items": semantic_items,
            "selected_item_ids": semantic_selected,
            "evaluated_item_ids": semantic_evaluated,
            "validated_item_ids": semantic_validated,
            "requested_claim_scope": ["semantic_children"],
            "covered_claim_scope": _coverage_scope(
                len(semantic_validated) == len(semantic_items), "semantic_children"
            ),
            "policy_fingerprint": policy(UNIVERSE_SEMANTIC_CHILDREN),
        },
        {
            "universe_id": UNIVERSE_TIMEPOINTS,
            "inventory_items": time_items,
            "selected_item_ids": time_selected,
            "evaluated_item_ids": time_selected,
            "validated_item_ids": time_selected,
            "requested_claim_scope": ["predictive_time_horizon"],
            "covered_claim_scope": _coverage_scope(
                time_complete, "predictive_time_horizon"
            ),
            "policy_fingerprint": policy(UNIVERSE_TIMEPOINTS),
        },
        {
            "universe_id": UNIVERSE_SCENARIO_PORTFOLIO,
            "inventory_items": scenario_items,
            "selected_item_ids": [row["item_id"] for row in scenario_items],
            "evaluated_item_ids": scenario_observed,
            "validated_item_ids": scenario_observed,
            "requested_claim_scope": ["scenario_and_holdout"],
            "covered_claim_scope": _coverage_scope(
                len(scenario_observed) == len(scenario_items), "scenario_and_holdout"
            ),
            "policy_fingerprint": policy(UNIVERSE_SCENARIO_PORTFOLIO),
        },
        {
            "universe_id": UNIVERSE_PREDICTIVE_AXES,
            "inventory_items": axis_items,
            "selected_item_ids": [row["item_id"] for row in axis_items],
            "evaluated_item_ids": axis_evaluated,
            "validated_item_ids": axis_validated,
            "requested_claim_scope": ["predictive_axes"],
            "covered_claim_scope": _coverage_scope(
                len(axis_validated) == len(axis_items), "predictive_axes"
            ),
            "policy_fingerprint": policy(UNIVERSE_PREDICTIVE_AXES),
        },
        {
            "universe_id": UNIVERSE_NATIVE_POLICY,
            "inventory_items": native_policy_items,
            "selected_item_ids": [row["item_id"] for row in native_policy_items],
            "evaluated_item_ids": [row["item_id"] for row in native_policy_items],
            "validated_item_ids": native_policy_validated,
            "requested_claim_scope": ["native_predictive_policy"],
            "covered_claim_scope": _coverage_scope(
                len(native_policy_validated) == len(native_policy_items),
                "native_predictive_policy",
            ),
            "policy_fingerprint": policy(UNIVERSE_NATIVE_POLICY),
        },
        {
            "universe_id": UNIVERSE_CLAIM_SCOPE,
            "inventory_items": claim_items,
            "selected_item_ids": [row["item_id"] for row in claim_items],
            "evaluated_item_ids": [row["item_id"] for row in claim_items],
            "validated_item_ids": claim_validated,
            "requested_claim_scope": ["predictive_claim_scope"],
            "covered_claim_scope": _coverage_scope(
                bool(receipt.predictive_claim_licensed), "predictive_claim_scope"
            ),
            "policy_fingerprint": policy(UNIVERSE_CLAIM_SCOPE),
        },
    ]
    for universe in universes:
        universe["selected_item_ids"] = list(universe["selected_item_ids"])
        universe["evaluated_item_ids"] = list(universe["evaluated_item_ids"])
        universe["validated_item_ids"] = list(universe["validated_item_ids"])
        # Empty selected/evaluated/validated sets are exact shallow evidence.
        # Never manufacture a bridge-health witness merely to satisfy a
        # transport schema.
        object_ids = sorted(
            {
                str(item["object_id"])
                for item in universe["inventory_items"]
                if str(item.get("object_id", ""))
            }
        )
        excluded_objects: list[dict[str, Any]] = []
        discovered_object_ids = list(object_ids)
        discovery_algorithm_id = "worldguard.native-object-universe.v1"
        if universe["universe_id"] == UNIVERSE_SEMANTIC_CHILDREN:
            discovery_algorithm_id = "worldguard.semantic-node-discovery.v1"
            discovered_object_ids = list(
                dict.fromkeys([*receipt.discovered_model_nodes, *object_ids])
            )
            for raw in receipt.excluded_model_nodes:
                node_id = str(raw.get("model_node_id", ""))
                if (
                    node_id
                    and node_id in receipt.discovered_model_nodes
                    and node_id not in object_ids
                    and str(raw.get("reason", ""))
                    and str(raw.get("disposition", ""))
                    in {
                        "not_applicable",
                        "outside_requested_scope",
                        "duplicate_alias",
                        "invalid_input",
                    }
                    and raw.get("critical") is False
                ):
                    excluded_objects.append(
                        {
                            "object_id": node_id,
                            "reason": str(raw["reason"]),
                            "disposition": str(raw["disposition"]),
                            "critical": False,
                        }
                    )
        universe["object_scope_attestation"] = _object_scope_attestation(
            discovery_algorithm_id=discovery_algorithm_id,
            discovery_input_fingerprint=receipt.coverage_fingerprint,
            discovered_object_ids=discovered_object_ids,
            declared_object_ids=object_ids,
            excluded_objects=excluded_objects,
        )
    return receipt_payload, universes


def build_target_native_depth_envelope(
    fixture_path: str | Path,
    *,
    run_binding: Mapping[str, Any],
    check_id: str,
    policy_fingerprints: Mapping[str, str],
) -> dict[str, Any]:
    receipt_payload, universes = build_dynamic_depth_universes(
        fixture_path,
        policy_fingerprints=policy_fingerprints,
    )
    created_at = str(receipt_payload.get("generated_at", ""))
    if not created_at:
        raise ValueError("native WorldGuard depth receipt omitted generated_at")
    _finalize_dynamic_runtime_contracts(
        universes,
        receipt_payload=receipt_payload,
        target_input_fingerprint=str(run_binding["target_input_fingerprint"]),
        precommitted_at=created_at,
    )
    predictive_claim_licensed = bool(
        receipt_payload.get("predictive_claim_licensed")
    )
    native_obligation_evidence = [
        {
            **dict(row),
            "status": "pass" if predictive_claim_licensed else "blocked",
        }
        for row in receipt_payload.get("native_obligation_evidence", [])
        if isinstance(row, Mapping)
    ]
    retired_binding_fields = sorted(
        field
        for field in (
            "evidence_domain",
            "scheduled_production_identity",
            "release_gate_identity",
        )
        if field in run_binding
    )
    if retired_binding_fields:
        raise ValueError(
            "retired native-depth run binding fields are forbidden: "
            + ", ".join(retired_binding_fields)
        )
    evidence_context = run_binding.get("evidence_context")
    if not isinstance(evidence_context, Mapping):
        raise ValueError("native-depth evidence_context must be an object")
    if set(evidence_context) != {"domain", "identity"}:
        raise ValueError("native-depth evidence_context must use the exact current shape")
    evidence_domain = str(evidence_context.get("domain", ""))
    if evidence_domain not in {
        "capability_validation",
        "scheduled_production",
        "release_gate",
    }:
        raise ValueError("native-depth evidence domain is unsupported")
    evidence_identity = evidence_context.get("identity")
    if not isinstance(evidence_identity, Mapping) or not evidence_identity:
        raise ValueError("native-depth evidence identity must be a non-empty object")
    normalized_evidence_context = {
        "domain": evidence_domain,
        "identity": dict(evidence_identity),
    }
    payload = {
        "schema_version": TARGET_NATIVE_DEPTH_SCHEMA,
        "target_skill_id": TARGET_SKILL_ID,
        "native_route_id": NATIVE_ROUTE_ID,
        "run_id": str(run_binding["run_id"]),
        "contract_hash": str(run_binding["contract_hash"]),
        "check_id": check_id,
        "request_fingerprint": str(run_binding["request_fingerprint"]),
        "target_input_fingerprint": str(run_binding["target_input_fingerprint"]),
        "target_obligation_ids": sorted(
            {
                obligation_id
                for row in native_obligation_evidence
                for obligation_id in row.get("target_obligation_ids", [])
            }
        ),
        "evidence_context": normalized_evidence_context,
        "native_owner_id": NATIVE_OWNER_ID,
        "native_receipt_id": str(receipt_payload["receipt_id"]),
        "native_receipt_hash": _sha256(receipt_payload),
        "native_receipt_created_at": created_at,
        "universes": universes,
        "native_obligation_evidence": native_obligation_evidence,
    }
    payload["evidence_payload_hash"] = _sha256(payload)
    return payload
