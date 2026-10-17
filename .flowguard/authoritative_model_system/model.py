"""Executable root of the worldguard repository software-DNA model.

This model checks the repository's own model, code, test, and evidence
denominator. It reports readiness from current files; it does not recreate
the target software and it does not delegate the check to another agent.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping

FLOWGUARD_MODEL_MARKER = "flowguard-executable-model"

REQUIRED_DEFINITION_FIELDS = (
    "schema_version",
    "blueprint_id",
    "inventory_id",
    "boundary",
    "scan_python_patterns",
    "scoped_out_patterns",
    "bounded_dynamic_prefixes",
    "dynamic_allowances",
    "dynamic_selector_contracts",
    "composite_behavior_contracts",
    "owner_overrides",
    "resource_groups",
    "claim_boundary",
)


@dataclass(frozen=True)
class SelfDnaInput:
    manifest_current: bool
    definition_current: bool
    mesh_current: bool
    owner_bindings_current: bool
    evidence_paths_current: bool


@dataclass(frozen=True)
class SelfDnaState:
    phase: str = "unverified"
    ready: bool = False


def evaluate_self_dna(inputs: SelfDnaInput) -> SelfDnaState:
    ready = all(
        (
            inputs.manifest_current,
            inputs.definition_current,
            inputs.mesh_current,
            inputs.owner_bindings_current,
            inputs.evidence_paths_current,
        )
    )
    return SelfDnaState(phase="ready" if ready else "blocked", ready=ready)


def _load_object(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"{path} must contain an object")
    return value


def check_blueprint_inputs(root: str | Path) -> dict[str, Any]:
    from flowguard.map.mapfile import load_map
    from flowguard.map.inventory import build_inventory
    from flowguard.map.check import run_check
    root_path = Path(root).resolve()
    data = load_map(root_path)
    findings = run_check(root_path, data, build_inventory(root_path, data.get("ignore", [])))
    errors = [item.message for item in findings if item.level == "error"]
    return {"status": "ready" if not errors else "blocked", "ready": not errors,
            "model_count": sum(len(c.get("models", [])) for c in data["components"]),
            "findings": errors}


def run_model() -> None:
    good = evaluate_self_dna(SelfDnaInput(True, True, True, True, True))
    assert good.ready and good.phase == "ready"
    for index in range(5):
        values = [True] * 5
        values[index] = False
        candidate = evaluate_self_dna(SelfDnaInput(*values))
        assert not candidate.ready and candidate.phase == "blocked"
    return {"ok": True, "model": 'authoritative_model_system'}


if __name__ == "__main__":
    run_model()
    print("authoritative_model_system: pass")
