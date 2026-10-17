"""Run the WorldGuard fact-revision FlowGuard model and native parity checks."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

from flowguard.review import review_scenarios


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(__file__).with_name("model.py")


def _load_model():
    spec = importlib.util.spec_from_file_location(
        "worldguard_fact_revision_flowguard_model",
        MODEL_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load model from {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _native_findings() -> list[str]:
    sys.path.insert(0, str(ROOT))
    from worldguard.fact_revision import (  # noqa: PLC0415
        FactPolarity,
        FactRevisionTransaction,
        FactSupport,
        FactWorldSnapshot,
        SignedFact,
        StrictFactRule,
        WorldFact,
        preview_fact_revision,
    )

    rain = WorldFact("rain")
    wet = WorldFact("wet")
    unrelated = WorldFact("unrelated")
    positive_rain = FactSupport(
        "support:rain",
        rain.fact_id,
        FactPolarity.POSITIVE,
        "source:observation",
        "evidence:rain",
    )
    negative_rain = FactSupport(
        "support:not-rain",
        rain.fact_id,
        FactPolarity.NEGATIVE,
        "source:counterevidence",
        "evidence:not-rain",
    )
    rule = StrictFactRule(
        "rule:rain-wet",
        (SignedFact(rain.fact_id, FactPolarity.POSITIVE),),
        SignedFact(wet.fact_id, FactPolarity.POSITIVE),
        "source:strict-rule",
        "evidence:rain-wet",
    )
    base = FactWorldSnapshot(
        snapshot_id="base",
        facts=(rain, wet, unrelated),
        supports=(positive_rain,),
        rules=(rule,),
    )
    transaction = FactRevisionTransaction(
        transaction_id="tx",
        base_fingerprint=base.fingerprint,
        additions=(negative_rain,),
        task_id="task:flowguard-fact-revision",
        task_local_owner_id="worldguard.task_local_world_revision",
        iteration=0,
        predecessor_iteration_fingerprint="root",
    )
    preview = preview_fact_revision(base, transaction)
    findings: list[str] = []
    states = {item.fact_id: item.state.value for item in preview.after_states}
    if not preview.contradiction_fact_ids:
        findings.append("native preview did not expose the rain contradiction")
    if states.get(rain.fact_id) != "both":
        findings.append("native preview collapsed four-valued both into a binary state")
    if states.get(unrelated.fact_id) != "neither":
        findings.append("native preview exploded a contradiction into an unrelated fact")
    base_states = {item.fact_id: item.state.value for item in preview.before_states}
    if base_states.get(rain.fact_id) != "true":
        findings.append("native preview mutated the base snapshot")
    return findings


def main() -> int:
    model = _load_model()
    report = review_scenarios(model.scenarios())
    findings = _native_findings()
    print(report.format_text(max_counterexamples=8))
    print(
        json.dumps(
            {
                "artifact_kind": "worldguard_fact_revision_flowguard_report",
                "status": "pass" if report.ok and not findings else "blocked",
                "scenario_count": len(model.scenarios()),
                "findings": findings,
                "claim_boundary": (
                    "This proves the finite fact-revision workflow and a native semantic parity sample only. "
                    "It does not prove source truth, installation, publication, or release."
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.ok and not findings else 1


if __name__ == "__main__":
    from flowguard.map.runner import run_owner
    raise SystemExit(run_owner(main))
