from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .io import dump_json, load_mapping


FULL_OUTPUT_HINT = "summary only; add --json for the full report"


def _non_pass_guards(child_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "guard": row.get("guard", ""),
            "status": row.get("status", ""),
            "errors": [
                {"code": error.get("code", ""), "message": error.get("message", "")}
                for error in row.get("errors", [])
            ],
            "counterexamples": row.get("counterexamples", []),
            "missing_slots": row.get("missing_slots", []),
        }
        for row in child_results
        if row.get("status") != "PASS"
    ]


def _unit_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_id": report.get("contract_id", ""),
        "status": report["status"],
        "structural_status": report.get("structural_status", ""),
        "semantic_status": report.get("semantic_status", ""),
        "gaps": report.get("gaps", []),
        "non_pass_guards": _non_pass_guards(report.get("child_results", [])),
        "scope_limits": report.get("scope_limits", []),
    }


def _mesh_summary(report: dict[str, Any]) -> dict[str, Any]:
    nodes = report.get("node_reports", {})
    depth = report.get("depth_receipt") or {}
    return {
        "status": report["status"],
        "structural_status": report.get("structural_status", ""),
        "semantic_status": report.get("semantic_status", ""),
        "gaps": [
            *report.get("findings", []),
            *(
                {"node_id": node_id, **gap}
                for node_id, node in sorted(nodes.items())
                for gap in node.get("gaps", [])
            ),
        ],
        "predictive_claim_licensed": depth.get("predictive_claim_licensed", False),
        "predictive_gaps": depth.get("predictive_gaps", []),
        "non_pass_nodes": {
            node_id: _unit_summary(node)
            for node_id, node in sorted(nodes.items())
            if node.get("status") != "PASS"
        },
        "scope_limits": sorted(set(report.get("scope_limits", []))),
    }


def _blueprint_summary(report: dict[str, Any]) -> dict[str, Any]:
    keys = ("operation", "status", "native_domain_qualified", "deepest_continuously_proven_layer",
            "first_unresolved_layer", "changed_ids", "materialized_ids", "target_id",
            "terminal_input_ids", "terminal_binding_ids", "claim_boundary")
    summary = {key: report[key] for key in keys if key in report}
    if "qualification_layers" in report:
        summary["layers"] = {row["layer_id"]: row["status"] for row in report["qualification_layers"]}
    summary["gaps"] = [
        {
            key: gap[key]
            for key in ("code", "message", "layer_id", "depth", "node_id", "element_id", "binding_id")
            if key in gap and gap[key] not in ("", None)
        }
        for gap in report.get("gaps", [])
    ]
    summary["status"] = report.get("status", "")
    summary["semantic_status"] = report.get("semantic_status", "")
    summary["scope_limits"] = report.get("scope_limits", [])
    return summary


def _emit(full: dict[str, Any], summarize, as_json: bool) -> None:
    if as_json:
        print(dump_json(full))
    else:
        print(dump_json({**summarize(full), "output": FULL_OUTPUT_HINT}))


def _example_summary(example: dict[str, Any]) -> dict[str, Any]:
    return {
        **{key: value for key, value in example.items() if key != "reports"},
        "reports": [_unit_summary(report) for report in example.get("reports", [])],
    }


