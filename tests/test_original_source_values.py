"""Read tables and values from documents through the same native source boundary."""
from copy import deepcopy
from pathlib import Path

from worldguard.contracts import GuardContract
from worldguard.io import load_mapping
from worldguard.kernel import run_worldguard
from worldguard.mesh import ModelMeshContract, run_model_mesh
from worldguard.source_readings import read_value

SEEDS = Path(__file__).parent / 'fixtures' / 'original_sources' / 'batch3'


def original_seed(name):
    root = SEEDS / name
    meta = load_mapping(root / 'seed.yaml')
    data = {**load_mapping(root / meta['world']), **load_mapping(root / 'sources.yaml')}
    if meta['mode'] == 'mesh':
        return run_model_mesh(ModelMeshContract.from_dict(data, base_dir=root), base_dir=root)
    return run_worldguard(GuardContract.from_dict(data, base_dir=root))


def test_d5_merged_headers_and_d6_wrong_column_hint():
    report = original_seed('x14_tide_wrong_column')
    time_notes = [note for reading in report.checked['source_readings']
                  for field, colour, note in reading['readings'] if field == 'time' and colour == 'R']
    assert time_notes
    assert any('this row' in note and 'lw.time' in note for note in time_notes)


def test_d7_numeric_source_paths_and_speed_conversion():
    report = original_seed('x02_kmh_typed_as_ms')
    speed = next(row for row in report.checked['source_values'] if row['name'] == 'speed')
    assert speed['edits_lo'] == [(None, 'inputs.causal_model.scenarios.patrol.speed_ms', 7.5)]
    assert any(field == 'value' and colour == 'R' for field, colour, _ in speed['readings'])
    distance = next(row for row in report.checked['source_values'] if row['name'] == 'distance')
    assert distance['sourced']


def test_d8_duration_and_range_preserve_text_world_edits():
    duration = original_seed('x06_compound_duration')
    row = duration.checked['source_values'][0]
    assert row['edits_lo'][0][2] == 1.333333
    ranged = original_seed('x07_range_between_minutes')
    row = ranged.checked['source_values'][0]
    assert row['range']
    assert row['edits_lo'][0][2] == .583333
    assert row['edits_hi'][0][2] == .75


def test_d9_decimal_convention_and_narrow_grouping_controls():
    for name in ('c02_nbsp_thousands', 'c03_decimal_comma_evident'):
        report = original_seed(name)
        assert all(row['sourced'] for row in report.checked['source_values'])
        assert not any(gap['code'].startswith('SOURCE_') for gap in report.gaps)


def test_d10_lower_case_room_codes_and_equivalent_v_prefix():
    mistake = original_seed('x09_lowercase_room_code')
    assert any(field == 'place' and colour == 'R' for row in mistake.checked['source_readings']
               for field, colour, _ in row['readings'])
    control = original_seed('c04_v_prefixed_version')
    assert not any(gap['code'].startswith('SOURCE_') for gap in control.gaps)


def test_unavailable_unit_owner_is_grey_without_guessing(monkeypatch, tmp_path):
    import worldguard.source_readings as readings
    from worldguard.source_readings import Text
    (tmp_path / 'note.md').write_text('The journey takes 7 furlongs.')
    text = Text('n', tmp_path / 'note.md')
    monkeypatch.setattr(readings, 'unit_info', lambda _: None)
    row = read_value('distance', {'paths': ['n'], 'source': 'n p1', 'unit': 'm'},
                     {None: {'n': 7}}, {'n': text}, {})
    assert not row['sourced']
    assert row['edits_lo'] == row['edits_hi'] == []
    assert any(field == 'unit' and colour == '.' for field, colour, _ in row['readings'])


def test_explicit_count_unit_compares_noun_suffix_without_converting_it(tmp_path):
    from worldguard.source_readings import Text
    (tmp_path / 'note.md').write_text('The vehicle has nine seats besides the driver.')
    row = read_value('capacity', {'paths': ['n'], 'source': 'n p1', 'unit': '1'},
                     {None: {'n': 10}}, {'n': Text('n', tmp_path / 'note.md')}, {})
    assert any(field == 'value' and colour == 'R' for field, colour, _ in row['readings'])
    assert row['edits_lo'] == [(None, 'n', 9)]


