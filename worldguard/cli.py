"""Portable commands for one world or a tree of worlds."""

from __future__ import annotations
import argparse
import os
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
    return _without_traces({key: report[key] for key in ("status", "checked", "gaps", "scope_limits", "tree", "mesh_id", "input_digests")})


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


def _open_lines(folder):
    """The folder's still-open contradictions as text; empty when none are recorded."""
    from .open_findings import load, render

    return render(load(folder)["open"], where=str(folder))


def _show_on_stderr(text):
    if text:
        print(text, file=sys.stderr)


def _still_there(mesh):
    """Whether a recorded contradiction's chapter, edge and event are still in the tree."""
    nodes = {node.model_id: node for node in mesh.nodes}
    edges = {edge.edge_id for edge in mesh.edges}

    def exists(item):
        if item.get("edge_id") and item["edge_id"] not in edges:
            return False
        node = nodes.get(item.get("node_id")) if item.get("node_id") else None
        if item.get("node_id") and node is None:
            return False
        if item.get("event_id") and node is not None and node.contract is not None:
            return any(isinstance(event, dict) and event.get("event_id") == item["event_id"]
                       for event in node.contract.inputs.get("events", []))
        return True

    return exists


def _example_path(name):
    filename = {"scene": "scene_locked_door.yaml", "trip": "trip_ferry.yaml", "story": "story_mesh.yaml"}[name]
    package = Path(__file__).resolve().parent
    for directory in (package.parent / "skills/worldguard/assets/examples", package.parent.parent / "assets/examples"):
        candidate = directory / filename
        if candidate.is_file():
            return candidate
    raise ValueError(f"The {name} example is distributed with the WorldGuard portable skill; use its launcher or supply a file.")


BROKEN_PIPE_EXIT = 141  # the shell's code for a writer stopped by SIGPIPE


def main(argv=None):
    """Run one command. A reader that closes the output early (for example `| head`) is reported once on
    stderr with its own exit code; it is neither an input error nor a check result."""
    try:
        code = _run(argv)
        sys.stdout.flush()
    except BrokenPipeError:
        # Point stdout at devnull so the interpreter's final flush does not raise a second time.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        print("worldguard: the reader closed the output early (broken pipe); the output is incomplete", file=sys.stderr)
        return BROKEN_PIPE_EXIT
    return code


