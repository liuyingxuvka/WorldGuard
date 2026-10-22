from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

import worldguard.blueprint as blueprint_module
from worldguard.blueprint import (
    BlueprintError,
    WorldBlueprintContract,
    _build_blueprint_indexes,
    blueprint_impact,
    blueprint_reverse_trace,
    check_world_blueprint,
    load_world_blueprint,
)
from worldguard.semantic import fingerprint_mesh


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/world_blueprint/planning_workflow_three_level.yaml"


def _payload() -> dict:
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


def _current(payload: dict) -> WorldBlueprintContract:
    payload = deepcopy(payload)
    payload.pop("blueprint_fingerprint", None)
    return WorldBlueprintContract.from_dict(payload, source_root=FIXTURE.parent)


def _renew_native_semantic_fingerprint(semantic: dict) -> None:
    identity = {
        key: value
        for key, value in semantic.items()
        if key not in {"content_fingerprint", "task_purpose"}
    }
    semantic["content_fingerprint"] = "sha256:" + fingerprint_mesh(identity)


def _assert_unqualified_query_source(blueprint: WorldBlueprintContract) -> None:
    qualification = check_world_blueprint(blueprint)
    assert qualification.status.value != "PASS" or not qualification.native_domain_qualified
    expected_gap_ids = sorted(gap.gap_id for gap in qualification.gaps)

    operations = (
        lambda: blueprint_impact(
            blueprint,
            changed_ids=["schedule_transition"],
        ),
        lambda: blueprint_reverse_trace(
            blueprint,
            target_id="root_plan_outcome",
        ),
    )
    for operation in operations:
        with pytest.raises(BlueprintError) as caught:
            operation()
        assert caught.value.code == "WORLD_BLUEPRINT_QUERY_SOURCE_UNQUALIFIED"
        assert caught.value.details == {
            "blueprint_id": blueprint.blueprint_id,
            "blueprint_fingerprint": blueprint.blueprint_fingerprint,
            "qualification_report_fingerprint": qualification.report_fingerprint,
            "qualification_status": qualification.status.value,
            "native_domain_qualified": qualification.native_domain_qualified,
            "source_gap_ids": expected_gap_ids,
        }


def test_leaf_change_has_exact_dependents_ancestors_interfaces_and_bindings() -> None:
    blueprint = load_world_blueprint(FIXTURE)

    report = blueprint_impact(
        blueprint,
        changed_ids=["schedule_transition"],
    )

    affected = set(report.materialized_ids)
    assert {
        "schedule_transition",
        "schedule_task_leaf",
        "scheduling_layer",
        "plan_root",
        "root_plan_outcome",
        "resource_reservation",
        "scheduling_summary",
        "governance_summary",
        "plan_outcome",
        "schedule_test",
        "schedule_native",
    } <= affected
    assert "authorization_norm" not in affected
    assert "authorize_task_leaf" not in affected
    assert all(row["path_reason"]["relation"] for row in report.affected_members)
    assert set(report.terminal_binding_ids) >= {
        "schedule_material",
        "schedule_evidence",
        "schedule_test",
        "schedule_native",
    }


def test_multiple_changed_ids_and_repeat_are_deterministic() -> None:
    blueprint = load_world_blueprint(FIXTURE)
    args = {
        "changed_ids": ["authorization_norm", "schedule_transition"],
    }

    first = blueprint_impact(blueprint, **args)
    second = blueprint_impact(blueprint, **args)

    assert first.to_dict() == second.to_dict()
    assert first.result_fingerprint == second.result_fingerprint
    assert first.changed_ids == ("authorization_norm", "schedule_transition")


def test_impact_rejects_unknown_id_without_widening() -> None:
    blueprint = load_world_blueprint(FIXTURE)
    with pytest.raises(BlueprintError) as caught:
        blueprint_impact(
            blueprint,
            changed_ids=["schedule_transition", "not-in-blueprint"],
        )
    assert caught.value.code == "WORLD_BLUEPRINT_QUERY_ID_UNKNOWN"
    assert caught.value.details == {"unknown_ids": ["not-in-blueprint"]}


def test_each_query_runs_exactly_one_current_source_preflight(monkeypatch) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    real_check = blueprint_module.check_world_blueprint
    calls: list[str] = []

    def counted_check(candidate):
        calls.append(candidate.blueprint_fingerprint)
        return real_check(candidate)

    monkeypatch.setattr(blueprint_module, "check_world_blueprint", counted_check)

    blueprint_impact(
        blueprint,
        changed_ids=["schedule_transition"],
    )
    assert calls == [blueprint.blueprint_fingerprint]

    blueprint_reverse_trace(
        blueprint,
        target_id="root_plan_outcome",
    )
    assert calls == [
        blueprint.blueprint_fingerprint,
        blueprint.blueprint_fingerprint,
    ]


