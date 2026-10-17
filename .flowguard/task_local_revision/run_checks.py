"""Run WorldGuard task-local FlowGuard scenarios and focused native tests."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from flowguard.review import review_scenarios


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(__file__).with_name("model.py")


def _load_model():
    spec = importlib.util.spec_from_file_location("worldguard_task_local_flowguard_model", MODEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load model from {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    model = _load_model()
    report = review_scenarios(model.scenarios())
    findings = []
    print(report.format_text(max_counterexamples=8))
    print(
        json.dumps(
            {
                "artifact_kind": "worldguard_task_local_revision_flowguard_report",
                "status": "pass" if report.ok and not findings else "blocked",
                "scenario_count": len(model.scenarios()),


                "findings": findings,
                "claim_boundary": "This proves the finite strict task-local workflow only; it does not prove factual truth, installation, publication, or release.",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.ok and not findings else 1


if __name__ == "__main__":
    from flowguard.map.runner import run_owner
    raise SystemExit(run_owner(main))
