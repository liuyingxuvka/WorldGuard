from __future__ import annotations
from copy import deepcopy
import pytest
from worldguard import GuardedReport, ModelMeshContract, QualificationContext, qualification_context_for_node, run_model_mesh, run_worldguard
from worldguard.status import GuardStatus

def _event_contract() -> dict:
    contract = {'contract_id': 'qualification:event', 'claim': {'claim_id': 'claim:event', 'text': 'the declared event makes the plan ready', 'requested_semantics': ['event'], 'asserts': [{'holds': 'ready', 'at': 't0'}]}, 'world_model': {'model_id': 'event-world', 'model_version': 'revision-1'}, 'inputs': {'events': [{'event_id': 'event-ready', 'at': 't0', 'initiates': 'ready'}]}}
    return contract

def test_unit_and_one_node_mesh_share_one_qualification_shape() -> None:
    contract = _event_contract()
    mesh_contract = ModelMeshContract.from_dict({'mesh_id': 'qualification-mesh', 'nodes': [{'model_id': 'event-world', 'contract': contract}]})
    shared_context = qualification_context_for_node(mesh_contract, mesh_contract.nodes[0])
    assert 'guard_purpose_declarations' not in contract
    unit = run_worldguard(contract, context=shared_context)
    mesh = run_model_mesh(mesh_contract)
    node = mesh.node_reports['event-world']
    assert node.to_dict() == unit.to_dict()
    assert node.derived_guards == ['EventGuard']
    assert node.gaps == []
    assert node.status == GuardStatus.PASS

def test_unavailable_provider_is_a_typed_non_pass() -> None:
    with pytest.raises(ValueError, match='unknown fields'):
        run_worldguard(_event_contract(), context={'provider_availability': {'EventGuard': False}})

def test_exact_input_repetition_has_stable_qualification_identity() -> None:
    first = run_worldguard(_event_contract())
    second = run_worldguard(deepcopy(_event_contract()))
    assert first.to_dict() == second.to_dict()
    assert set(first.to_dict()) == GuardedReport.REPORT_FIELDS

def test_unknown_report_field_fails_closed() -> None:
    with pytest.raises(ValueError, match='unknown fields'):
        GuardedReport.validate_payload_fields({'status': 'PASS', 'legacy': {}})

def test_one_row_per_problem_in_short_and_full_reports():
    from worldguard.cli import _unit_summary
    contract = _event_contract()
    contract['inputs']['events'][0]['requires'] = ['never']
    report = run_worldguard(contract)
    full = report.to_dict()
    short = _unit_summary(full)
    for payload in (full, short):
        rows = [row for row in payload['gaps'] if row['code'] == 'EVENT_PRECONDITION_UNMET']
        assert len(rows) == 1
        assert rows[0]['counterexample']['event_id'] == 'event-ready'
        assert rows[0]['counterexample']['missing_fluents'] == ['never']
        assert all((not row['code'].startswith(('SEM_', 'QUALIFICATION_STRUCTURAL_NON_PASS', 'QUALIFICATION_SEMANTIC_NON_PASS')) for row in payload['gaps']))
    assert set(short) == {'contract_id', 'status', 'checked', 'gaps', 'scope_limits'}
    assert set(full) == GuardedReport.REPORT_FIELDS

@pytest.mark.parametrize('name,expected,status', [('resource_skip.yaml', 'RESOURCE_CUMULATIVE_OVERCONSUMPTION', 'FAIL'), ('resource_first.yaml', 'RESOURCE_MISSING_TOKEN', 'FAIL'), ('two_places.yaml', 'SPACE_RCC8_CONTRADICTION WORLD_SPACE_TOKEN_MISMATCH', 'FAIL')])
def test_trial_native_problems_are_reported_once(name, expected, status):
    from pathlib import Path
    import yaml
    contract = yaml.safe_load((Path(__file__).parent / 'fixtures/trials/story_mut_out' / name).read_text())
    report = run_worldguard(contract)
    assert report.status.value == status
    assert sorted(row['code'] for row in report.gaps) == expected.split()

@pytest.mark.parametrize('file,expected', [('sb_metric_distance.yaml', 'BOUNDARY_EXCEEDED'), ('sb_numeric_dynamics.yaml', 'BOUNDARY_EXCEEDED'), ('sb_payoff.yaml', 'BOUNDARY_EXCEEDED'), ('sb_permission.yaml', 'BOUNDARY_EXCEEDED'), ('trip_boundary.yaml', 'BOUNDARY_EXCEEDED'), ('trip_boundary_neg.yaml', 'FAIL')])
def test_declared_boundary_trials_keep_their_native_status(file, expected, capsys):
    import json
    from pathlib import Path
    from worldguard.cli import main
    path = Path(__file__).parent / 'fixtures/trials' / file
    assert main(['check', '--contract', str(path), '--json']) == 1
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == expected
    assert not any((gap['code'] == 'QUALIFICATION_SEMANTIC_UNMAPPED' for gap in result['gaps']))
from worldguard.contracts import GUARD_BOUNDARY_SEMANTICS

