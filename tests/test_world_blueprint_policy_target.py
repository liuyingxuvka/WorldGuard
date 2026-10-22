from __future__ import annotations

import json
from pathlib import Path

from worldguard.blueprint import (
    GuardStatus,
    blueprint_impact,
    blueprint_reverse_trace,
    check_world_blueprint,
    load_world_blueprint,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests/fixtures/world_blueprint"
FIXTURE = FIXTURE_ROOT / "policy_access_execution.yaml"
MATERIAL = FIXTURE_ROOT / "support/policy-access-target-material.json"


def test_policy_target_is_independent_and_every_declared_role_is_bound() -> None:
    blueprint = load_world_blueprint(FIXTURE)
    material = json.loads(MATERIAL.read_text(encoding="utf-8"))

    report = check_world_blueprint(blueprint)

    assert report.status == GuardStatus.PASS
    assert report.native_domain_qualified is True
    assert report.gaps == ()
    assert blueprint.target_id == "policy-access-execution"
    assert blueprint.target_revision == "policy-revision-1"
    serialized_target = json.dumps(
        {"blueprint": blueprint.to_dict(), "material": material},
        ensure_ascii=False,
        sort_keys=True,
    )
    assert "planning-workflow" not in serialized_target
    assert "workflow_record_" not in serialized_target
    declared = {
        (element.element_id, role)
        for element in blueprint.elements
        for role in element.required_binding_roles
    }
    bound = {(row.subject_element_id, row.role) for row in blueprint.bindings}
    assert len(blueprint.elements) == 3
    assert declared == bound
    assert len(declared) == 8


def test_policy_target_runs_in_memory_impact_and_reverse_trace() -> None:
    blueprint = load_world_blueprint(FIXTURE)

    impact = blueprint_impact(
        blueprint,
        changed_ids=["access_policy_norm"],
    ).to_dict()
    reverse = blueprint_reverse_trace(
        blueprint,
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
