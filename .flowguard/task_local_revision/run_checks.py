"""Check the task-local workflow scenarios and replay their terminals against the real revision code."""

from __future__ import annotations

from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

from flowguard import Workflow
from flowguard.explorer import Explorer
from flowguard.review import review_scenarios


ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = Path(__file__).with_name("model.py")

IMPLEMENTED_BY = {
    "ValidateRevisionEvidence": "worldguard/task_local_revision.py:evaluate_candidate_world_revision",
    "DecideTaskLocalTerminal": "worldguard/task_local_revision.py:evaluate_candidate_world_revision",
}
TESTED_BY = {
    "task_local_closure_requires_current_typed_evidence": [
        "tests/test_task_local_revision.py:test_candidate_closes_only_with_current_depth_and_independent_holdout",
        "tests/test_task_local_revision.py:test_holdout_alias_or_construction_reuse_rejects_candidate",
    ],
    "task_local_open_native_gap_never_closes": [
        "tests/test_task_local_revision.py:test_native_depth_gap_is_derived_and_forces_continuation",
        "tests/test_task_local_revision.py:test_no_raw_gap_but_unlicensed_native_receipt_cannot_close",
    ],
    "fact_activation_returns_to_same_task_owner": [
        "tests/test_fact_revision.py:test_fact_activation_cannot_claim_model_closed_for_task",
    ],
}


