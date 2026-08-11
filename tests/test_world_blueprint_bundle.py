from __future__ import annotations

from pathlib import Path

import pytest

import worldguard
import worldguard.blueprint_bundle as bundle_module
from worldguard.blueprint import BlueprintError
from worldguard.cli import main


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/world_blueprint/planning_workflow_three_level.yaml"


@pytest.mark.parametrize(
    "operation",
    [
        "build_world_blueprint_bundle",
        "write_world_blueprint_bundle",
        "load_world_blueprint_bundle",
        "verify_world_blueprint_bundle",
        "query_world_blueprint_bundle",
    ],
)
def test_transport_bundle_routes_fail_closed_without_writing(
    operation: str, tmp_path: Path
) -> None:
    destination = tmp_path / "must-not-exist.bundle.json"
    function = getattr(bundle_module, operation)
    with pytest.raises(BlueprintError) as caught:
        if operation == "write_world_blueprint_bundle":
            function({}, destination)
        else:
            function(FIXTURE)
    assert caught.value.code == "WORLD_BLUEPRINT_NATIVE_DIRECTORY_ONLY"
    assert not destination.exists()


def test_package_surface_has_no_transport_bundle_exports() -> None:
    for name in (
        "build_world_blueprint_bundle",
        "write_world_blueprint_bundle",
        "load_world_blueprint_bundle",
        "verify_world_blueprint_bundle",
        "query_world_blueprint_bundle",
    ):
        assert not hasattr(worldguard, name)
        assert name not in worldguard.__all__


def test_blueprint_cli_has_no_bundle_operations(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["blueprint", "bundle-export", "--blueprint", str(FIXTURE), "--destination", "x"])
    assert caught.value.code == 2
    assert "invalid choice" in capsys.readouterr().err


def test_self_dna_cli_has_no_export_operation(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as caught:
        main(["self-dna", "export", "--root", str(ROOT), "--output", "x"])
    assert caught.value.code == 2
    assert "invalid choice" in capsys.readouterr().err
