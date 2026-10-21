# Task-Local Model Deepening

Load this reference for the `task_local_revision` shape: compare a frozen prediction with a later observation and decide whether a revised model closes the task. WorldGuard does not compute predictions: write the values your model implies in `expected_values`, then compare them with what was observed. Closing a revision currently needs a mesh model (`ModelMeshContract`).

## Freeze before observing

Use `schema_version: worldguard.task_local_revision.v2`. A `PredictionSnapshot` names a task id and purpose, a coverage universe (`coverage_universe_id`, `coverage_universe_owner_id`, `coverage_universe_source_ref`, and `coverage_ids` equal to the expectation ids), non-empty `assumptions` and `unknowns`, a finite budget (`iteration`, `max_iterations`), and its predecessor `predecessor_iteration_fingerprint` (`root` for iteration 0; for a later iteration the `revision_fingerprint` printed by the previous `revision`, plus the exact `prior_gap_ids`). WorldGuard computes `coverage_universe_fingerprint` and the prior-gap fingerprint itself; you may omit them.

The prediction also names the model it was made from (`model`: `model_id`, `model_version`, `path`; `freeze` records the model file's `sha256`, so you may omit it), a `prediction_sequence`, the declared `initial_state` and `intervention`, finite `expected_values` with absolute tolerances, `expected_relationships` (`left`/`relation`/`right`), and `weakening_conditions`. Every expectation declares one mismatch category: `initial_state`, `transition`, `causal_relation`, `resource`, `agent`, `observation_mapping`, or `other`.

An `ObservedWorldSnapshot` names the prediction, uses a strictly later `observation_sequence`, a non-empty `source_ref` and `evidence_id`, and carries actual values, relationships, or exact external-input requirements. WorldGuard computes its `evidence_fingerprint`.

## Compare and revise

Save the output of `freeze` and pass it to `compare`; `compare` refuses a prediction without the recorded `sha256` and blocks when the model file changed after `freeze`. It checks only declared expectations. Every missing or contradicted expectation keeps its mismatch category; the result never closes the task by itself. Revise by writing a separate candidate model; never overwrite the predecessor.

A `CandidateWorldModelRevision` names the base and candidate models (separate files), the frozen prediction and its comparison (the outputs of `freeze` and `compare` for the base model), `candidate_build_evidence_fingerprints` (the `observation_evidence_fingerprint` of every observation used to build the candidate), exactly two revalidations - `original_scenario` and `real_holdout_observation`, each written as `{check_id, role, empirical_comparison}` where `empirical_comparison` is the output of `compare` for the candidate - plus `candidate_applied`, `rollback_model` and `external_inputs`.

`revision` runs the candidate mesh once and derives state, transition, branch, perturbation, intervention, counterfactual and holdout gaps from that run. The original and the holdout scenarios declared in the candidate's `semantic_coverage` must both have executed. The two observations must be independent: different observation ids, sources, evidence and content, and the holdout must not appear in the candidate's build evidence.

## Continue or stop from evidence

The runtime computes input, resolved, persisted, introduced, and current gaps.

- Continue when a new addressable gap exists.
- Stop as `progress_stalled` when the gap fingerprint is unchanged or repeated.
- Stop as `iteration_limit` when the finite budget is exhausted.
- Return `external_input_required` only with the exact input, owner, reason, blocked gap ids, and affected claims.
- Emit `model_closed_for_task` only after a licensed predictive run, zero current gaps, and both independent revalidations pass.

A passing candidate is `accepted`; a failed unapplied candidate is `rejected`; a failed applied candidate is `rolled_back` only when its rollback model is the still-current base. When fact-level support changes, load `fact-revision.md`; fact activation ends at `task_local_revalidation_required` and returns here.

## Commands

```bash
python <skill-root>/scripts/run_worldguard.py task-model freeze <prediction.yaml>
python <skill-root>/scripts/run_worldguard.py task-model compare <frozen.json> <observation.yaml>
python <skill-root>/scripts/run_worldguard.py task-model revision <candidate-revision.yaml>
```

This loop shows only bounded task-local model closure under the declared evidence. It does not prove factual truth or accuracy outside that boundary.
