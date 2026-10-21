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
