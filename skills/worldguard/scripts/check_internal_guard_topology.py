#!/usr/bin/env python3
"""Verify one WorldGuard entrypoint and seven complete internal Guard routes."""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from pathlib import Path
from typing import Any


EXPECTED_GUARDS = (
    "EventGuard",
    "AgentGuard",
    "SpaceGuard",
    "ResourceGuard",
    "CausalGuard",
    "ConflictGuard",
    "NormGuard",
)
EXPECTED_TASK_SHAPES = (
    "unit_contract",
    "model_mesh",
    "world_blueprint",
    "task_local_revision",
    "template_pack",
)
EXPECTED_VERSION = "0.7.11"
PREDICTIVE_GUARDS = {"EventGuard", "CausalGuard"}
TERMINAL_STATUSES = ("PASS", "FAIL", "GAP", "BOUNDARY_EXCEEDED")
REQUIRED_ROW_FIELDS = {
    "route_id",
    "guard_id",
    "runner",
    "expectation_owner",
    "prediction_mode",
    "prediction_boundary",
    "response_owner",
    "purpose_validator",
    "semantic_executor_id",
    "semantic_registry",
    "applicability_semantics",
    "forbidden_semantics",
    "possible_consumed_input_fields",
    "first_native_action",
    "reference_path",
    "conditional_references",
    "deepening_trigger",
    "claim_boundary",
}
REQUIRED_TASK_SHAPE_FIELDS = {
    "shape_id",
    "applicability_facts",
    "forbidden_facts",
    "required_input_fields",
    "first_native_action",
    "reference_path",
    "conditional_references",
    "claim_boundary",
}
def _callable_id(value: Any) -> str:
    return f"{value.__module__}:{value.__name__}"


