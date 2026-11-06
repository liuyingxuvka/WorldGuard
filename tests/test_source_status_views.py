"""The native reports and views expose sourced status without inventing another decision owner."""
import hashlib
import json
from pathlib import Path

from worldguard.cli import main
from worldguard.contracts import GuardContract
from worldguard.io import load_mapping
from worldguard.kernel import run_worldguard
from worldguard.mesh import ModelMeshContract, run_model_mesh
from worldguard.timeline import timeline, render_timeline_text
from tests.test_original_seed_regression import load_seed, run_seed

FIXTURES = Path(__file__).parent / 'fixtures/original_sources'


def test_timeline_says_when_claim_passes_on_ai_transcription_only():
    folder = FIXTURES / 'batch3/x12_value_without_pointer'
    mode, data, _ = load_seed(folder)
    report = run_seed(mode, data, folder)
    contract = GuardContract.from_dict(data, base_dir=folder)
    view = timeline(contract, report=report)
    assert any(row.get('source_status', {}).get('colour') == 'grey' for row in view['claims'])
    assert '[passes on AI transcription only]' in render_timeline_text(view)


def test_source_status_digest_has_a_recomputable_original_file_bundle():
    folder = FIXTURES / 'batch3/c04_v_prefixed_version'
    mode, data, _ = load_seed(folder)
    report = run_seed(mode, data, folder)
    for row in report.checked['source_statuses']:
        sources = row['sources']
        payload = json.dumps(sources, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        assert row['source_digest'] == hashlib.sha256(payload).hexdigest()
        for source in sources:
            assert source['sha256'] == hashlib.sha256((folder / source['path']).read_bytes()).hexdigest()


def test_mesh_tree_exposes_grey_source_status(tmp_path):
    folder = FIXTURES / 'batch3/x12_value_without_pointer'
    _, data, _ = load_seed(folder)
    mesh = ModelMeshContract.from_dict({'mesh_id': 'grey', 'nodes': [{'model_id': 'n', 'contract': data}]}, base_dir=folder)
    report = run_model_mesh(mesh, base_dir=folder)
    assert any('[passes on AI transcription only]' in row for row in report.tree)


def test_timeline_cli_finds_sources_relative_to_world_file(tmp_path, capsys):
    from tests.test_original_sources import world
    (tmp_path / 'chapter.md').write_text('At 08:30 Anna opens the door.')
    target = tmp_path / 'world.json'
    target.write_text(json.dumps(world()))
    assert main(['timeline', '--contract', str(target), '--json']) == 0
    output = json.loads(capsys.readouterr().out)
    assert output['claims'][0]['source_status']['colour'] == 'green'


def test_default_summary_preserves_source_decisions_and_real_red_counterexample(tmp_path, capsys):
    from tests.test_original_sources import world
    (tmp_path / 'chapter.md').write_text('At 08:20 Anna opens the door.')
    target = tmp_path / 'world.json'
    target.write_text(json.dumps(world()))
    assert main(['check', '--contract', str(target)]) == 1
    compact_text = capsys.readouterr().out
    compact = json.loads(compact_text)
    assert main(['check', '--contract', str(target), '--json']) == 1
    full_text = capsys.readouterr().out
    full = json.loads(full_text)
    assert compact['status'] == full['status'] == 'FAIL'
    assert compact['checked']['source_statuses'] == full['checked']['source_statuses']
    assert compact['checked']['source_digests'] == full['checked']['source_digests']
    assert compact['checked']['source_checks'] == {'events': 1, 'values': 0, 'verified_readings': 0}
    assert 'source_readings' not in compact['checked']
    assert full['checked']['source_readings'][0]['span'] == 'At 08:20 Anna opens the door.'
    actual = next(gap for gap in compact['gaps'] if gap['code'] == 'SOURCE_TIME_DISAGREES')
    assert '8:20' in actual['message'] and '08:30' in actual['message'] and actual['source'] == 'ch p1'
    assert compact['output'] == 'summary only; add --json for the full report'
    assert len(compact_text.encode()) < len(full_text.encode())
