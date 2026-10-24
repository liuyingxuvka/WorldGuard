"""One tree of native world contracts and their ordered continuations."""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from copy import deepcopy
from pathlib import Path
from math import isfinite
from collections.abc import Mapping
from typing import Any
from .contracts import GuardContract
from .kernel import run_worldguard
from .io import load_mapping
from .clock import event_time_values, time_key, validate_times
from .semantic import event_replay, token_replay, causal_scenario_values, _fluent_values
from .qualification import QualificationContext
from .reports import GuardedReport
from .status import GuardStatus, aggregate_statuses, coerce_status
from .variants import validate_variants, apply_variant

EDGE_RELATIONS = {"parent_child", "continues"}
CYCLE_RELATIONS = EDGE_RELATIONS


def _retired(data, fields, where):
    for key in sorted(set(data) & set(fields)):
        raise ValueError(f"{where}{key} is retired; use model_id/contract/source nodes and from/to parent_child or continues edges")


@dataclass(frozen=True)
class ModelNode:
    model_id: str
    contract: GuardContract | None = None
    source: str = ""
    raw_contract: dict | None = field(default=None, repr=False, compare=False)

    @classmethod
    def from_dict(cls, data, *, base_dir=None):
        if not isinstance(data, Mapping):
            raise ValueError("model node must be a mapping")
        _retired(data, {"model_version", "model_kind", "authority", "freshness_status", "input_ports", "output_ports"}, "node.")
        if set(data) - {"model_id", "contract", "source"}:
            raise ValueError("model node has unknown fields: " + ", ".join(sorted(set(data)-{"model_id", "contract", "source"})))
        if not isinstance(data.get("source", ""), str):
            raise ValueError("model node source must be a string")
        contract = data.get("contract")
        if isinstance(contract, str):
            path = Path(base_dir or ".") / contract
            try:
                contract = load_mapping(path)
            except (OSError, UnicodeError, ValueError) as exc:
                raise ValueError(f"node {data.get('model_id', '')} contract {path}: {exc}") from exc
        if contract is not None and not isinstance(contract, Mapping):
            raise ValueError("model node contract must be a mapping, file path or null")
        return cls(str(data.get("model_id", "")), GuardContract.from_dict(contract) if contract is not None else None, data.get("source", ""), deepcopy(dict(contract)) if contract is not None else None)

    def to_dict(self):
        result = {"model_id": self.model_id}
        if self.contract is not None:
            result["contract"] = deepcopy(self.raw_contract) if self.raw_contract is not None else self.contract.to_dict()
        if self.source:
            result["source"] = self.source
        return result


@dataclass(frozen=True)
class ModelEdge:
    edge_id: str
    from_id: str
    to_id: str
    relation: str
    variables: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, Mapping):
            raise ValueError("model edge must be a mapping")
        _retired(data, {"source_model_id", "target_model_id", "port_mappings", "output_refs", "allowed_use", "forbidden_use", "read_only", "requires_current_source"}, "edge.")
        if set(data)-{"edge_id", "from", "to", "relation", "variables"}:
            raise ValueError("model edge has unknown fields")
        relation = data.get("relation")
        if relation not in EDGE_RELATIONS:
            raise ValueError(f"edge relation {relation!r} is retired or unknown; use parent_child or continues")
        variables = data.get("variables", [])
        if not isinstance(variables, list) or any(not isinstance(v, str) or not v.strip() for v in variables) or len(variables)!=len(set(variables)):
            raise ValueError("edge variables must be unique nonempty names")
        if variables and relation != "continues":
            raise ValueError("edge variables are only valid on continues edges")
        return cls(str(data.get("edge_id", "")), str(data.get("from", "")), str(data.get("to", "")), relation, variables)

    def to_dict(self):
        return {"edge_id":self.edge_id,"from":self.from_id,"to":self.to_id,"relation":self.relation, **({"variables":self.variables} if self.variables else {})}


