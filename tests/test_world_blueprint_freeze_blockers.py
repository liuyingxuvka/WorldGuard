from __future__ import annotations

import json
import shutil
from copy import deepcopy
from pathlib import Path

import yaml

from worldguard.blueprint import (
    WorldBlueprintContract,
    check_world_blueprint,
)
from worldguard.semantic import fingerprint_mesh


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/world_blueprint/planning_workflow_three_level.yaml"


def _payload() -> dict:
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


def _current(payload: dict, *, source_root: Path | None = None) -> WorldBlueprintContract:
    payload = deepcopy(payload)
    payload.pop("blueprint_fingerprint", None)
    return WorldBlueprintContract.from_dict(
        payload,
        source_root=source_root or FIXTURE.parent,
    )


def test_independent_commitment_inventory_blocks_caller_shrunk_output_graph() -> None:
    payload = _payload()
    root = next(node for node in payload["nodes"] if node["node_id"] == "plan_root")
    governance = next(
        row
        for row in root["child_output_mappings"]
        if row["child_node_id"] == "governance_layer"
    )
    governance.update(
        {
            "disposition": "internal_terminal",
            "parent_port_id": "",
            "reason": "caller removed the public governance output",
        }
    )
    root_derivation = next(
        row
        for row in root["output_derivations"]
        if row["parent_output_port_id"] == "root_plan_outcome"
    )
    root_derivation["sources"] = [
        row
        for row in root_derivation["sources"]
        if row["source_id"] != "governance_layer"
    ]
    for element_id in ("authorization_norm", "resource_reservation"):
        element = next(
            row for row in payload["elements"] if row["element_id"] == element_id
        )
        element["contributes_to_claim"] = False
        element["required_binding_roles"] = []
    payload["bindings"] = [
        row
        for row in payload["bindings"]
        if row["subject_element_id"]
        not in {"authorization_norm", "resource_reservation"}
        or row["role"] == "native_result"
    ]

    report = check_world_blueprint(_current(payload))

    assert report.native_domain_qualified is False
    assert any(
        gap.code == "WORLD_BLUEPRINT_REQUIRED_COMMITMENT_OUTPUT_MISSING"
        and gap.port_id == "root_plan_outcome"
        for gap in report.gaps
    )


def test_caller_cannot_shrink_blueprint_and_cached_commitment_authority_together(
    tmp_path: Path,
) -> None:
    payload = _payload()
    shutil.copytree(FIXTURE.parent / "support", tmp_path / "support")
    root = next(node for node in payload["nodes"] if node["node_id"] == "plan_root")
    governance = next(
        row
        for row in root["child_output_mappings"]
        if row["child_node_id"] == "governance_layer"
    )
    governance.update(
        {
            "disposition": "internal_terminal",
            "parent_port_id": "",
            "reason": "caller removed the public governance output",
        }
    )
    root_derivation = next(
        row
        for row in root["output_derivations"]
        if row["parent_output_port_id"] == "root_plan_outcome"
    )
    root_derivation["sources"] = [
        row
        for row in root_derivation["sources"]
        if row["source_id"] != "governance_layer"
    ]
    for element_id in ("authorization_norm", "resource_reservation"):
        element = next(
            row for row in payload["elements"] if row["element_id"] == element_id
        )
        element["contributes_to_claim"] = False
        element["required_binding_roles"] = []
    payload["bindings"] = [
        row
        for row in payload["bindings"]
        if row["subject_element_id"]
        not in {"authorization_norm", "resource_reservation"}
        or row["role"] == "native_result"
    ]

    authority_path = tmp_path / "support" / "behavior-commitments.json"
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    authority["adapter_result"]["commitments"][0][
        "required_contributor_element_ids"
    ] = ["assignment_transition", "schedule_transition"]
    authority["terminal_receipt"]["result_fingerprint"] = (
        "sha256:" + fingerprint_mesh(authority["adapter_result"])
    )
    caller_receipt_payload = {
        key: value
        for key, value in authority["terminal_receipt"].items()
        if key != "receipt_fingerprint"
    }
    authority["terminal_receipt"]["receipt_fingerprint"] = (
        "sha256:" + fingerprint_mesh(caller_receipt_payload)
    )
    authority_path.write_text(json.dumps(authority), encoding="utf-8")

    report = check_world_blueprint(_current(payload, source_root=tmp_path))

    assert report.native_domain_qualified is False
    assert any(
        gap.code in {
            "WORLD_BLUEPRINT_COMMITMENT_ADAPTER_RESULT_MISMATCH",
            "WORLD_BLUEPRINT_REQUIRED_COMMITMENT_OUTPUT_MISSING",
        }
        and gap.port_id == "root_plan_outcome"
        for gap in report.gaps
    )


def test_commitment_adapter_requires_replayable_exact_current_inputs() -> None:
    cases = {
        "external": (
            lambda ref: ref.update({"observation_mode": "external_identity"}),
            "commitment_adapter_input_not_replayable",
        ),
        "wrong-content": (
            lambda ref: ref.update({"content_fingerprint": "sha256:" + "0" * 64}),
            "commitment_adapter_input_content_mismatch",
        ),
    }
    for mutate, expected_reason in cases.values():
        payload = _payload()
        request_ref = next(
            row
            for row in payload["commitment_inventory"]["input_refs"]
            if row["input_kind"] == "request_contract"
        )
        mutate(request_ref)

        report = check_world_blueprint(_current(payload))

        gap = next(
            row
            for row in report.gaps
            if row.code == "WORLD_BLUEPRINT_COMMITMENT_INVENTORY_NOT_CURRENT"
        )
        assert gap.evidence["reason"] == expected_reason
        assert report.native_domain_qualified is False


