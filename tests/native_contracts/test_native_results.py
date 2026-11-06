"""Actual native results over the retained finite inputs, without abstract State replay."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import runpy
import shutil
import tempfile

from .expected import (REQUESTS, INPUT_RESULTS, EVENTS_RESULTS, CONSISTENCY_RESULTS,
                       COMPARE_RESULTS, CHECK_RESULTS, MESH_CASES, MESH_RESULTS)
from .world_cases import replay, stage_values, witness_assertions

ROOT = Path(__file__).resolve().parents[2]


def test_world_consistency_native_cases():
    CASES = tuple(REQUESTS[name] for name in CONSISTENCY_RESULTS)
    mismatches = []
    checked = 0
    for request in CASES:
        code, report = replay(request)
        expected = CONSISTENCY_RESULTS[request.case_id]
        actual = stage_values(request, code, report)[2]
        if actual != expected:
            mismatches.append(f'{request.case_id}: stage {expected!r}, native {actual!r}')
        checked += 1
    assert not mismatches, mismatches


def test_world_events_native_cases():
    CASES = tuple(REQUESTS[name] for name in EVENTS_RESULTS)
    mismatches = []
    checked = 0
    for request in CASES:
        if request.case_id == 'illegal_event_effect':
            import tempfile, io, json
            from pathlib import Path
            from contextlib import redirect_stdout
            from worldguard.cli import main
            contract = {'claim': {'claim_id': 'illegal-effect', 'asserts': [{'holds': 'F', 'at': 't2'}]}, 'inputs': {'events': [{'event_id': 'illegal', 'at': 't1', 'requires': 'missing', 'initiates': 'F'}]}}
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'world.json'
                path.write_text(json.dumps(contract))
                output = io.StringIO()
                with redirect_stdout(output):
                    code = main(['check', '--contract', str(path), '--json'])
                report = json.loads(output.getvalue())
            if report['claim_binding']['assertions'][0]['status'] != 'FAIL' or not any((row['code'] == 'CLAIM_ASSERTION_FALSE' and row.get('claim_row') == 0 for row in report.get('gaps', []))):
                mismatches.append('illegal_event_has_no_effect: the illegal initiation still satisfies the later assertion')
        else:
            code, report = replay(request)
        expected = EVENTS_RESULTS[request.case_id]
        actual = stage_values(request, code, report)[1]
        if actual != expected:
            mismatches.append(f'{request.case_id}: stage {expected!r}, native {actual!r}')
        from .world_cases import witness_assertions
        witness_assertions(request, report.get('gaps', []))
        if report['status'] != expected:
            mismatches.append(f'{request.case_id}: native status differs from the event contribution')
        checked += 1
    assert not mismatches, mismatches


def test_world_input_native_cases():
    CASES = tuple(REQUESTS[name] for name in INPUT_RESULTS)
    mismatches = []
    checked = 0
    for request in CASES:
        code, report = replay(request)
        expected = INPUT_RESULTS[request.case_id]
        actual = stage_values(request, code, report)[0]
        if actual != expected:
            mismatches.append(f'{request.case_id}: stage {expected!r}, native {actual!r}')
        if (code == 2) != (expected == 'error'):
            mismatches.append(f'{request.case_id}: typed input exit disagrees')
        checked += 1
    import hashlib, json, tempfile, io
    from pathlib import Path
    from contextlib import redirect_stdout
    from worldguard.cli import main
    from .world_cases import _real_contract
    with tempfile.TemporaryDirectory(prefix='check-inputs-') as directory:
        path = Path(directory) / 'world.json'
        path.write_text(json.dumps(_real_contract(CASES[0])))
        output = io.StringIO()
        with redirect_stdout(output):
            main(['check', '--contract', str(path)])
        report = json.loads(output.getvalue())
        expected = [{'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}]
        if report.get('input_digests') != expected:
            mismatches.append('summary_names_its_inputs: missing or incorrect raw input digest')
        root = Path(directory)
        node = root / 'nodes/world.json'
        node.parent.mkdir()
        contract = _real_contract(CASES[0])
        node.write_text(json.dumps(contract) + '\n')
        mesh = root / 'mesh.json'
        mesh.write_text(json.dumps({'mesh_id': "input-tree", 'nodes': [{'model_id': 'file', 'contract': 'nodes/world.json'}, {'model_id': 'inline', 'contract': contract}], 'edges': [{'edge_id': 'file-inline', 'from': 'file', 'to': 'inline', 'relation': 'parent_child'}]}, indent=2) + '\n')
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(['mesh-check', '--mesh', str(mesh)])
        report = json.loads(output.getvalue())
        expected = [{'path': p.relative_to(root).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in (mesh, node)]
        keys = {'checked', 'gaps', 'input_digests', 'mesh_id', 'output', 'scope_limits', 'status', 'tree'}
        if code != 0 or report.get('mesh_id') != "input-tree" or report.get('input_digests') != expected or (set(report) != keys):
            mismatches.append(f"mesh_summary_names_its_inputs: native mesh id/raw file digests/compact keys differ; actual id={report.get('mesh_id')!r}, digests={report.get('input_digests')!r}, keys={sorted(report)}")
    assert not mismatches, mismatches


def test_world_compare_native_cases():
    CASES = tuple(REQUESTS[name] for name in COMPARE_RESULTS)
    mismatches = []
    checked = 0
    for request in CASES:
        expected = COMPARE_RESULTS[request.case_id]
        for write_copy in (False, True):
            code, report = replay(request, write_observed=write_copy)
            if (code, report['status']) != (0 if expected == 'PASS' else 1, expected):
                mismatches.append(f'{request.case_id}: compare exit/status differs')
        checked += 1
    assert not mismatches, mismatches


def test_world_check_native_cases():
    CASES = tuple(REQUESTS[name] for name in CHECK_RESULTS)
    mismatches = []
    checked = 0
    requests = {q.case_id: q for q in CASES}
    for case, (expected_exit, expected_status, expected_stages) in CHECK_RESULTS.items():
        request = requests[case]
        code, report = replay(request)
        if (code, report['status']) != (expected_exit, expected_status):
            mismatches.append(f'{case}: exit/status differs')
        if stage_values(request, code, report) != expected_stages:
            mismatches.append(f'{case}: coarse received values differ from native contributions')
        gaps = report.get('gaps', [])
        if request.actor_state == 'unchecked':
            actor_rows = [row for row in gaps if row['code'] == 'EVENT_ACTOR_STATE_UNCHECKED']
            if len(actor_rows) != 1 or any((actor_rows[0].get(key) != value for key, value in {'status': 'GAP', 'event_id': 'unlock', 'actor': 'Lena', 'source': 'actor fixture', 'missing': ['place', 'uses']}.items())):
                mismatches.append('actor_state_checked: native gap does not name the event, actor and missing place and uses')
        if request.actor_state == 'free':
            if gaps or 'actor_state_free unlock (Lena): the door opens from either side' not in report['scope_limits']:
                mismatches.append('actor_state_checked: native free exemption omitted its reason or did not pass')
        identities = [(row['code'], row.get('guard'), row.get('claim_row'), row.get('variant_id'), row.get('event_id')) for row in gaps]
        if len(identities) != len(set(identities)):
            mismatches.append(f'{case}: one_row_per_problem failed')
        checked += 1
    assert not mismatches, mismatches


def test_world_timeline_native_cases():
    CASES = (REQUESTS["timeline_late_ferry"],)
    mismatches = []
    checked = 0
    for request in CASES:
        from .world_cases import replay_timeline
        replay_timeline(request)
        from .world_cases import _real_contract
        from worldguard.timeline import timeline, render_timeline_text
        view = timeline(_real_contract(request))
        rows = [line.split('fluents: ', 1)[1].split(' | tokens:', 1)[0] for line in render_timeline_text(view).splitlines() if 'fluents: ' in line]
        if len(rows) != len(view['steps']):
            mismatches.append('timeline_shows_changes_after_start: missing steps')
        else:
            state = set() if rows[0] == '-' else set(rows[0].split(', '))
            for index, (row, step) in enumerate(zip(rows, view['steps'])):
                if index and row != '=':
                    for change in row.split():
                        if change.startswith('+'):
                            state.add(change[1:])
                        elif change.startswith('-'):
                            state.discard(change[1:])
                        else:
                            mismatches.append('timeline_shows_changes_after_start: expected a signed delta')
                if state != set(step['fluents']):
                    mismatches.append('timeline_shows_changes_after_start: text cannot reconstruct native JSON')
        checked += 1
    assert not mismatches, mismatches


def test_skill_install_native_bytes_and_read_only_dry_run():
    import io, tempfile
    from pathlib import Path
    from contextlib import redirect_stdout
    from scripts import install_skill
    mismatches = []
    with tempfile.TemporaryDirectory(prefix='skill-install-model-') as directory:
        target = Path(directory) / 'skills'
        args = ['--target', str(target)]
        output = io.StringIO()
        with redirect_stdout(output):
            code = install_skill.main(args + ['--dry-run'])
        if code != 0 or target.exists():
            mismatches.append('dry run wrote the destination or failed')
        with redirect_stdout(output):
            code = install_skill.main(args)
        if code != 0:
            mismatches.append('install failed')
        with redirect_stdout(output):
            code = install_skill.main(args + ['--check'])
        if code != 0 or install_skill.installed_differences(target / 'worldguard'):
            mismatches.append('fresh installation differs')
        path = target / 'worldguard/SKILL.md'
        original = path.read_bytes()
        path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        output = io.StringIO()
        with redirect_stdout(output):
            code = install_skill.main(args + ['--check'])
        if code != 1 or 'differs: SKILL.md' not in output.getvalue():
            mismatches.append('edited byte not reported by name')
        path.write_bytes(original)
        with redirect_stdout(output):
            code = install_skill.main(args + ['--check'])
        if code != 0:
            mismatches.append('restored installation still differs')
    assert not mismatches, mismatches


def test_mesh_handoff_native_cases():
    from worldguard.cli import main
    small_tree = runpy.run_path(str(ROOT / 'tests/test_model_mesh.py'))['continued_tree']
    mismatches = []
    with tempfile.TemporaryDirectory(prefix='mesh-handoff-replay-') as folder:
        fixtures = shutil.copytree(ROOT / 'tests/fixtures/trials/mesh_continues', Path(folder) / 'mesh_continues')
        for request in MESH_CASES:
            if request.case.endswith('.yaml'):
                path = fixtures / request.case
            else:
                data = small_tree()
                if request.case == 'unrelated':
                    data['edges'] = [row for row in data['edges'] if row['edge_id'] != 'root-b']
                elif request.case == 'child_fail':
                    data['nodes'][2]['contract']['claim']['asserts'][0]['value'] = False
                elif request.case == 'child_gap':
                    data['nodes'][2]['contract']['claim']['asserts'][0]['holds'] = 'unknown_fluent'
                elif request.case == 'child_boundary':
                    data['nodes'][2]['contract']['claim']['requested_semantics'] = ['event', 'numeric_dynamics']
                elif request.planned_node:
                    data['nodes'].append({'model_id': 'c'})
                    data['edges'].append({'edge_id': 'root-c', 'from': 'root', 'to': 'c', 'relation': 'parent_child'})
                elif request.case == 'edge_time_backwards':
                    data['nodes'][2]['contract']['inputs']['events'][0]['at'] = 't0'
                    data['nodes'][2]['contract']['claim']['asserts'][0]['at'] = 't0'
                elif request.case == 'unnamed_fluent':
                    data['nodes'][2]['contract']['inputs']['event_model']['initial_states'] = ['lit', 'tom_on_mainland']
                elif request.has_variant:
                    change = {'nodes[b].contract.inputs.event_model.initial_states': ['dark']} if request.variant_caught else {'nodes[a].contract.claim.claim_id': 'same-world-new-label'}
                    data['variants'] = [{'id': request.case, 'code': 'MESH_HANDOFF_STATE_MISMATCH', 'set': change}]
                else:
                    data['edges'].append({'edge_id': 'back', 'from': 'b', 'to': 'a', 'relation': 'continues'})
                path = Path(folder) / (request.case + '.json')
                path.write_text(json.dumps(data))
            expected_exit, expected_status, expected_codes, expected_segments = MESH_RESULTS[request.case]
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(['mesh-check', '--mesh', str(path), '--json'])
            result = json.loads(output.getvalue())
            if request.case == 'unnamed_fluent':
                note = 'continues a-b: b starts with tom_on_mainland, which a never names'
                if note not in result['scope_limits']:
                    mismatches.append('unnamed_fluent: the new initial-state assumption is absent from scope_limits')
            codes = {row['code'] for row in result.get('gaps', [])}
            if (code, result['status']) != (expected_exit, expected_status) or not set(expected_codes) <= codes:
                mismatches.append(f"{request.case}: expected {expected_status}/{expected_codes}, actual {code}/{result['status']}/{sorted(codes)}")
            lines = result.get('tree', [])
            root_status = lines[0].split()[1] if lines else ''
            if lines and '(tree ' in lines[0]:
                root_status = lines[0].rsplit('(tree ', 1)[1].rstrip(')')
            segments = tuple(((part.split() + [''])[1] for line in lines for part in line.split(' -> continues ')[1:]))
            if request.one_root and root_status != result['status']:
                mismatches.append(f"{request.case}: root line {lines[:1]} does not show {result['status']}")
            if set(expected_segments) - set(segments):
                mismatches.append(f'{request.case}: continues segments {segments} lack {expected_segments}')
            if request.planned_node and (not any((line.split()[1:] == ['GAP', 'planned'] for line in lines))):
                mismatches.append(f'{request.case}: no planned node line in {lines}')
            if request.has_variant:
                variants = result.get('variants', [])
                if result.get('checked', {}).get('variants') != 1 or len(variants) != 1 or variants[0].get('caught') is not request.variant_caught:
                    mismatches.append(f'{request.case}: the native tree variant was not checked with its declared outcome')
    assert not mismatches, mismatches


def test_guard_registry_remains_the_catalogued_seven_guards():
    from tests.guard_catalog import GUARD_MODEL_PURPOSES
    from worldguard.guards import GUARD_RUNNERS
    assert set(GUARD_RUNNERS) == {purpose.guard for purpose in GUARD_MODEL_PURPOSES}


def chapter_codes(state_matches, time_forward):
    """Assemble two real chapter inputs; the production continuation owner decides."""
    from worldguard.mesh import ModelMeshContract, _continues_findings
    before = {'claim': {'requested_semantics': ['event']},
              'inputs': {'event_model': {'initial_states': ['lit']},
                         'events': [{'event_id': 'a', 'at': 1, 'requires': 'lit', 'initiates': 'lit'}]}}
    after = {'claim': {'requested_semantics': ['event']},
             'inputs': {'event_model': {'initial_states': ['lit'] if state_matches else []},
                        'events': [{'event_id': 'b', 'at': 2 if time_forward else 0, 'requires': 'lit'}]}}
    mesh = ModelMeshContract.from_dict({'mesh_id': 'finite-handoff',
        'nodes': [{'model_id': 'a', 'contract': before}, {'model_id': 'b', 'contract': after}],
        'edges': [{'edge_id': 'a-b', 'from': 'a', 'to': 'b', 'relation': 'continues'}]})
    return {finding.code for finding in _continues_findings(
        mesh, mesh.edges[0], mesh.nodes[0].contract, mesh.nodes[1].contract)}


import pytest


@pytest.mark.parametrize('state_matches,time_forward,codes', [
    (True, True, ()),
    (False, True, ('MESH_HANDOFF_STATE_MISMATCH',)),
    (True, False, ('MESH_HANDOFF_TIME_BACKWARDS',)),
    (False, False, ('MESH_HANDOFF_STATE_MISMATCH', 'MESH_HANDOFF_TIME_BACKWARDS')),
])
def test_chapter_handoff_calls_the_native_state_and_time_owner(state_matches, time_forward, codes):
    assert chapter_codes(state_matches, time_forward) == set(codes)


def test_chapter_handoff_recovers_after_bad_inputs_in_the_same_process():
    assert chapter_codes(False, False) == {'MESH_HANDOFF_STATE_MISMATCH', 'MESH_HANDOFF_TIME_BACKWARDS'}
    assert chapter_codes(True, True) == set()


@pytest.mark.parametrize('world', [
    {'inputs': {'events': [{'event_id': 'a', 'at': 'evening'}]}},
    {'inputs': {'events': [{'event_id': 'a', 'at': 1}, {'event_id': 'a', 'at': 2}]}},
    {'schema_version': None, 'inputs': {'events': [{'event_id': 'a', 'at': 1}]}},
])
def test_invalid_input_does_not_execute_later_stages(tmp_path, monkeypatch, capsys, world):
    from worldguard import kernel, qualification
    from worldguard.cli import main
    from worldguard.guards import GUARD_RUNNERS
    called = []

    def later_stage(*args, **kwargs):
        called.append('a later stage was reached')
        raise AssertionError('invalid input reached a later world check stage')

    monkeypatch.setattr(kernel, 'run_worldguard', later_stage)
    monkeypatch.setattr(qualification, 'qualify_guard_contract', later_stage)
    for name in GUARD_RUNNERS:
        monkeypatch.setitem(GUARD_RUNNERS, name, later_stage)
    path = tmp_path / 'invalid.json'
    path.write_text(json.dumps(world), encoding='utf-8')
    assert main(['check', '--contract', str(path), '--json']) == 2
    assert json.loads(capsys.readouterr().out)['error']['code'] == 'WORLDGUARD_INPUT_INVALID'
    assert called == []