@dataclass(frozen=True)
class ModelMeshContract:
    mesh_id: str
    nodes: list[ModelNode] = field(default_factory=list)
    edges: list[ModelEdge] = field(default_factory=list)
    variants: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data, *, base_dir=None):
        if not isinstance(data, Mapping):
            raise ValueError("model mesh must be a mapping")
        _retired(data, {"schema_version", "run_id", "snapshots", "provider_availability", "closure_profile", "semantic_coverage", "semantic_coverage_contract", "coverage_contract"}, "mesh.")
        if set(data)-{"mesh_id", "nodes", "edges", "variants"}:
            raise ValueError("model mesh has unknown fields")
        for name in ("nodes", "edges"):
            if not isinstance(data.get(name, []), (list, tuple)) or any(not isinstance(row, Mapping) for row in data.get(name, [])):
                raise ValueError(f"{name} must be a list of mappings")
        variants=data.get("variants", []);validate_variants(variants)
        return cls(str(data.get("mesh_id", "")), [ModelNode.from_dict(n,base_dir=base_dir) for n in data.get("nodes",[])], [ModelEdge.from_dict(e) for e in data.get("edges",[])], variants)

    def to_dict(self):
        return {"mesh_id":self.mesh_id,"nodes":[n.to_dict() for n in self.nodes],"edges":[e.to_dict() for e in self.edges], **({"variants":self.variants} if self.variants else {})}


@dataclass(frozen=True)
class MeshFinding:
    finding_id: str
    status: GuardStatus
    code: str
    message: str
    node_id: str = ""
    edge_id: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    def __post_init__(self):
        object.__setattr__(self,"status",coerce_status(self.status))
    def to_dict(self):
        return {"finding_id":self.finding_id,"status":self.status.value,"code":self.code,"message":self.message,"node_id":self.node_id,"edge_id":self.edge_id,"evidence":self.evidence}


@dataclass(frozen=True)
class MeshReport:
    status: GuardStatus
    node_reports: dict[str, GuardedReport] = field(default_factory=dict)
    findings: list[MeshFinding] = field(default_factory=list)
    checked: dict[str, int] = field(default_factory=dict)
    scope_limits: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)
    tree: list[str] = field(default_factory=list)
    variants: list[dict[str, Any]] = field(default_factory=list)
    def to_dict(self):
        return {"status":self.status.value,"checked":self.checked,
                "gaps":[*[{**({"source":self.sources[f.node_id]} if self.sources.get(f.node_id) else {}),**f.to_dict()} for f in self.findings],
                        *[{**({"source":self.sources[node_id]} if self.sources.get(node_id) else {}),"node_id":node_id,**gap} for node_id,report in sorted(self.node_reports.items()) for gap in report.gaps]],
                "nodes":{key:r.to_dict() for key,r in sorted(self.node_reports.items())},"scope_limits":self.scope_limits,"tree":self.tree,
                **({"variants":self.variants} if self.variants else {})}


def _descendants(mesh, model_id):
    children={}
    for edge in mesh.edges:
        if edge.relation=="parent_child":children.setdefault(edge.from_id,[]).append(edge.to_id)
    seen,todo={model_id},list(children.get(model_id,[]))
    while todo:
        child=todo.pop()
        if child not in seen:seen.add(child);todo.extend(children.get(child,[]))
    return frozenset(seen-{model_id})


def _tree_shape(mesh):
    """Parents, children and continuations among existing nodes; roots and whether they form one tree."""
    ids = {n.model_id for n in mesh.nodes}
    parents, children, continuations = {}, {}, {}
    for edge in mesh.edges:
        if edge.from_id not in ids or edge.to_id not in ids:
            continue
        if edge.relation == "parent_child":
            parents.setdefault(edge.to_id, []).append(edge.from_id)
            children.setdefault(edge.from_id, []).append(edge.to_id)
        elif edge.relation == "continues":
            continuations.setdefault(edge.from_id, []).append(edge)
    roots = sorted(ids - parents.keys())
    reachable = set()
    todo = list(roots)
    while todo:
        node = todo.pop()
        if node not in reachable:
            reachable.add(node)
            todo.extend(children.get(node, []))
    multiple = sorted(node for node, ps in parents.items() if len(ps) > 1)
    valid = len(roots) == 1 and not multiple and reachable == ids
    return ids, parents, children, continuations, roots, multiple, valid


