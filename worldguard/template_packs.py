"""WorldGuard-owned validating template packs for contract construction.

Templates provide deterministic scaffolding only. Guard routing, task purpose,
failure selection, native oracles, semantic execution, and predictive closure
remain owned by the existing WorldGuard runtime.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
import hashlib
import inspect
import json
from typing import Any

from .contracts import GuardContract, derive_required_guards
from .mesh import ModelMeshContract


TEMPLATE_PACK_SCHEMA_VERSION = "worldguard.template_pack_manifest.v1"
TEMPLATE_REGISTRY_SCHEMA_VERSION = "worldguard.template_pack_registry.v1"
TEMPLATE_INSTANCE_SCHEMA_VERSION = "worldguard.template_instance_receipt.v1"

GUARD_CONTRACT_KIND = "guard_contract"
MODEL_MESH_CONTRACT_KIND = "model_mesh_contract"
CONTRACT_KINDS = {GUARD_CONTRACT_KIND, MODEL_MESH_CONTRACT_KIND}

VALIDATOR_GUARD_SHAPE = "worldguard.guard_contract.shape.v1"
VALIDATOR_GUARD_ROUTES = "worldguard.guard_contract.routes.v1"
VALIDATOR_MESH_SHAPE = "worldguard.model_mesh_contract.shape.v1"
VALIDATOR_MESH_ROUTES = "worldguard.model_mesh_contract.routes.v1"

TARGET_TEMPLATE_INTERCHANGE_SCHEMA_VERSION = "worldguard.target_template_interchange.v1"
TARGET_TEMPLATE_CATALOG_SCHEMA_VERSION = "worldguard.target_template_catalog.v1"
TARGET_TEMPLATE_MANIFEST_SCHEMA_VERSION = "worldguard.target_template_manifest.v1"
WORLDGUARD_TEMPLATE_TARGET_ID = "worldguard"
WORLDGUARD_TEMPLATE_NATIVE_OWNER_ID = "worldguard.template_packs"
WORLDGUARD_TEMPLATE_ROUTE_ID = "worldguard.template_pack_builder"
WORLDGUARD_TEMPLATE_NATIVE_CHECK_ID = "check:worldguard:template-packs"
WORLDGUARD_TEMPLATE_EVIDENCE_DOMAIN_ID = "worldguard:native-validation"

WORLDGUARD_TEMPLATE_FAMILY_IDS = {
    GUARD_CONTRACT_KIND: "worldguard.guard_contract_templates",
    MODEL_MESH_CONTRACT_KIND: "worldguard.model_mesh_contract_templates",
}

TARGET_TEMPLATE_INTERCHANGE_FIELDS = frozenset(
    {
        "schema_version",
        "target_id",
        "native_owner_id",
        "family_id",
        "route_id",
        "request_fingerprint",
        "catalog",
        "applicability_results",
        "claim_boundary",
    }
)
TARGET_TEMPLATE_CATALOG_FIELDS = frozenset(
    {
        "schema_version",
        "catalog_id",
        "revision",
        "native_owner_id",
        "family_id",
        "base_template_id",
        "templates",
        "harvest_policy",
        "claim_boundary",
    }
)
TARGET_TEMPLATE_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "template_id",
        "revision",
        "template_kind",
        "native_owner_id",
        "family_id",
        "route_ids",
        "applicability_predicate_ids",
        "forbidden_condition_ids",
        "dependencies",
        "compatible_with",
        "conflicts_with",
        "dominates_template_ids",
        "composable",
        "composition_order",
        "is_validated_base",
        "field_ownership",
        "parameter_schema",
        "artifacts",
        "builder",
        "validators",
        "prompt_fragments",
        "protected_failure_ids",
        "fixtures",
        "claim_boundary",
    }
)
TARGET_APPLICABILITY_RESULT_FIELDS = frozenset(
    {
        "template_id",
        "eligible",
        "predicate_evidence_ids",
        "forbidden_clearance_evidence_ids",
        "reasons",
    }
)

PROJECTION_FAILURE_UNKNOWN_ROOT = "worldguard.template_projection.unknown_root_field"
PROJECTION_FAILURE_CANDIDATE_INVENTORY = "worldguard.template_projection.candidate_inventory_mismatch"
PROJECTION_FAILURE_WRONG_ROUTE = "worldguard.template_projection.wrong_route"
PROJECTION_FAILURE_STALE_NATIVE_IDENTITY = "worldguard.template_projection.stale_native_identity"
PROJECTION_PROTECTED_FAILURE_IDS = (
    PROJECTION_FAILURE_UNKNOWN_ROOT,
    PROJECTION_FAILURE_CANDIDATE_INVENTORY,
    PROJECTION_FAILURE_WRONG_ROUTE,
    PROJECTION_FAILURE_STALE_NATIVE_IDENTITY,
)

BUILTIN_TEMPLATE_PARAMETER_TYPES = {
    "contract_id": "string",
    "run_id": "string",
    "claim_id": "string",
    "claim_text": "string",
    "target_guards": "array",
    "requested_semantics": "array",
    "claim_atoms": "array",
    "model_id": "string",
    "model_version": "string",
    "event_inputs": "array",
    "agent_inputs": "object",
    "space_inputs": "array",
    "resource_inputs": "object",
    "causal_inputs": "object",
    "conflict_inputs": "object",
    "norms": "array",
    "facts": "array",
    "mesh_id": "string",
    "nodes": "array",
    "expected_model_node_ids": "array",
}


class TemplatePackError(ValueError):
    """Stable fail-closed error for template selection and construction."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.details = dict(details or {})


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in sorted(value.items(), key=lambda row: str(row[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_jsonable(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    return value


def content_fingerprint(value: Any) -> str:
    body = json.dumps(
        _jsonable(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def template_slot(slot_id: str) -> dict[str, str]:
    if not isinstance(slot_id, str) or not slot_id.strip():
        raise TemplatePackError("TEMPLATE_SLOT_ID_INVALID", "Template slot ids must be non-empty strings.")
    return {"$slot": slot_id}


def _is_slot(value: Any) -> bool:
    return isinstance(value, Mapping) and set(value) == {"$slot"}


def _validate_slot_shapes(value: Any, path: str = "") -> None:
    if isinstance(value, Mapping):
        if "$slot" in value:
            if not _is_slot(value) or not isinstance(value.get("$slot"), str) or not str(value["$slot"]).strip():
                raise TemplatePackError(
                    "TEMPLATE_SLOT_SHAPE_INVALID",
                    "A slot must be exactly one {'$slot': '<non-empty-id>'} object.",
                    details={"field_id": path},
                )
            return
        for key, item in value.items():
            child = f"{path}.{key}" if path else str(key)
            _validate_slot_shapes(item, child)
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            child = f"{path}[{index}]"
            _validate_slot_shapes(item, child)


def _leaf_field_ids(value: Any, path: str = "") -> tuple[str, ...]:
    if _is_slot(value):
        return (path,)
    if isinstance(value, Mapping):
        leaves: list[str] = []
        for key in sorted(value, key=str):
            child = f"{path}.{key}" if path else str(key)
            leaves.extend(_leaf_field_ids(value[key], child))
        return tuple(leaves)
    return (path,) if path else ()


def _paths_overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(f"{right}.") or right.startswith(f"{left}.")


@dataclass(frozen=True)
class TemplateFragment:
    fragment_id: str
    owned_field_ids: tuple[str, ...]
    payload: dict[str, Any]

    @classmethod
    def build(cls, fragment_id: str, payload: Mapping[str, Any]) -> "TemplateFragment":
        copied = deepcopy(dict(payload))
        return cls(
            fragment_id=fragment_id,
            owned_field_ids=tuple(sorted(_leaf_field_ids(copied))),
            payload=copied,
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TemplateFragment":
        return cls(
            fragment_id=str(data.get("fragment_id", "")),
            owned_field_ids=tuple(str(item) for item in data.get("owned_field_ids", [])),
            payload=deepcopy(dict(data.get("payload", {}))),
        )

    def validate(self) -> None:
        if not self.fragment_id:
            raise TemplatePackError("TEMPLATE_FRAGMENT_ID_MISSING", "Every template fragment needs a stable id.")
        _validate_slot_shapes(self.payload)
        declared = tuple(self.owned_field_ids)
        if len(declared) != len(set(declared)) or any(not item for item in declared):
            raise TemplatePackError(
                "TEMPLATE_FRAGMENT_FIELD_DECLARATION_INVALID",
                "Fragment field ownership ids must be non-empty and unique.",
                details={"fragment_id": self.fragment_id},
            )
        actual = tuple(sorted(_leaf_field_ids(self.payload)))
        if tuple(sorted(declared)) != actual:
            raise TemplatePackError(
                "TEMPLATE_FRAGMENT_FIELD_OWNERSHIP_MISMATCH",
                "Declared field ownership must exactly equal discovered payload leaves.",
                details={
                    "fragment_id": self.fragment_id,
                    "declared_field_ids": sorted(declared),
                    "actual_field_ids": list(actual),
                },
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fragment_id": self.fragment_id,
            "owned_field_ids": list(self.owned_field_ids),
            "payload": deepcopy(self.payload),
        }


@dataclass(frozen=True)
class TemplatePackManifest:
    pack_id: str
    pack_version: str
    contract_kind: str
    is_base: bool
    required_fact_ids: tuple[str, ...]
    excluded_fact_ids: tuple[str, ...]
    fragments: tuple[TemplateFragment, ...]
    native_validator_ids: tuple[str, ...]
    claim_boundary: str
    manifest_fingerprint: str
    schema_version: str = TEMPLATE_PACK_SCHEMA_VERSION

    @classmethod
    def build(
        cls,
        *,
        pack_id: str,
        pack_version: str,
        contract_kind: str,
        is_base: bool,
        required_fact_ids: Sequence[str] = (),
        excluded_fact_ids: Sequence[str] = (),
        fragments: Sequence[TemplateFragment],
        native_validator_ids: Sequence[str],
        claim_boundary: str,
    ) -> "TemplatePackManifest":
        manifest = cls(
            pack_id=pack_id,
            pack_version=pack_version,
            contract_kind=contract_kind,
            is_base=is_base,
            required_fact_ids=tuple(required_fact_ids),
            excluded_fact_ids=tuple(excluded_fact_ids),
            fragments=tuple(fragments),
            native_validator_ids=tuple(native_validator_ids),
            claim_boundary=claim_boundary,
            manifest_fingerprint="",
        )
        manifest = replace(manifest, manifest_fingerprint=manifest.current_fingerprint())
        manifest.validate()
        return manifest

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TemplatePackManifest":
        return cls(
            pack_id=str(data.get("pack_id", "")),
            pack_version=str(data.get("pack_version", "")),
            contract_kind=str(data.get("contract_kind", "")),
            is_base=bool(data.get("is_base", False)),
            required_fact_ids=tuple(str(item) for item in data.get("required_fact_ids", [])),
            excluded_fact_ids=tuple(str(item) for item in data.get("excluded_fact_ids", [])),
            fragments=tuple(TemplateFragment.from_dict(item) for item in data.get("fragments", [])),
            native_validator_ids=tuple(str(item) for item in data.get("native_validator_ids", [])),
            claim_boundary=str(data.get("claim_boundary", "")),
            manifest_fingerprint=str(data.get("manifest_fingerprint", "")),
            schema_version=str(data.get("schema_version", "")),
        )

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "pack_id": self.pack_id,
            "pack_version": self.pack_version,
            "contract_kind": self.contract_kind,
            "is_base": self.is_base,
            "required_fact_ids": list(self.required_fact_ids),
            "excluded_fact_ids": list(self.excluded_fact_ids),
            "fragments": [item.to_dict() for item in self.fragments],
            "native_validator_ids": list(self.native_validator_ids),
            "claim_boundary": self.claim_boundary,
        }

    def current_fingerprint(self) -> str:
        return content_fingerprint(self.fingerprint_payload())

    def validate(self) -> None:
        if self.schema_version != TEMPLATE_PACK_SCHEMA_VERSION:
            raise TemplatePackError(
                "TEMPLATE_MANIFEST_SCHEMA_INVALID",
                "Only the current WorldGuard template-pack manifest schema is accepted.",
                details={"pack_id": self.pack_id, "schema_version": self.schema_version},
            )
        if not self.pack_id or not self.pack_version or not self.claim_boundary:
            raise TemplatePackError(
                "TEMPLATE_MANIFEST_IDENTITY_INCOMPLETE",
                "Pack id, version, and claim boundary are required.",
                details={"pack_id": self.pack_id},
            )
        if self.contract_kind not in CONTRACT_KINDS:
            raise TemplatePackError(
                "TEMPLATE_CONTRACT_KIND_INVALID",
                "Template contract kind is not owned by WorldGuard.",
                details={"pack_id": self.pack_id, "contract_kind": self.contract_kind},
            )
        for field_name, values in (
            ("required_fact_ids", self.required_fact_ids),
            ("excluded_fact_ids", self.excluded_fact_ids),
            ("native_validator_ids", self.native_validator_ids),
        ):
            if len(values) != len(set(values)) or any(not item for item in values):
                raise TemplatePackError(
                    "TEMPLATE_MANIFEST_SET_INVALID",
                    "Manifest fact and validator inventories must be non-empty strings without duplicates.",
                    details={"pack_id": self.pack_id, "field": field_name},
                )
        if set(self.required_fact_ids).intersection(self.excluded_fact_ids):
            raise TemplatePackError(
                "TEMPLATE_APPLICABILITY_CONFLICT",
                "A fact cannot be both required and excluded.",
                details={"pack_id": self.pack_id},
            )
        if self.is_base and (self.required_fact_ids or self.excluded_fact_ids):
            raise TemplatePackError(
                "TEMPLATE_BASE_APPLICABILITY_INVALID",
                "A base template cannot carry candidate applicability facts.",
                details={"pack_id": self.pack_id},
            )
        if not self.fragments:
            raise TemplatePackError(
                "TEMPLATE_MANIFEST_FRAGMENTS_MISSING",
                "Every template pack needs at least one field-owning fragment.",
                details={"pack_id": self.pack_id},
            )
        fragment_ids = [item.fragment_id for item in self.fragments]
        if len(fragment_ids) != len(set(fragment_ids)):
            raise TemplatePackError(
                "TEMPLATE_FRAGMENT_ID_DUPLICATE",
                "Fragment ids must be unique inside a pack.",
                details={"pack_id": self.pack_id},
            )
        owners: list[tuple[str, str]] = []
        for fragment in self.fragments:
            fragment.validate()
            for field_id in fragment.owned_field_ids:
                conflict = next((row for row in owners if _paths_overlap(row[0], field_id)), None)
                if conflict:
                    raise TemplatePackError(
                        "TEMPLATE_FIELD_OWNERSHIP_CONFLICT",
                        "Two fragments in one pack own overlapping fields.",
                        details={
                            "pack_id": self.pack_id,
                            "field_id": field_id,
                            "existing_field_id": conflict[0],
                            "existing_owner": conflict[1],
                            "conflicting_owner": fragment.fragment_id,
                        },
                    )
                owners.append((field_id, fragment.fragment_id))
        if not self.native_validator_ids:
            raise TemplatePackError(
                "TEMPLATE_NATIVE_VALIDATOR_MISSING",
                "Every pack must bind at least one WorldGuard-native validator.",
                details={"pack_id": self.pack_id},
            )
        unknown = [item for item in self.native_validator_ids if item not in NATIVE_VALIDATORS]
        if unknown:
            raise TemplatePackError(
                "TEMPLATE_NATIVE_VALIDATOR_UNKNOWN",
                "A manifest names a validator not registered by WorldGuard.",
                details={"pack_id": self.pack_id, "validator_ids": unknown},
            )
        current = self.current_fingerprint()
        if self.manifest_fingerprint != current:
            raise TemplatePackError(
                "TEMPLATE_MANIFEST_STALE",
                "The declared manifest fingerprint does not match current content.",
                details={
                    "pack_id": self.pack_id,
                    "declared_fingerprint": self.manifest_fingerprint,
                    "current_fingerprint": current,
                },
            )

    def matches(self, fact_ids: frozenset[str]) -> bool:
        return set(self.required_fact_ids).issubset(fact_ids) and not set(
            self.excluded_fact_ids
        ).intersection(fact_ids)

    def to_dict(self) -> dict[str, Any]:
        return {**self.fingerprint_payload(), "manifest_fingerprint": self.manifest_fingerprint}


@dataclass(frozen=True)
class TemplateSelection:
    contract_kind: str
    fact_ids: tuple[str, ...]
    outcome: str
    base_pack_id: str
    candidate_pack_ids: tuple[str, ...]
    selected_pack_id: str
    registry_fingerprint: str
    selection_fingerprint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_kind": self.contract_kind,
            "fact_ids": list(self.fact_ids),
            "outcome": self.outcome,
            "base_pack_id": self.base_pack_id,
            "candidate_pack_ids": list(self.candidate_pack_ids),
            "selected_pack_id": self.selected_pack_id,
            "registry_fingerprint": self.registry_fingerprint,
            "selection_fingerprint": self.selection_fingerprint,
        }


@dataclass(frozen=True)
class TemplatePackRegistry:
    manifests: tuple[TemplatePackManifest, ...]
    registry_fingerprint: str
    schema_version: str = TEMPLATE_REGISTRY_SCHEMA_VERSION

    @classmethod
    def build(cls, manifests: Sequence[TemplatePackManifest]) -> "TemplatePackRegistry":
        registry = cls(tuple(manifests), "")
        registry = replace(registry, registry_fingerprint=registry.current_fingerprint())
        registry.validate()
        return registry

    def fingerprint_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "manifests": [
                item.to_dict() for item in sorted(self.manifests, key=lambda row: row.pack_id)
            ],
        }

    def current_fingerprint(self) -> str:
        return content_fingerprint(self.fingerprint_payload())

    def validate(self) -> None:
        if self.schema_version != TEMPLATE_REGISTRY_SCHEMA_VERSION:
            raise TemplatePackError("TEMPLATE_REGISTRY_SCHEMA_INVALID", "Template registry schema is not current.")
        if not self.manifests:
            raise TemplatePackError("TEMPLATE_REGISTRY_EMPTY", "Template registry has no manifests.")
        pack_ids = [item.pack_id for item in self.manifests]
        if len(pack_ids) != len(set(pack_ids)):
            raise TemplatePackError(
                "TEMPLATE_PACK_ID_DUPLICATE",
                "Template pack ids must be globally unique in one registry.",
            )
        for manifest in self.manifests:
            manifest.validate()
        for contract_kind in CONTRACT_KINDS:
            bases = [item.pack_id for item in self.manifests if item.contract_kind == contract_kind and item.is_base]
            if len(bases) > 1:
                raise TemplatePackError(
                    "TEMPLATE_BASE_AMBIGUOUS",
                    "A contract kind may have at most one current base template.",
                    details={"contract_kind": contract_kind, "base_pack_ids": sorted(bases)},
                )
        current = self.current_fingerprint()
        if self.registry_fingerprint != current:
            raise TemplatePackError(
                "TEMPLATE_REGISTRY_STALE",
                "Template registry fingerprint does not match current manifests.",
                details={"declared_fingerprint": self.registry_fingerprint, "current_fingerprint": current},
            )

    def by_id(self, pack_id: str) -> TemplatePackManifest:
        matches = [item for item in self.manifests if item.pack_id == pack_id]
        if len(matches) != 1:
            raise TemplatePackError(
                "TEMPLATE_PACK_NOT_FOUND",
                "Selected template pack is absent or duplicated.",
                details={"pack_id": pack_id, "match_count": len(matches)},
            )
        return matches[0]

    def select(self, contract_kind: str, fact_ids: Sequence[str] = ()) -> TemplateSelection:
        self.validate()
        if contract_kind not in CONTRACT_KINDS:
            raise TemplatePackError(
                "TEMPLATE_CONTRACT_KIND_INVALID",
                "Selection requested an unsupported contract kind.",
                details={"contract_kind": contract_kind},
            )
        normalized = tuple(sorted(set(str(item) for item in fact_ids if str(item))))
        fact_set = frozenset(normalized)
        bases = sorted(
            (item for item in self.manifests if item.contract_kind == contract_kind and item.is_base),
            key=lambda item: item.pack_id,
        )
        candidates = sorted(
            (
                item
                for item in self.manifests
                if item.contract_kind == contract_kind and not item.is_base and item.matches(fact_set)
            ),
            key=lambda item: item.pack_id,
        )
        candidate_ids = tuple(item.pack_id for item in candidates)
        base_id = bases[0].pack_id if len(bases) == 1 else ""
        if len(candidates) == 0:
            outcome = "no_match"
            selected_id = ""
        elif len(candidates) == 1:
            outcome = "selected"
            selected_id = candidates[0].pack_id
        else:
            outcome = "ambiguous"
            selected_id = ""
        payload = {
            "contract_kind": contract_kind,
            "fact_ids": list(normalized),
            "outcome": outcome,
            "base_pack_id": base_id,
            "candidate_pack_ids": list(candidate_ids),
            "selected_pack_id": selected_id,
            "registry_fingerprint": self.registry_fingerprint,
        }
        return TemplateSelection(
            contract_kind=contract_kind,
            fact_ids=normalized,
            outcome=outcome,
            base_pack_id=base_id,
            candidate_pack_ids=candidate_ids,
            selected_pack_id=selected_id,
            registry_fingerprint=self.registry_fingerprint,
            selection_fingerprint=content_fingerprint(payload),
        )


def _deep_merge(target: dict[str, Any], incoming: Mapping[str, Any], path: str = "") -> None:
    for key in sorted(incoming, key=str):
        item = incoming[key]
        child = f"{path}.{key}" if path else str(key)
        if key not in target:
            target[key] = deepcopy(item)
            continue
        if isinstance(target[key], dict) and isinstance(item, Mapping):
            _deep_merge(target[key], item, child)
            continue
        raise TemplatePackError(
            "TEMPLATE_FIELD_OWNERSHIP_CONFLICT",
            "Template composition encountered an overlapping write.",
            details={"field_id": child},
        )


@dataclass(frozen=True)
class TemplateComposition:
    contract_kind: str
    pack_ids: tuple[str, ...]
    field_owners: dict[str, str]
    payload: dict[str, Any]
    composition_fingerprint: str


def compose_template_packs(manifests: Sequence[TemplatePackManifest]) -> TemplateComposition:
    if not manifests:
        raise TemplatePackError("TEMPLATE_COMPOSITION_EMPTY", "No template packs were selected for composition.")
    for manifest in manifests:
        manifest.validate()
    kinds = {item.contract_kind for item in manifests}
    if len(kinds) != 1:
        raise TemplatePackError(
            "TEMPLATE_COMPOSITION_KIND_CONFLICT",
            "Template packs for different contract kinds cannot compose.",
            details={"contract_kinds": sorted(kinds)},
        )
    ordered = sorted(manifests, key=lambda item: (not item.is_base, item.pack_id))
    payload: dict[str, Any] = {}
    owners: dict[str, str] = {}
    for manifest in ordered:
        for fragment in sorted(manifest.fragments, key=lambda item: item.fragment_id):
            owner_id = f"{manifest.pack_id}:{fragment.fragment_id}"
            for field_id in fragment.owned_field_ids:
                conflict = next(
                    ((existing, owner) for existing, owner in owners.items() if _paths_overlap(existing, field_id)),
                    None,
                )
                if conflict:
                    raise TemplatePackError(
                        "TEMPLATE_FIELD_OWNERSHIP_CONFLICT",
                        "Selected template fragments own overlapping fields.",
                        details={
                            "field_id": field_id,
                            "existing_field_id": conflict[0],
                            "existing_owner": conflict[1],
                            "conflicting_owner": owner_id,
                        },
                    )
                owners[field_id] = owner_id
            _deep_merge(payload, fragment.payload)
    identity = {
        "contract_kind": next(iter(kinds)),
        "pack_fingerprints": [item.manifest_fingerprint for item in ordered],
        "field_owners": owners,
        "payload": payload,
    }
    return TemplateComposition(
        contract_kind=next(iter(kinds)),
        pack_ids=tuple(item.pack_id for item in ordered),
        field_owners=owners,
        payload=payload,
        composition_fingerprint=content_fingerprint(identity),
    )


def resolve_template_slots(payload: Mapping[str, Any], bindings: Mapping[str, Any]) -> dict[str, Any]:
    consumed: set[str] = set()

    def resolve(value: Any, path: str) -> Any:
        if _is_slot(value):
            slot_id = str(value["$slot"])
            if slot_id not in bindings:
                raise TemplatePackError(
                    "TEMPLATE_SLOT_MISSING",
                    "A required task-specific template slot has no binding.",
                    details={"slot_id": slot_id, "field_id": path},
                )
            consumed.add(slot_id)
            return deepcopy(bindings[slot_id])
        if isinstance(value, Mapping):
            return {str(key): resolve(item, f"{path}.{key}" if path else str(key)) for key, item in value.items()}
        if isinstance(value, list):
            return [resolve(item, f"{path}[{index}]") for index, item in enumerate(value)]
        if isinstance(value, tuple):
            return [resolve(item, f"{path}[{index}]") for index, item in enumerate(value)]
        return deepcopy(value)

    resolved = resolve(payload, "")
    unused = sorted(str(key) for key in bindings if str(key) not in consumed)
    if unused:
        raise TemplatePackError(
            "TEMPLATE_BINDING_UNUSED",
            "Every supplied template binding must resolve at least one declared slot.",
            details={"unused_slot_ids": unused},
        )
    return dict(resolved)


@dataclass(frozen=True)
class NativeTemplateValidationReceipt:
    validator_id: str
    contract_kind: str
    payload_fingerprint: str
    details: dict[str, Any]
    receipt_fingerprint: str
    status: str = "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "validator_id": self.validator_id,
            "contract_kind": self.contract_kind,
            "payload_fingerprint": self.payload_fingerprint,
            "details": deepcopy(self.details),
            "receipt_fingerprint": self.receipt_fingerprint,
            "status": self.status,
        }


def _require_guard_identity(contract: GuardContract) -> None:
    missing = []
    if not contract.contract_id:
        missing.append("contract_id")
    if not contract.run_id:
        missing.append("run_id")
    if not contract.claim.claim_id:
        missing.append("claim.claim_id")
    if not contract.world_model.model_id:
        missing.append("world_model.model_id")
    if missing:
        raise TemplatePackError(
            "TEMPLATE_NATIVE_VALIDATION_FAILED",
            "GuardContract identity is incomplete.",
            details={"missing_field_ids": missing},
        )


def _validate_guard_shape(payload: Mapping[str, Any]) -> dict[str, Any]:
    contract = GuardContract.from_dict(dict(payload))
    _require_guard_identity(contract)
    return {
        "contract_id": contract.contract_id,
        "canonical_contract_fingerprint": content_fingerprint(contract.to_dict()),
        "claim_boundary": "Canonical GuardContract construction only; no claim PASS is licensed.",
    }


def _validate_guard_routes(payload: Mapping[str, Any]) -> dict[str, Any]:
    contract = GuardContract.from_dict(dict(payload))
    _require_guard_identity(contract)
    required = tuple(derive_required_guards(contract.claim))
    missing = sorted(set(required).difference(contract.claim.target_guards))
    if missing:
        raise TemplatePackError("TEMPLATE_NATIVE_VALIDATION_FAILED", "Missing claim-derived Guard route.", details={"missing_guard_ids": missing})
    return {"contract_id": contract.contract_id, "derived_guard_ids": list(required),
            "claim_boundary": "Construction and route inventory only; no semantic execution."}


def _require_mesh_identity(mesh: ModelMeshContract) -> None:
    missing = []
    if not mesh.mesh_id:
        missing.append("mesh_id")
    if not mesh.run_id:
        missing.append("run_id")
    if missing:
        raise TemplatePackError(
            "TEMPLATE_NATIVE_VALIDATION_FAILED",
            "ModelMeshContract identity is incomplete.",
            details={"missing_field_ids": missing},
        )


def _validate_mesh_shape(payload: Mapping[str, Any]) -> dict[str, Any]:
    mesh = ModelMeshContract.from_dict(dict(payload))
    _require_mesh_identity(mesh)
    return {
        "mesh_id": mesh.mesh_id,
        "model_node_ids": [item.model_id for item in mesh.nodes],
        "canonical_mesh_fingerprint": content_fingerprint(mesh.to_dict()),
        "claim_boundary": "Canonical ModelMeshContract construction only; mesh execution remains required.",
    }


def _validate_mesh_routes(payload: Mapping[str, Any]) -> dict[str, Any]:
    mesh = ModelMeshContract.from_dict(dict(payload))
    _require_mesh_identity(mesh)
    rows = []
    for node in mesh.nodes:
        if node.contract is not None:
            rows.append({"model_id": node.model_id, **_validate_guard_routes(node.contract.to_dict())})
    return {"mesh_id": mesh.mesh_id, "embedded_route_inventories": rows,
            "claim_boundary": "Construction only; native mesh and predictive depth remain separate."}


NativeValidator = Callable[[Mapping[str, Any]], dict[str, Any]]
NATIVE_VALIDATORS: dict[str, NativeValidator] = {
    VALIDATOR_GUARD_SHAPE: _validate_guard_shape,
    VALIDATOR_GUARD_ROUTES: _validate_guard_routes,
    VALIDATOR_MESH_SHAPE: _validate_mesh_shape,
    VALIDATOR_MESH_ROUTES: _validate_mesh_routes,
}


def run_native_template_validators(
    contract_kind: str,
    payload: Mapping[str, Any],
    validator_ids: Sequence[str],
) -> tuple[NativeTemplateValidationReceipt, ...]:
    payload_fingerprint = content_fingerprint(payload)
    receipts: list[NativeTemplateValidationReceipt] = []
    for validator_id in validator_ids:
        validator = NATIVE_VALIDATORS.get(validator_id)
        if validator is None:
            raise TemplatePackError(
                "TEMPLATE_NATIVE_VALIDATOR_UNKNOWN",
                "A selected pack names an unregistered WorldGuard validator.",
                details={"validator_id": validator_id},
            )
        try:
            details = validator(payload)
        except TemplatePackError:
            raise
        except Exception as exc:
            raise TemplatePackError(
                "TEMPLATE_NATIVE_VALIDATION_FAILED",
                "A WorldGuard-native construction validator rejected the instance.",
                details={"validator_id": validator_id, "error": str(exc)},
            ) from exc
        receipt_payload = {
            "validator_id": validator_id,
            "contract_kind": contract_kind,
            "payload_fingerprint": payload_fingerprint,
            "details": details,
            "status": "pass",
        }
        receipts.append(
            NativeTemplateValidationReceipt(
                validator_id=validator_id,
                contract_kind=contract_kind,
                payload_fingerprint=payload_fingerprint,
                details=details,
                receipt_fingerprint=content_fingerprint(receipt_payload),
            )
        )
    return tuple(receipts)


@dataclass(frozen=True)
class TemplateInstanceReceipt:
    contract_kind: str
    selection: TemplateSelection
    pack_fingerprints: tuple[str, ...]
    composition_fingerprint: str
    binding_fingerprint: str
    output_fingerprint: str
    validator_receipts: tuple[NativeTemplateValidationReceipt, ...]
    instance_fingerprint: str
    claim_boundary: str
    schema_version: str = TEMPLATE_INSTANCE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "contract_kind": self.contract_kind,
            "selection": self.selection.to_dict(),
            "pack_fingerprints": list(self.pack_fingerprints),
            "composition_fingerprint": self.composition_fingerprint,
            "binding_fingerprint": self.binding_fingerprint,
            "output_fingerprint": self.output_fingerprint,
            "validator_receipts": [item.to_dict() for item in self.validator_receipts],
            "instance_fingerprint": self.instance_fingerprint,
            "claim_boundary": self.claim_boundary,
        }


@dataclass(frozen=True)
class TemplateInstance:
    data: dict[str, Any]
    receipt: TemplateInstanceReceipt

    def to_dict(self) -> dict[str, Any]:
        return {"data": deepcopy(self.data), "receipt": self.receipt.to_dict()}


def build_template_instance(
    registry: TemplatePackRegistry,
    *,
    contract_kind: str,
    fact_ids: Sequence[str] = (),
    slot_bindings: Mapping[str, Any],
) -> TemplateInstance:
    registry.validate()
    selection = registry.select(contract_kind, fact_ids)
    if selection.outcome == "ambiguous":
        raise TemplatePackError(
            "TEMPLATE_SELECTION_AMBIGUOUS",
            "More than one template candidate matches; WorldGuard will not guess.",
            details={"candidate_pack_ids": list(selection.candidate_pack_ids)},
        )
    if selection.outcome == "no_match":
        raise TemplatePackError(
            "TEMPLATE_SELECTION_NO_MATCH",
            "No current template candidate matches; WorldGuard will not activate the shared scaffold as a fallback.",
            details={"contract_kind": contract_kind, "selection": selection.to_dict()},
        )
    if not selection.base_pack_id:
        raise TemplatePackError(
            "TEMPLATE_SELECTED_BASE_MISSING",
            "The requested contract kind has no unique current base template.",
            details={"contract_kind": contract_kind, "selection": selection.to_dict()},
        )
    manifests = [registry.by_id(selection.base_pack_id)]
    if selection.selected_pack_id:
        manifests.append(registry.by_id(selection.selected_pack_id))
    composition = compose_template_packs(manifests)
    resolved = resolve_template_slots(composition.payload, slot_bindings)
    validator_ids = tuple(
        dict.fromkeys(
            validator_id
            for manifest in manifests
            for validator_id in manifest.native_validator_ids
        )
    )
    validator_receipts = run_native_template_validators(contract_kind, resolved, validator_ids)
    pack_fingerprints = tuple(item.manifest_fingerprint for item in manifests)
    binding_fingerprint = content_fingerprint(dict(slot_bindings))
    output_fingerprint = content_fingerprint(resolved)
    claim_boundary = (
        "Template-pack construction integrity only. WorldGuard semantic execution, native depth, "
        "provider readiness and any author-side maintenance closure remain separate evidence."
    )
    instance_payload = {
        "schema_version": TEMPLATE_INSTANCE_SCHEMA_VERSION,
        "contract_kind": contract_kind,
        "selection": selection.to_dict(),
        "pack_fingerprints": list(pack_fingerprints),
        "composition_fingerprint": composition.composition_fingerprint,
        "binding_fingerprint": binding_fingerprint,
        "output_fingerprint": output_fingerprint,
        "validator_receipts": [item.to_dict() for item in validator_receipts],
        "claim_boundary": claim_boundary,
    }
    receipt = TemplateInstanceReceipt(
        contract_kind=contract_kind,
        selection=selection,
        pack_fingerprints=pack_fingerprints,
        composition_fingerprint=composition.composition_fingerprint,
        binding_fingerprint=binding_fingerprint,
        output_fingerprint=output_fingerprint,
        validator_receipts=validator_receipts,
        instance_fingerprint=content_fingerprint(instance_payload),
        claim_boundary=claim_boundary,
    )
    return TemplateInstance(data=resolved, receipt=receipt)


def _sha256_identity(value: Any) -> str:
    return f"sha256:{content_fingerprint(value)}"


def _callable_content_hash(value: Callable[..., Any]) -> str:
    return _sha256_identity(
        {
            "module": value.__module__,
            "qualname": value.__qualname__,
            "source": inspect.getsource(value),
        }
    )


def _native_template_builder_content_hash() -> str:
    return _sha256_identity(
        {
            "entrypoint": "worldguard.template_packs:build_template_instance",
            "build": _callable_content_hash(build_template_instance),
            "compose": _callable_content_hash(compose_template_packs),
            "resolve": _callable_content_hash(resolve_template_slots),
        }
    )


def _native_template_validator_content_hash(validator_id: str) -> str:
    validator = NATIVE_VALIDATORS.get(validator_id)
    if validator is None:
        raise TemplatePackError(
            "TEMPLATE_NATIVE_VALIDATOR_UNKNOWN",
            "A projected manifest names an unregistered WorldGuard validator.",
            details={"validator_id": validator_id},
        )
    return _callable_content_hash(validator)


def _slot_ids(value: Any) -> tuple[str, ...]:
    if _is_slot(value):
        return (str(value["$slot"]),)
    if isinstance(value, Mapping):
        slots: list[str] = []
        for key in sorted(value, key=str):
            slots.extend(_slot_ids(value[key]))
        return tuple(slots)
    if isinstance(value, (list, tuple)):
        slots = []
        for item in value:
            slots.extend(_slot_ids(item))
        return tuple(slots)
    return ()


def _projection_parameter_schema(
    manifest: TemplatePackManifest,
    parameter_types: Mapping[str, str],
) -> dict[str, Any]:
    slot_ids = tuple(
        sorted(
            {
                slot_id
                for fragment in manifest.fragments
                for slot_id in _slot_ids(fragment.payload)
            }
        )
    )
    allowed_types = {"string", "integer", "number", "boolean", "array", "object"}
    properties: dict[str, dict[str, str]] = {}
    for slot_id in slot_ids:
        parameter_type = parameter_types.get(slot_id)
        if parameter_type not in allowed_types:
            raise TemplatePackError(
                "TEMPLATE_PROJECTION_PARAMETER_TYPE_UNDECLARED",
                "Every projected slot needs an explicit WorldGuard-authored JSON Schema type.",
                details={
                    "pack_id": manifest.pack_id,
                    "slot_id": slot_id,
                    "parameter_type": parameter_type,
                },
            )
        properties[slot_id] = {"type": parameter_type}
    return {
        "type": "object",
        "properties": properties,
        "required": list(slot_ids),
        "additionalProperties": False,
    }


def _require_exact_projection_fields(
    value: Any,
    expected: frozenset[str],
    *,
    path: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_OBJECT_REQUIRED",
            "The neutral projection field must be an object.",
            details={"path": path},
        )
    row = deepcopy(dict(value))
    unknown = sorted(set(row).difference(expected))
    if unknown:
        code = (
            "TEMPLATE_PROJECTION_ROOT_UNKNOWN_FIELD"
            if path == "$"
            else "TEMPLATE_PROJECTION_UNKNOWN_FIELD"
        )
        raise TemplatePackError(
            code,
            "The target-owned neutral projection contains an undeclared field.",
            details={"path": path, "unknown_field_ids": unknown},
        )
    missing = sorted(expected.difference(row))
    if missing:
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_FIELD_MISSING",
            "The target-owned neutral projection omits a required field.",
            details={"path": path, "missing_field_ids": missing},
        )
    return row


def _is_sha256_identity(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith("sha256:") or len(value) != 71:
        return False
    return all(character in "0123456789abcdef" for character in value.removeprefix("sha256:"))


def validate_target_template_interchange(payload: Any) -> dict[str, Any]:
    """Validate WorldGuard's exact unsealed target-template interchange.

    This validates target ownership and exact inventories only. A downstream
    authoring tool may seal additional transport identities without changing
    WorldGuard applicability or semantic meaning.
    """

    row = _require_exact_projection_fields(
        payload,
        TARGET_TEMPLATE_INTERCHANGE_FIELDS,
        path="$",
    )
    if row["schema_version"] != TARGET_TEMPLATE_INTERCHANGE_SCHEMA_VERSION:
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_SCHEMA_INVALID",
            "Only the current target-template projection schema is accepted.",
        )
    if row["target_id"] != WORLDGUARD_TEMPLATE_TARGET_ID:
        raise TemplatePackError("TEMPLATE_PROJECTION_TARGET_INVALID", "Projection target is not WorldGuard.")
    if row["native_owner_id"] != WORLDGUARD_TEMPLATE_NATIVE_OWNER_ID:
        raise TemplatePackError("TEMPLATE_PROJECTION_OWNER_INVALID", "Projection native owner is not current.")
    if row["route_id"] != WORLDGUARD_TEMPLATE_ROUTE_ID:
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_ROUTE_INVALID",
            "Projection route is not the current WorldGuard template-pack route.",
            details={"route_id": row["route_id"]},
        )
    if row["family_id"] not in set(WORLDGUARD_TEMPLATE_FAMILY_IDS.values()):
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_FAMILY_INVALID",
            "Projection family is not owned by a current WorldGuard contract kind.",
        )
    if not _is_sha256_identity(row["request_fingerprint"]):
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_REQUEST_FINGERPRINT_INVALID",
            "Projection request fingerprint must be lowercase sha256 identity.",
        )

    catalog = _require_exact_projection_fields(
        row["catalog"],
        TARGET_TEMPLATE_CATALOG_FIELDS,
        path="$.catalog",
    )
    if catalog["schema_version"] != TARGET_TEMPLATE_CATALOG_SCHEMA_VERSION:
        raise TemplatePackError("TEMPLATE_PROJECTION_CATALOG_SCHEMA_INVALID", "Catalog schema is not current.")
    if catalog["native_owner_id"] != row["native_owner_id"] or catalog["family_id"] != row["family_id"]:
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_CATALOG_IDENTITY_MISMATCH",
            "Catalog owner/family must equal the root target-owned identity.",
        )
    templates = catalog["templates"]
    if not isinstance(templates, list) or not templates:
        raise TemplatePackError("TEMPLATE_PROJECTION_CATALOG_EMPTY", "Projected catalog needs current templates.")
    template_ids: list[str] = []
    for index, value in enumerate(templates):
        manifest = _require_exact_projection_fields(
            value,
            TARGET_TEMPLATE_MANIFEST_FIELDS,
            path=f"$.catalog.templates[{index}]",
        )
        template_id = manifest.get("template_id")
        if not isinstance(template_id, str) or not template_id:
            raise TemplatePackError(
                "TEMPLATE_PROJECTION_TEMPLATE_ID_INVALID",
                "Every projected template needs a non-empty native id.",
                details={"template_index": index},
            )
        if manifest.get("schema_version") != TARGET_TEMPLATE_MANIFEST_SCHEMA_VERSION:
            raise TemplatePackError(
                "TEMPLATE_PROJECTION_MANIFEST_SCHEMA_INVALID",
                "Projected template manifest schema is not current.",
                details={"template_id": template_id},
            )
        if manifest.get("native_owner_id") != row["native_owner_id"] or manifest.get("family_id") != row["family_id"]:
            raise TemplatePackError(
                "TEMPLATE_PROJECTION_MANIFEST_IDENTITY_MISMATCH",
                "Projected template owner/family must equal the root identity.",
                details={"template_id": template_id},
            )
        if manifest.get("route_ids") != [row["route_id"]]:
            raise TemplatePackError(
                "TEMPLATE_PROJECTION_MANIFEST_ROUTE_MISMATCH",
                "Every projected template must bind only the current native route.",
                details={"template_id": template_id},
            )
        template_ids.append(template_id)
    if len(template_ids) != len(set(template_ids)):
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_CANDIDATE_INVENTORY_MISMATCH",
            "Projected native template ids must be unique.",
        )

    raw_results = row["applicability_results"]
    if not isinstance(raw_results, list):
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_APPLICABILITY_INVALID",
            "Applicability results must be an array.",
        )
    result_ids: list[str] = []
    for index, value in enumerate(raw_results):
        result = _require_exact_projection_fields(
            value,
            TARGET_APPLICABILITY_RESULT_FIELDS,
            path=f"$.applicability_results[{index}]",
        )
        if not isinstance(result.get("template_id"), str) or not result["template_id"]:
            raise TemplatePackError(
                "TEMPLATE_PROJECTION_APPLICABILITY_TEMPLATE_INVALID",
                "Each applicability row needs one native template id.",
            )
        if not isinstance(result.get("eligible"), bool):
            raise TemplatePackError(
                "TEMPLATE_PROJECTION_APPLICABILITY_ELIGIBLE_INVALID",
                "Target-owned applicability must be an exact boolean.",
            )
        for field_name in (
            "predicate_evidence_ids",
            "forbidden_clearance_evidence_ids",
            "reasons",
        ):
            values = result.get(field_name)
            if (
                not isinstance(values, list)
                or any(not isinstance(item, str) or not item for item in values)
                or len(values) != len(set(values))
            ):
                raise TemplatePackError(
                    "TEMPLATE_PROJECTION_APPLICABILITY_LIST_INVALID",
                    "Applicability evidence and reason inventories must be unique string arrays.",
                    details={"template_id": result["template_id"], "field": field_name},
                )
        result_ids.append(result["template_id"])
    if len(result_ids) != len(set(result_ids)) or set(result_ids) != set(template_ids):
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_CANDIDATE_INVENTORY_MISMATCH",
            "Applicability results must equal the native catalog inventory exactly once.",
            details={
                "catalog_template_ids": sorted(template_ids),
                "applicability_template_ids": sorted(result_ids),
            },
        )
    return row


