from __future__ import annotations

import json
import hashlib
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
import yaml
import worldguard.blueprint as blueprint_module

from worldguard.blueprint import (
    WORLD_ELEMENT_KINDS,
    BlueprintError,
    BlueprintLayerStatus,
    TargetSemanticAuthority,
    WorldBlueprintContract,
    _binding_receipt_fingerprint,
    _provider_capability_registration,
    _provider_observation_expected,
    _target_semantic_census_members,
    check_world_blueprint,
    compile_behavior_commitment_inventory_cache,
    load_world_blueprint,
)
from worldguard.semantic import fingerprint_mesh
from worldguard.status import GuardStatus

from tests.object_census_fixtures import signed_object_census


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/world_blueprint/planning_workflow_three_level.yaml"


def _payload() -> dict:
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


def _current(payload: dict) -> WorldBlueprintContract:
    payload = deepcopy(payload)
    payload.pop("blueprint_fingerprint", None)
    return WorldBlueprintContract.from_dict(payload, source_root=FIXTURE.parent)


def _current_at(payload: dict, source_root: Path) -> WorldBlueprintContract:
    payload = deepcopy(payload)
    payload.pop("blueprint_fingerprint", None)
    return WorldBlueprintContract.from_dict(payload, source_root=source_root)


def _renew_binding_receipt(payload: dict, binding_id: str, source_root: Path) -> None:
    contract = _current_at(payload, source_root)
    binding = next(row for row in contract.bindings if row.binding_id == binding_id)
    next(
        row for row in payload["bindings"] if row["binding_id"] == binding_id
    )["receipt_fingerprint"] = _binding_receipt_fingerprint(binding)


def _renew_native_semantic_fingerprint(semantic: dict) -> None:
    identity = {
        key: value
        for key, value in semantic.items()
        if key not in {"content_fingerprint", "task_purpose"}
    }
    semantic["content_fingerprint"] = "sha256:" + fingerprint_mesh(identity)








def test_three_level_non_code_blueprint_closes_to_declared_native_depth() -> None:
    blueprint = load_world_blueprint(FIXTURE)
    report = check_world_blueprint(blueprint)

    assert report.status == GuardStatus.PASS
    assert report.native_domain_qualified is True
    assert report.partial_model_usable is True
    assert len(report.native_execution_receipts) == len(blueprint.elements) == 13
    assert {row["terminal_status"] for row in report.native_execution_receipts} == {
        "PASS",
        "NOT_APPLICABLE",
    }
    assert all(
        row["schema_version"] == "worldguard.blueprint_native_execution.v2"
        and row["receipt_fingerprint"].startswith("sha256:")
        for row in report.native_execution_receipts
    )
    assert report.deepest_continuously_proven_layer == 2
    assert report.first_unresolved_layer is None
    assert [row.status for row in report.depth_layers] == [
        BlueprintLayerStatus.PROVEN,
        BlueprintLayerStatus.PROVEN,
        BlueprintLayerStatus.PROVEN,
    ]
    serialized = json.dumps(blueprint.to_dict(), sort_keys=True).lower()
    assert all(kind in WORLD_ELEMENT_KINDS for kind in {item.kind for item in blueprint.elements})
    assert not any(term in serialized for term in ('"module"', '"function"', '"class"', '"python"'))












def test_round_trip_and_report_identity_are_stable(tmp_path: Path) -> None:
    first = load_world_blueprint(FIXTURE)
    json_path = tmp_path / "planning-workflow.json"
    shutil.copytree(FIXTURE.parent / "support", tmp_path / "support")
    json_path.write_text(json.dumps(first.to_dict()), encoding="utf-8")
    second = load_world_blueprint(json_path)

    assert first.to_dict() == second.to_dict()
    assert first.blueprint_fingerprint == second.blueprint_fingerprint
    assert (
        check_world_blueprint(first).report_fingerprint
        == check_world_blueprint(second).report_fingerprint
    )


def test_duplicate_element_ownership_and_missing_owner_are_visible() -> None:
    duplicate = _payload()
    next(
        node for node in duplicate["nodes"] if node["node_id"] == "schedule_task_leaf"
    )["owned_element_ids"].append("assignment_transition")
    duplicate_report = check_world_blueprint(_current(duplicate))
    assert any(
        gap.code == "WORLD_BLUEPRINT_ELEMENT_OWNERSHIP_INVALID"
        and gap.element_id == "assignment_transition"
        for gap in duplicate_report.gaps
    )

    missing = _payload()
    next(
        node for node in missing["nodes"] if node["node_id"] == "assign_task_leaf"
    )["owned_element_ids"].remove("assignment_transition")
    missing_report = check_world_blueprint(_current(missing))
    assert any(
        gap.code == "WORLD_BLUEPRINT_ELEMENT_OWNERSHIP_INVALID"
        and gap.element_id == "assignment_transition"
        for gap in missing_report.gaps
    )


