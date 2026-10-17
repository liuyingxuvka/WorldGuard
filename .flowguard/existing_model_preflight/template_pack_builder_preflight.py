"""Read-only pointer to the current template owner in the living map."""

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
        "implementation": "worldguard/template_packs.py",
        "model": ".flowguard/template_selection/run_checks.py",
        "tests": "tests/test_template_packs.py",
        "responsibilities": [
            "Native registry, exact applicability and zero/one/many selection",
            "Base/candidate composition with exact disjoint field ownership",
            "Exact slots, canonical shape/routes and instance fingerprints",
        ],
        "boundary": "Current map consistency only; no model or domain test was executed.",
    }


if __name__ == "__main__":
    report = build_preflight()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)