def _project_target_template_manifest(
    manifest: TemplatePackManifest,
    *,
    family_id: str,
    base_pack_id: str,
    family_manifests: Sequence[TemplatePackManifest],
    parameter_types: Mapping[str, str],
    builder_content_hash: str,
) -> dict[str, Any]:
    candidate_ids = sorted(item.pack_id for item in family_manifests if not item.is_base)
    if manifest.is_base:
        predicate_ids = [f"worldguard.native-selection.base-no-match:{manifest.contract_kind}"]
        dependencies: list[str] = []
        compatible_with = candidate_ids
        conflicts_with: list[str] = []
    else:
        predicate_ids = [
            f"worldguard.native-applicability.required-fact:{fact_id}"
            for fact_id in manifest.required_fact_ids
        ] or [f"worldguard.native-applicability.match:{manifest.pack_id}"]
        dependencies = [base_pack_id] if base_pack_id else []
        compatible_with = [base_pack_id] if base_pack_id else []
        conflicts_with = [item for item in candidate_ids if item != manifest.pack_id]
    forbidden_ids = [
        f"worldguard.native-applicability.excluded-fact:{fact_id}"
        for fact_id in manifest.excluded_fact_ids
    ]
    field_ownership = sorted(
        {
            field_id
            for fragment in manifest.fragments
            for field_id in fragment.owned_field_ids
        }
    )
    fixtures_by_failure = {
        PROJECTION_FAILURE_UNKNOWN_ROOT: [
            f"worldguard.fixture.projection.unknown-root:{manifest.pack_id}"
        ],
        PROJECTION_FAILURE_CANDIDATE_INVENTORY: [
            f"worldguard.fixture.projection.candidate-inventory:{manifest.pack_id}"
        ],
        PROJECTION_FAILURE_WRONG_ROUTE: [
            f"worldguard.fixture.projection.wrong-route:{manifest.pack_id}"
        ],
        PROJECTION_FAILURE_STALE_NATIVE_IDENTITY: [
            f"worldguard.fixture.projection.stale-native-identity:{manifest.pack_id}"
        ],
    }
    return {
        "schema_version": TARGET_TEMPLATE_MANIFEST_SCHEMA_VERSION,
        "template_id": manifest.pack_id,
        "revision": manifest.pack_version,
        "template_kind": "base" if manifest.is_base else "profile",
        "native_owner_id": WORLDGUARD_TEMPLATE_NATIVE_OWNER_ID,
        "family_id": family_id,
        "route_ids": [WORLDGUARD_TEMPLATE_ROUTE_ID],
        "applicability_predicate_ids": predicate_ids,
        "forbidden_condition_ids": forbidden_ids,
        "dependencies": dependencies,
        "compatible_with": compatible_with,
        "conflicts_with": conflicts_with,
        "dominates_template_ids": [],
        "composable": not manifest.is_base,
        "composition_order": 0 if manifest.is_base else 1,
        "is_validated_base": manifest.is_base,
        "field_ownership": field_ownership,
        "parameter_schema": _projection_parameter_schema(manifest, parameter_types),
        "artifacts": [
            {
                "artifact_id": f"artifact:{manifest.pack_id}",
                "path_template": (
                    f"generated/worldguard/{manifest.contract_kind}/{manifest.pack_id}/"
                    "${request_fingerprint}.json"
                ),
                "content_template_hash": f"sha256:{manifest.manifest_fingerprint}",
            }
        ],
        "builder": {
            "builder_id": "worldguard.template_packs.build_template_instance",
            "entrypoint": "worldguard.template_packs:build_template_instance",
            "content_hash": builder_content_hash,
        },
        "validators": [
            {
                "validator_id": validator_id,
                "check_id": WORLDGUARD_TEMPLATE_NATIVE_CHECK_ID,
                "evidence_domain": WORLDGUARD_TEMPLATE_EVIDENCE_DOMAIN_ID,
                "content_hash": _native_template_validator_content_hash(validator_id),
            }
            for validator_id in manifest.native_validator_ids
        ],
        "prompt_fragments": [],
        "protected_failure_ids": list(PROJECTION_PROTECTED_FAILURE_IDS),
        "fixtures": {
            "known_good_ids": [f"worldguard.fixture.projection.good:{manifest.pack_id}"],
            "known_bad_by_failure": fixtures_by_failure,
            "ambiguity_ids": [f"worldguard.fixture.projection.ambiguity:{family_id}"],
            "stale_ids": [
                f"worldguard.fixture.projection.stale-native-identity:{manifest.pack_id}"
            ],
        },
        "claim_boundary": (
            f"{manifest.claim_boundary} This unsealed neutral projection preserves WorldGuard's "
            "native applicability, builder, validator, and semantic authority."
        ),
    }