def test_hierarchy_cycle_depth_mismatch_and_orphan_fail_closed() -> None:
    payload = _payload()
    root = next(node for node in payload["nodes"] if node["node_id"] == "plan_root")
    allocation = next(
        node for node in payload["nodes"] if node["node_id"] == "allocation_layer"
    )
    leaf = next(
        node for node in payload["nodes"] if node["node_id"] == "assign_task_leaf"
    )
    root["child_node_ids"].remove("allocation_layer")
    allocation["parent_node_id"] = "assign_task_leaf"
    allocation["child_node_ids"] = ["assign_task_leaf"]
    leaf["child_node_ids"] = ["allocation_layer"]

    report = check_world_blueprint(_current(payload))
    codes = {gap.code for gap in report.gaps}
    assert "WORLD_BLUEPRINT_HIERARCHY_CYCLE" in codes
    assert "WORLD_BLUEPRINT_NODE_ORPHAN" in codes
    assert "WORLD_BLUEPRINT_DEPTH_MISMATCH" in codes
    assert report.status == GuardStatus.FAIL


def test_child_output_must_have_one_compatible_parent_mapping() -> None:
    missing = _payload()
    allocation = next(
        node for node in missing["nodes"] if node["node_id"] == "allocation_layer"
    )
    allocation["child_output_mappings"] = []
    report = check_world_blueprint(_current(missing))
    gap = next(
        gap
        for gap in report.gaps
        if gap.code == "WORLD_BLUEPRINT_CHILD_OUTPUT_MAPPING_CARDINALITY"
    )
    assert gap.node_id == "assign_task_leaf"
    assert gap.port_id == "assign_task_result"

    incompatible = _payload()
    allocation = next(
        node for node in incompatible["nodes"] if node["node_id"] == "allocation_layer"
    )
    allocation["output_ports"][0]["schema_id"] = "worldguard.port.resource-result"
    incompatible_report = check_world_blueprint(_current(incompatible))
    assert any(
        gap.code in {
            "WORLD_BLUEPRINT_PORT_INCOMPATIBLE",
            "WORLD_BLUEPRINT_DERIVATION_PORT_INCOMPATIBLE",
        }
        for gap in incompatible_report.gaps
    )


def test_every_node_and_element_input_has_one_typed_source_owner() -> None:
    missing_child = _payload()
    root = next(
        node for node in missing_child["nodes"] if node["node_id"] == "plan_root"
    )
    root["child_input_mappings"] = [
        row
        for row in root["child_input_mappings"]
        if row["child_node_id"] != "allocation_layer"
    ]
    report = check_world_blueprint(_current(missing_child))
    assert any(
        gap.code == "WORLD_BLUEPRINT_NODE_INPUT_SOURCE_CARDINALITY"
        and gap.node_id == "allocation_layer"
        and gap.port_id == "allocation_request"
        for gap in report.gaps
    )

    unknown_source = _payload()
    root = next(
        node for node in unknown_source["nodes"] if node["node_id"] == "plan_root"
    )
    root["child_input_mappings"][0]["source_port_id"] = "missing_parent_input"
    report = check_world_blueprint(_current(unknown_source))
    assert any(
        gap.code == "WORLD_BLUEPRINT_CHILD_INPUT_SOURCE_UNKNOWN"
        for gap in report.gaps
    )

    incompatible = _payload()
    root = next(
        node for node in incompatible["nodes"] if node["node_id"] == "plan_root"
    )
    root["input_ports"][0]["cardinality"] = "many"
    report = check_world_blueprint(_current(incompatible))
    assert any(
        gap.code == "WORLD_BLUEPRINT_CHILD_INPUT_PORT_INCOMPATIBLE"
        for gap in report.gaps
    )

    missing_element = _payload()
    leaf = next(
        node
        for node in missing_element["nodes"]
        if node["node_id"] == "assign_task_leaf"
    )
    leaf["element_input_mappings"] = []
    report = check_world_blueprint(_current(missing_element))
    assert any(
        gap.code == "WORLD_BLUEPRINT_ELEMENT_INPUT_SOURCE_CARDINALITY"
        and gap.element_id == "assignment_transition"
        for gap in report.gaps
    )


