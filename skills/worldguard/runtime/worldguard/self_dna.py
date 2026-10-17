"""FlowGuard-owned WorldGuard repository self-DNA route.

``WorldBlueprint`` models an arbitrary external world or workflow.  It is not
the WorldGuard repository's own DNA.  This explicit route delegates that
whole-repository question to the current FlowGuard self-blueprint API and
returns a visible blocked result whenever the project authority is stale or
the released provider is unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any

from .semantic import fingerprint_mesh


REPORT_KIND = "worldguard.native_directory_self_dna_report.v2"
NATIVE_DIRECTORY_SCHEMA = "worldguard.native_directory_dna.v1"
LAYER_IDS = (
    "evidence_qualification",
    "implementation_inventory",
    "traceability",
    "independent_semantics",
    "model_code_test_binding",
    "resource_oracle_binding",
    "static_blueprint_readiness",
)


def _flowguard_identity() -> dict[str, str]:
    try:
        version = importlib.metadata.version("flowguard")
    except importlib.metadata.PackageNotFoundError:
        version = "unavailable"
    try:
        import flowguard

        return {
            "package": "flowguard",
            "version": version,
            "schema_version": "flowguard.map.v1",
            "module": str(Path(flowguard.__file__).resolve()),
        }
    except (ImportError, AttributeError) as exc:
        return {
            "package": "flowguard",
            "version": version,
            "schema_version": "unavailable",
            "module": "unavailable",
            "import_error": f"{type(exc).__name__}: {exc}",
        }


def _blocked(root: Path, code: str, message: str, *, exc: Exception | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "report_kind": REPORT_KIND,
        "software_id": "worldguard",
        "target_kind": "software",
        "status": "blocked",
        "ok": False,
        "root": str(root),
        "claim_boundary": "Only the exact WorldGuard native directory boundary is covered; no directory copy or transport artifact is produced.",
        "flowguard": _flowguard_identity(),
        "readiness": {
            "layers": [
                {"layer": layer, "status": "blocked", "gap": code if index == 0 else ""}
                for index, layer in enumerate(LAYER_IDS)
            ],
            "deepest_proven_layer": "",
            "first_gap": code,
            "gap_count": 1,
        },
        "gap": {"code": code, "message": message},
        "dna_qualification": {
            "status": "blocked",
            "qualified": False,
            "reasons": [code],
        },
    }
    if exc is not None:
        result["gap"]["exception"] = f"{type(exc).__name__}: {exc}"
    return result


def _native_directory_snapshot(root: Path) -> dict[str, Any]:
    """Describe the current repository directory without materializing DNA.

    The snapshot is deliberately an in-memory audit value.  Volatile caches
    and the shared FlowGuard model-mesh workspace are excluded so a peer's
    untracked evidence cannot be deleted or silently become source authority.
    """

    root = root.resolve()
    if not root.is_dir():
        raise OSError(f"native directory does not exist: {root}")
    excluded_prefixes = (
        (".git",),
        (".codex",),
        (".flowguard",),
        (".flowguard", "model-mesh"),
        (".pytest_cache",),
        ("__pycache__",),
        ("build",),
        ("dist",),
        ("coverage",),
        ("work",),
        ("worldguard.egg-info",),
    )
    excluded_suffixes = (".pyc", ".pyo")
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        parts = tuple(relative.parts)
        if any(parts[: len(prefix)] == prefix for prefix in excluded_prefixes):
            continue
        if path.suffix.lower() in excluded_suffixes:
            continue
        content = path.read_bytes()
        files.append(
            {
                "relative_path": relative.as_posix(),
                "bytes": len(content),
                "sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
            }
        )
    identity = {
        "schema_version": NATIVE_DIRECTORY_SCHEMA,
        "files": files,
    }
    return {
        **identity,
        "root": str(root),
        "file_count": len(files),
        "content_fingerprint": "sha256:" + fingerprint_mesh(identity),
        "excluded_prefixes": ["/".join(prefix) for prefix in excluded_prefixes],
        "excluded_suffixes": list(excluded_suffixes),
    }


def _build(root: Path) -> tuple[dict[str, Any], Any | None]:
    try:
        native_directory = _native_directory_snapshot(root)
    except (OSError, UnicodeError) as exc:
        return _blocked(root, "native_directory_unavailable", "The native directory could not be read.", exc=exc), None
    try:
        from flowguard.map.mapfile import load_map
        from flowguard.map.inventory import build_inventory
        from flowguard.map.check import run_check
        data = load_map(root)
        findings = run_check(root, data, build_inventory(root, data.get("ignore", [])), strict=True)
    except Exception as exc:
        return _blocked(root, "current_map_unavailable", "The current FlowGuard map could not be audited.", exc=exc), None
    errors = [{"code": f.code, "message": f.message} for f in findings if f.level == "error"]
    return {
        "report_kind": REPORT_KIND,
        "software_id": "worldguard",
        "target_kind": "software",
        "status": "ready" if not errors else "not_ready",
        "ok": not errors,
        "root": str(root),
        "native_directory": native_directory,
        "flowguard": _flowguard_identity(),
        "readiness": {"status": "ready" if not errors else "blocked", "gap_count": len(errors),
                      "first_gap": errors[0] if errors else None, "rows": errors},
        "map_components": len(data["components"]),
        "claim_boundary": "Current directory inventory and confirmed map/code/test bindings only. Models and tests are not executed; full semantic equivalence and release are not licensed.",
    }, data


def check(root: str | Path, *, compact: bool = False) -> tuple[dict[str, Any], int]:
    root_path = Path(root).resolve()
    payload, _bundle = _build(root_path)
    if compact:
        readiness = payload.get("readiness", {})
        native_directory = payload.get("native_directory")
        if isinstance(native_directory, dict):
            native_directory = {
                key: value
                for key, value in native_directory.items()
                if key != "files"
            }
        payload = {
            "report_kind": payload.get("report_kind"),
            "software_id": payload.get("software_id"),
            "target_kind": payload.get("target_kind"),
            "status": payload.get("status"),
            "ok": payload.get("ok"),
            "native_directory": native_directory,
            "flowguard": payload.get("flowguard"),
            "readiness": {
                key: readiness[key]
                for key in ("status", "deepest_proven_layer", "first_gap", "gap_count", "implementation_admitted", "rows")
                if key in readiness
            },
        }
    return payload, 0 if payload.get("ok") else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worldguard self-dna")
    sub = parser.add_subparsers(dest="command", required=True)
    check_parser = sub.add_parser("check", help="audit the FlowGuard-owned repository self-DNA")
    check_parser.add_argument("--root", default=".")
    check_parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    payload, code = check(args.root, compact=args.compact)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return code


__all__ = ["check", "main"]
