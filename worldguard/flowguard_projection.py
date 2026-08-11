"""Explicit target-owned projection from WorldBlueprint into FlowGuard-neutral IDs.

The adapter exports only identities and source-to-target bindings.  It does not
run a target, infer facts, or claim object-DNA qualification.  WorldGuard's
native report remains the authority for native semantics; FlowGuard consumes
this projection as a separate, receipt-bound evidence lane.
"""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from typing import Any

from .blueprint import (
    CrossArtifactProjectionResult,
    WorldBlueprintContract,
    WorldBlueprintReport,
    _cross_artifact_required_source_ids,
)
from .semantic import fingerprint_mesh


PROVIDER_ID = "worldguard.flowguard.blueprint-projection"
PROVIDER_VERSION = "v1"
PROVIDER_CAPABILITY_ID = "worldguard.flowguard.target-blueprint.v1"
EXECUTION_OWNER_ID = "worldguard.flowguard.blueprint-projection-owner"
EXECUTION_OWNER_VERSION = "v1"
RECEIPT_SCHEMA = "worldguard.cross_artifact_projection_receipt.v1"


class FlowGuardProjectionError(RuntimeError):
    """The optional FlowGuard projection boundary is unavailable or stale."""


def require_flowguard_toolchain() -> dict[str, str]:
    """Load the real FlowGuard provider surface lazily and fail explicitly.

    WorldGuard's native blueprint path must remain usable without FlowGuard.
    Only an explicit projection request crosses this boundary, and it may not
    silently substitute a local schema, alias, or compatibility reader.
    """

    try:
        module = importlib.import_module("flowguard.target_system_blueprint")
    except ImportError as exc:  # pragma: no cover - exercised in isolated envs
        raise FlowGuardProjectionError(
            "FlowGuard is required for an explicit blueprint projection"
        ) from exc
    required = (
        "TARGET_SYSTEM_PROVIDER_PROFILE_SCHEMA",
        "TargetSystemProviderProfileDeclaration",
    )
    missing = tuple(name for name in required if not hasattr(module, name))
    if missing:
        raise FlowGuardProjectionError(
            "installed FlowGuard provider surface is not current: "
            + ", ".join(missing)
        )
    return {
        "provider_profile_schema": str(module.TARGET_SYSTEM_PROVIDER_PROFILE_SCHEMA),
        "provider_profile_type": "TargetSystemProviderProfileDeclaration",
    }


def build_flowguard_provider_profile(
    *,
    provider_id: str,
    target_profile: str,
    target_kind: str,
    layer_plan_id: str,
    layer_plan_fingerprint: str,
    owner_id: str,
    claim_boundary: str,
) -> Any:
    """Create a provider declaration through the installed FlowGuard type.

    The caller supplies the target profile and layer-plan identity.  There is
    intentionally no WorldGuard default profile: domain adapters own that
    choice and FlowGuard only validates the resulting declaration.
    """

    require_flowguard_toolchain()
    module = importlib.import_module("flowguard.target_system_blueprint")
    declaration_type = module.TargetSystemProviderProfileDeclaration
    return declaration_type(
        provider_id=provider_id,
        target_profile=target_profile,
        target_kind=target_kind,
        layer_plan_id=layer_plan_id,
        layer_plan_fingerprint=layer_plan_fingerprint,
        owner_id=owner_id,
        claim_boundary=claim_boundary,
    )


def _producer_identity_fingerprint() -> str:
    return "sha256:" + fingerprint_mesh(
        {
            "provider_id": PROVIDER_ID,
            "provider_version": PROVIDER_VERSION,
            "provider_capability_id": PROVIDER_CAPABILITY_ID,
            "execution_owner_id": EXECUTION_OWNER_ID,
            "execution_owner_version": EXECUTION_OWNER_VERSION,
        }
    )