def _run(argv):
    parser = argparse.ArgumentParser(prog="worldguard")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Check a world and its claim assertions.")
    choice = check.add_mutually_exclusive_group(required=True)
    choice.add_argument("--contract")
    choice.add_argument("--example", choices=["scene", "trip"])
    check.add_argument("--json", action="store_true", help="print the full report")
    meshcheck = commands.add_parser("mesh-check", help="Check a tree of worlds and their handoffs.")
    choice = meshcheck.add_mutually_exclusive_group(required=True)
    choice.add_argument("--mesh")
    choice.add_argument("--example", choices=["story"])
    meshcheck.add_argument("--json", action="store_true", help="print the full report")
    timeline_parser = commands.add_parser("timeline", help="Show event and token changes with check results.")
    choice = timeline_parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--contract")
    choice.add_argument("--mesh")
    choice.add_argument("--example", choices=["scene", "trip", "story"])
    timeline_parser.add_argument("--scenario")
    timeline_parser.add_argument("--full", action="store_true", help="print the full state on every timeline step")
    timeline_parser.add_argument("--json", action="store_true", help="print the complete timeline structure")
    life = commands.add_parser("lifeline", help="Draw one character's or thing's life from the world model (Mermaid).")
    choice = life.add_mutually_exclusive_group(required=True)
    choice.add_argument("--contract")
    choice.add_argument("--mesh")
    choice.add_argument("--example", choices=["scene", "trip", "story"])
    life.add_argument("--of", required=True, metavar="ENTITY", help="the character, thing or place to follow")
    life.add_argument("--all", action="store_true", help="draw every step instead of folding long middles")
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
    if args.command == "lifeline":
        from .contracts import GuardContract
        from .kernel import run_worldguard
        from .lifeline import DEFAULT_LIMIT, lifeline, render_mermaid
        from .mesh import ModelMeshContract, run_model_mesh

        try:
            if args.example:
                key = "mesh" if args.example == "story" else "contract"
                setattr(args, key, str(_example_path(args.example)))
            if args.mesh:
                mesh = ModelMeshContract.from_dict(load_mapping(args.mesh), base_dir=Path(args.mesh).resolve().parent)
                view = lifeline(args.of, mesh=mesh, report=run_model_mesh(mesh), limit=None if args.all else DEFAULT_LIMIT)
            else:
                contract = GuardContract.from_dict(load_mapping(args.contract))
                view = lifeline(args.of, contract=contract, report=run_worldguard(contract), limit=None if args.all else DEFAULT_LIMIT)
            text = render_mermaid(view)
            notice = "" if args.example else _open_lines(Path(args.mesh or args.contract).resolve().parent)
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("lifeline", args.mesh or args.contract or args.example, exc)
        print(text)
        _show_on_stderr(notice)
        return 0
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
                    text = dump_json({"mesh_id": mesh.mesh_id, "tree": report.tree, "nodes": views})
                else:
                    lines = list(report.tree)
                    for row in report.tree:
                        identity = row.strip().split()[0]
                        if identity in views:
                            padding = row[: len(row) - len(row.lstrip())]
                            lines.extend(padding + line for line in render_timeline_text(views[identity], label=identity, full=args.full).splitlines())
                    text = "\n".join(lines)
            else:
                contract = GuardContract.from_dict(load_mapping(args.contract))
                report = run_worldguard(contract)
                view = timeline(contract, scenario=args.scenario, report=report)
                text = dump_json(view) if args.json else render_timeline_text(view, full=args.full)
            notice = "" if args.example else _open_lines(Path(args.mesh or args.contract).resolve().parent)
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("timeline", args.mesh or args.contract or args.example, exc)
        if args.json:
            _show_on_stderr(notice)
        elif notice:
            text = notice + "\n" + text
        print(text)
        return 0
    if args.command == "check":
        from .contracts import GuardContract
        from .kernel import run_worldguard

        try:
            path = str(_example_path(args.example)) if args.example else args.contract
            report = run_worldguard(GuardContract.from_dict(load_mapping(path)))
            digests = input_digests([path], Path(path).parent)
            notice = "" if args.example else _open_lines(Path(path).resolve().parent)
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("check", args.example or args.contract, exc)
        payload = {**report.to_dict(), 'input_digests': digests}
        _emit(payload, lambda value: {**_unit_summary(value), 'input_digests': value['input_digests']}, args.json)
        _show_on_stderr(notice)
        return 0 if report.status.value == "PASS" else 1
    if args.command == "mesh-check":
        from .mesh import ModelMeshContract, run_model_mesh

        try:
            path = str(_example_path(args.example)) if args.example else args.mesh
            base_dir = Path(path).resolve().parent
            data = load_mapping(path)
            mesh = ModelMeshContract.from_dict(data, base_dir=base_dir)
            report = run_model_mesh(mesh)
            paths = [path, *[base_dir / node['contract'] for node in data.get('nodes', []) if isinstance(node.get('contract'), str)]]
            digests = input_digests(paths, base_dir)
            if not args.example:
                from .open_findings import load
                load(base_dir)  # an unreadable record is an input error before anything is written
        except (OSError, UnicodeError, ValueError) as exc:
            return _input_error("mesh-check", args.example or args.mesh, exc)
        full = {**report.to_dict(), 'input_digests': digests}
        _emit(full, _mesh_summary, args.json)
        if not args.example:
            from .open_findings import record, render, store_path
            try:
                change = record(base_dir, Path(path).name, full["gaps"], mesh=mesh, exists=_still_there(mesh))
            except OSError as exc:
                print(f"worldguard: could not record open contradictions in {store_path(base_dir)}: {exc}", file=sys.stderr)
            else:
                _show_on_stderr(render(change["open"], change["closed"], where=str(base_dir)))
        return 0 if report.status.value == "PASS" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