def test_declared_external_input_is_an_exact_source_not_a_label() -> None:
    missing = _payload()
    missing["declared_inputs"] = []
    report = check_world_blueprint(_current(missing))
    assert any(
        gap.code == "WORLD_BLUEPRINT_NODE_INPUT_SOURCE_CARDINALITY"
        and gap.port_id == "root_plan_request"
        for gap in report.gaps
    )

    duplicate = _payload()
    duplicate["declared_inputs"].append(
        {
            "input_id": "second_external_plan_request",
            "node_id": "plan_root",
            "port_id": "root_plan_request",
        }
    )
    report = check_world_blueprint(_current(duplicate))
    assert any(
        gap.code == "WORLD_BLUEPRINT_NODE_INPUT_SOURCE_CARDINALITY"
        and gap.evidence["source_owner_ids"]
        == ["external_plan_request", "second_external_plan_request"]
        for gap in report.gaps
    )


def test_missing_test_binding_stops_continuous_depth_at_leaf() -> None:
    payload = _payload()
    payload["bindings"] = [
        row for row in payload["bindings"] if row["binding_id"] != "assignment_test"
    ]

    report = check_world_blueprint(_current(payload))

    gap = next(
        gap
        for gap in report.gaps
        if gap.code == "WORLD_BLUEPRINT_REQUIRED_BINDING_MISSING"
        and gap.element_id == "assignment_transition"
    )
    assert gap.required_role == "test_check"
    assert report.deepest_continuously_proven_layer == 1
    assert report.first_unresolved_layer == 2
    assert report.partial_model_usable is True


def test_binding_roles_do_not_substitute_for_each_other() -> None:
    payload = _payload()
    evidence = next(
        row for row in payload["bindings"] if row["binding_id"] == "assignment_evidence"
    )
    evidence["role"] = "test_check"

    report = check_world_blueprint(_current(payload))
    codes = {gap.code for gap in report.gaps if gap.element_id == "assignment_transition"}
    assert "WORLD_BLUEPRINT_BINDING_ROLE_DUPLICATE" in codes
    assert "WORLD_BLUEPRINT_REQUIRED_BINDING_MISSING" in codes


def test_declared_output_graph_owns_claim_contributor_and_binding_denominator() -> None:
    payload = _payload()
    claim_element_ids = {
        "assignment_transition",
        "schedule_transition",
        "resource_reservation",
        "authorization_norm",
    }
    for element in payload["elements"]:
        if element["element_id"] in claim_element_ids:
            element["contributes_to_claim"] = True
            element["required_binding_roles"] = ["native_result"]
    payload["bindings"] = [
        row
        for row in payload["bindings"]
        if row["subject_element_id"] not in claim_element_ids
        or row["role"] == "native_result"
    ]

    report = check_world_blueprint(_current(payload))

    codes = {gap.code for gap in report.gaps}
    assert "WORLD_BLUEPRINT_BINDING_ROLE_ASSERTION_MISMATCH" in codes
    missing = {
        (gap.element_id, gap.required_role)
        for gap in report.gaps
        if gap.code == "WORLD_BLUEPRINT_REQUIRED_BINDING_MISSING"
    }
    assert {
        (element_id, role)
        for element_id in claim_element_ids
        for role in {"target_material", "evidence", "test_check"}
    } <= missing
    assert report.native_domain_qualified is False


def test_parent_output_mapping_and_derivation_must_name_the_same_child_output() -> None:
    payload = _payload()
    allocation = next(
        node for node in payload["nodes"] if node["node_id"] == "allocation_layer"
    )
    allocation["output_derivations"][0]["sources"] = [
        {
            "source_kind": "owned_element_output",
            "source_id": "allocation_summary",
            "source_port_id": "allocation_summary_out",
        }
    ]

    report = check_world_blueprint(_current(payload))

    codes = {gap.code for gap in report.gaps}
    assert "WORLD_BLUEPRINT_PARENT_OUTPUT_MAPPING_NOT_DERIVED" in codes
    assert report.native_domain_qualified is False


