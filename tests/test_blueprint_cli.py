from __future__ import annotations

import builtins
import json
import shutil
from pathlib import Path

import pytest
import yaml

from worldguard.blueprint import (
    check_world_blueprint,
    load_world_blueprint,
)
from worldguard.cli import main


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/world_blueprint/planning_workflow_three_level.yaml"


def test_blueprint_check_cli_emits_canonical_report(capsys) -> None:
    exit_code = main(["blueprint", "check", "--blueprint", str(FIXTURE)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "PASS"
    assert payload["native_domain_qualified"] is True
    assert len(payload["blueprint_fingerprint"]) == 64
    assert len(payload["report_fingerprint"]) == 64






def test_blueprint_impact_cli_is_repeatable(capsys) -> None:
    argv = [
        "blueprint",
        "impact",
        "--blueprint",
        str(FIXTURE),
        "--changed-id",
        "schedule_transition",
    ]

    first_code = main(argv)
    first_output = capsys.readouterr().out
    second_code = main(argv)
    second_output = capsys.readouterr().out

    assert first_code == second_code == 0
    assert first_output == second_output
    payload = json.loads(first_output)
    assert payload["operation"] == "impact"
    assert payload["changed_ids"] == ["schedule_transition"]





def test_blueprint_impact_cli_rejects_mixed_known_unknown_ids_atomically(
    capsys,
) -> None:

    exit_code = main(
        [
            "blueprint",
            "impact",
            "--blueprint",
            str(FIXTURE),
            "--changed-id",
            "schedule_transition",
            "--changed-id",
            "not-in-blueprint",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["error"]["code"] == "WORLD_BLUEPRINT_QUERY_ID_UNKNOWN"
    assert payload["error"]["details"] == {"unknown_ids": ["not-in-blueprint"]}
    assert "affected_members" not in payload


def test_blueprint_trace_cli_is_native_and_does_not_import_flowguard(
    capsys,
    monkeypatch,
) -> None:
    real_import = builtins.__import__

    def reject_flowguard(name, *args, **kwargs):
        if name == "flowguard" or name.startswith("flowguard."):
            raise AssertionError("native blueprint operation imported FlowGuard")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", reject_flowguard)
    exit_code = main(
        [
            "blueprint",
            "trace",
            "--blueprint",
            str(FIXTURE),
            "--target-id",
            "root_plan_outcome",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["operation"] == "trace"
    assert payload["target_id"] == "root_plan_outcome"
    assert payload["gaps"] == []


def test_unknown_blueprint_operation_is_not_reinterpreted() -> None:
    with pytest.raises(SystemExit) as caught:
        main(["blueprint", "rebuild", "--blueprint", str(FIXTURE)])
    assert caught.value.code == 2


def test_blueprint_cli_missing_input_is_canonical_json(capsys, tmp_path: Path) -> None:
    missing = tmp_path / "missing-world-blueprint.yaml"

    exit_code = main(["blueprint", "check", "--blueprint", str(missing)])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "WORLD_BLUEPRINT_INPUT_INVALID"
    assert payload["error"]["details"]["input_path"] == str(missing)


def test_blueprint_trace_cli_rejects_an_unqualified_source_atomically(
    capsys,
    tmp_path: Path,
) -> None:
    payload = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    allocation = next(
        node for node in payload["nodes"] if node["node_id"] == "allocation_layer"
    )
    allocation["child_output_mappings"] = []
    payload.pop("blueprint_fingerprint", None)
    shutil.copytree(FIXTURE.parent / "support", tmp_path / "support")
    mutated = tmp_path / "broken-blueprint.yaml"
    mutated.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    blueprint = load_world_blueprint(mutated)
    qualification = check_world_blueprint(blueprint)

    exit_code = main(
        [
            "blueprint",
            "trace",
            "--blueprint",
            str(mutated),
            "--target-id",
            "root_plan_outcome",
        ]
    )
    result = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert result["status"] == "error"
    assert result["error"]["code"] == "WORLD_BLUEPRINT_QUERY_SOURCE_UNQUALIFIED"
    assert result["error"]["details"]["blueprint_fingerprint"] == (
        blueprint.blueprint_fingerprint
    )
    assert result["error"]["details"]["qualification_report_fingerprint"] == (
        qualification.report_fingerprint
    )
    assert result["error"]["details"]["source_gap_ids"] == sorted(
        gap.gap_id for gap in qualification.gaps
    )
    assert "terminal_input_ids" not in result
