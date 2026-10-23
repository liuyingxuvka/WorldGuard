from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from math import isfinite
from collections.abc import Mapping
from typing import Any

from .contracts import (
    GuardContract,
    claim_semantics,
)
from .kernel import run_worldguard
from .io import load_mapping
from .clock import event_time_values, time_key, validate_times
from .semantic import event_replay, token_replay, causal_scenario_values, _fluent_values
from .qualification import QualificationContext
from .reports import GuardedReport
from .status import GuardStatus, aggregate_statuses, coerce_status


FRESHNESS_STATUSES = {"current", "stale", "unknown"}
EDGE_RELATIONS = {
    "continues",
    "parent_child",
    "depends_on",
    "refines",
    "replaces",
    "conflicts_with",
    "consumes_output_of",
    "same_world_version",
    "supersedes",
}

CYCLE_RELATIONS = {
    "continues",
    "parent_child",
    "depends_on",
    "refines",
    "replaces",
    "consumes_output_of",
    "supersedes",
}
TRANSFER_RELATIONS = {"parent_child", "consumes_output_of"}
PORT_CARDINALITIES = {"one", "optional", "many"}


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
    source: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, base_dir: str | Path | None = None) -> "ModelNode":
        if not isinstance(data, Mapping):
            raise ValueError("model node must be a mapping")
        if not isinstance(data.get("source", ""), str):
            raise ValueError("model node source must be a string")
        contract_data = data.get("contract")
        if isinstance(contract_data, str):
            path = Path(base_dir or ".") / contract_data
            try:
                contract_data = load_mapping(path)
            except (OSError, UnicodeError, ValueError) as exc:
                raise ValueError(f"node {data.get('model_id', '')} contract {path}: {exc}") from exc
        if contract_data is not None and not isinstance(contract_data, Mapping):
            raise ValueError("model node contract must be a mapping, file path or null")
        freshness_status = str(data.get("freshness_status", "current"))
        if freshness_status not in FRESHNESS_STATUSES:
            raise ValueError(f"node {data.get('model_id', '')}: unknown freshness_status {freshness_status!r}")
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
            source=data.get("source", ""),
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
        if self.source:
            data["source"] = self.source
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
    variables: list[str] = field(default_factory=list)

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
        variables = data.get("variables", [])
        if not isinstance(variables, list) or any(not isinstance(name, str) or not name.strip() for name in variables):
            raise ValueError("edge variables must be a list of nonempty names")
        if len(variables) != len(set(variables)):
            raise ValueError("edge variables must be unique")
        if variables and relation != "continues":
            raise ValueError("edge variables are only valid on continues edges")
        if relation == "consumes_output_of" and not port_mappings:
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
            variables=variables,
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
            **({"variables": self.variables} if self.variables else {}),
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


@dataclass(frozen=True)
class ModelMeshContract:
    mesh_id: str
    schema_version: str = "worldguard.model_mesh.v1"
    run_id: str = "worldguard-mesh-run"
    nodes: list[ModelNode] = field(default_factory=list)
    edges: list[ModelEdge] = field(default_factory=list)
    snapshots: list[WorldStateSnapshot] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any], *, base_dir: str | Path | None = None) -> "ModelMeshContract":
        if not isinstance(data, Mapping):
            raise ValueError("model mesh must be a mapping")
        for name in ("nodes", "edges", "snapshots"):
            rows = data.get(name, [])
            if not isinstance(rows, (list, tuple)):
                raise ValueError(f"{name} must be a list of mappings")
            for index, row in enumerate(rows):
                if not isinstance(row, Mapping):
                    raise ValueError(f"{name}[{index}] must be a mapping")
        if "provider_availability" in data:
            raise ValueError("provider_availability is retired")
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
        if "semantic_coverage" in data:
            raise ValueError("semantic_coverage is retired; every node in the mesh is checked")
        nodes = [ModelNode.from_dict(item, base_dir=base_dir) for item in data.get("nodes", [])]
        return cls(
            mesh_id=str(data.get("mesh_id", "")),
            schema_version=str(data.get("schema_version", "worldguard.model_mesh.v1")),
            run_id=str(data.get("run_id", "worldguard-mesh-run")),
            nodes=nodes,
            edges=[ModelEdge.from_dict(item) for item in data.get("edges", [])],
            snapshots=[
                WorldStateSnapshot.from_dict(item) for item in data.get("snapshots", [])
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mesh_id": self.mesh_id,
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
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
    checked: dict[str, int] = field(default_factory=dict)
    scope_limits: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)

    def to_dict(self):
        return {"status": self.status.value, "checked": self.checked,
                "gaps": [*[{**({"source": self.sources[finding.node_id]} if self.sources.get(finding.node_id) else {}), **finding.to_dict()} for finding in self.findings],
                         *[{**({"source": self.sources[node_id]} if self.sources.get(node_id) else {}), "node_id": node_id, **gap} for node_id, report in sorted(self.node_reports.items()) for gap in report.gaps]],
                "nodes": {node_id: report.to_dict() for node_id, report in sorted(self.node_reports.items())},
                "scope_limits": self.scope_limits}


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
    )


