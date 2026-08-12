from __future__ import annotations

import inspect
import json
import sys
from hashlib import sha256
from copy import deepcopy
from pathlib import Path

from worldguard.blueprint import (
    blueprint_impact,
    blueprint_reverse_trace,
    load_world_blueprint,
)


ROOT = Path(__file__).resolve().parents[1]
SKILLGUARD_ROOT = ROOT / "skills/worldguard/.skillguard"
FIXTURE = ROOT / "tests/fixtures/world_blueprint/planning_workflow_three_level.yaml"

BLUEPRINT_CHECK_ID = "check:worldguard:blueprint-integrity"
BLUEPRINT_OWNER_ID = "owner:worldguard:blueprint-integrity"
BLUEPRINT_OBLIGATION_IDS = {
    "obligation:worldguard-blueprint-complete-fixture",
    "obligation:worldguard-blueprint-known-bad-closure",
    "obligation:worldguard-blueprint-qualification",
    "obligation:worldguard-blueprint-impact-reverse-trace",
    "obligation:worldguard-blueprint-query-read-only",
}
PROJECTION_CHECK_ID = "check:worldguard:portable-runtime-projection"
PROJECTION_OWNER_ID = "owner:worldguard:portable-runtime-projection"
PROJECTION_OBLIGATION_IDS = {
    "obligation:worldguard-blueprint-source-bundle-parity",
    "obligation:worldguard-portable-runtime-projection",
}
BLUEPRINT_CHECK_ARGS = [
    "-m",
    "pytest",
    "-p",
    "no:cacheprovider",
    "tests/test_world_blueprint.py",
    "tests/test_world_blueprint_freeze_blockers.py",
    "tests/test_world_blueprint_target_semantic_authority.py",
    "tests/test_world_blueprint_object_census.py",
    "tests/test_qualification.py",
    "tests/test_blueprint_impact_trace.py",
    "tests/test_blueprint_cli.py",
    "tests/test_world_blueprint_policy_target.py",
    "tests/test_world_blueprint_seven_guard_matrix.py::test_seven_guard_matrix_uses_independent_domain_oracles",
    "tests/test_world_blueprint_seven_guard_matrix.py::test_owner_inputs_do_not_invent_domain_facts",
    "tests/test_world_blueprint_seven_guard_matrix.py::test_event_rollout_keeps_event_fluent_transition_and_state_identities_separate",
    "tests/test_world_blueprint_seven_guard_matrix.py::test_every_native_field_has_one_disposition_and_mutation_path",
    "tests/test_world_blueprint_seven_guard_matrix.py::test_causal_claim_scopes_are_requested_evaluated_and_licensed_honestly",
    "tests/test_skillguard_blueprint_integrity.py::test_blueprint_queries_leave_contract_and_fixture_unchanged",
    "-q",
]
PROJECTION_CHECK_ARGS = [
    "-m",
    "pytest",
    "tests/test_worldguard_portable_runtime_projection.py",
    "tests/test_world_blueprint_seven_guard_matrix.py::test_source_and_bundled_runtime_have_all_file_parity_and_isolated_import",
    "-q",
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_skill_entrypoint_has_current_static_contract_sections_and_fields() -> None:
    text = (ROOT / "skills/worldguard/SKILL.md").read_text(encoding="utf-8")
    headings = {
        line.removeprefix("## ").strip()
        for line in text.splitlines()
        if line.startswith("## ")
    }
    assert {
        "Purpose",
        "Entrypoint Scope",
        "Local Material Routing",
        "Entrypoint Acceptance Map",
        "Use When",
        "Do Not Use When",
        "Required Workflow",
        "Hard Gates",
        "Output Requirements",
    } <= headings
    lowered = text.lower()
    for field in (
        "evidence",
        "failures",
        "blockers",
        "skipped_checks",
        "residual_risk",
        "claim_boundary",
    ):
        assert field in lowered
    assert (
        "[references/task-local-model-deepening.md]"
        "(references/task-local-model-deepening.md)"
    ) in text
    assert "`task-local-model-deepening.md`" not in text


def test_blueprint_queries_leave_contract_and_fixture_unchanged() -> None:
    fixture_before = FIXTURE.read_bytes()
    blueprint = load_world_blueprint(FIXTURE)
    contract_before = deepcopy(blueprint.to_dict())

    blueprint_impact(
        blueprint,
        blueprint_fingerprint=blueprint.blueprint_fingerprint,
        changed_ids=["schedule_transition"],
    )
    blueprint_reverse_trace(
        blueprint,
        blueprint_fingerprint=blueprint.blueprint_fingerprint,
        target_id="root_plan_outcome",
    )

    assert blueprint.to_dict() == contract_before
    assert FIXTURE.read_bytes() == fixture_before


def test_native_skillguard_contract_has_distinct_domain_and_process_owners() -> None:
    source = _read_json(SKILLGUARD_ROOT / "contract-source.json")

    source_checks = source["checks"]
    assert len(source_checks) == 10
    assert len({row["execution_owner_id"] for row in source_checks}) == 10
    check_ids = {row["check_id"] for row in source_checks}
    assert {
        check_id
        for binding in source["step_bindings"]
        for check_id in binding["check_ids"]
    } == check_ids
    assert {
        row["native_check_id"] for row in source["native_check_bindings"]
    } == check_ids
    assert set(source["depth_profile"]["native_check_ids"]) == check_ids
    assert {
        obligation_id
        for row in source_checks
        for obligation_id in row["covers_obligation_ids"]
    } == set(source["closure_profiles"][0]["required_obligation_ids"])
    blueprint_checks = [
        row for row in source_checks if row["check_id"] == BLUEPRINT_CHECK_ID
    ]
    assert len(blueprint_checks) == 1
    blueprint_check = blueprint_checks[0]
    assert blueprint_check["execution_owner_id"] == BLUEPRINT_OWNER_ID
    assert blueprint_check["semantic_check_id"] == (
        "semantic:worldguard:blueprint-integrity"
    )
    assert blueprint_check["evidence_domain_id"] == "worldguard:blueprint-integrity"
    assert blueprint_check["command"] == "python"
    assert blueprint_check["args"] == BLUEPRINT_CHECK_ARGS
    assert set(blueprint_check["covers_obligation_ids"]) == BLUEPRINT_OBLIGATION_IDS
    assert blueprint_check["depends_on_check_ids"] == []

    selector_paths = {
        row["path"] for row in blueprint_check["input_selectors"]
    }
    required_selector_paths = {
        "worldguard",
        "skills/worldguard/SKILL.md",
        "skills/worldguard/agents/openai.yaml",
        "skills/worldguard/references/world-blueprint.md",
        "skills/worldguard/references/entry-routing.md",
        "skills/worldguard/references/model-authority.md",
        "skills/worldguard/references/closure-report.md",
        "skills/worldguard/references/internal-guard-routes.json",
        "tests/fixtures/world_blueprint",
        "tests/test_world_blueprint.py",
        "tests/test_world_blueprint_freeze_blockers.py",
        "tests/test_world_blueprint_target_semantic_authority.py",
        "tests/test_world_blueprint_object_census.py",
        "tests/object_census_fixtures.py",
        "tests/test_qualification.py",
        "tests/test_blueprint_impact_trace.py",
        "tests/test_skillguard_blueprint_integrity.py",
        "tests/test_world_blueprint_seven_guard_matrix.py",
        "tests/test_blueprint_cli.py",
        "tests/test_world_blueprint_policy_target.py",
        "scripts/refresh_world_blueprint_external_dna_fixtures.py",
    }
    assert selector_paths == required_selector_paths
    assert BLUEPRINT_CHECK_ID in source["depth_profile"]["native_check_ids"]
    assert BLUEPRINT_CHECK_ID in source["depth_profile"]["provider_runtime"][
        "readiness_check_ids"
    ]
    assert BLUEPRINT_OBLIGATION_IDS <= set(
        source["closure_profiles"][0]["required_obligation_ids"]
    )

    projection_check = next(
        row for row in source_checks if row["check_id"] == PROJECTION_CHECK_ID
    )
    assert projection_check["execution_owner_id"] == PROJECTION_OWNER_ID
    assert projection_check["evidence_domain_id"] == (
        "worldguard:portable-runtime-projection"
    )
    assert projection_check["args"] == PROJECTION_CHECK_ARGS
    assert set(projection_check["covers_obligation_ids"]) == (
        PROJECTION_OBLIGATION_IDS
    )
    assert {
        row["path"] for row in projection_check["input_selectors"]
    } == {
        "worldguard",
        "skills/worldguard/runtime/worldguard",
        "scripts/sync_worldguard_portable_runtime.py",
        "tests/test_worldguard_portable_runtime_projection.py",
        "tests/test_world_blueprint_seven_guard_matrix.py",
    }
    assert PROJECTION_CHECK_ID in source["depth_profile"]["native_check_ids"]
    assert PROJECTION_CHECK_ID in source["depth_profile"]["provider_runtime"][
        "readiness_check_ids"
    ]
    assert PROJECTION_OBLIGATION_IDS <= set(
        source["closure_profiles"][0]["required_obligation_ids"]
    )

    assert not any("--all" in row.get("args", []) for row in source_checks)

    topology_check = next(
        row
        for row in source_checks
        if row["check_id"] == "check:worldguard:internal-guard-topology"
    )
    assert topology_check["args"] == [
        "-m",
        "pytest",
        "tests/test_internal_guard_topology.py",
        "tests/test_run_worldguard_check_helper.py",
        "-q",
    ]
    assert "obligation:worldguard-portable-check-entry-facade" in (
        topology_check["covers_obligation_ids"]
    )
    topology_paths = {row["path"] for row in topology_check["input_selectors"]}
    assert {
        "skills/worldguard/scripts/run_worldguard_check.py",
        "tests/test_run_worldguard_check_helper.py",
        "examples/model_mesh/basic_mesh.yaml",
        "skills/worldguard/runtime/worldguard",
    } <= topology_paths
    assert "raw-byte source/bundle parity remains owned only" in (
        topology_check["coverage_rationale"].lower()
    )

    model_check = next(
        row
        for row in source_checks
        if row["check_id"] == "check:worldguard:flowguard-contract-model"
    )
    assert model_check["evidence_domain_id"] == (
        "worldguard:maintenance-process-model"
    )
    assert model_check["covers_obligation_ids"] == [
        "obligation:worldguard-maintenance-model-export"
    ]
    assert "does not prove world domain behavior" in (
        model_check["coverage_rationale"].lower()
    )

    fact_revision_test_path = "tests/test_fact_revision.py"
    assert [
        row["check_id"]
        for row in source_checks
        if fact_revision_test_path
        in {selector["path"] for selector in row["input_selectors"]}
    ] == ["check:worldguard:fact-revision"]


def test_test_mesh_and_historical_plan_have_one_static_authority() -> None:
    scripts_root = Path.home() / ".codex/skills/skillguard/scripts"
    scripts_root_text = str(scripts_root)
    inserted = scripts_root_text not in sys.path
    if inserted:
        sys.path.insert(0, scripts_root_text)
    try:
        from skillguard_v2.test_mesh import (  # pylint: disable=import-outside-toplevel
            _load_current_test_mesh_manifest,
            execute_test_mesh,
        )
    finally:
        if inserted:
            sys.path.remove(scripts_root_text)

    mesh_path = SKILLGUARD_ROOT / "test-mesh.json"
    mesh = _load_current_test_mesh_manifest(mesh_path)
    assert [row["profile_id"] for row in mesh["profiles"]] == ["focused", "full"]
    assert mesh["profiles"][0]["full_admission_required"] is False
    assert mesh["profiles"][1]["full_admission_required"] is True
    assert inspect.signature(execute_test_mesh).parameters["mode"].default == "plan_only"
    assert list(ROOT.rglob("test-mesh.json")) == [mesh_path]

    historical = _read_json(ROOT / ".skillguard/worldguard-validation-plan.json")
    assert historical["status"] == "stale"
    assert historical["execution_disposition"] == "not_executable"
    assert historical["plan_id"] == (
        "worldguard-skillguard-0.7-historical-seven-check-validation"
    )
    assert "execution_identity" not in historical
    assert "historical_execution_identity" in historical
    assert len(historical["checks"]) == 7
    assert BLUEPRINT_CHECK_ID not in {
        row["check_id"] for row in historical["checks"]
    }
    assert historical["current_static_authority"] == {
        "contract_source_path": "skills/worldguard/.skillguard/contract-source.json",
        "test_mesh_path": "skills/worldguard/.skillguard/test-mesh.json",
        "execution_evidence": "not_run",
    }
    historical_hashes = historical["source_authority"]
    assert historical_hashes["contract_source_file_sha256"] != sha256(
        (SKILLGUARD_ROOT / "contract-source.json").read_bytes()
    ).hexdigest().upper()
    assert historical_hashes["compiled_contract_hash"] != sha256(
        (SKILLGUARD_ROOT / "compiled-contract.json").read_bytes()
    ).hexdigest().upper()
    assert historical_hashes["check_manifest_hash"] != sha256(
        (SKILLGUARD_ROOT / "check-manifest.json").read_bytes()
    ).hexdigest().upper()
