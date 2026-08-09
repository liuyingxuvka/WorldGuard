from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.sync_worldguard_portable_runtime import audit_projection
from tests.helpers import attach_task_purpose_declarations
from worldguard.blueprint import (
    NATIVE_SEMANTIC_FIELDS,
    NATIVE_SEMANTIC_FIELD_DISPOSITIONS,
    BlueprintBinding,
    BlueprintError,
    NativeSemanticRef,
    WorldElement,
    _blueprint_native_field_dispositions,
    _blueprint_native_inputs,
    _execute_blueprint_native_semantic,
    load_world_blueprint,
)
from worldguard.contracts import GuardContract
from worldguard.guard_model_contract import (
    GUARD_MODEL_PURPOSES,
    NATIVE_GOOD_CASES,
    PROTECTED_FAILURE_CLASSES,
)
from worldguard.semantic import EXECUTOR_REGISTRY, SemanticStatus


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_FIXTURE = (
    ROOT / "tests/fixtures/world_blueprint/planning_workflow_three_level.yaml"
)
MATRIX_FIXTURE = (
    ROOT / "tests/fixtures/world_blueprint/seven_guard_native_owner_matrix.json"
)
EXPECTED_OWNER_SET = {
    "EventGuard",
    "AgentGuard",
    "SpaceGuard",
    "ResourceGuard",
    "CausalGuard",
    "ConflictGuard",
    "NormGuard",
}


def _independent_fingerprint(payload: dict) -> str:
    body = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _semantic_payload(case: dict, *, boundary: str) -> dict:
    raw = case["raw_observation"]
    element_id = raw["element_id"]
    kind = raw["element_kind"]
    identity = {
        "semantic_id": f"semantic:{element_id}",
        "element_kind": kind,
        "native_object_id": f"native:{element_id}",
        "native_schema_id": f"worldguard.native.{kind}.v1",
        "provider_id": "worldguard.seven-guard-matrix",
        "provider_version": "v1",
        "observation_binding_id": f"binding:{element_id}",
        "semantic_fields": raw["semantic_fields"],
        "claim_boundary": boundary,
    }
    oracle = case.get("oracle", {})
    owner_guard = oracle.get("owner_guard", "")
    if owner_guard:
        purpose = next(row for row in GUARD_MODEL_PURPOSES if row.guard == owner_guard)
        observed_codes = [
            *oracle.get("structural_error_codes", []),
            *oracle.get("semantic_finding_codes", []),
        ]
        selected = next(
            (
                row
                for row in PROTECTED_FAILURE_CLASSES
                if row.guard == owner_guard and row.code in observed_codes
            ),
            next(row for row in PROTECTED_FAILURE_CLASSES if row.guard == owner_guard),
        )
        owner_pass = (
            oracle.get("structural_status") == "PASS"
            and oracle.get("semantic_status") == "PASS"
        )
        family_good = next(row for row in NATIVE_GOOD_CASES if row.guard == owner_guard)
        good_inputs = (
            oracle["canonical_owner_inputs"] if owner_pass else dict(family_good.inputs)
        )
        bad_inputs = (
            oracle["canonical_owner_inputs"]
            if selected.code in observed_codes
            else dict(selected.inputs)
        )
        identity["task_purpose"] = {
            "declaration_id": f"purpose:matrix:{element_id}",
            "purpose": purpose.purpose,
            "boundary": boundary,
            "selected_failure_ids": [selected.failure_id],
            "behavior_cases": [
                {
                    "case_id": f"case:matrix:{element_id}:good",
                    "case_kind": "known_good",
                    "text": case.get("description", family_good.text),
                    "inputs": good_inputs,
                    "coverage_context": {},
                    "pre_state": {},
                    "expected_output": (
                        oracle.get("output_subset", {}) if owner_pass else {}
                    ),
                    "post_state": {},
                    "effects": {},
                    "state_effect_disposition": "unverified",
                    "state_effect_reason": "The matrix checks the bounded native owner output only.",
                    "failure_id": "",
                    "blocked_claim": "",
                    "expected_guard_status": "PASS",
                    "expected_semantic_status": "PASS",
                    "expected_status": "",
                    "expected_code": "",
                    "oracle_id": f"oracle:worldguard:{owner_guard}:known-good",
                    "claim_boundary": boundary,
                },
                {
                    "case_id": f"case:matrix:{element_id}:bad:{selected.failure_id}",
                    "case_kind": "known_bad",
                    "text": selected.text or selected.blocked_claim,
                    "inputs": bad_inputs,
                    "coverage_context": dict(selected.coverage_context),
                    "pre_state": {},
                    "expected_output": {},
                    "post_state": {},
                    "effects": {},
                    "state_effect_disposition": "not_applicable",
                    "state_effect_reason": "This case proves the selected protected failure.",
                    "failure_id": selected.failure_id,
                    "blocked_claim": selected.blocked_claim,
                    "expected_guard_status": "",
                    "expected_semantic_status": "",
                    "expected_status": selected.expected_status,
                    "expected_code": selected.code,
                    "oracle_id": f"oracle:worldguard:{owner_guard}:{selected.layer}:{selected.code}",
                    "claim_boundary": boundary,
                },
            ],
        }
    native_identity = {
        key: value for key, value in identity.items() if key != "task_purpose"
    }
    return {
        **identity,
        "content_fingerprint": _independent_fingerprint(native_identity),
    }


