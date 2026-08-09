from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import tempfile
import zlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .blueprint import (
    BlueprintError,
    CrossArtifactProjectionResult,
    WorldBlueprintContract,
    WorldBlueprintReport,
    _build_blueprint_indexes,
    blueprint_impact,
    blueprint_reverse_trace,
    check_world_blueprint,
    compile_behavior_commitment_inventory_cache,
)
from .semantic import fingerprint_mesh


WORLD_BLUEPRINT_BUNDLE_SCHEMA_VERSION = "worldguard.world_blueprint_bundle.v2"
WORLD_BLUEPRINT_BUNDLE_MANIFEST_SCHEMA_VERSION = (
    "worldguard.world_blueprint_bundle_manifest.v2"
)
WORLD_BLUEPRINT_BUNDLE_VERIFICATION_SCHEMA_VERSION = (
    "worldguard.world_blueprint_bundle_verification.v2"
)
WORLD_BLUEPRINT_BUNDLE_QUERY_SCHEMA_VERSION = (
    "worldguard.world_blueprint_bundle_query.v2"
)

_BUNDLE_FIELDS = {
    "schema_version",
    "blueprint",
    "cross_artifact_projection",
    "replay_resources",
    "reproducibility_manifest",
    "logical_bundle_fingerprint",
}
_RETIRED_DERIVED_BUNDLE_FIELDS = {
    "qualification_report",
    "query_indexes",
    "fixed_query_answers",
    "handoff_answers",
    "handoff_qualification",
}
_MANIFEST_FIELDS = {
    "schema_version",
    "replay_resource_codec",
    "fingerprints",
    "counts",
    "status",
    "first_gap",
    "claim_boundary",
    "component_sizes",
}
_BUNDLE_QUERY_KINDS = {
    "node",
    "element",
    "behavior-case",
    "binding",
    "impact",
    "reverse",
}
_MAX_REPLAY_RESOURCE_BYTES = 16 * 1024 * 1024
_REPLAY_RESOURCE_CODEC_ID = "worldguard.replay-resource.zlib-rfc1950-base64.v1"
_REPLAY_RESOURCE_CODEC = {
    "codec_id": _REPLAY_RESOURCE_CODEC_ID,
    "container": "RFC1950",
    "compression_level": 9,
    "window_bits": 15,
    "binary_to_text": "RFC4648-base64",
    "semantic_identity": "decoded-byte-length+decoded-byte-sha256",
    "compressed_bytes_authority": "transport-only",
    "toolchain_boundary": (
        "RFC1950-compatible python.stdlib.zlib compress/decompressobj; "
        "encoder-version output is not semantic identity"
    ),
    "maximum_decoded_resource_bytes": _MAX_REPLAY_RESOURCE_BYTES,
}


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = os.lstat(path)
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        reparse_flag and file_attributes & reparse_flag
    )


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _safe_relative_resource_path(locator: str, *, owner: str) -> str:
    path_text = locator.partition("#")[0]
    relative = Path(path_text)
    if relative.is_absolute() or not path_text:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_RESOURCE_PATH_INVALID",
            f"{owner} requires a non-empty relative resource path.",
            details={"owner": owner, "locator": locator},
        )
    normalized = Path(*relative.parts)
    if ".." in normalized.parts:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_RESOURCE_PATH_INVALID",
            f"{owner} resource path escapes the bundle root.",
            details={"owner": owner, "locator": locator},
        )
    return normalized.as_posix()


def _replay_resource_paths(
    blueprint: WorldBlueprintContract,
    *,
    extra_locators: tuple[str, ...] = (),
) -> tuple[str, ...]:
    paths: set[str] = set()
    paths.update(
        _safe_relative_resource_path(row.locator, owner=f"binding {row.binding_id}")
        for row in blueprint.bindings
        if row.observation_mode in {"local_content", "provider_content"}
    )
    paths.update(
        _safe_relative_resource_path(
            row.locator, owner=f"commitment input {row.input_id}"
        )
        for row in blueprint.commitment_inventory.input_refs
        if row.observation_mode == "local_content"
    )
    paths.update(
        _safe_relative_resource_path(locator, owner="cross-artifact receipt")
        for locator in extra_locators
    )
    return tuple(sorted(paths))


def _embedded_resources(
    blueprint: WorldBlueprintContract,
    *,
    extra_locators: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    if not blueprint.source_root:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_SOURCE_ROOT_MISSING",
            "Portable bundle export requires the qualified blueprint source root.",
        )
    root = Path(blueprint.source_root).resolve()
    resources: list[dict[str, Any]] = []
    for relative_path in _replay_resource_paths(
        blueprint, extra_locators=extra_locators
    ):
        candidate = (root / Path(relative_path)).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise BlueprintError(
                "WORLD_BLUEPRINT_BUNDLE_RESOURCE_UNAVAILABLE",
                "A required replay resource is outside the source root or missing.",
                details={"relative_path": relative_path},
            )
        content = candidate.read_bytes()
        resources.append(
            {
                "relative_path": relative_path,
                "codec_id": _REPLAY_RESOURCE_CODEC_ID,
                "content_sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
                "content_size": len(content),
                "content_zlib_base64": base64.b64encode(
                    zlib.compress(content, level=9)
                ).decode("ascii"),
            }
        )
    return resources


def _query_indexes(blueprint: WorldBlueprintContract) -> dict[str, Any]:
    indexes = _build_blueprint_indexes(blueprint)
    return {
        "kinds": {key: indexes.kinds[key] for key in sorted(indexes.kinds)},
        "forward": {
            key: list(indexes.forward[key]) for key in sorted(indexes.forward)
        },
        "reverse": {
            key: list(indexes.reverse[key]) for key in sorted(indexes.reverse)
        },
        "binding_ids": sorted(indexes.binding_ids),
        "input_port_ids": sorted(indexes.input_port_ids),
        "output_port_ids": sorted(indexes.output_port_ids),
        "declared_input_ids": sorted(indexes.declared_input_ids),
    }


