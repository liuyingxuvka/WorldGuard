from __future__ import annotations

import json
import subprocess
import sys


def test_python_module_cli_help_runs():
    completed = subprocess.run(
        [sys.executable, "-m", "worldguard", "--help"],
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "mesh-check" in completed.stdout
    assert "check" in completed.stdout


def test_minimal_contract_runs_and_bad_input_is_a_json_error(tmp_path):
    minimal = tmp_path / "minimal.yaml"
    minimal.write_text('claim: {claim_id: c1, requested_semantics: [resource]}\ninputs:\n  resources:\n    places: {a: [{color: t, qty: 1}], b: []}\n    transitions:\n      - {id: move, consumes: [{place: a, color: t, qty: 1}], produces: [{place: b, color: t, qty: 1}]}\n', encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-m", "worldguard", "check", "--contract", str(minimal)],
        text=True, capture_output=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "PASS"
    bad = tmp_path / "bad.yaml"
    bad.write_text("claim: {claim_id: c1}\n", encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, "-m", "worldguard", "check", "--contract", str(bad)],
        text=True, capture_output=True,
    )
    assert completed.returncode == 2
    assert json.loads(completed.stdout)["error"]["code"] == "WORLDGUARD_INPUT_INVALID"