def _element_and_binding(
    case: dict,
    *,
    matrix: dict,
) -> tuple[WorldElement, BlueprintBinding]:
    raw = case["raw_observation"]
    oracle = case["oracle"]
    semantic_payload = _semantic_payload(
        case,
        boundary=matrix["claim_boundary"],
    )
    element = WorldElement.from_dict(
        {
            "element_id": raw["element_id"],
            "kind": raw["element_kind"],
            "owner_node_id": "matrix_root",
            "dependencies": [],
            "input_ports": [],
            "output_ports": [],
            "internal_terminal_outputs": [],
            "native_semantic": semantic_payload,
            "contributes_to_claim": False,
            "required_binding_roles": [],
        }
    )
    binding = BlueprintBinding.from_dict(
        {
            "binding_id": semantic_payload["observation_binding_id"],
            "role": "native_result",
            "subject_element_id": raw["element_id"],
            "resource_id": semantic_payload["native_object_id"],
            "owner": oracle["owner_guard"],
            "locator": f"matrix/{raw['element_id']}.json",
            "provider_id": semantic_payload["provider_id"],
            "provider_version": semantic_payload["provider_version"],
            "provider_capability_id": "worldguard.native-result.v1",
            "observation_mode": "local_content",
            "target_id": matrix["target_id"],
            "target_revision": matrix["target_revision"],
            "freshness_status": "current",
            "content_fingerprint": semantic_payload["content_fingerprint"],
            "receipt_fingerprint": semantic_payload["content_fingerprint"],
            "claim_boundary": matrix["claim_boundary"],
        }
    )
    return element, binding


def _assert_output_subset(observed: dict, expected: dict) -> None:
    for key, value in expected.items():
        assert observed[key] == value