def _load_model():
    spec = importlib.util.spec_from_file_location("worldguard_task_local_flowguard_model", MODEL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load model from {MODEL_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _model_terminal(model, request) -> str:
    state = model.RevisionState()
    for block in (model.ValidateRevisionEvidence(), model.DecideTaskLocalTerminal()):
        state = next(iter(block.apply(request, state))).new_state
    return state.terminal_reason


def native_conformance(model) -> dict:
    """Drive evaluate_candidate_world_revision with one real case per model terminal."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tests.test_task_local_revision import _fp, _model, _native_source, _revision
    from worldguard.task_local_revision import CandidateWorldModelRevision, evaluate_candidate_world_revision

    def run(folder: Path, change) -> dict:
        base = _model(folder, "v1.json", '{"version": 1}')
        candidate = _model(folder, "v2.json", '{"version": 2}')
        row = change(folder, base, candidate)
        return evaluate_candidate_world_revision(CandidateWorldModelRevision.from_dict(row), base_dir=folder)

    def stalled(folder, base, candidate):
        _revision(folder, base, candidate, native_gaps=["transition:missing-edge"])
        gaps = sorted("native:" + gap for gap in _native_source(folder, candidate)["predictive_gaps"])
        return _revision(folder, base, candidate, native_gaps=["transition:missing-edge"], iteration=1,
                         prior_gap_ids=gaps, prior_gap_fingerprints=[_fp(gaps)])

    def external(folder, base, candidate):
        row = _revision(folder, base, candidate, native_gaps=["holdout:unseen-regime"])
        row["external_inputs"] = [{
            "input_id": "external:holdout-observation", "owner_id": "owner:lab",
            "reason": "the required regime is not observable with local tools",
            "blocked_gap_ids": sorted("native:" + gap for gap in _native_source(folder, candidate)["predictive_gaps"]),
            "affected_claim_ids": ["claim:future-regime"],
        }]
        return row

    def reused_holdout(folder, base, candidate):
        row = _revision(folder, base, candidate)
        row["candidate_build_evidence_fingerprints"].append(
            row["revalidations"][1]["empirical_comparison"]["observation_evidence_fingerprint"])
        return row

    request = model.RevisionRequest
    cases = (
        (request(), lambda f, b, c: _revision(f, b, c), "model_closed_for_task"),
        (request(has_native_gap=True), lambda f, b, c: _revision(f, b, c, native_gaps=["branch:new-regime"]), "continue_iteration"),
        (request(predictive_licensed=False), lambda f, b, c: _revision(f, b, c, licensed=False), "continue_iteration"),
        (request(has_native_gap=True, gap_changed=False, iteration=1), stalled, "progress_stalled"),
        (request(has_native_gap=True, iteration=1, max_iterations=2), lambda f, b, c: _revision(
            f, b, c, native_gaps=["state:unknown"], iteration=1, max_iterations=2,
            prior_gap_ids=["native:state:previous-gap"], prior_gap_fingerprints=[_fp(["native:state:previous-gap"])]), "iteration_limit"),
        (request(has_native_gap=True, external_boundary_exact=True), external, "external_input_required"),
        (request(holdout_independent=False), reused_holdout, "candidate_rejected"),
    )
    findings = []
    with tempfile.TemporaryDirectory() as tmp:
        for index, (model_request, change, real_reason) in enumerate(cases):
            folder = Path(tmp) / f"case-{index}"
            folder.mkdir()
            observed = run(folder, change)["terminal_reason"]
            model_reason = _model_terminal(model, model_request)
            terminal_mapping = {"holdout_not_independent": "candidate_rejected"}
            mapped_terminal = terminal_mapping.get(model_reason, model_reason)
            if observed != real_reason or observed != mapped_terminal:
                findings.append({"model": model_reason, "mapped_model_terminal": mapped_terminal,
                                 "expected_code_terminal": real_reason, "observed": observed})
    return {"ok": not findings, "cases": len(cases), "findings": findings}


def broken_variants(model) -> dict:
    """Known-bad variants: name -> (broken block, invariants that must report a counterexample)."""

    class ClosesWithOpenGap(model.DecideTaskLocalTerminal):
        def apply(self, request, state):
            for result in super().apply(request, state):
                if result.new_state.open_native_gap:
                    result = replace(result, new_state=replace(result.new_state, task_closed=True))
                yield result

    class AdmitsReusedHoldout(model.ValidateRevisionEvidence):
        def apply(self, request, state):
            for result in super().apply(replace(request, holdout_independent=True), state):
                yield replace(result, new_state=replace(result.new_state, holdout_independent=request.holdout_independent))

    return {
        "closes_with_open_gap": (ClosesWithOpenGap(), ("task_local_open_native_gap_never_closes",)),
        "admits_reused_holdout": (AdmitsReusedHoldout(), ("task_local_closure_requires_current_typed_evidence",)),
    }


def missed_variants(model) -> list[str]:
    """Explore the intended design and every known-bad variant on the scenarios' safe inputs."""
    inputs = tuple(dict.fromkeys(
        request for scenario in model.scenarios() if scenario.expected.expected_status == "ok"
        for request in scenario.external_input_sequence
    ))

    def explore(blocks, name):
        return Explorer(workflow=Workflow(blocks, name=name), initial_states=(model.RevisionState(),),
                        external_inputs=inputs, invariants=model.INVARIANTS, max_sequence_length=1).explore()

    missed = [] if explore(model.build_workflow().blocks, "intended").ok else ["intended_design"]
    for name, (broken, invariant_names) in broken_variants(model).items():
        blocks = tuple(broken if isinstance(broken, type(block)) else block for block in model.build_workflow().blocks)
        caught = {violation.invariant_name for violation in explore(blocks, name).violations}
        if not set(invariant_names) <= caught:
            missed.append(name)
    return missed


def main() -> int:
    model = _load_model()
    report = review_scenarios(model.scenarios())
    conformance = native_conformance(model)
    missed = missed_variants(model)
    print(report.format_text(max_counterexamples=8))
    print(
        json.dumps(
            {
                "artifact_kind": "worldguard_task_local_revision_flowguard_report",
                "status": "pass" if report.ok and conformance["ok"] and not missed else "blocked",
                "scenario_count": len(model.scenarios()),
                "conformance": conformance,
                "known_bad_variants": {"declared": sorted(broken_variants(model)), "missed": missed},
                "claim_boundary": "The finite task-local workflow, with each terminal replayed once against evaluate_candidate_world_revision; it does not prove factual truth.",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.ok and conformance["ok"] and not missed else 1


if __name__ == "__main__":
    from flowguard.map.runner import run_owner
    raise SystemExit(run_owner(main))
