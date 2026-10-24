import pytest
from worldguard.contracts import GuardContract
from worldguard.reports import GuardResult
from worldguard.status import GuardStatus

def test_retired_world_model_version_alias_fails():
    with pytest.raises(ValueError, match='world_model.artifact_version is retired'):
        GuardContract.from_dict({'contract_id': 'c1', 'claim': {'claim_id': 'claim', 'text': 'text', 'requested_semantics': ['event']}, 'world_model': {'model_id': 'm1', 'artifact_version': 'v1'}})

@pytest.mark.parametrize(('world_model_extra', 'inputs', 'message'), [({'event_line': []}, {}, 'world_model uses retired Guard input fields'), ({}, {'norm_model': {}}, 'inputs uses retired alternate Guard paths'), ({}, {'event_model': {'events': []}}, 'inputs.event_model.events is retired'), ({}, {'event_model': {'exclusive_violation': []}}, 'inputs.event_model.exclusive_violation is retired'), ({}, {'agent_model': {'agents': {}}}, 'inputs.agent_model.agents is retired'), ({}, {'events': [{'branch_ids': ['b1']}]}, 'inputs.events\\[0\\] uses retired fields'), ({}, {'variable_observations': []}, 'inputs.variable_observations must be a mapping'), ({}, {'causal_model': {'scenarios': {'s1': {'values': {'x': 1}}}}}, 'records use retired nested values'), ({}, {'causal_model': {'interventions': [{'id': 'i1'}]}}, 'interventions\\[0\\] uses retired fields'), ({}, {'causal_model': {'counterfactuals': [{'variable': 'x'}]}}, 'counterfactuals\\[0\\] uses retired fields'), ({}, {'facts': [{'name': 'f1'}]}, 'inputs.facts\\[0\\].name is retired'), ({}, {'norms': [{'condition': {'fact': 'f1'}}]}, 'inputs.norms\\[0\\].condition.fact is retired')])
def test_retired_guard_input_paths_fail_visibly(world_model_extra, inputs, message):
    with pytest.raises(ValueError, match=message):
        GuardContract.from_dict({'contract_id': 'c1', 'claim': {'claim_id': 'claim', 'text': 'text', 'requested_semantics': ['event']}, 'world_model': {'model_id': 'm1', 'model_version': 'v1', **world_model_extra}, 'inputs': inputs})

def test_non_pass_result_requires_evidence():
    with pytest.raises(ValueError, match='lacks a problem'):
        GuardResult(guard='EventGuard', status=GuardStatus.GAP)

def test_contract_serializes_canonical_fields():
    contract = GuardContract.from_dict({'contract_id': 'c1', 'claim': {'claim_id': 'claim', 'text': 'text', 'requested_semantics': ['norm']}, 'world_model': {'model_id': 'm1', 'model_version': 'v1', 'scope_limits': ['toy']}, 'inputs': {'norms': []}})
    data = contract.to_dict()
    assert data['claim']['requested_semantics'] == ['norm']
    assert 'dependencies' not in data
    assert 'output_requirements' not in data

@pytest.mark.parametrize('times', [['t4b'], ['evening'], [True], [float('nan')], ['24:00'], ['t1', 'day2'], ['t1', '2026-01-01'], ['2026-01-01T09:00', '2026-01-01T10:00Z'], [580, '9:40']])
def test_contract_rejects_unknown_or_mixed_event_time_kinds(times):
    with pytest.raises(ValueError, match='time|prefix|timezone'):
        GuardContract.from_dict({'claim': {'requested_semantics': ['event']}, 'inputs': {'events': [{'event_id': f'named-{i}', 'at': at, 'initiates': 'ready'} for i, at in enumerate(times)]}})

@pytest.mark.parametrize('scenario', [None, 'same'])
def test_contract_rejects_duplicate_event_ids_in_one_scenario(scenario):
    events = [{'event_id': 'duplicate', 'at': 't1', 'initiates': 'ready'}, {'event_id': 'duplicate', 'at': 't2', 'initiates': 'done'}]
    if scenario:
        for event in events:
            event['scenario_id'] = scenario
    with pytest.raises(ValueError, match="duplicate event_id 'duplicate'"):
        GuardContract.from_dict({'claim': {'requested_semantics': ['event']}, 'inputs': {'events': events}})

@pytest.mark.parametrize('interventions', [{}, None, [42], [{}], [{'intervention_id': '', 'scenario_id': 's', 'set': {'x': 2}}], [{'intervention_id': 'do', 'scenario_id': 'unknown', 'set': {'x': 2}}], [{'intervention_id': 's', 'scenario_id': 's', 'set': {'x': 2}}], [{'intervention_id': 'do', 'scenario_id': 's'}], [{'intervention_id': 'do', 'scenario_id': 's', 'set': []}], [{'intervention_id': 'do', 'scenario_id': 's', 'set': {'unknown': 2}}], [{'intervention_id': 'do', 'scenario_id': 's', 'set': {'x': True}}], [{'intervention_id': 'do', 'scenario_id': 's', 'set': {'x': '2'}}], [{'intervention_id': 'do', 'scenario_id': 's', 'set': {'x': float('inf')}}], [{'intervention_id': 'do', 'scenario_id': 's', 'set': {'x': 2}}, {'intervention_id': 'do', 'scenario_id': 'h', 'set': {'x': 3}}]])
def test_intervention_input_shapes_and_identities_are_rejected(interventions):
    with pytest.raises(ValueError, match='interventions'):
        GuardContract.from_dict({'claim': {'claim_id': 'shape', 'requested_semantics': ['causal']}, 'inputs': {'causal_model': {'variables': ['x'], 'equations': {'x': '1'}, 'scenarios': {'s': {}}, 'holdout_scenarios': {'h': {}}, 'interventions': interventions}}})

def test_scenario_and_holdout_run_ids_cannot_overwrite_each_other():
    with pytest.raises(ValueError, match='distinct ids'):
        GuardContract.from_dict({'claim': {'claim_id': 'collision', 'requested_semantics': ['causal']}, 'inputs': {'causal_model': {'variables': ['x'], 'equations': {'x': '1'}, 'scenarios': {'same': {'x': 1}}, 'holdout_scenarios': {'same': {'x': -1}}}}})


@pytest.mark.parametrize('path', ['schema_version','run_id','dependencies','output_requirements','claim.atoms','claim.target_guard','claim.target_guards'])
def test_retired_contract_keys_are_input_errors(path, tmp_path, capsys):
    from worldguard.cli import main
    import json
    data={'claim':{'claim_id':'present-retired-key','requested_semantics':['event']},'inputs':{'events':[{'event_id':'e','at':'t0','initiates':'ready'}]}}
    section=data['claim'] if path.startswith('claim.') else data
    section[path.split('.')[-1]]=None
    file=tmp_path/'retired.json';file.write_text(json.dumps(data))
    assert main(['check','--contract',str(file)])==2
    error=json.loads(capsys.readouterr().out)['error']
    assert error['code']=='WORLDGUARD_INPUT_INVALID'
    assert path in error['message'] and 'retired' in error['message']
