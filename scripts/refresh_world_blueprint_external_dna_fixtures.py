"""Refresh the maintained external-object DNA fixtures through current owners.

This is an author-side fixture compiler. It projects explicitly authored raw-request
and raw-target observations without consulting the candidate blueprint or its semantic
authority for the object denominator. It is not an alternate runtime qualification path.
"""

from __future__ import annotations

import hashlib
import json
import re
import runpy
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from worldguard.blueprint import (
    BINDING_ROLES,
    BehaviorCaseContract,
    BlueprintBinding,
    GuardStatus,
    WorldBlueprintContract,
    _binding_receipt_fingerprint,
    check_world_blueprint,
    compile_behavior_commitment_inventory_cache,
)
from worldguard.blueprint_census import validate_external_object_census_source
from worldguard.semantic import fingerprint_mesh


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests/fixtures/world_blueprint"
SUPPORT_ROOT = FIXTURE_ROOT / "support"
ZERO_SHA256 = "sha256:" + "0" * 64

BASE_BLUEPRINT = FIXTURE_ROOT / "planning_workflow_three_level.yaml"
BASE_REQUEST = SUPPORT_ROOT / "behavior-request-contract.json"
BASE_MATERIAL = SUPPORT_ROOT / "target-material.json"
BASE_AUTHORITY = SUPPORT_ROOT / "target-semantic-authority.json"
BASE_CACHE = SUPPORT_ROOT / "behavior-commitments.json"
BASE_CENSUS = SUPPORT_ROOT / "target-object-census-authority.json"
BASE_CENSUS_SOURCE = SUPPORT_ROOT / "target-object-census-source.json"

SEVEN_BLUEPRINT = FIXTURE_ROOT / "seven_guard_portable_handoff.json"
SEVEN_AUTHORITY = SUPPORT_ROOT / "seven-guard-target-semantic-authority.json"
SEVEN_REQUEST = SUPPORT_ROOT / "seven-guard-behavior-request-contract.json"
SEVEN_MATERIAL = SUPPORT_ROOT / "seven-guard-validation-target-material.json"
SEVEN_CACHE = SUPPORT_ROOT / "seven-guard-behavior-commitments.json"
SEVEN_CENSUS = SUPPORT_ROOT / "seven-guard-target-object-census-authority.json"
SEVEN_CENSUS_SOURCE = SUPPORT_ROOT / "seven-guard-target-object-census-source.json"
SEVEN_MATRIX = FIXTURE_ROOT / "seven_guard_native_owner_matrix.json"

POLICY_BLUEPRINT = FIXTURE_ROOT / "policy_access_execution.yaml"
POLICY_AUTHORITY = SUPPORT_ROOT / "policy-access-target-semantic-authority.json"
POLICY_REQUEST = SUPPORT_ROOT / "policy-access-behavior-request-contract.json"
POLICY_MATERIAL = SUPPORT_ROOT / "policy-access-target-material.json"
POLICY_EVIDENCE = SUPPORT_ROOT / "policy-access-evidence.json"
POLICY_TESTS = SUPPORT_ROOT / "policy-access-tests.json"
POLICY_NATIVE_RESULTS = SUPPORT_ROOT / "policy-access-native-results.json"
POLICY_CACHE = SUPPORT_ROOT / "policy-access-behavior-commitments.json"
POLICY_CENSUS = SUPPORT_ROOT / "policy-access-target-object-census-authority.json"
POLICY_CENSUS_SOURCE = SUPPORT_ROOT / "policy-access-target-object-census-source.json"

DERIVED_SUPPORTS = {
    "allocation_summary": "derive_allocation_result",
    "governance_summary": "derive_governance_result",
    "plan_outcome": "derive_root_plan_outcome",
    "scheduling_summary": "derive_scheduling_result",
    "policy_decision_state": "derive_policy_decision",
}
BASE_MATERIAL_BINDINGS = {
    "actor_alex": ("actor_alex_material", "workflow_record_assignment"),
    "planner_role": ("planner_role_material", "workflow_record_assignment"),
    "schedule_event": ("schedule_event_material", "workflow_record_schedule"),
    "scheduled_state": ("scheduled_state_material", "workflow_record_schedule"),
    "task_prepare": ("task_prepare_material", "workflow_record_assignment"),
}
MATRIX_ELEMENT_IDS = {
    "matrix_agent_pass",
    "matrix_causal_pass",
    "matrix_conflict_pass",
    "matrix_event_pass",
    "matrix_norm_pass",
    "matrix_resource_pass",
    "matrix_space_pass",
}


