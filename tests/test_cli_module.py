from __future__ import annotations

import json
import os
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
    minimal.write_text('claim: {claim_id: c1, asserts: [{place: b, qty: 1}]}\ninputs:\n  resources:\n    places: {a: [{color: t, qty: 1}], b: []}\n    transitions:\n      - {id: move, consumes: [{place: a, color: t, qty: 1}], produces: [{place: b, color: t, qty: 1}]}\n', encoding="utf-8")
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


def test_repository_launcher_uses_the_repository_package(tmp_path):
    root = Path(__file__).resolve().parents[1]
    launcher = root / "skills" / "worldguard" / "scripts" / "run_worldguard.py"
    done = subprocess.run([sys.executable, str(launcher), "check", "--help"], cwd=tmp_path, text=True, capture_output=True)
    assert done.returncode == 0, done.stderr
    assert "--contract" in done.stdout and "--example" in done.stdout
    probe = f"import runpy; runpy.run_path({str(launcher)!r}); import worldguard; print(worldguard.__file__)"
    done = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, text=True, capture_output=True)
    assert Path(done.stdout.strip()).resolve().is_relative_to(root / "worldguard"), done.stderr


def test_default_output_is_a_summary_and_json_is_full():
    command = [sys.executable, "-m", "worldguard", "check", "--example", "fuel_cell"]
    done = subprocess.run(command, text=True, capture_output=True)
    assert done.returncode == 0, done.stderr
    assert len(done.stdout) < 10000
    summary = json.loads(done.stdout)
    assert summary["claim_statuses"] == ["PASS", "PASS", "FAIL"]
    failing = summary["reports"][2]
    assert {"status", "semantic_status", "gaps", "scope_limits"} <= set(failing)
    assert {row["guard"] for row in failing["non_pass_guards"]} == {"ConflictGuard", "NormGuard"}
    full = subprocess.run([*command, "--json"], text=True, capture_output=True)
    assert "child_results" in json.loads(full.stdout)["reports"][0]


