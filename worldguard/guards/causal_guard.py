from __future__ import annotations

from worldguard.contracts import GUARD_BOUNDARY_SEMANTICS, GuardContract
from worldguard.clock import event_time_values
from worldguard.semantic import causal_constraint_findings, equation_error, causal_runs
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


def _check(contract: GuardContract):
    guard = "CausalGuard"
    requested = requested_semantic_ids(contract)
    causal_model = contract.inputs.get("causal_model", {})
    event_times = event_time_values(contract.inputs.get("events", []))
    variables = causal_model.get("variables", [])
    equations = causal_model.get("equations", {})
    graph = causal_model.get("graph", [])
    claim_scope = causal_model.get("claim_scope", "equation_model")


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
        if causal_model.get("constraints"):
            return result(contract, guard, GuardStatus.GAP, channel="gap", impact="creates_gap",
                errors=[error("CAUSAL_CONSTRAINT_UNEVALUABLE", "Graph-only claims cannot evaluate numeric constraints.")],
                missing_slots=[{"needed": "scalar equations"}])
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

    equation_errors = {name: equation_error(equations[name], set(variables) | set(causal_model.get("exogenous", [])) | set(event_times)) for name in variables}
    equation_errors = {key: value for key, value in equation_errors.items() if value}
    if equation_errors:
        return result(contract, guard, GuardStatus.GAP, channel="gap", impact="creates_gap",
            errors=[error("CAUSAL_UNEVALUABLE_EQUATION", "A structural equation is outside the supported scalar subset.")],
            missing_slots=[equation_errors])
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

    violations, unevaluable = causal_constraint_findings(causal_model, event_times)
    if unevaluable and not violations:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=unevaluable,
            errors=[error("CAUSAL_CONSTRAINT_UNEVALUABLE", "A declared constraint cannot be evaluated.")],
        )
    if violations:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="causal",
            impact="supports_fail",
            errors=[error("CAUSAL_CONSTRAINT_VIOLATED", "A declared constraint does not hold in an evaluated scenario.")],
            counterexamples=[{"kind": "model_conflict", "steps": violations}],
        )

    runs, execution_errors = causal_runs(causal_model, variables, equations, event_times)
    intervention_values = runs["interventions"]
    for row in causal_model.get("counterfactuals", []):
        if row.get("query") not in intervention_values.get(str(row.get("intervention_id")), {}):
            execution_errors.append({"counterfactual": row, "error": "query or intervention is unavailable"})
    if execution_errors:
        return result(contract, guard, GuardStatus.GAP, channel="gap", impact="creates_gap",
            errors=[error("CAUSAL_SCENARIO_UNEVALUABLE", "A declared causal run cannot be evaluated safely.")],
            missing_slots=execution_errors)
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


def run(contract: GuardContract):
    """Check the complete native CausalGuard rules once, then append its boundary."""
    checked = _check(contract)
    if requested_semantic_ids(contract) & GUARD_BOUNDARY_SEMANTICS["CausalGuard"]:
        from dataclasses import replace
        from worldguard.status import aggregate_statuses
        checked = replace(checked,
            status=aggregate_statuses([checked.status, GuardStatus.BOUNDARY_EXCEEDED]),
            errors=[*checked.errors, error('CAUSAL_BOUNDARY_TEMPORAL_STORY', 'Temporal order alone is not SCM evidence.')])
    return checked