def run_model_mesh(mesh: ModelMeshContract | Mapping[str, Any], *, base_dir: str | Path | None = None) -> MeshReport:
    if not isinstance(mesh, ModelMeshContract):
        mesh = ModelMeshContract.from_dict(dict(mesh), base_dir=base_dir)

    node_reports: dict[str, GuardedReport] = {}
    findings: list[MeshFinding] = []
    node_ids: set[str] = set()
    duplicate_ids: set[str] = set()

    nodes_by_id = {node.model_id: node for node in mesh.nodes}
    contracts = {node.model_id: node.contract for node in mesh.nodes if node.contract is not None}
    for node in mesh.nodes:
        if node.model_id in node_ids:
            duplicate_ids.add(node.model_id)
        node_ids.add(node.model_id)
        findings.extend(_authority_findings(mesh, node))
        if node.contract is not None:
            report = run_worldguard(
                node.contract,
                context=replace(qualification_context_for_node(mesh, node), node_contracts=contracts,
                                descendant_ids=_descendants(mesh, node.model_id)),
            )
            node_reports[node.model_id] = report
        else:
            findings.append(_finding(
                mesh, GuardStatus.GAP, "MESH_EXPECTED_NODE_CONTRACT_MISSING",
                "Every mesh node requires a Guard contract, embedded or loaded from a file.",
                node_id=node.model_id,
            ))

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
        findings.extend(_edge_findings(mesh, edge, node_ids, nodes_by_id))
        if edge.relation == "continues" and edge.source_model_id in contracts and edge.target_model_id in contracts:
            findings.extend(_continues_findings(mesh, edge, contracts[edge.source_model_id], contracts[edge.target_model_id]))

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

    status = aggregate_statuses([*[r.status for r in node_reports.values()], *[f.status for f in findings]])
    return MeshReport(status=status, node_reports=node_reports, findings=findings,
        checked={"nodes": len(mesh.nodes), "edges": len(mesh.edges),
                 "roots": len(node_ids - {edge.target_model_id for edge in mesh.edges if edge.relation == "parent_child"})},
        sources={node.model_id: node.source for node in mesh.nodes if node.source},
        scope_limits=sorted({limit for node in mesh.nodes for limit in node.authority.scope_limits}))


def _descendants(mesh: ModelMeshContract, model_id: str) -> frozenset[str]:
    children: dict[str, list[str]] = {}
    for edge in mesh.edges:
        if edge.relation == "parent_child":
            children.setdefault(edge.source_model_id, []).append(edge.target_model_id)
    seen, todo = {model_id}, list(children.get(model_id, []))
    while todo:
        child = todo.pop()
        if child not in seen:
            seen.add(child)
            todo.extend(children.get(child, []))
    return frozenset(seen - {model_id})


