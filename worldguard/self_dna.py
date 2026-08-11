"""FlowGuard-owned WorldGuard repository self-DNA route.

``WorldBlueprint`` models an arbitrary external world or workflow.  It is not
the WorldGuard repository's own DNA.  This explicit route delegates that
whole-repository question to the current FlowGuard self-blueprint API and
returns a visible blocked result whenever the project authority is stale or
the released provider is unavailable.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
from typing import Any


REPORT_KIND = "worldguard.flowguard_software_self_dna_report.v1"
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
            "schema_version": str(flowguard.SCHEMA_VERSION),
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
        "claim_boundary": "Only the exact WorldGuard repository boundary is covered; WorldBlueprint remains an external-object/domain model.",
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


def _build(root: Path) -> tuple[dict[str, Any], Any | None]:
    try:
        from flowguard.self_blueprint import FlowGuardSelfBlueprintError, build_flowguard_self_blueprint
    except (ImportError, AttributeError) as exc:
        return _blocked(root, "flowguard_toolchain_unavailable", "The current FlowGuard self-blueprint API cannot be imported.", exc=exc), None
    try:
        bundle = build_flowguard_self_blueprint(root)
    except FlowGuardSelfBlueprintError as exc:
        return _blocked(root, "flowguard_self_blueprint_not_ready", "FlowGuard rejected the current WorldGuard project authority, definition, inventory, or model evidence; no local substitute is used.", exc=exc), None
    except (OSError, ValueError) as exc:
        return _blocked(root, "flowguard_self_blueprint_input_invalid", "The current FlowGuard self-blueprint inputs are invalid or unavailable.", exc=exc), None
    qualification = getattr(bundle, "dna_qualification", None)
    if qualification is None:
        return _blocked(
            root,
            "flowguard_dna_qualification_missing",
            "The current FlowGuard self-blueprint did not expose its provider-neutral DNA qualification contract.",
        ), None
    qualified = bool(qualification.qualified)
    return {
        "report_kind": REPORT_KIND,
        "software_id": "worldguard",
        "target_kind": "software",
        "status": "ready" if bundle.ok and qualified else "not_ready",
        "ok": bool(bundle.ok and qualified),
        "root": str(root),
        "claim_boundary": "This is the FlowGuard repository software-DNA boundary. The seven WorldGuard domain owners and WorldBlueprint remain separate child evidence.",
        "flowguard": _flowguard_identity(),
        "readiness": bundle.readiness_ledger.to_dict(),
        "dna_qualification": qualification.to_dict(),
        "bundle": bundle.to_dict(),
    }, bundle


def _outside(root: Path, output: Path) -> bool:
    try:
        output.relative_to(root)
    except ValueError:
        return True
    return False


def check(root: str | Path, *, compact: bool = False) -> tuple[dict[str, Any], int]:
    root_path = Path(root).resolve()
    payload, _bundle = _build(root_path)
    if compact:
        readiness = payload.get("readiness", {})
        payload = {
            "report_kind": payload.get("report_kind"),
            "software_id": payload.get("software_id"),
            "target_kind": payload.get("target_kind"),
            "status": payload.get("status"),
            "ok": payload.get("ok"),
            "flowguard": payload.get("flowguard"),
            "readiness": {
                key: readiness[key]
                for key in ("status", "deepest_proven_layer", "first_gap", "gap_count", "implementation_admitted", "rows")
                if key in readiness
            },
        }
    return payload, 0 if payload.get("ok") else 1


def export(root: str | Path, output: str | Path) -> tuple[dict[str, Any], int]:
    root_path = Path(root).resolve()
    output_path = Path(output).resolve()
    if not _outside(root_path, output_path):
        return _blocked(root_path, "self_dna_export_inside_repository", "Canonical self-DNA must be materialized outside the repository it describes."), 1
    payload, bundle = _build(root_path)
    if bundle is None or not bundle.ok:
        return payload, 1
    try:
        from flowguard.implementation_blueprint import project_canonical_software_blueprint, verify_materialized_project_blueprint_projection, write_canonical_blueprint_projection

        # The FlowGuard self wrapper carries the exact typed project bundle in
        # ``project_bundle``.  The wrapper is a reporting facade and is not
        # accepted by the canonical exporter itself.
        project_bundle = getattr(bundle, "project_bundle", None)
        if project_bundle is None:
            return _blocked(
                root_path,
                "flowguard_project_bundle_missing",
                "The current FlowGuard self-blueprint did not expose its exact typed project bundle.",
            ), 1
        projection = project_canonical_software_blueprint(project_bundle)
        written = write_canonical_blueprint_projection(projection, output_path)
        verification = verify_materialized_project_blueprint_projection(output_path, project_bundle)
        if not verification.ok:
            return _blocked(root_path, "self_dna_export_materialization_invalid", "FlowGuard did not verify the isolated canonical self-DNA materialization."), 1
        payload["export"] = {
            "status": "complete",
            "output": str(output_path),
            "projection_fingerprint": projection.fingerprint,
            "written_paths": [str(path) for path in written],
            "isolated_import_verified": True,
        }
        return payload, 0
    except (ImportError, AttributeError, OSError, ValueError) as exc:
        return _blocked(root_path, "self_dna_export_failed", "The current FlowGuard export API could not materialize and verify the external canonical self-DNA.", exc=exc), 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="worldguard self-dna")
    sub = parser.add_subparsers(dest="command", required=True)
    check_parser = sub.add_parser("check", help="audit the FlowGuard-owned repository self-DNA")
    check_parser.add_argument("--root", default=".")
    check_parser.add_argument("--compact", action="store_true")
    export_parser = sub.add_parser("export", help="materialize self-DNA outside the repository")
    export_parser.add_argument("--root", default=".")
    export_parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    payload, code = check(args.root, compact=args.compact) if args.command == "check" else export(args.root, args.output)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return code


__all__ = ["check", "export", "main"]