def test_seven_guard_matrix_uses_independent_domain_oracles() -> None:
    matrix = json.loads(MATRIX_FIXTURE.read_text(encoding="utf-8"))
    assert matrix["schema_version"] == "worldguard.seven_guard_native_owner_matrix.v3"
    assert len(matrix["cases"]) == 19

    accepted = [
        case
        for case in matrix["cases"]
        if "admission_error_code" not in case["oracle"]
    ]
    assert {case["oracle"]["owner_guard"] for case in accepted} == EXPECTED_OWNER_SET
    for owner in EXPECTED_OWNER_SET:
        owner_cases = [
            case
            for case in matrix["cases"]
            if case["oracle"].get("owner_guard") == owner
            or (
                owner == "ResourceGuard"
                and case["raw_observation"]["element_kind"] == "resource"
            )
        ]
        assert any(case["polarity"] == "positive" for case in owner_cases)
        assert any(
            case["polarity"] in {"negative", "admission_negative"}
            for case in owner_cases
        )

    base = load_world_blueprint(BLUEPRINT_FIXTURE)
    blueprint = replace(
        base,
        blueprint_id=matrix["blueprint_id"],
        target_id=matrix["target_id"],
        target_revision=matrix["target_revision"],
        declared_boundary=matrix["claim_boundary"],
    )

    for case in matrix["cases"]:
        oracle = case["oracle"]
        if "admission_error_code" in oracle:
            with pytest.raises(BlueprintError) as caught:
                _element_and_binding(case, matrix=matrix)
            assert caught.value.code == oracle["admission_error_code"]
            assert oracle["type_error"] in caught.value.details["type_errors"]
            continue

        element, binding = _element_and_binding(case, matrix=matrix)
        assert element.native_semantic is not None
        observed_payload = element.native_semantic.fingerprint_payload()

        # Expected owner inputs are literal domain oracles written from the raw
        # semantic contract, not generated by the production adapter.
        assert _blueprint_native_inputs(element.native_semantic) == oracle[
            "canonical_owner_inputs"
        ]

        first = _execute_blueprint_native_semantic(
            blueprint,
            element,
            binding,
            observed_payload,
        )
        second = _execute_blueprint_native_semantic(
            blueprint,
            element,
            binding,
            observed_payload,
        )
        assert first == second
        assert first["execution_disposition"] == "executed"
        assert first["owner_guard"] == oracle["owner_guard"]
        assert first["executor_id"] == (
            f"worldguard.semantic.{oracle['owner_guard'].removesuffix('Guard').lower()}.v1"
        )
        assert first["terminal_status"] == oracle["terminal_status"]
        assert first["structural_result"]["status"] == oracle["structural_status"]
        assert first["semantic_result"]["status"] == oracle["semantic_status"]
        assert [
            finding["code"]
            for finding in first["structural_result"].get("errors", [])
        ] == oracle["structural_error_codes"]
        assert [
            finding["code"]
            for finding in first["semantic_result"].get("findings", [])
        ] == oracle["semantic_finding_codes"]
        if "receipt_finding_codes" in oracle:
            assert [finding["code"] for finding in first["findings"]] == oracle[
                "receipt_finding_codes"
            ]
        _assert_output_subset(
            first["semantic_result"]["outputs"],
            oracle["output_subset"],
        )
        assert sorted(
            row["field_id"] for row in first.get("unverified_boundaries", [])
        ) == sorted(oracle["unverified_field_ids"])
        assert first.get("requested_claim_scope", "") == oracle.get(
            "requested_claim_scope", ""
        )
        assert first.get("evaluated_claim_scope", "") == oracle.get(
            "evaluated_claim_scope", ""
        )
        assert first.get("licensed_claim_scope", "") == oracle.get(
            "licensed_claim_scope", ""
        )
        assert first.get("qualified_subscope", "") == oracle.get(
            "qualified_subscope", ""
        )

        dispositions = first["field_dispositions"]
        assert len(dispositions) == len(element.native_semantic.semantic_fields)
        assert {row["field_id"] for row in dispositions} == set(
            element.native_semantic.semantic_fields
        )
        assert all(
            first[name].startswith("sha256:") and len(first[name]) == 71
            for name in (
                "request_fingerprint",
                "input_fingerprint",
                "result_fingerprint",
                "receipt_fingerprint",
            )
        )


def test_owner_inputs_do_not_invent_domain_facts() -> None:
    matrix = json.loads(MATRIX_FIXTURE.read_text(encoding="utf-8"))
    cases = {case["case_id"]: case for case in matrix["cases"]}

    agent = cases["agent-pass"]["oracle"]["canonical_owner_inputs"]
    record = agent["beliefs"]["planner_alex"]
    assert record == {
        "agent_id": "planner_alex",
        "beliefs": ["request_exists"],
        "desires": ["complete_plan"],
        "intentions": ["allocate_room"],
    }

    resource = cases["resource-pass"]["oracle"]["canonical_owner_inputs"]
    assert resource == {
        "resources": {
            "inventory": [
                {"resource_id": "room_a", "quantity": 1, "unit": "room"}
            ]
        }
    }

    causal = cases["causal-pass"]["oracle"]["canonical_owner_inputs"]
    assert "equations" not in causal["causal_model"]
    assert causal["causal_model"]["graph"] == [
        ["assignment_complete", "schedule_ready"]
    ]

    conflict = cases["conflict-pass"]["oracle"]["canonical_owner_inputs"]
    assert conflict["game_model"]["issue"] == "room allocation"
    assert conflict["game_model"]["actions"] == ["allocate", "wait"]

    norm = cases["norm-pass"]["oracle"]["canonical_owner_inputs"]
    assert norm["facts"] == [{"fact_id": "request_authorized", "value": True}]


