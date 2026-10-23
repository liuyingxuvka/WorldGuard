from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .io import dump_json, load_mapping


FULL_OUTPUT_HINT = "summary only; add --json for the full report"


def _without_traces(value):
    if isinstance(value, dict):
        return {key: _without_traces(child) for key, child in value.items() if key != "trace"}
    if isinstance(value, list):
        return [_without_traces(child) for child in value]
    return value


def _unit_summary(report):
    return _without_traces({key: report[key] for key in ("contract_id", "status", "checked", "gaps", "scope_limits")})


def _mesh_summary(report):
    return _without_traces({key: report[key] for key in ("status", "checked", "gaps", "scope_limits")})


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
    timeline_parser = subparsers.add_parser("timeline")
    timeline_parser.add_argument("--contract", required=True)
    timeline_parser.add_argument("--scenario")
    comparison = subparsers.add_parser("compare", help="Compare a world with supplied observations.")
    comparison.add_argument("--contract", required=True)
    comparison.add_argument("--observed", required=True)
    args = parser.parse_args(argv)
    if args.command == "compare":
        from .compare import compare_world
        try:
            result = compare_world(load_mapping(args.contract), load_mapping(args.observed))
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("compare", f"{args.contract} / {args.observed}", exc)
        print(dump_json(result))
        return 0 if result["status"] == "PASS" else 1
    if args.command == "timeline":
        from .contracts import GuardContract
        from .kernel import run_worldguard
        from .timeline import timeline
        try:
            contract = GuardContract.from_dict(load_mapping(args.contract))
            report = run_worldguard(contract)
            view = timeline(contract, scenario=args.scenario, problems=report.gaps)
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("timeline", args.contract, exc)
        print(dump_json(view))
        return 0
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
            mesh_report = run_model_mesh(ModelMeshContract.from_dict(load_mapping(args.mesh), base_dir=Path(args.mesh).resolve().parent))
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("mesh-check", args.mesh, exc)
        _emit(mesh_report.to_dict(), _mesh_summary, args.json)
        return 0 if mesh_report.status.value == "PASS" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
