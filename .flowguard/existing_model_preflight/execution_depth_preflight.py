"""Read-only pointer to the current native depth owner in the living map."""

from __future__ import annotations

import json
from pathlib import Path

from flowguard.map.check import run_check
from flowguard.map.inventory import build_inventory
from flowguard.map.mapfile import load_map

ROOT = Path(__file__).resolve().parents[2]


def build_preflight() -> dict:
    data = load_map(ROOT)
    inventory = build_inventory(ROOT, data.get("ignore", []))
    result = run_check(ROOT, data, inventory, strict=True)
    components = data.get("components", [])
    owner = next(item for item in components if item["id"] == "worldguard")
    return {
        "ok": not any(finding.level == "error" for finding in result),
        "owner": owner["id"],
        "fingerprint": owner["fingerprint"],
        "implementation": "worldguard/execution_depth.py",
        "model": ".flowguard/run_claim_derived_coverage_checks.py",
        "tests": "tests/test_execution_depth.py",
        "responsibilities": [
            "Current native_depth.v2 model/semantic identity",
            "Per-node and per-variable temporal coverage and exact obligations",
            "Predictive-license and task/candidate binding without supervision envelopes",
        ],
        "boundary": "Current map consistency only; no model or domain test was executed.",
    }


if __name__ == "__main__":
    report = build_preflight()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)