def test_root_output_reverse_trace_reaches_leaf_inputs_and_all_binding_roles() -> None:
    blueprint = load_world_blueprint(FIXTURE)

    report = blueprint_reverse_trace(
        blueprint,
        target_id="root_plan_outcome",
    )

    traced = {row["member_id"] for row in report.traced_members}
    assert {
        "assignment_transition",
        "schedule_transition",
        "resource_reservation",
        "authorization_norm",
        "assignment_transition_in",
        "schedule_transition_in",
        "resource_reservation_in",
        "authorization_norm_in",
    } <= traced
    assert "external_plan_request" in report.terminal_input_ids
    assert set(report.terminal_binding_ids) >= {
        "assignment_material",
        "assignment_evidence",
        "assignment_test",
        "assignment_native",
        "schedule_material",
        "schedule_evidence",
        "schedule_test",
        "schedule_native",
        "resource_material",
        "resource_evidence",
        "resource_test",
        "resource_native",
        "norm_material",
        "norm_evidence",
        "norm_test",
        "norm_native",
    }
    assert report.gaps == ()
    assert report.cycle_witnesses == ()


def test_input_source_edges_drive_impact_and_reverse_trace() -> None:
    blueprint = load_world_blueprint(FIXTURE)

    impact = blueprint_impact(
        blueprint,
        changed_ids=["external_plan_request"],
    )
    affected = set(impact.materialized_ids)
    assert {
        "root_plan_request",
        "allocation_request",
        "assign_task_request",
        "assignment_transition_in",
        "assignment_transition",
        "root_plan_outcome",
    } <= affected

    trace = blueprint_reverse_trace(
        blueprint,
        target_id="assignment_transition",
    )
    relations = {edge["relation"] for edge in trace.traversed_edges}
    assert {"maps_element_input", "maps_child_input", "external_input"} <= relations
    assert "external_plan_request" in trace.terminal_input_ids


def test_every_stable_blueprint_object_kind_is_an_impact_seed() -> None:
    payload = _payload()
    payload["declared_gaps"] = [
        {
            "gap_id": "gap_future_evidence",
            "gap_kind": "bindings",
            "code": "WORLD_BLUEPRINT_DECLARED_TEST_GAP",
            "message": "A future evidence source is intentionally outside this fixture.",
            "disposition": "boundary",
            "affected_claim_boundary": "planning workflow revision 1 only",
            "node_id": "authorize_task_leaf",
            "element_id": "authorization_norm",
        }
    ]
    blueprint = _current(payload)
    indexes = _build_blueprint_indexes(blueprint)
    expected_kinds = {
        "blueprint",
        "target",
        "node",
        "node_input_port",
        "node_output_port",
        "child_input_mapping",
        "element_input_mapping",
        "interface_mapping",
        "output_derivation",
        "element",
        "native_semantic",
        "element_input_port",
        "element_output_port",
        "element_dependency",
        "binding:target_material",
        "binding:evidence",
        "binding:test_check",
        "binding:native_result",
        "resource",
        "declared_input",
        "declared_output",
        "declared_gap",
    }
    assert set(indexes.kinds.values()) == expected_kinds
    assert indexes.kinds["gap_future_evidence"] == "declared_gap"

    blueprint = load_world_blueprint(FIXTURE)
    indexes = _build_blueprint_indexes(blueprint)
    assert set(indexes.kinds.values()) == expected_kinds.difference({"declared_gap"})
    representative_by_kind: dict[str, str] = {}
    for member_id, kind in sorted(indexes.kinds.items()):
        representative_by_kind.setdefault(kind, member_id)
    for kind in sorted(expected_kinds.difference({"declared_gap"})):
        member_id = representative_by_kind[kind]
        report = blueprint_impact(
            blueprint,
            changed_ids=[member_id],
        )
        assert member_id in report.materialized_ids, kind

    semantic = blueprint_impact(
        blueprint,
        changed_ids=["semantic:schedule_transition"],
    )
    assert {"schedule_transition", "schedule_native", "plan_root"} <= set(
        semantic.materialized_ids
    )


