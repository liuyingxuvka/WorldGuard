"""Independent completeness authority for external-object WorldBlueprint DNA.

The candidate blueprint is deliberately not an authority producer. A target
owner, requirements channel, or another independently owned adapter freezes the
object census and signs it outside this package. Runtime WorldGuard validates
the portable record and compares the candidate with it, but contains no private
key and grants no producer implicit trust.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any


EXTERNAL_OBJECT_CENSUS_SCHEMA = "worldguard.external_object_census_authority.v2"
EXTERNAL_OBJECT_CENSUS_SIGNATURE_SCHEMA = (
    "worldguard.external_object_census_authority_signature.v2"
)
EXTERNAL_OBJECT_CENSUS_SOURCE_SCHEMA = (
    "worldguard.external_object_census_source.v1"
)
EXTERNAL_OBJECT_CENSUS_DISCOVERY_RECEIPT_SCHEMA = (
    "worldguard.external_object_census_discovery_receipt.v1"
)
OBJECT_CLAIM_KINDS = frozenset(
    {"integrated_target", "oracle_carrying_capability_fixture"}
)
OBJECT_DISCOVERY_MODES = frozenset(
    {"independent_raw_target_request", "candidate_consistency"}
)
OBJECT_CENSUS_INPUT_KINDS = (
    "request_contract",
    "target_material",
    "target_object_census_source",
    "target_semantic_authority",
)
OBJECT_SUPPORT_ROLES = frozenset(
    {"target_material", "evidence", "test_check", "native_result"}
)
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")


class ExternalObjectCensusError(ValueError):
    """One exact current-format external-object census failure."""


def _canonical(value: object) -> object:
    return json.loads(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    )


def _digest(value: object) -> str:
    body = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _mapping(value: object, fields: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ExternalObjectCensusError(f"{label} is not exact-current")
    return value


def _rows(value: object, label: str) -> Sequence[Mapping[str, object]]:
    if not isinstance(value, list) or any(not isinstance(row, Mapping) for row in value):
        raise ExternalObjectCensusError(f"{label} must be an array of objects")
    return value  # type: ignore[return-value]


def _text(value: object, label: str) -> str:
    result = str(value or "").strip()
    if not result:
        raise ExternalObjectCensusError(f"{label} is required")
    return result


def _ids(value: object, label: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ExternalObjectCensusError(f"{label} must be an array")
    result = tuple(_text(item, label) for item in value)
    if result != tuple(sorted(result)):
        raise ExternalObjectCensusError(f"{label} must be canonically ordered")
    if len(result) != len(set(result)):
        raise ExternalObjectCensusError(f"{label} must contain unique ids")
    if not result and not allow_empty:
        raise ExternalObjectCensusError(f"{label} must not be empty")
    return result


def _fingerprint(value: object, label: str) -> str:
    result = _text(value, label)
    if not _SHA256.fullmatch(result):
        raise ExternalObjectCensusError(f"{label} must be an exact sha256 fingerprint")
    return result


def external_object_census_signing_payload(
    *,
    authority_fingerprint: str,
    producer_descriptor_fingerprint: str,
    signing_key_id: str,
) -> bytes:
    """Return the only current bytes an independent census producer signs."""

    material = {
        "schema_version": EXTERNAL_OBJECT_CENSUS_SIGNATURE_SCHEMA,
        "authority_fingerprint": _fingerprint(
            authority_fingerprint, "object census authority fingerprint"
        ),
        "producer_descriptor_fingerprint": _fingerprint(
            producer_descriptor_fingerprint,
            "object census producer descriptor fingerprint",
        ),
        "signing_key_id": _text(signing_key_id, "object census signing key id"),
    }
    return json.dumps(
        material, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def assemble_external_object_census_record(
    authority: Mapping[str, object],
    producer_descriptor: Mapping[str, object],
    *,
    authority_signature: str,
) -> dict[str, object]:
    """Assemble a record after an external producer has signed it.

    This helper never signs and has no access to a private key.
    """

    canonical_authority = _canonical(authority)
    canonical_descriptor = _canonical(producer_descriptor)
    return {
        "schema_version": EXTERNAL_OBJECT_CENSUS_SCHEMA,
        "authority": canonical_authority,
        "authority_fingerprint": _digest(canonical_authority),
        "producer_descriptor": canonical_descriptor,
        "producer_descriptor_fingerprint": _digest(canonical_descriptor),
        "authority_signature": _text(
            authority_signature, "object census authority signature"
        ),
    }


def _validate_members(
    value: object,
    *,
    label: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    member_ids: list[str] = []
    derived_guards: set[str] = set()
    for row in _rows(value, f"{label} members"):
        member = _mapping(
            row,
            {
                "element_id",
                "element_kind",
                "owner_node_id",
                "required_guard_owner_id",
                "support_mode",
                "binding_roles",
                "not_applicable_roles",
                "derivation_ids",
            },
            f"{label} member",
        )
        element_id = _text(member["element_id"], f"{label} element id")
        member_ids.append(element_id)
        _text(member["element_kind"], f"{label} {element_id} kind")
        _text(member["owner_node_id"], f"{label} {element_id} owner node")
        guard_owner = _text(
            member["required_guard_owner_id"],
            f"{label} {element_id} Guard owner",
        )
        if guard_owner != "not_applicable":
            derived_guards.add(guard_owner)
        support_mode = _text(
            member["support_mode"], f"{label} {element_id} support mode"
        )
        if support_mode not in {"direct", "derived"}:
            raise ExternalObjectCensusError(
                f"{label} {element_id} support mode is not current"
            )
        binding_roles = set(
            _ids(
                member["binding_roles"],
                f"{label} {element_id} binding roles",
                allow_empty=True,
            )
        )
        not_applicable_roles = set(
            _ids(
                member["not_applicable_roles"],
                f"{label} {element_id} not-applicable roles",
                allow_empty=True,
            )
        )
        if (
            binding_roles.intersection(not_applicable_roles)
            or binding_roles.union(not_applicable_roles) != OBJECT_SUPPORT_ROLES
        ):
            raise ExternalObjectCensusError(
                f"{label} {element_id} does not dispose every support role exactly once"
            )
        derivation_ids = _ids(
            member["derivation_ids"],
            f"{label} {element_id} derivation ids",
            allow_empty=True,
        )
        if (support_mode == "derived") != bool(derivation_ids):
            raise ExternalObjectCensusError(
                f"{label} {element_id} support mode and derivations disagree"
            )
    if not member_ids or member_ids != sorted(member_ids):
        raise ExternalObjectCensusError(
            f"{label} members must be non-empty and canonically ordered"
        )
    if len(member_ids) != len(set(member_ids)):
        raise ExternalObjectCensusError(f"{label} member ids are duplicated")
    return tuple(member_ids), tuple(sorted(derived_guards))


def validate_external_object_census_source(raw: object) -> dict[str, Any]:
    """Validate the independently authored raw census source.

    This source is a separately fingerprinted adapter input.  It is not the
    candidate blueprint and it is not the candidate-derived semantic authority.
    """

    source = _mapping(
        raw,
        {
            "schema_version",
            "source_id",
            "source_owner_id",
            "discovery_mode",
            "authority_id",
            "authority_revision",
            "authority_owner_id",
            "target_id",
            "target_revision",
            "claim_boundary",
            "object_claim_kind",
            "required_node_ids",
            "required_guard_owner_ids",
            "members",
        },
        "external object census source",
    )
    if source["schema_version"] != EXTERNAL_OBJECT_CENSUS_SOURCE_SCHEMA:
        raise ExternalObjectCensusError(
            "external object census source schema is not current"
        )
    for field in (
        "source_id",
        "source_owner_id",
        "authority_id",
        "authority_revision",
        "authority_owner_id",
        "target_id",
        "target_revision",
        "claim_boundary",
    ):
        _text(source[field], f"object census source {field}")
    discovery_mode = _text(
        source["discovery_mode"], "object census source discovery mode"
    )
    if discovery_mode not in OBJECT_DISCOVERY_MODES:
        raise ExternalObjectCensusError(
            "object census source discovery mode is not current"
        )
    claim_kind = _text(
        source["object_claim_kind"], "object census source claim kind"
    )
    if claim_kind not in OBJECT_CLAIM_KINDS:
        raise ExternalObjectCensusError(
            "object census source claim kind is not current"
        )
    required_nodes = _ids(
        source["required_node_ids"], "object census source required node ids"
    )
    required_guards = _ids(
        source["required_guard_owner_ids"],
        "object census source required Guard owner ids",
        allow_empty=True,
    )
    member_ids, derived_guards = _validate_members(
        source["members"], label="object census source"
    )
    if required_guards != derived_guards:
        raise ExternalObjectCensusError(
            "object census source Guard denominator differs from member owners"
        )
    return {
        "source": _canonical(source),
        "source_id": str(source["source_id"]),
        "source_owner_id": str(source["source_owner_id"]),
        "discovery_mode": discovery_mode,
        "required_node_ids": list(required_nodes),
        "required_element_ids": list(member_ids),
        "required_guard_owner_ids": list(required_guards),
        "members": _canonical(source["members"]),
        "members_fingerprint": _digest(source["members"]),
    }


def _validate_discovery_receipt(
    value: object,
    *,
    authority: Mapping[str, object],
) -> Mapping[str, object]:
    receipt = _mapping(
        value,
        {
            "schema_version",
            "discovery_id",
            "discovery_mode",
            "discovery_producer_id",
            "discovery_producer_version",
            "discovery_executor_id",
            "discovery_executor_version",
            "target_id",
            "target_revision",
            "claim_boundary",
            "source_id",
            "source_owner_id",
            "source_content_fingerprint",
            "request_contract_fingerprint",
            "target_material_fingerprint",
            "candidate_input_kinds",
            "required_node_ids",
            "required_element_ids",
            "required_guard_owner_ids",
            "member_count",
            "members_fingerprint",
            "terminal_status",
            "result_fingerprint",
            "receipt_fingerprint",
        },
        "object census discovery receipt",
    )
    if receipt["schema_version"] != EXTERNAL_OBJECT_CENSUS_DISCOVERY_RECEIPT_SCHEMA:
        raise ExternalObjectCensusError(
            "object census discovery receipt schema is not current"
        )
    for field in (
        "discovery_id",
        "discovery_producer_id",
        "discovery_producer_version",
        "discovery_executor_id",
        "discovery_executor_version",
        "target_id",
        "target_revision",
        "claim_boundary",
        "source_id",
        "source_owner_id",
    ):
        _text(receipt[field], f"object census discovery {field}")
    mode = _text(receipt["discovery_mode"], "object census discovery mode")
    if mode not in OBJECT_DISCOVERY_MODES:
        raise ExternalObjectCensusError(
            "object census discovery receipt mode is not current"
        )
    candidate_inputs = _ids(
        receipt["candidate_input_kinds"],
        "object census discovery candidate inputs",
        allow_empty=True,
    )
    if mode == "independent_raw_target_request" and candidate_inputs:
        raise ExternalObjectCensusError(
            "independent object discovery consulted candidate-derived inputs"
        )
    if mode == "candidate_consistency" and not candidate_inputs:
        raise ExternalObjectCensusError(
            "candidate-consistency discovery must disclose candidate inputs"
        )
    required_nodes = _ids(
        receipt["required_node_ids"],
        "object census discovery required node ids",
    )
    required_elements = _ids(
        receipt["required_element_ids"],
        "object census discovery required element ids",
    )
    required_guards = _ids(
        receipt["required_guard_owner_ids"],
        "object census discovery required Guard owner ids",
        allow_empty=True,
    )
    for field in (
        "source_content_fingerprint",
        "request_contract_fingerprint",
        "target_material_fingerprint",
        "members_fingerprint",
        "result_fingerprint",
        "receipt_fingerprint",
    ):
        _fingerprint(receipt[field], f"object census discovery {field}")
    if not isinstance(receipt["member_count"], int) or receipt["member_count"] < 1:
        raise ExternalObjectCensusError(
            "object census discovery member count is invalid"
        )
    if receipt["terminal_status"] != "PASS":
        raise ExternalObjectCensusError(
            "object census discovery receipt is not terminal PASS"
        )
    authority_member_ids = tuple(
        str(row["element_id"]) for row in authority["members"]  # type: ignore[index]
    )
    expected_identity = {
        "target_id": authority["target_id"],
        "target_revision": authority["target_revision"],
        "claim_boundary": authority["claim_boundary"],
        "required_node_ids": tuple(authority["required_node_ids"]),
        "required_element_ids": authority_member_ids,
        "required_guard_owner_ids": tuple(authority["required_guard_owner_ids"]),
        "member_count": len(authority_member_ids),
        "members_fingerprint": _digest(authority["members"]),
        "source_content_fingerprint": authority["input_fingerprints"][  # type: ignore[index]
            "target_object_census_source"
        ],
        "request_contract_fingerprint": authority["input_fingerprints"][  # type: ignore[index]
            "request_contract"
        ],
        "target_material_fingerprint": authority["input_fingerprints"][  # type: ignore[index]
            "target_material"
        ],
    }
    observed_identity = {
        "target_id": receipt["target_id"],
        "target_revision": receipt["target_revision"],
        "claim_boundary": receipt["claim_boundary"],
        "required_node_ids": required_nodes,
        "required_element_ids": required_elements,
        "required_guard_owner_ids": required_guards,
        "member_count": receipt["member_count"],
        "members_fingerprint": receipt["members_fingerprint"],
        "source_content_fingerprint": receipt["source_content_fingerprint"],
        "request_contract_fingerprint": receipt["request_contract_fingerprint"],
        "target_material_fingerprint": receipt["target_material_fingerprint"],
    }
    if observed_identity != expected_identity:
        raise ExternalObjectCensusError(
            "object census discovery receipt denominator is stale or foreign"
        )
    result_payload = {
        "schema_version": "worldguard.external_object_census_discovery_result.v1",
        **expected_identity,
        "discovery_mode": mode,
        "candidate_input_kinds": list(candidate_inputs),
        "terminal_status": "PASS",
    }
    if receipt["result_fingerprint"] != _digest(result_payload):
        raise ExternalObjectCensusError(
            "object census discovery result fingerprint is stale"
        )
    receipt_payload = {
        key: value for key, value in receipt.items() if key != "receipt_fingerprint"
    }
    if receipt["receipt_fingerprint"] != _digest(receipt_payload):
        raise ExternalObjectCensusError(
            "object census discovery receipt fingerprint is stale"
        )
    return receipt


def _validate_authority(value: object) -> Mapping[str, object]:
    authority = _mapping(
        value,
        {
            "authority_id",
            "authority_revision",
            "authority_owner_id",
            "target_id",
            "target_revision",
            "claim_boundary",
            "object_claim_kind",
            "required_node_ids",
            "required_guard_owner_ids",
            "members",
            "input_fingerprints",
            "discovery_receipt",
        },
        "object census authority",
    )
    for field in (
        "authority_id",
        "authority_revision",
        "authority_owner_id",
        "target_id",
        "target_revision",
        "claim_boundary",
    ):
        _text(authority[field], f"object census {field}")
    claim_kind = _text(authority["object_claim_kind"], "object census claim kind")
    if claim_kind not in OBJECT_CLAIM_KINDS:
        raise ExternalObjectCensusError("object census claim kind is not current")
    _ids(authority["required_node_ids"], "object census required node ids")
    required_guards = _ids(
        authority["required_guard_owner_ids"],
        "object census required Guard owner ids",
        allow_empty=True,
    )
    _, derived_guards = _validate_members(
        authority["members"], label="object census"
    )
    if required_guards != derived_guards:
        raise ExternalObjectCensusError(
            "object census Guard denominator differs from member owners"
        )
    input_fingerprints = _mapping(
        authority["input_fingerprints"],
        set(OBJECT_CENSUS_INPUT_KINDS),
        "object census input fingerprints",
    )
    for input_kind in OBJECT_CENSUS_INPUT_KINDS:
        _fingerprint(
            input_fingerprints[input_kind],
            f"object census {input_kind} fingerprint",
        )
    _validate_discovery_receipt(
        authority["discovery_receipt"], authority=authority
    )
    return authority


def _verify_rsa_pkcs1v15_sha256(
    message: bytes, signature: str, descriptor: Mapping[str, object]
) -> bool:
    prefix = "rsa-pkcs1v15-sha256:"
    if not signature.startswith(prefix):
        return False
    try:
        signature_bytes = bytes.fromhex(signature.removeprefix(prefix))
        modulus = int(str(descriptor["public_modulus_hex"]), 16)
        exponent = int(descriptor["public_exponent"])
    except (KeyError, TypeError, ValueError):
        return False
    width = (modulus.bit_length() + 7) // 8
    if len(signature_bytes) != width:
        return False
    decoded = pow(int.from_bytes(signature_bytes, "big"), exponent, modulus).to_bytes(
        width, "big"
    )
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420")
    digest_info += hashlib.sha256(message).digest()
    padding_length = width - len(digest_info) - 3
    if padding_length < 8:
        return False
    expected = b"\x00\x01" + (b"\xff" * padding_length) + b"\x00" + digest_info
    return decoded == expected


def validate_external_object_census_record(raw: object) -> dict[str, Any]:
    """Validate exact shape, fingerprints, and signature without granting trust."""

    record = _mapping(
        raw,
        {
            "schema_version",
            "authority",
            "authority_fingerprint",
            "producer_descriptor",
            "producer_descriptor_fingerprint",
            "authority_signature",
        },
        "external object census record",
    )
    if record["schema_version"] != EXTERNAL_OBJECT_CENSUS_SCHEMA:
        raise ExternalObjectCensusError("external object census schema is not current")
    authority = _validate_authority(record["authority"])
    authority_fingerprint = _fingerprint(
        record["authority_fingerprint"], "object census authority fingerprint"
    )
    if authority_fingerprint != _digest(authority):
        raise ExternalObjectCensusError("object census authority fingerprint is stale")
    descriptor = _mapping(
        record["producer_descriptor"],
        {
            "producer_id",
            "producer_version",
            "producer_capability_id",
            "discovery_executor_id",
            "discovery_executor_version",
            "signature_algorithm",
            "signing_key_id",
            "public_exponent",
            "public_modulus_hex",
        },
        "object census producer descriptor",
    )
    for field in (
        "producer_id",
        "producer_version",
        "producer_capability_id",
        "discovery_executor_id",
        "discovery_executor_version",
        "signing_key_id",
    ):
        _text(descriptor[field], f"object census producer {field}")
    if descriptor["signature_algorithm"] != "rsa-pkcs1v15-sha256":
        raise ExternalObjectCensusError(
            "object census signature algorithm is not current"
        )
    if not isinstance(descriptor["public_exponent"], int) or descriptor[
        "public_exponent"
    ] < 3:
        raise ExternalObjectCensusError("object census public exponent is invalid")
    try:
        modulus = int(
            _text(descriptor["public_modulus_hex"], "object census modulus"), 16
        )
    except ValueError as exc:
        raise ExternalObjectCensusError("object census modulus is invalid") from exc
    if modulus.bit_length() < 2048:
        raise ExternalObjectCensusError("object census public key is too small")
    descriptor_fingerprint = _fingerprint(
        record["producer_descriptor_fingerprint"],
        "object census producer descriptor fingerprint",
    )
    if descriptor_fingerprint != _digest(descriptor):
        raise ExternalObjectCensusError(
            "object census producer descriptor fingerprint is stale"
        )
    payload = external_object_census_signing_payload(
        authority_fingerprint=authority_fingerprint,
        producer_descriptor_fingerprint=descriptor_fingerprint,
        signing_key_id=str(descriptor["signing_key_id"]),
    )
    signature = _text(record["authority_signature"], "object census signature")
    if not _verify_rsa_pkcs1v15_sha256(payload, signature, descriptor):
        raise ExternalObjectCensusError("object census signature is invalid")
    discovery_receipt = authority["discovery_receipt"]
    producer_mismatches = {
        field: {"expected": expected, "observed": discovery_receipt.get(field)}
        for field, expected in (
            ("discovery_producer_id", descriptor["producer_id"]),
            ("discovery_producer_version", descriptor["producer_version"]),
            ("discovery_executor_id", descriptor["discovery_executor_id"]),
            (
                "discovery_executor_version",
                descriptor["discovery_executor_version"],
            ),
        )
        if discovery_receipt.get(field) != expected
    }
    if producer_mismatches:
        raise ExternalObjectCensusError(
            "object census discovery producer differs from the signing producer"
        )
    discovery_mode = str(discovery_receipt["discovery_mode"])
    return {
        "record": _canonical(record),
        "authority": _canonical(authority),
        "authority_fingerprint": authority_fingerprint,
        "producer_descriptor_fingerprint": descriptor_fingerprint,
        "discovery_mode": discovery_mode,
        "discovery_receipt": _canonical(discovery_receipt),
        "independent_discovery_declared": (
            discovery_mode == "independent_raw_target_request"
        ),
        "required_trust": {
            "authority_fingerprint": authority_fingerprint,
            "producer_descriptor_fingerprint": descriptor_fingerprint,
        },
    }


__all__ = [
    "EXTERNAL_OBJECT_CENSUS_SCHEMA",
    "EXTERNAL_OBJECT_CENSUS_SIGNATURE_SCHEMA",
    "EXTERNAL_OBJECT_CENSUS_SOURCE_SCHEMA",
    "EXTERNAL_OBJECT_CENSUS_DISCOVERY_RECEIPT_SCHEMA",
    "OBJECT_CENSUS_INPUT_KINDS",
    "OBJECT_CLAIM_KINDS",
    "OBJECT_DISCOVERY_MODES",
    "ExternalObjectCensusError",
    "assemble_external_object_census_record",
    "external_object_census_signing_payload",
    "validate_external_object_census_record",
    "validate_external_object_census_source",
]
