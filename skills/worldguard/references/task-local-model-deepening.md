# Task-Local Model Deepening

Load this reference for the `task_local_revision` shape or when EventGuard/CausalGuard declares predictive intent, intervention/counterfactual work, or a current predictive gap. WorldGuard does not compute predictions: write the values your model implies in `expected_values`, then compare them with what was observed. Closing a revision currently needs a mesh model (`ModelMeshContract`).

## Freeze before observing

Use only `worldguard.task_local_revision.v2`. Freeze a non-empty task id and purpose, independently owned coverage-universe id/source/inventory/fingerprint, non-empty assumptions and unknowns, finite iteration budget, and exact root or content-addressed predecessor. Later iterations bind exact prior gap ids and their set fingerprint.

Freeze `PredictionSnapshot` against the exact current model id, version, path, SHA-256, and sequence before reading the new observation. Preserve actual finite values and typed left/relation/right records in a strictly later `ObservedWorldSnapshot` with a content-addressed identity and source.

## Compare and revise

Compare only declared expectations. Keep every missing or contradicted expectation under its WorldGuard mismatch category. Create a separate candidate model; never overwrite the predecessor.

Bind one exact current native execution-depth receipt to the same task, coverage universe, and candidate. Derive state, transition, branch, perturbation, intervention, counterfactual, and holdout gaps from that receipt. A caller-authored remaining-gap list, progress boolean, PASS string, or understanding label has no authority.

Require exactly one typed original-scenario receipt and one typed real-holdout receipt. Each includes a content-addressed semantic result and empirical comparison. Their observation ids, sources, evidence fingerprints, content fingerprints, and semantic-result fingerprints must be independent; holdout evidence cannot appear in candidate construction.

## Continue or stop from evidence

The runtime computes input, resolved, persisted, introduced, and current gaps.

- Continue when a new addressable gap exists.
- Stop as `progress_stalled` when the gap fingerprint is unchanged or repeated.
- Stop as `iteration_limit` when the finite budget is exhausted.
- Return `external_input_required` only with the exact input, owner, reason, blocked gap ids, and affected claims.
- Emit `model_closed_for_task` only from the same task-local owner after native predictive license, zero current gaps, and both independent revalidations pass.

When fact-level support changes, load `fact-revision.md`. Fact activation ends at `task_local_revalidation_required` and returns to this same owner; it never closes the task.

## Native commands

```bash
python <skill-root>/scripts/run_worldguard.py task-model freeze <prediction.yaml>
python <skill-root>/scripts/run_worldguard.py task-model compare <prediction.yaml> <observation.yaml>
python <skill-root>/scripts/run_worldguard.py task-model depth-bind <prediction.yaml> <candidate-identity.yaml> <native-depth.json> --binding-id <id>
python <skill-root>/scripts/run_worldguard.py task-model revalidation-bind <prediction.yaml> <candidate-identity.yaml> <role> <semantic-result.json> <comparison.json> --check-id <id> --semantic-receipt-id <id> --semantic-status <status> --evidence-ref <ref>
python <skill-root>/scripts/run_worldguard.py task-model revision <candidate-revision.yaml>
```

This loop proves only bounded task-local model closure under current declared evidence. It does not prove universal factual truth, future accuracy outside the boundary, installation, or release.

## Canonical contract details

## Task-Local Prediction And Revision

`PredictionSnapshot` is the empirical task-local layer. It does not replace a
`GuardContract`, `ModelMeshContract`, semantic execution, or native predictive
depth. It freezes:

- one exact base world-model id, version, path, and SHA-256;
- one prediction sequence;
- the declared initial state and intervention;
- finite expected numeric values with absolute tolerances;
- expected relationships identified by stable ids and exact
  left/relation/right content; and
- explicit weakening conditions.

The current 0.7 shape always freezes a non-empty task id and purpose, an
independently owned coverage-universe id/source/inventory/fingerprint,
non-empty assumptions and unknowns, a finite iteration budget, and an exact
predecessor. Iteration zero uses the explicit `root` predecessor; later
iterations bind a content-addressed predecessor, exact prior gap ids, and the
latest fingerprint of that exact gap set. Missing
current fields, former shapes, defaulted empty fields, aliases, and fallback
readers are rejected.

A current comparison returns content-addressed observation evidence and input
gaps but never closes the task by itself. It does not accept a gap-transition
map or progress boolean. Exact external-input rows must name their owner,
reason, blocked gap ids, and affected claims.

Every expected value or relationship declares one mismatch category:
`initial_state`, `transition`, `causal_relation`, `resource`, `agent`,
`observation_mapping`, or `other`. The evaluator retains that declared owner;
it does not infer an owner from a target name.

`ObservedWorldSnapshot` must name the prediction, use a strictly later sequence,
retain a non-empty source reference, and carry actual finite values, typed
relationships, or an exact external-input boundary. Its evidence fingerprint
is recomputed from that complete payload. Missing declared expectations are
mismatches; they cannot be silently treated as unobserved success.

`CandidateWorldModelRevision` binds separate current base and candidate
artifacts. A candidate path or content hash equal to v1 is invalid because it
cannot be rolled back independently. Acceptance requires an exact declared
revalidation inventory containing both:

- `original_scenario`; and
- `real_holdout_observation`.

Candidate evaluation also consumes one
`worldguard_task_local_native_depth_receipt`. WorldGuard creates this binding
from the exact native `worldguard.native_depth.v2` receipt plus the task,
candidate, and independent coverage fingerprint. This source type is produced by the native mesh owner: supply the current candidate as a native `ModelMeshContract` mapping (or the existing depth-fixture mapping containing `mesh`). Other model kinds remain unsupported by this binder. The binder reads the candidate and validates the complete producer shape, current mesh/coverage fingerprints, numeric coverage, and license consistency; it reuses the recorded execution without rerunning the mesh. The existing outer binding retains the exact task and independent coverage-universe identity. State, transition, branch,
perturbation, intervention, counterfactual, and holdout gaps are derived from
that receipt. Caller-authored remaining-gap lists have no authority, and a
native receipt with `predictive_claim_licensed: false` remains open even if its
raw gap list is empty.

Each revalidation binds the exact task/candidate, a typed content-addressed
semantic receipt, and a sealed `worldguard_observed_world_comparison_receipt`.
There must be exactly one original and one real holdout. Their observation id,
source, evidence fingerprint, and content fingerprint must differ, and
the holdout fingerprint cannot appear in candidate-construction evidence.
Semantic `PASS` text without the complete current native `SemanticExecutionReceipt` in `source_result.native_receipt` is invalid. The validator binds its registered executor, consumed inputs, and actually executed scenario/holdout ids to the current candidate. One recorded native execution may be reused for both roles only when it covers both scopes; it never substitutes for the two independent empirical observations. Depth closure receipts retain their native `semantic_receipts` so the existing predictive assessment can rederive all nested coverage and license values without rerunning the owners. Older receipts lacking these execution sources are insufficient for task closure.

The evaluator computes input, resolved, persisted, introduced, and current gap
ids. A new gap continues, an unchanged or repeated gap fingerprint stalls, and
the finite iteration limit blocks. `model_closed_for_task` is emitted only by
the sole task-local owner after native predictive license, zero current gaps,
and both independent revalidations pass.

The evaluator is read-only. A passing candidate is `accepted`; a failed
unapplied candidate is `rejected`; a failed applied candidate is `rolled_back`
only when its rollback identity exactly equals the still-current v1. These
dispositions modify no WorldGuard code, core threshold, installed skill, or
reusable default.
