from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_semantic_rollout_runner_uses_the_current_model_input() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / ".flowguard" / "run_semantic_rollout_checks.py")],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["runtime"]["structural_status"] == "PASS"
    assert payload["runtime"]["semantic_status"] != "PASS"
