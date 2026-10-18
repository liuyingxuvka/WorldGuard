from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections.abc import Mapping
from math import ceil, sqrt
import re
from typing import Any

from .contracts import (
    GuardContract,
    claim_predictive_intent,
    claim_semantics,
    derive_required_guards,
    unmapped_claim_semantics,
)
from .ledgers import LedgerEntry, ledger_entry
from .kernel import run_worldguard
from .qualification import QualificationContext
from .reports import GuardedReport
from .semantic import (
    NativeDepthReceipt,
    ProviderStatus,
    SemanticExecutionReceipt,
    SemanticStatus,
    aggregate_provider_status,
    aggregate_semantic_status,
    fingerprint_mesh,
    _semantic_consumed_inputs,
    _variable_timepoint_map,
)
from .status import GuardStatus, aggregate_statuses, coerce_status


FRESHNESS_STATUSES = {"current", "stale", "unknown"}
EDGE_RELATIONS = {
    "parent_child",
    "depends_on",
    "refines",
    "replaces",
    "conflicts_with",
    "consumes_output_of",
    "same_world_version",
    "supersedes",
}

CLOSED_MODEL_EXCLUSION_DISPOSITIONS = {
    "not_applicable",
    "outside_requested_scope",
    "duplicate_alias",
    "invalid_input",
}
CYCLE_RELATIONS = {
    "parent_child",
    "depends_on",
    "refines",
    "replaces",
    "consumes_output_of",
    "supersedes",
}
TRANSFER_RELATIONS = {"parent_child", "consumes_output_of"}
PORT_CARDINALITIES = {"one", "optional", "many"}

PREDICTIVE_AXIS_IDS = (
    "state",
    "transition",
    "event",
    "fluent",
    "branch",
    "perturbation",
    "intervention",
    "counterfactual",
)
PREDICTIVE_AXIS_EXPECTED_FIELDS = {
    "state": "state_ids",
    "transition": "transition_ids",
    "event": "event_ids",
    "fluent": "fluent_ids",
    "branch": "branch_ids",
    "perturbation": "perturbation_ids",
    "intervention": "intervention_ids",
    "counterfactual": "counterfactual_ids",
}
PREDICTIVE_AXIS_OBSERVATION_FIELDS = {
    "state": ("executed_state_ids",),
    "transition": ("executed_transition_ids",),
    "event": ("executed_event_ids",),
    "fluent": (
        "reached_fluent_ids",
        "active_fluent_ids",
        "final_fluent_ids_by_scenario",
    ),
    "branch": ("executed_branch_ids",),
    "perturbation": ("executed_perturbation_ids",),
    "intervention": ("executed_intervention_ids",),
    "counterfactual": ("executed_counterfactual_ids",),
}


