from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from tests.helpers import attach_task_purpose_declarations
from worldguard import (
    ModelMeshContract,
    qualification_context_for_node,
    run_model_mesh,
    run_worldguard,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "worldguard" / "scripts" / "check_entry_prompt_bundle.py"
SPEC = importlib.util.spec_from_file_location("worldguard_prompt_bundle", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SKILL_ROOT = ROOT / "skills" / "worldguard"


def _compose(**facts):
    return MODULE.compose_prompt_bundle(SKILL_ROOT, facts)


def _claim(*, semantics: list[str], target_guards: list[str] | None = None) -> dict:
    return {
        "claim_id": "claim:prompt-bundle",
        "text": "check the requested world behavior",
        "target_guards": target_guards or [],
        "requested_semantics": semantics,
    }


def test_bounded_event_bundle_stays_light():
    report = _compose(
        task_shape="unit_contract",
        claim=_claim(semantics=["event"], target_guards=["EventGuard"]),
    )

    assert report["ok"], report["findings"]
    assert report["derived_guard_ids"] == ["EventGuard"]
    assert "references/task-local-model-deepening.md" not in report["bundle_paths"]
    assert "references/model-mesh.md" not in report["bundle_paths"]
    assert "references/template-packs.md" not in report["bundle_paths"]


def test_predictive_bundle_derives_event_and_causal_and_loads_deepening():
    report = _compose(
        task_shape="unit_contract",
        claim=_claim(semantics=["prediction"], target_guards=["EventGuard"]),
    )

    assert report["ok"], report["findings"]
    assert report["derived_guard_ids"] == ["EventGuard", "CausalGuard"]
    assert report["caller_target_guard_omissions"] == ["CausalGuard"]
    assert "references/task-local-model-deepening.md" in report["bundle_paths"]


def test_mesh_handoff_loads_only_mesh_handoff_and_guard_material():
    report = _compose(
        task_shape="model_mesh",
        claim=_claim(semantics=["agent", "normative"]),
        handoff_present=True,
    )

    assert report["ok"], report["findings"]
    assert report["derived_guard_ids"] == ["AgentGuard", "NormGuard"]
    assert "references/model-mesh.md" in report["bundle_paths"]
    assert "references/handoff-contracts.md" in report["bundle_paths"]
    assert "references/task-local-model-deepening.md" not in report["bundle_paths"]


def test_template_shape_does_not_invent_guard_routes():
    report = _compose(task_shape="template_pack")

    assert report["ok"], report["findings"]
    assert report["derived_guard_ids"] == []
    assert "references/template-packs.md" in report["bundle_paths"]
    assert "references/guard-model-contract.md" not in report["bundle_paths"]


def test_retired_shape_candidates_block_without_guessing():
    report = _compose(
        task_shape_candidates=["unit_contract", "model_mesh"],
        claim=_claim(semantics=["event"]),
    )

    assert not report["ok"]
    codes = {item["code"] for item in report["findings"]}
    assert "prompt_fact_fields_retired" in codes
    assert "task_shape_invalid" in codes


def test_unmapped_semantics_block():
    report = _compose(
        task_shape="unit_contract",
        claim=_claim(semantics=["quantum_oracle"]),
    )

    assert not report["ok"]
    assert "claim_semantics_unmapped" in {item["code"] for item in report["findings"]}


def test_missing_mandatory_reference_blocks(tmp_path: Path):
    topology = json.loads(
        (SKILL_ROOT / "references" / "internal-guard-routes.json").read_text(
            encoding="utf-8"
        )
    )
    topology["task_shapes"][0]["reference_path"] = "references/missing.md"
    topology_path = tmp_path / "routes.json"
    topology_path.write_text(json.dumps(topology), encoding="utf-8")

    report = MODULE.compose_prompt_bundle(
        SKILL_ROOT,
        {"task_shape": "unit_contract", "claim": _claim(semantics=["event"])},
        topology_path=topology_path,
    )

    assert not report["ok"]
    assert any(
        item["code"] == "mandatory_prompt_reference_missing"
        and item.get("path") == "references/missing.md"
        for item in report["findings"]
    )


def test_prompt_budget_blocks_after_mandatory_paths_are_composed(tmp_path: Path):
    topology = json.loads(
        (SKILL_ROOT / "references" / "internal-guard-routes.json").read_text(
            encoding="utf-8"
        )
    )
    topology["prompt_budget"]["selected_operation_bundle_max_bytes"] = 1
    topology_path = tmp_path / "routes.json"
    topology_path.write_text(json.dumps(topology), encoding="utf-8")

    report = MODULE.compose_prompt_bundle(
        SKILL_ROOT,
        {"task_shape": "unit_contract", "claim": _claim(semantics=["event"])},
        topology_path=topology_path,
    )

    assert not report["ok"]
    assert "selected_prompt_bundle_budget_exceeded" in {
        item["code"] for item in report["findings"]
    }


def test_unit_mesh_and_prompt_use_same_guard_denominator_and_fingerprint():
    claim = _claim(semantics=["prediction"], target_guards=["EventGuard"])
    contract = attach_task_purpose_declarations(
        {
            "contract_id": "prompt-parity",
            "run_id": "prompt-parity-run",
            "claim": claim,
            "world_model": {
                "model_id": "prompt-parity-world",
                "model_version": "revision-1",
            },
            "inputs": {
                "events": [
                    {"event_id": "ready", "at": "t0", "initiates": "ready"}
                ],
                "causal_model": {
                    "variables": ["ready"],
                    "equations": {"ready": "1"},
                    "scenarios": {"normal": {"ready": 1}},
                    "interventions": [],
                    "counterfactuals": [],
                },
            },
        },
        guards=["EventGuard", "CausalGuard"],
    )
    mesh_contract = ModelMeshContract.from_dict(
        {
            "mesh_id": "prompt-parity-mesh",
            "nodes": [{"model_id": "prompt-parity-world", "contract": contract}],
        }
    )
    context = qualification_context_for_node(mesh_contract, mesh_contract.nodes[0])
    unit = run_worldguard(contract, context=context)
    mesh_node = run_model_mesh(mesh_contract).node_reports["prompt-parity-world"]
    prompt = _compose(task_shape="unit_contract", claim=claim)

    assert prompt["ok"], prompt["findings"]
    assert prompt["derived_guard_ids"] == unit.derived_guards == mesh_node.derived_guards
    assert (
        prompt["guard_derivation_fingerprint"]
        == unit.guard_derivation_fingerprint
        == mesh_node.guard_derivation_fingerprint
    )


def test_route_capsule_budget_is_measured_in_utf8_bytes(tmp_path: Path):
    topology = json.loads(
        (SKILL_ROOT / "references" / "internal-guard-routes.json").read_text(
            encoding="utf-8"
        )
    )
    topology["prompt_budget"]["single_route_capsule_max_bytes"] = 1
    topology_path = tmp_path / "routes.json"
    topology_path.write_text(json.dumps(topology), encoding="utf-8")

    report = MODULE.compose_prompt_bundle(
        SKILL_ROOT,
        {"task_shape": "unit_contract", "claim": _claim(semantics=["event"])},
        topology_path=topology_path,
    )

    assert not report["ok"]
    assert report["route_capsules"][0]["guard_id"] == "EventGuard"
    assert "route_capsule_budget_exceeded" in {
        item["code"] for item in report["findings"]
    }


def _blueprint_facts(operation: str, **overrides):
    facts = {
        "task_shape": "world_blueprint",
        "request_source_spans": [
            {
                "source_id": "user-request",
                "start": 0,
                "end": 28,
                "text": "create or query this blueprint",
            }
        ],
        "blueprint_operation": operation,
        "target_id": "planning-workflow",
        "target_revision": "revision-1",
        "declared_boundary": "planning workflow revision 1 only",
        "world_blueprint_or_query_identity": "blueprint:planning-workflow:revision-1",
        "affected_guard_ids": [],
    }
    facts.update(overrides)
    return facts


def test_world_blueprint_route_blocks_minimal_unbound_facts():
    for operation in ("check", "trace"):
        report = _compose(
            task_shape="world_blueprint",
            blueprint_operation=operation,
            affected_guard_ids=[],
        )
        assert not report["ok"]
        assert "blueprint_required_input_missing" in {
            item["code"] for item in report["findings"]
        }


def test_world_blueprint_all_eight_operations_are_exact():
    cases = {
        "create": {"target_material_refs": ["request:user-request"]},
        "update": {
            "change_intent": "add one scheduling branch",
            "changed_ids": ["schedule_transition"],
        },
        "check": {},
        "impact": {"changed_ids": ["schedule_transition"]},
        "trace": {"trace_target_id": "root_plan_outcome"},
        "bundle-export": {"bundle_destination": "exports/planning.bundle.json"},
        "bundle-verify": {
            "bundle_identity": "sha256:bundle",
            "materialization_root": "empty/verify",
        },
        "bundle-query": {
            "bundle_identity": "sha256:bundle",
            "materialization_root": "empty/query",
            "bundle_query_kind": "node",
            "bundle_member_id": "plan_root",
        },
    }

    for operation, extra in cases.items():
        report = _compose(**_blueprint_facts(operation, **extra))
        assert report["ok"], (operation, report["findings"])
        assert report["blueprint_operation"] == operation
        assert "references/world-blueprint.md" in report["bundle_paths"]
        if operation.startswith("bundle-"):
            assert "semantic truth" in report["blueprint_operation_claim_boundary"]


def test_world_blueprint_reference_has_maintainable_headroom_and_one_route() -> None:
    reference = SKILL_ROOT / "references" / "world-blueprint.md"
    reference_text = reference.read_text(encoding="utf-8")
    report = _compose(**_blueprint_facts("check"))

    assert report["ok"], report["findings"]
    assert report["bundle_paths"].count("references/world-blueprint.md") == 1
    assert "references/guard-model-contract.md" not in report["bundle_paths"]
    assert report["blueprint_reference_bytes"] == len(reference.read_bytes())
    assert report["blueprint_reference_bytes"] <= 15000
    assert report["blueprint_reference_headroom_bytes"] >= 1000
    for required_boundary in (
        "not a source-code inventory",
        "Event ids appear only as `executed_event_ids`",
        "## Typed interfaces",
        "## Role-separated bindings",
        "## Understanding depth",
        "## Impact semantics",
        "## Reverse trace semantics",
        "## Claim boundary",
    ):
        assert required_boundary in reference_text

    affected = _compose(
        **_blueprint_facts("check", affected_guard_ids=["EventGuard"])
    )
    assert affected["ok"], affected["findings"]
    assert affected["bundle_paths"].count("references/world-blueprint.md") == 1
    assert affected["bundle_paths"].count("references/guard-model-contract.md") == 1


def test_world_blueprint_operation_specific_identity_is_required():
    missing_impact = _compose(**_blueprint_facts("impact", changed_ids=[]))
    missing_trace = _compose(**_blueprint_facts("trace", trace_target_id=""))
    missing_create = _compose(**_blueprint_facts("create"))
    missing_update = _compose(**_blueprint_facts("update", changed_ids=[]))
    missing_export = _compose(**_blueprint_facts("bundle-export"))
    missing_verify = _compose(**_blueprint_facts("bundle-verify"))
    missing_query = _compose(
        **_blueprint_facts(
            "bundle-query",
            bundle_identity="sha256:bundle",
            materialization_root="empty/query",
            bundle_query_kind="unknown",
            bundle_member_id="",
        )
    )

    for report in (
        missing_impact,
        missing_trace,
        missing_create,
        missing_update,
        missing_export,
        missing_verify,
        missing_query,
    ):
        assert not report["ok"]
        assert "blueprint_operation_input_missing" in {
            item["code"] for item in report["findings"]
        }


def test_bundle_verify_and_query_do_not_require_external_target_identity() -> None:
    common = {
        "task_shape": "world_blueprint",
        "request_source_spans": [
            {
                "source_id": "user-request",
                "start": 0,
                "end": 18,
                "text": "inspect this bundle",
            }
        ],
        "affected_guard_ids": [],
        "bundle_identity": "sha256:bundle",
        "materialization_root": "empty/materialization",
    }
    verify = _compose(**common, blueprint_operation="bundle-verify")
    query = _compose(
        **common,
        blueprint_operation="bundle-query",
        bundle_query_kind="binding",
        bundle_member_id="assignment_native",
    )

    assert verify["ok"], verify["findings"]
    assert query["ok"], query["findings"]
    assert "semantic truth" in verify["blueprint_operation_claim_boundary"]
    assert "semantic truth" in query["blueprint_operation_claim_boundary"]
