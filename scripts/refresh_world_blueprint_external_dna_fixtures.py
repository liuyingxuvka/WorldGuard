"""Refresh the maintained external-object DNA fixtures through current owners.

This is an author-side fixture compiler: it writes the three blueprint fixtures, their
bindings, support records and native results, then checks that each fixture passes.
It is not an alternate runtime qualification path.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from worldguard.blueprint import (
    BehaviorCaseContract,
    BlueprintBinding,
    GuardStatus,
    WorldBlueprintContract,
    _binding_receipt_fingerprint,
    check_world_blueprint,
)
from worldguard.semantic import fingerprint_mesh


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests/fixtures/world_blueprint"
SUPPORT_ROOT = FIXTURE_ROOT / "support"
ZERO_SHA256 = "sha256:" + "0" * 64

BASE_BLUEPRINT = FIXTURE_ROOT / "planning_workflow_three_level.yaml"
BASE_MATERIAL = SUPPORT_ROOT / "target-material.json"

SEVEN_BLUEPRINT = FIXTURE_ROOT / "seven_guard_portable_handoff.json"
SEVEN_MATERIAL = SUPPORT_ROOT / "seven-guard-validation-target-material.json"
SEVEN_MATRIX = FIXTURE_ROOT / "seven_guard_native_owner_matrix.json"

POLICY_BLUEPRINT = FIXTURE_ROOT / "policy_access_execution.yaml"
POLICY_MATERIAL = SUPPORT_ROOT / "policy-access-target-material.json"
POLICY_EVIDENCE = SUPPORT_ROOT / "policy-access-evidence.json"
POLICY_TESTS = SUPPORT_ROOT / "policy-access-tests.json"
POLICY_NATIVE_RESULTS = SUPPORT_ROOT / "policy-access-native-results.json"

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
        if path_text.endswith(".json"):
            return _canonical_json_bytes(json.loads(content.decode("utf-8")))
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
            continue
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




def _refresh_one(
    *,
    blueprint_path: Path,
    material_path: Path,
    blueprint: dict[str, Any],
) -> None:
    blueprint.pop("blueprint_fingerprint", None)
    existing_binding_ids = {
        row["binding_id"] for row in blueprint["bindings"]
    }
    element_ids = {row["element_id"] for row in blueprint["elements"]}
    material_file = material_path.relative_to(FIXTURE_ROOT).as_posix()
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

    _refresh_integrated_external_support_records(blueprint)
    _refresh_binding_content_and_receipts(blueprint)
    _write_blueprint(blueprint_path, blueprint)

    parsed = WorldBlueprintContract.from_dict(
        {key: value for key, value in blueprint.items() if key != "blueprint_fingerprint"},
        source_root=FIXTURE_ROOT,
    )
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


def _prepare_seven_guard_validation() -> dict[str, Any]:
    blueprint = _load_blueprint(SEVEN_BLUEPRINT)
    matrix = _load_json(SEVEN_MATRIX)
    replacements = (
        ("planning workflow revision 1 only", "seven-Guard capability validation revision 1 only"),
        ("planning-workflow", "seven-guard-capability-validation"),
    )
    blueprint = _replace_strings(blueprint, replacements)
    matrix = _replace_strings(matrix, replacements)
    blueprint = _normalize_seven_guard_revision(blueprint)
    matrix = _normalize_seven_guard_revision(matrix)

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
    _write_json(SEVEN_MATRIX, matrix)
    return blueprint


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


def _prepare_policy_access_execution() -> dict[str, Any]:
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
        "declared_gaps": [],
    }

    return blueprint


def main() -> int:
    _refresh_one(
        blueprint_path=BASE_BLUEPRINT,
        material_path=BASE_MATERIAL,
        blueprint=_load_blueprint(BASE_BLUEPRINT),
    )
    _refresh_one(
        blueprint_path=SEVEN_BLUEPRINT,
        material_path=SEVEN_MATERIAL,
        blueprint=_prepare_seven_guard_validation(),
    )
    _refresh_one(
        blueprint_path=POLICY_BLUEPRINT,
        material_path=POLICY_MATERIAL,
        blueprint=_prepare_policy_access_execution(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