def test_parent_input_feedback_is_a_real_producer_and_decorative_inputs_fail() -> None:
    feedback = _payload()
    root = next(node for node in feedback["nodes"] if node["node_id"] == "plan_root")
    root["input_ports"].append(
        {
            "port_id": "root_feedback",
            "value_type": "plan_result",
            "schema_id": "worldguard.port.plan-result",
            "schema_version": "v1",
            "refines": [],
            "cardinality": "one",
        }
    )
    feedback["declared_inputs"].append(
        {
            "input_id": "external_root_feedback",
            "node_id": "plan_root",
            "port_id": "root_feedback",
        }
    )
    allocation_mapping = next(
        row
        for row in root["child_output_mappings"]
        if row["child_node_id"] == "allocation_layer"
    )
    allocation_mapping.update(
        {"disposition": "parent_input", "parent_port_id": "root_feedback"}
    )

    feedback_report = check_world_blueprint(_current(feedback))
    source_gap = next(
        gap
        for gap in feedback_report.gaps
        if gap.code == "WORLD_BLUEPRINT_NODE_INPUT_SOURCE_CARDINALITY"
        and gap.port_id == "root_feedback"
    )
    assert set(source_gap.evidence["source_owner_ids"]) == {
        "external_root_feedback",
        allocation_mapping["mapping_id"],
    }

    decorative = _payload()
    root = next(node for node in decorative["nodes"] if node["node_id"] == "plan_root")
    root["input_ports"].append(
        {
            "port_id": "unused_request",
            "value_type": "task_request",
            "schema_id": "worldguard.port.task-request",
            "schema_version": "v1",
            "refines": [],
            "cardinality": "one",
        }
    )
    decorative["declared_inputs"].append(
        {
            "input_id": "external_unused_request",
            "node_id": "plan_root",
            "port_id": "unused_request",
        }
    )
    decorative_report = check_world_blueprint(_current(decorative))
    assert any(
        gap.code == "WORLD_BLUEPRINT_NODE_INPUT_DECORATIVE"
        and gap.port_id == "unused_request"
        for gap in decorative_report.gaps
    )


def test_unknown_element_kind_relation_and_stale_fingerprint_are_rejected() -> None:
    unknown_kind = _payload()
    unknown_kind["elements"][0]["kind"] = "software_module"
    with pytest.raises(BlueprintError) as caught:
        _current(unknown_kind)
    assert caught.value.code == "WORLD_BLUEPRINT_ELEMENT_KIND_UNKNOWN"

    unknown_relation = _payload()
    unknown_relation["elements"][0]["dependencies"][0]["relation"] = "maybe_related"
    with pytest.raises(BlueprintError) as caught:
        _current(unknown_relation)
    assert caught.value.code == "WORLD_BLUEPRINT_RELATION_UNKNOWN"

    current = load_world_blueprint(FIXTURE).to_dict()
    current["nodes"][0]["title"] = "changed without renewing blueprint identity"
    with pytest.raises(BlueprintError) as caught:
        WorldBlueprintContract.from_dict(current, source_root=FIXTURE.parent)
    assert caught.value.code == "WORLD_BLUEPRINT_FINGERPRINT_STALE"

    retired = _payload()
    retired["elements"][0]["target_native"] = {"state": "plan_ready"}
    with pytest.raises(BlueprintError) as caught:
        _current(retired)
    assert caught.value.code == "WORLD_BLUEPRINT_UNKNOWN_FIELD"


def test_binding_hash_and_target_identity_are_exact() -> None:
    malformed_hash = _payload()
    malformed_hash["bindings"][0]["content_fingerprint"] = "not-a-current-hash"
    with pytest.raises(BlueprintError) as caught:
        _current(malformed_hash)
    assert caught.value.code == "WORLD_BLUEPRINT_BINDING_FINGERPRINT_INVALID"

    uppercase_hash = _payload()
    uppercase_hash["bindings"][0]["content_fingerprint"] = "sha256:" + "A" * 64
    with pytest.raises(BlueprintError) as caught:
        _current(uppercase_hash)
    assert caught.value.code == "WORLD_BLUEPRINT_BINDING_FINGERPRINT_INVALID"

    wrong_target = _payload()
    next(
        row
        for row in wrong_target["bindings"]
        if row["binding_id"] == "assignment_material"
    )["target_id"] = "different-planning-workflow"
    report = check_world_blueprint(_current(wrong_target))
    mismatch = next(
        gap
        for gap in report.gaps
        if gap.code == "WORLD_BLUEPRINT_BINDING_TARGET_MISMATCH"
    )
    assert mismatch.binding_id == "assignment_material"
    assert mismatch.evidence == {
        "expected_target_id": "planning-workflow",
        "observed_target_id": "different-planning-workflow",
    }


def test_native_semantics_are_typed_exact_and_observation_bound() -> None:
    kind_mismatch = _payload()
    kind_mismatch["elements"][0]["native_semantic"]["element_kind"] = "event"
    with pytest.raises(BlueprintError) as caught:
        _current(kind_mismatch)
    assert caught.value.code == "WORLD_BLUEPRINT_NATIVE_SEMANTIC_KIND_MISMATCH"

    wrong_type = _payload()
    resource = next(
        row for row in wrong_type["elements"] if row["element_id"] == "resource_reservation"
    )
    resource["native_semantic"]["semantic_fields"]["quantity"] = "one"
    with pytest.raises(BlueprintError) as caught:
        _current(wrong_type)
    assert caught.value.code == "WORLD_BLUEPRINT_NATIVE_SEMANTIC_FIELDS_INVALID"

    wrong_hash = _payload()
    wrong_hash["elements"][0]["native_semantic"]["content_fingerprint"] = (
        "sha256:" + "0" * 64
    )
    with pytest.raises(BlueprintError) as caught:
        _current(wrong_hash)
    assert caught.value.code == "WORLD_BLUEPRINT_NATIVE_SEMANTIC_FINGERPRINT_INVALID"

    wrong_observation = _payload()
    semantic = wrong_observation["elements"][0]["native_semantic"]
    semantic["observation_binding_id"] = "assignment_native"
    _renew_native_semantic_fingerprint(semantic)
    report = check_world_blueprint(_current(wrong_observation))
    assert any(
        gap.code == "WORLD_BLUEPRINT_NATIVE_SEMANTIC_OBSERVATION_MISMATCH"
        and gap.element_id == "plan_outcome"
        for gap in report.gaps
    )


