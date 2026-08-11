# WorldGuard Entry Routing

Use this reference immediately after the public `worldguard` entry admits a task. It owns prompt loading only; WorldGuard runtime contracts still own semantic behavior.

## 1. Extract typed task facts

Preserve a source span for every extracted fact. Do not treat a keyword as a route decision.

- `task_shape`: one required current value—`unit_contract`, `model_mesh`, `world_blueprint`, `task_local_revision`, or `template_pack`—supported by the preserved request source spans.
- `claim_facts`: claim id/text, structured atoms, requested semantics, predictive intent, and any caller-supplied `target_guards`.
- `input_facts`: concrete world-model fields, models/edges/handoffs, task/coverage/predecessor identities, or template parameters/validator identities.
- `boundary_facts`: explicit unavailable providers, unsupported semantics, missing evidence, and requested claim scope.

If a fact is absent, record it as missing. Do not invent it and do not ask the AI whether it understands.

## 2. Select exactly one public task shape

Read `task_shapes` in `internal-guard-routes.json` and evaluate its declared applicability, forbidden facts, and required inputs.

The topology keeps three input meanings separate. A task shape's `required_input_fields` is the minimum admission surface for selecting that shape. A Guard route's `possible_consumed_input_fields` is the complete field surface that its semantic executor may read on any current legal branch; it is not a list of fields that every run must supply. A terminal semantic receipt's `consumed_inputs` records the concrete values used by that one execution. Do not substitute one layer for another.

- `unit_contract`: one claim checked against one explicit world-model boundary.
- `model_mesh`: multi-node ownership, freshness, handoff, coverage, or closure.
- `world_blueprint`: exactly one target-neutral in-memory hierarchy operation: `create`, `update`, `check`, `impact`, or `trace`.
- `task_local_revision`: compare a frozen prediction/model with later independent observation and revise within a finite task.
- `template_pack`: select and build reusable target-owned WorldGuard scaffolding.

Zero matching shapes is a visible no-match. Several matching shapes is an ambiguity naming the missing discriminators. Never use a score to choose.

## 3. Derive the complete internal Guard set

For unit, mesh, and task-local work, pass the current `claim` object to `worldguard.contracts.derive_guard_requirements`. That native owner returns the denominator, unmapped semantics, and their canonical fingerprint. Unit qualification, mesh qualification, and prompt composition must consume that same result; the prompt composer must not independently derive a semantics-to-Guard selector from route metadata. The result may contain one or several of EventGuard, AgentGuard, SpaceGuard, ResourceGuard, CausalGuard, ConflictGuard, and NormGuard.

`claim.target_guards` is a completeness assertion, not authority to shrink the denominator. Unmapped semantics, a missing derived Guard, missing required inputs, or a forbidden boundary remains visible. Do not retry through another Guard when one route fails.

Prediction semantics intentionally require EventGuard and CausalGuard together. A bounded Guard `PASS` licenses only that Guard's declared semantics.

For `world_blueprint`, route from preserved request source spans, typed `blueprint_operation`, operation-specific identity, and explicit `affected_guard_ids`. The operation must be exactly `create`, `update`, `check`, `impact`, or `trace`. `create` requires target/revision/boundary plus target-material references; `update` requires target/revision/boundary, a current blueprint identity, change intent, and changed ids; `check` requires target/revision/boundary plus the blueprint identity; `impact` requires those identities plus changed ids; `trace` requires those identities plus one trace target. Unknown, absent, mixed, or incomplete operations block. The affected set controls conditional Guard material and must contain only current Guard ids; it is never replaced by keyword matching or an all-Guard load and is not itself evidence that an affected-scope query ran.

Target-object DNA is an in-memory audit lane, not a transport or retrieval route. No export, bundle, materialization root, copied directory, or standalone package is produced. When the requested conclusion is object DNA rather than candidate-model consistency, the route must preserve the external census source derived from frozen raw request/target inputs, the matching current discovery receipt, executable external-test and evidence-alignment receipts, and the caller's exact trusted census-authority or producer-descriptor fingerprint. Producer trust identifies an allowed signer but never replaces the per-revision discovery receipt. Any absent or mismatched gate remains an explicit object-DNA gap and does not block lightweight native modeling.

## 4. Load only the selected material

Always load each selected shape's `reference_path` and each derived Guard's `reference_path`. Load a conditional reference only when its declared trigger is true.

- Unit shape: `worldguard-contracts.md`; each Guard: `guard-model-contract.md`.
- Mesh shape: `model-mesh.md`; add `handoff-contracts.md` only for handoffs.
- World blueprint shape: `world-blueprint.md`; add Guard material only for the explicit affected Guard set.
- Task-local shape or predictive trigger: `task-local-model-deepening.md`; add `fact-revision.md` only for fact support revision.
- Template shape: `template-packs.md`.
- Final authority or reporting only: `model-authority.md` or `closure-report.md`.

Missing mandatory references block the route. Unrelated deep references stay unloaded so the task retains reasoning headroom.

## 5. Start the declared native action

Use the selected shape and Guard capsules' exact `first_native_action`. Preserve `PASS`, `FAIL`, `GAP`, and `BOUNDARY_EXCEEDED` without collapsing them. Prompt selection proves only that the correct instructions were loaded; it never proves semantic execution, factual truth, installation, or release.
