from __future__ import annotations
from worldguard.contracts import GuardContract
from worldguard.guard_model_contract import PROTECTED_FAILURE_CLASSES
GUARD_SEMANTICS = {'EventGuard': 'event', 'AgentGuard': 'agent', 'SpaceGuard': 'spatial', 'ResourceGuard': 'resource', 'CausalGuard': 'causal', 'ConflictGuard': 'conflict', 'NormGuard': 'norm'}

def make_contract(guard: str, *, text: str='claim', requested_semantics: list[str] | None=None, inputs: dict | None=None, world_model: dict | None=None, asserts: list[dict] | None=None) -> GuardContract:
    task_contract_id = f'test:{guard}'
    run_id = 'test-run'
    resolved_world_model = world_model or {'model_id': 'model-001', 'model_version': 'test'}
    return GuardContract.from_dict({'contract_id': task_contract_id, 'schema_version': 'worldguard.contract.v1', 'run_id': run_id, 'claim': {'claim_id': 'claim-001', 'text': text, 'target_guards': [guard], 'requested_semantics': requested_semantics if requested_semantics is not None else [GUARD_SEMANTICS[guard]], 'asserts': asserts or []}, 'world_model': resolved_world_model, 'inputs': inputs or {}, 'dependencies': {'upstream_results': [], 'read_only': True}, 'output_requirements': {'require_ledgers': True, 'require_counterexample_for_non_pass': True, 'allowed_status': ['PASS', 'FAIL', 'GAP', 'BOUNDARY_EXCEEDED']}})