@pytest.mark.parametrize('guard', list(GUARD_BOUNDARY_SEMANTICS))
def test_each_derived_guard_boundary_is_a_final_boundary(guard):
    import re
    from pathlib import Path
    import yaml
    from tests.helpers import GUARD_SEMANTICS, make_contract
    text = (Path(__file__).parents[1] / 'skills/worldguard/references/guard-inputs.md').read_text()
    block, assertion = re.search(f'^## {guard}\\n\\n```yaml\\n(.*?)```\\n\\nClaim assertion: `(\\{{.*?\\}})`', text, re.S | re.M).groups()
    contract = make_contract(guard, inputs=yaml.safe_load(block), asserts=[yaml.safe_load(assertion)], requested_semantics=[GUARD_SEMANTICS[guard], sorted(GUARD_BOUNDARY_SEMANTICS[guard])[0]])
    report = run_worldguard(contract)
    assert report.status == GuardStatus.BOUNDARY_EXCEEDED
    assert report.guard_results[0].status == GuardStatus.BOUNDARY_EXCEEDED
    assert report.claim_binding['status'] == 'PASS'
    assert not any((gap['code'] == 'QUALIFICATION_SEMANTIC_UNMAPPED' for gap in report.gaps))

def test_boundary_of_an_unselected_guard_remains_unmapped_with_a_hint():
    contract = _event_contract()
    contract['claim']['requested_semantics'].append('geometry')
    report = run_worldguard(contract)
    assert report.status == GuardStatus.GAP
    assert report.derived_guards == ['EventGuard']
    gap = next((gap for gap in report.gaps if gap['code'] == 'QUALIFICATION_SEMANTIC_UNMAPPED'))
    assert gap['semantic'] == 'geometry'
    assert 'SpaceGuard' in gap['message'] and 'request space' in gap['message']

@pytest.mark.parametrize('broken,expected', [('missing', GuardStatus.GAP), ('contradiction', GuardStatus.FAIL)])
def test_real_native_non_pass_outranks_a_declared_boundary(broken, expected):
    contract = _event_contract()
    contract['claim']['requested_semantics'].append('numeric_dynamics')
    if broken == 'missing':
        contract['inputs'] = {}
    else:
        contract['inputs']['events'][0]['requires'] = ['not_given']
    report = run_worldguard(contract)
    assert report.status == expected
    assert report.guard_results[0].status == expected
    assert not any((gap['code'] == 'QUALIFICATION_SEMANTIC_UNMAPPED' for gap in report.gaps))

@pytest.mark.parametrize('inputs,expected_code', [({'events': ['bad']}, 'EVENT_MISSING_INITIATION_AXIOM'), ({'resources': {'places': {'p': [{'color': 'x', 'qty': 1}]}, 'transitions': ['bad']}}, 'RESOURCE_UNEVALUABLE_TRANSITION')])
def test_malformed_native_records_keep_their_typed_guard_gap(tmp_path, capsys, inputs, expected_code):
    import json
    from worldguard.cli import main
    semantics = 'event' if 'events' in inputs else 'resource'
    path = tmp_path / 'malformed.json'
    path.write_text(json.dumps({'claim': {'requested_semantics': [semantics], 'asserts': []}, 'inputs': inputs}))
    assert main(['check', '--contract', str(path), '--json']) == 1
    captured = capsys.readouterr()
    assert captured.err == ''
    report = json.loads(captured.out)
    assert report['status'] == 'GAP'
    assert expected_code in {row['code'] for row in report['gaps']}

def test_malformed_event_keeps_native_gap_with_an_entity_registry():
    report = run_worldguard({'world_model': {'entities': {'known': {}}}, 'claim': {'requested_semantics': ['event'], 'asserts': []}, 'inputs': {'events': ['bad']}})
    assert report.status.value == 'GAP'
    assert 'EVENT_MISSING_INITIATION_AXIOM' in {row['code'] for row in report.gaps}


def test_unmapped_semantics_preserve_claim_identity():
    contract=_event_contract()
    contract['claim']={'claim_id':'claim:unknown','text':'an unregistered semantic claim','requested_semantics':['unregistered-domain']}
    report=run_worldguard(contract)
    assert report.unmapped_semantics==[{'semantic':'unregistered-domain','affected_claim_ids':['claim:unknown']}]
    assert report.status==GuardStatus.GAP


def test_space_rows_agree_with_token_places(tmp_path):
    from pathlib import Path
    import yaml
    from worldguard.cli import main
    story = yaml.safe_load((Path(__file__).parent / 'fixtures/trials/story_v1.yaml').read_text())
    assert run_worldguard(story).status is GuardStatus.PASS
    unrelated = deepcopy(story)
    for row in unrelated['inputs']['spatial_relations']:
        if row['x'] == 'cora':
            row['y'] = 'mainland'
    report = run_worldguard(unrelated)
    assert report.status is GuardStatus.GAP
    (gap,) = report.gaps
    assert gap['code'] == 'WORLD_SPACE_TOKEN_UNRELATED'
    assert gap['counterexample'] == {'at': 't4', 'x': 'cora', 'token_place': 'lamp_room', 'spatial_region': 'mainland', 'relation': 'NTPP'}
    path = tmp_path / 'unrelated.yaml'
    path.write_text(yaml.safe_dump(unrelated))
    assert main(['check', '--contract', str(path)]) == 1
    apart = deepcopy(unrelated)
    apart['inputs']['spatial_relations'].append({'at': 't4', 'x': 'mainland', 'y': 'lighthouse', 'relation': 'DC'})
    report = run_worldguard(apart)
    assert report.status is GuardStatus.FAIL
    assert [row['code'] for row in report.gaps] == ['WORLD_SPACE_TOKEN_MISMATCH']
    path = tmp_path / 'apart.yaml'
    path.write_text(yaml.safe_dump(apart))
    assert main(['check', '--contract', str(path)]) == 1