@pytest.mark.parametrize(
    ("locator", "expected_reason"),
    [
        ("../outside.json#workflow_record_assignment", "locator_escapes_source_root"),
        ("support/missing.json#workflow_record_assignment", "resource_missing"),
        ("support/target-material.json#missing_selector", "resource_selector_missing"),
    ],
)
def test_local_binding_locator_must_be_safe_and_observable(
    locator: str,
    expected_reason: str,
) -> None:
    payload = _payload()
    binding = payload["bindings"][0]
    binding["locator"] = locator
    _renew_binding_receipt(payload, binding["binding_id"], FIXTURE.parent)
    report = check_world_blueprint(_current(payload))
    gap = next(
        row
        for row in report.gaps
        if row.code == "WORLD_BLUEPRINT_BINDING_RESOURCE_UNAVAILABLE"
        and row.binding_id == binding["binding_id"]
    )
    assert gap.evidence["reason"] == expected_reason


def test_fake_current_hash_and_receipt_do_not_create_content_evidence() -> None:
    fake_content = _payload()
    binding = next(
        row
        for row in fake_content["bindings"]
        if row["binding_id"] == "assignment_material"
    )
    binding["content_fingerprint"] = "sha256:" + "0" * 64
    _renew_binding_receipt(fake_content, binding["binding_id"], FIXTURE.parent)
    report = check_world_blueprint(_current(fake_content))
    assert any(
        gap.code == "WORLD_BLUEPRINT_BINDING_CONTENT_MISMATCH"
        and gap.binding_id == binding["binding_id"]
        for gap in report.gaps
    )

    fake_receipt = _payload()
    next(
        row
        for row in fake_receipt["bindings"]
        if row["binding_id"] == "assignment_material"
    )["receipt_fingerprint"] = "sha256:" + "0" * 64
    report = check_world_blueprint(_current(fake_receipt))
    assert any(
        gap.code == "WORLD_BLUEPRINT_BINDING_RECEIPT_MISMATCH"
        and gap.binding_id == "assignment_material"
        for gap in report.gaps
    )


