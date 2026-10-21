"""WorldGuard-owned validating template packs for contract construction.

Templates provide deterministic scaffolding only. Guard routing, native semantics,
behavior evidence, and predictive closure
remain owned by the existing WorldGuard runtime.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
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







class TemplatePackError(ValueError):
    """Stable fail-closed error for template selection and construction."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.details = dict(details or {})


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
        )
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
            schema_version=str(data.get("schema_version", "")),
        )

    def to_dict(self) -> dict[str, Any]:
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

    def matches(self, fact_ids: frozenset[str]) -> bool:
        return set(self.required_fact_ids).issubset(fact_ids) and not set(
            self.excluded_fact_ids
        ).intersection(fact_ids)



@dataclass(frozen=True)
class TemplateSelection:
    contract_kind: str
    fact_ids: tuple[str, ...]
    outcome: str
    base_pack_id: str
    candidate_pack_ids: tuple[str, ...]
    selected_pack_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_kind": self.contract_kind,
            "fact_ids": list(self.fact_ids),
            "outcome": self.outcome,
            "base_pack_id": self.base_pack_id,
            "candidate_pack_ids": list(self.candidate_pack_ids),
            "selected_pack_id": self.selected_pack_id,
        }


@dataclass(frozen=True)
class TemplatePackRegistry:
    manifests: tuple[TemplatePackManifest, ...]
    schema_version: str = TEMPLATE_REGISTRY_SCHEMA_VERSION

    @classmethod
    def build(cls, manifests: Sequence[TemplatePackManifest]) -> "TemplatePackRegistry":
        registry = cls(tuple(manifests))
        registry.validate()
        return registry



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
        return TemplateSelection(
            contract_kind=contract_kind,
            fact_ids=normalized,
            outcome=outcome,
            base_pack_id=base_id,
            candidate_pack_ids=candidate_ids,
            selected_pack_id=selected_id,
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
    return TemplateComposition(
        contract_kind=next(iter(kinds)),
        pack_ids=tuple(item.pack_id for item in ordered),
        field_owners=owners,
        payload=payload,
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
    details: dict[str, Any]
    status: str = "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "validator_id": self.validator_id,
            "contract_kind": self.contract_kind,
            "details": deepcopy(self.details),
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
        receipts.append(
            NativeTemplateValidationReceipt(
                validator_id=validator_id,
                contract_kind=contract_kind,
                details=details,
            )
        )
    return tuple(receipts)


@dataclass(frozen=True)
class TemplateInstanceReceipt:
    contract_kind: str
    selection: TemplateSelection
    pack_ids: tuple[str, ...]
    validator_receipts: tuple[NativeTemplateValidationReceipt, ...]
    claim_boundary: str
    schema_version: str = TEMPLATE_INSTANCE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "contract_kind": self.contract_kind,
            "selection": self.selection.to_dict(),
            "pack_ids": list(self.pack_ids),
            "validator_receipts": [item.to_dict() for item in self.validator_receipts],
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
    receipt = TemplateInstanceReceipt(
        contract_kind=contract_kind,
        selection=selection,
        pack_ids=composition.pack_ids,
        validator_receipts=validator_receipts,
        claim_boundary=(
            "Template construction only. Run the built contract with run_worldguard or "
            "run_model_mesh for any verdict."
        ),
    )
    return TemplateInstance(data=resolved, receipt=receipt)


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
            "Reusable WorldGuard construction scaffold only; behavior evidence, "
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
                    "asserts": template_slot("claim_asserts"),
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
