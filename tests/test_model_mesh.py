import json
import pytest
import yaml
from worldguard import GuardContract, ModelMeshContract, MeshReport, derive_required_guards, run_model_mesh
from worldguard.cli import main
from worldguard.status import GuardStatus

@pytest.mark.parametrize('payload', [{'mesh_id': 'm', 'semantic_coverage_contract': {}}, {'mesh_id': 'm', 'coverage_contract': {}}, {'mesh_id': 'm', 'semantic_coverage': {'expected_node_ids': []}}, {'mesh_id': 'm', 'semantic_coverage': {'excluded_nodes': []}}, {'mesh_id': 'm', 'semantic_coverage': {'per_object_coverage': {}}}, {'mesh_id': 'm', 'semantic_coverage': {'expected_child_ids': []}}, {'mesh_id': 'm', 'semantic_coverage': {'horizon': {'timepoint_ids': ['t0']}}}])
def test_retired_mesh_fields_fail_instead_of_falling_back(payload):
    with pytest.raises(ValueError, match='retired'):
        ModelMeshContract.from_dict(payload)

def pass_mesh():
    mesh = {'mesh_id': 'mesh-pass', 'nodes': [{'model_id': 'event-source', 'contract': {'contract_id': 'event-contract', 'claim': {'claim_id': 'event-claim', 'text': 'operator starts after precheck', 'requested_semantics': ['event'], 'asserts': [{'holds': 'ready', 'at': 't0'}]}, 'world_model': {'model_id': 'event-model', 'model_version': 'v1'}, 'inputs': {'events': [{'event_id': 'e1', 'at': 't0', 'initiates': 'ready'}]}}}, {'model_id': 'norm-target', 'contract': {'contract_id': 'norm-contract', 'claim': {'claim_id': 'norm-claim', 'text': 'operator may start', 'requested_semantics': ['norm'], 'asserts': [{'action': 'start', 'modality': 'permitted'}]}, 'world_model': {'model_id': 'norm-model', 'model_version': 'v1'}, 'inputs': {'norms': [{'modality': 'permitted', 'action': 'start', 'condition': 'precheck_complete'}], 'facts': [{'fact_id': 'precheck_complete', 'value': True}]}}}], 'edges': [{'edge_id': 'event-to-norm', 'from': 'event-source', 'to': 'norm-target', 'relation': 'parent_child'}]}
    mesh['nodes'][0]['contract']
    mesh['nodes'][1]['contract']
    return mesh

def test_model_mesh_pass_preserves_child_ledgers():
    report = run_model_mesh(pass_mesh())
    assert report.status == GuardStatus.PASS
    assert set(report.node_reports) == {'event-source', 'norm-target'}
    assert report.node_reports['event-source'].guard_results[0].guard == 'EventGuard'
    assert report.node_reports['norm-target'].guard_results[0].guard == 'NormGuard'

def test_child_gap_prevents_mesh_pass_and_preserves_gap_ledger():
    mesh = pass_mesh()
    mesh['nodes'][0]['contract']['inputs'] = {}
    report = run_model_mesh(mesh)
    assert report.status == GuardStatus.GAP
    assert any((row['status'] == 'GAP' for row in report.to_dict()['gaps']))

def test_dependency_cycle_fails_mesh():
    mesh = {'mesh_id': 'cycle-mesh', 'nodes': [{'model_id': 'a'}, {'model_id': 'b'}], 'edges': [{'edge_id': 'a-b', 'from': 'a', 'to': 'b', 'relation': 'parent_child'}, {'edge_id': 'b-a', 'from': 'b', 'to': 'a', 'relation': 'parent_child'}]}
    report = run_model_mesh(mesh)
    assert report.status == GuardStatus.FAIL
    assert any((finding.code == 'MESH_DEPENDENCY_CYCLE' for finding in report.findings))

