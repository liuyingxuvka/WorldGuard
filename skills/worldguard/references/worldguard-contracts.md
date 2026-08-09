# WorldGuard Contracts

## Contract Layers

`GuardContract` is the unit-level check surface for one claim against one explicit model.

`ModelMeshContract` is the topology-level check surface for multiple model nodes, model edges, authority boundaries, freshness requirements, and handoff closure. It must not replace or bloat `GuardContract`.

## GuardContract

Required canonical fields:

- `contract_id`
- `schema_version`
- `run_id`
- `claim.claim_id`
- `claim.text`
- `claim.target_guards`
- `claim.requested_semantics`
- `claim.atoms[].atom_id`
- `claim.atoms[].text`
- `claim.atoms[].requested_semantics`
- `claim.atoms[].predictive_intent`
- `world_model.model_id`
- `world_model.model_version`
- `world_model.entities`
- `world_model.relations`
- `world_model.assumptions`
- `world_model.scope_limits`
- `inputs.events`
- `inputs.variable_observations` or equivalent signal/time-series observations when predictive variables or signals are exposed
- `inputs.beliefs`
- `inputs.spatial_relations`
- `inputs.resources`
- `inputs.causal_model`
- `inputs.game_model`
- `inputs.norms`
- `dependencies.upstream_results`
- `dependencies.read_only`
- `output_requirements.require_ledgers`
- `output_requirements.require_counterexample_for_non_pass`
- `output_requirements.allowed_status`
- `guard_purpose_declarations` with exactly one task-model-instance declaration
  for every Guard child that may be selected or claim-derived

`guard_purpose_contract` is a runtime-owned field on each formal per-Guard
child candidate. It is derived only from the matching explicit parent
`guard_purpose_declarations` row after the task-local good/bad proof passes; it
is never synthesized from the Guard name. It contains the current family
catalog fingerprint, exact task declaration and proof fingerprints, selected
failure ids, task/run/model/Guard identity, candidate identity, and
freeze/construction sequence. Unit and semantic verifiers reject a missing,
empty, unknown-oracle, incomplete-proof, stale, wrong-instance, or out-of-order
binding before running the Guard proof.

`claim.target_guard` is retired and rejected in normal runtime. Migrate old
files directly to `claim.target_guards` before invoking WorldGuard.

`claim.target_guards` is an execution declaration, not the authority for what
must be checked. The sole `worldguard.contracts.derive_guard_requirements`
owner maps structured atom semantics to their owning Guards and returns the
canonical denominator, unmapped semantics, and derivation fingerprint. Unit,
mesh, and prompt routing consume that same result rather than maintaining
parallel selectors. WorldGuard compares the derived set with the declared set. Missing derived
routes fail closed. Claims without current `requested_semantics` or structured
atoms are rejected; the caller's target list is never used as a fallback
authority.

Likewise, `semantic_coverage.expected_model_node_ids` is a completeness
assertion over the mesh-discovered node inventory. It cannot shrink that
inventory. `excluded_model_nodes` requires a reason plus closed disposition and
is valid only for a discovered non-critical node that contributes to neither
execution coverage nor covered claim scope.

## Guard Model Adequacy Contract

Contract shape alone does not prove that a Guard model is meaningful. The
family catalog must exhaust native runtime failure codes, while each real task
child separately declares:

- the invalid claim class the Guard prevents;
- the boundary it deliberately does not license;
- exactly one task-local native good case;
- a non-empty one-or-many selection from the source-discovered Guard-owned unit
  and semantic failure codes;
- exactly one task-local native bad case for every selected failure; and
- an oracle that observes the exact expected status and single stable code.

The current declaration and executable oracle live in
`worldguard.guard_model_contract`; the human-readable ownership table is in
`guard-model-contract.md`. A changed literal Guard-owned failure code changes
the family oracle catalog and must be reconciled before a task may select it.
The family catalog never automatically becomes a real child's declared
purpose. Mesh registration and provider-lifecycle codes remain separately owned
and cannot be counted as individual-Guard coverage.

