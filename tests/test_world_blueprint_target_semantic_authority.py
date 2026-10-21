from __future__ import annotations

import hashlib
import json
import runpy
import shutil
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from worldguard.blueprint import (
    WorldBlueprintContract,
    _binding_receipt_fingerprint,
    check_world_blueprint,
    compile_behavior_commitment_inventory_cache,
)
from worldguard.semantic import fingerprint_mesh



ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests/fixtures/world_blueprint"
BASELINE_FIXTURE = FIXTURE_ROOT / "planning_workflow_three_level.yaml"
SEVEN_GUARD_FIXTURE = FIXTURE_ROOT / "seven_guard_portable_handoff.json"


def _yaml_payload() -> dict:
    return yaml.safe_load(BASELINE_FIXTURE.read_text(encoding="utf-8"))


def _json_payload() -> dict:
    return json.loads(SEVEN_GUARD_FIXTURE.read_text(encoding="utf-8"))


def _current(payload: dict, *, source_root: Path) -> WorldBlueprintContract:
    candidate = deepcopy(payload)
    candidate.pop("blueprint_fingerprint", None)
    return WorldBlueprintContract.from_dict(candidate, source_root=source_root)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _file_fingerprint(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _selector_fingerprint(payload: object) -> str:
    content = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _input_ref(payload: dict, kind: str) -> dict:
    return next(
        row
        for row in payload["commitment_inventory"]["input_refs"]
        if row["input_kind"] == kind
    )


def _binding(payload: dict, binding_id: str) -> dict:
    return next(row for row in payload["bindings"] if row["binding_id"] == binding_id)


def _renew_binding_receipt(
    payload: dict,
    binding_id: str,
    *,
    source_root: Path,
) -> None:
    contract = _current(payload, source_root=source_root)
    modeled = next(row for row in contract.bindings if row.binding_id == binding_id)
    _binding(payload, binding_id)["receipt_fingerprint"] = (
        _binding_receipt_fingerprint(modeled)
    )


def _renew_native_receipt(
    payload: dict,
    binding_id: str,
    *,
    source_root: Path,
) -> None:
    report = check_world_blueprint(_current(payload, source_root=source_root))
    receipt = next(
        row
        for row in report.native_execution_receipts
        if row["observation_binding_id"] == binding_id
    )
    _binding(payload, binding_id)["receipt_fingerprint"] = receipt[
        "receipt_fingerprint"
    ]




def _forge_cache_envelope_for_changed_material(
    payload: dict,
    *,
    source_root: Path,
    material: dict,
) -> None:
    """Refresh every caller-controlled cache field, including a lying assertion.

    The current adapter must ignore this self-consistent-looking cache and replay
    the independently supplied target semantic authority against target material.
    """

    cache_path = source_root / payload["commitment_inventory"]["locator"]
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    contract = _current(payload, source_root=source_root)
    refs = contract.commitment_inventory.to_dict()["input_refs"]
    cache["input_refs"] = refs
    material_ref = next(row for row in refs if row["input_kind"] == "target_material")
    observations = cache["adapter_result"]["input_observations"]
    material_observation = next(
        row for row in observations if row["input_kind"] == "target_material"
    )
    material_observation.update(material_ref)
    material_observation["observed_content_fingerprint"] = material_ref[
        "content_fingerprint"
    ]
    for assertion in cache["adapter_result"]["target_semantic_authority"][
        "material_assertions"
    ]:
        value: object = material
        for part in assertion["source_path"]:
            value = value[part]  # type: ignore[index]
        assertion.update(
            {
                "source_value": value,
                "semantic_value": value,
                "source_error": "",
                "semantic_error": "",
                "matched": True,
            }
        )
    adapter_result = cache["adapter_result"]
    terminal = cache["terminal_receipt"]
    terminal["request_fingerprint"] = "sha256:" + fingerprint_mesh(
        {
            "schema_version": "worldguard.behavior_commitment_adapter_request.v2",
            "inventory_reference": contract.commitment_inventory.to_dict(),
            "registration_fingerprint": adapter_result["registration_fingerprint"],
        }
    )
    terminal["input_fingerprint"] = "sha256:" + fingerprint_mesh(
        sorted(observations, key=lambda row: row["input_id"])
    )
    terminal["result_fingerprint"] = "sha256:" + fingerprint_mesh(adapter_result)
    receipt_payload = {
        key: value for key, value in terminal.items() if key != "receipt_fingerprint"
    }
    terminal["receipt_fingerprint"] = "sha256:" + fingerprint_mesh(receipt_payload)
    _write_json(cache_path, cache)


def test_changed_target_material_cannot_pass_with_old_model_after_coherent_refresh(
    tmp_path: Path,
) -> None:
    payload = _yaml_payload()
    shutil.copytree(FIXTURE_ROOT / "support", tmp_path / "support")
    material_path = tmp_path / "support/target-material.json"
    material = json.loads(material_path.read_text(encoding="utf-8"))
    material["workflow_record_assignment"] = {
        "actor_id": "mallory",
        "role": "auditor",
        "task": "destroy_materials",
        "transition": ["closed", "deleted"],
    }
    _write_json(material_path, material)

    material_ref = _input_ref(payload, "target_material")
    material_ref["content_fingerprint"] = _file_fingerprint(material_path)
    assignment_binding = _binding(payload, "assignment_material")
    assignment_binding["content_fingerprint"] = _selector_fingerprint(
        material["workflow_record_assignment"]
    )
    _renew_binding_receipt(
        payload,
        "assignment_material",
        source_root=tmp_path,
    )
    _forge_cache_envelope_for_changed_material(
        payload,
        source_root=tmp_path,
        material=material,
    )

    report = check_world_blueprint(_current(payload, source_root=tmp_path))

    gap = next(
        row
        for row in report.gaps
        if row.code == "WORLD_BLUEPRINT_TARGET_SEMANTIC_MATERIAL_MISMATCH"
    )
    mismatched_assertions = {
        row["assertion_id"] for row in gap.evidence["assertion_failures"]
    }
    assert {
        "assignment-actor",
        "assignment-role",
        "assignment-task",
        "assignment-source",
        "assignment-target",
    }.issubset(mismatched_assertions)
    assert report.native_domain_qualified is False


def test_binding_owner_cannot_disagree_with_actual_registered_guard_receipt() -> None:
    payload = _json_payload()
    causal_binding = _binding(payload, "binding:matrix_causal_pass")
    causal_binding["owner"] = "EventGuard"

    report = check_world_blueprint(_current(payload, source_root=FIXTURE_ROOT))

    assert any(
        row.code == "WORLD_BLUEPRINT_TARGET_BINDING_RESPONSIBILITY_MISMATCH"
        and row.element_id == "matrix_causal_pass"
        for row in report.gaps
    )
    actual_receipt = next(
        row
        for row in report.native_execution_receipts
        if row["element_id"] == "matrix_causal_pass"
    )
    assert causal_binding["owner"] == "EventGuard"
    assert actual_receipt["owner_guard"] == "CausalGuard"
    assert report.native_domain_qualified is False


def test_whole_causal_element_cannot_be_removed_into_six_owner_false_green() -> None:
    payload = _json_payload()
    payload["elements"] = [
        row for row in payload["elements"] if row["element_id"] != "matrix_causal_pass"
    ]
    payload["bindings"] = [
        row
        for row in payload["bindings"]
        if row["subject_element_id"] != "matrix_causal_pass"
    ]
    for node in payload["nodes"]:
        node["owned_element_ids"] = [
            element_id
            for element_id in node["owned_element_ids"]
            if element_id != "matrix_causal_pass"
        ]

    report = check_world_blueprint(_current(payload, source_root=FIXTURE_ROOT))

    gap = next(
        row
        for row in report.gaps
        if row.code == "WORLD_BLUEPRINT_TARGET_ELEMENT_DENOMINATOR_MISMATCH"
    )
    assert gap.evidence["missing_element_ids"] == ["matrix_causal_pass"]
    assert report.native_domain_qualified is False


@pytest.mark.parametrize(
    "field_group",
    ["inputs", "pre_state", "output", "post_state", "effects", "failure", "boundary"],
)
def test_target_authority_exactly_binds_behavior_contract(field_group: str) -> None:
    payload = _yaml_payload()
    element = next(
        row
        for row in payload["elements"]
        if row["element_id"] == "assignment_transition"
    )
    purpose = element["native_semantic"]["task_purpose"]
    good = next(row for row in purpose["behavior_cases"] if row["case_kind"] == "known_good")
    bad = next(row for row in purpose["behavior_cases"] if row["case_kind"] == "known_bad")
    if field_group == "inputs":
        good["inputs"]["events"] = [{"event_id": "caller-added-event"}]
    elif field_group == "pre_state":
        good["pre_state"] = {}
    elif field_group == "output":
        good["expected_output"] = {}
    elif field_group == "post_state":
        good["post_state"] = {}
    elif field_group == "effects":
        good["effects"] = {}
    elif field_group == "failure":
        bad["blocked_claim"] = "Caller weakened the independently declared failure."
    else:
        good["claim_boundary"] = "caller-expanded boundary"

    report = check_world_blueprint(_current(payload, source_root=FIXTURE_ROOT))

    assert any(
        row.code == "WORLD_BLUEPRINT_TARGET_SEMANTIC_MISMATCH"
        and row.element_id == "assignment_transition"
        for row in report.gaps
    )
    assert report.native_domain_qualified is False


def test_authority_cannot_relabel_registered_native_owner(
    tmp_path: Path,
) -> None:
    payload = _json_payload()
    shutil.copytree(FIXTURE_ROOT / "support", tmp_path / "support")
    authority_path = tmp_path / "support/seven-guard-target-semantic-authority.json"
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    causal = next(
        row for row in authority["elements"] if row["element_id"] == "matrix_causal_pass"
    )
    causal.update(
        {
            "required_guard_owner_id": "EventGuard",
            "required_executor_id": "worldguard.semantic.event.v1",
            "required_executor_version": "v1",
        }
    )
    native_responsibility = next(
        row for row in causal["binding_responsibilities"] if row["role"] == "native_result"
    )
    native_responsibility["owner_id"] = "EventGuard"
    event = next(
        row for row in authority["elements"] if row["element_id"] == "matrix_event_pass"
    )
    event.update(
        {
            "required_guard_owner_id": "CausalGuard",
            "required_executor_id": "worldguard.semantic.causal.v1",
            "required_executor_version": "v1",
        }
    )
    next(
        row for row in event["binding_responsibilities"] if row["role"] == "native_result"
    )["owner_id"] = "CausalGuard"
    _write_json(authority_path, authority)
    _input_ref(payload, "target_semantic_authority")["content_fingerprint"] = (
        _file_fingerprint(authority_path)
    )

    report = check_world_blueprint(_current(payload, source_root=tmp_path))

    gap = next(
        row
        for row in report.gaps
        if row.code == "WORLD_BLUEPRINT_TARGET_SEMANTIC_OWNER_REGISTRY_MISMATCH"
    )
    assert gap.evidence["mismatches"][0]["element_id"] == "matrix_causal_pass"
    assert report.native_domain_qualified is False


def test_material_assertion_denominator_must_cover_every_required_leaf(
    tmp_path: Path,
) -> None:
    payload = _yaml_payload()
    shutil.copytree(FIXTURE_ROOT / "support", tmp_path / "support")
    authority_path = tmp_path / "support/target-semantic-authority.json"
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    authority["material_assertions"] = [
        row
        for row in authority["material_assertions"]
        if row["assertion_id"] != "assignment-task"
    ]
    _write_json(authority_path, authority)
    _input_ref(payload, "target_semantic_authority")["content_fingerprint"] = (
        _file_fingerprint(authority_path)
    )

    report = check_world_blueprint(_current(payload, source_root=tmp_path))

    gap = next(
        row
        for row in report.gaps
        if row.code == "WORLD_BLUEPRINT_TARGET_SEMANTIC_MATERIAL_MISMATCH"
    )
    assert ["workflow_record_assignment", "task"] in gap.evidence[
        "missing_source_paths"
    ]
    assert report.native_domain_qualified is False


def test_every_target_element_has_exact_four_role_dispositions() -> None:
    expected = {
        BASELINE_FIXTURE: (13, 30, 22, 4),
        SEVEN_GUARD_FIXTURE: (20, 58, 22, 4),
    }
    for fixture, (element_count, binding_count, not_applicable_count, derived_count) in (
        expected.items()
    ):
        payload = (
            yaml.safe_load(fixture.read_text(encoding="utf-8"))
            if fixture.suffix == ".yaml"
            else json.loads(fixture.read_text(encoding="utf-8"))
        )
        authority_ref = _input_ref(payload, "target_semantic_authority")
        authority = json.loads(
            (FIXTURE_ROOT / authority_ref["locator"]).read_text(encoding="utf-8")
        )
        assert len(authority["elements"]) == element_count
        assert sum(
            len(row["binding_responsibilities"])
            for row in authority["elements"]
        ) == binding_count
        assert sum(
            len(row["not_applicable_responsibilities"])
            for row in authority["elements"]
        ) == not_applicable_count
        assert sum(
            row["support_mode"] == "derived" for row in authority["elements"]
        ) == derived_count
        for row in authority["elements"]:
            binding_roles = {
                item["role"] for item in row["binding_responsibilities"]
            }
            not_applicable_roles = {
                item["role"]
                for item in row["not_applicable_responsibilities"]
            }
            assert binding_roles.isdisjoint(not_applicable_roles)
            assert binding_roles | not_applicable_roles == {
                "target_material",
                "evidence",
                "test_check",
                "native_result",
            }
            assert all(
                item["reason"].strip()
                for item in row["not_applicable_responsibilities"]
            )


def test_seven_guard_revision_projection_is_exact_and_idempotent() -> None:
    payload = _json_payload()
    assert payload["target_revision"] == "validation-revision-1"
    assert all(
        row["target_revision"] == "validation-revision-1"
        for row in payload["bindings"]
    )

    compiler = runpy.run_path(
        str(ROOT / "scripts/refresh_world_blueprint_external_dna_fixtures.py")
    )
    normalize = compiler["_normalize_seven_guard_revision"]
    previously_projected = {
        "target_revision": "validation-validation-validation-revision-1",
        "input_id": (
            "request:seven-guard-capability-validation:"
            "validation-validation-revision-1"
        ),
    }
    once = normalize(previously_projected)
    assert once == {
        "target_revision": "validation-revision-1",
        "input_id": (
            "request:seven-guard-capability-validation:validation-revision-1"
        ),
    }
    assert normalize(once) == once


def test_non_contributing_material_binding_cannot_be_removed() -> None:
    payload = _yaml_payload()
    payload["bindings"] = [
        row
        for row in payload["bindings"]
        if row["binding_id"] != "actor_alex_material"
    ]
    actor = next(
        row for row in payload["elements"] if row["element_id"] == "actor_alex"
    )
    actor["required_binding_roles"] = ["native_result"]

    report = check_world_blueprint(_current(payload, source_root=FIXTURE_ROOT))

    assert any(
        row.code == "WORLD_BLUEPRINT_TARGET_BINDING_RESPONSIBILITY_MISMATCH"
        and row.element_id == "actor_alex"
        for row in report.gaps
    )
    assert any(
        row.code == "WORLD_BLUEPRINT_REQUIRED_BINDING_MISSING"
        and row.element_id == "actor_alex"
        and row.required_role == "target_material"
        for row in report.gaps
    )


def test_not_applicable_role_cannot_gain_candidate_binding() -> None:
    payload = _yaml_payload()
    invented = deepcopy(_binding(payload, "assignment_evidence"))
    invented.update(
        {
            "binding_id": "actor_alex_invented_evidence",
            "subject_element_id": "actor_alex",
        }
    )
    payload["bindings"].append(invented)
    actor = next(
        row for row in payload["elements"] if row["element_id"] == "actor_alex"
    )
    actor["required_binding_roles"] = [
        "evidence",
        "native_result",
        "target_material",
    ]
    _renew_binding_receipt(
        payload,
        "actor_alex_invented_evidence",
        source_root=FIXTURE_ROOT,
    )

    report = check_world_blueprint(_current(payload, source_root=FIXTURE_ROOT))

    assert any(
        row.code == "WORLD_BLUEPRINT_NOT_APPLICABLE_ROLE_BOUND"
        and row.element_id == "actor_alex"
        and row.required_role == "evidence"
        for row in report.gaps
    )


def test_authority_cannot_omit_one_role_disposition(tmp_path: Path) -> None:
    payload = _yaml_payload()
    shutil.copytree(FIXTURE_ROOT / "support", tmp_path / "support")
    authority_path = tmp_path / "support/target-semantic-authority.json"
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    actor = next(
        row for row in authority["elements"] if row["element_id"] == "actor_alex"
    )
    actor["not_applicable_responsibilities"] = [
        row
        for row in actor["not_applicable_responsibilities"]
        if row["role"] != "evidence"
    ]
    _write_json(authority_path, authority)
    _input_ref(payload, "target_semantic_authority")["content_fingerprint"] = (
        _file_fingerprint(authority_path)
    )

    report = check_world_blueprint(_current(payload, source_root=tmp_path))

    assert any(
        row.code == "WORLD_BLUEPRINT_TARGET_SEMANTIC_AUTHORITY_INVALID"
        for row in report.gaps
    )


def test_parent_summary_requires_exact_child_output_derivation() -> None:
    payload = _yaml_payload()
    allocation = next(
        row for row in payload["nodes"] if row["node_id"] == "allocation_layer"
    )
    derivation = next(
        row
        for row in allocation["output_derivations"]
        if row["derivation_id"] == "derive_allocation_result"
    )
    derivation["sources"][0]["source_port_id"] = "caller_rewired_output"

    report = check_world_blueprint(_current(payload, source_root=FIXTURE_ROOT))

    assert any(
        row.code == "WORLD_BLUEPRINT_TARGET_DERIVATION_RESPONSIBILITY_MISMATCH"
        and row.element_id == "allocation_summary"
        for row in report.gaps
    )


def test_consistent_target_change_passes_and_receives_new_blueprint_identity(
    tmp_path: Path,
) -> None:
    payload = _yaml_payload()
    original = _current(payload, source_root=FIXTURE_ROOT)
    shutil.copytree(FIXTURE_ROOT / "support", tmp_path / "support")

    material_path = tmp_path / "support/target-material.json"
    material = json.loads(material_path.read_text(encoding="utf-8"))
    material["workflow_record_assignment"]["task"] = "review_materials"
    _write_json(material_path, material)
    _input_ref(payload, "target_material")["content_fingerprint"] = (
        _file_fingerprint(material_path)
    )
    changed_material_fingerprint = _selector_fingerprint(
        material["workflow_record_assignment"]
    )
    for binding_id in (
        "actor_alex_material",
        "assignment_material",
        "planner_role_material",
        "task_prepare_material",
    ):
        _binding(payload, binding_id)["content_fingerprint"] = (
            changed_material_fingerprint
        )
        _renew_binding_receipt(payload, binding_id, source_root=tmp_path)

    element = next(
        row for row in payload["elements"] if row["element_id"] == "task_prepare"
    )
    semantic = element["native_semantic"]
    semantic["semantic_fields"]["identity"] = "review_materials"
    semantic_identity = {
        key: value
        for key, value in semantic.items()
        if key not in {"content_fingerprint", "task_purpose"}
    }
    semantic["content_fingerprint"] = "sha256:" + fingerprint_mesh(semantic_identity)

    native_path = tmp_path / "support/native-results.json"
    native_results = json.loads(native_path.read_text(encoding="utf-8"))
    native_results["native_task_prepare"] = semantic_identity
    _write_json(native_path, native_results)
    task_binding = _binding(payload, "task_prepare_native")
    task_binding["content_fingerprint"] = semantic["content_fingerprint"]

    authority_path = tmp_path / "support/target-semantic-authority.json"
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    authority_task = next(
        row for row in authority["elements"] if row["element_id"] == "task_prepare"
    )
    authority_task["native_semantic"] = deepcopy(semantic)
    _write_json(authority_path, authority)
    _input_ref(payload, "target_semantic_authority")["content_fingerprint"] = (
        _file_fingerprint(authority_path)
    )

    _renew_native_receipt(payload, "task_prepare_native", source_root=tmp_path)
    updated_contract = _current(payload, source_root=tmp_path)
    cache = compile_behavior_commitment_inventory_cache(updated_contract)
    _write_json(tmp_path / "support/behavior-commitments.json", cache)
    final_contract = _current(payload, source_root=tmp_path)
    report = check_world_blueprint(final_contract)

    assert report.status == "PASS"
    assert report.gaps == ()
    assert final_contract.blueprint_fingerprint != original.blueprint_fingerprint
