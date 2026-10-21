# Task-Local Fact Revision

Use this route only beneath the existing task-local world-revision owner when
support for named facts is incomplete, contradictory, or needs retraction.
It is not another Guard, belief database, truth service, or alternate
WorldGuard entrypoint.

## State Semantics

Fact state is four-valued:

- `true`: positive support exists and negative support does not;
- `false`: negative support exists and positive support does not;
- `both`: both signs have independent support;
- `neither`: neither sign has support.

These are proposition-support states. They are not the WorldGuard Guard
terminals `PASS`, `FAIL`, `GAP`, or `BOUNDARY_EXCEEDED`. `both` does not cause
explosion, and `neither` is not closed-world falsity.

## Transaction

1. Freeze one `FactWorldSnapshot` with stable fact, support, rule, source, and
   evidence ids.
2. Express additions and retractions in one `FactRevisionTransaction` bound to
   the exact base fingerprint, task id, sole
   `worldguard.task_local_world_revision` owner, iteration, and predecessor.
3. Name every fact whose state must be preserved and every expected terminal
   state delta.
4. Preview on a copy. Inspect closure termination, changed support ids, rule
   chains, contradictions, preservation outcomes, and the preview fingerprint.
5. Activate only that current preview. Acknowledge the exact contradiction
   set and bind at least one current regression and one current holdout receipt
   to the preview fingerprint. Bind the activation request to the same task,
   owner, and exact candidate fact-model fingerprint.
6. Treat successful activation as an intermediate candidate handoff. Its only
   successful terminal is `task_local_revalidation_required`; rerun the
   prediction, the candidate mesh, the original scenario, and the independent
   real holdout through the same task-local owner.

Retraction removes a support id, not a fact. Strict rules derive only their
declared signed consequent when all signed antecedents have support. Missing
support does not synthesize negative support.

## Activation Gates

Activation blocks when the base or preview fingerprint is stale, closure did
not terminate, a preserved fact changed, an expected delta is wrong, the
visible contradiction set was not acknowledged, regression or holdout
evidence is missing/stale/non-pass, or the transaction was already activated.
The activation result returns a new immutable task-local snapshot and receipt;
it never mutates WorldGuard code, installed skills, Guard rules, reusable
defaults, or a global fact store. It never emits `model_closed_for_task`, even
when its local fact regression and holdout evidence pass.

## Commands

```bash
python <skill-root>/scripts/run_worldguard.py task-model fact-revision-preview <base.yaml> <transaction.yaml>
python <skill-root>/scripts/run_worldguard.py task-model fact-revision-activate <base.yaml> <transaction.yaml> <activation.yaml>
```

## Canonical contract details

### Fact-level transaction

`FactWorldSnapshot` and `FactRevisionTransaction` are a subordinate form of
the same task-local revision owner. `FactSupport` records one independent
positive or negative support with stable source and evidence ids.
`StrictFactRule` derives only one declared signed consequent when every signed
antecedent has support. The resulting fact state is `true`, `false`, `both`,
or `neither`; these values are not Guard terminal statuses.

Preview is copy-based and returns the exact base/candidate fingerprints,
support and rule-chain deltas, contradiction ids, preserved-fact outcomes,
closure status, and preview fingerprint. Activation requires that fingerprint,
the exact visible contradiction set, and current `regression` plus `holdout`
evidence bound to the preview. A stale base, changed preserved fact, missing
evidence, or prior activation of the transaction remains blocked.

The fact transaction and activation request also bind the same task, the sole
`worldguard.task_local_world_revision` owner, iteration, predecessor, preview,
and candidate fingerprint. Successful activation ends only at
`task_local_revalidation_required`; the task-local owner must rerun prediction,
native depth, original, and independent holdout evidence before closure.
