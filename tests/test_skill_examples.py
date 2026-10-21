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
    blocks = re.findall(r"^## (\w+Guard)\n\n```yaml\n(.*?)```", text, flags=re.S | re.M)
    assert [guard for guard, _ in blocks] == GUARDS
    for guard, block in blocks:
        assert run_worldguard(make_contract(guard, inputs=yaml.safe_load(block))).status.value == "PASS", guard