def _write_receipt(
    result: CrossArtifactProjectionResult,
    receipt_path: Path,
) -> tuple[str, str]:
    receipt_payload = {
        "schema_version": RECEIPT_SCHEMA,
        "projection_id": result.projection_id,
        "provider_id": result.provider_id,
        "provider_version": result.provider_version,
        "provider_capability_id": result.provider_capability_id,
        "execution_owner_id": result.execution_owner_id,
        "execution_owner_version": result.execution_owner_version,
        "producer_identity_fingerprint": result.producer_identity_fingerprint,
        "projection_result_fingerprint": "sha256:" + fingerprint_mesh(result.evidence_payload()),
        "terminal_status": result.status,
    }
    content = json.dumps(
        receipt_payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_bytes(content)
    return (
        "sha256:" + hashlib.sha256(content).hexdigest(),
        "sha256:" + fingerprint_mesh(receipt_payload),
    )


def build_flowguard_projection(
    blueprint: WorldBlueprintContract,
    report: WorldBlueprintReport,
    *,
    receipt_locator: str = "support/flowguard-blueprint-projection-receipt.json",
) -> CrossArtifactProjectionResult:
    """Build one current projection for the supplied native report.

    A non-qualified native report produces a typed ``gap`` projection with the
    full source denominator unresolved.  It never shrinks the denominator or
    silently chooses a partial success path.
    """

    if report.blueprint_fingerprint != blueprint.blueprint_fingerprint:
        raise ValueError("FlowGuard projection report does not target the blueprint fingerprint")
    required = _cross_artifact_required_source_ids(blueprint)
    projected = required if report.native_domain_qualified else ()
    unresolved = () if report.native_domain_qualified else required
    normalized_payload = {
        "projection_items": [
            {
                "source_id": source_id,
                "target_ids": [f"worldguard:{blueprint.blueprint_id}"],
            }
            for source_id in projected
        ]
    }
    status = "proven" if report.native_domain_qualified else "gap"
    receipt_root = Path(blueprint.source_root).resolve()
    if not blueprint.source_root:
        raise ValueError("FlowGuard projection requires an explicit blueprint source root")
    path = Path(receipt_locator)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("FlowGuard projection receipt locator must stay inside the source root")
    preliminary = CrossArtifactProjectionResult.from_dict(
        {
            "schema_version": "worldguard.cross_artifact_projection.v1",
            "projection_id": f"projection:{blueprint.blueprint_id}:flowguard:v1",
            "provider_id": PROVIDER_ID,
            "provider_version": PROVIDER_VERSION,
            "provider_capability_id": PROVIDER_CAPABILITY_ID,
            "execution_owner_id": EXECUTION_OWNER_ID,
            "execution_owner_version": EXECUTION_OWNER_VERSION,
            "target_id": blueprint.target_id,
            "target_revision": blueprint.target_revision,
            "claim_boundary": blueprint.declared_boundary,
            "source_blueprint_fingerprint": "sha256:" + blueprint.blueprint_fingerprint,
            "source_report_fingerprint": "sha256:" + report.report_fingerprint,
            "required_source_ids": list(required),
            "projected_source_ids": list(projected),
            "unresolved_source_ids": list(unresolved),
            "normalized_payload": normalized_payload,
            "normalized_payload_fingerprint": "sha256:" + fingerprint_mesh(normalized_payload),
            "status": status,
            "receipt_locator": receipt_locator,
            "receipt_content_fingerprint": "sha256:" + "0" * 64,
            "producer_identity_fingerprint": _producer_identity_fingerprint(),
            "terminal_receipt_fingerprint": "sha256:" + "0" * 64,
        }
    )
    content_fingerprint, terminal_fingerprint = _write_receipt(
        preliminary,
        receipt_root / path,
    )
    return CrossArtifactProjectionResult.from_dict(
        {
            **preliminary.to_dict(),
            "receipt_content_fingerprint": content_fingerprint,
            "terminal_receipt_fingerprint": terminal_fingerprint,
        }
    )


__all__ = [
    "EXECUTION_OWNER_ID",
    "EXECUTION_OWNER_VERSION",
    "FlowGuardProjectionError",
    "PROVIDER_CAPABILITY_ID",
    "PROVIDER_ID",
    "PROVIDER_VERSION",
    "build_flowguard_projection",
    "build_flowguard_provider_profile",
    "require_flowguard_toolchain",
]