def _semantic_implementation_input_surface(
    semantic_source: Path,
    entrypoint_name: str,
) -> list[str]:
    """Derive possible input reads from executor code, independently of metadata."""

    module = ast.parse(semantic_source.read_text(encoding="utf-8"))
    functions = {
        node.name: node
        for node in module.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    direct_roots: set[str] = set()
    expanded_roots: set[str] = set()
    leaf_paths: set[str] = set()
    visited: set[tuple[str, tuple[tuple[str, str], ...]]] = set()

    def literal_get_keys(
        call: ast.AST,
        symbolic_keys: dict[str, tuple[str, ...]],
    ) -> tuple[str, ...]:
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
            return ()
        if call.func.attr != "get" or not call.args:
            return ()
        key = call.args[0]
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            return (key.value,)
        if isinstance(key, ast.Name):
            return symbolic_keys.get(key.id, ())
        return ()

    def direct_input_paths(
        call: ast.AST,
        symbolic_keys: dict[str, tuple[str, ...]],
    ) -> tuple[str, ...]:
        keys = literal_get_keys(call, symbolic_keys)
        if not keys or not isinstance(call, ast.Call):
            return ()
        owner = call.func.value
        if not isinstance(owner, ast.Attribute) or owner.attr != "inputs":
            return ()
        return tuple(
            "mesh.semantic_coverage"
            if key == "_semantic_coverage"
            else f"inputs.{key}"
            for key in keys
        )

    def alias_get_paths(
        call: ast.AST,
        aliases: dict[str, str],
        symbolic_keys: dict[str, tuple[str, ...]],
    ) -> tuple[str, ...]:
        keys = literal_get_keys(call, symbolic_keys)
        if not keys or not isinstance(call, ast.Call):
            return ()
        owner = call.func.value
        if not isinstance(owner, ast.Name) or owner.id not in aliases:
            return ()
        return tuple(f"{aliases[owner.id]}.{key}" for key in keys)

    def visit(function_name: str, parameter_roots: dict[str, str]) -> None:
        visit_key = (function_name, tuple(sorted(parameter_roots.items())))
        if visit_key in visited:
            return
        visited.add(visit_key)
        function = functions.get(function_name)
        if function is None:
            return

        aliases = dict(parameter_roots)
        symbolic_keys: dict[str, tuple[str, ...]] = {}
        for node in ast.walk(function):
            if not isinstance(node, ast.comprehension) or not isinstance(
                node.target, ast.Name
            ):
                continue
            if not isinstance(node.iter, (ast.List, ast.Tuple, ast.Set)):
                continue
            values = tuple(
                str(item.value)
                for item in node.iter.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            )
            if len(values) == len(node.iter.elts):
                symbolic_keys[node.target.id] = values
        for node in ast.walk(function):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            paths = direct_input_paths(value, symbolic_keys) or alias_get_paths(
                value, aliases, symbolic_keys
            )
            if len(paths) != 1:
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    aliases[target.id] = paths[0]

        for node in ast.walk(function):
            if not isinstance(node, ast.Call):
                continue
            direct_roots.update(direct_input_paths(node, symbolic_keys))
            for leaf in alias_get_paths(node, aliases, symbolic_keys):
                root_name = leaf.rsplit(".", 1)[0]
                expanded_roots.add(root_name)
                leaf_paths.add(leaf)

        for node in ast.walk(function):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            callee = functions.get(node.func.id)
            if callee is None:
                continue
            callee_roots: dict[str, str] = {}
            parameter_names = [argument.arg for argument in callee.args.args]
            for parameter_name, argument in zip(parameter_names, node.args):
                if isinstance(argument, ast.Name) and argument.id in aliases:
                    callee_roots[parameter_name] = aliases[argument.id]
                    continue
                paths = direct_input_paths(
                    argument, symbolic_keys
                ) or alias_get_paths(argument, aliases, symbolic_keys)
                if len(paths) == 1:
                    callee_roots[parameter_name] = paths[0]
            visit(node.func.id, callee_roots)

    visit(entrypoint_name, {})
    return sorted((direct_roots - expanded_roots) | leaf_paths)


def _declared_path_covers(observed: str, declared: str) -> bool:
    return observed == declared or observed.startswith(f"{declared}.")


def check(
    repository_root: Path,
    *,
    topology_path: Path | None = None,
    flowguard_alignment_path: Path | None = None,
) -> dict[str, object]:
    repository_root = repository_root.resolve()
    skill_root = repository_root / "skills" / "worldguard"
    topology_path = (
        topology_path.resolve()
        if topology_path is not None
        else skill_root / "references" / "internal-guard-routes.json"
    )
    flowguard_alignment_path = (
        flowguard_alignment_path.resolve()
        if flowguard_alignment_path is not None
        else repository_root / ".flowguard" / "run_claim_derived_coverage_checks.py"
    )
    findings: list[dict[str, object]] = []

    payload = json.loads(topology_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "worldguard.internal_guard_routes.v3":
        findings.append(
            {
                "code": "topology_schema_mismatch",
                "observed": payload.get("schema_version"),
            }
        )
    selection = payload.get("selection_authority", {})
    expected_selection = {
        "task_shape_rule": "one_required_current_task_shape_field",
        "guard_coverage_rule": "complete_set_from_structured_claim_semantics",
        "guard_derivation_owner": "worldguard.contracts:derive_guard_requirements",
        "caller_target_guards_authoritative": False,
        "keyword_scoring_authoritative": False,
        "failure_retry_to_another_guard": False,
    }
    if selection != expected_selection:
        findings.append(
            {
                "code": "selection_authority_mismatch",
                "expected": expected_selection,
                "observed": selection,
            }
        )
    shapes = payload.get("task_shapes", [])
    if not isinstance(shapes, list):
        shapes = []
        findings.append({"code": "task_shapes_not_list"})
    declared_shapes = {
        str(row.get("shape_id")): row
        for row in shapes
        if isinstance(row, dict) and row.get("shape_id")
    }
    if len(declared_shapes) != len(shapes):
        findings.append({"code": "duplicate_or_unidentified_task_shape"})
    if tuple(declared_shapes) != EXPECTED_TASK_SHAPES:
        findings.append(
            {
                "code": "task_shape_inventory_mismatch",
                "expected": list(EXPECTED_TASK_SHAPES),
                "observed": list(declared_shapes),
            }
        )
    for shape_id, row in declared_shapes.items():
        missing_fields = sorted(REQUIRED_TASK_SHAPE_FIELDS - row.keys())
        if missing_fields:
            findings.append(
                {
                    "code": "task_shape_fields_missing",
                    "shape_id": shape_id,
                    "fields": missing_fields,
                }
            )
            continue
        for field in ("applicability_facts", "required_input_fields"):
            value = row.get(field)
            if not isinstance(value, list) or not value:
                findings.append(
                    {
                        "code": "task_shape_list_field_invalid",
                        "shape_id": shape_id,
                        "field": field,
                    }
                )
        for field in ("first_native_action", "reference_path", "claim_boundary"):
            if not str(row.get(field, "")).strip():
                findings.append(
                    {
                        "code": "task_shape_text_field_missing",
                        "shape_id": shape_id,
                        "field": field,
                    }
                )
        reference = skill_root / str(row.get("reference_path", ""))
        if not reference.is_file():
            findings.append(
                {
                    "code": "task_shape_reference_missing",
                    "shape_id": shape_id,
                    "path": row.get("reference_path"),
                }
            )
        for conditional in row.get("conditional_references", []):
            if not isinstance(conditional, dict) or not str(conditional.get("trigger", "")).strip():
                findings.append(
                    {
                        "code": "task_shape_conditional_reference_invalid",
                        "shape_id": shape_id,
                    }
                )
                continue
            conditional_path = skill_root / str(conditional.get("path", ""))
            if not conditional_path.is_file():
                findings.append(
                    {
                        "code": "task_shape_conditional_reference_missing",
                        "shape_id": shape_id,
                        "path": conditional.get("path"),
                    }
                )
    rows = payload.get("routes", [])
    if not isinstance(rows, list):
        rows = []
        findings.append({"code": "topology_routes_not_list"})
    declared = {
        str(row.get("guard_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("guard_id")
    }
    if len(declared) != len(rows):
        findings.append({"code": "duplicate_or_unidentified_guard_route"})
    if tuple(declared) != EXPECTED_GUARDS:
        findings.append(
            {
                "code": "declared_guard_inventory_mismatch",
                "expected": list(EXPECTED_GUARDS),
                "observed": list(declared),
            }
        )

    public = payload.get("public_entrypoint", {})
    if public != {"skill_id": "worldguard", "console_id": "worldguard"}:
        findings.append({"code": "public_entrypoint_mismatch", "observed": public})
    if tuple(payload.get("terminal_statuses", ())) != TERMINAL_STATUSES:
        findings.append({"code": "declared_terminal_status_mismatch"})

    task_fact_schema = payload.get("task_fact_schema", {})
    if task_fact_schema.get("required_fields") != [
        "request_source_spans",
        "task_shape",
        "claim.requested_semantics_or_atoms",
    ]:
        findings.append(
            {
                "code": "task_fact_schema_mismatch",
                "observed": task_fact_schema.get("required_fields"),
            }
        )

    prompt_budget = payload.get("prompt_budget", {})
    entry_max = prompt_budget.get("entry_shell_max_bytes")
    route_max = prompt_budget.get("single_route_capsule_max_bytes")
    blueprint_max = prompt_budget.get("single_blueprint_reference_max_bytes")
    selected_max = prompt_budget.get("selected_operation_bundle_max_bytes")
    headroom = prompt_budget.get("minimum_reasoning_headroom_bytes")
    if not isinstance(entry_max, int) or entry_max <= 0:
        findings.append({"code": "entry_prompt_budget_invalid"})
    else:
        skill_length = len((skill_root / "SKILL.md").read_bytes())
        if skill_length > entry_max:
            findings.append(
                {
                    "code": "entry_prompt_budget_exceeded",
                    "observed": skill_length,
                    "maximum": entry_max,
                }
            )
    if not isinstance(route_max, int) or route_max <= 0:
        findings.append({"code": "route_capsule_budget_invalid"})
    else:
        for row in payload.get("routes", []):
            if not isinstance(row, dict):
                continue
            capsule_bytes = len(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            if capsule_bytes > route_max:
                findings.append(
                    {
                        "code": "route_capsule_budget_exceeded",
                        "guard_id": row.get("guard_id"),
                        "observed": capsule_bytes,
                        "maximum": route_max,
                    }
                )
    blueprint_path = skill_root / "references" / "world-blueprint.md"
    if not isinstance(blueprint_max, int) or blueprint_max <= 0:
        findings.append({"code": "blueprint_reference_budget_invalid"})
    elif blueprint_path.is_file() and len(blueprint_path.read_bytes()) > blueprint_max:
        findings.append(
            {
                "code": "blueprint_reference_budget_exceeded",
                "observed": len(blueprint_path.read_bytes()),
                "maximum": blueprint_max,
            }
        )
    if not isinstance(selected_max, int) or selected_max <= 0:
        findings.append({"code": "selected_operation_bundle_budget_invalid"})
    if not isinstance(headroom, int) or headroom < 12000:
        findings.append(
            {
                "code": "reasoning_headroom_too_small",
                "observed": headroom,
                "minimum": 12000,
            }
        )

    pyproject = tomllib.loads(
        (repository_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    project_version = str(pyproject.get("project", {}).get("version", ""))
    if project_version != EXPECTED_VERSION:
        findings.append(
            {
                "code": "project_version_mismatch",
                "expected": EXPECTED_VERSION,
                "observed": project_version,
            }
        )
    version_path = repository_root / "VERSION"
    source_version = (
        version_path.read_text(encoding="utf-8").strip()
        if version_path.is_file()
        else ""
    )
    if source_version != EXPECTED_VERSION:
        findings.append(
            {
                "code": "source_version_file_mismatch",
                "expected": EXPECTED_VERSION,
                "observed": source_version,
            }
        )
    readme = (repository_root / "README.md").read_text(encoding="utf-8")
    for marker in (
        f"**Source version:** `v{EXPECTED_VERSION}`",
        f"**源码版本：** `v{EXPECTED_VERSION}`",
    ):
        if marker not in readme:
            findings.append(
                {
                    "code": "readme_source_version_mismatch",
                    "expected": marker,
                }
            )
    changelog = (repository_root / "CHANGELOG.md").read_text(encoding="utf-8")
    if f"## v{EXPECTED_VERSION} " not in changelog:
        findings.append(
            {
                "code": "changelog_source_version_missing",
                "expected": EXPECTED_VERSION,
            }
        )
    scripts = pyproject.get("project", {}).get("scripts", {})
    if scripts != {"worldguard": "worldguard.cli:main"}:
        findings.append(
            {"code": "project_console_inventory_mismatch", "observed": scripts}
        )
    installed_skill_ids = sorted(
        path.parent.name
        for path in (repository_root / "skills").glob("*/SKILL.md")
    )
    if installed_skill_ids != ["worldguard"]:
        findings.append(
            {
                "code": "consumer_skill_inventory_mismatch",
                "observed": installed_skill_ids,
            }
        )

    flowguard_alignment = flowguard_alignment_path.read_text(encoding="utf-8")
    retired_runtime_path = "worldguard/skillguard_depth.py"
    current_runtime_path = "worldguard/execution_depth.py"
    if retired_runtime_path in flowguard_alignment:
        findings.append(
            {
                "code": "retired_runtime_authority_path_present",
                "path": retired_runtime_path,
            }
        )
    if current_runtime_path not in flowguard_alignment:
        findings.append(
            {
                "code": "current_runtime_authority_alignment_incomplete",
                "path": current_runtime_path,
            }
        )

    added = False
    root_text = str(repository_root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
        added = True
    semantic_input_surfaces: dict[str, dict[str, list[str]]] = {}
    try:
        import worldguard as worldguard_package
        from worldguard.contracts import (
            SEMANTIC_GUARD_ROUTES,
            derive_guard_requirements,
        )
        from worldguard.guard_model_contract import GUARD_MODEL_PURPOSES
        from worldguard.guards import GUARD_RUNNERS
        from worldguard.semantic import EXECUTOR_REGISTRY
        from worldguard.status import GuardStatus

        runtime_guards = tuple(GUARD_RUNNERS)
        semantic_guards = tuple(EXECUTOR_REGISTRY)
        purpose_guards = tuple(item.guard for item in GUARD_MODEL_PURPOSES)
        status_values = tuple(item.value for item in GuardStatus)
        if worldguard_package.__version__ != EXPECTED_VERSION:
            findings.append(
                {
                    "code": "runtime_version_mismatch",
                    "expected": EXPECTED_VERSION,
                    "observed": worldguard_package.__version__,
                }
            )
        if _callable_id(derive_guard_requirements) != selection.get(
            "guard_derivation_owner"
        ):
            findings.append(
                {
                    "code": "guard_derivation_owner_mismatch",
                    "expected": _callable_id(derive_guard_requirements),
                    "observed": selection.get("guard_derivation_owner"),
                }
            )
        for inventory_name, observed in (
            ("runner", runtime_guards),
            ("semantic", semantic_guards),
            ("purpose", purpose_guards),
        ):
            if observed != EXPECTED_GUARDS:
                findings.append(
                    {
                        "code": f"{inventory_name}_guard_inventory_mismatch",
                        "expected": list(EXPECTED_GUARDS),
                        "observed": list(observed),
                    }
                )
        if status_values != TERMINAL_STATUSES:
            findings.append(
                {
                    "code": "runtime_terminal_status_mismatch",
                    "observed": list(status_values),
                }
            )

        for guard_id in EXPECTED_GUARDS:
            row = declared.get(guard_id)
            if not isinstance(row, dict):
                continue
            if "required_input_fields" in row:
                findings.append(
                    {
                        "code": "retired_internal_route_input_field_present",
                        "guard_id": guard_id,
                        "field": "required_input_fields",
                    }
                )
            missing_fields = sorted(REQUIRED_ROW_FIELDS - row.keys())
            if missing_fields:
                findings.append(
                    {
                        "code": "internal_route_fields_missing",
                        "guard_id": guard_id,
                        "fields": missing_fields,
                    }
                )
                continue
            expected_mode = (
                "claim_derived_predictive_participant"
                if guard_id in PREDICTIVE_GUARDS
                else "bounded_expectation_only"
            )
            expected_values = {
                "route_id": (
                    f"internal:worldguard:{guard_id.removesuffix('Guard').lower()}"
                ),
                "runner": _callable_id(GUARD_RUNNERS[guard_id]),
                "expectation_owner": (
                    "worldguard.contracts:GuardContract.for_guard"
                ),
                "prediction_mode": expected_mode,
                "response_owner": "worldguard.reports:GuardResult",
                "purpose_validator": (
                    "worldguard.guard_model_contract:"
                    "verify_guard_candidate_purpose_contract"
                ),
                "semantic_executor_id": (
                    EXECUTOR_REGISTRY[guard_id].binding.executor_id
                ),
                "semantic_registry": "worldguard.semantic:EXECUTOR_REGISTRY",
                "applicability_semantics": [
                    semantic
                    for semantic, guards in SEMANTIC_GUARD_ROUTES.items()
                    if guard_id in guards
                ],
                "possible_consumed_input_fields": list(
                    EXECUTOR_REGISTRY[
                        guard_id
                    ].binding.possible_consumed_input_fields
                ),
            }
            for field, expected in expected_values.items():
                if row.get(field) != expected:
                    findings.append(
                        {
                            "code": "internal_route_binding_mismatch",
                            "guard_id": guard_id,
                            "field": field,
                            "expected": expected,
                            "observed": row.get(field),
                        }
                    )
            if not str(row.get("prediction_boundary", "")).strip():
                findings.append(
                    {"code": "prediction_boundary_missing", "guard_id": guard_id}
                )
            for field in (
                "forbidden_semantics",
                "first_native_action",
                "reference_path",
                "deepening_trigger",
                "claim_boundary",
            ):
                value = row.get(field)
                if field == "forbidden_semantics":
                    valid = isinstance(value, list) and bool(value)
                else:
                    valid = bool(str(value or "").strip())
                if not valid:
                    findings.append(
                        {
                            "code": "internal_route_admission_field_invalid",
                            "guard_id": guard_id,
                            "field": field,
                        }
                    )
            declared_possible_inputs = list(
                EXECUTOR_REGISTRY[
                    guard_id
                ].binding.possible_consumed_input_fields
            )
            implementation_inputs = _semantic_implementation_input_surface(
                repository_root / "worldguard" / "semantic.py",
                EXECUTOR_REGISTRY[guard_id].execute.__name__,
            )
            omitted_inputs = sorted(
                observed
                for observed in implementation_inputs
                if not any(
                    _declared_path_covers(observed, declared_input)
                    for declared_input in declared_possible_inputs
                )
            )
            semantic_input_surfaces[guard_id] = {
                "implementation": implementation_inputs,
                "binding": declared_possible_inputs,
                "route": list(row.get("possible_consumed_input_fields", [])),
            }
            if omitted_inputs:
                findings.append(
                    {
                        "code": "semantic_input_surface_omitted",
                        "guard_id": guard_id,
                        "fields": omitted_inputs,
                        "implementation_fields": implementation_inputs,
                        "binding_fields": declared_possible_inputs,
                    }
                )
            route_possible_inputs = row.get("possible_consumed_input_fields")
            if (
                not isinstance(route_possible_inputs, list)
                or not route_possible_inputs
                or len(route_possible_inputs) != len(set(route_possible_inputs))
            ):
                findings.append(
                    {
                        "code": "internal_route_possible_input_surface_invalid",
                        "guard_id": guard_id,
                    }
                )
            reference = skill_root / str(row.get("reference_path", ""))
            if not reference.is_file():
                findings.append(
                    {
                        "code": "internal_route_reference_missing",
                        "guard_id": guard_id,
                        "path": row.get("reference_path"),
                    }
                )
            conditionals = row.get("conditional_references", [])
            if not isinstance(conditionals, list):
                findings.append(
                    {
                        "code": "internal_route_conditional_references_invalid",
                        "guard_id": guard_id,
                    }
                )
            else:
                for conditional in conditionals:
                    if not isinstance(conditional, dict) or not str(conditional.get("trigger", "")).strip():
                        findings.append(
                            {
                                "code": "internal_route_conditional_reference_invalid",
                                "guard_id": guard_id,
                            }
                        )
                        continue
                    conditional_path = skill_root / str(conditional.get("path", ""))
                    if not conditional_path.is_file():
                        findings.append(
                            {
                                "code": "internal_route_conditional_reference_missing",
                                "guard_id": guard_id,
                                "path": conditional.get("path"),
                            }
                        )
    finally:
        if added:
            sys.path.remove(root_text)

    return {
        "schema_version": "worldguard.internal_guard_topology_check.v5",
        "status": "pass" if not findings else "fail",
        "ok": not findings,
        "source_version": source_version,
        "public_skill_ids": installed_skill_ids,
        "project_console_ids": sorted(scripts),
        "internal_guard_ids": list(EXPECTED_GUARDS),
        "task_shape_ids": list(EXPECTED_TASK_SHAPES),
        "semantic_input_surfaces": semantic_input_surfaces,
        "findings": findings,
        "claim_boundary": (
            "This target-native check proves the current source declares one "
            "WorldGuard entrypoint and seven exact internal Guard routes. Portable "
            "runtime projection parity belongs to the canonical projection owner "
            "and is not evaluated here. It does not prove a task-specific Guard "
            "run, factual truth, installation, release, or predictive closure."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--topology")
    parser.add_argument("--flowguard-alignment")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = check(
        Path(args.repository_root),
        topology_path=Path(args.topology) if args.topology else None,
        flowguard_alignment_path=(
            Path(args.flowguard_alignment) if args.flowguard_alignment else None
        ),
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status={report['status']} findings={len(report['findings'])}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
