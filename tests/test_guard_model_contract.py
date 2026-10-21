from __future__ import annotations
from collections import Counter
from dataclasses import replace
from pathlib import Path
import pytest
from worldguard.contracts import GuardContract
import worldguard.guard_model_contract as purpose_authority
from worldguard.guard_model_contract import GUARD_MODEL_PURPOSES, MESH_RUNTIME_FAILURES, NATIVE_GOOD_CASES, PROTECTED_FAILURE_CLASSES, discover_guard_owned_failure_codes, guard_family_purpose_contract_fingerprint, run_guard_model_contract
from worldguard.guards import GUARD_RUNNERS
from worldguard.kernel import run_worldguard
from worldguard.semantic import execute_semantic
from worldguard.status import GuardStatus
ROOT = Path(__file__).resolve().parents[1]


def test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure():
    report = run_guard_model_contract()
    assert report['ok'] is True
    assert report['purpose_count'] == 7
    assert Counter((case.guard for case in NATIVE_GOOD_CASES)) == Counter({purpose.guard: 1 for purpose in GUARD_MODEL_PURPOSES})
    discovered = discover_guard_owned_failure_codes()
    expected = {(guard, layer, code) for (guard, layer), codes in discovered.items() for code in codes}
    declared = [(case.guard, case.layer, case.code) for case in PROTECTED_FAILURE_CLASSES]
    assert len(declared) == len(set(declared)) == len(expected)
    assert set(declared) == expected
    assert report['protected_failure_count'] == report['known_bad_count'] == len(expected)
    assert report['executed_case_count'] == len(expected) + len(NATIVE_GOOD_CASES)
    assert {item['family_contract_fingerprint'] for item in report['observations']} == {guard_family_purpose_contract_fingerprint()}
    bad_observations = [item for item in report['observations'] if 'failure_id' in item]
    assert len(bad_observations) == len(expected)
    assert all((item['observed_status'] == item['expected_status'] for item in bad_observations))
    assert all((item['observed_codes'] == [item['expected_code']] for item in bad_observations))

def test_mesh_runtime_failures_are_explicitly_outside_individual_guard_universe():
    protected_codes = {case.code for case in PROTECTED_FAILURE_CLASSES}
    assert set(MESH_RUNTIME_FAILURES) == {'SEM_EXECUTOR_UNREGISTERED', 'SEM_PROVIDER_UNAVAILABLE'}
    assert protected_codes.isdisjoint(MESH_RUNTIME_FAILURES)

def test_causal_guard_rejects_partially_defined_structural_equations():
    task_contract_id = 'partial-causal-equations'
    run_id = 'partial-causal-equations'
    model_instance_id = 'partial-scm'
    contract = GuardContract.from_dict({'contract_id': task_contract_id, 'run_id': run_id, 'claim': {'claim_id': 'partial-causal-equations', 'text': 'the declared SCM is complete', 'target_guards': ['CausalGuard'], 'requested_semantics': ['causal']}, 'world_model': {'model_id': model_instance_id, 'model_version': 'v1'}, 'inputs': {'causal_model': {'variables': ['x', 'y'], 'equations': {'x': 1}, 'graph': []}}})
    result = GUARD_RUNNERS['CausalGuard'](contract.for_guard('CausalGuard'))
    assert result.status is GuardStatus.GAP
    assert [item['code'] for item in result.errors] == ['CAUSAL_MISSING_STRUCTURAL_EQUATION']
    assert result.missing_slots == [{'variable': 'y', 'needed': 'structural_equation'}]


def test_bundled_guard_model_contract_matches_the_canonical_runtime():
    source = ROOT / 'worldguard' / 'guard_model_contract.py'
    bundled = ROOT / 'skills' / 'worldguard' / 'runtime' / 'worldguard' / 'guard_model_contract.py'
    assert bundled.read_bytes() == source.read_bytes()