def _common_ancestor(parents, left, right):
    """The nearest node whose subtree holds both ends (first parent wins), or None."""
    chain, node = [], left
    while node is not None and node not in chain:
        chain.append(node)
        node = (parents.get(node) or [None])[0]
    node, seen = right, set()
    while node is not None and node not in seen:
        if node in chain:
            return node
        seen.add(node)
        node = (parents.get(node) or [None])[0]
    return None


def _tree_structure(mesh, reports, findings):
    """Tree lines: own status, subtree status when it differs, and each continues edge's result."""
    ids, parents, children, continuations, roots, _multiple, _valid = _tree_shape(mesh)
    planned = {n.model_id for n in mesh.nodes if n.contract is None}
    own = {node: (reports[node].status if node in reports else GuardStatus.GAP) for node in ids}
    edges = {edge.edge_id: edge for edge in mesh.edges}
    placed, edge_findings, tree_level = {}, {}, []
    for finding in findings:
        edge = edges.get(finding.edge_id) if finding.edge_id else None
        if finding.node_id in ids:
            placed.setdefault(finding.node_id, []).append(finding.status)
        elif edge is not None and edge.from_id in ids and edge.to_id in ids:
            edge_findings.setdefault(edge.edge_id, []).append(finding)
            home = _common_ancestor(parents, edge.from_id, edge.to_id)
            if home is None:
                tree_level.append(finding.status)
            else:
                placed.setdefault(home, []).append(finding.status)
        else:
            tree_level.append(finding.status)
    seen, lines = set(), []

    def subtree(node, top):
        statuses, todo, inside = [], [node], set()
        while todo:
            current = todo.pop()
            if current in inside:
                continue
            inside.add(current)
            statuses.append(own[current])
            statuses.extend(placed.get(current, []))
            todo.extend(children.get(current, []))
        if top:
            statuses.extend(tree_level)
        return aggregate_statuses(statuses)

    def segment(edge):
        rows = edge_findings.get(edge.edge_id, [])
        if not rows and (edge.from_id in planned or edge.to_id in planned):
            return f" -> continues {edge.to_id} GAP planned"
        status = aggregate_statuses([row.status for row in rows]) if rows else GuardStatus.PASS
        codes = ",".join(sorted({row.code for row in rows}))
        return f" -> continues {edge.to_id} {status.value}" + (f" {codes}" if codes else "")

    def visit(node, depth, top):
        if node in seen:
            return
        seen.add(node)
        mine = "GAP planned" if node in planned else own[node].value
        whole = subtree(node, top)
        line = "  " * depth + node + " " + mine
        if whole != own[node]:
            line += f" (tree {whole.value})"
        for edge in sorted(continuations.get(node, []), key=lambda e: (e.to_id, e.edge_id)):
            line += segment(edge)
        lines.append(line)
        for child in sorted(children.get(node, [])):
            visit(child, depth + 1, False)
    for root in roots:
        visit(root, 0, True)
    for node in sorted(ids - seen):
        visit(node, 0, True)
    return lines


def qualification_context_for_node(mesh, node):
    return QualificationContext(node_contracts={n.model_id:n.contract for n in mesh.nodes if n.contract is not None}, descendant_ids=_descendants(mesh,node.model_id))


