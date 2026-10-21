from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import yaml
import pytest


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


def test_check_exit_code_follows_the_verdict(tmp_path):
    original = Path(__file__).resolve().parent / "fixtures" / "scene_locked_door.yaml"
    data = yaml.safe_load(original.read_text(encoding="utf-8"))
    transitions = data["inputs"]["resources"]["transitions"]
    data["inputs"]["resources"]["transitions"] = [transitions[0], transitions[2], transitions[1]]
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.safe_dump(data), encoding="utf-8")
    for path, expected in [(original, 0), (broken, 1)]:
        completed = subprocess.run(
            [sys.executable, "-m", "worldguard", "check", "--contract", str(path)],
            text=True, capture_output=True,
        )
        assert completed.returncode == expected, completed.stdout + completed.stderr


def test_check_rejects_null_and_non_mapping_contract_sections(tmp_path):
    base = yaml.safe_load((Path(__file__).parent / "fixtures" / "scene_locked_door.yaml").read_text())
    for name in ("claim", "world_model", "inputs"):
        for value in (None, []):
            path = tmp_path / f"{name}-{type(value).__name__}.json"
            path.write_text(json.dumps({**base, name: value}), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, "-m", "worldguard", "check", "--contract", str(path)],
                text=True, capture_output=True,
            )
            payload = json.loads(completed.stdout)
            assert completed.returncode == 2, completed.stdout + completed.stderr
            assert payload["operation"] == "check"
            assert payload["error"]["code"] == "WORLDGUARD_INPUT_INVALID"
            assert payload["error"]["message"] == f"{name} must be a mapping"
            assert "Traceback" not in completed.stdout + completed.stderr


def test_mesh_check_rejects_bad_container_and_node_shapes_but_keeps_contractless_gap(tmp_path):
    malformed = [
        {"nodes": None}, {"nodes": [42]}, {"nodes": {}},
        {"edges": None}, {"snapshots": [42]},
        {"nodes": [{"model_id": "node", "contract": []}]},
    ]
    for index, values in enumerate(malformed):
        path = tmp_path / f"mesh-{index}.json"
        path.write_text(json.dumps({"mesh_id": "shape-probe", **values}), encoding="utf-8")
        completed = subprocess.run(
            [sys.executable, "-m", "worldguard", "mesh-check", "--mesh", str(path)],
            text=True, capture_output=True,
        )
        payload = json.loads(completed.stdout)
        assert completed.returncode == 2, completed.stdout + completed.stderr
        assert payload["operation"] == "mesh-check"
        assert payload["error"]["code"] == "WORLDGUARD_INPUT_INVALID"
        assert payload["error"]["details"]["error_type"] == "ValueError"
    path = tmp_path / "contractless.json"
    path.write_text(json.dumps({"mesh_id": "contractless", "nodes": [{"model_id": "node", "contract": None}]}))
    completed = subprocess.run(
        [sys.executable, "-m", "worldguard", "mesh-check", "--mesh", str(path)],
        text=True, capture_output=True,
    )
    assert completed.returncode == 1
    assert json.loads(completed.stdout)["status"] == "GAP"


def test_check_does_not_reclassify_an_internal_native_type_error(tmp_path, monkeypatch):
    from worldguard.cli import main
    import worldguard.kernel

    def internal_defect(*args, **kwargs):
        raise TypeError("internal native defect")

    monkeypatch.setattr(worldguard.kernel, "run_worldguard", internal_defect)
    scene = Path(__file__).parent / "fixtures" / "scene_locked_door.yaml"
    with pytest.raises(TypeError, match="internal native defect"):
        main(["check", "--contract", str(scene)])


def test_portable_launcher_runs_from_a_copied_skill(tmp_path):
    skill = tmp_path / "worldguard"
    shutil.copytree(
        Path(__file__).resolve().parents[1] / "skills" / "worldguard",
        skill,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    launcher = skill / "scripts" / "run_worldguard.py"
    done = subprocess.run([sys.executable, str(launcher), "check", "--help"], cwd=tmp_path, text=True, capture_output=True)
    assert done.returncode == 0, done.stderr
    assert "--contract" in done.stdout and "--example" in done.stdout
    example = skill / "assets" / "examples" / "scene_locked_door.yaml"
    done = subprocess.run([sys.executable, str(launcher), "check", "--contract", str(example)], cwd=tmp_path, text=True, capture_output=True)
    assert done.returncode == 0, done.stdout[-500:]
    probe = f"import sys; sys.path.insert(0, {str(skill / 'runtime')!r}); import worldguard.cli as c; print(c.__file__)"
    done = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, text=True, capture_output=True)
    assert Path(done.stdout.strip()).resolve().is_relative_to(skill / "runtime")
