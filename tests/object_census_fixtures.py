"""Test/developer-only signer for independent WorldBlueprint object censuses.

The private exponent remains outside ``worldguard/`` and the portable runtime.
Production can validate a signed public record but cannot manufacture a census
or decide that its producer is trusted.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from worldguard.blueprint_census import (
    EXTERNAL_OBJECT_CENSUS_DISCOVERY_RECEIPT_SCHEMA,
    assemble_external_object_census_record,
    external_object_census_signing_payload,
    validate_external_object_census_source,
)


_TEST_CENSUS_MODULUS_HEX = (
    "b3d0315c2195f01b4b06d794f09951344498b7dfe7f652c97847ee5abab80904"
    "32179c5fa5e42f13843710ff63418f2ab6bb79c042870300658810f5ad7a8d8c"
    "5b434483b0482bcc27de962181c08e7fc87e924d21057752e3e7f4e71547d49c"
    "1b8b2dd6728695bb790490e8a4a56f628a5ba08d8a22fe2b8e31ee53b99312d"
    "55b1ac076dd8cd746bec9eaa9bea2ffca573c3d5584f1384f18b64a4878c7095"
    "730a952c3d0d63b963bb22837024cd6be82246fd8bf4f046f26f1b3019786a5e"
    "088a3163a39643dc1a7de1fb82caab0200b22663cf1305eef645c11fa4aa76fab"
    "07f4a8b5c0b908352d67e10442dfce0d33c41f3559a832fa8caa93da73596ddf"
)
_TEST_CENSUS_PRIVATE_EXPONENT_HEX = (
    "6334209760dc351d09b69ba7cb59fae828544d55d5c71b8395bdb1ae12c7c809"
    "ad8d4333adf587577021655a512b714e32849a364d3de995056f1d543dc298677"
    "04e5b758003414ea04c786dc20537591e875e35f95ae7ab2e9be18cc03be1fbc"
    "26276069326d76317f041f66827f19cdf129030a69e89b603fc5e2d88fbb06e5"
    "f870e905b6822080aaff837454e7df2b672f920d305d9daee5db0d50de64726b"
    "5c3d5935da30b1e077fc4b7eb9e668cf2066eeb9549d20aeeddff59d70428651"
    "25b1ab81229b79c4299c624ef27d9761338785fd2bad582a5a6c728156ab1d291"
    "ffa5ea0431f07d711a034f894145770d4b7cb5fc5e9f4fad27d842fa13b7e1"
)

OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR = {
    "producer_id": "worldguard.tests.external-object-census",
    "producer_version": "1",
    "producer_capability_id": "worldguard.external-object-census.discovery.v1",
    "discovery_executor_id": "worldguard.tests.external-object-census.discovery.v1",
    "discovery_executor_version": "v1",
    "signature_algorithm": "rsa-pkcs1v15-sha256",
    "signing_key_id": "worldguard-test-object-census-2026-01",
    "public_exponent": 65537,
    "public_modulus_hex": _TEST_CENSUS_MODULUS_HEX,
}


def _digest(value: object) -> str:
    body = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _sign(payload: bytes) -> str:
    modulus = int(_TEST_CENSUS_MODULUS_HEX, 16)
    private_exponent = int(_TEST_CENSUS_PRIVATE_EXPONENT_HEX, 16)
    width = (modulus.bit_length() + 7) // 8
    digest_info = bytes.fromhex("3031300d060960864801650304020105000420")
    digest_info += hashlib.sha256(payload).digest()
    encoded = (
        b"\x00\x01"
        + (b"\xff" * (width - len(digest_info) - 3))
        + b"\x00"
        + digest_info
    )
    signature = pow(int.from_bytes(encoded, "big"), private_exponent, modulus)
    return "rsa-pkcs1v15-sha256:" + signature.to_bytes(width, "big").hex()


def signed_object_census(authority: Mapping[str, object]) -> dict[str, object]:
    authority_fingerprint = _digest(authority)
    descriptor_fingerprint = _digest(OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR)
    payload = external_object_census_signing_payload(
        authority_fingerprint=authority_fingerprint,
        producer_descriptor_fingerprint=descriptor_fingerprint,
        signing_key_id=str(
            OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR["signing_key_id"]
        ),
    )
    return assemble_external_object_census_record(
        authority,
        OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR,
        authority_signature=_sign(payload),
    )


def discovery_receipt_for_source(
    source: Mapping[str, object],
    *,
    input_fingerprints: Mapping[str, str],
) -> dict[str, object]:
    """Issue the fixture producer's discovery receipt from raw source inputs.

    The caller supplies fingerprints of the frozen request, raw target material,
    independent census source, and candidate semantic projection.  Only the
    first three are discovery inputs; the semantic projection is signed later
    for freshness/comparison but cannot define the denominator.
    """

    validated = validate_external_object_census_source(source)
    mode = str(validated["discovery_mode"])
    candidate_input_kinds = (
        [] if mode == "independent_raw_target_request" else ["target_semantic_authority"]
    )
    result_payload = {
        "schema_version": "worldguard.external_object_census_discovery_result.v1",
        "target_id": source["target_id"],
        "target_revision": source["target_revision"],
        "claim_boundary": source["claim_boundary"],
        "required_node_ids": list(validated["required_node_ids"]),
        "required_element_ids": list(validated["required_element_ids"]),
        "required_guard_owner_ids": list(validated["required_guard_owner_ids"]),
        "member_count": len(validated["required_element_ids"]),
        "members_fingerprint": validated["members_fingerprint"],
        "source_content_fingerprint": input_fingerprints[
            "target_object_census_source"
        ],
        "request_contract_fingerprint": input_fingerprints["request_contract"],
        "target_material_fingerprint": input_fingerprints["target_material"],
        "discovery_mode": mode,
        "candidate_input_kinds": candidate_input_kinds,
        "terminal_status": "PASS",
    }
    receipt = {
        "schema_version": EXTERNAL_OBJECT_CENSUS_DISCOVERY_RECEIPT_SCHEMA,
        "discovery_id": (
            f"discovery:{source['source_id']}:{source['target_revision']}"
        ),
        "discovery_mode": mode,
        "discovery_producer_id": OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR[
            "producer_id"
        ],
        "discovery_producer_version": OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR[
            "producer_version"
        ],
        "discovery_executor_id": OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR[
            "discovery_executor_id"
        ],
        "discovery_executor_version": OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR[
            "discovery_executor_version"
        ],
        "target_id": source["target_id"],
        "target_revision": source["target_revision"],
        "claim_boundary": source["claim_boundary"],
        "source_id": source["source_id"],
        "source_owner_id": source["source_owner_id"],
        "source_content_fingerprint": input_fingerprints[
            "target_object_census_source"
        ],
        "request_contract_fingerprint": input_fingerprints["request_contract"],
        "target_material_fingerprint": input_fingerprints["target_material"],
        "candidate_input_kinds": candidate_input_kinds,
        "required_node_ids": list(validated["required_node_ids"]),
        "required_element_ids": list(validated["required_element_ids"]),
        "required_guard_owner_ids": list(validated["required_guard_owner_ids"]),
        "member_count": len(validated["required_element_ids"]),
        "members_fingerprint": validated["members_fingerprint"],
        "terminal_status": "PASS",
        "result_fingerprint": _digest(result_payload),
    }
    return {**receipt, "receipt_fingerprint": _digest(receipt)}


def signed_object_census_from_source(
    source: Mapping[str, object],
    *,
    input_fingerprints: Mapping[str, str],
) -> dict[str, object]:
    """Build and sign authority only from the frozen independent source."""

    validated = validate_external_object_census_source(source)
    authority = {
        "authority_id": source["authority_id"],
        "authority_revision": source["authority_revision"],
        "authority_owner_id": source["authority_owner_id"],
        "target_id": source["target_id"],
        "target_revision": source["target_revision"],
        "claim_boundary": source["claim_boundary"],
        "object_claim_kind": source["object_claim_kind"],
        "required_node_ids": list(validated["required_node_ids"]),
        "required_guard_owner_ids": list(validated["required_guard_owner_ids"]),
        "members": list(validated["members"]),
        "input_fingerprints": dict(input_fingerprints),
        "discovery_receipt": discovery_receipt_for_source(
            source, input_fingerprints=input_fingerprints
        ),
    }
    return signed_object_census(authority)


OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR_FINGERPRINT = _digest(
    OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR
)


__all__ = [
    "OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR",
    "OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR_FINGERPRINT",
    "discovery_receipt_for_source",
    "signed_object_census",
    "signed_object_census_from_source",
]
