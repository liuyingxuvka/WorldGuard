from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER = REPO_ROOT / "skills" / "worldguard" / "scripts" / "run_worldguard_check.py"
PORTABLE_RUNTIME = REPO_ROOT / "skills" / "worldguard" / "runtime"


def _environment(*python_paths: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(str(path) for path in python_paths)
    return environment


def _run_helper(
    *arguments: str,
    helper: Path = HELPER,
    environment: dict[str, str] | None = None,
    cwd: Path = REPO_ROOT,
    python_options: tuple[str, ...] = (),
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *python_options, str(helper), *arguments],
        cwd=cwd,
        env=environment or _environment(),
        text=True,
        capture_output=True,
        check=False,
    )


def _run_portable_cli(
    *arguments: str,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "worldguard", *arguments],
        cwd=cwd,
        env=_environment(PORTABLE_RUNTIME),
        text=True,
        capture_output=True,
        check=False,
    )


def _write_unit_contract(path: Path) -> None:
    mesh = yaml.safe_load(
        (REPO_ROOT / "examples" / "model_mesh" / "basic_mesh.yaml").read_text(
            encoding="utf-8"
        )
    )
    path.write_text(
        yaml.safe_dump(mesh["nodes"][0]["contract"], sort_keys=False),
        encoding="utf-8",
    )


def _assert_same_public_result(
    helper_result: subprocess.CompletedProcess[str],
    cli_result: subprocess.CompletedProcess[str],
) -> None:
    def normalize_generated_at(value: object) -> object:
        if isinstance(value, dict):
            return {
                key: (
                    "<generated-at>"
                    if key == "generated_at"
                    else normalize_generated_at(item)
                )
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [normalize_generated_at(item) for item in value]
        return value

    assert helper_result.returncode == cli_result.returncode
    assert helper_result.stderr == cli_result.stderr
    assert normalize_generated_at(json.loads(helper_result.stdout)) == normalize_generated_at(
        json.loads(cli_result.stdout)
    )


def test_legacy_example_contract_and_mesh_surfaces_delegate_to_portable_cli(
    tmp_path: Path,
) -> None:
    contract = tmp_path / "contract.yaml"
    _write_unit_contract(contract)
    mesh = REPO_ROOT / "examples" / "model_mesh" / "basic_mesh.yaml"
    mesh_before = mesh.read_bytes()
    cases = (
        (("--example", "fuel_cell"), ("check", "--example", "fuel_cell")),
        (("--contract", str(contract)), ("check", "--contract", str(contract))),
        (("--mesh", str(mesh)), ("mesh-check", "--mesh", str(mesh))),
    )

    for legacy_arguments, canonical_arguments in cases:
        _assert_same_public_result(
            _run_helper(*legacy_arguments),
            _run_portable_cli(*canonical_arguments, cwd=tmp_path),
        )
    assert mesh.read_bytes() == mesh_before


def test_legacy_branch_precedence_is_preserved(tmp_path: Path) -> None:
    contract = tmp_path / "contract.yaml"
    _write_unit_contract(contract)
    missing = tmp_path / "missing.yaml"

    example_result = _run_helper(
        "--example",
        "fuel_cell",
        "--contract",
        str(missing),
        "--mesh",
        str(missing),
    )
    _assert_same_public_result(
        example_result,
        _run_portable_cli("check", "--example", "fuel_cell", cwd=tmp_path),
    )

    contract_result = _run_helper(
        "--contract",
        str(contract),
        "--mesh",
        str(missing),
    )
    _assert_same_public_result(
        contract_result,
        _run_portable_cli("check", "--contract", str(contract), cwd=tmp_path),
    )


def test_missing_selection_keeps_legacy_parser_error_contract() -> None:
    completed = _run_helper()

    assert completed.returncode == 2
    assert completed.stdout == ""
    assert (
        "provide --example fuel_cell, --contract <path>, or --mesh <path>"
        in completed.stderr
    )


def test_runtime_exception_keeps_legacy_single_json_error_contract(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing-contract.yaml"

    completed = _run_helper("--contract", str(missing))

    assert completed.returncode == 1
    assert completed.stderr == ""
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert isinstance(payload["error"], str) and payload["error"]
    assert set(payload) == {"ok", "error"}


def test_missing_portable_runtime_fails_without_importing_external_package(
    tmp_path: Path,
) -> None:
    copied_helper = (
        tmp_path
        / "isolated-skill"
        / "scripts"
        / "run_worldguard_check.py"
    )
    copied_helper.parent.mkdir(parents=True)
    shutil.copy2(HELPER, copied_helper)

    external_root = tmp_path / "external"
    external_package = external_root / "worldguard"
    external_package.mkdir(parents=True)
    marker = tmp_path / "external-imported.txt"
    (external_package / "__init__.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('imported')\n",
        encoding="utf-8",
    )

    completed = _run_helper(
        "--example",
        "fuel_cell",
        helper=copied_helper,
        environment=_environment(external_root),
        cwd=tmp_path,
        python_options=("-S",),
    )

    assert completed.returncode == 1
    assert completed.stderr == ""
    assert "portable WorldGuard runtime is incomplete" in json.loads(
        completed.stdout
    )["error"]
    assert not marker.exists()


def test_preloaded_external_worldguard_is_rejected_without_fallback(
    tmp_path: Path,
) -> None:
    external_root = tmp_path / "preloaded-external"
    external_package = external_root / "worldguard"
    external_package.mkdir(parents=True)
    (external_package / "__init__.py").write_text(
        "EXTERNAL_SENTINEL = True\n",
        encoding="utf-8",
    )
    launcher = (
        "import runpy, sys; "
        "import worldguard; "
        f"sys.argv = [{str(HELPER)!r}, '--example', 'fuel_cell']; "
        f"runpy.run_path({str(HELPER)!r}, run_name='__main__')"
    )
    completed = subprocess.run(
        [sys.executable, "-S", "-c", launcher],
        cwd=tmp_path,
        env=_environment(external_root),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert completed.stderr == ""
    assert "escaped bundled root" in json.loads(completed.stdout)["error"]