def test_unknown_physical_unit_in_source_stays_grey(tmp_path):
    from worldguard.source_readings import Text
    (tmp_path / 'note.md').write_text('The path is 7 furlongs long.')
    row = read_value('distance', {'paths': ['n'], 'source': 'n p1', 'unit': 'm'},
                     {None: {'n': 7}}, {'n': Text('n', tmp_path / 'note.md')}, {})
    assert not row['sourced']
    assert row['edits_lo'] == []
    assert any(colour == '.' for _, colour, _ in row['readings'])


def test_source_offset_unit_is_not_silently_treated_as_a_scale_only(tmp_path):
    from worldguard.source_readings import Text
    (tmp_path / 'note.md').write_text('The sensor reads 7 degC.')
    row = read_value('temperature', {'paths': ['n'], 'source': 'n p1', 'unit': 'K'},
                     {None: {'n': 7}}, {'n': Text('n', tmp_path / 'note.md')}, {})
    assert not row['sourced']
    assert row['edits_lo'] == []
    assert any(colour == '.' for _, colour, _ in row['readings'])


def test_nested_node_contract_resolves_own_sources_and_shared_mesh_sources(tmp_path):
    from tests.test_original_sources import world
    import json
    folder = tmp_path / 'chapter'
    folder.mkdir()
    data = world()
    data['texts'] = {'ch': 'local.md'}
    (folder / 'local.md').write_text('At 08:30 Anna opens the door.')
    (folder / 'world.json').write_text(json.dumps(data))
    (tmp_path / 'other.md').write_text('Unrelated notes.')
    mesh = ModelMeshContract.from_dict({'mesh_id': 'm', 'texts': {'shared': 'other.md'},
        'nodes': [{'model_id': 'n', 'contract': 'chapter/world.json'}]}, base_dir=tmp_path)
    report = run_model_mesh(mesh)
    digests = report.node_reports['n'].checked['source_digests']
    assert {row['path'] for row in digests} == {'chapter/local.md', 'other.md'}
    assert report.node_reports['n'].checked['source_readings'][0]['sourced']


def test_mesh_local_sources_and_parent_dependencies_use_manifest_folder(tmp_path):
    from tests.test_original_sources import world
    import hashlib
    import json
    folder = tmp_path / 'chapter'
    folder.mkdir()
    data = world()
    data['texts'] = {'ch': 'local.md'}
    raw = b'At 08:30 Anna opens the door.'
    (folder / 'local.md').write_bytes(raw)
    (folder / 'world.json').write_text(json.dumps(data))
    root = {'claim': {'claim_id': 'parent', 'asserts': [{'node': 'n', 'holds': 'open', 'at': '09:00'}]}}
    mesh = ModelMeshContract.from_dict({'mesh_id': 'local', 'nodes': [
        {'model_id': 'root', 'contract': root}, {'model_id': 'n', 'contract': 'chapter/world.json'}],
        'edges': [{'edge_id': 'next', 'from': 'root', 'to': 'n', 'relation': 'parent_child'}]}, base_dir=tmp_path)
    report = run_model_mesh(mesh)
    expected = [{'path': 'chapter/local.md', 'sha256': hashlib.sha256(raw).hexdigest()}]
    for name in ('root', 'n'):
        status = report.node_reports[name].checked['source_statuses'][0]
        assert status['colour'] == 'green'
        assert status['sources'] == expected


def test_signed_original_value_is_not_mistaken_for_its_positive_transcription(tmp_path):
    from worldguard.source_readings import Text
    (tmp_path / 'note.md').write_text('The transfer is -3 kg.')
    spec = {'paths': ['n'], 'source': 'n p1', 'unit': 'kg'}
    text = {'n': Text('n', tmp_path / 'note.md')}
    mistake = read_value('transfer', spec, {None: {'n': 3}}, text, {})
    assert not mistake['sourced']
    assert any(field == 'value' and colour == 'R' for field, colour, _ in mistake['readings'])
    assert mistake['edits_lo'] == [(None, 'n', -3)]
    faithful = read_value('transfer', spec, {None: {'n': -3}}, text, {})
    assert faithful['sourced']
    assert not any(colour == 'R' for _, colour, _ in faithful['readings'])