def _continues_findings(mesh: ModelMeshContract, edge: ModelEdge, source: GuardContract, target: GuardContract) -> list[MeshFinding]:
    """Compare the actual source end state to the target's declared start."""
    findings = []
    def add(status, code, message, **evidence):
        findings.append(_finding(mesh, status, code, message, edge_id=edge.edge_id, evidence=evidence))
    source_events = source.inputs.get("events", [])
    target_events = target.inputs.get("events", [])
    named_times = [(f"edge {edge.edge_id} {side} event {event.get('event_id')}", event.get("at"))
                   for side, events in (("source", source_events), ("target", target_events)) for event in events]
    validate_times(named_times)
    if source_events and target_events:
        end = max((event["at"] for event in source_events), key=time_key)
        start = min((event["at"] for event in target_events), key=time_key)
        if time_key(start) < time_key(end):
            add(GuardStatus.FAIL, "MESH_HANDOFF_TIME_BACKWARDS", "Target begins before the source ends.", source_end=end, target_start=start)
    source_initial = source.inputs.get("event_model", {}).get("initial_states", [])
    target_initial = target.inputs.get("event_model", {}).get("initial_states", [])
    holding = frozenset(_fluent_values(source_initial))
    for _event, _before, after in event_replay(source_events, source_initial):
        holding = after
    target_start = set(_fluent_values(target_initial))
    mentioned = set(target_start)
    for event in target_events:
        for key in ("requires", "initiates", "terminates", "releases"):
            mentioned.update(_fluent_values(event.get(key)))
    for fluent in sorted(mentioned):
        if (fluent in holding) != (fluent in target_start):
            add(GuardStatus.FAIL, "MESH_HANDOFF_STATE_MISMATCH", "A target fluent differs from the source end state.",
                fluent=fluent, source_end=fluent in holding, target_initial=fluent in target_start)
    source_resources = source.inputs.get("resources", {})
    target_resources = target.inputs.get("resources", {})
    shared = set(source_resources.get("unique", [])) & set(target_resources.get("unique", []))
    if shared:
        final, source_error = token_replay(source_resources, events=source_events)
        initial, target_error = token_replay({**target_resources, "transitions": []})
        if source_error is not None or target_error is not None:
            add(GuardStatus.FAIL, "MESH_HANDOFF_STATE_MISMATCH", "A unique token state cannot be replayed across this edge.",
                source_error=source_error, target_error=target_error)
        else:
            for color in sorted(shared):
                left = {place: qty for (place, token), qty in final.items() if token == color and qty}
                right = {place: qty for (place, token), qty in initial.items() if token == color and qty}
                if left != right:
                    add(GuardStatus.FAIL, "MESH_HANDOFF_STATE_MISMATCH", "A unique token starts at a different location.",
                        color=color, source_end=left, target_initial=right)
    if edge.variables:
        source_values = causal_scenario_values(source.inputs.get("causal_model", {}), event_time_values(source_events))
        target_values = causal_scenario_values(target.inputs.get("causal_model", {}), event_time_values(target_events))
        for scenario in sorted(target_values) or ["<none>"]:
            left = next(iter(source_values.values())) if len(source_values) == 1 else source_values.get(scenario, {})
            right = target_values.get(scenario, {})
            for name in edge.variables:
                if name not in left or name not in right:
                    add(GuardStatus.GAP, "MESH_HANDOFF_VALUE_MISSING", "A requested variable cannot be compared.",
                        variable=name, scenario=scenario, source_value=left.get(name), target_value=right.get(name))
                elif not isfinite(left[name]) or not isfinite(right[name]):
                    raise ValueError(f"edge {edge.edge_id}: variable {name} in {scenario} must be finite")
                elif abs(left[name] - right[name]) > 1e-9:
                    add(GuardStatus.FAIL, "MESH_HANDOFF_VALUE_MISMATCH", "A carried variable differs between nodes.",
                        variable=name, scenario=scenario, source_value=left[name], target_value=right[name])
    return findings


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
