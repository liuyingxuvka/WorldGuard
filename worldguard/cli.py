from __future__ import annotations

import argparse
import sys
from pathlib import Path

from yaml import YAMLError

from .io import dump_json, load_mapping




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
    mesh_check = subparsers.add_parser("mesh-check")
    mesh_check.add_argument("--mesh", required=True)
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
    blueprint_impact_command = blueprint_commands.add_parser("impact")
    blueprint_impact_command.add_argument("--blueprint", required=True)
    blueprint_impact_command.add_argument("--changed-id", action="append", required=True)
    blueprint_trace_command = blueprint_commands.add_parser("trace")
    blueprint_trace_command.add_argument("--blueprint", required=True)
    blueprint_trace_command.add_argument("--target-id", required=True)
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
            print(dump_json(example))
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
        except (OSError, UnicodeError, ValueError, YAMLError) as exc:
            return _input_error("check", args.contract, exc)
        print(dump_json(report.to_dict()))
        return 0 if report.status.value == "PASS" else 1
    if args.command == "mesh-check":
        from .mesh import ModelMeshContract, run_model_mesh
        try:
            mesh_report = run_model_mesh(ModelMeshContract.from_dict(load_mapping(args.mesh)))
        except (OSError, UnicodeError, ValueError, YAMLError) as exc:
            return _input_error("mesh-check", args.mesh, exc)
        print(dump_json(mesh_report.to_dict()))
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
                print(dump_json(report.to_dict()))
                return 0 if report.status.value == "PASS" else 1
            if operation == "impact":
                report = blueprint_impact(
                    current_blueprint,
                    changed_ids=args.changed_id,
                )
                print(dump_json(report.to_dict()))
                return 0 if not report.gaps else 1
            if operation == "trace":
                report = blueprint_reverse_trace(
                    current_blueprint,
                    target_id=args.target_id,
                )
                print(dump_json(report.to_dict()))
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
        except (OSError, UnicodeError, ValueError, YAMLError) as exc:
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
                FactRevisionActivationRequest,
                FactRevisionTransaction,
                FactWorldSnapshot,
                activate_fact_revision,
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
                preview_fact_revision,
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
            prediction = PredictionSnapshot.from_dict(load_mapping(prediction_path))
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