def _fixed_query_answers(
    blueprint: WorldBlueprintContract,
    *,
    trusted_object_census_authority_fingerprints: Iterable[str] = (),
    trusted_object_census_producer_descriptor_fingerprints: Iterable[str] = (),
) -> dict[str, Any]:
    impact_target_ids = (
        [blueprint.elements[0].element_id] if blueprint.elements else []
    )
    impact_answers = {
        target_id: blueprint_impact(
            blueprint,
            blueprint_fingerprint=blueprint.blueprint_fingerprint,
            changed_ids=[target_id],
            trusted_object_census_authority_fingerprints=(
                trusted_object_census_authority_fingerprints
            ),
            trusted_object_census_producer_descriptor_fingerprints=(
                trusted_object_census_producer_descriptor_fingerprints
            ),
        ).to_dict()
        for target_id in impact_target_ids
    }
    reverse_target_ids = sorted(row.output_id for row in blueprint.declared_outputs)
    reverse_answers = {
        target_id: blueprint_reverse_trace(
            blueprint,
            blueprint_fingerprint=blueprint.blueprint_fingerprint,
            target_id=target_id,
            trusted_object_census_authority_fingerprints=(
                trusted_object_census_authority_fingerprints
            ),
            trusted_object_census_producer_descriptor_fingerprints=(
                trusted_object_census_producer_descriptor_fingerprints
            ),
        ).to_dict()
        for target_id in reverse_target_ids
    }
    return {
        "query_plan": {
            "impact_target_ids": impact_target_ids,
            "reverse_target_ids": reverse_target_ids,
        },
        "impact_by_element": impact_answers,
        "reverse_by_element_or_declared_output": reverse_answers,
    }