def run_model_mesh(mesh, *, base_dir=None):
    if not isinstance(mesh,ModelMeshContract):mesh=ModelMeshContract.from_dict(mesh,base_dir=base_dir)
    findings=[];reports={};ids=set();duplicates=set();contracts={n.model_id:n.contract for n in mesh.nodes if n.contract is not None}
    for node in mesh.nodes:
        if node.model_id in ids:duplicates.add(node.model_id)
        ids.add(node.model_id)
        if node.contract is None:
            findings.append(_finding(mesh,GuardStatus.GAP,"MESH_EXPECTED_NODE_CONTRACT_MISSING","Every node requires a world contract.",node_id=node.model_id))
        else:
            reports[node.model_id]=run_worldguard(node.contract,context=qualification_context_for_node(mesh,node))
    for node in sorted(duplicates):findings.append(_finding(mesh,GuardStatus.FAIL,"MESH_DUPLICATE_MODEL_ID","Duplicate model ids make topology ambiguous.",node_id=node))
    for edge in mesh.edges:
        for side,node_id in (("from",edge.from_id),("to",edge.to_id)):
            if node_id not in ids:findings.append(_finding(mesh,GuardStatus.GAP,"MESH_EDGE_NODE_MISSING","An edge names a missing node.",edge_id=edge.edge_id,evidence={"side":side,"model_id":node_id}))
        if edge.relation=="continues" and edge.from_id in contracts and edge.to_id in contracts:
            findings.extend(_continues_findings(mesh,edge,contracts[edge.from_id],contracts[edge.to_id]))
    for cycle in _cycles(mesh.edges):findings.append(_finding(mesh,GuardStatus.FAIL,"MESH_DEPENDENCY_CYCLE","Tree or continuation edges contain a cycle.",evidence={"cycle":cycle}))
    _ids,_parents,_children,_continuations,roots,multiple,valid=_tree_shape(mesh)
    if not valid:findings.append(_finding(mesh,GuardStatus.GAP,"MESH_NOT_ONE_TREE","A model tree needs one root and at most one parent per node, connected through parent_child edges.",evidence={"roots":roots,"multiple_parents":multiple}))
    variant_results=[]
    for variant in mesh.variants:
        changed=apply_variant(mesh.to_dict(),variant)
        result=run_model_mesh(changed)
        codes={str(g.get("code")) for g in result.to_dict()["gaps"]}
        expected=variant.get("expect","FAIL");code=variant.get("code")
        caught=result.status.value==expected and (not code or code in codes)
        variant_results.append({"id":variant["id"],"status":result.status.value,"expected":expected,"code":code,"caught":caught})
        if not caught:findings.append(_finding(mesh,GuardStatus.GAP,"VARIANT_NOT_CAUGHT","A tree variant did not fail with its declared status and code.",evidence={"variant":variant["id"],"expected":expected,"code":code,"actual":result.status.value,"codes":sorted(codes)}))
    status=aggregate_statuses([*[r.status for r in reports.values()],*[f.status for f in findings]])
    lines=_tree_structure(mesh,reports,findings)
    return MeshReport(status,reports,findings,{"nodes":len(mesh.nodes),"edges":len(mesh.edges),"roots":len(roots),"variants":len(variant_results)},
                      sorted({v for n in mesh.nodes if n.contract for v in n.contract.world_model.scope_limits}),
                      {n.model_id:n.source for n in mesh.nodes if n.source},lines,variant_results)


