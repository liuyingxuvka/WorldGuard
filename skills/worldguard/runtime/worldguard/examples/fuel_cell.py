from __future__ import annotations
import argparse
from importlib.resources import files
from typing import Any
import yaml
from worldguard.contracts import GuardContract
from worldguard.guard_model_contract import PROTECTED_FAILURE_CLASSES
from worldguard.io import dump_json
from worldguard.kernel import run_worldguard
REQUIRED_GUARDS = ['EventGuard', 'AgentGuard', 'SpaceGuard', 'ResourceGuard', 'CausalGuard', 'ConflictGuard', 'NormGuard']
BOUNDARY_STRINGS = ['no real fuel-cell thermodynamics', 'no legal compliance finding', 'no safety certification', 'no deployment readiness claim', 'no market truth or strategy proof']

def _load_yaml(name: str) -> dict[str, Any]:
    path = files('worldguard.examples').joinpath('fuel_cell', name)
    with path.open('r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)

def build_contracts() -> list[GuardContract]:
    story = _load_yaml('input_story_fragment.yaml')['input_story_fragment']
    world = _load_yaml('world_model.yaml')['world_model']
    state = world['initial_world_state']
    scope_limits = story['scope_limits']
    contracts = []
    inputs = {'events': world['events'], 'beliefs': state['agents'], 'spatial_relations': state['rcc8_relations'], 'resources': state['resources'], 'causal_model': {'variables': state['causal_variables'], 'equations': state['causal_equations'], 'scenarios': {'demo_day': {}}}, 'game_model': {'payoffs': state['conflict_payoffs']}, 'norms': state['norms'], 'facts': [{'fact_id': 'c_precheck_complete', 'value': True}, {'fact_id': 'nda_active', 'value': True}]}
    model = {'model_id': world['model_id'], 'model_version': world['model_version'], 'scope_limits': scope_limits}
    for claim in story['claims']:
        task_contract_id = f"fuel-cell:{claim['claim_id']}"
        claim_inputs = {**inputs, 'norms': [*inputs['norms'], *claim.get('claimed_norms', [])]}
        contracts.append(GuardContract.from_dict({'contract_id': task_contract_id, 'schema_version': 'worldguard.contract.v1', 'run_id': 'fuel-cell-toy', 'claim': {'claim_id': claim['claim_id'], 'text': claim['text'], 'target_guards': claim['target_guards'], 'requested_semantics': claim['requested_semantics']}, 'world_model': model, 'inputs': claim_inputs, 'dependencies': {'upstream_results': [], 'read_only': True}, 'output_requirements': {'require_ledgers': True, 'require_counterexample_for_non_pass': True, 'allowed_status': ['PASS', 'FAIL', 'GAP', 'BOUNDARY_EXCEEDED']}}))
    return contracts

def run_check() -> dict[str, Any]:
    story = _load_yaml('input_story_fragment.yaml')['input_story_fragment']
    expected = _load_yaml('expected_guard_report.yaml')['expected_guard_report']
    ledger_outputs = _load_yaml('ledger_outputs.yaml')['ledger_outputs']
    reports = [run_worldguard(contract) for contract in build_contracts()]
    guards_seen = sorted({result.guard for report in reports for result in report.child_results})
    statuses = [report.status.value for report in reports]
    scope_notes = [*story['scope_limits'], *ledger_outputs['artifact_scope_note']['no_real_world_claims']]
    toy_boundaries_ok = all((any((boundary in item for item in scope_notes)) or boundary in str(scope_notes) for boundary in BOUNDARY_STRINGS))
    mismatches = [{'claim_id': claim['claim_id'], 'expected': claim.get('expected_status'), 'actual': status} for claim, status in zip(story['claims'], statuses) if claim.get('expected_status') != status]
    ok = set(guards_seen) == set(REQUIRED_GUARDS) and expected.get('aggregate_status') == 'FAIL' and ('FAIL' in statuses) and toy_boundaries_ok and not mismatches
    return {'ok': ok, 'example': 'fuel_cell', 'guards_verified': guards_seen, 'claim_statuses': statuses, 'mismatches': mismatches, 'expected_aggregate_status': expected.get('aggregate_status'), 'toy_boundaries_verified': BOUNDARY_STRINGS, 'reports': [report.to_dict() for report in reports]}

def main(argv: list[str] | None=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    if not args.check:
        parser.error('fuel_cell example requires --check')
    result = run_check()
    print(dump_json(result))
    return 0 if result['ok'] else 1
if __name__ == '__main__':
    raise SystemExit(main())