def _project_target_applicability_result(
    manifest: TemplatePackManifest,
    *,
    selection: TemplateSelection,
    fact_set: frozenset[str],
) -> dict[str, Any]:
    if manifest.is_base:
        eligible = False
        predicate_evidence: list[str] = []
        forbidden_evidence: list[str] = []
        reasons = ["worldguard.shared-scaffold-is-not-a-selectable-fallback"]
    else:
        matched_by_manifest = manifest.matches(fact_set)
        matched_by_selection = manifest.pack_id in set(selection.candidate_pack_ids)
        if matched_by_manifest != matched_by_selection:
            raise TemplatePackError(
                "TEMPLATE_PROJECTION_CANDIDATE_INVENTORY_MISMATCH",
                "Native manifest applicability and native selection candidate inventory disagree.",
                details={
                    "pack_id": manifest.pack_id,
                    "manifest_match": matched_by_manifest,
                    "selection_match": matched_by_selection,
                },
            )
        eligible = matched_by_selection
        predicate_evidence = []
        forbidden_evidence = []
        reasons: list[str] = []
        if eligible:
            predicate_evidence = [
                f"worldguard.fact-present:{fact_id}"
                for fact_id in manifest.required_fact_ids
            ] or [f"worldguard.native-selection:{selection.selection_fingerprint}:matched"]
            forbidden_evidence = [
                f"worldguard.fact-absent:{fact_id}"
                for fact_id in manifest.excluded_fact_ids
            ]
        else:
            reasons.extend(
                f"worldguard.required-fact-missing:{fact_id}"
                for fact_id in manifest.required_fact_ids
                if fact_id not in fact_set
            )
            reasons.extend(
                f"worldguard.excluded-fact-present:{fact_id}"
                for fact_id in manifest.excluded_fact_ids
                if fact_id in fact_set
            )
            if not reasons:
                reasons.append("worldguard.native-candidate-not-matched")
    return {
        "template_id": manifest.pack_id,
        "eligible": eligible,
        "predicate_evidence_ids": predicate_evidence,
        "forbidden_clearance_evidence_ids": forbidden_evidence,
        "reasons": reasons,
    }