def _continues_findings(mesh: ModelMeshContract, edge: ModelEdge, from_contract: GuardContract, to_contract: GuardContract) -> list[MeshFinding]:
    """Compare the actual source end state to the next node's declared start."""
    findings = []
    def add(status, code, message, **evidence):
        findings.append(_finding(mesh, status, code, message, edge_id=edge.edge_id, evidence=evidence))
    from_events = from_contract.inputs.get("events", [])
    to_events = to_contract.inputs.get("events", [])
    missing_times = [{"side": side, "index": index}
                     for side, events in (("from", from_events), ("to", to_events))
                     for index, event in enumerate(events) if not isinstance(event, Mapping) or "at" not in event]
    named_times = [(f"edge {edge.edge_id} {side} event {event.get('event_id')}", event["at"])
                   for side, events in (("from", from_events), ("to", to_events))
                   for event in events if isinstance(event, Mapping) and "at" in event]
    validate_times(named_times)
    from_missing_time = any(row["side"] == "from" for row in missing_times)
    if missing_times:
        add(GuardStatus.GAP, "MESH_HANDOFF_TIME_MISSING", "Event times are needed to compare the handoff.", events=missing_times)
    else:
        if from_events and to_events:
            end = max((event["at"] for event in from_events), key=time_key)
            start = min((event["at"] for event in to_events), key=time_key)
            if time_key(start) < time_key(end):
                add(GuardStatus.FAIL, "MESH_HANDOFF_TIME_BACKWARDS", "The next node begins before the previous node ends.", from_end=end, to_start=start)
    if not from_missing_time and all(isinstance(event, Mapping) for event in to_events):
        from_initial = from_contract.inputs.get("event_model", {}).get("initial_states", [])
        to_initial = to_contract.inputs.get("event_model", {}).get("initial_states", [])
        holding = frozenset(_fluent_values(from_initial))
        for _event, _before, after in event_replay(from_events, from_initial):
            holding = after
        to_start = set(_fluent_values(to_initial))
        mentioned = set(to_start)
        for event in to_events:
            for key in ("requires", "initiates", "terminates", "releases"):
                mentioned.update(_fluent_values(event.get(key)))
        for fluent in sorted(mentioned):
            if (fluent in holding) != (fluent in to_start):
                add(GuardStatus.FAIL, "MESH_HANDOFF_STATE_MISMATCH", "A next-node fluent differs from the previous end state.",
                    fluent=fluent, from_end=fluent in holding, to_initial=fluent in to_start)
    from_resources = from_contract.inputs.get("resources", {})
    to_resources = to_contract.inputs.get("resources", {})
    shared = set(from_resources.get("unique", [])) & set(to_resources.get("unique", []))
    replay_resources = from_resources
    if shared and from_missing_time:
        timed_events = {event.get("event_id") for event in from_events
                        if isinstance(event, Mapping) and "at" in event and not event.get("scenario_id")}
        transfers = from_resources.get("transitions", [])
        def colors(transfer):
            return {str(arc.get("color")) for key in ("consumes", "produces")
                    for arc in transfer.get(key, []) if isinstance(arc, Mapping)}
        uncertain = set().union(*(colors(row) for row in transfers
                                  if isinstance(row, Mapping) and "event" in row and row["event"] not in timed_events))
        # A transfer coupling two colors cannot give either a known end state if one is uncertain.
        while True:
            coupled = set().union(*(colors(row) for row in transfers if isinstance(row, Mapping) and colors(row) & uncertain))
            if coupled <= uncertain:
                break
            uncertain.update(coupled)
        shared -= uncertain
        replay_resources = {**from_resources, "transitions": [row for row in transfers
            if isinstance(row, Mapping) and not colors(row) & uncertain
            and ("event" not in row or row["event"] in timed_events)]}
    if shared:
        final, from_error = token_replay(replay_resources, validate=not from_missing_time,
            events=[event for event in from_events if isinstance(event, Mapping)])
        initial, to_error = token_replay({**to_resources, "transitions": []})
        if from_error is not None or to_error is not None:
            add(GuardStatus.FAIL, "MESH_HANDOFF_STATE_MISMATCH", "A unique token state cannot be replayed across this edge.",
                from_error=from_error, to_error=to_error)
        else:
            for color in sorted(shared):
                left = {place: qty for (place, token), qty in final.items() if token == color and qty}
                right = {place: qty for (place, token), qty in initial.items() if token == color and qty}
                if left != right:
                    add(GuardStatus.FAIL, "MESH_HANDOFF_STATE_MISMATCH", "A unique token starts at a different location.",
                        color=color, from_end=left, to_initial=right)
    if edge.variables:
        from_values = causal_scenario_values(from_contract.inputs.get("causal_model", {}), event_time_values([event for event in from_events if isinstance(event, Mapping)]))
        to_values = causal_scenario_values(to_contract.inputs.get("causal_model", {}), event_time_values([event for event in to_events if isinstance(event, Mapping)]))
        for scenario in sorted(to_values) or ["<none>"]:
            left = next(iter(from_values.values())) if len(from_values) == 1 else from_values.get(scenario, {})
            right = to_values.get(scenario, {})
            for name in edge.variables:
                if name not in left or name not in right:
                    add(GuardStatus.GAP, "MESH_HANDOFF_VALUE_MISSING", "A requested variable cannot be compared.",
                        variable=name, scenario=scenario, from_value=left.get(name), to_value=right.get(name))
                elif not isfinite(left[name]) or not isfinite(right[name]):
                    raise ValueError(f"edge {edge.edge_id}: variable {name} in {scenario} must be finite")
                elif abs(left[name] - right[name]) > 1e-9:
                    add(GuardStatus.FAIL, "MESH_HANDOFF_VALUE_MISMATCH", "A carried variable differs between nodes.",
                        variable=name, scenario=scenario, from_value=left[name], to_value=right[name])
    return findings


