from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from semantic_rollout_model import run_checks  # noqa: E402
from worldguard import SemanticStatus, run_model_mesh  # noqa: E402



def _runtime_probe() -> dict[str, object]:
    task_contract_id = "event-contract"
    run_id = "flowguard-semantic-rollout"
    model_instance_id = "event"
    mesh = {
        "mesh_id": "flowguard-runtime-probe",
        "run_id": run_id,
        "nodes": [
            {
                "model_id": "event-node",
                "authority": {"owns": ["event"]},
                "contract": {
                    "contract_id": task_contract_id,
                    "run_id": run_id,
                    "claim": {
                        "claim_id": "event-claim",
                        "text": "bounded event claim",
                        "target_guards": ["EventGuard"],
                        "requested_semantics": ["event"],
                    },
                    "world_model": {"model_id": model_instance_id, "model_version": "v1"},
                    "inputs": {"events": [{"event_id": "e1", "at": "t0"}]},
                },
            }
        ],
    }
    report = run_model_mesh(mesh)
    receipt = report.depth_receipt
    ok = (
        report.structural_status.value == "PASS"
        and report.semantic_status != SemanticStatus.PASS
        and report.status.value != "PASS"
        and receipt is not None
        and bool(receipt.findings)
        and bool(receipt.claim_boundary)
    )
    return {
        "ok": ok,
        "structural_status": report.structural_status.value,
        "semantic_status": report.semantic_status.value,
        "aggregate_status": report.status.value,
        "receipt_id": receipt.receipt_id if receipt else "",
    }


def main() -> int:
    modeled = run_checks()
    runtime = _runtime_probe()
    result = {"ok": bool(modeled["ok"] and runtime["ok"]), "modeled": modeled, "runtime": runtime}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