def build_target_template_interchange(
    registry: TemplatePackRegistry,
    *,
    contract_kind: str,
    native_registry_fingerprint: str,
    fact_ids: Sequence[str] = (),
    route_id: str = WORLDGUARD_TEMPLATE_ROUTE_ID,
    parameter_types: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Project native templates into WorldGuard's neutral interchange shape.

    WorldGuard remains the sole route/applicability/semantic owner. The return
    value deliberately omits central `manifest_digest` and `catalog_digest`;
    a downstream authoring tool may validate and seal those transport identities.
    """

    registry.validate()
    if route_id != WORLDGUARD_TEMPLATE_ROUTE_ID:
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_ROUTE_INVALID",
            "Only the current WorldGuard template-pack route may emit this projection.",
            details={"route_id": route_id, "expected_route_id": WORLDGUARD_TEMPLATE_ROUTE_ID},
        )
    if native_registry_fingerprint != registry.registry_fingerprint:
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_NATIVE_IDENTITY_STALE",
            "The caller-supplied native registry identity is not current.",
            details={
                "supplied_registry_fingerprint": native_registry_fingerprint,
                "current_registry_fingerprint": registry.registry_fingerprint,
            },
        )
    selection = registry.select(contract_kind, fact_ids)
    family_id = WORLDGUARD_TEMPLATE_FAMILY_IDS[contract_kind]
    family_manifests = tuple(
        sorted(
            (item for item in registry.manifests if item.contract_kind == contract_kind),
            key=lambda item: item.pack_id,
        )
    )
    if not family_manifests:
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_CATALOG_EMPTY",
            "The current native registry has no manifests for the requested contract kind.",
            details={"contract_kind": contract_kind},
        )
    base_ids = [item.pack_id for item in family_manifests if item.is_base]
    base_pack_id = base_ids[0] if len(base_ids) == 1 else ""
    effective_parameter_types = {
        **BUILTIN_TEMPLATE_PARAMETER_TYPES,
        **dict(parameter_types or {}),
    }
    builder_content_hash = _native_template_builder_content_hash()
    templates = [
        _project_target_template_manifest(
            manifest,
            family_id=family_id,
            base_pack_id=base_pack_id,
            family_manifests=family_manifests,
            parameter_types=effective_parameter_types,
            builder_content_hash=builder_content_hash,
        )
        for manifest in family_manifests
    ]
    fact_set = frozenset(selection.fact_ids)
    applicability_results = [
        _project_target_applicability_result(
            manifest,
            selection=selection,
            fact_set=fact_set,
        )
        for manifest in family_manifests
    ]
    native_ids = [item.pack_id for item in family_manifests]
    projected_ids = [item["template_id"] for item in templates]
    applicability_ids = [item["template_id"] for item in applicability_results]
    if projected_ids != native_ids or applicability_ids != native_ids:
        raise TemplatePackError(
            "TEMPLATE_PROJECTION_CANDIDATE_INVENTORY_MISMATCH",
            "Projection catalog and applicability rows must equal the native family inventory.",
            details={
                "native_template_ids": native_ids,
                "projected_template_ids": projected_ids,
                "applicability_template_ids": applicability_ids,
            },
        )
    request_fingerprint = _sha256_identity(
        {
            "schema_version": TARGET_TEMPLATE_INTERCHANGE_SCHEMA_VERSION,
            "target_id": WORLDGUARD_TEMPLATE_TARGET_ID,
            "native_owner_id": WORLDGUARD_TEMPLATE_NATIVE_OWNER_ID,
            "family_id": family_id,
            "route_id": route_id,
            "contract_kind": contract_kind,
            "fact_ids": list(selection.fact_ids),
            "native_registry_fingerprint": registry.registry_fingerprint,
            "native_selection_fingerprint": selection.selection_fingerprint,
        }
    )
    claim_boundary = (
        "WorldGuard owns this route, native candidate inventory, applicability, manifests, "
        "builder, validators, fixtures, and semantic meaning. A downstream authoring tool "
        "may seal transport identities but cannot infer, rank, or replace them."
    )
    projection = {
        "schema_version": TARGET_TEMPLATE_INTERCHANGE_SCHEMA_VERSION,
        "target_id": WORLDGUARD_TEMPLATE_TARGET_ID,
        "native_owner_id": WORLDGUARD_TEMPLATE_NATIVE_OWNER_ID,
        "family_id": family_id,
        "route_id": route_id,
        "request_fingerprint": request_fingerprint,
        "catalog": {
            "schema_version": TARGET_TEMPLATE_CATALOG_SCHEMA_VERSION,
            "catalog_id": f"worldguard.template_catalog.{contract_kind}",
            "revision": registry.registry_fingerprint,
            "native_owner_id": WORLDGUARD_TEMPLATE_NATIVE_OWNER_ID,
            "family_id": family_id,
            "base_template_id": base_pack_id,
            "templates": templates,
            "harvest_policy": {
                "required": True,
                "allowed_dispositions": ["reused", "created", "not_harvestable"],
            },
            "claim_boundary": (
                "Unsealed WorldGuard-owned neutral catalog for one exact contract kind; "
                "downstream transport digests are outside WorldGuard semantic authority."
            ),
        },
        "applicability_results": applicability_results,
        "claim_boundary": claim_boundary,
    }
    return validate_target_template_interchange(projection)


def _manifest(
    *,
    pack_id: str,
    contract_kind: str,
    is_base: bool,
    payload: Mapping[str, Any],
    required_fact_ids: Sequence[str] = (),
    validator_ids: Sequence[str],
) -> TemplatePackManifest:
    return TemplatePackManifest.build(
        pack_id=pack_id,
        pack_version="1",
        contract_kind=contract_kind,
        is_base=is_base,
        required_fact_ids=required_fact_ids,
        fragments=(TemplateFragment.build(f"fragment:{pack_id}", payload),),
        native_validator_ids=validator_ids,
        claim_boundary=(
            "Reusable WorldGuard construction scaffold only; task purpose, native oracle evidence, "
            "semantic execution, and predictive closure are not supplied by this pack."
        ),
    )


def builtin_template_registry() -> TemplatePackRegistry:
    guard_validators = (VALIDATOR_GUARD_SHAPE, VALIDATOR_GUARD_ROUTES)
    mesh_validators = (VALIDATOR_MESH_SHAPE, VALIDATOR_MESH_ROUTES)
    manifests: list[TemplatePackManifest] = [
        _manifest(
            pack_id="worldguard.guard-contract.base",
            contract_kind=GUARD_CONTRACT_KIND,
            is_base=True,
            validator_ids=guard_validators,
            payload={
                "contract_id": template_slot("contract_id"),
                "schema_version": "worldguard.contract.v1",
                "run_id": template_slot("run_id"),
                "claim": {
                    "claim_id": template_slot("claim_id"),
                    "text": template_slot("claim_text"),
                    "target_guards": template_slot("target_guards"),
                    "requested_semantics": template_slot("requested_semantics"),
                    "atoms": template_slot("claim_atoms"),
                },
                "world_model": {
                    "model_id": template_slot("model_id"),
                    "model_version": template_slot("model_version"),
                    "entities": {},
                    "relations": {},
                    "assumptions": [],
                    "scope_limits": [],
                },
                "dependencies": {"upstream_results": [], "read_only": True},
                "output_requirements": {
                    "require_ledgers": True,
                    "require_counterexample_for_non_pass": True,
                    "allowed_status": ["PASS", "FAIL", "GAP", "BOUNDARY_EXCEEDED"],
                },
            },
        ),
        _manifest(
            pack_id="worldguard.model-mesh.base",
            contract_kind=MODEL_MESH_CONTRACT_KIND,
            is_base=True,
            validator_ids=mesh_validators,
            payload={
                "mesh_id": template_slot("mesh_id"),
                "schema_version": "worldguard.model_mesh.v1",
                "run_id": template_slot("run_id"),
                "nodes": template_slot("nodes"),
                "edges": [],
                "snapshots": [],
                "provider_availability": {},
                "semantic_coverage": {
                    "expected_model_node_ids": template_slot("expected_model_node_ids"),
                    "excluded_model_nodes": [],
                    "expected_semantic_child_ids": [],
                    "scenario_ids": [],
                    "holdout_scenario_ids": [],
                    "state_ids": [],
                    "transition_ids": [],
                    "branch_ids": [],
                    "perturbation_ids": [],
                    "intervention_ids": [],
                    "counterfactual_ids": [],
                    "horizon": {},
                    "timepoint_ids": [],
                    "time_strata": {},
                    "minimum_timepoint_count": 0,
                    "minimum_timepoint_coverage": 0.0,
                    "per_model_node": {},
                },
            },
        ),
    ]
    guard_inputs = {
        "EventGuard": ("events", "event_inputs"),
        "AgentGuard": ("beliefs", "agent_inputs"),
        "SpaceGuard": ("spatial_relations", "space_inputs"),
        "ResourceGuard": ("resources", "resource_inputs"),
        "CausalGuard": ("causal_model", "causal_inputs"),
        "ConflictGuard": ("game_model", "conflict_inputs"),
    }
    for guard, (field_id, slot_id) in guard_inputs.items():
        manifests.append(
            _manifest(
                pack_id=f"worldguard.guard-contract.{guard.removesuffix('Guard').lower()}",
                contract_kind=GUARD_CONTRACT_KIND,
                is_base=False,
                required_fact_ids=(f"guard:{guard}",),
                validator_ids=guard_validators,
                payload={"inputs": {field_id: template_slot(slot_id)}},
            )
        )
    manifests.append(
        _manifest(
            pack_id="worldguard.guard-contract.norm",
            contract_kind=GUARD_CONTRACT_KIND,
            is_base=False,
            required_fact_ids=("guard:NormGuard",),
            validator_ids=guard_validators,
            payload={
                "inputs": {
                    "norms": template_slot("norms"),
                    "facts": template_slot("facts"),
                }
            },
        )
    )
    for profile in ("bounded", "predictive"):
        manifests.append(
            _manifest(
                pack_id=f"worldguard.model-mesh.{profile}",
                contract_kind=MODEL_MESH_CONTRACT_KIND,
                is_base=False,
                required_fact_ids=(f"coverage:{profile}",),
                validator_ids=mesh_validators,
                payload={"semantic_coverage": {"profile": profile}},
            )
        )
    return TemplatePackRegistry.build(manifests)

def run_template_pack_contract() -> dict[str, Any]:
    """Run WorldGuard's target-native template-pack construction oracle."""

    observations: list[dict[str, Any]] = []

    def observe(case_id: str, expected: Any, observed: Any) -> None:
        observations.append(
            {
                "case_id": case_id,
                "expected": expected,
                "observed": observed,
                "passed": observed == expected,
            }
        )

    registry = builtin_template_registry()
    observe("selection:zero", "no_match", registry.select(GUARD_CONTRACT_KIND).outcome)
    observe(
        "selection:one",
        "selected",
        registry.select(GUARD_CONTRACT_KIND, ("guard:EventGuard",)).outcome,
    )
    observe(
        "selection:many",
        "ambiguous",
        registry.select(
            GUARD_CONTRACT_KIND,
            ("guard:EventGuard", "guard:CausalGuard"),
        ).outcome,
    )

    projection = build_target_template_interchange(
        registry,
        contract_kind=GUARD_CONTRACT_KIND,
        fact_ids=("guard:EventGuard",),
        native_registry_fingerprint=registry.registry_fingerprint,
    )
    observe(
        "projection:good-schema",
        TARGET_TEMPLATE_INTERCHANGE_SCHEMA_VERSION,
        projection["schema_version"],
    )
    native_guard_ids = sorted(
        item.pack_id
        for item in registry.manifests
        if item.contract_kind == GUARD_CONTRACT_KIND
    )
    projection_catalog_ids = [
        item["template_id"] for item in projection["catalog"]["templates"]
    ]
    projection_result_ids = [
        item["template_id"] for item in projection["applicability_results"]
    ]
    observe(
        "projection:candidate-inventory",
        native_guard_ids,
        projection_catalog_ids if projection_catalog_ids == projection_result_ids else [],
    )

    unknown_root = deepcopy(projection)
    unknown_root["family_guess"] = "forbidden"
    try:
        validate_target_template_interchange(unknown_root)
        unknown_root_code = "<accepted>"
    except TemplatePackError as exc:
        unknown_root_code = exc.code
    observe(
        "projection:unknown-root",
        "TEMPLATE_PROJECTION_ROOT_UNKNOWN_FIELD",
        unknown_root_code,
    )

    try:
        build_target_template_interchange(
            registry,
            contract_kind=GUARD_CONTRACT_KIND,
            native_registry_fingerprint=registry.registry_fingerprint,
            route_id="worldguard.not-the-template-route",
        )
        wrong_route_code = "<accepted>"
    except TemplatePackError as exc:
        wrong_route_code = exc.code
    observe(
        "projection:wrong-route",
        "TEMPLATE_PROJECTION_ROUTE_INVALID",
        wrong_route_code,
    )

    try:
        build_target_template_interchange(
            registry,
            contract_kind=GUARD_CONTRACT_KIND,
            native_registry_fingerprint="0" * 64,
        )
        stale_native_identity_code = "<accepted>"
    except TemplatePackError as exc:
        stale_native_identity_code = exc.code
    observe(
        "projection:stale-native-identity",
        "TEMPLATE_PROJECTION_NATIVE_IDENTITY_STALE",
        stale_native_identity_code,
    )

    try:
        build_template_instance(
            registry,
            contract_kind=GUARD_CONTRACT_KIND,
            slot_bindings={},
        )
        no_match_code = "<accepted>"
    except TemplatePackError as exc:
        no_match_code = exc.code
    observe("native:guard-no-match", "TEMPLATE_SELECTION_NO_MATCH", no_match_code)

    mesh_instance = build_template_instance(
        registry,
        contract_kind=MODEL_MESH_CONTRACT_KIND,
        fact_ids=("coverage:bounded",),
        slot_bindings={
            "mesh_id": "template-oracle:mesh",
            "run_id": "template-oracle:mesh-run",
            "nodes": [],
            "expected_model_node_ids": [],
        },
    )
    observe("native:model-mesh", 2, len(mesh_instance.receipt.validator_receipts))

    stale_data = registry.by_id("worldguard.guard-contract.event").to_dict()
    stale_data["pack_version"] = "stale"
    try:
        TemplatePackManifest.from_dict(stale_data).validate()
        stale_code = "<accepted>"
    except TemplatePackError as exc:
        stale_code = exc.code
    observe("counterexample:stale", "TEMPLATE_MANIFEST_STALE", stale_code)

    conflict_base = TemplatePackManifest.build(
        pack_id="template-oracle.conflict.base",
        pack_version="1",
        contract_kind=GUARD_CONTRACT_KIND,
        is_base=True,
        fragments=(
            TemplateFragment.build(
                "fragment:conflict-base",
                {"contract_id": template_slot("contract_id")},
            ),
        ),
        native_validator_ids=(VALIDATOR_GUARD_SHAPE,),
        claim_boundary="template oracle conflict base",
    )
    conflict_candidate = TemplatePackManifest.build(
        pack_id="template-oracle.conflict.candidate",
        pack_version="1",
        contract_kind=GUARD_CONTRACT_KIND,
        is_base=False,
        required_fact_ids=("conflict",),
        fragments=(
            TemplateFragment.build(
                "fragment:conflict-candidate",
                {"contract_id": "overlap"},
            ),
        ),
        native_validator_ids=(VALIDATOR_GUARD_SHAPE,),
        claim_boundary="template oracle conflict candidate",
    )
    try:
        compose_template_packs((conflict_base, conflict_candidate))
        conflict_code = "<accepted>"
    except TemplatePackError as exc:
        conflict_code = exc.code
    observe(
        "counterexample:field-conflict",
        "TEMPLATE_FIELD_OWNERSHIP_CONFLICT",
        conflict_code,
    )

    current_base = registry.by_id("worldguard.guard-contract.base")
    unknown = replace(
        current_base,
        native_validator_ids=("worldguard.template-validator.unknown",),
        manifest_fingerprint="",
    )
    unknown = replace(unknown, manifest_fingerprint=unknown.current_fingerprint())
    try:
        unknown.validate()
        unknown_code = "<accepted>"
    except TemplatePackError as exc:
        unknown_code = exc.code
    observe(
        "counterexample:unknown-validator",
        "TEMPLATE_NATIVE_VALIDATOR_UNKNOWN",
        unknown_code,
    )

    passed = all(item["passed"] for item in observations)
    return {
        "schema_version": "worldguard.template_pack_native_check.v1",
        "ok": passed,
        "manifest_count": len(registry.manifests),
        "base_pack_count": sum(1 for item in registry.manifests if item.is_base),
        "candidate_pack_count": sum(1 for item in registry.manifests if not item.is_base),
        "registry_fingerprint": registry.registry_fingerprint,
        "projection_schema_version": TARGET_TEMPLATE_INTERCHANGE_SCHEMA_VERSION,
        "projection_root_fields": sorted(TARGET_TEMPLATE_INTERCHANGE_FIELDS),
        "observations": observations,
        "failures": [item for item in observations if not item["passed"]],
        "claim_boundary": (
            "This native check proves WorldGuard template selection, construction validation, "
            "and counterexample reactions only. It does not prove a target world claim, semantic "
            "execution, predictive depth, installation, release, or future AI behavior."
        ),
    }
