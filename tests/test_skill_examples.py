import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from tests.helpers import make_contract
from worldguard.kernel import run_worldguard

SKILL = Path(__file__).resolve().parents[1] / "skills" / "worldguard"
GUARDS = ["EventGuard", "AgentGuard", "SpaceGuard", "ResourceGuard", "CausalGuard", "ConflictGuard", "NormGuard"]
FALSE_ROWS = {  # one claim assertion per Guard that the reference world contradicts
    "EventGuard": {"holds": "iris_inside", "at": "t1"},
    "AgentGuard": {"agent": "Mara", "intends": "steal_map"},
    "SpaceGuard": {"relation": "DC", "x": "key", "y": "box", "at": "t1"},
    "ResourceGuard": {"place": "on_ferry", "color": "traveler", "qty": 2},
    "CausalGuard": {"variable": "slack_h", "op": "<", "value": 0},
    "ConflictGuard": {"player": "a", "state": "s", "reward": 5},
    "NormGuard": {"actor": "pilot", "action": "leave_harbor", "modality": "forbidden"},
}

UNRESOLVED_ROWS = {
    "EventGuard": [{"holds": "absent_fluent", "at": "t1"}, {"event": "absent_event", "before": "e_unlock"}],
    "AgentGuard": [{"agent": "absent_agent", "intends": "unlock_door"}],
    "SpaceGuard": [{"relation": "NTPP", "x": "absent_object", "y": "box", "at": "t1"}],
    "ResourceGuard": [{"place": "absent_place", "qty": 1}],
    "CausalGuard": [{"variable": "absent_variable", "value": 1}],
    "ConflictGuard": [{"player": "absent_player", "state": "s", "reward": 1}],
    "NormGuard": [{"actor": "absent_actor", "action": "leave_harbor", "modality": "permitted"}],
}

@pytest.mark.parametrize("name", ["scene_locked_door.yaml", "trip_ferry.yaml"])
def test_skill_example_worlds_pass_through_the_portable_launcher(name: str) -> None:
    done = subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "run_worldguard.py"), "check", "--contract", str(SKILL / "assets" / "examples" / name)],
        text=True,
        capture_output=True,
    )
    assert done.returncode == 0, done.stdout[-500:]
    assert json.loads(done.stdout)["status"] == "PASS"


def test_every_guard_input_block_in_the_reference_passes() -> None:
    text = (SKILL / "references" / "guard-inputs.md").read_text(encoding="utf-8")
    blocks = re.findall(r"^## (\w+Guard)\n\n```yaml\n(.*?)```\n\nClaim assertion: `(\{.*?\})`", text, flags=re.S | re.M)
    assert [guard for guard, _, _ in blocks] == GUARDS
    for guard, block, row in blocks:
        report = run_worldguard(make_contract(guard, inputs=yaml.safe_load(block), asserts=[yaml.safe_load(row)]))
        assert report.status.value == "PASS", (guard, report.gaps)
        report = run_worldguard(make_contract(guard, inputs=yaml.safe_load(block), asserts=[FALSE_ROWS[guard]]))
        assert report.status.value == "FAIL", guard
        assert [gap["code"] for gap in report.gaps] == ["CLAIM_ASSERTION_FALSE"], guard
        for unresolved in UNRESOLVED_ROWS[guard]:
            report = run_worldguard(make_contract(guard, inputs=yaml.safe_load(block), asserts=[unresolved]))
            assert all(result.status.value == "PASS" for result in report.guard_results), (guard, report.gaps)
            assert report.status.value == "GAP", (guard, report.gaps)
            assert [gap["code"] for gap in report.gaps] == ["CLAIM_ASSERTION_UNRESOLVED"], guard


def test_repository_mesh_example_passes() -> None:
    mesh = SKILL.parents[1] / "examples" / "model_mesh" / "basic_mesh.yaml"
    done = subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "run_worldguard.py"), "mesh-check", "--mesh", str(mesh)],
        text=True,
        capture_output=True,
    )
    assert done.returncode == 0, done.stdout[-500:]
    assert json.loads(done.stdout)["status"] == "PASS"


def test_installed_skill_runs_trip_example_without_repository_layout(tmp_path):
    target = tmp_path / 'skills'
    install = subprocess.run([sys.executable, str(SKILL.parents[1] / 'scripts/install_skill.py'), '--target', str(target)],
                             text=True, capture_output=True)
    assert install.returncode == 0, install.stdout + install.stderr
    done = subprocess.run([sys.executable, str(target / 'worldguard/scripts/run_worldguard.py'), 'check', '--example', 'trip'],
                          cwd=tmp_path, text=True, capture_output=True)
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)['status'] == 'PASS'


def test_contract_reference_world_variants_compare_and_timeline_are_runnable(tmp_path, capsys):
    from worldguard.cli import main
    text = (SKILL / 'references/worldguard-contracts.md').read_text()
    raw = re.search(r'## Runnable world.*?```yaml\n(.*?)```', text, re.S).group(1)
    observed = re.search(r'## Compare the world.*?```yaml\n(.*?)```', text, re.S).group(1)
    world, observation = tmp_path / 'world.yaml', tmp_path / 'observed.yaml'
    world.write_text(raw)
    observation.write_text(observed)
    assert main(['check', '--contract', str(world)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'PASS' and report['checked']['variants'] == 1
    assert main(['timeline', '--contract', str(world)]) == 0
    assert len(json.loads(capsys.readouterr().out)['steps']) == 4
    assert main(['compare', '--contract', str(world), '--observed', str(observation)]) == 1
    assert len(json.loads(capsys.readouterr().out)['mismatches']) == 2


def test_mesh_reference_with_contract_files_is_runnable(tmp_path, capsys):
    from worldguard.cli import main
    text = (SKILL / 'references/model-mesh.md').read_text()
    blocks = re.findall(r'```yaml\n(.*?)```', text, re.S)
    assert len(blocks) == 3
    for name, body in zip(('mesh.yaml', 'part1.yaml', 'part2.yaml'), blocks):
        (tmp_path / name).write_text(body)
    assert main(['mesh-check', '--mesh', str(tmp_path / 'mesh.yaml')]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'PASS'