def test_install_skill_copies_the_skill_and_the_launcher_writes_no_bytecode(tmp_path):
    root = Path(__file__).resolve().parents[1]
    target = tmp_path / "skills"
    installer = [sys.executable, str(root / "scripts" / "install_skill.py"), "--target", str(target)]
    done = subprocess.run(installer, text=True, capture_output=True)
    assert done.returncode == 0, done.stderr
    launcher = target / "worldguard" / "scripts" / "run_worldguard.py"
    example = target / "worldguard" / "assets" / "examples" / "trip_ferry.yaml"
    env = {key: value for key, value in os.environ.items() if key != "PYTHONDONTWRITEBYTECODE"}
    done = subprocess.run([sys.executable, str(launcher), "check", "--contract", str(example)], cwd=tmp_path, env=env, text=True, capture_output=True)
    assert done.returncode == 0, done.stdout[-500:]
    probe = f"import runpy; runpy.run_path({str(launcher)!r}); import worldguard; print(worldguard.__file__)"
    done = subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, env=env, text=True, capture_output=True)
    assert Path(done.stdout.strip()).resolve().is_relative_to(target / "worldguard" / "runtime"), done.stderr
    assert not list((target / "worldguard").rglob("__pycache__"))
    check = subprocess.run([*installer, "--check"], text=True, capture_output=True)
    assert check.returncode == 0, check.stdout

    skill_text = target / "worldguard" / "SKILL.md"
    original = skill_text.read_bytes()
    original_stat = skill_text.stat()
    changed = original.replace(b"WorldGuard", b"WorldGuarX", 1)
    assert changed != original and len(changed) == len(original)
    skill_text.write_bytes(changed)
    os.utime(skill_text, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    drift = subprocess.run([*installer, "--check"], text=True, capture_output=True)
    assert drift.returncode == 1
    assert "differs: SKILL.md" in drift.stdout

    skill_text.write_bytes(original)
    os.utime(skill_text, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    check = subprocess.run([*installer, "--check"], text=True, capture_output=True)
    assert check.returncode == 0, check.stdout
    runtime_file = target / "worldguard" / "runtime" / "worldguard" / "io.py"
    runtime_bytes = runtime_file.read_bytes()
    runtime_stat = runtime_file.stat()
    runtime_file.write_bytes(bytes([runtime_bytes[0] ^ 1]) + runtime_bytes[1:])
    os.utime(runtime_file, ns=(runtime_stat.st_atime_ns, runtime_stat.st_mtime_ns))
    check = subprocess.run([*installer, "--check"], text=True, capture_output=True)
    assert check.returncode == 1 and "runtime: differs: io.py" in check.stdout

    runtime_file.write_bytes(runtime_bytes)
    os.utime(runtime_file, ns=(runtime_stat.st_atime_ns, runtime_stat.st_mtime_ns))
    check = subprocess.run([*installer, "--check"], text=True, capture_output=True)
    assert check.returncode == 0, check.stdout
    (target / "worldguard" / "runtime" / "worldguard" / "__init__.py").unlink()
    missing = subprocess.run([sys.executable, str(launcher), "check", "--help"], cwd=tmp_path, env=env, text=True, capture_output=True)
    assert missing.returncode == 1
    assert "WorldGuard runtime is missing" in missing.stderr


def test_launcher_reads_json_without_pyyaml(tmp_path):
    skill = Path(__file__).resolve().parents[1] / "skills" / "worldguard"
    example = skill / "assets" / "examples" / "trip_ferry.yaml"
    as_json = tmp_path / "trip.json"
    as_json.write_text(json.dumps(yaml.safe_load(example.read_text(encoding="utf-8"))), encoding="utf-8")

    def run_without_yaml(contract):
        probe = (
            "import runpy, sys; sys.modules['yaml'] = None; "
            f"sys.argv = ['run_worldguard.py', 'check', '--contract', {str(contract)!r}]; "
            f"runpy.run_path({str(skill / 'scripts' / 'run_worldguard.py')!r}, run_name='__main__')"
        )
        return subprocess.run([sys.executable, "-c", probe], cwd=tmp_path, text=True, capture_output=True)

    done = run_without_yaml(as_json)
    assert done.returncode == 0, done.stderr[-500:]
    assert json.loads(done.stdout)["status"] == "PASS"
    done = run_without_yaml(example)
    assert done.returncode == 2
    assert "PyYAML" in json.loads(done.stdout)["error"]["message"]


@pytest.mark.parametrize("times", [
    ("0", "2.5"), ("1", "2.5"), ("t1", "t2"), ('"9:40"', '"10:20"'),
    ("2026-11-02", "2026-11-03"),
    ("2026-11-02T09:40:00", "2026-11-02T10:20:00"),
    ("2026-11-02T09:40:00+01:00", "2026-11-02T10:20:00+01:00"),
])
@pytest.mark.parametrize("full", [False, True])
def test_actual_cli_preserves_native_yaml_time_values(tmp_path, times, full):
    path = tmp_path / "native-times.yaml"
    path.write_text('claim: {claim_id: time, asserts: [{event: first, before: second}]}\ninputs:\n  events:\n'
                    f'    - {{event_id: first, at: {times[0]}, initiates: ready}}\n'
                    f'    - {{event_id: second, at: {times[1]}, requires: ready, initiates: done}}\n')
    completed = subprocess.run([sys.executable, "-m", "worldguard", "check", "--contract", str(path),
                                *(["--json"] if full else [])], capture_output=True, text=True)
    assert completed.returncode == 0, (completed.stdout, completed.stderr)
    report = json.loads(completed.stdout)
    assert report["status"] == "PASS"
    if full:
        assert len(report["semantic_receipts"][0]["outputs"]["observed_timepoints"]) == 2


def test_cli_reports_unquoted_yaml_clock_mix_with_quote_hint(tmp_path):
    path = tmp_path / "mixed-clock.yaml"
    path.write_text('claim: {requested_semantics: [event]}\ninputs:\n  events:\n'
                    '    - {event_id: raw_clock, at: 9:40, initiates: ready}\n'
                    '    - {event_id: quoted_clock, at: "10:20", initiates: done}\n')
    completed = subprocess.run([sys.executable, "-m", "worldguard", "check", "--contract", str(path)],
                               capture_output=True, text=True)
    assert completed.returncode == 2
    result = json.loads(completed.stdout)
    assert result["error"]["code"] == "WORLDGUARD_INPUT_INVALID"
    assert 'quote clock times' in result["error"]["message"]
    assert 'raw_clock' in result["error"]["message"]


def test_cli_rejects_label_suffix_instead_of_sorting_it_last(tmp_path):
    path = tmp_path / "bad-label.json"
    path.write_text(json.dumps({"claim": {"requested_semantics": ["event"]},
                               "inputs": {"events": [{"event_id": "bad-label", "at": "t4b", "initiates": "ready"}]}}))
    completed = subprocess.run([sys.executable, "-m", "worldguard", "check", "--contract", str(path)],
                               capture_output=True, text=True)
    assert completed.returncode == 2
    result = json.loads(completed.stdout)
    assert result["error"]["code"] == "WORLDGUARD_INPUT_INVALID"
    assert "bad-label" in result["error"]["message"]


def test_cli_missing_event_time_keeps_native_gap(tmp_path):
    path = tmp_path / "missing-time.json"
    path.write_text(json.dumps({"claim": {"claim_id": "missing-time", "requested_semantics": ["event"]},
                               "inputs": {"events": [{"event_id": "e1", "initiates": "ready"}]}}))
    completed = subprocess.run([sys.executable, "-m", "worldguard", "check", "--contract", str(path), "--json"],
                               capture_output=True, text=True)
    assert completed.returncode == 1
    result = json.loads(completed.stdout)
    assert result["status"] == "GAP"
    assert result["semantic_receipts"][0]["findings"][0]["code"] == "SEM_EVENT_MISSING_AXIOM"