def _handoff_answers(
    blueprint: WorldBlueprintContract,
    report: WorldBlueprintReport,
    *,
    fixed_queries: Mapping[str, Any],
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for element in blueprint.elements:
        semantic = element.native_semantic
        if semantic is None or semantic.task_purpose is None:
            continue
        for case in semantic.task_purpose.behavior_cases:
            cases.append(
                {
                    "element_id": element.element_id,
                    "declaration_id": semantic.task_purpose.declaration_id,
                    "case_id": case.case_id,
                    "case_kind": case.case_kind,
                    "oracle_id": case.oracle_id,
                    "case_fingerprint": case.case_fingerprint,
                }
            )
    first_gap = None
    if report.first_unresolved_layer is not None:
        first_gap = {
            "depth": report.first_unresolved_layer,
            "gap_ids": sorted(
                gap.gap_id
                for gap in report.gaps
                if gap.depth == report.first_unresolved_layer
            ),
        }
    return {
        "root_node_id": blueprint.root_node_id,
        "children_by_node": {
            node.node_id: list(node.child_node_ids) for node in blueprint.nodes
        },
        "ports_by_owner": {
            **{
                f"node:{node.node_id}": {
                    "inputs": [row.to_dict() for row in node.input_ports],
                    "outputs": [row.to_dict() for row in node.output_ports],
                }
                for node in blueprint.nodes
            },
            **{
                f"element:{element.element_id}": {
                    "inputs": [row.to_dict() for row in element.input_ports],
                    "outputs": [row.to_dict() for row in element.output_ports],
                }
                for element in blueprint.elements
            },
        },
        "elements": [
            {
                "element_id": row.element_id,
                "kind": row.kind,
                "owner_node_id": row.owner_node_id,
            }
            for row in blueprint.elements
        ],
        "behavior_cases_and_oracles": cases,
        "bindings": [row.to_dict() for row in blueprint.bindings],
        "first_gap": first_gap,
        "impact_answers": fixed_queries["impact_by_element"],
        "reverse_answers": fixed_queries[
            "reverse_by_element_or_declared_output"
        ],
    }


def _handoff_qualification(report: WorldBlueprintReport) -> dict[str, Any]:
    projection_layer = next(
        row
        for row in report.qualification_layers
        if row.layer_id == "cross_artifact_projection"
    )
    return {
        "native_handoff_qualified": report.native_domain_qualified,
        "object_dna_handoff_qualified": report.object_dna_qualified,
        "object_census": report.object_census,
        "full_cross_artifact_handoff_qualified": (
            report.full_domain_qualified and projection_layer.status.value == "proven"
        ),
        "cross_artifact_projection_status": projection_layer.status.value,
        "claim_boundary": report.claim_boundary,
    }


def _fingerprint(value: Any) -> str:
    return "sha256:" + fingerprint_mesh(value)


def _first_gap(report: WorldBlueprintReport) -> dict[str, Any] | None:
    if report.first_unresolved_layer is None:
        return None
    return {
        "depth": report.first_unresolved_layer,
        "gap_ids": sorted(
            gap.gap_id
            for gap in report.gaps
            if gap.depth == report.first_unresolved_layer
        ),
    }


def _behavior_case_catalog(
    blueprint: WorldBlueprintContract,
) -> tuple[list[str], list[dict[str, str]]]:
    case_ids: list[str] = []
    owners: list[dict[str, str]] = []
    for element in blueprint.elements:
        semantic = element.native_semantic
        if semantic is None or semantic.task_purpose is None:
            continue
        for case in semantic.task_purpose.behavior_cases:
            case_ids.append(case.case_id)
            owners.append(
                {
                    "case_id": case.case_id,
                    "element_id": element.element_id,
                    "declaration_id": semantic.task_purpose.declaration_id,
                }
            )
    return sorted(case_ids), sorted(owners, key=lambda row: row["case_id"])


def _reproducibility_manifest(
    blueprint: WorldBlueprintContract,
    report: WorldBlueprintReport,
    *,
    replay_resources: list[dict[str, Any]],
    commitment_cache: Mapping[str, Any],
    cross_artifact_projection: Mapping[str, Any] | None,
    trusted_object_census_authority_fingerprints: Iterable[str] = (),
    trusted_object_census_producer_descriptor_fingerprints: Iterable[str] = (),
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Recompute every governed projection and retain only its compact DNA."""

    source_qualified = (
        report.status.value == "PASS" and report.native_domain_qualified
    )
    query_indexes: dict[str, Any] | None = None
    fixed_queries: dict[str, Any] = {
        "query_plan": {"impact_target_ids": [], "reverse_target_ids": []},
        "impact_by_element": {},
        "reverse_by_element_or_declared_output": {},
    }
    if source_qualified:
        query_indexes = _query_indexes(blueprint)
        fixed_queries = _fixed_query_answers(
            blueprint,
            trusted_object_census_authority_fingerprints=(
                trusted_object_census_authority_fingerprints
            ),
            trusted_object_census_producer_descriptor_fingerprints=(
                trusted_object_census_producer_descriptor_fingerprints
            ),
        )

    handoff_answers = _handoff_answers(
        blueprint,
        report,
        fixed_queries=fixed_queries,
    )
    handoff_qualification = _handoff_qualification(report)
    handoff_projection = {
        "answers": handoff_answers,
        "qualification": handoff_qualification,
    }
    report_payload = report.to_dict()
    case_ids, case_owners = _behavior_case_catalog(blueprint)
    query_kinds = query_indexes["kinds"] if query_indexes is not None else {}
    query_kind_counts: dict[str, int] = {}
    for kind in query_kinds.values():
        query_kind_counts[kind] = query_kind_counts.get(kind, 0) + 1
    forward_edge_count = (
        sum(len(rows) for rows in query_indexes["forward"].values())
        if query_indexes is not None
        else 0
    )
    reverse_edge_count = (
        sum(len(rows) for rows in query_indexes["reverse"].values())
        if query_indexes is not None
        else 0
    )
    projection_payload: Mapping[str, Any] | None = cross_artifact_projection
    catalog = {
        "node_ids": sorted(node.node_id for node in blueprint.nodes),
        "element_ids": sorted(element.element_id for element in blueprint.elements),
        "behavior_case_ids": case_ids,
        "behavior_case_owners": case_owners,
        "binding_ids": sorted(binding.binding_id for binding in blueprint.bindings),
        "replay_resource_paths": sorted(
            str(row["relative_path"]) for row in replay_resources
        ),
        "query_member_ids": sorted(query_kinds),
        "impact_target_ids": list(fixed_queries["query_plan"]["impact_target_ids"]),
        "reverse_target_ids": list(fixed_queries["query_plan"]["reverse_target_ids"]),
    }
    manifest = {
        "schema_version": WORLD_BLUEPRINT_BUNDLE_MANIFEST_SCHEMA_VERSION,
        "replay_resource_codec": dict(_REPLAY_RESOURCE_CODEC),
        "fingerprints": {
            "blueprint": blueprint.blueprint_fingerprint,
            "qualification_report": report.report_fingerprint,
            "query_indexes": (
                _fingerprint(query_indexes) if query_indexes is not None else None
            ),
            "fixed_impact_answers": _fingerprint(
                fixed_queries["impact_by_element"]
            ),
            "fixed_reverse_answers": _fingerprint(
                fixed_queries["reverse_by_element_or_declared_output"]
            ),
            "handoff_projection": _fingerprint(handoff_projection),
            "replay_resources": _fingerprint(replay_resources),
            "commitment_cache": _fingerprint(commitment_cache),
            "catalog": _fingerprint(catalog),
            "cross_artifact_projection": (
                _fingerprint(projection_payload)
                if projection_payload is not None
                else None
            ),
        },
        "counts": {
            "nodes": len(blueprint.nodes),
            "elements": len(blueprint.elements),
            "behavior_cases": len(case_ids),
            "bindings": len(blueprint.bindings),
            "replay_resources": len(replay_resources),
            "qualification_layers": len(report.qualification_layers),
            "depth_layers": len(report.depth_layers),
            "native_execution_receipts": len(report.native_execution_receipts),
            "gaps": len(report.gaps),
            "query_members": len(query_kinds),
            "query_forward_edges": forward_edge_count,
            "query_reverse_edges": reverse_edge_count,
            "query_members_by_kind": {
                key: query_kind_counts[key] for key in sorted(query_kind_counts)
            },
            "fixed_impact_answers": len(fixed_queries["impact_by_element"]),
            "fixed_reverse_answers": len(
                fixed_queries["reverse_by_element_or_declared_output"]
            ),
        },
        "status": {
            "qualification": report.status.value,
            "native_handoff_qualified": handoff_qualification[
                "native_handoff_qualified"
            ],
            "full_cross_artifact_handoff_qualified": handoff_qualification[
                "full_cross_artifact_handoff_qualified"
            ],
            "object_dna_handoff_qualified": handoff_qualification[
                "object_dna_handoff_qualified"
            ],
            "object_census_authority_status": report.object_census[
                "authority_status"
            ],
            "object_census_authority_licensed": report.object_census[
                "authority_licensed"
            ],
            "object_census_coverage_complete": report.object_census[
                "coverage_complete"
            ],
            "object_claim_kind": report.object_census["object_claim_kind"],
            "object_census_first_gap": report.object_census["first_gap"],
            "cross_artifact_projection": handoff_qualification[
                "cross_artifact_projection_status"
            ],
            "query_derivation": "recomputed" if source_qualified else "not_run",
        },
        "first_gap": _first_gap(report),
        "claim_boundary": report.claim_boundary,
        "component_sizes": {
            "blueprint_utf8_bytes": len(_canonical_json_bytes(blueprint.to_dict())),
            "cross_artifact_projection_utf8_bytes": len(
                _canonical_json_bytes(projection_payload)
            ),
            "replay_resources_utf8_bytes": len(
                _canonical_json_bytes(replay_resources)
            ),
            "regenerated_commitment_cache_utf8_bytes": len(
                _canonical_json_bytes(commitment_cache)
            ),
            "qualification_report_utf8_bytes": len(
                _canonical_json_bytes(report_payload)
            ),
            "query_indexes_utf8_bytes": len(
                _canonical_json_bytes(query_indexes)
            ),
            "fixed_query_answers_utf8_bytes": len(
                _canonical_json_bytes(fixed_queries)
            ),
            "handoff_projection_utf8_bytes": len(
                _canonical_json_bytes(handoff_projection)
            ),
        },
    }
    return manifest, {
        "query_indexes": query_indexes,
        "fixed_queries": fixed_queries,
        "handoff_answers": handoff_answers,
        "handoff_qualification": handoff_qualification,
        "catalog": catalog,
    }


def build_world_blueprint_bundle(
    blueprint: WorldBlueprintContract,
    *,
    cross_artifact_projection: CrossArtifactProjectionResult
    | Mapping[str, Any]
    | None = None,
    trusted_object_census_authority_fingerprints: Iterable[str] = (),
    trusted_object_census_producer_descriptor_fingerprints: Iterable[str] = (),
) -> dict[str, Any]:
    report = check_world_blueprint(
        blueprint,
        cross_artifact_projection=cross_artifact_projection,
        trusted_object_census_authority_fingerprints=(
            trusted_object_census_authority_fingerprints
        ),
        trusted_object_census_producer_descriptor_fingerprints=(
            trusted_object_census_producer_descriptor_fingerprints
        ),
    )
    projection_payload = (
        report.cross_artifact_projection.to_dict()
        if report.cross_artifact_projection is not None
        else None
    )
    replay_resources = _embedded_resources(
        blueprint,
        extra_locators=(
            (report.cross_artifact_projection.receipt_locator,)
            if report.cross_artifact_projection is not None
            else ()
        ),
    )
    commitment_cache = compile_behavior_commitment_inventory_cache(blueprint)
    manifest, _ = _reproducibility_manifest(
        blueprint,
        report,
        replay_resources=replay_resources,
        commitment_cache=commitment_cache,
        cross_artifact_projection=projection_payload,
        trusted_object_census_authority_fingerprints=(
            trusted_object_census_authority_fingerprints
        ),
        trusted_object_census_producer_descriptor_fingerprints=(
            trusted_object_census_producer_descriptor_fingerprints
        ),
    )
    payload: dict[str, Any] = {
        "schema_version": WORLD_BLUEPRINT_BUNDLE_SCHEMA_VERSION,
        "blueprint": blueprint.to_dict(),
        "cross_artifact_projection": projection_payload,
        "replay_resources": replay_resources,
        "reproducibility_manifest": manifest,
    }
    return {
        **payload,
        "logical_bundle_fingerprint": _fingerprint(payload),
    }


def write_world_blueprint_bundle(
    blueprint: WorldBlueprintContract,
    destination: str | Path,
    *,
    cross_artifact_projection: CrossArtifactProjectionResult
    | Mapping[str, Any]
    | None = None,
    source_blueprint_path: str | Path | None = None,
    trusted_object_census_authority_fingerprints: Iterable[str] = (),
    trusted_object_census_producer_descriptor_fingerprints: Iterable[str] = (),
) -> dict[str, Any]:
    destination_path = Path(destination)
    if _is_link_or_reparse(destination_path):
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_DESTINATION_LINKED",
            "Portable bundle destination must not be a link or reparse point.",
            details={"destination": str(destination_path)},
        )
    if destination_path.exists() and destination_path.is_dir():
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_DESTINATION_INVALID",
            "Portable bundle destination must be a file path, not a directory.",
            details={"destination": str(destination_path)},
        )
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if any(
        parent.exists() and _is_link_or_reparse(parent)
        for parent in destination_path.parents
    ):
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_DESTINATION_LINKED",
            "Portable bundle destination ancestors must not be links or reparse points.",
            details={"destination": str(destination_path)},
        )
    resolved_destination = destination_path.resolve()
    projection_locator = ""
    if isinstance(cross_artifact_projection, CrossArtifactProjectionResult):
        projection_locator = cross_artifact_projection.receipt_locator
    elif isinstance(cross_artifact_projection, Mapping):
        projection_locator = str(
            cross_artifact_projection.get("receipt_locator", "")
        )
    protected_paths: set[Path] = set()
    declared_source_path = source_blueprint_path or blueprint.source_path
    if declared_source_path:
        protected_paths.add(Path(declared_source_path).resolve())
    if blueprint.source_root:
        replay_root = Path(blueprint.source_root).resolve()
        protected_paths.update(
            (replay_root / Path(relative_path)).resolve()
            for relative_path in _replay_resource_paths(
                blueprint,
                extra_locators=(
                    (projection_locator,) if projection_locator else ()
                ),
            )
        )
        protected_paths.add(
            (
                replay_root
                / Path(
                    _safe_relative_resource_path(
                        blueprint.commitment_inventory.locator,
                        owner="commitment inventory cache",
                    )
                )
            ).resolve()
        )
    if resolved_destination in protected_paths:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_DESTINATION_PROTECTED",
            "Portable bundle destination must not overwrite the source blueprint or a replay resource.",
            details={"destination": str(resolved_destination)},
        )
    payload = build_world_blueprint_bundle(
        blueprint,
        cross_artifact_projection=cross_artifact_projection,
        trusted_object_census_authority_fingerprints=(
            trusted_object_census_authority_fingerprints
        ),
        trusted_object_census_producer_descriptor_fingerprints=(
            trusted_object_census_producer_descriptor_fingerprints
        ),
    )
    content = _canonical_json_bytes(payload) + b"\n"
    prefix = f".{destination_path.name}.worldguard-bundle-"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=prefix,
        suffix=".tmp",
        dir=destination_path.parent,
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    try:
        _write_bundle_temp_file(temporary_path, content)
        observed = temporary_path.read_bytes()
        if (
            observed != content
            or hashlib.sha256(observed).digest()
            != hashlib.sha256(content).digest()
        ):
            raise BlueprintError(
                "WORLD_BLUEPRINT_BUNDLE_EXPORT_TEMP_VALIDATION_FAILED",
                "Portable bundle temporary bytes did not match the canonical payload.",
            )
        os.replace(temporary_path, destination_path)
    finally:
        if (
            temporary_path.parent.resolve() == destination_path.parent.resolve()
            and temporary_path.name.startswith(prefix)
            and temporary_path.exists()
        ):
            temporary_path.unlink()
    return payload


def _write_bundle_temp_file(path: Path, content: bytes) -> None:
    with path.open("wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def load_world_blueprint_bundle(path: str | Path) -> dict[str, Any]:
    try:
        payload: Any = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_LOAD_FAILED",
            "Portable blueprint bundle is missing or invalid JSON.",
            details={"error_type": type(exc).__name__, "error": str(exc)},
        ) from exc
    if not isinstance(payload, Mapping):
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_SHAPE_INVALID",
            "Portable blueprint bundle root must be an object.",
        )
    return dict(payload)


@dataclass(frozen=True)
class _VerifiedBundleReplay:
    payload: dict[str, Any]
    blueprint: WorldBlueprintContract
    report: WorldBlueprintReport
    manifest: dict[str, Any]
    derived: dict[str, Any]
    logical_bundle_fingerprint: str
    bundle_utf8_bytes: int


def _validate_bundle_envelope(
    bundle: Mapping[str, Any] | str | Path,
) -> tuple[dict[str, Any], str, int]:
    payload = (
        load_world_blueprint_bundle(bundle)
        if isinstance(bundle, (str, Path))
        else dict(bundle)
    )
    if set(payload) != _BUNDLE_FIELDS:
        unknown_fields = sorted(set(payload).difference(_BUNDLE_FIELDS))
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_SHAPE_INVALID",
            "Portable blueprint bundle fields are incomplete or unknown.",
            details={
                "missing_fields": sorted(_BUNDLE_FIELDS.difference(payload)),
                "unknown_fields": unknown_fields,
                "retired_derived_fields": sorted(
                    set(unknown_fields).intersection(_RETIRED_DERIVED_BUNDLE_FIELDS)
                ),
            },
        )
    if payload["schema_version"] != WORLD_BLUEPRINT_BUNDLE_SCHEMA_VERSION:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_SCHEMA_INVALID",
            "Portable blueprint bundle schema is not current.",
        )
    fingerprint_payload = {
        key: value
        for key, value in payload.items()
        if key != "logical_bundle_fingerprint"
    }
    expected_logical_fingerprint = _fingerprint(fingerprint_payload)
    if payload["logical_bundle_fingerprint"] != expected_logical_fingerprint:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_FINGERPRINT_MISMATCH",
            "Portable blueprint bundle logical fingerprint is stale.",
            details={
                "expected": expected_logical_fingerprint,
                "observed": payload["logical_bundle_fingerprint"],
            },
        )
    return (
        payload,
        expected_logical_fingerprint,
        len(_canonical_json_bytes(payload)) + 1,
    )


def _materialize_replay_resources(
    payload: Mapping[str, Any],
    *,
    materialization_root: str | Path,
) -> tuple[Path, list[dict[str, Any]], set[str]]:
    requested_root = Path(materialization_root)
    if _is_link_or_reparse(requested_root) or any(
        parent.exists() and _is_link_or_reparse(parent)
        for parent in requested_root.parents
    ):
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_MATERIALIZATION_ROOT_LINKED",
            "Bundle materialization root and its existing ancestors must not be links.",
        )
    if requested_root.exists():
        if not requested_root.is_dir() or any(requested_root.iterdir()):
            raise BlueprintError(
                "WORLD_BLUEPRINT_BUNDLE_MATERIALIZATION_ROOT_NOT_EMPTY",
                "Bundle materialization root must not exist or must be an empty directory.",
            )
    else:
        requested_root.mkdir(parents=True, exist_ok=False)
    root = requested_root.resolve()
    resources_value = payload["replay_resources"]
    if not isinstance(resources_value, list):
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_RESOURCE_SHAPE_INVALID",
            "Portable blueprint replay_resources must be a list.",
        )
    resources: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for value in resources_value:
        if not isinstance(value, Mapping) or set(value) != {
            "relative_path",
            "codec_id",
            "content_sha256",
            "content_size",
            "content_zlib_base64",
        }:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BUNDLE_RESOURCE_SHAPE_INVALID",
                "Portable blueprint replay resource has an invalid shape.",
            )
        row = dict(value)
        relative_path = _safe_relative_resource_path(
            str(row["relative_path"]), owner="bundle replay resource"
        )
        if relative_path in seen_paths:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BUNDLE_RESOURCE_DUPLICATE",
                "Portable blueprint replay resource path is duplicated.",
                details={"relative_path": relative_path},
            )
        seen_paths.add(relative_path)
        if row["codec_id"] != _REPLAY_RESOURCE_CODEC_ID:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BUNDLE_RESOURCE_CODEC_MISMATCH",
                "Portable blueprint replay resource codec is not current.",
                details={
                    "relative_path": relative_path,
                    "expected": _REPLAY_RESOURCE_CODEC_ID,
                    "observed": row["codec_id"],
                },
            )
        declared_size = row["content_size"]
        if (
            not isinstance(declared_size, int)
            or isinstance(declared_size, bool)
            or declared_size < 0
            or declared_size > _MAX_REPLAY_RESOURCE_BYTES
        ):
            raise BlueprintError(
                "WORLD_BLUEPRINT_BUNDLE_RESOURCE_SIZE_INVALID",
                "Portable blueprint replay resource has an invalid decoded byte size.",
                details={
                    "relative_path": relative_path,
                    "content_size": declared_size,
                    "maximum": _MAX_REPLAY_RESOURCE_BYTES,
                },
            )
        try:
            compressed = base64.b64decode(
                str(row["content_zlib_base64"]), validate=True
            )
            decompressor = zlib.decompressobj()
            content = decompressor.decompress(compressed, declared_size + 1)
            if decompressor.unconsumed_tail:
                raise BlueprintError(
                    "WORLD_BLUEPRINT_BUNDLE_RESOURCE_DECOMPRESSION_LIMIT",
                    "Portable blueprint replay resource exceeds its declared decoded size.",
                    details={
                        "relative_path": relative_path,
                        "declared_size": declared_size,
                        "maximum": _MAX_REPLAY_RESOURCE_BYTES,
                    },
                )
            content += decompressor.flush()
            if not decompressor.eof or decompressor.unused_data:
                raise ValueError("compressed resource has a non-canonical tail")
        except BlueprintError:
            raise
        except (ValueError, TypeError, zlib.error) as exc:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BUNDLE_RESOURCE_ENCODING_INVALID",
                "Portable blueprint replay resource is not valid canonical zlib/base64.",
                details={"relative_path": relative_path},
            ) from exc
        if len(content) != declared_size:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BUNDLE_RESOURCE_SIZE_MISMATCH",
                "Portable blueprint replay resource decoded byte size is stale.",
                details={
                    "relative_path": relative_path,
                    "expected": declared_size,
                    "observed": len(content),
                },
            )
        observed_hash = "sha256:" + hashlib.sha256(content).hexdigest()
        if row["content_sha256"] != observed_hash:
            raise BlueprintError(
                "WORLD_BLUEPRINT_BUNDLE_RESOURCE_HASH_MISMATCH",
                "Portable blueprint replay resource bytes do not match the manifest.",
                details={
                    "relative_path": relative_path,
                    "expected": row["content_sha256"],
                    "observed": observed_hash,
                },
            )
        destination = (root / Path(relative_path)).resolve()
        if not destination.is_relative_to(root):
            raise BlueprintError(
                "WORLD_BLUEPRINT_BUNDLE_RESOURCE_PATH_INVALID",
                "Portable blueprint replay resource escapes materialization root.",
                details={"relative_path": relative_path},
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        resources.append(row)

    materialized_paths: set[str] = set()
    for candidate in root.rglob("*"):
        if _is_link_or_reparse(candidate):
            raise BlueprintError(
                "WORLD_BLUEPRINT_BUNDLE_MATERIALIZED_LINK_FORBIDDEN",
                "Bundle materialization produced or encountered a linked path.",
                details={
                    "relative_path": candidate.relative_to(root).as_posix()
                },
            )
        if candidate.is_file():
            materialized_paths.add(candidate.relative_to(root).as_posix())
    if materialized_paths != seen_paths:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_MATERIALIZED_DENOMINATOR_MISMATCH",
            "Materialized file denominator does not exactly match replay_resources.",
            details={
                "missing_paths": sorted(seen_paths.difference(materialized_paths)),
                "unknown_paths": sorted(materialized_paths.difference(seen_paths)),
            },
        )
    return root, resources, seen_paths


def _replay_world_blueprint_bundle(
    bundle: Mapping[str, Any] | str | Path,
    *,
    materialization_root: str | Path,
    trusted_object_census_authority_fingerprints: Iterable[str] = (),
    trusted_object_census_producer_descriptor_fingerprints: Iterable[str] = (),
) -> _VerifiedBundleReplay:
    payload, logical_fingerprint, bundle_utf8_bytes = _validate_bundle_envelope(
        bundle
    )
    manifest_value = payload["reproducibility_manifest"]
    if not isinstance(manifest_value, Mapping) or set(manifest_value) != _MANIFEST_FIELDS:
        observed_fields = set(manifest_value) if isinstance(manifest_value, Mapping) else set()
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_MANIFEST_SHAPE_INVALID",
            "Portable blueprint reproducibility manifest has an invalid shape.",
            details={
                "missing_fields": sorted(_MANIFEST_FIELDS.difference(observed_fields)),
                "unknown_fields": sorted(observed_fields.difference(_MANIFEST_FIELDS)),
            },
        )
    manifest = dict(manifest_value)
    if manifest["schema_version"] != WORLD_BLUEPRINT_BUNDLE_MANIFEST_SCHEMA_VERSION:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_MANIFEST_SCHEMA_INVALID",
            "Portable blueprint reproducibility manifest schema is not current.",
        )
    if manifest["replay_resource_codec"] != _REPLAY_RESOURCE_CODEC:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_RESOURCE_CODEC_MISMATCH",
            "Portable blueprint replay resource codec contract is not current.",
            details={
                "expected": _REPLAY_RESOURCE_CODEC,
                "observed": manifest["replay_resource_codec"],
            },
        )

    root, resources, seen_paths = _materialize_replay_resources(
        payload,
        materialization_root=materialization_root,
    )
    blueprint_payload = payload["blueprint"]
    if not isinstance(blueprint_payload, Mapping):
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_BLUEPRINT_INVALID",
            "Portable blueprint bundle does not contain a normalized blueprint.",
        )
    blueprint = WorldBlueprintContract.from_dict(blueprint_payload, source_root=root)
    cache_relative_path = _safe_relative_resource_path(
        blueprint.commitment_inventory.locator,
        owner="commitment inventory cache",
    )
    if cache_relative_path in seen_paths:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_RETIRED_CACHE_BODY_PRESENT",
            "Portable replay resources must not transport the deterministic commitment cache body.",
            details={"relative_path": cache_relative_path},
        )
    projection_value = payload["cross_artifact_projection"]
    if projection_value is not None and not isinstance(projection_value, Mapping):
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_PROJECTION_INVALID",
            "Portable blueprint projection must be an object or null.",
        )
    projection_payload = (
        dict(projection_value) if isinstance(projection_value, Mapping) else None
    )
    expected_resource_paths = set(
        _replay_resource_paths(
            blueprint,
            extra_locators=(
                (str(projection_payload.get("receipt_locator", "")),)
                if projection_payload is not None
                else ()
            ),
        )
    )
    if seen_paths != expected_resource_paths:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_RESOURCE_DENOMINATOR_MISMATCH",
            "Replay resource inventory does not equal the blueprint-required denominator.",
            details={
                "missing_paths": sorted(expected_resource_paths.difference(seen_paths)),
                "extra_paths": sorted(seen_paths.difference(expected_resource_paths)),
            },
        )

    commitment_cache = compile_behavior_commitment_inventory_cache(blueprint)
    observed_cache_fingerprint = _fingerprint(commitment_cache)
    declared_fingerprints = manifest.get("fingerprints")
    declared_cache_fingerprint = (
        declared_fingerprints.get("commitment_cache")
        if isinstance(declared_fingerprints, Mapping)
        else None
    )
    if declared_cache_fingerprint != observed_cache_fingerprint:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_COMMITMENT_CACHE_MISMATCH",
            "Isolated replay did not reproduce the declared commitment cache identity.",
            details={
                "expected": declared_cache_fingerprint,
                "observed": observed_cache_fingerprint,
            },
        )
    cache_path = (root / Path(cache_relative_path)).resolve()
    if not cache_path.is_relative_to(root) or _is_link_or_reparse(cache_path):
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_CACHE_PATH_INVALID",
            "Regenerated commitment cache path is unsafe.",
            details={"relative_path": cache_relative_path},
        )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(_canonical_json_bytes(commitment_cache) + b"\n")

    report = check_world_blueprint(
        blueprint,
        cross_artifact_projection=projection_payload,
        trusted_object_census_authority_fingerprints=(
            trusted_object_census_authority_fingerprints
        ),
        trusted_object_census_producer_descriptor_fingerprints=(
            trusted_object_census_producer_descriptor_fingerprints
        ),
    )
    expected_manifest, derived = _reproducibility_manifest(
        blueprint,
        report,
        replay_resources=resources,
        commitment_cache=commitment_cache,
        cross_artifact_projection=projection_payload,
        trusted_object_census_authority_fingerprints=(
            trusted_object_census_authority_fingerprints
        ),
        trusted_object_census_producer_descriptor_fingerprints=(
            trusted_object_census_producer_descriptor_fingerprints
        ),
    )
    mismatched_fields = sorted(
        key for key in _MANIFEST_FIELDS if manifest.get(key) != expected_manifest[key]
    )
    if mismatched_fields:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_MANIFEST_MISMATCH",
            "Bundle-only replay did not reproduce the compact manifest.",
            details={
                "mismatched_fields": mismatched_fields,
                "expected_manifest_fingerprint": _fingerprint(expected_manifest),
                "observed_manifest_fingerprint": _fingerprint(manifest),
                "expected_report_fingerprint": report.report_fingerprint,
                "observed_report_fingerprint": (
                    manifest.get("fingerprints", {}).get("qualification_report", "")
                    if isinstance(manifest.get("fingerprints"), Mapping)
                    else ""
                ),
            },
        )
    return _VerifiedBundleReplay(
        payload=payload,
        blueprint=blueprint,
        report=report,
        manifest=manifest,
        derived=derived,
        logical_bundle_fingerprint=logical_fingerprint,
        bundle_utf8_bytes=bundle_utf8_bytes,
    )


def verify_world_blueprint_bundle(
    bundle: Mapping[str, Any] | str | Path,
    *,
    materialization_root: str | Path,
    trusted_object_census_authority_fingerprints: Iterable[str] = (),
    trusted_object_census_producer_descriptor_fingerprints: Iterable[str] = (),
) -> dict[str, Any]:
    replay = _replay_world_blueprint_bundle(
        bundle,
        materialization_root=materialization_root,
        trusted_object_census_authority_fingerprints=(
            trusted_object_census_authority_fingerprints
        ),
        trusted_object_census_producer_descriptor_fingerprints=(
            trusted_object_census_producer_descriptor_fingerprints
        ),
    )
    handoff = replay.derived["handoff_qualification"]
    result_payload = {
        "schema_version": WORLD_BLUEPRINT_BUNDLE_VERIFICATION_SCHEMA_VERSION,
        "status": "PASS" if handoff["native_handoff_qualified"] else "GAP",
        **handoff,
        "logical_bundle_fingerprint": replay.logical_bundle_fingerprint,
        "blueprint_fingerprint": replay.blueprint.blueprint_fingerprint,
        "qualification_report_fingerprint": replay.report.report_fingerprint,
        "reproducibility_manifest_fingerprint": _fingerprint(replay.manifest),
        "counts": replay.manifest["counts"],
        "first_gap": replay.manifest["first_gap"],
        "component_sizes": replay.manifest["component_sizes"],
        "bundle_utf8_bytes": replay.bundle_utf8_bytes,
    }
    return {
        **result_payload,
        "verification_fingerprint": _fingerprint(result_payload),
    }


def _require_bundle_query_source(replay: _VerifiedBundleReplay) -> None:
    if replay.report.status.value == "PASS" and replay.report.native_domain_qualified:
        return
    raise BlueprintError(
        "WORLD_BLUEPRINT_QUERY_SOURCE_UNQUALIFIED",
        "Blueprint bundle queries require one current native-qualified source report.",
        details={
            "blueprint_id": replay.blueprint.blueprint_id,
            "blueprint_fingerprint": replay.blueprint.blueprint_fingerprint,
            "qualification_report_fingerprint": replay.report.report_fingerprint,
            "qualification_status": replay.report.status.value,
            "native_domain_qualified": replay.report.native_domain_qualified,
            "source_gap_ids": sorted(gap.gap_id for gap in replay.report.gaps),
        },
    )


def query_world_blueprint_bundle(
    bundle: Mapping[str, Any] | str | Path,
    *,
    materialization_root: str | Path,
    query_kind: str,
    member_id: str,
    trusted_object_census_authority_fingerprints: Iterable[str] = (),
    trusted_object_census_producer_descriptor_fingerprints: Iterable[str] = (),
) -> dict[str, Any]:
    """Return one exact portable object-DNA slice through the canonical replay owner."""

    normalized_kind = str(query_kind).strip()
    normalized_id = str(member_id).strip()
    if normalized_kind not in _BUNDLE_QUERY_KINDS:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_QUERY_KIND_UNKNOWN",
            "Portable blueprint query kind is not current.",
            details={
                "query_kind": normalized_kind,
                "allowed_query_kinds": sorted(_BUNDLE_QUERY_KINDS),
            },
        )
    if not normalized_id:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_QUERY_ID_UNKNOWN",
            "Portable blueprint query requires one stable id.",
            details={"query_kind": normalized_kind, "member_id": normalized_id},
        )
    replay = _replay_world_blueprint_bundle(
        bundle,
        materialization_root=materialization_root,
        trusted_object_census_authority_fingerprints=(
            trusted_object_census_authority_fingerprints
        ),
        trusted_object_census_producer_descriptor_fingerprints=(
            trusted_object_census_producer_descriptor_fingerprints
        ),
    )
    _require_bundle_query_source(replay)
    blueprint = replay.blueprint

    selected: dict[str, Any] | None = None
    if normalized_kind == "node":
        row = next(
            (item for item in blueprint.nodes if item.node_id == normalized_id),
            None,
        )
        selected = row.to_dict() if row is not None else None
    elif normalized_kind == "element":
        row = next(
            (item for item in blueprint.elements if item.element_id == normalized_id),
            None,
        )
        selected = row.to_dict() if row is not None else None
    elif normalized_kind == "behavior-case":
        matches: list[dict[str, Any]] = []
        for element in blueprint.elements:
            semantic = element.native_semantic
            if semantic is None or semantic.task_purpose is None:
                continue
            for case in semantic.task_purpose.behavior_cases:
                if case.case_id == normalized_id:
                    receipt = next(
                        (
                            row
                            for row in replay.report.native_execution_receipts
                            if row.get("element_id") == element.element_id
                        ),
                        None,
                    )
                    observations: list[dict[str, Any]] = []
                    if receipt is not None:
                        if case.case_kind == "admission_bad":
                            proof = receipt.get(
                                "admission_case_proof_result", {}
                            )
                        else:
                            proof = receipt.get(
                                "purpose_contract_result", {}
                            ).get("proof_receipt", {})
                        if isinstance(proof, Mapping) and isinstance(
                            proof.get("observations"), list
                        ):
                            observations = [
                                dict(row)
                                for row in proof["observations"]
                                if isinstance(row, Mapping)
                                and row.get("case_id") == case.case_id
                            ]
                    if len(observations) != 1:
                        raise BlueprintError(
                            "WORLD_BLUEPRINT_BUNDLE_CASE_PROOF_MISSING",
                            "Portable behavior-case query requires one exact replay observation.",
                            details={
                                "member_id": normalized_id,
                                "element_id": element.element_id,
                                "observation_count": len(observations),
                            },
                        )
                    matches.append(
                        {
                            "element_id": element.element_id,
                            "declaration_id": semantic.task_purpose.declaration_id,
                            "purpose_fingerprint": (
                                semantic.task_purpose.purpose_fingerprint
                            ),
                            "case": case.to_dict(),
                            "case_fingerprint": case.case_fingerprint,
                            "native_oracle_observation": observations[0],
                            "native_execution_receipt_fingerprint": receipt[
                                "receipt_fingerprint"
                            ],
                        }
                    )
        if len(matches) > 1:
            raise BlueprintError(
                "WORLD_BLUEPRINT_QUERY_ID_AMBIGUOUS",
                "Portable blueprint behavior-case id is not unique.",
                details={"member_id": normalized_id, "match_count": len(matches)},
            )
        selected = matches[0] if matches else None
    elif normalized_kind == "binding":
        row = next(
            (item for item in blueprint.bindings if item.binding_id == normalized_id),
            None,
        )
        selected = row.to_dict() if row is not None else None
    elif normalized_kind == "impact":
        selected = blueprint_impact(
            blueprint,
            blueprint_fingerprint=blueprint.blueprint_fingerprint,
            changed_ids=[normalized_id],
            trusted_object_census_authority_fingerprints=(
                trusted_object_census_authority_fingerprints
            ),
            trusted_object_census_producer_descriptor_fingerprints=(
                trusted_object_census_producer_descriptor_fingerprints
            ),
        ).to_dict()
    elif normalized_kind == "reverse":
        selected = blueprint_reverse_trace(
            blueprint,
            blueprint_fingerprint=blueprint.blueprint_fingerprint,
            target_id=normalized_id,
            trusted_object_census_authority_fingerprints=(
                trusted_object_census_authority_fingerprints
            ),
            trusted_object_census_producer_descriptor_fingerprints=(
                trusted_object_census_producer_descriptor_fingerprints
            ),
        ).to_dict()

    if selected is None:
        raise BlueprintError(
            "WORLD_BLUEPRINT_BUNDLE_QUERY_ID_UNKNOWN",
            "Portable blueprint query id is absent from the requested catalog.",
            details={"query_kind": normalized_kind, "member_id": normalized_id},
        )
    result_payload = {
        "schema_version": WORLD_BLUEPRINT_BUNDLE_QUERY_SCHEMA_VERSION,
        "status": "PASS",
        "query_kind": normalized_kind,
        "member_id": normalized_id,
        "logical_bundle_fingerprint": replay.logical_bundle_fingerprint,
        "blueprint_fingerprint": blueprint.blueprint_fingerprint,
        "qualification_report_fingerprint": replay.report.report_fingerprint,
        "object_dna_qualified": replay.report.object_dna_qualified,
        "object_census": replay.report.object_census,
        "claim_boundary": replay.report.claim_boundary,
        "slice": selected,
    }
    return {
        **result_payload,
        "result_fingerprint": _fingerprint(result_payload),
    }