def test_unknown_relation_and_missing_transfer_mapping_fail_closed() -> None:
    unknown = pass_mesh()
    unknown['edges'][0]['relation'] = 'looks_like_dependency'
    with pytest.raises(ValueError, match='relation'):
        ModelMeshContract.from_dict(unknown)
    missing = pass_mesh()
    missing['edges'][0]['port_mappings'] = []
    with pytest.raises(ValueError, match='port_mappings'):
        ModelMeshContract.from_dict(missing)

@pytest.mark.parametrize(('edge_field', 'expected_code'), [('from', 'MESH_EDGE_NODE_MISSING'), ('to', 'MESH_EDGE_NODE_MISSING')])
def test_missing_handoff_endpoint_remains_a_visible_gap(edge_field: str, expected_code: str) -> None:
    mesh = pass_mesh()
    mesh['edges'][0][edge_field] = 'missing-model'
    report = run_model_mesh(mesh)
    assert report.status == GuardStatus.GAP
    assert any((finding.code == expected_code and finding.evidence.get('side') == edge_field for finding in report.findings))

def test_public_api_exports_model_mesh():
    mesh = ModelMeshContract.from_dict(pass_mesh())
    report = run_model_mesh(mesh)
    assert isinstance(report, MeshReport)

def test_cli_mesh_check_outputs_json(tmp_path, capsys):
    path = tmp_path / 'mesh.yaml'
    path.write_text(yaml.safe_dump(pass_mesh()), encoding='utf-8')
    assert main(['mesh-check', '--mesh', str(path), '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['status'] == 'PASS'
    assert set(data['nodes']) == {'event-source', 'norm-target'}

def test_mesh_node_claims_must_be_bound_to_their_models():
    unbound = pass_mesh()
    del unbound['nodes'][1]['contract']['claim']['asserts']
    report = run_model_mesh(unbound)
    assert report.status == GuardStatus.GAP
    assert [gap['code'] for gap in report.node_reports['norm-target'].gaps] == ['CLAIM_NOT_BOUND']
    contradicted = pass_mesh()
    contradicted['nodes'][1]['contract']['claim']['asserts'] = [{'action': 'start', 'modality': 'forbidden'}]
    report = run_model_mesh(contradicted)
    assert report.status == GuardStatus.FAIL

def test_expected_contractless_node_is_counted_and_blocks_aggregate_pass():
    report = run_model_mesh({'mesh_id': 'contractless', 'nodes': [{'model_id': 'missing-contract'}]})
    assert report.status == GuardStatus.GAP
    assert report.to_dict()['checked'] == {'nodes': 1, 'edges': 0, 'roots': 1, 'variants': 0}
    assert 'missing-contract' not in report.node_reports
    assert any((finding.code == 'MESH_EXPECTED_NODE_CONTRACT_MISSING' for finding in report.findings))

def test_retired_semantic_coverage_cli_is_a_typed_input_error(tmp_path, capsys):
    path = tmp_path / 'retired.json'
    path.write_text(json.dumps({'mesh_id': 'old', 'semantic_coverage': {'profile': 'bounded'}}))
    assert main(['mesh-check', '--mesh', str(path)]) == 2
    error = json.loads(capsys.readouterr().out)['error']
    assert error['code'] == 'WORLDGUARD_INPUT_INVALID'
    assert 'semantic_coverage' in error['message'] and 'retired' in error['message']

@pytest.mark.parametrize('filename,status,code,detail', [('chapters_ok_rooted.yaml', 'PASS', None, None), ('end_state_contradiction.yaml', 'FAIL', 'MESH_HANDOFF_STATE_MISMATCH', 'lamp_dark'), ('ch2_resurrects.yaml', 'FAIL', 'MESH_HANDOFF_STATE_MISMATCH', 'cora_at_mainland'), ('time_backwards.yaml', 'FAIL', 'MESH_HANDOFF_TIME_BACKWARDS', None)])
def test_continues_carries_state_and_time(filename, status, code, detail, capsys):
    from pathlib import Path
    path = Path(__file__).parent / 'fixtures/trials/mesh_continues' / filename
    assert main(['mesh-check', '--mesh', str(path), '--json']) == (0 if status == 'PASS' else 1)
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == status
    if code:
        assert any((row['code'] == code for row in report['gaps']))
    if detail:
        assert detail in json.dumps(report['gaps'])

def continued_tree():

    def contract(name, initial, at, begins, ends):
        return {'contract_id': name, 'claim': {'claim_id': name, 'asserts': [{'holds': begins, 'at': at}]}, 'inputs': {'event_model': {'initial_states': initial}, 'events': [{'event_id': name, 'at': at, 'initiates': [begins], 'terminates': [ends]}]}}
    return {'mesh_id': 'tree', 'nodes': [{'model_id': 'root', 'contract': {'claim': {'claim_id': 'summary', 'asserts': [{'node': 'b', 'holds': 'done', 'at': 't2'}]}}}, {'model_id': 'a', 'contract': contract('a', ['dark'], 't1', 'lit', 'dark')}, {'model_id': 'b', 'contract': contract('b', ['lit'], 't2', 'done', 'lit')}], 'edges': [{'edge_id': 'root-a', 'from': 'root', 'to': 'a', 'relation': 'parent_child'}, {'edge_id': 'root-b', 'from': 'root', 'to': 'b', 'relation': 'parent_child'}, {'edge_id': 'a-b', 'from': 'a', 'to': 'b', 'relation': 'continues'}]}

def _mesh_cli(tmp_path, capsys, data):
    path = tmp_path / 'mesh.yaml'
    path.write_text(yaml.safe_dump(data))
    result = main(['mesh-check', '--mesh', str(path), '--json'])
    captured = capsys.readouterr()
    return (result, json.loads(captured.out or captured.err))

def test_parent_rows_read_descendants_without_running_parent_guards(tmp_path, capsys):
    tree = continued_tree()
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 0 and report['status'] == 'PASS'
    assert report['checked']['roots'] == 1
    assert report['nodes']['root']['checked']['guards'] == []
    tree['nodes'][0]['contract']['claim']['asserts'][0]['value'] = False
    assert _mesh_cli(tmp_path, capsys, tree)[1]['status'] == 'FAIL'

def test_node_rows_read_descendants_only(tmp_path, capsys):
    tree = continued_tree()
    tree['edges'] = [edge for edge in tree['edges'] if edge['edge_id'] != 'root-b']
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 1 and report['status'] == 'GAP'
    assert 'descendant' in json.dumps(report['gaps'])
    standalone = tree['nodes'][0]['contract']
    path = tmp_path / 'standalone.yaml'
    path.write_text(yaml.safe_dump(standalone))
    assert main(['check', '--contract', str(path)]) == 1
    assert 'node rows need mesh-check' in capsys.readouterr().out

def test_child_failure_reaches_root_even_when_parent_assertion_is_true(tmp_path, capsys):
    tree = continued_tree()
    tree['nodes'][2]['contract']['claim']['asserts'][0]['value'] = False
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 1 and report['status'] == 'FAIL'
    assert report['nodes']['root']['status'] == 'PASS'
    assert report['nodes']['b']['status'] == 'FAIL'

def test_continues_cycle_fails(tmp_path, capsys):
    tree = continued_tree()
    tree['edges'].append({'edge_id': 'back', 'from': 'b', 'to': 'a', 'relation': 'continues'})
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 1 and any((row['code'] == 'MESH_DEPENDENCY_CYCLE' for row in report['gaps']))

def test_contract_paths_resolve_beside_mesh_and_missing_file_names_node(tmp_path, capsys):
    tree = continued_tree()
    baseline = run_model_mesh(tree).to_dict()
    for node in tree['nodes']:
        path = tmp_path / (node['model_id'] + '.yaml')
        path.write_text(yaml.safe_dump(node['contract']))
        node['contract'] = path.name
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 0 and report == baseline
    tree['nodes'][1]['contract'] = 'missing.yaml'
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 2 and 'node a' in json.dumps(report) and ('missing.yaml' in json.dumps(report))

@pytest.mark.parametrize('change', ['freshness', 'ports', 'empty_ports', 'empty_port_map', 'clock'])
def test_continues_rejects_invalid_inputs(tmp_path, capsys, change):
    tree = continued_tree()
    if change == 'freshness':
        tree['nodes'][1]['freshness_status'] = 'fresh'
    elif change == 'ports':
        tree['edges'][2]['port_mappings'] = [{'mapping_id': 'bad', 'source_port_id': 'x', 'target_port_id': 'y'}]
    elif change in {'empty_ports', 'empty_port_map'}:
        tree['edges'][2]['port_mappings'] = [] if change == 'empty_ports' else {}
    else:
        tree['nodes'][2]['contract']['inputs']['events'][0]['at'] = '2026-11-02T10:00'
        tree['nodes'][2]['contract']['claim']['asserts'][0]['at'] = '2026-11-02T10:00'
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 2 and report['error']['code'] == 'WORLDGUARD_INPUT_INVALID'

def test_continues_compares_unique_token_positions(tmp_path, capsys):
    tree = continued_tree()
    source, target = (tree['nodes'][index]['contract']['inputs'] for index in (1, 2))
    source['events'][0]['actor'] = 'token'
    source['resources'] = {'unique': ['token'], 'places': {'left': [{'color': 'token', 'qty': 1}]}, 'transitions': [{'id': 'move', 'event': 'a', 'consumes': [{'place': 'left', 'color': 'token', 'qty': 1}], 'produces': [{'place': 'right', 'color': 'token', 'qty': 1}]}]}
    target['resources'] = {'unique': ['token'], 'places': {'left': [{'color': 'token', 'qty': 1}]}}
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 1 and any((row['code'] == 'MESH_HANDOFF_STATE_MISMATCH' and row['evidence'].get('color') == 'token' for row in report['gaps']))

def test_continues_compares_requested_scenario_values_and_missing_values(tmp_path, capsys):
    tree = continued_tree()
    tree['edges'][2]['variables'] = ['v']
    for index in (1, 2):
        tree['nodes'][index]['contract']['inputs']['causal_model'] = {'variables': ['v'], 'exogenous': ['seed'], 'equations': {'v': 'seed'}, 'scenarios': {'first': {'seed': 1}}}
    assert _mesh_cli(tmp_path, capsys, tree)[0] == 0
    target = tree['nodes'][2]['contract']['inputs']['causal_model']
    target['scenarios']['first']['seed'] = 1 + 5e-10
    assert _mesh_cli(tmp_path, capsys, tree)[0] == 0
    target['scenarios']['second'] = {'seed': 2}
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 1 and any((row['code'] == 'MESH_HANDOFF_VALUE_MISMATCH' for row in report['gaps']))
    tree['nodes'][1]['contract']['inputs'].pop('causal_model')
    assert any((row['code'] == 'MESH_HANDOFF_VALUE_MISSING' for row in _mesh_cli(tmp_path, capsys, tree)[1]['gaps']))

def test_continues_trip_cannot_depart_before_prior_arrival(tmp_path, capsys):
    tree = continued_tree()
    for index, at in ((1, '2026-11-02T10:20'), (2, '2026-11-02T10:00')):
        contract = tree['nodes'][index]['contract']
        contract['inputs']['events'][0]['at'] = at
        contract['claim']['asserts'][0]['at'] = at
    tree['nodes'][0]['contract']['claim']['asserts'][0]['at'] = '2026-11-02T10:00'
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 1 and any((row['code'] == 'MESH_HANDOFF_TIME_BACKWARDS' for row in report['gaps']))

def test_unmentioned_source_fluents_do_not_need_target_copies(tmp_path, capsys):
    tree = continued_tree()
    tree['nodes'][1]['contract']['inputs']['event_model']['initial_states'].append('source_only')
    assert _mesh_cli(tmp_path, capsys, tree)[0] == 0

@pytest.mark.parametrize('side', [1, 2])
@pytest.mark.parametrize('independent_failure', [False, True])
def test_continues_missing_event_time_preserves_native_node_reports(tmp_path, capsys, side, independent_failure):
    tree = continued_tree()
    del tree['nodes'][side]['contract']['inputs']['events'][0]['at']
    if independent_failure:
        other = 3 - side
        tree['nodes'][other]['contract']['claim']['asserts'][0]['value'] = False
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 1
    assert report['status'] == ('FAIL' if independent_failure else 'GAP')
    assert set(report['nodes']) == {'root', 'a', 'b'}
    assert report['nodes'][tree['nodes'][side]['model_id']]['status'] == 'GAP'
    assert any((row['code'] == 'MESH_HANDOFF_TIME_MISSING' for row in report['gaps']))

@pytest.mark.parametrize('dimension,expected_code', [('fluent', 'MESH_HANDOFF_STATE_MISMATCH'), ('token', 'MESH_HANDOFF_STATE_MISMATCH'), ('variable', 'MESH_HANDOFF_VALUE_MISMATCH')])
def test_missing_target_time_does_not_hide_independent_handoff_failures(tmp_path, capsys, dimension, expected_code):
    tree = continued_tree()
    source, target = (tree['nodes'][index]['contract']['inputs'] for index in (1, 2))
    del target['events'][0]['at']
    if dimension == 'fluent':
        target['event_model']['initial_states'] = []
    elif dimension == 'token':
        source['resources'] = {'unique': ['token'], 'places': {'left': [{'color': 'token', 'qty': 1}]}}
        target['resources'] = {'unique': ['token'], 'places': {'right': [{'color': 'token', 'qty': 1}]}}
    else:
        tree['edges'][2]['variables'] = ['v']
        for inputs, value in ((source, 1), (target, 2)):
            inputs['causal_model'] = {'variables': ['v'], 'equations': {'v': str(value)}, 'scenarios': {'actual': {}}}
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 1 and report['status'] == 'FAIL'
    assert report['nodes']['b']['status'] == 'GAP'
    assert any((row['code'] == 'MESH_HANDOFF_TIME_MISSING' for row in report['gaps']))
    assert any((row['code'] == expected_code for row in report['gaps']))

def test_missing_source_time_does_not_hide_an_unmoved_unique_color_mismatch(tmp_path, capsys):
    tree = continued_tree()
    source, target = (tree['nodes'][index]['contract']['inputs'] for index in (1, 2))
    del source['events'][0]['at']
    source['events'][0]['actor'] = 'y'
    source['resources'] = {'unique': ['x'], 'places': {'left': [{'color': 'x', 'qty': 1}], 'yard': [{'color': 'y', 'qty': 1}]}, 'transitions': [{'id': 'move-y', 'event': 'a', 'consumes': [{'place': 'yard', 'color': 'y', 'qty': 1}], 'produces': [{'place': 'elsewhere', 'color': 'y', 'qty': 1}]}]}
    target['resources'] = {'unique': ['x'], 'places': {'right': [{'color': 'x', 'qty': 1}]}}
    code, report = _mesh_cli(tmp_path, capsys, tree)
    assert code == 1 and report['status'] == 'FAIL'
    assert any((row['code'] == 'MESH_HANDOFF_STATE_MISMATCH' and row['evidence'].get('color') == 'x' for row in report['gaps']))

def test_continues_roundtrip_omits_only_its_forbidden_port_mapping_field():
    tree = continued_tree()
    mesh = ModelMeshContract.from_dict(tree)
    serialized = mesh.to_dict()
    assert 'port_mappings' not in serialized['edges'][2]
    assert 'port_mappings' not in serialized['edges'][0]
    assert ModelMeshContract.from_dict(serialized).to_dict() == serialized


@pytest.mark.parametrize('where,key', [('mesh','schema_version'),('mesh','run_id'),('mesh','snapshots'),('node','model_version'),('node','model_kind'),('node','authority'),('node','freshness_status'),('node','input_ports'),('node','output_ports'),('edge','source_model_id'),('edge','target_model_id'),('edge','port_mappings'),('edge','allowed_use'),('edge','forbidden_use'),('edge','read_only'),('edge','requires_current_source')])
def test_retired_mesh_keys_and_relations_are_input_errors(where,key,tmp_path,capsys):
    data=continued_tree()
    section=data if where=='mesh' else data['nodes'][0] if where=='node' else data['edges'][0]
    section[key]=None
    result,report=_mesh_cli(tmp_path,capsys,data)
    assert result==2
    assert key in report['error']['message'] and 'retired' in report['error']['message']


def test_a_mesh_with_two_roots_is_not_one_tree():
    from pathlib import Path
    path=Path(__file__).parent/'fixtures/trials/mesh_continues/chapters_ok.yaml'
    report=run_model_mesh(yaml.safe_load(path.read_text()))
    problem=next(f for f in report.findings if f.code=='MESH_NOT_ONE_TREE')
    assert report.status is GuardStatus.GAP
    assert problem.evidence['roots']==['ch1','ch2']
    rooted=path.with_name('chapters_ok_rooted.yaml')
    assert run_model_mesh(yaml.safe_load(rooted.read_text())).status is GuardStatus.PASS


def test_mesh_summary_prints_the_tree(tmp_path,capsys):
    data=continued_tree();file=tmp_path/'tree.yaml';file.write_text(yaml.safe_dump(data))
    assert main(['mesh-check','--mesh',str(file)])==0
    result=json.loads(capsys.readouterr().out)
    assert result['tree']==['root PASS','  a PASS -> continues b PASS','  b PASS']


def test_tree_lines_show_subtree_and_edge_status():
    data=continued_tree()
    data['nodes'][2]['contract']['inputs']['events'][0]['at']='t0'
    data['nodes'][2]['contract']['claim']['asserts'][0]['at']='t0'
    data['nodes'][0]['contract']['claim']['asserts'][0]['at']='t0'
    report=run_model_mesh(data)
    assert report.status is GuardStatus.FAIL
    assert report.tree==['root PASS (tree FAIL)','  a PASS -> continues b FAIL MESH_HANDOFF_TIME_BACKWARDS','  b PASS']
    planned=continued_tree()
    planned['nodes'].append({'model_id':'c'})
    planned['edges'].append({'edge_id':'root-c','from':'root','to':'c','relation':'parent_child'})
    report=run_model_mesh(planned)
    assert report.status is GuardStatus.GAP
    assert report.tree==['root PASS (tree GAP)','  a PASS -> continues b PASS','  b PASS','  c GAP planned']
    child=continued_tree()
    child['nodes'][2]['contract']['claim']['asserts'][0]['value']=False
    report=run_model_mesh(child)
    assert report.tree[0]=='root PASS (tree FAIL)' and report.tree[2]=='  b FAIL'


def test_mesh_variant_must_fail_with_its_code():
    from copy import deepcopy
    data=continued_tree()
    data['variants']=[{'id':'lost-light','expect':'FAIL','code':'MESH_HANDOFF_STATE_MISMATCH','remove':['nodes[a].contract.inputs.events[a].initiates']}]
    before=deepcopy(data);report=run_model_mesh(data)
    assert report.status is GuardStatus.PASS
    assert report.checked['variants']==1 and report.variants[0]['caught']
    assert data==before
    data['edges']=[e for e in data['edges'] if e['relation']!='continues']
    report=run_model_mesh(data)
    assert report.status is GuardStatus.GAP
    assert not report.variants[0]['caught']
    assert any(row['code']=='VARIANT_NOT_CAUGHT' for row in report.to_dict()['gaps'])