def test_commitment_adapter_requires_registered_capability() -> None:
    payload = _payload()
    payload["commitment_inventory"]["adapter_capability_id"] = (
        "caller.behavior-commitment.replay.v1"
    )

    report = check_world_blueprint(_current(payload))

    gap = next(
        row
        for row in report.gaps
        if row.code == "WORLD_BLUEPRINT_COMMITMENT_INVENTORY_NOT_CURRENT"
    )
    assert gap.evidence["reason"] == "commitment_adapter_unregistered"
    assert report.native_domain_qualified is False


def test_native_receipts_are_issued_by_current_domain_owners_not_blueprint() -> None:
    report = check_world_blueprint(_current(_payload()))

    executed = [
        row
        for row in report.native_execution_receipts
        if row["execution_disposition"] == "executed"
    ]
    not_applicable = [
        row
        for row in report.native_execution_receipts
        if row["execution_disposition"] == "not_applicable"
    ]
    assert executed
    assert not_applicable
    assert all(row["owner_guard"].endswith("Guard") for row in executed)
    assert all(
        row["executor_id"].startswith("worldguard.semantic.") for row in executed
    )
    assert all(
        row["executor_id"] != "worldguard.blueprint.native_semantic.v1"
        for row in report.native_execution_receipts
    )
    assert all(
        row["request_fingerprint"].startswith("sha256:")
        and row["input_fingerprint"].startswith("sha256:")
        and row["result_fingerprint"].startswith("sha256:")
        and row["terminal_status"] in {"PASS", "NOT_APPLICABLE"}
        for row in report.native_execution_receipts
    )


def test_caller_self_signed_provider_result_cannot_close_provider_content(
    tmp_path: Path,
) -> None:
    payload = _payload()
    binding = next(
        row
        for row in payload["bindings"]
        if row["binding_id"] == "assignment_evidence"
    )
    binding.update(
        {
            "observation_mode": "provider_content",
            "locator": "provider-results.json#assignment_evidence",
            "provider_id": "caller.named.provider",
            "provider_version": "pretend-v1",
            "provider_capability_id": "caller.claimed.capability",
        }
    )
    result = {
        "schema_version": "worldguard.blueprint_provider_observation.v1",
        "observation_id": "observation:assignment_evidence",
        "binding_id": binding["binding_id"],
        "role": binding["role"],
        "subject_element_id": binding["subject_element_id"],
        "owner": binding["owner"],
        "observation_mode": "provider_content",
        "provider_id": binding["provider_id"],
        "provider_version": binding["provider_version"],
        "provider_capability_id": binding["provider_capability_id"],
        "target_id": binding["target_id"],
        "target_revision": binding["target_revision"],
        "resource_id": binding["resource_id"],
        "content_fingerprint": binding["content_fingerprint"],
        "claim_boundary": binding["claim_boundary"],
        "status": "current",
    }
    receipt = "sha256:" + fingerprint_mesh(result)
    result["receipt_fingerprint"] = receipt
    binding["receipt_fingerprint"] = receipt
    shutil.copytree(FIXTURE.parent / "support", tmp_path / "support")
    (tmp_path / "provider-results.json").write_text(
        json.dumps({"assignment_evidence": result}),
        encoding="utf-8",
    )

    report = check_world_blueprint(_current(payload, source_root=tmp_path))

    provider_gap = next(
        gap
        for gap in report.gaps
        if gap.code == "WORLD_BLUEPRINT_PROVIDER_CONTENT_NOT_CURRENT"
        and gap.binding_id == "assignment_evidence"
    )
    assert provider_gap.evidence["reason"] in {
        "provider_capability_unregistered",
        "provider_execution_attestation_missing",
    }
    assert report.native_domain_qualified is False


def test_every_element_output_requires_consumption_derivation_or_terminal() -> None:
    payload = _payload()
    element = next(
        row
        for row in payload["elements"]
        if row["element_id"] == "assignment_transition"
    )
    element["output_ports"].append(
        {
            "port_id": "orphan_probe_out",
            "value_type": "plan_result",
            "schema_id": "worldguard.port.plan-result",
            "schema_version": "v1",
            "refines": [],
            "cardinality": "one",
        }
    )

    report = check_world_blueprint(_current(payload))

    assert any(
        gap.code == "WORLD_BLUEPRINT_ELEMENT_OUTPUT_UNDISPOSITIONED"
        and gap.element_id == "assignment_transition"
        and gap.port_id == "orphan_probe_out"
        for gap in report.gaps
    )


def test_port_compatibility_uses_schema_identity_not_value_type_text() -> None:
    payload = _payload()
    root = next(node for node in payload["nodes"] if node["node_id"] == "plan_root")
    allocation = next(
        node for node in payload["nodes"] if node["node_id"] == "allocation_layer"
    )
    root_input = next(
        port for port in root["input_ports"] if port["port_id"] == "root_plan_request"
    )
    child_input = next(
        port
        for port in allocation["input_ports"]
        if port["port_id"] == "allocation_request"
    )
    root_input.update(
        {
            "schema_id": "worldguard.port.plan-request",
            "schema_version": "v1",
            "refines": [],
        }
    )
    child_input.update(
        {
            "schema_id": "worldguard.port.unrelated-request",
            "schema_version": "v1",
            "refines": [],
        }
    )
    assert root_input["value_type"] == child_input["value_type"]

    report = check_world_blueprint(_current(payload))

    assert any(
        gap.code == "WORLD_BLUEPRINT_CHILD_INPUT_PORT_INCOMPATIBLE"
        and gap.port_id == "allocation_request"
        and gap.evidence["compatibility_relation"] == "incompatible"
        for gap in report.gaps
    )
