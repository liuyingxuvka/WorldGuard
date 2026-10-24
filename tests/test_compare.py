"""Observation comparison uses actual expected world values and rejects unknown identities."""
from copy import deepcopy
from pathlib import Path
import json

import pytest
import yaml

from worldguard.cli import main
from worldguard.compare import compare_world
from worldguard.io import load_mapping

TRIP = Path(__file__).resolve().parents[1] / 'skills/worldguard/assets/examples/trip_ferry.yaml'


@pytest.mark.parametrize('at,status,difference', [('2026-11-02T10:25', 'FAIL', 20), ('2026-11-02T10:08', 'PASS', 3)])
def test_trip_arrival_uses_minutes_and_declared_tolerance(tmp_path, capsys, at, status, difference):
    path = tmp_path / 'observed.yaml'
    path.write_text(yaml.safe_dump({'events': {'d1_train_arr': at}, 'time_tolerance': 5, 'source': 'trip log'}))
    assert main(['compare', '--contract', str(TRIP), '--observed', str(path)]) == (0 if status == 'PASS' else 1)
    result = json.loads(capsys.readouterr().out)
    assert result['status'] == status and result['source'] == 'trip log'
    row = (result['matches'] or result['mismatches'])[0]
    assert row['id'] == 'd1_train_arr' and row['kind'] == 'event'
    assert row['difference'] == difference and row['tolerance'] == 5
    if status == 'FAIL':
        assert row['mismatch_code'] == 'value_outside_tolerance'


@pytest.mark.parametrize('observed', [
    {'events': {'missing': '2026-11-02T10:25'}},
    {'variables': {'missing': 1}},
    {'scenario': 'missing', 'variables': {'slack_out_h': 1}},
    {'events': {'d1_train_arr': 't10'}},
    {'time_tolerance': -1}, {'tolerance': float('nan')}, {'variables': {'slack_out_h': True}},
])
def test_invalid_comparisons_are_typed_input_errors(tmp_path, capsys, observed):
    path = tmp_path / 'observed.yaml'
    path.write_text(yaml.safe_dump(observed))
    assert main(['compare', '--contract', str(TRIP), '--observed', str(path)]) == 2
    assert json.loads(capsys.readouterr().out)['error']['code'] == 'WORLDGUARD_INPUT_INVALID'


def test_variables_come_from_native_scenarios_and_inputs_are_unchanged():
    world = load_mapping(TRIP)
    before = deepcopy(world)
    observed = {'variables': {'slack_back_h': .75}, 'tolerance': .01}
    result = compare_world(world, observed)
    assert result['status'] == 'PASS' and result['matches'][0]['expected_value'] == .75
    assert world == before and observed == {'variables': {'slack_back_h': .75}, 'tolerance': .01}
    result = compare_world(world, {'variables': {'slack_back_h': .5}, 'tolerance': .01})
    assert result['status'] == 'FAIL' and result['mismatches'][0]['difference'] == -.25
    assert len(result['mismatches']) == 1  # Unobserved event/variable ids are not mismatches.


def test_multiple_scenarios_require_an_explicit_choice():
    world = load_mapping(TRIP)
    world['inputs']['causal_model']['scenarios']['alternative'] = {}
    with pytest.raises(ValueError, match='explicit'):
        compare_world(world, {'variables': {'slack_back_h': .75}})
    assert compare_world(world, {'scenario': 'alternative', 'variables': {'slack_back_h': .75}})['status'] == 'PASS'


@pytest.mark.parametrize('expected,actual,bound,difference', [('t10', 't13', 3, 3), ('10:00', '10:03', 3, 3), (10, 13, 3, 3)])
def test_event_time_units_follow_the_canonical_clock(expected, actual, bound, difference):
    world = {'claim': {'requested_semantics': ['event']}, 'inputs': {'events': [{'event_id': 'e', 'at': expected}]}}
    result = compare_world(world, {'events': {'e': actual}, 'time_tolerance': bound})
    assert result['status'] == 'PASS' and result['matches'][0]['difference'] == difference


def test_compare_help_has_both_inputs(capsys):
    with pytest.raises(SystemExit) as exc:
        main(['compare', '--help'])
    assert exc.value.code == 0
    text = capsys.readouterr().out
    assert '--contract' in text and '--observed' in text


def test_mesh_compare_names_the_late_node(tmp_path,capsys):
    from tests.test_model_mesh import continued_tree
    world=tmp_path/'world.json';world.write_text(json.dumps(continued_tree()))
    observed=tmp_path/'observed.json';observed.write_text(json.dumps({'nodes':{'a':{'events':{'a':'t3'}}}}))
    assert main(['compare','--mesh',str(world),'--observed',str(observed)])==1
    result=json.loads(capsys.readouterr().out)
    assert result['mismatches'][0]['node']=='a' and result['mismatches'][0]['id']=='a'
    assert result['mismatches'][0]['difference']==2


def test_written_observed_copy_shows_the_downstream_break(tmp_path,capsys):
    from tests.test_model_mesh import continued_tree
    from worldguard.mesh import compare_mesh_with_observed_copy
    original=continued_tree();before=deepcopy(original)
    original['nodes'][1]['contract']['inputs']['causal_model']={'variables':['x'],'equations':{'x':'1'},'scenarios':{'plan':{}}}
    before=deepcopy(original)
    observations={'nodes':{'a':{'events':{'a':'t3'},'variables':{'x':2},'scenario':'plan'}}}
    result,copied=compare_mesh_with_observed_copy(original,observations)
    expected=deepcopy(original);expected['nodes'][1]['contract']['inputs']['events'][0]['at']='t3'
    assert copied==expected and original==before
    from worldguard.compare import compare_with_observed_copy
    single_result,single_copy=compare_with_observed_copy(original["nodes"][1]["contract"],observations["nodes"]["a"])
    assert single_copy==expected["nodes"][1]["contract"] and single_result["status"]==result["status"]
    world=tmp_path/'world.json';world.write_text(json.dumps(original));obs=tmp_path/'observed.json';obs.write_text(json.dumps(observations));out=tmp_path/'out.json'
    assert main(['compare','--mesh',str(world),'--observed',str(obs),'--write-observed',str(out)])==1
    capsys.readouterr()
    assert json.loads(out.read_text())==expected and json.loads(world.read_text())==before
    assert main(['mesh-check','--mesh',str(out),'--json'])==1
    report=json.loads(capsys.readouterr().out)
    assert any(g['code']=='MESH_HANDOFF_TIME_BACKWARDS' for g in report['gaps'])
    assert main(['compare','--mesh',str(world),'--observed',str(obs),'--write-observed',str(out)])==2
    assert json.loads(out.read_text())==expected
