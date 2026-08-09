"""Run the bounded WorldGuard behavior ledger and its primary-path evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard import review_behavior_commitment_ledger

from model import (
    VALIDATION_PATHS,
    build_primary_path_reports,
    build_worldguard_behavior_commitment_ledger,
    current_fingerprints,
    validation_receipt_hash,
)


TARGETED_TESTS = {
    "input": (
        "tests/test_contracts.py",
        "tests/test_guard_model_contract.py",
    ),
    "template": ("tests/test_template_packs.py",),
    "fact": ("tests/test_fact_revision.py",),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _toolchain_identity() -> dict[str, object]:
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_implementation": sys.implementation.name,
        "python_version": list(sys.version_info[:3]),
        "pytest_version": importlib.metadata.version("pytest"),
    }


def _run_shard(shard_id: str) -> dict[str, object]:
    tests = TARGETED_TESTS[shard_id]
    command = [sys.executable, "-m", "pytest", "-q", *tests]
    recorded_command = "python -m pytest -q " + " ".join(tests)
    started_at = _now()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        check=False,
    )
    finished_at = _now()
    validation = {
        "artifact_type": "worldguard_behavior_commitment_validation",
        "schema_version": "2.0",
        "shard_id": shard_id,
        "command": recorded_command,
        "status": "passed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "started_at": started_at,
        "finished_at": finished_at,
        "artifact_fingerprints": current_fingerprints(shard_id),
        "toolchain_identity": _toolchain_identity(),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    validation["receipt_hash"] = validation_receipt_hash(validation)
    VALIDATION_PATHS[shard_id].write_text(
        json.dumps(validation, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return validation


def _aggregate() -> dict[str, object]:
    input_report, template_report, fact_report = build_primary_path_reports()
    ledger_report = review_behavior_commitment_ledger(
        build_worldguard_behavior_commitment_ledger()
    )
    payload = {
        "artifact_type": "worldguard_behavior_commitment_aggregation",
        "schema_version": "2.0",
        "ok": bool(
            input_report.ok
            and template_report.ok
            and fact_report.ok
            and ledger_report.ok
        ),
        "execution_count": 0,
        "shard_receipt_hashes": {
            shard_id: json.loads(path.read_text(encoding="utf-8")).get(
                "receipt_hash", ""
            )
            if path.is_file()
            else ""
            for shard_id, path in VALIDATION_PATHS.items()
        },
        "input_primary_path": input_report.to_dict(),
        "template_primary_path": template_report.to_dict(),
        "fact_primary_path": fact_report.to_dict(),
        "behavior_commitment_ledger": ledger_report.to_dict(),
    }
    result_path = Path(__file__).with_name("result.json")
    result_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(input_report.format_text())
    print()
    print(template_report.format_text())
    print()
    print(fact_report.format_text())
    print()
    print(ledger_report.format_text())
    return 0 if payload["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--shard",
        required=False,
        default="model",
        choices=("model", "input", "template", "fact", "aggregate"),
        help=(
            "Run exactly one affected evidence owner, or aggregate current "
            "immutable shard receipts without starting tests."
        ),
    )
    args = parser.parse_args(argv)
    if args.shard == "model":
        from run_model_checks import main as run_model_checks_main

        return run_model_checks_main()
    if args.shard == "aggregate":
        return _aggregate()
    validation = _run_shard(args.shard)
    print(str(validation["stdout"]), end="")
    if validation["stderr"]:
        print(str(validation["stderr"]), file=sys.stderr, end="")
    print(
        json.dumps(
            {
                "artifact_type": "worldguard_behavior_commitment_shard_result",
                "shard_id": args.shard,
                "status": validation["status"],
                "exit_code": validation["exit_code"],
                "receipt_hash": validation["receipt_hash"],
            },
            sort_keys=True,
        )
    )
    return 0 if validation["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