def _object_census_member(
    element_id: str,
    element_kind: str,
    owner_node_id: str,
    required_guard_owner_id: str,
    binding_roles: tuple[str, ...],
    not_applicable_roles: tuple[str, ...],
    *,
    support_mode: str = "direct",
    derivation_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Author one raw-request census row without consulting a candidate model."""

    return {
        "element_id": element_id,
        "element_kind": element_kind,
        "owner_node_id": owner_node_id,
        "required_guard_owner_id": required_guard_owner_id,
        "support_mode": support_mode,
        "binding_roles": sorted(binding_roles),
        "not_applicable_roles": sorted(not_applicable_roles),
        "derivation_ids": sorted(derivation_ids),
    }


_ALL_DIRECT_ROLES = ("evidence", "native_result", "target_material", "test_check")
_NATIVE_MATERIAL_ROLES = ("native_result", "target_material")
_EVIDENCE_TEST_NOT_APPLICABLE = ("evidence", "test_check")
_DERIVED_NOT_APPLICABLE = ("evidence", "target_material", "test_check")


BASE_OBJECT_CENSUS_MEMBERS = (
    _object_census_member(
        "actor_alex",
        "agent",
        "assign_task_leaf",
        "AgentGuard",
        _NATIVE_MATERIAL_ROLES,
        _EVIDENCE_TEST_NOT_APPLICABLE,
    ),
    _object_census_member(
        "allocation_summary",
        "relation",
        "allocation_layer",
        "not_applicable",
        ("native_result",),
        _DERIVED_NOT_APPLICABLE,
        support_mode="derived",
        derivation_ids=("derive_allocation_result",),
    ),
    _object_census_member(
        "assignment_transition",
        "transition",
        "assign_task_leaf",
        "EventGuard",
        _ALL_DIRECT_ROLES,
        (),
    ),
    _object_census_member(
        "authorization_norm",
        "norm",
        "authorize_task_leaf",
        "NormGuard",
        _ALL_DIRECT_ROLES,
        (),
    ),
    _object_census_member(
        "governance_summary",
        "relation",
        "governance_layer",
        "not_applicable",
        ("native_result",),
        _DERIVED_NOT_APPLICABLE,
        support_mode="derived",
        derivation_ids=("derive_governance_result",),
    ),
    _object_census_member(
        "plan_outcome",
        "state",
        "plan_root",
        "EventGuard",
        ("native_result",),
        _DERIVED_NOT_APPLICABLE,
        support_mode="derived",
        derivation_ids=("derive_root_plan_outcome",),
    ),
    _object_census_member(
        "planner_role",
        "property",
        "assign_task_leaf",
        "not_applicable",
        _NATIVE_MATERIAL_ROLES,
        _EVIDENCE_TEST_NOT_APPLICABLE,
    ),
    _object_census_member(
        "resource_reservation",
        "resource",
        "reserve_resource_leaf",
        "ResourceGuard",
        _ALL_DIRECT_ROLES,
        (),
    ),
    _object_census_member(
        "schedule_event",
        "event",
        "schedule_task_leaf",
        "EventGuard",
        _NATIVE_MATERIAL_ROLES,
        _EVIDENCE_TEST_NOT_APPLICABLE,
    ),
    _object_census_member(
        "schedule_transition",
        "transition",
        "schedule_task_leaf",
        "EventGuard",
        _ALL_DIRECT_ROLES,
        (),
    ),
    _object_census_member(
        "scheduled_state",
        "state",
        "schedule_task_leaf",
        "EventGuard",
        _NATIVE_MATERIAL_ROLES,
        _EVIDENCE_TEST_NOT_APPLICABLE,
    ),
    _object_census_member(
        "scheduling_summary",
        "state",
        "scheduling_layer",
        "EventGuard",
        ("native_result",),
        _DERIVED_NOT_APPLICABLE,
        support_mode="derived",
        derivation_ids=("derive_scheduling_result",),
    ),
    _object_census_member(
        "task_prepare",
        "entity",
        "assign_task_leaf",
        "not_applicable",
        _NATIVE_MATERIAL_ROLES,
        _EVIDENCE_TEST_NOT_APPLICABLE,
    ),
)

SEVEN_GUARD_MATRIX_CENSUS_MEMBERS = tuple(
    _object_census_member(
        element_id,
        element_kind,
        "plan_root",
        guard_owner,
        _ALL_DIRECT_ROLES,
        (),
    )
    for element_id, element_kind, guard_owner in (
        ("matrix_agent_pass", "agent", "AgentGuard"),
        ("matrix_causal_pass", "causal_link", "CausalGuard"),
        ("matrix_conflict_pass", "conflict", "ConflictGuard"),
        ("matrix_event_pass", "event", "EventGuard"),
        ("matrix_norm_pass", "norm", "NormGuard"),
        ("matrix_resource_pass", "resource", "ResourceGuard"),
        ("matrix_space_pass", "relation", "SpaceGuard"),
    )
)

POLICY_OBJECT_CENSUS_MEMBERS = (
    _object_census_member(
        "access_policy_norm",
        "norm",
        "evaluate_access_leaf",
        "NormGuard",
        _ALL_DIRECT_ROLES,
        (),
    ),
    _object_census_member(
        "policy_decision_state",
        "state",
        "policy_root",
        "EventGuard",
        _NATIVE_MATERIAL_ROLES,
        _EVIDENCE_TEST_NOT_APPLICABLE,
        support_mode="derived",
        derivation_ids=("derive_policy_decision",),
    ),
    _object_census_member(
        "request_actor",
        "agent",
        "evaluate_access_leaf",
        "AgentGuard",
        _NATIVE_MATERIAL_ROLES,
        _EVIDENCE_TEST_NOT_APPLICABLE,
    ),
)


def _raw_request_object_census(
    request: dict[str, Any],
    *,
    source_id: str,
    source_owner_id: str,
    authority_id: str,
    authority_owner_id: str,
    discovery_mode: str,
    object_claim_kind: str,
    members: tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Create the request-owned denominator from explicit independent observations."""

    semantic = request["semantic_authority"]
    observed_element_ids = sorted(row["element_id"] for row in members)
    if observed_element_ids != semantic["required_element_ids"]:
        raise ValueError(
            "independent census member observations do not match the raw request "
            "element denominator"
        )
    observed_guard_owners = sorted(
        {
            row["required_guard_owner_id"]
            for row in members
            if row["required_guard_owner_id"] != "not_applicable"
        }
    )
    if observed_guard_owners != semantic["required_guard_owner_ids"]:
        raise ValueError(
            "independent census member observations do not match the raw request "
            "Guard-owner denominator"
        )
    return {
        "schema_version": "worldguard.external_object_census_source.v1",
        "source_id": source_id,
        "source_owner_id": source_owner_id,
        "discovery_mode": discovery_mode,
        "authority_id": authority_id,
        "authority_revision": request["target_revision"],
        "authority_owner_id": authority_owner_id,
        "target_id": request["target_id"],
        "target_revision": request["target_revision"],
        "claim_boundary": request["claim_boundary"],
        "object_claim_kind": object_claim_kind,
        "required_node_ids": list(semantic["required_node_ids"]),
        "required_guard_owner_ids": list(semantic["required_guard_owner_ids"]),
        "members": [deepcopy(row) for row in members],
    }


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(_canonical_json_bytes(value) + b"\n")


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain one JSON object")
    return value


def _load_blueprint(path: Path) -> dict[str, Any]:
    if path.suffix == ".json":
        return _load_json(path)
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain one blueprint object")
    return value


def _write_blueprint(path: Path, value: dict[str, Any]) -> None:
    if path.suffix == ".json":
        _write_json(path, value)
        return
    path.write_text(
        yaml.safe_dump(value, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
        newline="\n",
    )


def _replace_strings(value: Any, replacements: tuple[tuple[str, str], ...]) -> Any:
    if isinstance(value, dict):
        return {
            key: _replace_strings(member, replacements)
            for key, member in value.items()
        }
    if isinstance(value, list):
        return [_replace_strings(member, replacements) for member in value]
    if isinstance(value, str):
        for old, new in replacements:
            value = value.replace(old, new)
    return value


def _normalize_seven_guard_revision(value: Any) -> Any:
    """Project planning or previously projected revisions to one stable identity."""

    if isinstance(value, dict):
        return {
            key: _normalize_seven_guard_revision(member)
            for key, member in value.items()
        }
    if isinstance(value, list):
        return [_normalize_seven_guard_revision(member) for member in value]
    if isinstance(value, str):
        return re.sub(
            r"(?:validation-)*revision-1",
            "validation-revision-1",
            value,
        )
    return value


def _selected_content(locator: str) -> bytes:
    path_text, separator, selector = locator.partition("#")
    content = (FIXTURE_ROOT / path_text).read_bytes()
    if not separator:
        return content
    value = json.loads(content.decode("utf-8"))
    if not isinstance(value, dict) or selector not in value:
        raise KeyError(f"missing selector {selector} in {path_text}")
    return _canonical_json_bytes(value[selector])


def _binding_receipt(binding: dict[str, Any]) -> str:
    candidate = BlueprintBinding.from_dict(
        {**binding, "receipt_fingerprint": ZERO_SHA256}
    )
    return _binding_receipt_fingerprint(candidate)


def _material_binding(
    blueprint: dict[str, Any],
    *,
    element_id: str,
    binding_id: str,
    material_id: str,
    locator: str,
) -> dict[str, Any]:
    binding = {
        "binding_id": binding_id,
        "role": "target_material",
        "subject_element_id": element_id,
        "resource_id": material_id,
        "owner": "workflow_owner",
        "locator": locator,
        "provider_id": "fixture.local",
        "provider_version": "v1",
        "provider_capability_id": "fixture.json-selector",
        "observation_mode": "local_content",
        "target_id": blueprint["target_id"],
        "target_revision": blueprint["target_revision"],
        "freshness_status": "current",
        "content_fingerprint": "sha256:"
        + hashlib.sha256(_selected_content(locator)).hexdigest(),
        "receipt_fingerprint": ZERO_SHA256,
        "claim_boundary": blueprint["declared_boundary"],
    }
    binding["receipt_fingerprint"] = _binding_receipt(binding)
    return binding


def _matrix_binding(
    blueprint: dict[str, Any], *, element_id: str, role: str
) -> dict[str, Any]:
    locator = "seven_guard_native_owner_matrix.json"
    binding_id = f"binding:{element_id}:{role}"
    owner_by_role = {
        "target_material": "seven-guard-validation-material-owner",
        "evidence": "seven-guard-validation-oracle-owner",
        "test_check": "seven-guard-validation-check-owner",
    }
    capability_by_role = {
        "target_material": "worldguard.validation-case-material.v1",
        "evidence": "worldguard.validation-case-oracle.v1",
        "test_check": "worldguard.validation-case-check.v1",
    }
    binding = {
        "binding_id": binding_id,
        "role": role,
        "subject_element_id": element_id,
        "resource_id": f"seven-guard-validation:{element_id}:{role}",
        "owner": owner_by_role[role],
        "locator": locator,
        "provider_id": "worldguard.seven-guard-validation",
        "provider_version": "v1",
        "provider_capability_id": capability_by_role[role],
        "observation_mode": "local_content",
        "target_id": blueprint["target_id"],
        "target_revision": blueprint["target_revision"],
        "freshness_status": "current",
        "content_fingerprint": "sha256:"
        + hashlib.sha256(_selected_content(locator)).hexdigest(),
        "receipt_fingerprint": ZERO_SHA256,
        "claim_boundary": blueprint["declared_boundary"],
    }
    binding["receipt_fingerprint"] = _binding_receipt(binding)
    return binding


def _binding_responsibility(binding: dict[str, Any]) -> dict[str, Any]:
    return {
        "binding_id": binding["binding_id"],
        "role": binding["role"],
        "owner_id": binding["owner"],
        "resource_id": binding["resource_id"],
        "locator": binding["locator"],
        "provider_id": binding["provider_id"],
        "provider_version": binding["provider_version"],
        "provider_capability_id": binding["provider_capability_id"],
        "observation_mode": binding["observation_mode"],
    }


def _native_payload(semantic: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(semantic[key])
        for key in (
            "semantic_id",
            "element_kind",
            "native_object_id",
            "native_schema_id",
            "provider_id",
            "provider_version",
            "observation_binding_id",
            "semantic_fields",
            "claim_boundary",
        )
    }


def _refresh_native_semantic_fingerprints(blueprint: dict[str, Any]) -> None:
    for element in blueprint["elements"]:
        semantic = element["native_semantic"]
        semantic["content_fingerprint"] = (
            "sha256:" + fingerprint_mesh(_native_payload(semantic))
        )


def _derivation_responsibility(
    blueprint: dict[str, Any], *, element_id: str, derivation_id: str
) -> dict[str, Any]:
    matches = [
        (node, derivation)
        for node in blueprint["nodes"]
        for derivation in node.get("output_derivations", [])
        if derivation["derivation_id"] == derivation_id
    ]
    if len(matches) != 1:
        raise ValueError(f"{element_id} requires one derivation {derivation_id}")
    node, derivation = matches[0]
    return {
        "derivation_id": derivation["derivation_id"],
        "target_element_id": element_id,
        "owner_node_id": node["node_id"],
        "parent_output_port_id": derivation["parent_output_port_id"],
        "sources": deepcopy(derivation["sources"]),
    }


def _not_applicable_reason(element_id: str, role: str, derived: bool) -> str:
    if role == "target_material" and derived:
        return (
            f"{element_id} is derived from the exact declared output lineage and "
            "has no independent target-material record."
        )
    if role == "target_material":
        return (
            f"{element_id} has no separate target-material artifact inside this "
            "bounded target; its current semantic identity is native-only."
        )
    if role == "evidence":
        return (
            f"{element_id} has no independent evidence artifact in this target "
            "boundary; no evidence identity is invented."
        )
    return (
        f"{element_id} has no separate target check; its native purpose cases own "
        "the applicable semantic check without a duplicate test identity."
    )


def _refresh_authority(
    blueprint: dict[str, Any], authority: dict[str, Any]
) -> None:
    authority["schema_version"] = "worldguard.target_semantic_authority.v2"
    elements_by_id = {row["element_id"]: row for row in blueprint["elements"]}
    bindings_by_element: dict[str, list[dict[str, Any]]] = {}
    for binding in blueprint["bindings"]:
        bindings_by_element.setdefault(binding["subject_element_id"], []).append(
            binding
        )
    for row in authority["elements"]:
        element_id = row["element_id"]
        row["native_semantic"] = deepcopy(
            elements_by_id[element_id]["native_semantic"]
        )
        applicable = sorted(
            bindings_by_element.get(element_id, []),
            key=lambda binding: binding["binding_id"],
        )
        row["binding_responsibilities"] = [
            _binding_responsibility(binding) for binding in applicable
        ]
        applicable_roles = {binding["role"] for binding in applicable}
        derived = element_id in DERIVED_SUPPORTS
        row["not_applicable_responsibilities"] = [
            {
                "role": role,
                "reason": _not_applicable_reason(element_id, role, derived),
            }
            for role in sorted(BINDING_ROLES.difference(applicable_roles))
        ]
        row["support_mode"] = "derived" if derived else "direct"
        row["derivation_responsibilities"] = (
            [
                _derivation_responsibility(
                    blueprint,
                    element_id=element_id,
                    derivation_id=DERIVED_SUPPORTS[element_id],
                )
            ]
            if derived
            else []
        )


def _refresh_binding_content_and_receipts(blueprint: dict[str, Any]) -> None:
    for binding in blueprint["bindings"]:
        binding["content_fingerprint"] = "sha256:" + hashlib.sha256(
            _selected_content(binding["locator"])
        ).hexdigest()
        binding["receipt_fingerprint"] = (
            ZERO_SHA256
            if binding["role"] == "native_result"
            else _binding_receipt(binding)
        )


def _refresh_integrated_external_support_records(
    blueprint: dict[str, Any],
) -> None:
    """Project executable test designs and semantic evidence from target contracts."""

    elements = {row["element_id"]: row for row in blueprint["elements"]}
    containers: dict[Path, dict[str, Any]] = {}
    for binding in blueprint["bindings"]:
        if binding["role"] not in {"evidence", "test_check"}:
            continue
        path_text, separator, selector = binding["locator"].partition("#")
        if not separator:
            raise ValueError(
                f"integrated support binding {binding['binding_id']} requires a selector"
            )
        path = FIXTURE_ROOT / path_text
        container = containers.setdefault(path, _load_json(path))
        existing = container.get(selector, {})
        if not isinstance(existing, dict):
            existing = {}
        element = elements[binding["subject_element_id"]]
        if binding["role"] == "evidence":
            container[selector] = {
                "schema_version": "worldguard.external_evidence_observation.v1",
                "evidence_id": existing.get(
                    "evidence_id", f"evidence:{binding['resource_id']}"
                ),
                "target_id": blueprint["target_id"],
                "target_revision": blueprint["target_revision"],
                "claim_boundary": blueprint["declared_boundary"],
                "subject_element_id": binding["subject_element_id"],
                "owner_id": binding["owner"],
                "source_id": binding["resource_id"],
                "producer_id": binding["provider_id"],
                "producer_version": binding["provider_version"],
                "freshness_status": "current",
                "observed": True,
                "supports": binding["subject_element_id"],
                "observation": (
                    f"Observed support for {binding['subject_element_id']} within "
                    f"{blueprint['declared_boundary']}."
                ),
            }
            continue
        task_purpose = element.get("native_semantic", {}).get("task_purpose", {})
        known_good = [
            row
            for row in task_purpose.get("behavior_cases", [])
            if row.get("case_kind") == "known_good"
        ]
        if len(known_good) != 1:
            raise ValueError(
                f"test binding {binding['binding_id']} requires one known-good case"
            )
        case = known_good[0]
        parsed_case = BehaviorCaseContract.from_dict(
            case,
            owner=f"fixture-test:{binding['subject_element_id']}",
        )
        container[selector] = {
            "schema_version": "worldguard.external_test_check.v1",
            "check_id": existing.get("check_id", f"check:{binding['resource_id']}"),
            "target_id": blueprint["target_id"],
            "target_revision": blueprint["target_revision"],
            "claim_boundary": blueprint["declared_boundary"],
            "subject_element_id": binding["subject_element_id"],
            "owner_id": binding["owner"],
            "source_id": binding["resource_id"],
            "producer_id": binding["provider_id"],
            "producer_version": binding["provider_version"],
            "freshness_status": "current",
            "execution_mode": "current_domain_owner",
            "behavior_case_id": case["case_id"],
            "behavior_case_fingerprint": parsed_case.case_fingerprint,
            "inputs": deepcopy(case["inputs"]),
            "oracle": {
                "oracle_id": case["oracle_id"],
                "expected_output": deepcopy(case["expected_output"]),
                "expected_post_state": deepcopy(case["post_state"]),
                "expected_effects": deepcopy(case["effects"]),
                "expected_terminal_status": "PASS",
            },
        }
    for path, container in sorted(containers.items(), key=lambda row: str(row[0])):
        _write_json(path, container)


def _refresh_input_fingerprints(blueprint: dict[str, Any]) -> None:
    for input_ref in blueprint["commitment_inventory"]["input_refs"]:
        input_ref["content_fingerprint"] = "sha256:" + hashlib.sha256(
            _selected_content(input_ref["locator"])
        ).hexdigest()


def _census_member(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "element_id": row["element_id"],
        "element_kind": row["element_kind"],
        "owner_node_id": row["owner_node_id"],
        "required_guard_owner_id": row["required_guard_owner_id"],
        "support_mode": row["support_mode"],
        "binding_roles": sorted(
            responsibility["role"]
            for responsibility in row["binding_responsibilities"]
        ),
        "not_applicable_roles": sorted(
            responsibility["role"]
            for responsibility in row["not_applicable_responsibilities"]
        ),
        "derivation_ids": sorted(
            responsibility["derivation_id"]
            for responsibility in row["derivation_responsibilities"]
        ),
    }


def _compile_census_source_from_raw_inputs(
    *,
    request_path: Path,
    material_path: Path,
    census_source_path: Path,
) -> dict[str, Any]:
    """Compile the census source without reading a candidate or semantic authority.

    The request owns the detailed denominator.  Raw target material is used to
    prove that every requested material identity exists and that no raw target
    member silently falls outside the request.  Candidate blueprint and
    target-semantic files are deliberately not parameters of this adapter.
    """

    request = _load_json(request_path)
    material = _load_json(material_path)
    source = request.get("object_census")
    if not isinstance(source, dict):
        raise TypeError(f"{request_path} requires one object_census object")
    validated = validate_external_object_census_source(source)
    identity_mismatches = {
        field: {"expected": request.get(field), "observed": source.get(field)}
        for field in ("target_id", "target_revision", "claim_boundary")
        if request.get(field) != source.get(field)
    }
    semantic_request = request.get("semantic_authority")
    if not isinstance(semantic_request, dict):
        raise TypeError(f"{request_path} requires semantic_authority")
    denominator_mismatches = {
        field: {"expected": expected, "observed": observed}
        for field, expected, observed in (
            (
                "required_node_ids",
                semantic_request.get("required_node_ids"),
                validated["required_node_ids"],
            ),
            (
                "required_element_ids",
                semantic_request.get("required_element_ids"),
                validated["required_element_ids"],
            ),
            (
                "required_guard_owner_ids",
                semantic_request.get("required_guard_owner_ids"),
                validated["required_guard_owner_ids"],
            ),
        )
        if expected != observed
    }
    required_material_ids = sorted(
        {
            str(material_id)
            for behavior in request.get("behaviors", [])
            if isinstance(behavior, dict)
            for material_id in behavior.get("required_material_ids", [])
        }
    )
    material_ids = sorted(material)
    if identity_mismatches or denominator_mismatches or required_material_ids != material_ids:
        raise ValueError(
            "raw request/target object-census discovery did not close: "
            + json.dumps(
                {
                    "identity_mismatches": identity_mismatches,
                    "denominator_mismatches": denominator_mismatches,
                    "required_material_ids": required_material_ids,
                    "observed_material_ids": material_ids,
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    _write_json(census_source_path, source)
    return source


def _append_census_source_input(
    *,
    blueprint: dict[str, Any],
    census_source_path: Path,
) -> None:
    blueprint["commitment_inventory"]["input_refs"].append(
        {
            "input_id": (
                f"object-census-source:{blueprint['target_id']}:"
                f"{blueprint['target_revision']}"
            ),
            "input_kind": "target_object_census_source",
            "observation_mode": "local_content",
            "locator": census_source_path.relative_to(FIXTURE_ROOT).as_posix(),
            "target_id": blueprint["target_id"],
            "target_revision": blueprint["target_revision"],
            "content_fingerprint": ZERO_SHA256,
        }
    )


def _refresh_external_object_census(
    *,
    blueprint: dict[str, Any],
    census_path: Path,
    census_source_path: Path,
) -> None:
    """Sign the raw-input census source after all governed inputs are frozen."""

    input_fingerprints = {
        row["input_kind"]: row["content_fingerprint"]
        for row in blueprint["commitment_inventory"]["input_refs"]
        if row["input_kind"]
        in {
            "request_contract",
            "target_material",
            "target_object_census_source",
            "target_semantic_authority",
        }
    }
    census_source = _load_json(census_source_path)
    signer = runpy.run_path(str(ROOT / "tests/object_census_fixtures.py"))[
        "signed_object_census_from_source"
    ]
    _write_json(
        census_path,
        signer(census_source, input_fingerprints=input_fingerprints),
    )
    blueprint["commitment_inventory"]["input_refs"].append(
        {
            "input_id": (
                f"object-census:{blueprint['target_id']}:"
                f"{blueprint['target_revision']}"
            ),
            "input_kind": "target_object_census_authority",
            "observation_mode": "local_content",
            "locator": census_path.relative_to(FIXTURE_ROOT).as_posix(),
            "target_id": blueprint["target_id"],
            "target_revision": blueprint["target_revision"],
            "content_fingerprint": "sha256:"
            + hashlib.sha256(census_path.read_bytes()).hexdigest(),
        }
    )
    blueprint["commitment_inventory"]["input_refs"] = sorted(
        blueprint["commitment_inventory"]["input_refs"],
        key=lambda row: row["input_id"],
    )


def _refresh_one(
    *,
    blueprint_path: Path,
    request_path: Path,
    material_path: Path,
    authority_path: Path,
    cache_path: Path,
    census_path: Path,
    census_source_path: Path,
    blueprint: dict[str, Any],
    authority: dict[str, Any],
) -> None:
    blueprint.pop("blueprint_fingerprint", None)
    blueprint["commitment_inventory"]["input_refs"] = [
        row
        for row in blueprint["commitment_inventory"]["input_refs"]
        if row["input_kind"]
        not in {
            "target_object_census_authority",
            "target_object_census_source",
        }
    ]
    existing_binding_ids = {
        row["binding_id"] for row in blueprint["bindings"]
    }
    element_ids = {row["element_id"] for row in blueprint["elements"]}
    material_locator = next(
        row["locator"]
        for row in blueprint["commitment_inventory"]["input_refs"]
        if row["input_kind"] == "target_material"
    )
    material_file = material_locator.partition("#")[0]
    for element_id, (binding_id, material_id) in BASE_MATERIAL_BINDINGS.items():
        if element_id in element_ids and binding_id not in existing_binding_ids:
            blueprint["bindings"].append(
                _material_binding(
                    blueprint,
                    element_id=element_id,
                    binding_id=binding_id,
                    material_id=material_id,
                    locator=f"{material_file}#{material_id}",
                )
            )
    if blueprint_path == SEVEN_BLUEPRINT:
        for element_id in sorted(MATRIX_ELEMENT_IDS):
            for role in ("target_material", "evidence", "test_check"):
                binding_id = f"binding:{element_id}:{role}"
                if binding_id not in existing_binding_ids:
                    blueprint["bindings"].append(
                        _matrix_binding(
                            blueprint, element_id=element_id, role=role
                        )
                    )
    blueprint["bindings"] = sorted(
        blueprint["bindings"], key=lambda row: row["binding_id"]
    )
    roles_by_element: dict[str, set[str]] = {}
    for binding in blueprint["bindings"]:
        roles_by_element.setdefault(binding["subject_element_id"], set()).add(
            binding["role"]
        )
    for element in blueprint["elements"]:
        element["required_binding_roles"] = sorted(
            roles_by_element.get(element["element_id"], set())
        )

    census_source = _compile_census_source_from_raw_inputs(
        request_path=request_path,
        material_path=material_path,
        census_source_path=census_source_path,
    )
    if census_source["object_claim_kind"] == "integrated_target":
        _refresh_integrated_external_support_records(blueprint)
    _refresh_binding_content_and_receipts(blueprint)
    _refresh_authority(blueprint, authority)
    _write_json(authority_path, authority)
    _append_census_source_input(
        blueprint=blueprint,
        census_source_path=census_source_path,
    )
    _refresh_input_fingerprints(blueprint)
    _refresh_external_object_census(
        blueprint=blueprint,
        census_path=census_path,
        census_source_path=census_source_path,
    )
    _write_blueprint(blueprint_path, blueprint)

    parsed = WorldBlueprintContract.from_dict(
        {key: value for key, value in blueprint.items() if key != "blueprint_fingerprint"},
        source_root=FIXTURE_ROOT,
    )
    cache = compile_behavior_commitment_inventory_cache(parsed)
    _write_json(cache_path, cache)

    first_report = check_world_blueprint(parsed)
    receipts = {
        row["element_id"]: row["receipt_fingerprint"]
        for row in first_report.native_execution_receipts
    }
    for binding in blueprint["bindings"]:
        if binding["role"] == "native_result":
            binding["receipt_fingerprint"] = receipts[
                binding["subject_element_id"]
            ]
    parsed = WorldBlueprintContract.from_dict(
        {key: value for key, value in blueprint.items() if key != "blueprint_fingerprint"},
        source_root=FIXTURE_ROOT,
    )
    blueprint["blueprint_fingerprint"] = parsed.blueprint_fingerprint
    _write_blueprint(blueprint_path, blueprint)
    final_report = check_world_blueprint(
        WorldBlueprintContract.from_dict(blueprint, source_root=FIXTURE_ROOT)
    )
    if final_report.status != GuardStatus.PASS:
        raise RuntimeError(
            f"{blueprint_path.name} did not close: "
            + ",".join(sorted({gap.code for gap in final_report.gaps}))
        )


def _prepare_seven_guard_validation() -> tuple[dict[str, Any], dict[str, Any]]:
    blueprint = _load_blueprint(SEVEN_BLUEPRINT)
    authority = _load_json(SEVEN_AUTHORITY)
    request = _load_json(SEVEN_REQUEST)
    matrix = _load_json(SEVEN_MATRIX)
    replacements = (
        ("planning workflow revision 1 only", "seven-Guard capability validation revision 1 only"),
        ("planning-workflow", "seven-guard-capability-validation"),
    )
    blueprint = _replace_strings(blueprint, replacements)
    authority = _replace_strings(authority, replacements)
    request = _replace_strings(request, replacements)
    matrix = _replace_strings(matrix, replacements)
    blueprint = _normalize_seven_guard_revision(blueprint)
    authority = _normalize_seven_guard_revision(authority)
    request = _normalize_seven_guard_revision(request)
    matrix = _normalize_seven_guard_revision(matrix)
    request["object_census"] = _raw_request_object_census(
        request,
        source_id=(
            "seven-guard-capability-validation:object-census-source:"
            "validation-revision-1"
        ),
        source_owner_id=(
            "seven-guard-capability-validation-object-census-source-owner"
        ),
        authority_id=(
            "seven-guard-capability-validation:object-census:"
            "validation-revision-1"
        ),
        authority_owner_id=(
            "seven-guard-capability-validation-object-census-owner"
        ),
        discovery_mode="candidate_consistency",
        object_claim_kind="oracle_carrying_capability_fixture",
        members=tuple(
            sorted(
                (*BASE_OBJECT_CENSUS_MEMBERS, *SEVEN_GUARD_MATRIX_CENSUS_MEMBERS),
                key=lambda row: row["element_id"],
            )
        ),
    )

    resource_copies = {
        "target-material.json": "seven-guard-validation-target-material.json",
        "evidence.json": "seven-guard-validation-evidence.json",
        "tests.json": "seven-guard-validation-tests.json",
    }
    for source_name, destination_name in resource_copies.items():
        _write_json(
            SUPPORT_ROOT / destination_name,
            _load_json(SUPPORT_ROOT / source_name),
        )
    for binding in blueprint["bindings"]:
        for source_name, destination_name in resource_copies.items():
            binding["locator"] = binding["locator"].replace(
                f"support/{source_name}", f"support/{destination_name}"
            )
        if binding["role"] == "native_result":
            _, separator, selector = binding["locator"].partition("#")
            binding["locator"] = (
                "support/seven-guard-validation-native-results.json"
                + (f"#{selector}" if separator else "")
            )
    for input_ref in blueprint["commitment_inventory"]["input_refs"]:
        input_ref["locator"] = input_ref["locator"].replace(
            "support/target-material.json",
            "support/seven-guard-validation-target-material.json",
        )

    _refresh_native_semantic_fingerprints(blueprint)
    native_results = {
        binding["locator"].partition("#")[2]: _native_payload(
            next(
                element["native_semantic"]
                for element in blueprint["elements"]
                if element["element_id"] == binding["subject_element_id"]
            )
        )
        for binding in blueprint["bindings"]
        if binding["role"] == "native_result"
    }
    if "" in native_results:
        raise ValueError("every validation native binding requires one selector")
    _write_json(
        SUPPORT_ROOT / "seven-guard-validation-native-results.json",
        native_results,
    )
    _write_json(SEVEN_REQUEST, request)
    _write_json(SEVEN_MATRIX, matrix)
    return blueprint, authority


def _policy_binding(
    *,
    element_id: str,
    binding_id: str,
    role: str,
    resource_id: str,
    locator: str,
    owner: str,
) -> dict[str, Any]:
    native = role == "native_result"
    return {
        "binding_id": binding_id,
        "role": role,
        "subject_element_id": element_id,
        "resource_id": resource_id,
        "owner": owner,
        "locator": locator,
        "provider_id": (
            "worldguard.fixture.native" if native else "worldguard.policy-fixture"
        ),
        "provider_version": "v1",
        "provider_capability_id": (
            "worldguard.native-result.v1"
            if native
            else "worldguard.policy-fixture.json-selector.v1"
        ),
        "observation_mode": "local_content",
        "target_id": "policy-access-execution",
        "target_revision": "policy-revision-1",
        "freshness_status": "current",
        "content_fingerprint": ZERO_SHA256,
        "receipt_fingerprint": ZERO_SHA256,
        "claim_boundary": "field access policy execution revision 1 only",
    }


def _prepare_policy_access_execution() -> tuple[dict[str, Any], dict[str, Any]]:
    """Author a non-planning target from explicit policy material and semantics."""

    source = _load_blueprint(BASE_BLUEPRINT)
    source_elements = {row["element_id"]: row for row in source["elements"]}
    boundary = "field access policy execution revision 1 only"

    request_actor = _replace_strings(
        deepcopy(source_elements["actor_alex"]),
        (
            ("planning workflow revision 1 only", boundary),
            ("actor_alex", "request_actor"),
            ("assign_task_leaf", "evaluate_access_leaf"),
            ("native_actor_alex", "native_request_actor"),
            ("actor_alex_native", "request_actor_native"),
            ("actor_alex_out", "request_actor_out"),
            ("Alex", "Inspector Lee"),
            ("alex", "inspector_lee"),
            ("planning_context_available", "training_record_available"),
            ("complete_plan", "complete_field_inspection"),
            ("assign_task", "request_restricted_access"),
            ("planning actor claim", "policy requester claim"),
        ),
    )
    request_actor["output_ports"][0].update(
        {
            "value_type": "policy_subject_identity",
            "schema_id": "worldguard.port.policy-subject-identity",
        }
    )
    actor_good_case = request_actor["native_semantic"]["task_purpose"][
        "behavior_cases"
    ][0]
    actor_record = next(iter(actor_good_case["inputs"]["beliefs"].values()))
    actor_good_case["inputs"]["beliefs"] = {"inspector_lee": actor_record}

    access_norm = _replace_strings(
        deepcopy(source_elements["authorization_norm"]),
        (
            ("planning workflow revision 1 only", boundary),
            ("authorization_norm", "access_policy_norm"),
            ("authorize_task_leaf", "evaluate_access_leaf"),
            ("native_norm", "native_access_policy_norm"),
            ("norm_native", "access_policy_norm_native"),
            ("actor_alex", "request_actor"),
            ("execute_task", "enter_restricted_zone"),
            ("assignment_authorized", "training_valid"),
            ("task authorization", "restricted-area access"),
            ("authorization semantics", "access-policy semantics"),
            ("authorization", "access-policy decision"),
        ),
    )
    access_norm["dependencies"] = [
        {
            "dependency_id": "dep_access_policy_subject",
            "relation": "depends_on",
            "depends_on_element_id": "request_actor",
        }
    ]
    access_norm["input_ports"][0].update(
        {
            "port_id": "access_policy_norm_in",
            "value_type": "access_request",
            "schema_id": "worldguard.port.access-request",
        }
    )
    access_norm["output_ports"][0].update(
        {
            "port_id": "access_policy_norm_out",
            "value_type": "access_decision",
            "schema_id": "worldguard.port.access-decision",
        }
    )

    decision_state = _replace_strings(
        deepcopy(source_elements["scheduled_state"]),
        (
            ("planning workflow revision 1 only", boundary),
            ("scheduled_state", "policy_decision_state"),
            ("schedule_task_leaf", "policy_root"),
            ("native_scheduled_state", "native_policy_decision_state"),
            ("scheduled_state_native", "policy_decision_state_native"),
            ("scheduled_state_out", "policy_decision_state_out"),
            ("scheduled", "access_approved"),
            ("schedule", "policy decision"),
        ),
    )
    decision_state["dependencies"] = [
        {
            "dependency_id": "dep_policy_decision_norm",
            "relation": "caused_by",
            "depends_on_element_id": "access_policy_norm",
        }
    ]
    decision_state["output_ports"][0].update(
        {
            "value_type": "policy_decision_state_identity",
            "schema_id": "worldguard.port.policy-decision-state-identity",
        }
    )

    _refresh_native_semantic_fingerprints(
        {"elements": [request_actor, access_norm, decision_state]}
    )

    root_node = {
        "node_id": "policy_root",
        "title": "Evaluate one field access policy request",
        "depth": 0,
        "parent_node_id": "",
        "child_node_ids": ["evaluate_access_leaf"],
        "owned_element_ids": ["policy_decision_state"],
        "input_ports": [
            {
                "port_id": "policy_request",
                "value_type": "access_request",
                "schema_id": "worldguard.port.access-request",
                "schema_version": "v1",
                "refines": [],
                "cardinality": "one",
            }
        ],
        "output_ports": [
            {
                "port_id": "policy_decision",
                "value_type": "access_decision",
                "schema_id": "worldguard.port.access-decision",
                "schema_version": "v1",
                "refines": [],
                "cardinality": "one",
            }
        ],
        "child_input_mappings": [
            {
                "mapping_id": "policy_request_to_evaluation",
                "child_node_id": "evaluate_access_leaf",
                "child_input_port_id": "access_request",
                "source_kind": "parent_input",
                "source_id": "policy_root",
                "source_port_id": "policy_request",
            }
        ],
        "element_input_mappings": [],
        "child_output_mappings": [
            {
                "mapping_id": "evaluation_to_policy_root",
                "child_node_id": "evaluate_access_leaf",
                "child_output_port_id": "access_decision_result",
                "disposition": "parent_output",
                "parent_port_id": "policy_decision",
                "reason": "",
            }
        ],
        "output_derivations": [
            {
                "derivation_id": "derive_policy_decision",
                "parent_output_port_id": "policy_decision",
                "sources": [
                    {
                        "source_kind": "child_output",
                        "source_id": "evaluate_access_leaf",
                        "source_port_id": "access_decision_result",
                    }
                ],
            }
        ],
    }
    leaf_node = {
        "node_id": "evaluate_access_leaf",
        "title": "Apply the access norm to the field request",
        "depth": 1,
        "parent_node_id": "policy_root",
        "child_node_ids": [],
        "owned_element_ids": ["access_policy_norm", "request_actor"],
        "input_ports": [
            {
                "port_id": "access_request",
                "value_type": "access_request",
                "schema_id": "worldguard.port.access-request",
                "schema_version": "v1",
                "refines": [],
                "cardinality": "one",
            }
        ],
        "output_ports": [
            {
                "port_id": "access_decision_result",
                "value_type": "access_decision",
                "schema_id": "worldguard.port.access-decision",
                "schema_version": "v1",
                "refines": [],
                "cardinality": "one",
            }
        ],
        "child_input_mappings": [],
        "element_input_mappings": [
            {
                "mapping_id": "access_request_to_norm",
                "element_id": "access_policy_norm",
                "element_input_port_id": "access_policy_norm_in",
                "source_kind": "node_input",
                "source_id": "evaluate_access_leaf",
                "source_port_id": "access_request",
            }
        ],
        "child_output_mappings": [],
        "output_derivations": [
            {
                "derivation_id": "derive_access_decision_result",
                "parent_output_port_id": "access_decision_result",
                "sources": [
                    {
                        "source_kind": "owned_element_output",
                        "source_id": "access_policy_norm",
                        "source_port_id": "access_policy_norm_out",
                    }
                ],
            }
        ],
    }

    material = {
        "policy_subject": {
            "agent_id": "inspector_lee",
            "belief": "training_record_available",
        },
        "policy_rule": {
            "modality": "permitted",
            "subject_id": "request_actor",
            "action": "enter_restricted_zone",
            "condition": "training_valid",
            "condition_value": True,
        },
        "policy_decision_record": {
            "state_id": "access_approved",
            "initial": False,
            "terminal": True,
        },
    }
    evidence = {
        "policy_observation": {
            "evidence_id": "policy-observation-1",
            "observed": True,
            "supports": "access_policy_norm",
        }
    }
    tests = {
        "policy_check": {
            "check_id": "policy-check-v1",
            "inputs": ["request_actor", "enter_restricted_zone", "training_valid"],
            "expected_output": "permitted",
        }
    }
    _write_json(POLICY_MATERIAL, material)
    _write_json(POLICY_EVIDENCE, evidence)
    _write_json(POLICY_TESTS, tests)

    native_results = {
        element["native_semantic"]["native_object_id"]: _native_payload(
            element["native_semantic"]
        )
        for element in (request_actor, access_norm, decision_state)
    }
    _write_json(POLICY_NATIVE_RESULTS, native_results)

    bindings = [
        _policy_binding(
            element_id="request_actor",
            binding_id="request_actor_material",
            role="target_material",
            resource_id="policy_subject",
            locator="support/policy-access-target-material.json#policy_subject",
            owner="policy-source-owner",
        ),
        _policy_binding(
            element_id="request_actor",
            binding_id="request_actor_native",
            role="native_result",
            resource_id="native_request_actor",
            locator="support/policy-access-native-results.json#native_request_actor",
            owner="AgentGuard",
        ),
        _policy_binding(
            element_id="access_policy_norm",
            binding_id="access_policy_norm_material",
            role="target_material",
            resource_id="policy_rule",
            locator="support/policy-access-target-material.json#policy_rule",
            owner="policy-source-owner",
        ),
        _policy_binding(
            element_id="access_policy_norm",
            binding_id="access_policy_norm_evidence",
            role="evidence",
            resource_id="policy_observation",
            locator="support/policy-access-evidence.json#policy_observation",
            owner="policy-evidence-owner",
        ),
        _policy_binding(
            element_id="access_policy_norm",
            binding_id="access_policy_norm_test",
            role="test_check",
            resource_id="policy_check",
            locator="support/policy-access-tests.json#policy_check",
            owner="policy-check-owner",
        ),
        _policy_binding(
            element_id="access_policy_norm",
            binding_id="access_policy_norm_native",
            role="native_result",
            resource_id="native_access_policy_norm",
            locator="support/policy-access-native-results.json#native_access_policy_norm",
            owner="NormGuard",
        ),
        _policy_binding(
            element_id="policy_decision_state",
            binding_id="policy_decision_state_material",
            role="target_material",
            resource_id="policy_decision_record",
            locator=(
                "support/policy-access-target-material.json#"
                "policy_decision_record"
            ),
            owner="policy-source-owner",
        ),
        _policy_binding(
            element_id="policy_decision_state",
            binding_id="policy_decision_state_native",
            role="native_result",
            resource_id="native_policy_decision_state",
            locator=(
                "support/policy-access-native-results.json#"
                "native_policy_decision_state"
            ),
            owner="EventGuard",
        ),
    ]

    blueprint = {
        "schema_version": "worldguard.world_blueprint.v1",
        "blueprint_id": "policy-access-execution-two-level",
        "target_id": "policy-access-execution",
        "target_revision": "policy-revision-1",
        "declared_boundary": boundary,
        "root_node_id": "policy_root",
        "nodes": [root_node, leaf_node],
        "elements": [request_actor, access_norm, decision_state],
        "bindings": bindings,
        "declared_inputs": [
            {
                "input_id": "external_policy_request",
                "node_id": "policy_root",
                "port_id": "policy_request",
            }
        ],
        "declared_outputs": [
            {
                "output_id": "declared_policy_decision",
                "node_id": "policy_root",
                "port_id": "policy_decision",
            }
        ],
        "commitment_inventory": {
            "inventory_id": "policy-access-execution:commitments:policy-revision-1",
            "authority_owner_id": "policy-request-contract-owner",
            "locator": "support/policy-access-behavior-commitments.json",
            "adapter_id": "worldguard.request-contract.commitment-adapter",
            "adapter_version": "v2",
            "adapter_capability_id": "worldguard.behavior-commitment.replay.v2",
            "target_id": "policy-access-execution",
            "target_revision": "policy-revision-1",
            "input_refs": [
                {
                    "input_id": "request:policy-access-execution:policy-revision-1",
                    "input_kind": "request_contract",
                    "observation_mode": "local_content",
                    "locator": "support/policy-access-behavior-request-contract.json",
                    "target_id": "policy-access-execution",
                    "target_revision": "policy-revision-1",
                    "content_fingerprint": ZERO_SHA256,
                },
                {
                    "input_id": (
                        "target-material:policy-access-execution:policy-revision-1"
                    ),
                    "input_kind": "target_material",
                    "observation_mode": "local_content",
                    "locator": "support/policy-access-target-material.json",
                    "target_id": "policy-access-execution",
                    "target_revision": "policy-revision-1",
                    "content_fingerprint": ZERO_SHA256,
                },
                {
                    "input_id": (
                        "target-semantics:policy-access-execution:policy-revision-1"
                    ),
                    "input_kind": "target_semantic_authority",
                    "observation_mode": "local_content",
                    "locator": "support/policy-access-target-semantic-authority.json",
                    "target_id": "policy-access-execution",
                    "target_revision": "policy-revision-1",
                    "content_fingerprint": ZERO_SHA256,
                },
            ],
            "claim_boundary": boundary,
        },
        "declared_gaps": [],
    }

    request_contract = {
        "schema_version": "worldguard.behavior_request_contract.v2",
        "request_id": "policy-access-request:policy-revision-1",
        "authority_owner_id": "policy-request-contract-owner",
        "adapter_id": "worldguard.request-contract.commitment-adapter",
        "adapter_version": "v2",
        "adapter_capability_id": "worldguard.behavior-commitment.replay.v2",
        "target_id": "policy-access-execution",
        "target_revision": "policy-revision-1",
        "claim_boundary": boundary,
        "behaviors": [
            {
                "commitment_id": "commitment:declared-policy-decision",
                "behavior_id": "behavior:evaluate-field-access",
                "output_id": "declared_policy_decision",
                "node_id": "policy_root",
                "port_id": "policy_decision",
                "owner_id": "policy-request-contract-owner",
                "input_ids": ["external_policy_request"],
                "required_contributor_element_ids": ["access_policy_norm"],
                "required_material_ids": [
                    "policy_subject",
                    "policy_rule",
                    "policy_decision_record",
                ],
            }
        ],
        "semantic_authority": {
            "authority_id": (
                "policy-access-execution:target-semantics:policy-revision-1"
            ),
            "authority_owner_id": "policy-target-semantic-authority-owner",
            "required_node_ids": ["evaluate_access_leaf", "policy_root"],
            "required_element_ids": [
                "access_policy_norm",
                "policy_decision_state",
                "request_actor",
            ],
            "required_guard_owner_ids": ["AgentGuard", "EventGuard", "NormGuard"],
        },
    }
    request_contract["object_census"] = _raw_request_object_census(
        request_contract,
        source_id=(
            "policy-access-execution:object-census-source:policy-revision-1"
        ),
        source_owner_id="policy-access-execution-object-census-source-owner",
        authority_id=(
            "policy-access-execution:object-census:policy-revision-1"
        ),
        authority_owner_id="policy-access-execution-object-census-owner",
        discovery_mode="independent_raw_target_request",
        object_claim_kind="integrated_target",
        members=POLICY_OBJECT_CENSUS_MEMBERS,
    )
    _write_json(POLICY_REQUEST, request_contract)

    authority_elements = []
    responsibility = {
        "request_actor": (
            "evaluate_access_leaf",
            "agent",
            "AgentGuard",
            "worldguard.semantic.agent.v1",
        ),
        "access_policy_norm": (
            "evaluate_access_leaf",
            "norm",
            "NormGuard",
            "worldguard.semantic.norm.v1",
        ),
        "policy_decision_state": (
            "policy_root",
            "state",
            "EventGuard",
            "worldguard.semantic.event.v1",
        ),
    }
    elements_by_id = {row["element_id"]: row for row in blueprint["elements"]}
    for element_id, (
        owner_node_id,
        element_kind,
        guard_owner,
        executor_id,
    ) in responsibility.items():
        authority_elements.append(
            {
                "element_id": element_id,
                "owner_node_id": owner_node_id,
                "element_kind": element_kind,
                "required_guard_owner_id": guard_owner,
                "required_executor_id": executor_id,
                "required_executor_version": "v1",
                "native_semantic": deepcopy(
                    elements_by_id[element_id]["native_semantic"]
                ),
                "binding_responsibilities": [],
                "not_applicable_responsibilities": [],
                "support_mode": "direct",
                "derivation_responsibilities": [],
            }
        )

    authority = {
        "schema_version": "worldguard.target_semantic_authority.v2",
        "authority_id": "policy-access-execution:target-semantics:policy-revision-1",
        "authority_owner_id": "policy-target-semantic-authority-owner",
        "target_id": "policy-access-execution",
        "target_revision": "policy-revision-1",
        "claim_boundary": boundary,
        "required_node_ids": ["evaluate_access_leaf", "policy_root"],
        "elements": authority_elements,
        "material_assertions": [
            {
                "assertion_id": "policy-subject-agent",
                "source_input_kind": "target_material",
                "source_path": ["policy_subject", "agent_id"],
                "target_element_id": "request_actor",
                "semantic_path": ["semantic_fields", "agent_id"],
            },
            {
                "assertion_id": "policy-subject-belief",
                "source_input_kind": "target_material",
                "source_path": ["policy_subject", "belief"],
                "target_element_id": "request_actor",
                "semantic_path": ["semantic_fields", "beliefs", 0],
            },
            {
                "assertion_id": "policy-rule-modality",
                "source_input_kind": "target_material",
                "source_path": ["policy_rule", "modality"],
                "target_element_id": "access_policy_norm",
                "semantic_path": ["semantic_fields", "modality"],
            },
            {
                "assertion_id": "policy-rule-subject",
                "source_input_kind": "target_material",
                "source_path": ["policy_rule", "subject_id"],
                "target_element_id": "access_policy_norm",
                "semantic_path": ["semantic_fields", "subject_id"],
            },
            {
                "assertion_id": "policy-rule-action",
                "source_input_kind": "target_material",
                "source_path": ["policy_rule", "action"],
                "target_element_id": "access_policy_norm",
                "semantic_path": ["semantic_fields", "action"],
            },
            {
                "assertion_id": "policy-rule-condition",
                "source_input_kind": "target_material",
                "source_path": ["policy_rule", "condition"],
                "target_element_id": "access_policy_norm",
                "semantic_path": ["semantic_fields", "condition"],
            },
            {
                "assertion_id": "policy-rule-condition-value",
                "source_input_kind": "target_material",
                "source_path": ["policy_rule", "condition_value"],
                "target_element_id": "access_policy_norm",
                "semantic_path": ["semantic_fields", "facts", 0, "value"],
            },
            {
                "assertion_id": "policy-decision-state",
                "source_input_kind": "target_material",
                "source_path": ["policy_decision_record", "state_id"],
                "target_element_id": "policy_decision_state",
                "semantic_path": ["semantic_fields", "state_id"],
            },
            {
                "assertion_id": "policy-decision-initial",
                "source_input_kind": "target_material",
                "source_path": ["policy_decision_record", "initial"],
                "target_element_id": "policy_decision_state",
                "semantic_path": ["semantic_fields", "initial"],
            },
            {
                "assertion_id": "policy-decision-terminal",
                "source_input_kind": "target_material",
                "source_path": ["policy_decision_record", "terminal"],
                "target_element_id": "policy_decision_state",
                "semantic_path": ["semantic_fields", "terminal"],
            },
        ],
    }
    return blueprint, authority


def main() -> int:
    base_blueprint = _load_blueprint(BASE_BLUEPRINT)
    base_authority = _load_json(BASE_AUTHORITY)
    base_request = _load_json(BASE_REQUEST)
    base_request["object_census"] = _raw_request_object_census(
        base_request,
        source_id="planning-workflow:object-census-source:revision-1",
        source_owner_id="planning-workflow-object-census-source-owner",
        authority_id="planning-workflow:object-census:revision-1",
        authority_owner_id="planning-workflow-object-census-owner",
        discovery_mode="independent_raw_target_request",
        object_claim_kind="integrated_target",
        members=BASE_OBJECT_CENSUS_MEMBERS,
    )
    _write_json(BASE_REQUEST, base_request)
    _refresh_one(
        blueprint_path=BASE_BLUEPRINT,
        request_path=BASE_REQUEST,
        material_path=BASE_MATERIAL,
        authority_path=BASE_AUTHORITY,
        cache_path=BASE_CACHE,
        census_path=BASE_CENSUS,
        census_source_path=BASE_CENSUS_SOURCE,
        blueprint=base_blueprint,
        authority=base_authority,
    )

    seven_blueprint, seven_authority = _prepare_seven_guard_validation()
    _refresh_one(
        blueprint_path=SEVEN_BLUEPRINT,
        request_path=SEVEN_REQUEST,
        material_path=SEVEN_MATERIAL,
        authority_path=SEVEN_AUTHORITY,
        cache_path=SEVEN_CACHE,
        census_path=SEVEN_CENSUS,
        census_source_path=SEVEN_CENSUS_SOURCE,
        blueprint=seven_blueprint,
        authority=seven_authority,
    )

    policy_blueprint, policy_authority = _prepare_policy_access_execution()
    _refresh_one(
        blueprint_path=POLICY_BLUEPRINT,
        request_path=POLICY_REQUEST,
        material_path=POLICY_MATERIAL,
        authority_path=POLICY_AUTHORITY,
        cache_path=POLICY_CACHE,
        census_path=POLICY_CENSUS,
        census_source_path=POLICY_CENSUS_SOURCE,
        blueprint=policy_blueprint,
        authority=policy_authority,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
