from __future__ import annotations

from worldguard.contracts import GuardContract
from worldguard.status import GuardStatus

from ._helpers import error, requested_semantic_ids, result


def _has_cycle(edges: list[list[str] | tuple[str, str]]) -> bool:
    graph: dict[str, list[str]] = {}
    for edge in edges:
        if len(edge) != 2:
            continue
        graph.setdefault(edge[0], []).append(edge[1])
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in graph.get(node, []):
            if visit(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def run(contract: GuardContract):
    guard = "CausalGuard"
    requested = requested_semantic_ids(contract)
    causal_model = contract.inputs.get("causal_model", {})
    variables = causal_model.get("variables", [])
    equations = causal_model.get("equations", {})
    graph = causal_model.get("graph", [])
    claim_scope = causal_model.get("claim_scope", "equation_model")

    if requested & {"temporal_story"}:
        return result(
            contract,
            guard,
            GuardStatus.BOUNDARY_EXCEEDED,
            channel="boundary",
            impact="marks_boundary",
            boundary={"owner": guard, "unsupported_claim_parts": ["temporal_story_without_scm"]},
            errors=[error("CAUSAL_BOUNDARY_TEMPORAL_STORY", "Temporal order alone is not SCM evidence.")],
        )

    if graph and _has_cycle(graph):
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="causal",
            impact="supports_fail",
            errors=[error("CAUSAL_CYCLE", "SCM graph contains a directed cycle.")],
            counterexamples=[{"kind": "model_conflict", "steps": graph}],
        )

    if claim_scope == "graph_only":
        malformed_edges = [
            edge
            for edge in graph
            if not isinstance(edge, (list, tuple)) or len(edge) != 2
        ]
        graph_ids = {
            str(value)
            for edge in graph
            if isinstance(edge, (list, tuple)) and len(edge) == 2
            for value in edge
        }
        if not variables or not graph or malformed_edges or not graph_ids.issubset(
            {str(value) for value in variables}
        ):
            return result(
                contract,
                guard,
                GuardStatus.GAP,
                channel="gap",
                impact="creates_gap",
                missing_slots=[{"needed": "complete declared variable graph"}],
                errors=[
                    error(
                        "CAUSAL_MISSING_STRUCTURAL_EQUATION",
                        "Graph-only evaluation requires declared variables and exact edges.",
                    )
                ],
            )
        return result(
            contract,
            guard,
            GuardStatus.PASS,
            channel="causal",
            impact="supports_pass",
            payload={"variables": variables, "evaluated_graph_edges": len(graph)},
            supported=True,
            consumed_inputs={"causal_model": causal_model},
        )

    missing_equations = [var for var in variables if var not in equations]
    if not variables or not equations or missing_equations:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"variable": var, "needed": "structural_equation"} for var in (missing_equations or ["variables/equations"])],
            errors=[error("CAUSAL_MISSING_STRUCTURAL_EQUATION", "Required SCM equation is missing.")],
        )

    declared_behavior = {
        name: causal_model.get(name)
        for name in (
            "scenarios",
            "holdout_scenarios",
            "interventions",
            "counterfactuals",
        )
        if causal_model.get(name)
    }
    if not declared_behavior:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[
                {
                    "needed": "scenario, holdout_scenario, intervention, or counterfactual obligation"
                }
            ],
            errors=[
                error(
                    "CAUSAL_MISSING_BEHAVIOR_OBLIGATION",
                    "An equation-model claim needs at least one declared behavior that can be executed.",
                )
            ],
        )

    return result(
        contract,
        guard,
        GuardStatus.PASS,
        channel="causal",
        impact="supports_pass",
        payload={"variables": variables, "declared_behavior_kinds": sorted(declared_behavior)},
        supported=True,
        consumed_inputs={"causal_model": causal_model},
    )