def test_self_consistent_static_native_copy_cannot_replace_event_execution(
    tmp_path: Path,
) -> None:
    payload = _payload()
    shutil.copytree(FIXTURE.parent / "support", tmp_path / "support")
    event = next(
        row
        for row in payload["elements"]
        if row["element_id"] == "schedule_event"
    )
    fields = event["native_semantic"]["semantic_fields"]
    fields["initiates"] = list(fields["terminates"])
    _renew_native_semantic_fingerprint(event["native_semantic"])

    native_results_path = tmp_path / "support" / "native-results.json"
    native_results = json.loads(native_results_path.read_text(encoding="utf-8"))
    native_results["native_schedule_event"] = {
        key: value
        for key, value in event["native_semantic"].items()
        if key not in {"content_fingerprint", "task_purpose"}
    }
    native_results_path.write_text(
        json.dumps(native_results, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    binding = next(
        row
        for row in payload["bindings"]
        if row["binding_id"] == "schedule_event_native"
    )
    binding["content_fingerprint"] = event["native_semantic"][
        "content_fingerprint"
    ]
    _renew_binding_receipt(payload, binding["binding_id"], tmp_path)

    report = check_world_blueprint(_current_at(payload, tmp_path))

    execution_gap = next(
        gap
        for gap in report.gaps
        if gap.code == "WORLD_BLUEPRINT_NATIVE_EXECUTION_FAILED"
        and gap.element_id == "schedule_event"
    )
    assert execution_gap.evidence["execution_status"] == "GAP"
    assert any(
        finding["code"] == "WORLD_BLUEPRINT_TARGET_BEHAVIOR_CASE_UNBOUND"
        for finding in execution_gap.evidence["findings"]
    )
    assert report.native_domain_qualified is False
    assert any(
        row["element_id"] == "schedule_event" and row["status"] == "GAP"
        for row in report.native_execution_receipts
    )


def test_applicable_native_owner_cannot_run_without_task_local_purpose() -> None:
    payload = _payload()
    element = next(
        row
        for row in payload["elements"]
        if row["element_id"] == "assignment_transition"
    )
    element["native_semantic"].pop("task_purpose")

    report = check_world_blueprint(_current(payload))
    receipt = next(
        row
        for row in report.native_execution_receipts
        if row["element_id"] == "assignment_transition"
    )

    assert receipt["execution_disposition"] == "not_run"
    assert receipt["status"] == "GAP"
    assert receipt["structural_result"] == {}
    assert receipt["semantic_result"] == {}
    assert [row["code"] for row in receipt["findings"]] == [
        "WORLD_BLUEPRINT_TASK_PURPOSE_MISSING"
    ]
    assert report.native_domain_qualified is False


def test_invalid_counterexample_oracle_blocks_native_owner_execution() -> None:
    payload = _payload()
    element = next(
        row
        for row in payload["elements"]
        if row["element_id"] == "assignment_transition"
    )
    bad_case = next(
        row
        for row in element["native_semantic"]["task_purpose"]["behavior_cases"]
        if row["case_kind"] == "known_bad"
    )
    bad_case["expected_code"] = "SEM_EVENT_UNDECLARED_COUNTEREXAMPLE"

    report = check_world_blueprint(_current(payload))
    receipt = next(
        row
        for row in report.native_execution_receipts
        if row["element_id"] == "assignment_transition"
    )

    assert receipt["execution_disposition"] == "not_run"
    assert receipt["status"] == "GAP"
    assert any(
        row["code"] == "WORLD_BLUEPRINT_BEHAVIOR_ORACLE_INVALID"
        for row in receipt["findings"]
    )
    assert report.native_domain_qualified is False


def test_production_derived_good_oracle_cannot_replace_native_oracle() -> None:
    payload = _payload()
    element = next(
        row
        for row in payload["elements"]
        if row["element_id"] == "assignment_transition"
    )
    good_case = next(
        row
        for row in element["native_semantic"]["task_purpose"]["behavior_cases"]
        if row["case_kind"] == "known_good"
    )
    good_case["oracle_id"] = "oracle:production:assignment-output"

    report = check_world_blueprint(_current(payload))
    receipt = next(
        row
        for row in report.native_execution_receipts
        if row["element_id"] == "assignment_transition"
    )

    assert receipt["execution_disposition"] == "not_run"
    assert any(
        row["code"] == "WORLD_BLUEPRINT_BEHAVIOR_ORACLE_INVALID"
        for row in receipt["findings"]
    )


def test_duplicate_task_purpose_declaration_blocks_both_target_owners() -> None:
    payload = _payload()
    assignment = next(
        row
        for row in payload["elements"]
        if row["element_id"] == "assignment_transition"
    )
    resource = next(
        row
        for row in payload["elements"]
        if row["element_id"] == "resource_reservation"
    )
    resource["native_semantic"]["task_purpose"]["declaration_id"] = (
        assignment["native_semantic"]["task_purpose"]["declaration_id"]
    )

    report = check_world_blueprint(_current(payload))
    affected = [
        row
        for row in report.native_execution_receipts
        if row["element_id"]
        in {"assignment_transition", "resource_reservation"}
    ]

    assert len(affected) == 2
    assert all(row["execution_disposition"] == "not_run" for row in affected)
    assert all(
        any(
            finding["code"]
            == "WORLD_BLUEPRINT_TASK_PURPOSE_DECLARATION_DUPLICATE"
            for finding in row["findings"]
        )
        for row in affected
    )


def test_native_execution_cannot_bypass_for_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def blocked_for_guard(*_args: object, **_kwargs: object) -> object:
        raise ValueError("The test intercepted the mandatory child-contract path.")

    monkeypatch.setattr(
        blueprint_module.GuardContract,
        "for_guard",
        blocked_for_guard,
    )
    report = check_world_blueprint(load_world_blueprint(FIXTURE))
    receipt = next(
        row
        for row in report.native_execution_receipts
        if row["element_id"] == "assignment_transition"
    )

    assert receipt["execution_disposition"] == "not_run"
    assert receipt["structural_result"] == {}
    assert receipt["semantic_result"] == {}
    assert any(
        row["code"] == "WORLD_BLUEPRINT_NATIVE_OWNER_EXECUTION_ERROR"
        for row in receipt["findings"]
    )


def test_state_effect_oracle_mismatch_cannot_preserve_owner_pass() -> None:
    payload = _payload()
    element = next(
        row
        for row in payload["elements"]
        if row["element_id"] == "assignment_transition"
    )
    good_case = next(
        row
        for row in element["native_semantic"]["task_purpose"]["behavior_cases"]
        if row["case_kind"] == "known_good"
    )
    good_case["post_state"]["reached_state_ids"] = ["assigned"]

    report = check_world_blueprint(_current(payload))
    receipt = next(
        row
        for row in report.native_execution_receipts
        if row["element_id"] == "assignment_transition"
    )

    assert receipt["structural_result"]["status"] == "PASS"
    assert receipt["semantic_result"]["status"] == "PASS"
    assert receipt["behavior_case_result"]["status"] == "FAIL"
    assert receipt["status"] == "FAIL"
    assert any(
        row["code"] == "WORLD_BLUEPRINT_TARGET_BEHAVIOR_ORACLE_MISMATCH"
        for row in receipt["findings"]
    )
    assert any(
        row["path"] == "post_state.reached_state_ids"
        for row in receipt["behavior_case_result"]["mismatches"]
    )
    assert report.native_domain_qualified is False


@pytest.mark.parametrize(
    "mutation", ["missing_good", "duplicate_case_id", "extra_bad_failure"]
)
def test_behavior_case_set_must_be_complete_and_unambiguous(mutation: str) -> None:
    payload = _payload()
    element = next(
        row
        for row in payload["elements"]
        if row["element_id"] == "assignment_transition"
    )
    cases = element["native_semantic"]["task_purpose"]["behavior_cases"]
    if mutation == "missing_good":
        cases[:] = [row for row in cases if row["case_kind"] != "known_good"]
        expected_code = "WORLD_BLUEPRINT_BEHAVIOR_CASE_CARDINALITY_INVALID"
    elif mutation == "duplicate_case_id":
        cases[1]["case_id"] = cases[0]["case_id"]
        expected_code = "WORLD_BLUEPRINT_BEHAVIOR_CASE_ID_DUPLICATE"
    else:
        extra = deepcopy(cases[1])
        extra["case_id"] = "case:assignment_transition:bad:foreign"
        extra["failure_id"] = "failure:event:foreign"
        cases.append(extra)
        expected_code = "WORLD_BLUEPRINT_BEHAVIOR_CASE_CARDINALITY_INVALID"

    with pytest.raises(BlueprintError) as captured:
        _current(payload)

    assert captured.value.code == expected_code


def test_external_identity_is_preserved_but_never_closes_content() -> None:
    payload = _payload()
    binding = payload["bindings"][0]
    binding["observation_mode"] = "external_identity"
    binding["locator"] = "provider://workflow/assignment"
    _renew_binding_receipt(payload, binding["binding_id"], FIXTURE.parent)

    report = check_world_blueprint(_current(payload))

    gap = next(
        row
        for row in report.gaps
        if row.code == "WORLD_BLUEPRINT_BINDING_CONTENT_NOT_VERIFIED"
        and row.binding_id == binding["binding_id"]
    )
    assert gap.severity == GuardStatus.BOUNDARY_EXCEEDED
    assert gap.evidence["content_not_verified"] is True
    assert report.native_domain_qualified is False


def test_provider_content_requires_one_complete_exact_current_receipt(
    tmp_path: Path,
) -> None:
    base = _payload()
    binding = next(
        row for row in base["bindings"] if row["binding_id"] == "assignment_evidence"
    )
    binding.update(
        {
            "observation_mode": "provider_content",
            "locator": "provider-results.json#assignment_evidence",
            "provider_id": "external.workflow.provider",
            "provider_version": "v7",
            "provider_capability_id": "workflow.content-observation.v1",
        }
    )
    modeled_binding = next(
        row
        for row in _current(base).bindings
        if row.binding_id == "assignment_evidence"
    )
    registration = _provider_capability_registration(modeled_binding)
    assert registration is not None
    execution_expected = _provider_observation_expected(
        modeled_binding,
        registration,
    )
    result = {
        "schema_version": "worldguard.blueprint_provider_observation.v2",
        "observation_id": "observation:assignment_evidence",
        "binding_id": "assignment_evidence",
        "role": "evidence",
        "subject_element_id": "assignment_transition",
        "owner": "evidence_owner",
        "observation_mode": "provider_content",
        "provider_id": "external.workflow.provider",
        "provider_version": "v7",
        "provider_capability_id": "workflow.content-observation.v1",
        "target_id": "planning-workflow",
        "target_revision": "revision-1",
        "resource_id": "evidence_assignment",
        "content_fingerprint": binding["content_fingerprint"],
        "claim_boundary": "planning workflow revision 1 only",
        "status": "current",
        "execution_owner_id": registration["execution_owner_id"],
        "execution_owner_version": registration["execution_owner_version"],
        "registry_entry_fingerprint": registration[
            "registry_entry_fingerprint"
        ],
        "terminal_status": "current",
        **execution_expected,
    }
    receipt = "sha256:" + fingerprint_mesh(result)
    result["receipt_fingerprint"] = receipt
    binding["receipt_fingerprint"] = receipt

    authority = json.loads(
        (FIXTURE.parent / "support/target-semantic-authority.json").read_text(
            encoding="utf-8"
        )
    )
    authority_element = next(
        row
        for row in authority["elements"]
        if row["element_id"] == "assignment_transition"
    )
    authority_binding = next(
        row
        for row in authority_element["binding_responsibilities"]
        if row["binding_id"] == "assignment_evidence"
    )
    authority_binding.update(
        {
            "owner_id": binding["owner"],
            "resource_id": binding["resource_id"],
            "locator": binding["locator"],
            "provider_id": binding["provider_id"],
            "provider_version": binding["provider_version"],
            "provider_capability_id": binding["provider_capability_id"],
            "observation_mode": binding["observation_mode"],
        }
    )
    authority_bytes = (
        json.dumps(authority, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    authority_ref = next(
        row
        for row in base["commitment_inventory"]["input_refs"]
        if row["input_kind"] == "target_semantic_authority"
    )
    authority_ref["content_fingerprint"] = (
        "sha256:" + hashlib.sha256(authority_bytes).hexdigest()
    )

    census_ref = next(
        row
        for row in base["commitment_inventory"]["input_refs"]
        if row["input_kind"] == "target_object_census_authority"
    )
    census_record = json.loads(
        (FIXTURE.parent / census_ref["locator"]).read_text(encoding="utf-8")
    )
    census_authority = census_record["authority"]
    semantic_authority = TargetSemanticAuthority.from_dict(authority)
    census_authority["required_node_ids"] = list(
        semantic_authority.required_node_ids
    )
    census_authority["required_guard_owner_ids"] = list(
        semantic_authority.required_guard_owner_ids
    )
    census_authority["members"] = _target_semantic_census_members(
        semantic_authority
    )
    census_authority["input_fingerprints"] = {
        input_kind: next(
            row["content_fingerprint"]
            for row in base["commitment_inventory"]["input_refs"]
            if row["input_kind"] == input_kind
        )
        for input_kind in (
            "request_contract",
            "target_material",
            "target_semantic_authority",
            "target_object_census_source",
        )
    }
    signed_census = signed_object_census(census_authority)
    census_bytes = (
        json.dumps(signed_census, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n"
    ).encode("utf-8")
    census_ref["content_fingerprint"] = (
        "sha256:" + hashlib.sha256(census_bytes).hexdigest()
    )

    def with_receipt(row: dict) -> dict:
        row = {key: value for key, value in row.items() if key != "receipt_fingerprint"}
        return {**row, "receipt_fingerprint": "sha256:" + fingerprint_mesh(row)}

    cases = {
        "pass": (result, None),
        "partial": ({key: value for key, value in result.items() if key != "provider_version"}, "provider_result_shape_mismatch"),
        "foreign": (with_receipt({**result, "target_id": "another-workflow"}), "provider_result_identity_mismatch"),
        "stale": (with_receipt({**result, "status": "stale"}), "provider_result_stale"),
        "fake-current": ({**result, "receipt_fingerprint": "sha256:" + "0" * 64}, "provider_result_receipt_mismatch"),
        "missing": (None, "provider_result_missing"),
    }
    for case_id, (provider_result, expected_reason) in cases.items():
        case_root = tmp_path / case_id
        shutil.copytree(FIXTURE.parent / "support", case_root / "support")
        (case_root / "support/target-semantic-authority.json").write_bytes(
            authority_bytes
        )
        (case_root / census_ref["locator"]).write_bytes(census_bytes)
        if provider_result is not None:
            (case_root / "provider-results.json").write_text(
                json.dumps({"assignment_evidence": provider_result}),
                encoding="utf-8",
            )
        current = _current_at(base, case_root)
        cache = compile_behavior_commitment_inventory_cache(current)
        (case_root / "support/behavior-commitments.json").write_text(
            json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report = check_world_blueprint(_current_at(base, case_root))
        matching = [
            gap
            for gap in report.gaps
            if gap.code == "WORLD_BLUEPRINT_PROVIDER_CONTENT_NOT_CURRENT"
            and gap.binding_id == "assignment_evidence"
        ]
        if expected_reason is None:
            assert matching == []
            assert report.native_domain_qualified is True
        else:
            assert matching[0].evidence["reason"] == expected_reason
            assert report.native_domain_qualified is False
