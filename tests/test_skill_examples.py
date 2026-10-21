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
            assert report.structural_status.value == "PASS", (guard, report.gaps)
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