def _mixed_event_rollout_outputs(
    *,
    event_id: str = "event:observed",
    state_id: str = "state:declared",
    transition_id: str = "transition:declared",
    source_state: str = "state:source",
    target_state: str = "state:target",
    initiates: str = "fluent:initiated",
    terminates: str = "fluent:terminated",
    releases: str = "fluent:released",
) -> dict:
    contract = GuardContract.from_dict(
        attach_task_purpose_declarations(
            {
                "contract_id": "event-identity-domain-regression",
                "run_id": "event-identity-domain-regression-run",
                "claim": {
                    "claim_id": "event-identity-domain-regression-claim",
                    "text": "Evaluate one bounded event rollout without crossing identity domains.",
                    "target_guards": ["EventGuard"],
                    "requested_semantics": ["event"],
                },
                "world_model": {
                    "model_id": "event-identity-domain-world",
                    "model_version": "revision-1",
                },
                "inputs": {
                    "events": [
                        {
                            "event_id": event_id,
                            "at": "t1",
                            "initiates": [initiates],
                            "terminates": [terminates],
                            "releases": [releases],
                        }
                    ],
                    "event_model": {
                        "initial_states": ["fluent:initial"],
                        "states": [
                            {"state_id": state_id, "initial": False, "terminal": False},
                            {"state_id": source_state, "initial": True, "terminal": False},
                            {"state_id": target_state, "initial": False, "terminal": True},
                        ],
                        "guard_values": {"guard:declared": True},
                        "transitions": [
                            {
                                "transition_id": transition_id,
                                "source_state": source_state,
                                "target_state": target_state,
                                "guard": "guard:declared",
                                "effect": "effect:declared",
                            }
                        ],
                    },
                },
            },
            guards=["EventGuard"],
        )
    )
    status, findings, _, outputs = EXECUTOR_REGISTRY["EventGuard"].execute(contract)
    assert status == SemanticStatus.PASS
    assert findings == []
    return outputs


