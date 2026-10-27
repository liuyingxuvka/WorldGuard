"""Portable commands for one world or a tree of worlds."""

from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Any
from .io import dump_json, load_mapping, input_digests

FULL_OUTPUT_HINT = "summary only; add --json for the full report"


def _without_traces(value):
    if isinstance(value, dict):
        return {k: _without_traces(v) for k, v in value.items() if k != "trace"}
    if isinstance(value, list):
        return [_without_traces(v) for v in value]
    return value


def _unit_summary(report):
    return _without_traces({key: report[key] for key in ("contract_id", "status", "checked", "gaps", "scope_limits")})


def _mesh_summary(report):
    return _without_traces({key: report[key] for key in ("status", "checked", "gaps", "scope_limits", "tree")})


def _emit(full, summarize, as_json):
    print(dump_json(full if as_json else {**summarize(full), "output": FULL_OUTPUT_HINT}))


def _input_error(operation, input_path, exc):
    print(
        dump_json(
            {
                "operation": operation,
                "status": "error",
                "error": {"code": "WORLDGUARD_INPUT_INVALID", "message": str(exc), "details": {"input_path": input_path, "error_type": type(exc).__name__}},
            }
        )
    )
    return 2


def _example_path(name):
    filename = {"scene": "scene_locked_door.yaml", "trip": "trip_ferry.yaml", "story": "story_mesh.yaml"}[name]
    package = Path(__file__).resolve().parent
    for directory in (package.parent / "skills/worldguard/assets/examples", package.parent.parent / "assets/examples"):
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    raise ValueError(f"The {name} example is distributed with the WorldGuard portable skill; use its launcher or supply a file.")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="worldguard")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check")
    choice = check.add_mutually_exclusive_group(required=True)
    choice.add_argument("--contract")
    choice.add_argument("--example", choices=["scene", "trip"])
    check.add_argument("--json", action="store_true", help="print the full report")
    meshcheck = commands.add_parser("mesh-check")
    choice = meshcheck.add_mutually_exclusive_group(required=True)
    choice.add_argument("--mesh")
    choice.add_argument("--example", choices=["story"])
    meshcheck.add_argument("--json", action="store_true", help="print the full report")
    timeline_parser = commands.add_parser("timeline")
    choice = timeline_parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--contract")
    choice.add_argument("--mesh")
    choice.add_argument("--example", choices=["scene", "trip", "story"])
    timeline_parser.add_argument("--scenario")
    timeline_parser.add_argument("--json", action="store_true", help="print the complete timeline structure")
    comparison = commands.add_parser("compare", help="Compare supplied observations with a world or model tree.")
    choice = comparison.add_mutually_exclusive_group(required=True)
    choice.add_argument("--contract")
    choice.add_argument("--mesh")
    comparison.add_argument("--observed", required=True)
    comparison.add_argument("--write-observed", metavar="OUT", help="write an independent copy changing only compared event times")
    args = parser.parse_args(argv)
    if args.command == "compare":
        from .compare import compare_with_observed_copy, compare_world
        from .mesh import compare_mesh, compare_mesh_with_observed_copy
        from .mesh import ModelMeshContract

        try:
            path = args.mesh or args.contract
            data = load_mapping(path)
            world = ModelMeshContract.from_dict(data, base_dir=Path(path).resolve().parent) if args.mesh else data
            observed = load_mapping(args.observed)
            if args.write_observed:
                result, copied = compare_mesh_with_observed_copy(world, observed) if args.mesh else compare_with_observed_copy(world, observed)
            else:
                result = compare_mesh(world, observed) if args.mesh else compare_world(world, observed)
            if args.write_observed:
                with Path(args.write_observed).open("x", encoding="utf-8") as stream:
                    stream.write(dump_json(copied) + "\n")
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("compare", f"{path} / {args.observed}", exc)
        print(dump_json(result))
        return 0 if result["status"] == "PASS" else 1
    if args.command == "timeline":
        from .contracts import GuardContract
        from .kernel import run_worldguard
        from .mesh import ModelMeshContract, run_model_mesh
        from .timeline import timeline, render_timeline_text

        try:
            if args.example:
                if args.example == "story":
                    args.mesh = str(_example_path("story"))
                else:
                    args.contract = str(_example_path(args.example))
            if args.mesh:
                if args.scenario:
                    raise ValueError("--scenario only applies to --contract")
                mesh = ModelMeshContract.from_dict(load_mapping(args.mesh), base_dir=Path(args.mesh).resolve().parent)
                report = run_model_mesh(mesh)
                views = {}
                for row in report.tree:
                    identity = row.strip().split()[0]
                    node = next(n for n in mesh.nodes if n.model_id == identity)
                    if node.contract is not None and node.contract.inputs.get("events"):
                        views[identity] = timeline(node.contract, report=report.node_reports[identity])
                if args.json:
                    print(dump_json({"mesh_id": mesh.mesh_id, "tree": report.tree, "nodes": views}))
                else:
                    print("\n".join(report.tree))
                    for row in report.tree:
                        identity = row.strip().split()[0]
                        if identity in views:
                            padding = row[: len(row) - len(row.lstrip())]
                            print("\n".join(padding + line for line in render_timeline_text(views[identity], label=identity).splitlines()))
            else:
                contract = GuardContract.from_dict(load_mapping(args.contract))
                report = run_worldguard(contract)
                view = timeline(contract, scenario=args.scenario, report=report)
                print(dump_json(view) if args.json else render_timeline_text(view))
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("timeline", args.mesh or args.contract or args.example, exc)
        return 0
    if args.command == "check":
        from .contracts import GuardContract
        from .kernel import run_worldguard

        try:
            path = str(_example_path(args.example)) if args.example else args.contract
            report = run_worldguard(GuardContract.from_dict(load_mapping(path)))
            digests = input_digests([path], Path(path).parent)
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("check", args.example or args.contract, exc)
        payload = {**report.to_dict(), 'input_digests': digests}
        _emit(payload, lambda value: {**_unit_summary(value), 'input_digests': value['input_digests']}, args.json)
        return 0 if report.status.value == "PASS" else 1
    if args.command == "mesh-check":
        from .mesh import ModelMeshContract, run_model_mesh

        try:
            path = str(_example_path(args.example)) if args.example else args.mesh
            mesh = ModelMeshContract.from_dict(load_mapping(path), base_dir=Path(path).resolve().parent)
            report = run_model_mesh(mesh)
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("mesh-check", args.example or args.mesh, exc)
        _emit(report.to_dict(), _mesh_summary, args.json)
        return 0 if report.status.value == "PASS" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
