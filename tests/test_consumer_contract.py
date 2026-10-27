"""The WorldGuard surface used by LogicWriting; small native contracts only."""
import ast
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'tests/fixtures/consumers'


@pytest.fixture(scope='module')
def installed(tmp_path_factory):
    target = tmp_path_factory.mktemp('consumer-skills')
    subprocess.run([sys.executable, str(ROOT / 'scripts/install_skill.py'), '--target', str(target)], check=True, capture_output=True)
    return target / 'worldguard'


def run(installed, *args):
    return subprocess.run([sys.executable, str(installed / 'scripts/run_worldguard.py'), *map(str, args)],
                          cwd=installed, text=True, capture_output=True)


def test_installed_layout_and_launcher(installed):
    # LogicWriting scripts/provider_preflight.py:_worldguard_preflight.
    assert re.search(r'^name: worldguard$', (installed / 'SKILL.md').read_text(), re.M)
    # LogicWriting scripts/provider_preflight.py requires these runtime files.
    assert all((installed / name).is_file() for name in ('scripts/run_worldguard.py', 'runtime/worldguard/__init__.py', 'runtime/worldguard/cli.py'))
    launcher = ast.parse((installed / 'scripts/run_worldguard.py').read_text())
    # LogicWriting scripts/provider_preflight.py pins the runtime root and insertion ASTs.
    for expected in ('RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "runtime"', 'sys.path.insert(0, str(RUNTIME_ROOT))'):
        assert ast.dump(ast.parse(expected).body[0]) in {ast.dump(node) for node in ast.walk(launcher)}
    version = ast.parse((installed / 'runtime/worldguard/__init__.py').read_text())
    values = [node.value.value for node in version.body if isinstance(node, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id == '__version__' for target in node.targets)]
    # LogicWriting scripts/provider_preflight.py accepts exactly one stable literal version.
    assert len(values) == 1 and re.fullmatch(r'[0-9]+(?:\.[0-9]+){2}', values[0])


def test_cli_help_is_the_consumer_interface(installed):
    # LogicWriting references/worldguard-contracts.md and provider preflight.
    check = run(installed, 'check', '--help')
    assert check.returncode == 0 and all(flag in check.stdout for flag in ('--contract', '--example'))
    # LogicWriting references/worldguard-contracts.md exposes both timeline inputs.
    timeline = run(installed, 'timeline', '--help')
    assert timeline.returncode == 0 and all(flag in timeline.stdout for flag in ('--contract', '--mesh'))


def test_contract_summary_and_failures(installed):
    good = run(installed, 'check', '--contract', FIXTURES / 'logicwriting_fiction_world.yaml')
    payload = json.loads(good.stdout)
    # LogicWriting scripts/_common.py:read_worldguard_report and worldguard_report_identity_problems.
    assert good.returncode == 0 and payload['status'] == 'PASS' and payload['contract_id'] == 'scene-last-tide-001'
    # LogicWriting scripts/_common.py reads the compact producer contract.
    assert set(payload) == {'checked', 'contract_id', 'gaps', 'output', 'scope_limits', 'status'}
    late = run(installed, 'check', '--contract', FIXTURES / 'logicwriting_world_late.yaml')
    # LogicWriting references/worldguard-contracts.md names these native codes.
    assert late.returncode == 1 and {row['code'] for row in json.loads(late.stdout)['gaps']} == {'EVENT_PRECONDITION_UNMET', 'CLAIM_ASSERTION_FALSE'}


def test_contract_identity_and_missing_binding(installed, tmp_path):
    data = yaml.safe_load((FIXTURES / 'logicwriting_fiction_world.yaml').read_text())
    data.pop('contract_id')
    target = tmp_path / 'world.yaml'
    target.write_text(yaml.safe_dump(data))
    result = run(installed, 'check', '--contract', target)
    # LogicWriting scripts/_common.py:worldguard_report_identity_problems uses the claim fallback.
    assert result.returncode == 0 and json.loads(result.stdout)['contract_id'] == data['claim']['claim_id']
    data['claim'].pop('asserts')
    target.write_text(yaml.safe_dump(data))
    result = run(installed, 'check', '--contract', target)
    # LogicWriting scripts/world_refs.py requires a bound claim, not merely an id.
    assert result.returncode == 1 and json.loads(result.stdout)['status'] == 'GAP'
    assert 'CLAIM_NOT_BOUND' in {row['code'] for row in json.loads(result.stdout)['gaps']}


def test_duplicate_event_identity_and_unreadable_file(installed, tmp_path):
    data = yaml.safe_load((FIXTURES / 'logicwriting_fiction_world.yaml').read_text())
    data['inputs']['events'][1]['event_id'] = data['inputs']['events'][0]['event_id']
    target = tmp_path / 'duplicate.yaml'
    target.write_text(yaml.safe_dump(data))
    # LogicWriting scripts/world_refs.py uses event_id as an identity.
    assert run(installed, 'check', '--contract', target).returncode == 2
    # LogicWriting references/worldguard-contracts.md distinguishes unreadable input (2).
    assert run(installed, 'check', '--contract', tmp_path / 'missing.yaml').returncode == 2


def test_consumer_reference_pages(installed):
    # LogicWriting references/worldguard-contracts.md links both native references.
    assert all((installed / 'references' / name).is_file() for name in ('worldguard-contracts.md', 'guard-inputs.md'))
