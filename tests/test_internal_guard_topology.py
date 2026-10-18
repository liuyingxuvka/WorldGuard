from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "skills"
    / "worldguard"
    / "scripts"
    / "check_internal_guard_topology.py"
)
SPEC = importlib.util.spec_from_file_location(
    "worldguard_internal_topology_check", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _payload() -> dict:
    return json.loads(
        (
            ROOT
            / "skills"
            / "worldguard"
            / "references"
            / "internal-guard-routes.json"
        ).read_text(encoding="utf-8")
    )


def test_current_worldguard_has_one_entry_and_seven_internal_routes():
    report = MODULE.check(ROOT)

    assert report["ok"], report["findings"]
    assert report["schema_version"] == "worldguard.internal_guard_topology_check.v5"
    assert "canonical projection owner" in report["claim_boundary"]
    assert "not evaluated here" in report["claim_boundary"]
    assert not hasattr(MODULE, "_runtime_inventory")
    assert not hasattr(MODULE, "_hash")
    assert report["public_skill_ids"] == ["worldguard"]
    assert report["project_console_ids"] == ["worldguard"]
    assert report["source_version"] == "0.7.15"
    assert len(report["internal_guard_ids"]) == 7
    assert report["semantic_input_surfaces"]["EventGuard"]["implementation"] == sorted(
        report["semantic_input_surfaces"]["EventGuard"]["binding"]
    )
    assert report["semantic_input_surfaces"]["CausalGuard"]["implementation"] == sorted(
        report["semantic_input_surfaces"]["CausalGuard"]["binding"]
    )
    assert report["semantic_input_surfaces"]["ConflictGuard"]["implementation"] == sorted(
        report["semantic_input_surfaces"]["ConflictGuard"]["binding"]
    )
    assert report["task_shape_ids"] == [
        "unit_contract",
        "model_mesh",
        "world_blueprint",
        "task_local_revision",
        "template_pack",
    ]


def test_source_version_identity_drift_is_rejected(monkeypatch):
    monkeypatch.setattr(MODULE, "EXPECTED_VERSION", "9.9.9")

    report = MODULE.check(ROOT)

    assert not report["ok"]
    assert "source_version_file_mismatch" in {
        finding["code"] for finding in report["findings"]
    }


def test_missing_internal_route_is_rejected(tmp_path: Path):
    payload = _payload()
    payload["routes"] = payload["routes"][:-1]
    topology = tmp_path / "topology.json"
    topology.write_text(json.dumps(payload), encoding="utf-8")

    report = MODULE.check(ROOT, topology_path=topology)

    assert not report["ok"]
    assert "declared_guard_inventory_mismatch" in {
        finding["code"] for finding in report["findings"]
    }


def test_non_predictive_guard_cannot_claim_predictive_mode(tmp_path: Path):
    payload = _payload()
    agent = next(
        row for row in payload["routes"] if row["guard_id"] == "AgentGuard"
    )
    agent["prediction_mode"] = "claim_derived_predictive_participant"
    topology = tmp_path / "topology.json"
    topology.write_text(json.dumps(payload), encoding="utf-8")

    report = MODULE.check(ROOT, topology_path=topology)

    assert not report["ok"]
    assert any(
        finding["code"] == "internal_route_binding_mismatch"
        and finding.get("guard_id") == "AgentGuard"
        and finding.get("field") == "prediction_mode"
        for finding in report["findings"]
    )


def test_missing_route_admission_field_is_rejected(tmp_path: Path):
    payload = _payload()
    del payload["routes"][0]["first_native_action"]
    topology = tmp_path / "topology.json"
    topology.write_text(json.dumps(payload), encoding="utf-8")

    report = MODULE.check(ROOT, topology_path=topology)

    assert not report["ok"]
    assert any(
        finding["code"] == "internal_route_fields_missing"
        and finding.get("guard_id") == "EventGuard"
        and "first_native_action" in finding.get("fields", [])
        for finding in report["findings"]
    )


def test_implementation_input_surface_catches_shared_route_and_binding_omission(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from worldguard.semantic import EXECUTOR_REGISTRY

    omitted_field = "inputs.event_model.initial_states"
    payload = _payload()
    event_route = next(
        row for row in payload["routes"] if row["guard_id"] == "EventGuard"
    )
    event_route["possible_consumed_input_fields"].remove(omitted_field)
    topology = tmp_path / "routes.json"
    topology.write_text(json.dumps(payload), encoding="utf-8")

    executor = EXECUTOR_REGISTRY["EventGuard"]
    narrowed_binding = replace(
        executor.binding,
        possible_consumed_input_fields=tuple(
            field
            for field in executor.binding.possible_consumed_input_fields
            if field != omitted_field
        ),
    )
    monkeypatch.setitem(
        EXECUTOR_REGISTRY,
        "EventGuard",
        replace(executor, binding=narrowed_binding),
    )

    report = MODULE.check(ROOT, topology_path=topology)

    assert not report["ok"]
    omission = next(
        finding
        for finding in report["findings"]
        if finding["code"] == "semantic_input_surface_omitted"
        and finding["guard_id"] == "EventGuard"
    )
    assert omission["fields"] == [omitted_field]
    assert not any(
        finding["code"] == "internal_route_binding_mismatch"
        and finding.get("guard_id") == "EventGuard"
        and finding.get("field") == "possible_consumed_input_fields"
        for finding in report["findings"]
    )


def test_retired_internal_route_required_input_field_is_rejected(
    tmp_path: Path,
) -> None:
    payload = _payload()
    event_route = next(
        row for row in payload["routes"] if row["guard_id"] == "EventGuard"
    )
    event_route["required_input_fields"] = event_route.pop(
        "possible_consumed_input_fields"
    )
    topology = tmp_path / "routes.json"
    topology.write_text(json.dumps(payload), encoding="utf-8")

    report = MODULE.check(ROOT, topology_path=topology)

    assert not report["ok"]
    assert {
        "retired_internal_route_input_field_present",
        "internal_route_fields_missing",
    } <= {finding["code"] for finding in report["findings"]}


def test_missing_task_shape_reference_is_rejected(tmp_path: Path):
    payload = _payload()
    payload["task_shapes"][0]["reference_path"] = "references/not-present.md"
    topology = tmp_path / "topology.json"
    topology.write_text(json.dumps(payload), encoding="utf-8")

    report = MODULE.check(ROOT, topology_path=topology)

    assert not report["ok"]
    assert any(
        finding["code"] == "task_shape_reference_missing"
        and finding.get("shape_id") == "unit_contract"
        for finding in report["findings"]
    )


def test_keyword_scoring_cannot_become_route_authority(tmp_path: Path):
    payload = _payload()
    payload["selection_authority"]["keyword_scoring_authoritative"] = True
    topology = tmp_path / "topology.json"
    topology.write_text(json.dumps(payload), encoding="utf-8")

    report = MODULE.check(ROOT, topology_path=topology)

    assert not report["ok"]
    assert "selection_authority_mismatch" in {
        finding["code"] for finding in report["findings"]
    }


def test_retired_runtime_authority_path_is_rejected(tmp_path: Path):
    alignment = tmp_path / "run_claim_derived_coverage_checks.py"
    alignment.write_text(
        "\n".join(
            (
                '"worldguard/skillguard_depth.py"',
                '"worldguard/execution_depth.py"',
                '"worldguard/execution_depth.py"',
                '"worldguard/execution_depth.py"',
            )
        ),
        encoding="utf-8",
    )

    report = MODULE.check(ROOT, flowguard_alignment_path=alignment)

    assert not report["ok"]
    assert "retired_runtime_authority_path_present" in {
        finding["code"] for finding in report["findings"]
    }
