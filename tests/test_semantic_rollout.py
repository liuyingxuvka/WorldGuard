from __future__ import annotations
import pytest
from worldguard import run_model_mesh
from worldguard.semantic import event_replay
from worldguard.cli import main as worldguard_main
from worldguard.status import GuardStatus

def _mesh(guard: str, inputs: dict, *, text: str='bounded semantic claim', asserts: list | None=None) -> dict:
    semantic = {'EventGuard': 'event', 'AgentGuard': 'agent', 'SpaceGuard': 'space', 'ResourceGuard': 'resource', 'CausalGuard': 'causal', 'ConflictGuard': 'conflict', 'NormGuard': 'norm'}[guard]
    mesh = {'mesh_id': f'mesh-{semantic}', 'nodes': [{'model_id': f'{semantic}-node', 'contract': {'contract_id': f'contract-{semantic}', 'claim': {'claim_id': f'claim-{semantic}', 'text': text, 'requested_semantics': [semantic], 'asserts': asserts or []}, 'world_model': {'model_id': f'model-{semantic}', 'model_version': 'v1'}, 'inputs': inputs}}]}
    mesh['nodes'][0]['contract']
    return mesh
NEGATIVE_PROBES = [('EventGuard', {'events': [{'event_id': 'e1', 'at': 't0'}]}, 'EVENT_MISSING_INITIATION_AXIOM'), ('AgentGuard', {'beliefs': {'a1': {'agent_id': 'a1', 'beliefs': ['ready']}}, 'agent_model': {}}, 'AGENT_INCOMPLETE_BDI'), ('SpaceGuard', {'spatial_relations': [{'x': 'a', 'y': 'b', 'at': 't0', 'relation': 'NTPP'}, {'x': 'b', 'y': 'c', 'at': 't0', 'relation': 'NTPP'}, {'x': 'a', 'y': 'c', 'at': 't0', 'relation': 'DC'}]}, 'SPACE_RCC8_CONTRADICTION'), ('ResourceGuard', {'resources': {'places': {'tank': [{'color': 'fuel', 'qty': 1}]}, 'transitions': [{'id': 'use-1', 'consumes': [{'place': 'tank', 'color': 'fuel', 'qty': 1}]}, {'id': 'use-2', 'consumes': [{'place': 'tank', 'color': 'fuel', 'qty': 1}]}]}}, 'RESOURCE_CUMULATIVE_OVERCONSUMPTION'), ('CausalGuard', {'causal_model': {'variables': ['x', 'y'], 'equations': {'x': 1, 'y': 'external_solver(x)'}, 'graph': [['x', 'y']]}}, 'CAUSAL_UNEVALUABLE_EQUATION'), ('ConflictGuard', {'game_model': {'payoffs': [{'player': 'p1', 'value': 1}]}}, 'CONFLICT_INCOMPLETE_GAME'), ('NormGuard', {'norms': [{'modality': 'permitted', 'action': 'start'}]}, 'NORM_MISSING_CONDITION_FACT')]

def test_known_shallow_semantic_probe_cannot_project_pass():
    """Keep the finite negative-probe matrix statically enumerable."""
    for guard, inputs, expected_code in NEGATIVE_PROBES:
        report = run_model_mesh(_mesh(guard, inputs))
        assert report.status != GuardStatus.PASS
        assert expected_code in {finding['code'] for node in report.node_reports.values() for checked in node.guard_results for finding in checked.errors}

def _valid_event_mesh() -> dict:
    return _mesh('EventGuard', {'events': [{'event_id': 'e1', 'at': 't0', 'initiates': 'ready'}]}, asserts=[{'holds': 'ready', 'at': 't0'}])

def test_valid_bounded_semantic_rollout_reports_distinct_green_components():
    report = run_model_mesh(_valid_event_mesh())
    assert report.status == GuardStatus.PASS
    assert report.to_dict()['checked'] == {'nodes': 1, 'edges': 0, 'roots': 1, 'variants': 0, 'node_variants': 0}
    assert report.to_dict()['gaps'] == []

def test_retired_closure_profile_is_rejected_instead_of_skipping_semantics():
    mesh = _valid_event_mesh()
    mesh['closure_profile'] = 'structural_only'
    with pytest.raises(ValueError, match='closure_profile is retired'):
        run_model_mesh(mesh)

@pytest.mark.parametrize('retired_value', ['semantic_rollout', 'structural_only'])
def test_retired_closure_profile_cli_selector_is_rejected(retired_value: str):
    with pytest.raises(SystemExit) as error:
        worldguard_main(['mesh-check', '--mesh', 'unused.yaml', '--closure-profile', retired_value])
    assert error.value.code == 2

def test_provider_unavailable_is_visible_and_fail_closed():
    mesh = _valid_event_mesh()
    mesh['provider_availability'] = {'EventGuard': False}
    with pytest.raises(ValueError, match='provider_availability is retired'):
        run_model_mesh(mesh)

def test_scoped_events_execute_from_their_native_scenario_ids():
    mesh = _mesh('EventGuard', {'events': [{'event_id': 'shared', 'at': 't0', 'initiates': 'ready'}, {'event_id': 'left', 'at': 't1', 'scenario_id': 'left-scenario', 'initiates': 'left-done'}, {'event_id': 'right', 'at': 't1', 'scenario_id': 'right-scenario', 'initiates': 'right-done'}]}, asserts=[{'holds': 'ready', 'at': 't0'}])
    report = run_model_mesh(mesh)
    assert report.status == GuardStatus.PASS
    events = mesh['nodes'][0]['contract']['inputs']['events']
    left = list(event_replay(events, scenario_id='left-scenario'))
    right = list(event_replay(events, scenario_id='right-scenario'))
    assert [row[0]['event_id'] for row in left] == ['shared', 'left']
    assert [row[0]['event_id'] for row in right] == ['shared', 'right']
    assert left[-1][2] == frozenset({'ready', 'left-done'})
    assert right[-1][2] == frozenset({'ready', 'right-done'})

@pytest.mark.parametrize('missing_scope,expected', [('s_missing', GuardStatus.FAIL), (None, GuardStatus.GAP)])
def test_missing_event_time_does_not_hide_independent_scenario_failures(missing_scope, expected):
    from worldguard import run_worldguard
    missing = {'event_id': 'missing', 'initiates': 'irrelevant'}
    if missing_scope:
        missing['scenario_id'] = missing_scope
    report = run_worldguard({'claim': {'claim_id': 'partial-event-times', 'requested_semantics': ['event'], 'asserts': [{'holds': 'done', 'at': 't1', 'scenario': 's_bad'}]}, 'inputs': {'events': [missing, {'event_id': 'broken', 'scenario_id': 's_bad', 'at': 't1', 'initiates': 'done', 'requires': 'never'}]}})
    assert report.status == expected
    errors = [error['code'] for result in report.guard_results for error in result.errors]
    assert ('EVENT_PRECONDITION_UNMET' in errors) is (missing_scope is not None)
    if missing_scope:
        # The broken event cannot establish done in the otherwise ordered scenario.
        assert report.claim_binding['status'] == 'FAIL'