def test_event_rollout_keeps_event_fluent_transition_and_state_identities_separate() -> None:
    outputs = _mixed_event_rollout_outputs()

    assert outputs["executed_event_ids"] == ["event:observed"]
    assert outputs["declared_initial_fluent_ids"] == ["fluent:initial"]
    assert outputs["initiated_fluent_ids"] == ["fluent:initiated"]
    assert outputs["terminated_fluent_ids"] == ["fluent:terminated"]
    assert outputs["released_fluent_ids"] == ["fluent:released"]
    assert outputs["reached_fluent_ids"] == ["fluent:initial", "fluent:initiated"]
    assert outputs["active_fluent_ids"] == ["fluent:initial", "fluent:initiated"]
    assert outputs["final_fluent_ids_by_scenario"] == {
        "default": ["fluent:initial", "fluent:initiated"]
    }
    assert outputs["declared_state_ids"] == [
        "state:declared",
        "state:source",
        "state:target",
    ]
    assert outputs["declared_transition_ids"] == ["transition:declared"]
    assert outputs["referenced_transition_state_ids"] == [
        "state:source",
        "state:target",
    ]
    assert outputs["reached_state_ids"] == ["state:source", "state:target"]
    assert outputs["executed_state_ids"] == ["state:source", "state:target"]
    assert outputs["executed_transition_ids"] == ["transition:declared"]

    identity_fields = (
        "executed_event_ids",
        "declared_state_ids",
        "declared_transition_ids",
        "referenced_transition_state_ids",
        "reached_state_ids",
        "executed_state_ids",
        "executed_transition_ids",
    )
    baseline_domains = {field: outputs[field] for field in identity_fields}

    event_mutation = _mixed_event_rollout_outputs(event_id="event:mutated")
    assert event_mutation["executed_event_ids"] == ["event:mutated"]
    assert {
        field: event_mutation[field]
        for field in identity_fields
        if field != "executed_event_ids"
    } == {
        field: baseline_domains[field]
        for field in identity_fields
        if field != "executed_event_ids"
    }

    state_mutation = _mixed_event_rollout_outputs(state_id="state:mutated")
    assert state_mutation["declared_state_ids"] == [
        "state:mutated",
        "state:source",
        "state:target",
    ]
    assert {
        field: state_mutation[field]
        for field in identity_fields
        if field != "declared_state_ids"
    } == {
        field: baseline_domains[field]
        for field in identity_fields
        if field != "declared_state_ids"
    }

    transition_mutation = _mixed_event_rollout_outputs(
        transition_id="transition:mutated"
    )
    assert transition_mutation["declared_transition_ids"] == [
        "transition:mutated"
    ]
    assert {
        field: transition_mutation[field]
        for field in identity_fields
        if field not in {"declared_transition_ids", "executed_transition_ids"}
    } == {
        field: baseline_domains[field]
        for field in identity_fields
        if field not in {"declared_transition_ids", "executed_transition_ids"}
    }
    assert transition_mutation["executed_transition_ids"] == [
        "transition:mutated"
    ]

    reference_mutation = _mixed_event_rollout_outputs(
        source_state="state:source-mutated"
    )
    assert reference_mutation["referenced_transition_state_ids"] == [
        "state:source-mutated",
        "state:target",
    ]
    assert {
        field: reference_mutation[field]
        for field in identity_fields
        if field not in {"declared_state_ids", "referenced_transition_state_ids", "reached_state_ids", "executed_state_ids"}
    } == {
        field: baseline_domains[field]
        for field in identity_fields
        if field not in {"declared_state_ids", "referenced_transition_state_ids", "reached_state_ids", "executed_state_ids"}
    }
    assert reference_mutation["reached_state_ids"] == [
        "state:source-mutated",
        "state:target",
    ]

    for fluent_field, output_field in (
        ("initiates", "initiated_fluent_ids"),
        ("terminates", "terminated_fluent_ids"),
        ("releases", "released_fluent_ids"),
    ):
        mutation = _mixed_event_rollout_outputs(
            **{fluent_field: f"fluent:{fluent_field}-mutated"}
        )
        assert mutation[output_field] == [f"fluent:{fluent_field}-mutated"]
        assert {field: mutation[field] for field in identity_fields} == baseline_domains


def _mutated_value(kind: str, field_id: str, value):
    if kind == "relation" and field_id == "relation":
        return "EC"
    if field_id == "mechanism_claim_scope":
        return "mechanism_truth" if value == "graph_only" else "graph_only"
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value + 1
    if isinstance(value, str):
        return value + "_mutated"
    if isinstance(value, list):
        mutated = deepcopy(value)
        if not mutated:
            return ["declared_conflict"]
        first = mutated[0]
        if isinstance(first, str):
            mutated[0] = first + "_mutated"
        elif isinstance(first, dict):
            first = dict(first)
            if "value" in first:
                first["value"] = (
                    not first["value"]
                    if isinstance(first["value"], bool)
                    else first["value"] + 1
                )
            elif "from" in first:
                first["from"] = str(first["from"]) + "_mutated"
            mutated[0] = first
        return mutated
    raise AssertionError(f"No mutation rule for {kind}.{field_id}")