@dataclass(frozen=True)
class ModelAuthority:
    owns: list[str] = field(default_factory=list)
    excludes: list[str] = field(default_factory=list)
    scope_limits: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "ModelAuthority":
        data = data or {}
        return cls(
            owns=list(data.get("owns", [])),
            excludes=list(data.get("excludes", [])),
            scope_limits=list(data.get("scope_limits", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "owns": self.owns,
            "excludes": self.excludes,
            "scope_limits": self.scope_limits,
        }


@dataclass(frozen=True)
class ModelPort:
    port_id: str
    value_type: str
    cardinality: str = "one"

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelPort":
        allowed = {"port_id", "value_type", "cardinality"}
        unknown = sorted(set(data).difference(allowed))
        if unknown:
            raise ValueError("model port has unknown fields: " + ", ".join(unknown))
        port_id = str(data.get("port_id", "")).strip()
        value_type = str(data.get("value_type", "")).strip()
        cardinality = str(data.get("cardinality", "one")).strip()
        if not port_id or not value_type:
            raise ValueError("model port requires port_id and value_type")
        if cardinality not in PORT_CARDINALITIES:
            raise ValueError(f"unknown model port cardinality: {cardinality}")
        return cls(
            port_id=port_id,
            value_type=value_type,
            cardinality=cardinality,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "port_id": self.port_id,
            "value_type": self.value_type,
            "cardinality": self.cardinality,
        }


@dataclass(frozen=True)
class ModelNode:
    model_id: str
    model_version: str = ""
    model_kind: str = "world_model"
    authority: ModelAuthority = field(default_factory=ModelAuthority)
    freshness_status: str = "current"
    input_ports: list[ModelPort] = field(default_factory=list)
    output_ports: list[ModelPort] = field(default_factory=list)
    contract: GuardContract | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelNode":
        contract_data = data.get("contract")
        freshness_status = str(data.get("freshness_status", "current"))
        if freshness_status not in FRESHNESS_STATUSES:
            freshness_status = "unknown"
        input_ports = [ModelPort.from_dict(item) for item in data.get("input_ports", [])]
        output_ports = [ModelPort.from_dict(item) for item in data.get("output_ports", [])]
        all_port_ids = [port.port_id for port in [*input_ports, *output_ports]]
        if len(all_port_ids) != len(set(all_port_ids)):
            raise ValueError(
                f"model node {data.get('model_id', '')} has duplicate port ids"
            )
        return cls(
            model_id=str(data.get("model_id", "")),
            model_version=str(data.get("model_version", "")),
            model_kind=str(data.get("model_kind", "world_model")),
            authority=ModelAuthority.from_dict(data.get("authority")),
            freshness_status=freshness_status,
            input_ports=input_ports,
            output_ports=output_ports,
            contract=GuardContract.from_dict(contract_data) if contract_data else None,
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "model_kind": self.model_kind,
            "authority": self.authority.to_dict(),
            "freshness_status": self.freshness_status,
            "input_ports": [port.to_dict() for port in self.input_ports],
            "output_ports": [port.to_dict() for port in self.output_ports],
        }
        if self.contract:
            data["contract"] = self.contract.to_dict()
        return data


@dataclass(frozen=True)
class ModelPortMapping:
    mapping_id: str
    source_port_id: str
    target_port_id: str

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelPortMapping":
        allowed = {"mapping_id", "source_port_id", "target_port_id"}
        unknown = sorted(set(data).difference(allowed))
        if unknown:
            raise ValueError(
                "model port mapping has unknown fields: " + ", ".join(unknown)
            )
        mapping_id = str(data.get("mapping_id", "")).strip()
        source_port_id = str(data.get("source_port_id", "")).strip()
        target_port_id = str(data.get("target_port_id", "")).strip()
        if not mapping_id or not source_port_id or not target_port_id:
            raise ValueError(
                "model port mapping requires mapping_id, source_port_id, and target_port_id"
            )
        return cls(mapping_id, source_port_id, target_port_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mapping_id": self.mapping_id,
            "source_port_id": self.source_port_id,
            "target_port_id": self.target_port_id,
        }


@dataclass(frozen=True)
class ModelEdge:
    edge_id: str
    source_model_id: str
    target_model_id: str
    relation: str
    port_mappings: list[ModelPortMapping] = field(default_factory=list)
    allowed_use: list[str] = field(default_factory=list)
    forbidden_use: list[str] = field(default_factory=list)
    read_only: bool = True
    requires_current_source: bool = True

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelEdge":
        if "output_refs" in data:
            raise ValueError(
                "model edge output_refs is retired; use exact port_mappings"
            )
        relation = str(data.get("relation", "")).strip()
        if relation not in EDGE_RELATIONS:
            raise ValueError(
                f"unknown model edge relation for {data.get('edge_id', '')}: {relation or '<missing>'}"
            )
        port_mappings = [
            ModelPortMapping.from_dict(item) for item in data.get("port_mappings", [])
        ]
        mapping_ids = [mapping.mapping_id for mapping in port_mappings]
        mapping_pairs = [
            (mapping.source_port_id, mapping.target_port_id)
            for mapping in port_mappings
        ]
        if len(mapping_ids) != len(set(mapping_ids)) or len(mapping_pairs) != len(
            set(mapping_pairs)
        ):
            raise ValueError(
                f"model edge {data.get('edge_id', '')} has duplicate port mappings"
            )
        if relation in TRANSFER_RELATIONS and not port_mappings:
            raise ValueError(
                f"model edge {data.get('edge_id', '')} relation {relation} requires port_mappings"
            )
        if relation not in TRANSFER_RELATIONS and port_mappings:
            raise ValueError(
                f"model edge {data.get('edge_id', '')} relation {relation} does not transfer ports"
            )
        return cls(
            edge_id=str(data.get("edge_id", "")),
            source_model_id=str(data.get("source_model_id", "")),
            target_model_id=str(data.get("target_model_id", "")),
            relation=relation,
            port_mappings=port_mappings,
            allowed_use=list(data.get("allowed_use", [])),
            forbidden_use=list(data.get("forbidden_use", [])),
            read_only=bool(data.get("read_only", True)),
            requires_current_source=bool(data.get("requires_current_source", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_model_id": self.source_model_id,
            "target_model_id": self.target_model_id,
            "relation": self.relation,
            "port_mappings": [mapping.to_dict() for mapping in self.port_mappings],
            "allowed_use": self.allowed_use,
            "forbidden_use": self.forbidden_use,
            "read_only": self.read_only,
            "requires_current_source": self.requires_current_source,
        }


@dataclass(frozen=True)
class WorldStateSnapshot:
    snapshot_id: str
    model_ids: list[str] = field(default_factory=list)
    status: str = "current"
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorldStateSnapshot":
        return cls(
            snapshot_id=str(data.get("snapshot_id", "")),
            model_ids=list(data.get("model_ids", [])),
            status=str(data.get("status", "current")),
            notes=list(data.get("notes", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "model_ids": self.model_ids,
            "status": self.status,
            "notes": self.notes,
        }


def _ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _time_strata_from_value(value: Any) -> dict[str, list[str]]:
    if isinstance(value, Mapping):
        return {
            str(stratum_id): _ordered_unique([str(item) for item in items])
            for stratum_id, items in value.items()
            if isinstance(items, (list, tuple, set))
        }
    if isinstance(value, list):
        return {
            str(row.get("stratum_id", "")): _ordered_unique(
                [str(item) for item in row.get("timepoint_ids", [])]
            )
            for row in value
            if isinstance(row, Mapping) and str(row.get("stratum_id", ""))
        }
    return {}


@dataclass(frozen=True)
class PredictiveAxisDisposition:
    axis_id: str
    disposition: str
    observation_field: str = ""
    reason: str = ""
    claim_boundary: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PredictiveAxisDisposition":
        allowed = {
            "axis_id",
            "disposition",
            "observation_field",
            "reason",
            "claim_boundary",
        }
        unknown = sorted(set(data).difference(allowed))
        if unknown:
            raise ValueError(
                "predictive axis disposition has unknown fields: "
                + ", ".join(unknown)
            )
        return cls(
            axis_id=str(data.get("axis_id", "")).strip(),
            disposition=str(data.get("disposition", "")).strip(),
            observation_field=str(data.get("observation_field", "")).strip(),
            reason=str(data.get("reason", "")).strip(),
            claim_boundary=str(data.get("claim_boundary", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "axis_id": self.axis_id,
            "disposition": self.disposition,
            "claim_boundary": self.claim_boundary,
        }
        if self.observation_field:
            result["observation_field"] = self.observation_field
        if self.reason:
            result["reason"] = self.reason
        return result


@dataclass(frozen=True)
class SemanticCoverageContract:
    profile: str = "bounded"
    expected_model_node_ids: list[str] = field(default_factory=list)
    expected_model_node_ids_explicit: bool = False
    excluded_model_nodes: list[dict[str, Any]] = field(default_factory=list)
    expected_semantic_child_ids: list[str] = field(default_factory=list)
    scenario_ids: list[str] = field(default_factory=list)
    holdout_scenario_ids: list[str] = field(default_factory=list)
    state_ids: list[str] = field(default_factory=list)
    transition_ids: list[str] = field(default_factory=list)
    event_ids: list[str] = field(default_factory=list)
    fluent_ids: list[str] = field(default_factory=list)
    branch_ids: list[str] = field(default_factory=list)
    perturbation_ids: list[str] = field(default_factory=list)
    intervention_ids: list[str] = field(default_factory=list)
    counterfactual_ids: list[str] = field(default_factory=list)
    horizon: dict[str, Any] = field(default_factory=dict)
    timepoint_ids: list[str] = field(default_factory=list)
    time_strata: dict[str, list[str]] = field(default_factory=dict)
    minimum_timepoint_count: Any = 0
    minimum_timepoint_coverage: Any = 0.0
    axis_dispositions: list[PredictiveAxisDisposition] = field(default_factory=list)
    per_model_node: dict[str, dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any] | None,
        *,
        default_model_node_ids: list[str] | None = None,
    ) -> "SemanticCoverageContract":
        data = data or {}
        retired = sorted(
            {
                "expected_node_ids",
                "excluded_nodes",
                "per_object_coverage",
                "expected_child_ids",
            }.intersection(data)
        )
        horizon = data.get("horizon", {})
        if isinstance(horizon, Mapping):
            retired.extend(
                f"horizon.{key}"
                for key in (
                    "timepoint_ids",
                    "time_strata",
                    "minimum_timepoint_count",
                    "minimum_timepoint_coverage",
                )
                if key in horizon
            )
        if retired:
            raise ValueError(
                "semantic coverage uses retired fields: " + ", ".join(retired)
            )
        profile = str(data.get("profile", "bounded")).strip().lower()
        if profile not in {"bounded", "predictive"}:
            raise ValueError(f"unknown semantic coverage profile: {profile}")
        expected_nodes = data.get("expected_model_node_ids", default_model_node_ids or [])
        if not expected_nodes:
            expected_nodes = default_model_node_ids or []
        expected_explicit = "expected_model_node_ids" in data
        raw_exclusions = data.get("excluded_model_nodes", [])
        exclusion_rows: list[dict[str, Any]] = []
        if not isinstance(raw_exclusions, (list, tuple)):
            raise ValueError("excluded_model_nodes must be a list of current row objects")
        for value in raw_exclusions:
            if not isinstance(value, Mapping):
                raise ValueError(
                    "excluded_model_nodes entries must be current row objects"
                )
            exclusion_rows.append(dict(value))
        raw_per_model_node = data.get("per_model_node", {})
        if not isinstance(raw_per_model_node, Mapping):
            raw_per_model_node = {}
        raw_axis_dispositions = data.get("axis_dispositions", [])
        if not isinstance(raw_axis_dispositions, (list, tuple)):
            raise ValueError("axis_dispositions must be a list of current row objects")
        axis_dispositions: list[PredictiveAxisDisposition] = []
        for raw_disposition in raw_axis_dispositions:
            if not isinstance(raw_disposition, Mapping):
                raise ValueError(
                    "axis_dispositions entries must be current row objects"
                )
            axis_dispositions.append(
                PredictiveAxisDisposition.from_dict(raw_disposition)
            )
        axis_ids = [row.axis_id for row in axis_dispositions]
        if profile == "predictive":
            missing_axes = sorted(set(PREDICTIVE_AXIS_IDS).difference(axis_ids))
            extra_axes = sorted(set(axis_ids).difference(PREDICTIVE_AXIS_IDS))
            duplicate_axes = sorted(
                axis_id for axis_id in set(axis_ids) if axis_ids.count(axis_id) > 1
            )
            if missing_axes or extra_axes or duplicate_axes:
                raise ValueError(
                    "predictive axis dispositions must contain exactly one current row "
                    f"per axis; missing={missing_axes}, extra={extra_axes}, "
                    f"duplicates={duplicate_axes}"
                )
            for row in axis_dispositions:
                if row.disposition not in {"required", "not_applicable"}:
                    raise ValueError(
                        f"predictive axis {row.axis_id} has invalid disposition: "
                        f"{row.disposition or '<missing>'}"
                    )
                if not row.claim_boundary:
                    raise ValueError(
                        f"predictive axis {row.axis_id} requires claim_boundary"
                    )
                expected_field = PREDICTIVE_AXIS_EXPECTED_FIELDS[row.axis_id]
                expected_ids = data.get(expected_field, [])
                if not isinstance(expected_ids, (list, tuple)):
                    raise ValueError(f"{expected_field} must be a list")
                if row.disposition == "required":
                    allowed_observations = PREDICTIVE_AXIS_OBSERVATION_FIELDS[
                        row.axis_id
                    ]
                    if row.observation_field not in allowed_observations:
                        raise ValueError(
                            f"predictive axis {row.axis_id} observation_field must be one of "
                            f"{list(allowed_observations)}"
                        )
                    if row.reason:
                        raise ValueError(
                            f"required predictive axis {row.axis_id} must not carry reason"
                        )
                    if not expected_ids:
                        raise ValueError(
                            f"required predictive axis {row.axis_id} has empty "
                            f"{expected_field}"
                        )
                else:
                    if row.observation_field:
                        raise ValueError(
                            f"not_applicable predictive axis {row.axis_id} must not carry "
                            "observation_field"
                        )
                    if not row.reason:
                        raise ValueError(
                            f"not_applicable predictive axis {row.axis_id} requires reason"
                        )
                    if expected_ids:
                        raise ValueError(
                            f"not_applicable predictive axis {row.axis_id} must not carry "
                            f"{expected_field}"
                        )
        return cls(
            profile=profile,
            expected_model_node_ids=[str(item) for item in expected_nodes],
            expected_model_node_ids_explicit=expected_explicit,
            excluded_model_nodes=exclusion_rows,
            expected_semantic_child_ids=[
                str(item)
                for item in data.get("expected_semantic_child_ids", [])
            ],
            scenario_ids=[str(item) for item in data.get("scenario_ids", [])],
            holdout_scenario_ids=[
                str(item) for item in data.get("holdout_scenario_ids", [])
            ],
            state_ids=[str(item) for item in data.get("state_ids", [])],
            transition_ids=[str(item) for item in data.get("transition_ids", [])],
            event_ids=[str(item) for item in data.get("event_ids", [])],
            fluent_ids=[str(item) for item in data.get("fluent_ids", [])],
            branch_ids=[str(item) for item in data.get("branch_ids", [])],
            perturbation_ids=[str(item) for item in data.get("perturbation_ids", [])],
            intervention_ids=[str(item) for item in data.get("intervention_ids", [])],
            counterfactual_ids=[str(item) for item in data.get("counterfactual_ids", [])],
            horizon=dict(data.get("horizon", {})),
            timepoint_ids=[
                str(item)
                for item in data.get("timepoint_ids", [])
            ],
            time_strata=_time_strata_from_value(data.get("time_strata", {})),
            minimum_timepoint_count=data.get("minimum_timepoint_count", 0),
            minimum_timepoint_coverage=data.get("minimum_timepoint_coverage", 0.0),
            axis_dispositions=axis_dispositions,
            per_model_node={
                str(node_id): dict(policy)
                for node_id, policy in raw_per_model_node.items()
                if isinstance(policy, Mapping)
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "expected_model_node_ids": self.expected_model_node_ids,
            "expected_model_node_ids_explicit": self.expected_model_node_ids_explicit,
            "excluded_model_nodes": self.excluded_model_nodes,
            "expected_semantic_child_ids": self.expected_semantic_child_ids,
            "scenario_ids": self.scenario_ids,
            "holdout_scenario_ids": self.holdout_scenario_ids,
            "state_ids": self.state_ids,
            "transition_ids": self.transition_ids,
            "event_ids": self.event_ids,
            "fluent_ids": self.fluent_ids,
            "branch_ids": self.branch_ids,
            "perturbation_ids": self.perturbation_ids,
            "intervention_ids": self.intervention_ids,
            "counterfactual_ids": self.counterfactual_ids,
            "horizon": self.horizon,
            "timepoint_ids": self.timepoint_ids,
            "time_strata": self.time_strata,
            "minimum_timepoint_count": self.minimum_timepoint_count,
            "minimum_timepoint_coverage": self.minimum_timepoint_coverage,
            "axis_dispositions": [
                row.to_dict() for row in self.axis_dispositions
            ],
            "per_model_node": self.per_model_node,
        }


@dataclass(frozen=True)
class ModelMeshContract:
    mesh_id: str
    schema_version: str = "worldguard.model_mesh.v1"
    run_id: str = "worldguard-mesh-run"
    nodes: list[ModelNode] = field(default_factory=list)
    edges: list[ModelEdge] = field(default_factory=list)
    snapshots: list[WorldStateSnapshot] = field(default_factory=list)
    provider_availability: dict[str, bool] = field(default_factory=dict)
    provider_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    semantic_coverage: SemanticCoverageContract = field(
        default_factory=SemanticCoverageContract
    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelMeshContract":
        if "closure_profile" in data:
            raise ValueError(
                "closure_profile is retired; current WorldGuard always requires semantic execution"
            )
        retired = sorted(
            {"semantic_coverage_contract", "coverage_contract"}.intersection(data)
        )
        if retired:
            raise ValueError(
                "model mesh uses retired fields: " + ", ".join(retired)
            )
        nodes = [ModelNode.from_dict(item) for item in data.get("nodes", [])]
        coverage_data = data.get("semantic_coverage")
        return cls(
            mesh_id=str(data.get("mesh_id", "")),
            schema_version=str(data.get("schema_version", "worldguard.model_mesh.v1")),
            run_id=str(data.get("run_id", "worldguard-mesh-run")),
            nodes=nodes,
            edges=[ModelEdge.from_dict(item) for item in data.get("edges", [])],
            snapshots=[
                WorldStateSnapshot.from_dict(item) for item in data.get("snapshots", [])
            ],
            provider_availability={
                str(key): bool(value)
                for key, value in dict(data.get("provider_availability", {})).items()
            },
            provider_results={
                str(key): dict(value)
                for key, value in dict(data.get("provider_results", {})).items()
                if isinstance(value, Mapping)
            },
            semantic_coverage=SemanticCoverageContract.from_dict(
                coverage_data,
                default_model_node_ids=[node.model_id for node in nodes],
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mesh_id": self.mesh_id,
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
            "provider_availability": self.provider_availability,
            "provider_results": self.provider_results,
            "semantic_coverage": self.semantic_coverage.to_dict(),
        }


@dataclass(frozen=True)
class MeshFinding:
    finding_id: str
    status: GuardStatus
    code: str
    message: str
    node_id: str = ""
    edge_id: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", coerce_status(self.status))

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "status": self.status.value,
            "code": self.code,
            "message": self.message,
            "node_id": self.node_id,
            "edge_id": self.edge_id,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class MeshReport:
    status: GuardStatus
    node_reports: dict[str, GuardedReport] = field(default_factory=dict)
    findings: list[MeshFinding] = field(default_factory=list)
    aggregate_ledger: list[LedgerEntry] = field(default_factory=list)
    scope_limits: list[str] = field(default_factory=list)
    structural_status: GuardStatus = GuardStatus.GAP
    semantic_status: SemanticStatus = SemanticStatus.NOT_RUN
    provider_status: ProviderStatus = ProviderStatus.NOT_REQUIRED
    rollout_status: SemanticStatus = SemanticStatus.NOT_RUN
    semantic_receipts: list[SemanticExecutionReceipt] = field(default_factory=list)
    depth_receipt: NativeDepthReceipt | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", coerce_status(self.status))
        object.__setattr__(self, "structural_status", coerce_status(self.structural_status))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "structural_status": self.structural_status.value,
            "semantic_status": self.semantic_status.value,
            "provider_status": self.provider_status.value,
            "rollout_status": self.rollout_status.value,
            "node_reports": {
                model_id: report.to_dict() for model_id, report in self.node_reports.items()
            },
            "semantic_receipts": [receipt.to_dict() for receipt in self.semantic_receipts],
            "findings": [finding.to_dict() for finding in self.findings],
            "aggregate_ledger": [entry.to_dict() for entry in self.aggregate_ledger],
            "scope_limits": self.scope_limits,
            "depth_receipt": self.depth_receipt.to_dict() if self.depth_receipt else None,
        }


def _coverage_route_state(mesh: ModelMeshContract) -> dict[str, Any]:
    nodes_by_id = {node.model_id: node for node in mesh.nodes}
    discovered_nodes = list(dict.fromkeys(node.model_id for node in mesh.nodes))
    declared_nodes = list(
        dict.fromkeys(mesh.semantic_coverage.expected_model_node_ids)
    )
    if not declared_nodes:
        declared_nodes = list(discovered_nodes)
    findings: list[MeshFinding] = []
    exclusion_rows: list[dict[str, Any]] = []
    seen_exclusions: set[str] = set()
    valid_excluded_ids: set[str] = set()
    reconciliation_gaps: list[str] = []
    for raw in mesh.semantic_coverage.excluded_model_nodes:
        retired_id_field = "node_id" in raw or "object_id" in raw
        node_id = str(raw.get("model_node_id", "") or "").strip()
        reason = str(raw.get("reason", "") or "").strip()
        disposition = str(raw.get("disposition", "") or "").strip().lower()
        node = nodes_by_id.get(node_id)
        critical = bool(
            node
            and node.contract
            and (
                claim_predictive_intent(node.contract.claim)
                or mesh.semantic_coverage.profile == "predictive"
            )
        )
        row = {
            "model_node_id": node_id,
            "reason": reason,
            "disposition": disposition,
            "critical": critical,
        }
        exclusion_rows.append(row)
        invalid: list[str] = []
        if retired_id_field:
            invalid.append("retired_id_field")
        if not node_id or node_id in seen_exclusions:
            invalid.append("duplicate_or_missing_id")
        seen_exclusions.add(node_id)
        if node_id not in nodes_by_id:
            invalid.append("unknown_node")
        if not reason:
            invalid.append("reason_missing")
        if disposition not in CLOSED_MODEL_EXCLUSION_DISPOSITIONS:
            invalid.append("disposition_not_closed")
        if node_id in declared_nodes:
            invalid.append("declared_and_excluded_overlap")
        if critical:
            invalid.append("critical_predictive_node")
        if invalid:
            reconciliation_gaps.extend(
                f"model_node_exclusion_invalid:{node_id}:{item}" for item in invalid
            )
            findings.append(
                _finding(
                    mesh,
                    GuardStatus.GAP,
                    "MESH_MODEL_NODE_EXCLUSION_INVALID",
                    "A model-node exclusion is missing closure evidence, overlaps declared coverage, or excludes a predictive-critical node.",
                    node_id=node_id,
                    evidence={"exclusion": row, "invalid_reasons": invalid},
                )
            )
            continue
        connected_edges = [
            edge.edge_id
            for edge in mesh.edges
            if edge.source_model_id == node_id or edge.target_model_id == node_id
        ]
        if connected_edges:
            reconciliation_gaps.append(
                f"excluded_model_node_still_connected:{node_id}"
            )
            findings.append(
                _finding(
                    mesh,
                    GuardStatus.GAP,
                    "MESH_EXCLUDED_MODEL_NODE_STILL_CONNECTED",
                    "An excluded node still participates in mesh handoffs and therefore cannot silently disappear from the predictive denominator.",
                    node_id=node_id,
                    evidence={"edge_ids": connected_edges, "exclusion": row},
                )
            )
        valid_excluded_ids.add(node_id)

    omitted_discovered = set(discovered_nodes).difference(
        declared_nodes, valid_excluded_ids
    )
    for node_id in sorted(omitted_discovered):
        reconciliation_gaps.append(f"discovered_model_node_undeclared:{node_id}")
        findings.append(
            _finding(
                mesh,
                GuardStatus.GAP,
                "MESH_EXPECTED_MODEL_NODE_DECLARATION_INCOMPLETE",
                "The caller expected-node list omitted a discovered mesh node; the node remains in the effective denominator.",
                node_id=node_id,
                evidence={
                    "discovered_model_node_ids": discovered_nodes,
                    "declared_model_node_ids": declared_nodes,
                },
            )
        )
    expected_nodes = list(
        dict.fromkeys(
            [
                *declared_nodes,
                *(
                    node_id
                    for node_id in discovered_nodes
                    if node_id not in valid_excluded_ids
                ),
            ]
        )
    )
    required_guards: dict[str, list[str]] = {}
    declared_guards: dict[str, list[str]] = {}
    missing_guards: dict[str, list[str]] = {}
    unmapped_semantics: dict[str, list[str]] = {}
    expected_children = set(mesh.semantic_coverage.expected_semantic_child_ids)
    skipped_models: list[dict[str, Any]] = []
    skipped_children: list[dict[str, Any]] = []
    semantic_required = True

    for node_id in expected_nodes:
        node = nodes_by_id.get(node_id)
        if node is None:
            skipped_models.append(
                {
                    "node_id": node_id,
                    "reason": "expected_model_node_missing",
                    "coverage_impact": "required_node_not_executed",
                }
            )
            findings.append(
                _finding(
                    mesh,
                    GuardStatus.GAP,
                    "MESH_EXPECTED_MODEL_NODE_MISSING",
                    "An expected semantic-coverage model node is absent from the mesh.",
                    node_id=node_id,
                    evidence={"expected_model_node_id": node_id},
                )
            )
            continue
        if node.contract is None:
            skipped_models.append(
                {
                    "node_id": node_id,
                    "reason": "missing_guard_contract",
                    "coverage_impact": "required_node_not_executed",
                }
            )
            skipped_children.append(
                {
                    "child_id": f"{node_id}:<contract-required>",
                    "node_id": node_id,
                    "guard": "",
                    "reason": "missing_guard_contract",
                    "coverage_impact": "required_semantic_child_not_executed",
                }
            )
            if semantic_required:
                findings.append(
                    _finding(
                        mesh,
                        GuardStatus.GAP,
                        "MESH_EXPECTED_NODE_CONTRACT_MISSING",
                        "An expected semantic-rollout node has no GuardContract.",
                        node_id=node_id,
                        evidence={"expected_model_node_id": node_id},
                    )
                )
            continue
        declared = list(dict.fromkeys(node.contract.claim.target_guards))
        required = list(derive_required_guards(node.contract.claim))
        if mesh.semantic_coverage.profile == "predictive":
            required = list(dict.fromkeys([*required, "EventGuard", "CausalGuard"]))
        unknown = list(unmapped_claim_semantics(node.contract.claim))
        declared_guards[node_id] = declared
        required_guards[node_id] = required
        if unknown:
            unmapped_semantics[node_id] = unknown
            findings.append(
                _finding(
                    mesh,
                    GuardStatus.GAP,
                    "MESH_CLAIM_SEMANTIC_UNMAPPED",
                    "Structured claim semantics have no WorldGuard-owned Guard route.",
                    node_id=node_id,
                    evidence={"unmapped_semantics": unknown},
                )
            )
        for guard in set(declared).union(required):
            expected_children.add(f"{node_id}:{guard}")
        missing = [guard for guard in required if guard not in declared]
        if missing:
            missing_guards[node_id] = missing
            findings.append(
                _finding(
                    mesh,
                    GuardStatus.GAP,
                    "MESH_CLAIM_DERIVED_GUARD_MISSING",
                    "A Guard required by structured claim semantics is absent from caller-declared routes.",
                    node_id=node_id,
                    evidence={
                        "required_guards": required,
                        "declared_guards": declared,
                        "missing_guards": missing,
                    },
                )
            )
            skipped_children.extend(
                {
                    "child_id": f"{node_id}:{guard}",
                    "node_id": node_id,
                    "guard": guard,
                    "reason": "claim_derived_guard_missing",
                    "coverage_impact": "required_semantic_child_not_executed",
                }
                for guard in missing
            )

    return {
        "expected_nodes": expected_nodes,
        "discovered_nodes": discovered_nodes,
        "declared_nodes": declared_nodes,
        "excluded_models": [
            row for row in exclusion_rows if row["model_node_id"] in valid_excluded_ids
        ],
        "reconciliation_gaps": list(dict.fromkeys(reconciliation_gaps)),
        "required_guards": required_guards,
        "declared_guards": declared_guards,
        "missing_guards": missing_guards,
        "unmapped_semantics": unmapped_semantics,
        "expected_children": sorted(expected_children),
        "skipped_models": skipped_models,
        "skipped_children": skipped_children,
        "findings": findings,
    }


def _predictive_requested(mesh: ModelMeshContract) -> bool:
    return bool(
        mesh.semantic_coverage.profile == "predictive"
        or any(
            node.contract and claim_predictive_intent(node.contract.claim)
            for node in mesh.nodes
        )
    )


def _output_ids(
    receipts: list[SemanticExecutionReceipt],
    output_field: str,
) -> set[str]:
    return {
        str(item)
        for receipt in receipts
        for item in receipt.outputs.get(output_field, [])
    }


def _output_field_ids(
    receipts: list[SemanticExecutionReceipt],
    output_field: str,
) -> set[str]:
    if output_field != "final_fluent_ids_by_scenario":
        return _output_ids(receipts, output_field)
    observed: set[str] = set()
    for receipt in receipts:
        per_scenario = receipt.outputs.get(output_field, {})
        if not isinstance(per_scenario, Mapping):
            continue
        for values in per_scenario.values():
            if isinstance(values, (list, tuple, set)):
                observed.update(str(value) for value in values)
    return observed


def _predictive_axis_observed_ids(
    receipts: list[SemanticExecutionReceipt],
    axis_id: str,
    observation_field: str,
) -> set[str]:
    fields = (
        (observation_field,)
        if observation_field
        else PREDICTIVE_AXIS_OBSERVATION_FIELDS[axis_id]
    )
    observed: set[str] = set()
    for output_field in fields:
        observed.update(_output_field_ids(receipts, output_field))
    return observed


def _predictive_axis_assessment(
    coverage: SemanticCoverageContract,
    receipts: list[SemanticExecutionReceipt],
) -> tuple[list[str], list[dict[str, Any]]]:
    dispositions = {row.axis_id: row for row in coverage.axis_dispositions}
    gaps: list[str] = []
    results: list[dict[str, Any]] = []
    for axis_id in PREDICTIVE_AXIS_IDS:
        expected_field = PREDICTIVE_AXIS_EXPECTED_FIELDS[axis_id]
        expected_ids = set(getattr(coverage, expected_field))
        row = dispositions.get(axis_id)
        if row is None:
            gaps.append(f"predictive_axis_disposition_missing:{axis_id}")
            results.append(
                {
                    "axis_id": axis_id,
                    "disposition": "invalid",
                    "expected_field": expected_field,
                    "observation_field": "",
                    "observation_fields_checked": list(
                        PREDICTIVE_AXIS_OBSERVATION_FIELDS[axis_id]
                    ),
                    "reason": "predictive axis disposition is missing",
                    "claim_boundary": "",
                    "expected_ids": sorted(expected_ids),
                    "observed_ids": [],
                    "missing_ids": sorted(expected_ids),
                    "outside_declared_ids": [],
                    "passed": False,
                    "status": "blocked",
                }
            )
            continue
        observed_ids = _predictive_axis_observed_ids(
            receipts,
            axis_id,
            row.observation_field,
        )
        missing_ids: list[str] = []
        outside_declared_ids: list[str] = []
        if row.disposition == "required":
            missing_ids = sorted(expected_ids.difference(observed_ids))
            outside_declared_ids = sorted(observed_ids.difference(expected_ids))
            gaps.extend(
                f"predictive_{expected_field}_not_executed:{item_id}"
                for item_id in missing_ids
            )
            gaps.extend(
                f"predictive_{expected_field}_outside_declared:{item_id}"
                for item_id in outside_declared_ids
            )
            passed = not missing_ids and not outside_declared_ids
            status = "validated" if passed else "blocked"
        else:
            outside_declared_ids = sorted(observed_ids)
            gaps.extend(
                f"predictive_{axis_id}_not_applicable_observed:{item_id}"
                for item_id in outside_declared_ids
            )
            passed = not expected_ids and not observed_ids
            status = "not_applicable" if passed else "blocked"
        results.append(
            {
                "axis_id": axis_id,
                "disposition": row.disposition,
                "expected_field": expected_field,
                "observation_field": row.observation_field,
                "observation_fields_checked": (
                    [row.observation_field]
                    if row.observation_field
                    else list(PREDICTIVE_AXIS_OBSERVATION_FIELDS[axis_id])
                ),
                "reason": row.reason,
                "claim_boundary": row.claim_boundary,
                "expected_ids": sorted(expected_ids),
                "observed_ids": sorted(observed_ids),
                "missing_ids": missing_ids,
                "outside_declared_ids": outside_declared_ids,
                "passed": passed,
                "status": status,
            }
        )
    return gaps, results


_NUMERIC_TIME_RE = re.compile(r"^(.*?)([-+]?\d+(?:\.\d+)?)$")


def _event_timepoint_ids(
    mesh: ModelMeshContract,
    node_ids: set[str] | None = None,
) -> list[str]:
    timepoints: list[str] = []
    for node in mesh.nodes:
        if node_ids is not None and node.model_id not in node_ids:
            continue
        if node.contract is None:
            continue
        events = node.contract.inputs.get("events", [])
        for event in events:
            if isinstance(event, Mapping) and event.get("at") not in (None, ""):
                timepoints.append(str(event["at"]))
    return _ordered_unique(timepoints)


def _declared_object_ids(
    value: Any, *, object_id_field: str | None = None
) -> list[str]:
    if isinstance(value, Mapping):
        return [str(key) for key in value]
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            if isinstance(item, Mapping):
                object_id = item.get(object_id_field) if object_id_field else None
                if object_id not in (None, ""):
                    result.append(str(object_id))
            elif str(item):
                result.append(str(item))
        return _ordered_unique(result)
    if value not in (None, ""):
        return [str(value)]
    return []


def _node_variable_ids(node: ModelNode) -> list[str]:
    if node.contract is None:
        return []
    causal = node.contract.inputs.get("causal_model", {})
    values: list[str] = []
    if isinstance(causal, Mapping):
        values.extend(
            _declared_object_ids(
                causal.get("variables", []), object_id_field="variable_id"
            )
        )
        values.extend(
            _declared_object_ids(
                causal.get("signals", []), object_id_field="signal_id"
            )
        )
    return _ordered_unique(values)


def _output_variable_timepoints(
    receipts: list[SemanticExecutionReceipt],
) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for receipt in receipts:
        raw = receipt.outputs.get("observed_variable_timepoints", {})
        if not isinstance(raw, Mapping):
            continue
        for variable_id, timepoint_ids in raw.items():
            values = (
                timepoint_ids
                if isinstance(timepoint_ids, (list, tuple, set))
                else [timepoint_ids]
            )
            result.setdefault(str(variable_id), set()).update(
                str(item) for item in values if str(item)
            )
    return result


def _time_position(value: str, start: str, end: str) -> float | None:
    if value == start:
        return 0.0
    if value == end:
        return 1.0
    numeric = [_NUMERIC_TIME_RE.fullmatch(item) for item in (value, start, end)]
    if all(numeric):
        assert numeric[0] is not None and numeric[1] is not None and numeric[2] is not None
        prefixes = {match.group(1) for match in numeric}
        if len(prefixes) == 1:
            point, lower, upper = (float(match.group(2)) for match in numeric)
            if upper != lower:
                return (point - lower) / (upper - lower)
    try:
        point_time, start_time, end_time = (
            datetime.fromisoformat(item.replace("Z", "+00:00"))
            for item in (value, start, end)
        )
    except ValueError:
        return None
    span = (end_time - start_time).total_seconds()
    if span == 0:
        return None
    return (point_time - start_time).total_seconds() / span


def _timepoint_depth_assessment(
    mesh: ModelMeshContract,
    receipts: list[SemanticExecutionReceipt],
    horizon_steps: int,
    *,
    coverage_contract: SemanticCoverageContract | None = None,
    node_ids: set[str] | None = None,
    observed_timepoint_ids: set[str] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    coverage = coverage_contract or mesh.semantic_coverage
    horizon = coverage.horizon
    start = str(horizon.get("start", ""))
    end = str(horizon.get("end", ""))
    observed = (
        set(observed_timepoint_ids)
        if observed_timepoint_ids is not None
        else _output_ids(receipts, "observed_timepoints")
    )
    event_timepoints = (
        []
        if observed_timepoint_ids is not None
        else _event_timepoint_ids(mesh, node_ids)
    )
    explicit_strata = {
        str(stratum_id): _ordered_unique([str(item) for item in items])
        for stratum_id, items in coverage.time_strata.items()
    }
    representative_ids = _ordered_unique(
        [
            *coverage.timepoint_ids,
            *(item for items in explicit_strata.values() for item in items),
            *event_timepoints,
            *sorted(observed),
        ]
    )
    gaps: list[str] = []
    try:
        declared_count = int(coverage.minimum_timepoint_count)
        if isinstance(coverage.minimum_timepoint_count, bool) or declared_count < 0:
            raise ValueError
    except (TypeError, ValueError):
        declared_count = 0
        gaps.append("predictive_minimum_timepoint_count_invalid")
    try:
        declared_ratio = float(coverage.minimum_timepoint_coverage)
        if isinstance(coverage.minimum_timepoint_coverage, bool) or not 0 <= declared_ratio <= 1:
            raise ValueError
    except (TypeError, ValueError):
        declared_ratio = 0.0
        gaps.append("predictive_minimum_timepoint_coverage_invalid")

    native_floor = (
        min(horizon_steps, max(3, ceil(sqrt(horizon_steps))))
        if horizon_steps > 0
        else 0
    )
    ratio_floor_count = ceil(horizon_steps * declared_ratio) if horizon_steps > 0 else 0
    required_count = max(native_floor, declared_count, ratio_floor_count)
    if horizon_steps > 0 and required_count > horizon_steps:
        gaps.append("predictive_timepoint_floor_exceeds_horizon")
    required_ratio = (required_count / horizon_steps) if horizon_steps > 0 else 1.0

    phase_positions: dict[str, float] = {}
    unresolved: list[str] = []
    outside: list[str] = []
    # Canonical early/middle/late strata are target-owned and cannot be
    # replaced by caller labels.  Declared strata may add stricter checks, but
    # three arbitrary names containing only early points never satisfy the
    # temporal distribution gate.
    canonical_strata = {"early": [], "middle": [], "late": []}
    for timepoint_id in representative_ids:
        position = _time_position(timepoint_id, start, end) if start and end else None
        if position is None:
            unresolved.append(timepoint_id)
            continue
        if not 0 <= position <= 1:
            outside.append(timepoint_id)
            continue
        phase_positions[timepoint_id] = position
        if position < (1 / 3):
            canonical_strata["early"].append(timepoint_id)
        elif position < (2 / 3):
            canonical_strata["middle"].append(timepoint_id)
        else:
            canonical_strata["late"].append(timepoint_id)
    if unresolved:
        gaps.append("predictive_time_strata_unresolvable")
    gaps.extend(f"predictive_timepoint_outside_horizon:{item}" for item in outside)
    in_horizon_observed = set(observed).intersection(phase_positions)

    required_representatives = set(coverage.timepoint_ids)
    required_representatives.update(
        item for items in explicit_strata.values() for item in items
    )
    gaps.extend(
        f"predictive_timepoint_not_executed:{item}"
        for item in sorted(required_representatives.difference(observed))
    )
    if start and start not in observed:
        gaps.append("predictive_horizon_start_not_observed")
    if end and end not in observed:
        gaps.append("predictive_horizon_end_not_observed")
    if len(observed) < 2:
        gaps.append("predictive_timepoint_depth_insufficient")

    observed_count = len(in_horizon_observed)
    observed_ratio = (
        min(1.0, observed_count / horizon_steps) if horizon_steps > 0 else 0.0
    )
    if observed_count < required_count:
        gaps.append(
            f"predictive_timepoint_sample_floor_not_met:{observed_count}/{required_count}"
        )
    if observed_ratio + 1e-12 < required_ratio:
        gaps.append(
            "predictive_timepoint_coverage_ratio_not_met:"
            f"{observed_ratio:.6f}/{required_ratio:.6f}"
        )

    observed_positions = sorted(
        phase_positions[timepoint_id]
        for timepoint_id in in_horizon_observed
    )
    max_normalized_gap: float | None = None
    allowed_max_normalized_gap: float | None = None
    if observed_positions:
        with_boundaries = [0.0, *observed_positions, 1.0]
        max_normalized_gap = max(
            right - left
            for left, right in zip(with_boundaries, with_boundaries[1:])
        )
        allowed_max_normalized_gap = min(
            0.5,
            2.5 / max(observed_count - 1, 1),
        )
        if max_normalized_gap > allowed_max_normalized_gap + 1e-12:
            gaps.append(
                "predictive_timepoint_max_gap_exceeded:"
                f"{max_normalized_gap:.6f}/{allowed_max_normalized_gap:.6f}"
            )

    strata_results: list[dict[str, Any]] = []
    for stratum_id, expected_ids in canonical_strata.items():
        expected_set = set(expected_ids)
        observed_ids = sorted(expected_set.intersection(observed))
        passed = bool(expected_set and observed_ids)
        if not passed:
            gaps.append(f"predictive_time_stratum_uncovered:{stratum_id}")
        strata_results.append(
            {
                "stratum_id": stratum_id,
                "expected_timepoint_ids": list(expected_ids),
                "observed_timepoint_ids": observed_ids,
                "passed": passed,
                "origin": "worldguard_native_early_middle_late",
            }
        )
    for stratum_id, expected_ids in explicit_strata.items():
        expected_set = set(expected_ids)
        observed_ids = sorted(expected_set.intersection(observed))
        passed = bool(expected_set) and expected_set <= observed
        if not passed:
            gaps.append(f"predictive_declared_time_stratum_incomplete:{stratum_id}")
        strata_results.append(
            {
                "stratum_id": f"declared:{stratum_id}",
                "expected_timepoint_ids": list(expected_ids),
                "observed_timepoint_ids": observed_ids,
                "passed": passed,
                "origin": "target_declared_additional_stratum",
            }
        )

    return list(dict.fromkeys(gaps)), {
        "horizon_step_count": horizon_steps,
        "expected_timepoint_ids": representative_ids,
        "observed_timepoint_ids": sorted(observed),
        "expected_timepoint_count": len(representative_ids),
        "executed_timepoint_count": observed_count,
        "native_minimum_timepoint_count": native_floor,
        "declared_minimum_timepoint_count": declared_count,
        "effective_minimum_timepoint_count": required_count,
        "declared_minimum_timepoint_coverage": declared_ratio,
        "effective_minimum_timepoint_coverage": required_ratio,
        "observed_timepoint_coverage": observed_ratio,
        "max_normalized_timepoint_gap": max_normalized_gap,
        "allowed_max_normalized_timepoint_gap": allowed_max_normalized_gap,
        "time_strata_results": strata_results,
        "unresolved_timepoint_ids": unresolved,
        "outside_horizon_timepoint_ids": outside,
    }


def _predictive_assessment(
    mesh: ModelMeshContract,
    coverage_state: dict[str, Any],
    receipts: list[SemanticExecutionReceipt],
) -> tuple[list[str], bool, dict[str, Any]]:
    coverage = mesh.semantic_coverage
    requested = _predictive_requested(mesh)
    expected_children = set(coverage_state["expected_children"])
    executed_children = {
        f"{receipt.node_id}:{receipt.guard}"
        for receipt in receipts
        if receipt.status not in {SemanticStatus.NOT_RUN, SemanticStatus.BOUNDARY_ONLY}
    }
    passed_children = {
        f"{receipt.node_id}:{receipt.guard}"
        for receipt in receipts
        if receipt.status == SemanticStatus.PASS
    }
    expected_nodes = set(coverage_state["expected_nodes"])
    executed_nodes = {
        node_id
        for node_id in expected_nodes
        if any(child.startswith(f"{node_id}:") for child in executed_children)
    }
    gaps: list[str] = []
    gaps.extend(coverage_state.get("reconciliation_gaps", []))
    gaps.extend(
        f"missing_model_node:{row['node_id']}"
        for row in coverage_state["skipped_models"]
    )
    gaps.extend(
        f"missing_required_guard:{node_id}:{guard}"
        for node_id, guards in coverage_state["missing_guards"].items()
        for guard in guards
    )
    gaps.extend(
        f"unmapped_claim_semantic:{node_id}:{semantic}"
        for node_id, semantics in coverage_state["unmapped_semantics"].items()
        for semantic in semantics
    )
    gaps.extend(
        f"semantic_child_not_executed:{child_id}"
        for child_id in sorted(expected_children.difference(executed_children))
    )
    gaps.extend(
        f"semantic_child_not_passed:{child_id}"
        for child_id in sorted(expected_children.difference(passed_children))
        if child_id in executed_children
    )

    scenario_expected_to_output = {
        "scenario_ids": "executed_scenario_ids",
        "holdout_scenario_ids": "executed_holdout_scenario_ids",
    }
    actual: dict[str, set[str]] = {
        expected_field: _output_ids(receipts, output_field)
        for expected_field, output_field in scenario_expected_to_output.items()
    }
    predictive_axis_results: list[dict[str, Any]] = []
    per_model_node_results: list[dict[str, Any]] = []
    horizon_steps = 0
    time_quantitative: dict[str, Any] = {
        "horizon_step_count": 0,
        "expected_timepoint_ids": [],
        "observed_timepoint_ids": sorted(_output_ids(receipts, "observed_timepoints")),
        "expected_timepoint_count": 0,
        "executed_timepoint_count": 0,
        "native_minimum_timepoint_count": 0,
        "declared_minimum_timepoint_count": 0,
        "effective_minimum_timepoint_count": 0,
        "declared_minimum_timepoint_coverage": 0.0,
        "effective_minimum_timepoint_coverage": 0.0,
        "observed_timepoint_coverage": 0.0,
        "time_strata_results": [],
        "unresolved_timepoint_ids": [],
        "outside_horizon_timepoint_ids": [],
    }
    if requested:
        claim_atoms = [
            atom
            for node in mesh.nodes
            if node.model_id in expected_nodes and node.contract
            for atom in node.contract.claim.atoms
        ]
        if not claim_atoms:
            gaps.append("structured_claim_atoms_missing")
        horizon = coverage.horizon
        try:
            horizon_steps = int(horizon.get("steps", 0))
        except (TypeError, ValueError):
            horizon_steps = 0
        if (
            horizon_steps < 2
            or horizon.get("start") in (None, "")
            or horizon.get("end") in (None, "")
            or horizon.get("start") == horizon.get("end")
        ):
            gaps.append("nondegenerate_horizon_missing")
        time_gaps, time_quantitative = _timepoint_depth_assessment(
            mesh,
            receipts,
            horizon_steps,
        )
        gaps.extend(time_gaps)
        for field_id in scenario_expected_to_output:
            expected = set(getattr(coverage, field_id))
            if not expected:
                gaps.append(f"predictive_{field_id}_missing")
                continue
            for missing_id in sorted(expected.difference(actual[field_id])):
                gaps.append(f"predictive_{field_id}_not_executed:{missing_id}")
        axis_gaps, predictive_axis_results = _predictive_axis_assessment(
            coverage,
            receipts,
        )
        gaps.extend(axis_gaps)
        for guard in ("EventGuard", "CausalGuard"):
            guard_receipts = [
                receipt
                for receipt in receipts
                if receipt.guard == guard and receipt.status == SemanticStatus.PASS
            ]
            guard_scenarios = _output_ids(guard_receipts, "executed_scenario_ids")
            guard_holdouts = _output_ids(guard_receipts, "executed_holdout_scenario_ids")
            if set(coverage.scenario_ids).difference(guard_scenarios):
                gaps.append(f"{guard}:scenario_rollout_incomplete")
            if set(coverage.holdout_scenario_ids).difference(guard_holdouts):
                gaps.append(f"{guard}:holdout_rollout_incomplete")

        # Aggregate coverage is not per-object coverage.  Re-evaluate every
        # expected model node against either its explicit target-owned policy
        # or the shared policy.  This prevents one richly rolled-out child
        # from hiding another child that contributed only one or two points.
        for node_id in sorted(expected_nodes):
            node = next((item for item in mesh.nodes if item.model_id == node_id), None)
            if node is None or node.contract is None:
                continue
            raw_node_policy = coverage.per_model_node.get(node_id)
            if raw_node_policy is None:
                node_coverage = coverage
                node_policy_origin = "shared_target_policy"
            else:
                merged_policy = coverage.to_dict()
                merged_policy.pop("per_model_node", None)
                merged_policy.update(raw_node_policy)
                node_coverage = SemanticCoverageContract.from_dict(
                    merged_policy,
                    default_model_node_ids=[node_id],
                )
                node_policy_origin = "target_per_model_node_policy"
            node_receipts = [
                receipt for receipt in receipts if receipt.node_id == node_id
            ]
            node_actual = {
                expected_field: _output_ids(node_receipts, output_field)
                for expected_field, output_field in scenario_expected_to_output.items()
            }
            try:
                node_horizon_steps = int(node_coverage.horizon.get("steps", 0))
            except (TypeError, ValueError):
                node_horizon_steps = 0
            node_gaps: list[str] = []
            if (
                node_horizon_steps < 2
                or node_coverage.horizon.get("start") in (None, "")
                or node_coverage.horizon.get("end") in (None, "")
                or node_coverage.horizon.get("start")
                == node_coverage.horizon.get("end")
            ):
                node_gaps.append("nondegenerate_horizon_missing")
            node_time_gaps, node_time_quantitative = _timepoint_depth_assessment(
                mesh,
                node_receipts,
                node_horizon_steps,
                coverage_contract=node_coverage,
                node_ids={node_id},
            )
            node_gaps.extend(node_time_gaps)
            variable_timepoint_results: list[dict[str, Any]] = []
            variable_observations = _output_variable_timepoints(node_receipts)
            for variable_id in _node_variable_ids(node):
                variable_gaps, variable_quantitative = _timepoint_depth_assessment(
                    mesh,
                    node_receipts,
                    node_horizon_steps,
                    coverage_contract=node_coverage,
                    node_ids={node_id},
                    observed_timepoint_ids=set(
                        variable_observations.get(variable_id, set())
                    ),
                )
                node_gaps.extend(
                    f"variable_timepoint:{variable_id}:{gap}"
                    for gap in variable_gaps
                )
                variable_timepoint_results.append(
                    {
                        "variable_or_signal_id": variable_id,
                        "passed": not variable_gaps,
                        "gaps": variable_gaps,
                        "timepoint_coverage": variable_quantitative,
                    }
                )
            for field_id in scenario_expected_to_output:
                expected = set(getattr(node_coverage, field_id))
                if not expected:
                    node_gaps.append(f"predictive_{field_id}_missing")
                    continue
                for missing_id in sorted(expected.difference(node_actual[field_id])):
                    node_gaps.append(f"predictive_{field_id}_not_executed:{missing_id}")
            node_axis_gaps, node_axis_results = _predictive_axis_assessment(
                node_coverage,
                node_receipts,
            )
            node_gaps.extend(node_axis_gaps)
            required_node_guards = set(
                coverage_state["required_guards"].get(node_id, [])
            )
            for guard in required_node_guards.intersection(
                {"EventGuard", "CausalGuard"}
            ):
                guard_receipts = [
                    receipt
                    for receipt in node_receipts
                    if receipt.guard == guard and receipt.status == SemanticStatus.PASS
                ]
                guard_scenarios = _output_ids(
                    guard_receipts, "executed_scenario_ids"
                )
                guard_holdouts = _output_ids(
                    guard_receipts, "executed_holdout_scenario_ids"
                )
                if set(node_coverage.scenario_ids).difference(guard_scenarios):
                    node_gaps.append(f"{guard}:scenario_rollout_incomplete")
                if set(node_coverage.holdout_scenario_ids).difference(guard_holdouts):
                    node_gaps.append(f"{guard}:holdout_rollout_incomplete")
            node_gaps = list(dict.fromkeys(node_gaps))
            gaps.extend(
                f"predictive_object:{node_id}:{gap}" for gap in node_gaps
            )
            per_model_node_results.append(
                {
                    "model_node_id": node_id,
                    "policy_origin": node_policy_origin,
                    "passed": not node_gaps,
                    "gaps": node_gaps,
                    "timepoint_coverage": node_time_quantitative,
                    "per_variable_timepoint_results": variable_timepoint_results,
                    "exposed_variable_or_signal_count": len(
                        variable_timepoint_results
                    ),
                    "expected_axis_counts": {
                        row["axis_id"]: len(row["expected_ids"])
                        for row in node_axis_results
                    },
                    "executed_axis_counts": {
                        row["axis_id"]: len(row["observed_ids"])
                        for row in node_axis_results
                    },
                    "axis_results": node_axis_results,
                }
            )

    expected_child_count = len(expected_children)
    executed_expected_count = len(expected_children.intersection(executed_children))
    quantitative = {
        "predictive_requested": requested,
        "expected_model_node_count": len(expected_nodes),
        "executed_model_node_count": len(executed_nodes),
        "expected_semantic_child_count": expected_child_count,
        "executed_semantic_child_count": executed_expected_count,
        "semantic_child_coverage_ratio": (
            executed_expected_count / expected_child_count if expected_child_count else 0.0
        ),
        "horizon": dict(coverage.horizon),
        "per_model_node_results": per_model_node_results,
        "predictive_axis_results": predictive_axis_results,
        **time_quantitative,
    }
    for field_id in scenario_expected_to_output:
        quantitative[f"expected_{field_id.removesuffix('_ids')}_count"] = len(
            getattr(coverage, field_id)
        )
        quantitative[f"executed_{field_id.removesuffix('_ids')}_count"] = len(
            actual[field_id]
        )
    for row in predictive_axis_results:
        axis_id = str(row["axis_id"])
        quantitative[f"expected_{axis_id}_count"] = len(row["expected_ids"])
        quantitative[f"executed_{axis_id}_count"] = len(row["observed_ids"])
        quantitative[f"{axis_id}_axis_disposition"] = row["disposition"]
    gaps = list(dict.fromkeys(gaps))
    licensed = bool(requested and not gaps and expected_children <= passed_children)
    return gaps, licensed, quantitative


def _qualification_rollout_inputs(mesh: ModelMeshContract) -> dict[str, Any]:
    coverage = mesh.semantic_coverage
    meaningful = bool(
        coverage.profile == "predictive"
        or coverage.expected_model_node_ids_explicit
        or coverage.excluded_model_nodes
        or coverage.expected_semantic_child_ids
        or coverage.scenario_ids
        or coverage.holdout_scenario_ids
        or coverage.state_ids
        or coverage.transition_ids
        or coverage.event_ids
        or coverage.fluent_ids
        or coverage.branch_ids
        or coverage.perturbation_ids
        or coverage.intervention_ids
        or coverage.counterfactual_ids
        or coverage.horizon
        or coverage.timepoint_ids
        or coverage.time_strata
        or coverage.minimum_timepoint_count
        or coverage.minimum_timepoint_coverage
        or coverage.axis_dispositions
        or coverage.per_model_node
    )
    return coverage.to_dict() if meaningful else {}


def qualification_context_for_node(
    mesh: ModelMeshContract,
    node: ModelNode,
) -> QualificationContext:
    if node.contract is None:
        raise ValueError(f"model node {node.model_id} lacks a Guard contract")
    return QualificationContext(
        node_id=node.model_id,
        target_id=node.contract.world_model.model_id or node.model_id,
        target_revision=node.contract.world_model.model_version or node.model_version,
        provider_availability=mesh.provider_availability,
        provider_results=mesh.provider_results,
        rollout_inputs=_qualification_rollout_inputs(mesh),
    )


def run_model_mesh(mesh: ModelMeshContract | Mapping[str, Any]) -> MeshReport:
    if not isinstance(mesh, ModelMeshContract):
        mesh = ModelMeshContract.from_dict(dict(mesh))

    coverage_state = _coverage_route_state(mesh)
    excluded_model_ids = {
        str(row["model_node_id"]) for row in coverage_state["excluded_models"]
    }
    node_reports: dict[str, GuardedReport] = {}
    findings: list[MeshFinding] = list(coverage_state["findings"])
    aggregate_ledger: list[LedgerEntry] = []
    node_ids: set[str] = set()
    duplicate_ids: set[str] = set()

    for node in mesh.nodes:
        if node.model_id in node_ids:
            duplicate_ids.add(node.model_id)
        node_ids.add(node.model_id)
        if node.model_id in excluded_model_ids:
            continue
        findings.extend(_authority_findings(mesh, node))
        if node.contract is not None:
            report = run_worldguard(
                node.contract,
                context=qualification_context_for_node(mesh, node),
            )
            node_reports[node.model_id] = report
            aggregate_ledger.extend(report.aggregate_ledger)

    for model_id in sorted(duplicate_ids):
        findings.append(
            _finding(
                mesh,
                GuardStatus.FAIL,
                "MESH_DUPLICATE_MODEL_ID",
                "Duplicate model ids make mesh topology ambiguous.",
                node_id=model_id,
                evidence={"model_id": model_id},
            )
        )

    for edge in mesh.edges:
        findings.extend(_edge_findings(mesh, edge, node_ids, {node.model_id: node for node in mesh.nodes}))

    for cycle in _cycles(mesh.edges):
        findings.append(
            _finding(
                mesh,
                GuardStatus.FAIL,
                "MESH_DEPENDENCY_CYCLE",
                "Mesh dependency edges contain a cycle.",
                evidence={"cycle": cycle},
            )
        )

    aggregate_ledger.extend(_finding_ledgers(mesh, findings))
    statuses = [report.structural_status for report in node_reports.values()]
    statuses.extend(finding.status for finding in findings)
    structural_status = aggregate_statuses(statuses) if statuses else GuardStatus.GAP

    semantic_receipts = [
        receipt
        for node_id in sorted(node_reports)
        for receipt in node_reports[node_id].semantic_receipts
    ]
    semantic_required = True
    semantic_status = aggregate_semantic_status(semantic_receipts)
    predictive_gaps, predictive_licensed, quantitative_coverage = _predictive_assessment(
        mesh,
        coverage_state,
        semantic_receipts,
    )
    expected_children = set(coverage_state["expected_children"])
    executed_children = {
        f"{receipt.node_id}:{receipt.guard}"
        for receipt in semantic_receipts
        if receipt.status not in {SemanticStatus.NOT_RUN, SemanticStatus.BOUNDARY_ONLY}
    }
    coverage_incomplete = bool(
        coverage_state["skipped_models"]
        or coverage_state["skipped_children"]
        or expected_children.difference(executed_children)
    )
    if semantic_status in {SemanticStatus.FAIL, SemanticStatus.BOUNDARY_ONLY}:
        rollout_status = semantic_status
    elif coverage_incomplete or (_predictive_requested(mesh) and not predictive_licensed):
        rollout_status = SemanticStatus.GAP
    else:
        rollout_status = semantic_status
    provider_status = aggregate_provider_status(
        semantic_receipts,
        required=semantic_required,
    )
    status = aggregate_statuses(
        [structural_status, _semantic_guard_status(rollout_status)]
    )
    scope_limits = []
    for node in mesh.nodes:
        if node.model_id in excluded_model_ids:
            continue
        scope_limits.extend(node.authority.scope_limits)
    depth_receipt = _depth_receipt(
        mesh,
        structural_status=structural_status,
        semantic_status=semantic_status,
        provider_status=provider_status,
        rollout_status=rollout_status,
        node_reports=node_reports,
        findings=findings,
        semantic_receipts=semantic_receipts,
        coverage_state=coverage_state,
        predictive_gaps=predictive_gaps,
        predictive_licensed=predictive_licensed,
        quantitative_coverage=quantitative_coverage,
    )
    return MeshReport(
        status=status,
        structural_status=structural_status,
        semantic_status=semantic_status,
        provider_status=provider_status,
        rollout_status=rollout_status,
        node_reports=node_reports,
        semantic_receipts=semantic_receipts,
        findings=findings,
        aggregate_ledger=aggregate_ledger,
        scope_limits=scope_limits,
        depth_receipt=depth_receipt,
    )


def _semantic_guard_status(status: SemanticStatus) -> GuardStatus:
    if status == SemanticStatus.PASS:
        return GuardStatus.PASS
    if status == SemanticStatus.FAIL:
        return GuardStatus.FAIL
    if status == SemanticStatus.BOUNDARY_ONLY:
        return GuardStatus.BOUNDARY_EXCEEDED
    return GuardStatus.GAP


def _native_obligation_observations(
    *,
    semantic_receipts: list[SemanticExecutionReceipt],
    quantitative_coverage: dict[str, Any],
    claim_atoms: list[dict[str, Any]],
    required_guards: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """Preserve exact WorldGuard-native content behind every depth obligation."""

    observations: list[dict[str, Any]] = []

    def add(
        native_object_id: str,
        obligation_ids: list[str],
        content: dict[str, Any],
    ) -> None:
        observations.append(
            {
                "native_object_id": native_object_id,
                "target_obligation_ids": obligation_ids,
                "evidence_ref": f"worldguard:{native_object_id}",
                "evidence_sha256": fingerprint_mesh(content),
                "content": content,
            }
        )

    for receipt in semantic_receipts:
        add(
            f"semantic-child:{receipt.node_id}:{receipt.guard}",
            ["obligation:worldguard-semantic-universe"],
            {"semantic_receipt": receipt.to_dict()},
        )

    for raw_node in quantitative_coverage.get("per_model_node_results", []):
        if not isinstance(raw_node, Mapping):
            continue
        node_id = str(raw_node.get("model_node_id", ""))
        timepoint_coverage = raw_node.get("timepoint_coverage", {})
        if node_id and isinstance(timepoint_coverage, Mapping):
            content = {
                "model_node_id": node_id,
                "timepoint_coverage": dict(timepoint_coverage),
            }
            add(
                f"timepoints:{node_id}",
                [
                    "obligation:worldguard-timepoint-strata-depth",
                    "obligation:worldguard-receipt-freshness",
                ],
                content,
            )
        for raw_variable in raw_node.get("per_variable_timepoint_results", []):
            if not isinstance(raw_variable, Mapping):
                continue
            variable_id = str(raw_variable.get("variable_or_signal_id", ""))
            variable_timepoints = raw_variable.get("timepoint_coverage", {})
            if node_id and variable_id and isinstance(variable_timepoints, Mapping):
                add(
                    f"timepoints:{node_id}:variable:{variable_id}",
                    [
                        "obligation:worldguard-timepoint-strata-depth",
                        "obligation:worldguard-receipt-freshness",
                    ],
                    {
                        "model_node_id": node_id,
                        "variable_or_signal_id": variable_id,
                        "timepoint_coverage": dict(variable_timepoints),
                    },
                )

    scenario_fields = {
        key: value
        for key, value in quantitative_coverage.items()
        if "scenario" in key or "holdout" in key
    }
    add(
        "scenario-holdout-portfolio",
        ["obligation:worldguard-scenario-holdout-depth"],
        scenario_fields,
    )
    predictive_axis_fields = {
        key: value
        for key, value in quantitative_coverage.items()
        if any(
            token in key
            for token in (
                "state",
                "transition",
                "event",
                "fluent",
                "branch",
                "perturbation",
                "intervention",
                "counterfactual",
                "horizon",
            )
        )
    }
    add(
        "predictive-axes",
        ["obligation:worldguard-predictive-axes"],
        predictive_axis_fields,
    )
    for atom in claim_atoms:
        node_id = str(atom.get("node_id", ""))
        atom_id = str(atom.get("atom_id", ""))
        add(
            f"claim-route:{node_id}:{atom_id}",
            ["obligation:worldguard-claim-routes"],
            {
                "claim_atom": atom,
                "required_guards": list(required_guards.get(node_id, [])),
            },
        )
    return observations


def _native_depth_identity(mesh: ModelMeshContract, coverage_state: dict[str, Any]) -> dict[str, Any]:
    """The producer's current input identity; no native execution occurs here."""
    fingerprint = fingerprint_mesh(mesh.to_dict())
    expected_nodes = coverage_state["expected_nodes"]
    claim_atoms = [
        {"node_id": node.model_id, **atom.to_dict()}
        for node in mesh.nodes
        if node.model_id in expected_nodes and node.contract
        for atom in node.contract.claim.atoms
    ]
    coverage_fingerprint = fingerprint_mesh(
        {
            "mesh_fingerprint": fingerprint,
            "semantic_coverage": mesh.semantic_coverage.to_dict(),
            "claim_atoms": claim_atoms,
            "required_guards": coverage_state["required_guards"],
            "expected_children": coverage_state["expected_children"],
            "discovered_model_nodes": coverage_state["discovered_nodes"],
            "declared_model_nodes": coverage_state["declared_nodes"],
            "excluded_model_nodes": coverage_state["excluded_models"],
            "model_node_reconciliation_gaps": coverage_state[
                "reconciliation_gaps"
            ],
        }
    )
    return {"mesh_fingerprint": fingerprint, "coverage_fingerprint": coverage_fingerprint, "claim_atoms": claim_atoms}


def validate_semantic_receipt_for_mesh(source: Mapping[str, Any], mesh: ModelMeshContract) -> SemanticExecutionReceipt:
    receipt = SemanticExecutionReceipt.from_dict(source)
    node = next((node for node in mesh.nodes if node.model_id == receipt.node_id), None)
    if node is None or node.contract is None or receipt.guard not in derive_required_guards(node.contract.claim):
        raise ValueError("semantic source does not belong to a current candidate node/Guard")
    variable_timepoints = _variable_timepoint_map(node.contract) if receipt.guard in {"EventGuard", "CausalGuard"} else {}
    expected = _semantic_consumed_inputs(receipt.guard, node.contract, variable_timepoints=variable_timepoints)
    if receipt.status not in {SemanticStatus.NOT_RUN, SemanticStatus.BOUNDARY_ONLY} and receipt.consumed_inputs != expected:
        raise ValueError("semantic source consumed inputs do not match the current candidate")
    return receipt


def validate_native_depth_receipt(source: Mapping[str, Any], mesh: ModelMeshContract) -> NativeDepthReceipt:
    """Validate a reusable native receipt against its exact current mesh inputs."""
    receipt = NativeDepthReceipt.from_dict(source)
    state = _coverage_route_state(mesh)
    identity = _native_depth_identity(mesh, state)
    expected = {
        **identity, "mesh_id": mesh.mesh_id, "run_id": mesh.run_id,
        "predictive_profile": mesh.semantic_coverage.profile,
        "required_guards": state["required_guards"], "declared_guards": state["declared_guards"],
        "missing_guards": state["missing_guards"], "expected_model_nodes": state["expected_nodes"],
        "discovered_model_nodes": state["discovered_nodes"], "declared_model_nodes": state["declared_nodes"],
        "excluded_model_nodes": state["excluded_models"], "model_node_reconciliation_gaps": state["reconciliation_gaps"],
        "expected_semantic_children": state["expected_children"],
    }
    if any(source[key] != value for key, value in expected.items()):
        raise ValueError("native depth source does not bind the current candidate mesh and coverage")
    if not receipt.semantic_receipts:
        raise ValueError("native depth source lacks reusable native semantic execution receipts")
    executions = [validate_semantic_receipt_for_mesh(row, mesh) for row in receipt.semantic_receipts]
    children = [f"{row.node_id}:{row.guard}" for row in executions]
    if len(children) != len(set(children)) or set(children) != set(receipt.expected_semantic_children):
        raise ValueError("native depth source semantic inventory is incomplete or duplicated")
    gaps, licensed, quantitative = _predictive_assessment(mesh, state, executions)
    if (receipt.predictive_gaps != gaps or receipt.predictive_claim_licensed != licensed
            or receipt.quantitative_coverage != quantitative):
        raise ValueError("native depth source coverage/license differs from native semantic outputs")
    executed = [f"{row.node_id}:{row.guard}" for row in executions if row.status not in {SemanticStatus.NOT_RUN, SemanticStatus.BOUNDARY_ONLY}]
    providers = {f"{row.node_id}:{row.guard}": row.provider_status.value for row in executions}
    for row in receipt.skipped_children:
        providers.setdefault(str(row.get("child_id", "")), "NOT_EXECUTED")
    obligations = _native_obligation_observations(semantic_receipts=executions, quantitative_coverage=quantitative, claim_atoms=identity["claim_atoms"], required_guards=state["required_guards"])
    if (receipt.executed_semantic_children != executed or receipt.provider_states != providers
            or receipt.bindings != [row.binding.to_dict() for row in executions]
            or receipt.native_obligation_evidence != obligations):
        raise ValueError("native depth source execution projections are inconsistent")
    summary = [row for row in receipt.findings if row.get("code") == "SEMANTIC_ROLLOUT_SUMMARY"]
    if len(summary) != 1 or summary[0].get("predictive_gaps") != gaps or summary[0].get("predictive_claim_licensed") is not licensed:
        raise ValueError("native depth summary and derived predictive license disagree")
    if licensed and (any(row.get("status") != "PASS" for row in receipt.structural_checks)
                     or {row.get("node_id") for row in receipt.structural_checks} != set(receipt.expected_model_nodes)
                     or summary[0].get("structural_status") != "PASS"):
        raise ValueError("native depth license requires complete passing structural checks")
    return receipt


def _depth_receipt(
    mesh: ModelMeshContract,
    *,
    structural_status: GuardStatus,
    semantic_status: SemanticStatus,
    provider_status: ProviderStatus,
    rollout_status: SemanticStatus,
    node_reports: dict[str, GuardedReport],
    findings: list[MeshFinding],
    semantic_receipts: list[SemanticExecutionReceipt],
    coverage_state: dict[str, Any],
    predictive_gaps: list[str],
    predictive_licensed: bool,
    quantitative_coverage: dict[str, Any],
) -> NativeDepthReceipt:
    structural_checks = [
        {"node_id": node_id, "status": report.status.value}
        for node_id, report in sorted(node_reports.items())
    ]
    structural_checks.extend(
        {
            "finding_id": finding.finding_id,
            "code": finding.code,
            "status": finding.status.value,
        }
        for finding in findings
    )
    executed = [
        f"{receipt.node_id}:{receipt.guard}"
        for receipt in semantic_receipts
        if receipt.status not in {SemanticStatus.NOT_RUN, SemanticStatus.BOUNDARY_ONLY}
    ]
    skipped = [
        {
            "child_id": f"{receipt.node_id}:{receipt.guard}",
            "node_id": receipt.node_id,
            "guard": receipt.guard,
            "reason": receipt.skipped_reason or receipt.status.value,
            "coverage_impact": "required_semantic_child_not_executed",
        }
        for receipt in semantic_receipts
        if receipt.status in {SemanticStatus.NOT_RUN, SemanticStatus.BOUNDARY_ONLY}
    ]
    skipped.extend(coverage_state["skipped_children"])
    if predictive_licensed:
        boundary = (
            "Predictive coverage is licensed only for the current mesh fingerprint, "
            "structured claim atoms, declared horizon, scenarios, holdouts, branches, "
            "perturbations, interventions, counterfactuals, and supported executors."
        )
    elif structural_status == GuardStatus.PASS and rollout_status == SemanticStatus.PASS:
        boundary = (
            "Bounded semantic rollout passed only for the declared WorldGuard executor "
            "subsets; predictive readiness was not licensed."
        )
    else:
        boundary = "Semantic closure is incomplete; do not claim full world-model validity or prediction."
    executed_set = set(executed)
    for child_id in sorted(set(coverage_state["expected_children"]).difference(executed_set)):
        if any(row.get("child_id") == child_id for row in skipped):
            continue
        node_id, _, guard = child_id.partition(":")
        skipped.append(
            {
                "child_id": child_id,
                "node_id": node_id,
                "guard": guard,
                "reason": "expected_semantic_child_not_executed",
                "coverage_impact": "required_semantic_child_not_executed",
            }
        )
    semantic_findings = [
        {"node_id": receipt.node_id, "guard": receipt.guard, **finding}
        for receipt in semantic_receipts
        for finding in receipt.findings
    ]
    semantic_findings.append(
        {
            "code": "SEMANTIC_ROLLOUT_SUMMARY",
            "structural_status": structural_status.value,
            "semantic_status": semantic_status.value,
            "provider_status": provider_status.value,
            "rollout_status": rollout_status.value,
            "predictive_claim_licensed": predictive_licensed,
            "predictive_gaps": predictive_gaps,
        }
    )
    provider_states = {
        f"{receipt.node_id}:{receipt.guard}": receipt.provider_status.value
        for receipt in semantic_receipts
    }
    for row in skipped:
        child_id = str(row.get("child_id", ""))
        if child_id:
            provider_states.setdefault(child_id, "NOT_EXECUTED")
    bindings = [
        {
            **receipt.binding.to_dict(),
        }
        for receipt in semantic_receipts
    ]
    identity = _native_depth_identity(mesh, coverage_state)
    fingerprint = identity["mesh_fingerprint"]
    coverage_fingerprint = identity["coverage_fingerprint"]
    claim_atoms = identity["claim_atoms"]
    expected_nodes = coverage_state["expected_nodes"]
    executed_nodes = sorted(
        node_id
        for node_id in expected_nodes
        if any(child.startswith(f"{node_id}:") for child in executed_set)
    )
    return NativeDepthReceipt(
        receipt_id=f"{mesh.run_id}:{mesh.mesh_id}:semantic-depth:{fingerprint[:12]}",
        mesh_id=mesh.mesh_id,
        run_id=mesh.run_id,
        mesh_fingerprint=fingerprint,
        structural_checks=structural_checks,
        executed_semantic_children=executed,
        provider_states=provider_states,
        bindings=bindings,
        findings=semantic_findings,
        skipped_children=skipped,
        claim_boundary=boundary,
        receipt_version="worldguard.native_depth.v2",
        generated_at=datetime.now(timezone.utc).isoformat(),
        coverage_fingerprint=coverage_fingerprint,
        predictive_profile=mesh.semantic_coverage.profile,
        claim_atoms=claim_atoms,
        required_guards=coverage_state["required_guards"],
        declared_guards=coverage_state["declared_guards"],
        missing_guards=coverage_state["missing_guards"],
        expected_model_nodes=expected_nodes,
        discovered_model_nodes=coverage_state["discovered_nodes"],
        declared_model_nodes=coverage_state["declared_nodes"],
        excluded_model_nodes=coverage_state["excluded_models"],
        model_node_reconciliation_gaps=coverage_state["reconciliation_gaps"],
        executed_model_nodes=executed_nodes,
        skipped_model_nodes=coverage_state["skipped_models"],
        expected_semantic_children=coverage_state["expected_children"],
        quantitative_coverage=quantitative_coverage,
        predictive_gaps=predictive_gaps,
        native_obligation_evidence=_native_obligation_observations(
            semantic_receipts=semantic_receipts,
            quantitative_coverage=quantitative_coverage,
            claim_atoms=claim_atoms,
            required_guards=coverage_state["required_guards"],
        ),
        predictive_claim_licensed=predictive_licensed,
        semantic_receipts=[receipt.to_dict() for receipt in semantic_receipts],
    )


def _authority_findings(mesh: ModelMeshContract, node: ModelNode) -> list[MeshFinding]:
    if node.contract is None:
        return []
    requested = {
        semantic
        for semantic in claim_semantics(node.contract.claim)
        if semantic not in {"prediction", "predictive", "forecast", "future_outcome"}
    }
    excluded = requested.intersection(node.authority.excludes)
    if excluded:
        return [
            _finding(
                mesh,
                GuardStatus.BOUNDARY_EXCEEDED,
                "MESH_AUTHORITY_EXCLUDED_SEMANTIC",
                "Node contract requests semantics excluded by model authority.",
                node_id=node.model_id,
                evidence={"excluded_semantics": sorted(excluded)},
            )
        ]
    missing = requested.difference(node.authority.owns)
    if node.authority.owns and missing:
        return [
            _finding(
                mesh,
                GuardStatus.GAP,
                "MESH_AUTHORITY_UNOWNED_SEMANTIC",
                "Node contract requests semantics not owned by model authority.",
                node_id=node.model_id,
                evidence={"unowned_semantics": sorted(missing)},
            )
        ]
    return []


def _edge_findings(
    mesh: ModelMeshContract,
    edge: ModelEdge,
    node_ids: set[str],
    nodes_by_id: dict[str, ModelNode],
) -> list[MeshFinding]:
    findings: list[MeshFinding] = []
    if edge.source_model_id not in node_ids:
        findings.append(
            _finding(
                mesh,
                GuardStatus.GAP,
                "MESH_MISSING_SOURCE_NODE",
                "Handoff source model id is missing from mesh nodes.",
                edge_id=edge.edge_id,
                evidence=edge.to_dict(),
            )
        )
    if edge.target_model_id not in node_ids:
        findings.append(
            _finding(
                mesh,
                GuardStatus.GAP,
                "MESH_MISSING_TARGET_NODE",
                "Handoff target model id is missing from mesh nodes.",
                edge_id=edge.edge_id,
                evidence=edge.to_dict(),
            )
        )
    if not edge.read_only:
        findings.append(
            _finding(
                mesh,
                GuardStatus.FAIL,
                "MESH_MUTABLE_HANDOFF",
                "Mesh handoffs must be read-only.",
                edge_id=edge.edge_id,
                evidence=edge.to_dict(),
            )
        )
    transferred_source_ports = {
        mapping.source_port_id for mapping in edge.port_mappings
    }
    forbidden = sorted(transferred_source_ports.intersection(edge.forbidden_use))
    if forbidden:
        findings.append(
            _finding(
                mesh,
                GuardStatus.FAIL,
                "MESH_FORBIDDEN_DOWNSTREAM_USE",
                "Downstream handoff consumes output refs listed as forbidden.",
                edge_id=edge.edge_id,
                evidence={"forbidden_refs": forbidden, "edge": edge.to_dict()},
            )
        )
    if edge.allowed_use:
        unallowed = sorted(transferred_source_ports.difference(edge.allowed_use))
        if unallowed:
            findings.append(
                _finding(
                    mesh,
                    GuardStatus.BOUNDARY_EXCEEDED,
                    "MESH_UNALLOWED_DOWNSTREAM_USE",
                    "Downstream handoff consumes output refs outside the allowed-use boundary.",
                    edge_id=edge.edge_id,
                    evidence={"unallowed_refs": unallowed, "edge": edge.to_dict()},
                )
            )
    source = nodes_by_id.get(edge.source_model_id)
    target = nodes_by_id.get(edge.target_model_id)
    if source and target and edge.relation in TRANSFER_RELATIONS:
        source_ports = {port.port_id: port for port in source.output_ports}
        target_ports = {port.port_id: port for port in target.input_ports}
        for mapping in edge.port_mappings:
            source_port = source_ports.get(mapping.source_port_id)
            target_port = target_ports.get(mapping.target_port_id)
            if source_port is None:
                findings.append(
                    _finding(
                        mesh,
                        GuardStatus.FAIL,
                        "MESH_UNKNOWN_SOURCE_PORT",
                        "Port mapping names an undeclared producer output.",
                        edge_id=edge.edge_id,
                        evidence={
                            "mapping": mapping.to_dict(),
                            "declared_source_ports": sorted(source_ports),
                        },
                    )
                )
                continue
            if target_port is None:
                findings.append(
                    _finding(
                        mesh,
                        GuardStatus.FAIL,
                        "MESH_UNKNOWN_TARGET_PORT",
                        "Port mapping names an undeclared consumer input.",
                        edge_id=edge.edge_id,
                        evidence={
                            "mapping": mapping.to_dict(),
                            "declared_target_ports": sorted(target_ports),
                        },
                    )
                )
                continue
            if (
                source_port.value_type != target_port.value_type
                or source_port.cardinality != target_port.cardinality
            ):
                findings.append(
                    _finding(
                        mesh,
                        GuardStatus.FAIL,
                        "MESH_INCOMPATIBLE_PORT_MAPPING",
                        "Producer and consumer ports have incompatible type or cardinality.",
                        edge_id=edge.edge_id,
                        evidence={
                            "mapping": mapping.to_dict(),
                            "source_port": source_port.to_dict(),
                            "target_port": target_port.to_dict(),
                        },
                    )
                )
    if edge.requires_current_source and source and source.freshness_status != "current":
        findings.append(
            _finding(
                mesh,
                GuardStatus.GAP,
                "MESH_STALE_SOURCE",
                "Handoff requires current source evidence but source is not current.",
                node_id=edge.source_model_id,
                edge_id=edge.edge_id,
                evidence={"freshness_status": source.freshness_status, "edge": edge.to_dict()},
            )
        )
    return findings


def _cycles(edges: list[ModelEdge]) -> list[list[str]]:
    graph: dict[str, list[str]] = {}
    for edge in edges:
        if edge.relation in CYCLE_RELATIONS:
            graph.setdefault(edge.source_model_id, []).append(edge.target_model_id)

    visiting: list[str] = []
    visited: set[str] = set()
    cycles: list[list[str]] = []

    def visit(node: str) -> None:
        if node in visiting:
            cycles.append([*visiting[visiting.index(node) :], node])
            return
        if node in visited:
            return
        visiting.append(node)
        for child in graph.get(node, []):
            visit(child)
        visiting.pop()
        visited.add(node)

    for node in list(graph):
        visit(node)
    return cycles


def _finding(
    mesh: ModelMeshContract,
    status: GuardStatus,
    code: str,
    message: str,
    *,
    node_id: str = "",
    edge_id: str = "",
    evidence: dict[str, Any] | None = None,
) -> MeshFinding:
    suffix = node_id or edge_id or str(len(code))
    return MeshFinding(
        finding_id=f"{mesh.run_id}:{mesh.mesh_id}:{code}:{suffix}",
        status=status,
        code=code,
        message=message,
        node_id=node_id,
        edge_id=edge_id,
        evidence=evidence or {},
    )


def _finding_ledgers(mesh: ModelMeshContract, findings: list[MeshFinding]) -> list[LedgerEntry]:
    entries = []
    for finding in findings:
        if finding.status == GuardStatus.FAIL:
            impact = "supports_fail"
            channel = "aggregate"
        elif finding.status == GuardStatus.GAP:
            impact = "creates_gap"
            channel = "gap"
        elif finding.status == GuardStatus.BOUNDARY_EXCEEDED:
            impact = "marks_boundary"
            channel = "boundary"
        else:
            impact = "informational"
            channel = "aggregate"
        entries.append(
            ledger_entry(
                run_id=mesh.run_id,
                claim_id=mesh.mesh_id,
                guard="ModelMesh",
                channel=channel,
                status_impact=impact,
                payload=finding.to_dict(),
                step=finding.code,
            )
        )
    return entries