def _input_error(operation: str, input_path: str, exc: Exception) -> int:
    print(
        dump_json(
            {
                "operation": operation,
                "status": "error",
                "error": {
                    "code": "WORLDGUARD_INPUT_INVALID",
                    "message": str(exc),
                    "details": {"input_path": input_path, "error_type": type(exc).__name__},
                },
            }
        )
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worldguard")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser("check")
    check.add_argument("--contract", default="")
    check.add_argument("--example", choices=["fuel_cell"], default="")
    check.add_argument("--json", action="store_true", help="print the full report")
    mesh_check = subparsers.add_parser("mesh-check")
    mesh_check.add_argument("--mesh", required=True)
    mesh_check.add_argument("--json", action="store_true", help="print the full report")
    blueprint = subparsers.add_parser(
        "blueprint",
        help="check or query one current target-neutral WorldBlueprint",
    )
    blueprint_commands = blueprint.add_subparsers(
        dest="blueprint_command",
        required=True,
    )
    blueprint_check = blueprint_commands.add_parser("check")
    blueprint_check.add_argument("--blueprint", required=True)
    blueprint_check.add_argument("--json", action="store_true", help="print the full report")
    blueprint_impact_command = blueprint_commands.add_parser("impact")
    blueprint_impact_command.add_argument("--blueprint", required=True)
    blueprint_impact_command.add_argument("--changed-id", action="append", required=True)
    blueprint_impact_command.add_argument("--json", action="store_true", help="print the full report")
    blueprint_trace_command = blueprint_commands.add_parser("trace")
    blueprint_trace_command.add_argument("--blueprint", required=True)
    blueprint_trace_command.add_argument("--target-id", required=True)
    blueprint_trace_command.add_argument("--json", action="store_true", help="print the full report")
    task_model = subparsers.add_parser(
        "task-model",
        help="freeze, compare, and reversibly evaluate one task-local world model",
    )
    task_model_commands = task_model.add_subparsers(
        dest="task_model_command",
        required=True,
    )
    task_model_freeze = task_model_commands.add_parser(
        "freeze",
        help="freeze a prediction against the exact current task model",
    )
    task_model_freeze.add_argument("prediction")
    task_model_compare = task_model_commands.add_parser(
        "compare",
        help="compare one later real observation with a frozen prediction",
    )
    task_model_compare.add_argument("prediction")
    task_model_compare.add_argument("observation")
    task_model_revision = task_model_commands.add_parser(
        "revision",
        help="accept, reject, or roll back a separate candidate task model",
    )
    task_model_revision.add_argument("revision")
    fact_revision_preview = task_model_commands.add_parser(
        "fact-revision-preview",
        help="preview a four-valued fact revision without mutating its base",
    )
    fact_revision_preview.add_argument("base")
    fact_revision_preview.add_argument("transaction")
    fact_revision_activate = task_model_commands.add_parser(
        "fact-revision-activate",
        help="activate one current preview with regression and holdout evidence",
    )
    fact_revision_activate.add_argument("base")
    fact_revision_activate.add_argument("transaction")
    fact_revision_activate.add_argument("activation")

    args = parser.parse_args(argv)
    if args.command == "check":
        from .contracts import GuardContract
        from .kernel import run_worldguard
        from .qualification import QualificationContext
        if args.example == "fuel_cell":
            from .examples.fuel_cell import run_check as run_fuel_cell_check
            example = run_fuel_cell_check()
            _emit(example, _example_summary, args.json)
            return 0 if example["ok"] else 1
        if not args.contract:
            parser.error("check requires --contract or --example fuel_cell")
        try:
            contract = GuardContract.from_dict(load_mapping(args.contract))
            context = QualificationContext(
                node_id=contract.world_model.model_id or contract.contract_id,
                target_id=contract.world_model.model_id or contract.contract_id,
                target_revision=contract.world_model.model_version,
            )
            report = run_worldguard(contract, context=context)
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("check", args.contract, exc)
        _emit(report.to_dict(), _unit_summary, args.json)
        return 0 if report.status.value == "PASS" else 1
    if args.command == "mesh-check":
        from .mesh import ModelMeshContract, run_model_mesh
        try:
            mesh_report = run_model_mesh(ModelMeshContract.from_dict(load_mapping(args.mesh)))
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("mesh-check", args.mesh, exc)
        _emit(mesh_report.to_dict(), _mesh_summary, args.json)
        return 0 if mesh_report.status.value == "PASS" else 1
    if args.command == "blueprint":
        from .blueprint import (
            BlueprintError,
            blueprint_impact,
            blueprint_reverse_trace,
            check_world_blueprint,
            load_world_blueprint,
        )
        operation = args.blueprint_command
        try:
            current_blueprint = load_world_blueprint(args.blueprint)
            if operation == "check":
                report = check_world_blueprint(current_blueprint)
                _emit(report.to_dict(), _blueprint_summary, args.json)
                return 0 if report.status.value == "PASS" else 1
            if operation == "impact":
                report = blueprint_impact(
                    current_blueprint,
                    changed_ids=args.changed_id,
                )
                _emit(report.to_dict(), _blueprint_summary, args.json)
                return 0 if not report.gaps else 1
            if operation == "trace":
                report = blueprint_reverse_trace(
                    current_blueprint,
                    target_id=args.target_id,
                )
                _emit(report.to_dict(), _blueprint_summary, args.json)
                return 0 if report.status.value == "PASS" else 1
            raise BlueprintError(
                "WORLD_BLUEPRINT_OPERATION_UNKNOWN",
                f"Unknown blueprint operation: {operation}.",
                details={"operation": operation},
            )
        except BlueprintError as exc:
            print(
                dump_json(
                    {
                        "operation": operation,
                        "status": "error",
                        "error": {
                            "code": exc.code,
                            "message": str(exc),
                            "details": exc.details,
                        },
                    }
                )
            )
            return 2
        except (OSError, UnicodeError, ValueError) as exc:
            print(
                dump_json(
                    {
                        "operation": operation,
                        "status": "error",
                        "error": {
                            "code": "WORLD_BLUEPRINT_INPUT_INVALID",
                            "message": "Blueprint input could not be loaded or parsed.",
                            "details": {
                                "input_path": str(getattr(args, "blueprint", "")),
                                "error_type": type(exc).__name__,
                            },
                        },
                    }
                )
            )
            return 2
    if args.command == "task-model":
        from .task_local_revision import (
            CandidateWorldModelRevision,
            ObservedWorldSnapshot,
            PredictionSnapshot,
            compare_observed_world,
            evaluate_candidate_world_revision,
            freeze_prediction_snapshot,
        )
        if args.task_model_command == "fact-revision-preview":
            from .fact_revision import (
                FactRevisionTransaction,
                FactWorldSnapshot,
                preview_fact_revision,
            )
            base = FactWorldSnapshot.from_dict(load_mapping(args.base))
            transaction = FactRevisionTransaction.from_dict(
                load_mapping(args.transaction)
            )
            preview = preview_fact_revision(base, transaction)
            print(dump_json(preview.to_dict()))
            return 0 if preview.status == "ready" else 1
        if args.task_model_command == "fact-revision-activate":
            from .fact_revision import (
                FactRevisionActivationRequest,
                FactRevisionTransaction,
                FactWorldSnapshot,
                activate_fact_revision,
            )
            base = FactWorldSnapshot.from_dict(load_mapping(args.base))
            transaction = FactRevisionTransaction.from_dict(
                load_mapping(args.transaction)
            )
            activation = FactRevisionActivationRequest.from_dict(
                load_mapping(args.activation)
            )
            result = activate_fact_revision(base, transaction, activation)
            print(dump_json(result.to_dict()))
            return 0 if result.receipt.activated else 1
        if args.task_model_command == "freeze":
            path = Path(args.prediction)
            prediction = PredictionSnapshot.from_dict(load_mapping(path))
            receipt = freeze_prediction_snapshot(prediction, base_dir=path.parent)
        elif args.task_model_command == "compare":
            prediction_path = Path(args.prediction)
            frozen = load_mapping(prediction_path)
            if frozen.get("artifact_kind") == "worldguard_prediction_snapshot_receipt":
                frozen = frozen.get("prediction", {})
            prediction = PredictionSnapshot.from_dict(frozen)
            observation = ObservedWorldSnapshot.from_dict(
                load_mapping(args.observation)
            )
            receipt = compare_observed_world(
                prediction,
                observation,
                base_dir=prediction_path.parent,
            )
        else:
            path = Path(args.revision)
            revision = CandidateWorldModelRevision.from_dict(load_mapping(path))
            receipt = evaluate_candidate_world_revision(
                revision,
                base_dir=path.parent,
            )
        print(dump_json(receipt))
        return 0 if receipt["status"] == "pass" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
