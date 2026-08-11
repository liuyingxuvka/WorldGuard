from __future__ import annotations

import json
from pathlib import Path

from worldguard.blueprint import (
    BINDING_ROLES,
    GuardStatus,
    blueprint_impact,
    blueprint_reverse_trace,
    check_world_blueprint,
    load_world_blueprint,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests/fixtures/world_blueprint"
FIXTURE = FIXTURE_ROOT / "policy_access_execution.yaml"
AUTHORITY = (
    FIXTURE_ROOT / "support/policy-access-target-semantic-authority.json"
)
MATERIAL = FIXTURE_ROOT / "support/policy-access-target-material.json"
REQUEST = FIXTURE_ROOT / "support/policy-access-behavior-request-contract.json"


def _resolve(value: object, path: list[str | int]) -> object:
    current = value
    for part in path:
        if isinstance(part, int):
            assert isinstance(current, list)
            current = current[part]
        else:
            assert isinstance(current, dict)
            current = current[part]
    return current


def test_policy_target_is_independent_and_every_element_closes_four_roles() -> None:
    blueprint = load_world_blueprint(FIXTURE)
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    material = json.loads(MATERIAL.read_text(encoding="utf-8"))
    request = json.loads(REQUEST.read_text(encoding="utf-8"))

    report = check_world_blueprint(blueprint)

    assert report.status == GuardStatus.PASS
    assert report.native_domain_qualified is True
    assert report.gaps == ()
    assert blueprint.target_id == "policy-access-execution"
    assert blueprint.target_revision == "policy-revision-1"
    assert request["target_id"] == blueprint.target_id
    assert request["behaviors"][0]["behavior_id"] == (
        "behavior:evaluate-field-access"
    )
    assert request["behaviors"][0]["required_contributor_element_ids"] == [
        "access_policy_norm"
    ]
    serialized_target = json.dumps(
        {
            "blueprint": blueprint.to_dict(),
            "authority": authority,
            "material": material,
            "request": request,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    assert "planning-workflow" not in serialized_target
    assert "workflow_record_" not in serialized_target

    elements = authority["elements"]
    assert len(elements) == 3
    applicable_count = 0
    not_applicable_count = 0
    derivation_count = 0
    for element in elements:
        applicable_roles = {
            row["role"] for row in element["binding_responsibilities"]
        }
        not_applicable_roles = {
            row["role"]
            for row in element["not_applicable_responsibilities"]
        }
        assert applicable_roles.isdisjoint(not_applicable_roles)
        assert applicable_roles.union(not_applicable_roles) == BINDING_ROLES
        assert all(
            row["reason"].strip()
            for row in element["not_applicable_responsibilities"]
        )
        applicable_count += len(applicable_roles)
        not_applicable_count += len(not_applicable_roles)
        derivation_count += len(element["derivation_responsibilities"])
    assert (applicable_count, not_applicable_count, derivation_count) == (8, 4, 1)
    assert applicable_count + not_applicable_count == 3 * len(BINDING_ROLES)

    semantics = {
        row["element_id"]: row["native_semantic"] for row in elements
    }
    for assertion in authority["material_assertions"]:
        assert _resolve(material, assertion["source_path"]) == _resolve(
            semantics[assertion["target_element_id"]],
            assertion["semantic_path"],
        )


def test_policy_target_runs_in_memory_impact_and_reverse_trace() -> None:
    blueprint = load_world_blueprint(FIXTURE)

    impact = blueprint_impact(
        blueprint,
        blueprint_fingerprint=blueprint.blueprint_fingerprint,
        changed_ids=["access_policy_norm"],
    ).to_dict()
    reverse = blueprint_reverse_trace(
        blueprint,
        blueprint_fingerprint=blueprint.blueprint_fingerprint,
        target_id="declared_policy_decision",
    ).to_dict()

    impacted_ids = {row["member_id"] for row in impact["affected_members"]}
    reverse_ids = {row["member_id"] for row in reverse["traced_members"]}
    assert "declared_policy_decision" in impacted_ids
    assert "policy_decision_state" in impacted_ids
    assert "access_policy_norm" in reverse_ids
    assert "request_actor" in reverse_ids
    assert set(reverse["terminal_input_ids"]).issuperset(
        {
            "external_policy_request",
            "policy_subject",
            "policy_rule",
            "policy_observation",
            "policy_check",
        }
    )
    assert impact["gaps"] == []
    assert reverse["gaps"] == []

    report = check_world_blueprint(blueprint)
    assert report.status == "PASS"
    assert report.native_domain_qualified is True
    assert report.full_domain_qualified is False