def _lighthouse_contract(name):
    from pathlib import Path
    import yaml
    return yaml.safe_load((Path(__file__).parent / 'fixtures/trials/lighthouse_key' / name).read_text())


def test_actor_state_unchecked_is_a_gap():
    contract = _lighthouse_contract('ch2_naive_no_variant.yaml')
    report = run_worldguard(contract)
    assert report.status is GuardStatus.GAP
    assert report.gaps == [{
        'code': 'EVENT_ACTOR_STATE_UNCHECKED', 'status': 'GAP', 'event_id': 'e_unlock',
        'actor': 'Lena', 'tracked_fluents': ['lena_has_key', 'lena_on_mainland'], 'source': 'ch2 p3',
        'message': "The event's actor has state in this world that the event does not require; require it or give actor_state_free: <reason>.",
    }]

    pair = deepcopy(contract)
    pair['inputs']['event_model']['initial_states'] += ['helena_x', 'éva_has_key']
    second = {**pair['inputs']['events'][-1], 'event_id': 'e_unlock_again', 'actor': 'ÉVA',
              'at': '21:01', 'requires': 'door_unlocked', 'terminates': [], 'source': 'ch2 p4'}
    pair['inputs']['events'].append(second)
    pair_report = run_worldguard(pair)
    assert pair_report.status is GuardStatus.GAP
    assert [(row['event_id'], row['actor'], row['tracked_fluents']) for row in pair_report.gaps] == [
        ('e_unlock', 'Lena', ['lena_has_key', 'lena_on_mainland']),
        ('e_unlock_again', 'ÉVA', ['éva_has_key']),
    ]

    independent = deepcopy(contract)
    independent['claim'] = {'asserts': [{'variable': 'x', 'op': '>=', 'value': 0}]}
    independent['inputs']['causal_model'] = {'variables': ['x'], 'equations': {'x': '1'}, 'scenarios': {'base': {}}}
    report = run_worldguard(independent)
    assert report.derived_guards == ['CausalGuard']
    assert report.status is GuardStatus.GAP
    assert [row['code'] for row in report.gaps] == ['EVENT_ACTOR_STATE_UNCHECKED']


def test_actor_state_free_reason_is_printed():
    import re
    from worldguard import GuardContract
    from worldguard.cli import _unit_summary

    contract = _lighthouse_contract('ch2_naive_no_variant.yaml')
    contract['inputs']['events'][-1]['actor_state_free'] = 'the door opens from either side'
    reason = 'actor_state_free e_unlock (Lena): the door opens from either side'
    report = run_worldguard(contract)
    assert report.status is GuardStatus.PASS
    assert report.gaps == []
    assert reason in report.to_dict()['scope_limits']
    assert reason in _unit_summary(report.to_dict())['scope_limits']
    mesh = {'nodes': [{'model_id': 'root', 'contract': contract}, {'model_id': 'child', 'contract': contract}],
            'edges': [{'edge_id': 'root-child', 'from': 'root', 'to': 'child', 'relation': 'parent_child'}]}
    tree = run_model_mesh(mesh)
    assert tree.status is GuardStatus.PASS
    assert tree.scope_limits == sorted({reason, 'chapter 2 only'})
    for invalid in ('', ' \t ', None):
        contract['inputs']['events'][-1]['actor_state_free'] = invalid
        with pytest.raises(ValueError, match=re.escape('inputs.events[2].actor_state_free must be a nonempty reason')):
            GuardContract.from_dict(contract)


def test_shipped_worlds_have_no_actor_state_gap():
    from pathlib import Path
    import yaml

    examples = Path(__file__).parents[1] / 'skills/worldguard/assets/examples'
    for name in ('scene_locked_door.yaml', 'trip_ferry.yaml', 'story_mesh.yaml'):
        contract = yaml.safe_load((examples / name).read_text())
        report = run_model_mesh(contract, base_dir=examples) if name == 'story_mesh.yaml' else run_worldguard(contract)
        assert report.status is GuardStatus.PASS
        assert not any(row['code'] == 'EVENT_ACTOR_STATE_UNCHECKED' for row in report.to_dict()['gaps'])
    for name in ('ch1_fixed.yaml', 'ch2_fixed.yaml'):
        report = run_worldguard(_lighthouse_contract(name))
        assert report.status is GuardStatus.PASS
        assert not any(row['code'] == 'EVENT_ACTOR_STATE_UNCHECKED' for row in report.gaps)