def test_every_native_field_has_one_disposition_and_mutation_path() -> None:
    assert set(NATIVE_SEMANTIC_FIELD_DISPOSITIONS) == set(NATIVE_SEMANTIC_FIELDS)
    for kind, fields in NATIVE_SEMANTIC_FIELDS.items():
        assert set(NATIVE_SEMANTIC_FIELD_DISPOSITIONS[kind]) == set(fields)

    matrix = json.loads(MATRIX_FIXTURE.read_text(encoding="utf-8"))
    representatives = {}
    for case in matrix["cases"]:
        if "admission_error_code" not in case["oracle"]:
            representatives.setdefault(case["raw_observation"]["element_kind"], case)

    base = load_world_blueprint(BLUEPRINT_FIXTURE)
    for kind in ("entity", "property"):
        element = next(row for row in base.elements if row.kind == kind)
        assert element.native_semantic is not None
        representatives[kind] = {
            "raw_observation": {
                "element_id": element.element_id,
                "element_kind": kind,
                "semantic_fields": element.native_semantic.semantic_fields,
            }
        }

    assert set(representatives) == set(NATIVE_SEMANTIC_FIELDS)
    boundary = matrix["claim_boundary"]
    for kind, case in representatives.items():
        raw = case["raw_observation"]
        original_payload = _semantic_payload(case, boundary=boundary)
        original = NativeSemanticRef.from_dict(
            original_payload,
            element_id=raw["element_id"],
            expected_kind=kind,
        )
        original_rows = {
            row["field_id"]: row
            for row in _blueprint_native_field_dispositions(original)
        }
        assert set(original_rows) == set(NATIVE_SEMANTIC_FIELDS[kind])

        for field_id, value in raw["semantic_fields"].items():
            mutated_case = deepcopy(case)
            mutated_case["raw_observation"]["semantic_fields"][field_id] = (
                _mutated_value(kind, field_id, value)
            )
            mutated_payload = _semantic_payload(mutated_case, boundary=boundary)
            mutated = NativeSemanticRef.from_dict(
                mutated_payload,
                element_id=raw["element_id"],
                expected_kind=kind,
            )
            mutated_rows = {
                row["field_id"]: row
                for row in _blueprint_native_field_dispositions(mutated)
            }
            disposition = original_rows[field_id]["disposition"]
            if disposition in {
                "owner_input",
                "owner_input_with_unverified_semantics",
            }:
                assert _blueprint_native_inputs(original) != _blueprint_native_inputs(
                    mutated
                )
            else:
                assert original_rows[field_id]["declared_value"] != mutated_rows[
                    field_id
                ]["declared_value"]


def test_causal_claim_scopes_are_requested_evaluated_and_licensed_honestly() -> None:
    matrix = json.loads(MATRIX_FIXTURE.read_text(encoding="utf-8"))
    cases = {case["case_id"]: case for case in matrix["cases"]}

    graph_only = cases["causal-pass"]["oracle"]
    assert graph_only["requested_claim_scope"] == "graph_only"
    assert graph_only["evaluated_claim_scope"] == "graph_only"
    assert graph_only["licensed_claim_scope"] == "graph_only"

    self_cycle = cases["causal-self-cycle-fail"]["oracle"]
    assert self_cycle["structural_error_codes"] == ["CAUSAL_CYCLE"]
    assert self_cycle["terminal_status"] == "FAIL"
    assert "licensed_claim_scope" not in self_cycle

    mechanism_truth = cases["causal-mechanism-truth-gap"]["oracle"]
    assert mechanism_truth["terminal_status"] == "GAP"
    assert mechanism_truth["requested_claim_scope"] == "mechanism_truth"
    assert mechanism_truth["evaluated_claim_scope"] == "graph_only"
    assert mechanism_truth["qualified_subscope"] == "graph_only"
    assert "licensed_claim_scope" not in mechanism_truth


def test_source_and_bundled_runtime_have_all_file_parity_and_isolated_import(
    tmp_path: Path,
) -> None:
    projection_report = audit_projection(ROOT)
    assert projection_report["ok"], projection_report["failures"]
    assert projection_report["action"] == "check"
    assert projection_report["transaction_state"] == "read_only"
    assert projection_report["write_performed"] is False
    assert projection_report["authority"]["direction"] == (
        "author_source_to_derived_projection_only"
    )

    bundled_root = ROOT / "skills/worldguard/runtime/worldguard"

    script = f"""
import json
import pathlib
import sys
sys.path.insert(0, {str(bundled_root.parent)!r})
import worldguard
from worldguard.blueprint import NATIVE_SEMANTIC_FIELDS, NATIVE_SEMANTIC_FIELD_DISPOSITIONS
print(json.dumps({{
    "module_path": str(pathlib.Path(worldguard.__file__).resolve()),
    "field_kinds": sorted(NATIVE_SEMANTIC_FIELDS),
    "disposition_kinds": sorted(NATIVE_SEMANTIC_FIELD_DISPOSITIONS),
}}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    assert Path(observed["module_path"]).is_relative_to(bundled_root)
    assert observed["field_kinds"] == sorted(NATIVE_SEMANTIC_FIELDS)
    assert observed["disposition_kinds"] == sorted(
        NATIVE_SEMANTIC_FIELD_DISPOSITIONS
    )