def _cycles(edges: list[ModelEdge]) -> list[list[str]]:
    graph: dict[str, list[str]] = {}
    for edge in edges:
        if edge.relation in CYCLE_RELATIONS:
            graph.setdefault(edge.from_id, []).append(edge.to_id)

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
        finding_id=f"{mesh.mesh_id}:{code}:{suffix}",
        status=status,
        code=code,
        message=message,
        node_id=node_id,
        edge_id=edge_id,
        evidence=evidence or {},
    )

def compare_mesh_with_observed_copy(world, observed):
    """Compare a tree once and copy only selected event times."""
    from .compare import _compare_world, _number
    if not isinstance(world, ModelMeshContract):
        world = ModelMeshContract.from_dict(world)
    if not isinstance(observed, Mapping) or not isinstance(observed.get("nodes"), Mapping):
        raise ValueError("mesh observations require a nodes mapping")
    if set(observed) - {"nodes", "time_tolerance", "tolerance", "source"}:
        raise ValueError("mesh observations have unknown fields")
    defaults = {k:observed[k] for k in ("time_tolerance", "tolerance", "source") if k in observed}
    for key in ("time_tolerance", "tolerance"):
        if key in defaults:_number(defaults[key], key, nonnegative=True)
    by_id = {node.model_id:node for node in world.nodes}
    if len(by_id)!=len(world.nodes):
        raise ValueError("mesh observations require unique model ids")
    copied = deepcopy(world.to_dict()); matches=[];mismatches=[]
    for node_id, values in observed["nodes"].items():
        if node_id not in by_id or by_id[node_id].contract is None:
            raise ValueError(f"observed node {node_id!r} is unknown or lacks a contract")
        if not isinstance(values, Mapping):
            raise ValueError(f"observed node {node_id!r} must be a mapping")
        result, contract, selected = _compare_world(by_id[node_id].contract, {**defaults, **values})
        matches.extend({"node":node_id, **row} for row in result["matches"])
        mismatches.extend({"node":node_id, **row} for row in result["mismatches"])
        destination = next(row["contract"] for row in copied["nodes"] if row["model_id"]==node_id)
        for event_id, index in selected.items():
            destination["inputs"]["events"][index]["at"] = deepcopy(values["events"][event_id])
    return {"mesh_id":world.mesh_id,"status":"FAIL" if mismatches else "PASS","matches":matches,"mismatches":mismatches,
            **({"source":observed["source"]} if "source" in observed else {})}, copied


def compare_mesh(world, observed):
    return compare_mesh_with_observed_copy(world, observed)[0]