## GuardResult

Required canonical fields:

- `result_id`
- `contract_id`
- `guard`
- `status`
- `supported_claims`
- `rejected_claims`
- `missing_slots`
- `boundary_exceeded`
- `errors`
- `counterexamples`
- `ledgers`
- `assumptions_used`
- `scope_limits`
- `consumed_inputs`

For `FAIL`, `GAP`, and `BOUNDARY_EXCEEDED`, require at least one concrete evidence field: missing slots, boundary trace, errors, or counterexamples.

An aggregate or suite-level result is not proof of an individual WorldGuard obligation. Each obligation must retain its own typed `evidence_ref`, and every content-addressed evidence reference must use the exact lowercase content hash produced by its current native owner.

## GuardedReport qualification

`GuardedReport` is the one current unit and mesh-node qualification surface. `worldguard.qualification` derives the full Guard denominator before execution. An extra caller-declared Guard is a denominator error: qualification records a typed gap and executes no structural or semantic owner. After exact reconciliation, each required owner executes once. Mesh aggregation consumes that report read-only; it does not run a second semantic loop.

The report keeps these axes separate:

- declared, derived, effective, omitted, and unexpected Guard ids plus the canonical Guard-derivation fingerprint;
- unmapped semantics with affected claim and atom ids;
- native `GuardResult` rows and semantic execution receipts;
- structural, semantic, provider, rollout/depth, and final statuses;
- provider evidence id, provider id/version/capability, content and receipt fingerprints, target id/revision, contract fingerprint, claim boundary, source, and validation state without interpreting the external payload;
- exact gaps, aggregate read-only ledger, scope limits, target/contract fingerprints, and final qualification fingerprint.

A supplied provider result is one indivisible current envelope. All identity fields are required and must exactly match the active executor, capability, target, revision, contract, and claim boundary; its content and receipt fingerprints must exactly match the current semantic receipt. Missing or mismatched fields produce `STALE` provider evidence and semantic `NOT_RUN`. No field is filled from a native fallback. When no provider result is supplied, the one current native execution receipt derives the evidence identity instead.

A final `PASS` requires every applicable axis to pass and zero gaps. Structural pass may remain visible while missing or stale provider evidence, semantic `NOT_RUN`, an omitted derived Guard, unexpected declaration, unmapped semantics, or unresolved rollout/depth keeps the final result non-pass. Repeated exact inputs and one normalized `QualificationContext` produce one stable result identity for unit and one-node mesh evaluation.

Read `world-blueprint.md` for the separate target-neutral hierarchical blueprint contract. It does not replace `GuardContract`, `GuardedReport`, or `ModelMeshContract`.

## LedgerEntry

Required canonical fields:

- `ledger_entry_id`
- `run_id`
- `claim_id`
- `guard`
- `channel`
- `status_impact`
- `payload`
- `source_refs`
- `read_only_for_downstream`
- `created_at_step`

Every downstream-facing ledger entry must be read-only.

## ModelMeshContract

Read `model-mesh.md` for the canonical mesh fields.

Core rule: child `GuardContract` success is not whole-mesh success. Mesh closure must also preserve child reports and validate model authority, handoffs, freshness, and cycles.

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
candidate, and independent coverage fingerprint. State, transition, branch,
perturbation, intervention, counterfactual, and holdout gaps are derived from
that receipt. Caller-authored remaining-gap lists have no authority, and a
native receipt with `predictive_claim_licensed: false` remains open even if its
raw gap list is empty.

Each revalidation binds the exact task/candidate, a typed content-addressed
semantic receipt, and a sealed `worldguard_observed_world_comparison_receipt`.
There must be exactly one original and one real holdout. Their observation id,
source, evidence fingerprint, content fingerprint, and semantic source
fingerprint must differ, and
the holdout fingerprint cannot appear in candidate-construction evidence.
Semantic `PASS` text without the typed source receipt is invalid.

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