def test_dependency_and_declared_output_seed_affect_both_relation_endpoints() -> None:
    blueprint = load_world_blueprint(FIXTURE)
    dependency = blueprint_impact(
        blueprint,
        changed_ids=["dep_schedule_assignment"],
    )
    assert {"assignment_transition", "schedule_transition"} <= set(
        dependency.materialized_ids
    )

    output = blueprint_impact(
        blueprint,
        changed_ids=["declared_plan_outcome"],
    )
    assert {"plan_root", "root_plan_outcome", "planning-workflow"} <= set(
        output.materialized_ids
    )


def test_broken_parent_child_hop_rejects_the_query_source_before_trace() -> None:
    payload = _payload()
    allocation = next(
        node for node in payload["nodes"] if node["node_id"] == "allocation_layer"
    )
    allocation["child_output_mappings"] = []
    blueprint = _current(payload)

    qualification = check_world_blueprint(blueprint)
    mapping_gap_ids = {
        gap.gap_id
        for gap in qualification.gaps
        if gap.code == "WORLD_BLUEPRINT_CHILD_OUTPUT_MAPPING_CARDINALITY"
    }
    assert mapping_gap_ids

    _assert_unqualified_query_source(blueprint)


@pytest.mark.parametrize("source_defect", ["binding", "native", "provider"])
def test_impact_and_trace_reject_each_unqualified_source_class(
    source_defect: str,
) -> None:
    payload = _payload()
    if source_defect == "binding":
        binding = next(
            row for row in payload["bindings"] if row["binding_id"] == "assignment_evidence"
        )
        binding["freshness_status"] = "stale"
    elif source_defect == "native":
        element = next(
            row
            for row in payload["elements"]
            if row["element_id"] == "schedule_transition"
        )
        semantic = element["native_semantic"]
        semantic["semantic_fields"]["target_state"] = semantic["semantic_fields"][
            "source_state"
        ]
        _renew_native_semantic_fingerprint(semantic)
    else:
        binding = next(
            row for row in payload["bindings"] if row["binding_id"] == "assignment_evidence"
        )
        binding.update(
            {
                "observation_mode": "provider_content",
                "provider_id": "unregistered.query.provider",
                "provider_version": "v1",
                "provider_capability_id": "unregistered.query.capability",
            }
        )

    _assert_unqualified_query_source(_current(payload))


def test_unqualified_source_stops_before_query_index_materialization(monkeypatch) -> None:
    payload = _payload()
    allocation = next(
        node for node in payload["nodes"] if node["node_id"] == "allocation_layer"
    )
    allocation["child_output_mappings"] = []
    blueprint = _current(payload)
    index_calls: list[str] = []

    def reject_index(candidate):
        index_calls.append(candidate.blueprint_fingerprint)
        raise AssertionError("query index must not be built from an unqualified source")

    monkeypatch.setattr(blueprint_module, "_build_blueprint_indexes", reject_index)
    _assert_unqualified_query_source(blueprint)
    assert index_calls == []


def test_dependency_feedback_reports_cycle_witness_and_terminates() -> None:
    payload = _payload()
    assignment = next(
        element
        for element in payload["elements"]
        if element["element_id"] == "assignment_transition"
    )
    assignment["dependencies"].append(
        {
            "dependency_id": "dep_assignment_schedule_feedback",
            "relation": "depends_on",
            "depends_on_element_id": "schedule_transition",
        }
    )
    blueprint = _current(payload)

    report = blueprint_reverse_trace(
        blueprint,
        target_id="root_plan_outcome",
    )

    assert report.cycle_witnesses
    assert any(
        {"assignment_transition", "schedule_transition"}
        <= set(witness["member_ids"])
        for witness in report.cycle_witnesses
    )
    assert len(report.traced_members) < 200


def test_reverse_trace_rejects_unknown_target() -> None:
    blueprint = load_world_blueprint(FIXTURE)
    with pytest.raises(BlueprintError) as caught:
        blueprint_reverse_trace(
            blueprint,
            target_id="unknown-output",
        )
    assert caught.value.code == "WORLD_BLUEPRINT_QUERY_ID_UNKNOWN"


def test_reverse_trace_rejects_non_traceable_blueprint_container() -> None:
    blueprint = load_world_blueprint(FIXTURE)

    with pytest.raises(BlueprintError) as caught:
        blueprint_reverse_trace(
            blueprint,
            target_id=blueprint.blueprint_id,
        )

    assert caught.value.code == "WORLD_BLUEPRINT_TRACE_TARGET_KIND_INVALID"
