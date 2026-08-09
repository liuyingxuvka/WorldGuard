from __future__ import annotations

import importlib.util
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from worldguard.contracts import GuardContract
import worldguard.guard_model_contract as purpose_authority
from worldguard.guard_model_contract import (
    GuardCandidatePurposeError,
    GUARD_MODEL_PURPOSES,
    MESH_RUNTIME_FAILURES,
    NATIVE_GOOD_CASES,
    PROTECTED_FAILURE_CLASSES,
    build_calibration_task_purpose_declaration,
    discover_guard_owned_failure_codes,
    guard_family_purpose_contract_fingerprint,
    run_guard_model_contract,
    verify_guard_candidate_purpose_contract,
)
from worldguard.guards import GUARD_RUNNERS
from worldguard.kernel import run_worldguard
from worldguard.semantic import execute_semantic
from worldguard.status import GuardStatus


ROOT = Path(__file__).resolve().parents[1]


def _load_contract_exhaustion_module():
    path = ROOT / ".flowguard" / "guard_model_contract_exhaustion.py"
    spec = importlib.util.spec_from_file_location("guard_model_contract_exhaustion_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_candidate_order_module():
    path = ROOT / ".flowguard" / "guard_candidate_purpose_order.py"
    spec = importlib.util.spec_from_file_location("guard_candidate_purpose_order_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure():
    report = run_guard_model_contract()

    assert report["ok"] is True
    assert report["purpose_count"] == 7
    assert Counter(case.guard for case in NATIVE_GOOD_CASES) == Counter(
        {purpose.guard: 1 for purpose in GUARD_MODEL_PURPOSES}
    )

    discovered = discover_guard_owned_failure_codes()
    expected = {
        (guard, layer, code)
        for (guard, layer), codes in discovered.items()
        for code in codes
    }
    declared = [(case.guard, case.layer, case.code) for case in PROTECTED_FAILURE_CLASSES]
    assert len(declared) == len(set(declared)) == len(expected) == 81
    assert set(declared) == expected
    assert report["protected_failure_count"] == report["known_bad_count"] == 81
    assert report["candidate_binding_count"] == 88
    assert {
        item["family_contract_fingerprint"] for item in report["observations"]
    } == {guard_family_purpose_contract_fingerprint()}

    bad_observations = [item for item in report["observations"] if "failure_id" in item]
    assert len(bad_observations) == 81
    assert all(item["observed_status"] == item["expected_status"] for item in bad_observations)
    assert all(item["observed_codes"] == [item["expected_code"]] for item in bad_observations)


def test_mesh_runtime_failures_are_explicitly_outside_individual_guard_universe():
    protected_codes = {case.code for case in PROTECTED_FAILURE_CLASSES}
    assert set(MESH_RUNTIME_FAILURES) == {
        "SEM_EXECUTOR_UNREGISTERED",
        "SEM_PROVIDER_UNAVAILABLE",
    }
    assert protected_codes.isdisjoint(MESH_RUNTIME_FAILURES)


def test_causal_guard_rejects_partially_defined_structural_equations():
    task_contract_id = "partial-causal-equations"
    run_id = "partial-causal-equations"
    model_instance_id = "partial-scm"
    contract = GuardContract.from_dict(
        {
            "contract_id": task_contract_id,
            "run_id": run_id,
                "claim": {
                    "claim_id": "partial-causal-equations",
                    "text": "the declared SCM is complete",
                    "target_guards": ["CausalGuard"],
                    "requested_semantics": ["causal"],
                },
            "world_model": {"model_id": model_instance_id, "model_version": "v1"},
            "inputs": {
                "causal_model": {
                    "variables": ["x", "y"],
                    "equations": {"x": 1},
                    "graph": [],
                }
            },
            "guard_purpose_declarations": [
                build_calibration_task_purpose_declaration(
                    "CausalGuard",
                    task_contract_id=task_contract_id,
                    run_id=run_id,
                    model_instance_id=model_instance_id,
                    selected_failure_ids=[
                        "failure:causal:guard:causal-missing-structural-equation"
                    ],
                    purpose="Prevent this task model from treating a partially defined SCM as complete.",
                    boundary="This declaration does not establish causal identification or factual truth.",
                )
            ],
        }
    )

    result = GUARD_RUNNERS["CausalGuard"](contract.for_guard("CausalGuard"))

    assert result.status is GuardStatus.GAP
    assert [item["code"] for item in result.errors] == ["CAUSAL_MISSING_STRUCTURAL_EQUATION"]
    assert result.missing_slots == [{"variable": "y", "needed": "structural_equation"}]


def test_guard_model_contract_exhaustion_is_exact_and_oracle_bound():
    module = _load_contract_exhaustion_module()
    report = module.review_guard_model_contract_exhaustion()

    expected_ids = {case.failure_id for case in PROTECTED_FAILURE_CLASSES}
    generated_ids = {case.case_id for case in report.generated_cases}
    assert report.ok is True
    assert report.decision == "contract_exhaustion_ready"
    assert report.confidence == "full"
    assert len(report.generated_cases) == len(expected_ids) == 81
    assert generated_ids == expected_ids
    assert not report.findings


def test_guard_candidate_purpose_order_model_covers_all_rejections():
    module = _load_candidate_order_module()
    report = module.review_guard_candidate_purpose_order()

    assert report.ok is True
    assert "invariant_violations: 0" in report.format_text()
    assert "reachability_failures: 0" in report.format_text()


def test_bundled_guard_model_contract_matches_the_canonical_runtime():
    source = ROOT / "worldguard" / "guard_model_contract.py"
    bundled = ROOT / "skills" / "worldguard" / "runtime" / "worldguard" / "guard_model_contract.py"
    assert bundled.read_bytes() == source.read_bytes()


def _event_contract() -> GuardContract:
    task_contract_id = "real-event-candidate"
    run_id = "real-event-candidate"
    model_instance_id = "event-model"
    return GuardContract.from_dict(
        {
            "contract_id": task_contract_id,
            "run_id": run_id,
            "claim": {
                "claim_id": "real-event-candidate",
                "text": "a declared event initiates readiness",
                "target_guards": ["EventGuard"],
                "requested_semantics": ["event"],
            },
            "world_model": {"model_id": model_instance_id, "model_version": "v1"},
            "inputs": {"events": [{"event_id": "e1", "at": "t0", "initiates": "ready"}]},
            "guard_purpose_declarations": [
                build_calibration_task_purpose_declaration(
                    "EventGuard",
                    task_contract_id=task_contract_id,
                    run_id=run_id,
                    model_instance_id=model_instance_id,
                    selected_failure_ids=[
                        "failure:event:guard:event-contradictory-fluents",
                        "failure:event:semantic:sem-event-missing-axiom",
                    ],
                    purpose="Prevent this event model from accepting contradictory fluents or axiom-free events.",
                    boundary="This task declaration does not cover continuous physical dynamics.",
                )
            ],
        }
    )


def test_formal_guard_candidate_freezes_current_task_purpose_before_construction():
    candidate = _event_contract().for_guard("EventGuard")
    binding = verify_guard_candidate_purpose_contract(candidate, "EventGuard")

    assert binding.family_contract_fingerprint == guard_family_purpose_contract_fingerprint()
    assert binding.frozen_for_candidate_id == candidate.contract_id
    assert binding.purpose_frozen_sequence < binding.candidate_constructed_sequence
    assert set(binding.family_guard_ids) == {purpose.guard for purpose in GUARD_MODEL_PURPOSES}
    assert set(binding.protected_failure_ids) == {
        "failure:event:guard:event-contradictory-fluents",
        "failure:event:semantic:sem-event-missing-axiom",
    }
    assert binding.purpose.startswith("Prevent this event model")
    assert binding.proof_receipt["status"] == "pass"
    assert binding.proof_receipt["known_good_count"] == 1
    assert binding.proof_receipt["known_bad_count"] == 2
    assert len(binding.declaration_fingerprint) == 64
    assert len(binding.proof_receipt_fingerprint) == 64
    assert GuardContract.from_dict(candidate.to_dict()).guard_purpose_contract == binding


@pytest.mark.parametrize(
    ("expected_code", "mutate"),
    [
        ("GUARD_CANDIDATE_PURPOSE_MISSING", lambda binding: None),
        (
            "GUARD_CANDIDATE_PURPOSE_STALE",
            lambda binding: replace(binding, family_contract_fingerprint="0" * 64),
        ),
        (
            "GUARD_CANDIDATE_PURPOSE_ORDER_INVALID",
            lambda binding: replace(binding, purpose_frozen_sequence=2),
        ),
        (
            "GUARD_CANDIDATE_PURPOSE_STALE",
            lambda binding: replace(
                binding,
                protected_failure_ids=binding.protected_failure_ids[:-1],
            ),
        ),
    ],
)
def test_real_kernel_rejects_invalid_candidate_purpose_before_guard_proof(
    monkeypatch,
    expected_code,
    mutate,
):
    original = purpose_authority.freeze_guard_purpose_contract

    def tampered_freeze(guard, **kwargs):
        return mutate(original(guard, **kwargs))

    monkeypatch.setattr(purpose_authority, "freeze_guard_purpose_contract", tampered_freeze)
    with pytest.raises(GuardCandidatePurposeError) as captured:
        run_worldguard(_event_contract())

    assert captured.value.code == expected_code


def test_missing_task_purpose_never_falls_back_to_family_catalog():
    data = _event_contract().to_dict()
    data["guard_purpose_declarations"] = []
    with pytest.raises(GuardCandidatePurposeError) as captured:
        GuardContract.from_dict(data).for_guard("EventGuard")
    assert captured.value.code == "GUARD_TASK_PURPOSE_DECLARATION_MISSING_OR_DUPLICATE"


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        (
            lambda declaration: declaration.update(selected_failure_ids=[]),
            "GUARD_TASK_PURPOSE_FAILURE_UNIVERSE_EMPTY_OR_DUPLICATE",
        ),
        (
            lambda declaration: declaration.update(selected_failure_ids=["failure:event:unknown"]),
            "GUARD_TASK_PURPOSE_NATIVE_ORACLE_UNKNOWN",
        ),
        (
            lambda declaration: declaration["known_bad_cases"].pop(),
            "GUARD_TASK_PURPOSE_BAD_PROOF_CARDINALITY_INVALID",
        ),
    ],
)
def test_task_purpose_rejects_empty_unknown_or_incomplete_failure_proof(
    mutation,
    expected_code,
):
    data = _event_contract().to_dict()
    declaration = data["guard_purpose_declarations"][0]
    mutation(declaration)
    with pytest.raises(GuardCandidatePurposeError) as captured:
        GuardContract.from_dict(data).for_guard("EventGuard")
    assert captured.value.code == expected_code


def test_real_semantic_verifier_rejects_stale_candidate_before_executor_runs():
    candidate = _event_contract().for_guard("EventGuard")
    assert candidate.guard_purpose_contract is not None
    stale = replace(
        candidate,
        guard_purpose_contract=replace(
            candidate.guard_purpose_contract,
            guard_contract_fingerprint="f" * 64,
        ),
    )

    with pytest.raises(GuardCandidatePurposeError) as captured:
        execute_semantic(
            node_id="node:event",
            guard="EventGuard",
            contract=stale,
            provider_available=True,
        )

    assert captured.value.code == "GUARD_CANDIDATE_PURPOSE_STALE"
