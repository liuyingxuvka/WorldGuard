"""Original documents, not the AI transcription, decide sourced reading results."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from worldguard.cli import main
from worldguard.contracts import GuardContract
from worldguard.kernel import run_worldguard
from worldguard.mesh import ModelMeshContract, run_model_mesh


def world(text='At 08:30 Anna opens the door.', *, actor='Anna', at='08:30', pointer='ch p1'):
    return {
        'contract_id': 'original-reading',
        'claim': {'claim_id': 'open', 'text': 'the door opens', 'requested_semantics': ['event'],
                  'asserts': [{'holds': 'open', 'at': at[:11] + '09:00' if 'T' in at else '09:00'}]},
        'world_model': {'model_id': 'room', 'model_version': '1', 'relations': {}},
        'inputs': {'events': [{'event_id': 'open', 'at': at, 'actor': actor,
                              'actor_state_free': 'the event requires no prior personal state',
                              'source': pointer, 'initiates': ['open'] }],
                   'event_model': {'initial_states': [], 'required_fluents': ['open']}},
        'texts': {'ch': 'chapter.md'},
    }


def check(tmp_path, text, **kwargs):
    (tmp_path / 'chapter.md').write_text(text, encoding='utf-8')
    contract = GuardContract.from_dict(world(**kwargs), base_dir=tmp_path)
    return run_worldguard(contract)


def test_original_time_and_unquoted_paragraphs_are_exposed(tmp_path):
    report = check(tmp_path, 'At 08:20 Anna opens the door.\n\nAt 08:25 she closes it.')
    assert 'SOURCE_TIME_DISAGREES' in {g['code'] for g in report.gaps}
    assert any(value.startswith('TEXT_UNCITED ch p2:') for value in report.scope_limits)
    assert report.checked['source_readings'][0]['edits'] == {'at': '8:20'}
    assert report.checked['source_digests'] == [{'path': 'chapter.md', 'sha256': hashlib.sha256(
        (tmp_path / 'chapter.md').read_bytes()).hexdigest()}]


def test_d3_quote_typography_and_soft_hyphens_and_name_boundaries(tmp_path):
    report = check(tmp_path, 'At 08:30 Anna opens the archi\u00adve—door.',
                   pointer='ch p1 "Anna opens the archive-door"')
    assert not any(g['code'].startswith('SOURCE_') for g in report.gaps)
    report = check(tmp_path, 'At 08:30 Hanna opens the door.')
    # Hanna is a known other person; substring Anna cannot license the actor.
    data = world()
    data['world_model']['relations'] = {'h': {'at': ['Hanna', 'hall']}}
    report = run_worldguard(GuardContract.from_dict(data, base_dir=tmp_path))
    assert 'SOURCE_ACTOR_DISAGREES' in {g['code'] for g in report.gaps}


def test_d4_line_break_collapsing_keeps_grouped_numbers(tmp_path):
    report = check(tmp_path, 'At 08:30 Anna\n opens the 7\u202f500 kg door.',
                   pointer='ch p1 "Anna opens the 7 500 kg door"')
    assert '7\u202f500' in report.checked['source_readings'][0]['span']
    assert not any(g['code'] == 'SOURCE_QUOTE_NOT_IN_TEXT' for g in report.gaps)


def test_d11_another_participant_before_actor_is_grey(tmp_path):
    data = world()
    data['inputs']['events'][0]['with'] = ['Berta']
    (tmp_path / 'chapter.md').write_text('At 08:30 Berta watches Anna open the door.')
    report = run_worldguard(GuardContract.from_dict(data, base_dir=tmp_path))
    reading = report.checked['source_readings'][0]
    assert not reading['sourced']
    assert any(field == 'actor' and colour == '.' for field, colour, _ in reading['readings'])
    assert not any(g['code'] == 'SOURCE_ACTOR_DISAGREES' for g in report.gaps)


def test_d12_abbreviated_date_and_titles_keep_sentence_date_context(tmp_path):
    report = check(tmp_path, 'On Oct. 6, 2026 Dr. Anna opens the door at 08:30 a.m.',
                   at='2026-10-06T08:30')
    assert not any(g['code'].startswith('SOURCE_') for g in report.gaps)
    assert report.checked['source_readings'][0]['sourced']


def test_invalid_pointer_and_quote_have_named_failures(tmp_path):
    report = check(tmp_path, 'At 08:30 Anna opens the door.', pointer='ch p7')
    assert 'SOURCE_SPAN_MISSING' in {g['code'] for g in report.gaps}
    report = check(tmp_path, 'At 08:30 Anna opens the door.', pointer='ch p1 "a different passage"')
    assert 'SOURCE_QUOTE_NOT_IN_TEXT' in {g['code'] for g in report.gaps}


def test_cli_binds_paths_to_contract_folder_and_includes_text_digest(tmp_path, capsys):
    (tmp_path / 'chapter.md').write_text('At 08:30 Anna opens the door.')
    target = tmp_path / 'world.json'
    target.write_text(json.dumps(world()))
    assert main(['check', '--contract', str(target), '--json']) == 0
    payload = json.loads(capsys.readouterr().out)
    assert {row['path'] for row in payload['input_digests']} == {'world.json', 'chapter.md'}


def test_mesh_level_texts_reach_native_nodes(tmp_path):
    (tmp_path / 'chapter.md').write_text('At 08:20 Anna opens the door.')
    data = world()
    data.pop('texts')
    mesh = ModelMeshContract.from_dict({'mesh_id': 'm', 'texts': {'ch': 'chapter.md'},
        'nodes': [{'model_id': 'room', 'contract': data}], 'edges': []}, base_dir=tmp_path)
    report = run_model_mesh(mesh, base_dir=tmp_path)
    assert 'SOURCE_TIME_DISAGREES' in {g['code'] for g in report.to_dict()['gaps']}
