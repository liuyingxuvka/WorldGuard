---
name: worldguard
description: Model-first checks for claims about events, agents, space, resources, causality, conflicts, norms, predictions, model meshes, hierarchical world blueprints, task-local reality revision, or WorldGuard template packs. Use when a conclusion must be licensed by an explicit world model and visible evidence boundary.
---

# WorldGuard

## Purpose

Use WorldGuard to turn a world claim into an explicit, executable, evidence-preserving model check. It keeps one public skill and console while retaining seven complete internal Guard routes.

WorldGuard does not ask the AI whether it understands. Understanding is demonstrated only by a model that makes bounded predictions, exposes missing inputs and counterexamples, survives native checks and independent revalidation, and produces the exact terminal licensed by current evidence.

## Entrypoint Scope

`worldguard` is the sole installed skill and console. EventGuard, AgentGuard, SpaceGuard, ResourceGuard, CausalGuard, ConflictGuard, and NormGuard are internal routes, not child skills, aliases, alternate consoles, or fallbacks.

An internal failure never triggers another Guard as a retry. A multi-semantic claim may legitimately require several Guards; WorldGuard derives the complete set from structured claim semantics.

## Use When

- A bounded claim covers events, agents, space, resources, causality, conflict, norms, or prediction.
- Several models need ownership, freshness, handoff, coverage, or closure analysis.
- A behavior-bearing target needs a hierarchical blueprint, affected-only impact,
  reverse trace, or a bounded in-memory handoff view.
- A finite model must be compared with later observation, revised, scaffolded, or audited.

## Do Not Use When

- The request has no explicit model/evidence boundary.
- Another Guard or writer is expected to repair missing inputs or reinterpret WorldGuard's result.
- A fixture, structural/prompt/repository check is being treated as factual truth, or the task belongs to another Guard family.

## Entrypoint Acceptance Map

Before selecting work, extract typed facts and preserve their source spans:

- one current `task_shape`: `unit_contract`, `model_mesh`, `world_blueprint`, `task_local_revision`, or `template_pack`;
- claim id/text, structured atoms or requested semantics, and predictive intent;
- concrete inputs for the selected shape and every derived Guard;
- explicit unavailable providers, unsupported boundaries, and desired claim scope.

Missing facts remain missing. Do not invent them, use a keyword score as authority, trust `claim.target_guards` to shrink coverage, or record an understanding level.

## Required Workflow

1. Read [references/entry-routing.md](references/entry-routing.md).
2. Select exactly one public task shape from typed facts:
   - `unit_contract` for one claim and one explicit world-model boundary;
   - `model_mesh` for multi-node authority, freshness, handoff, coverage, or closure;
   - `world_blueprint` for exactly one typed in-memory `create`, `update`, `check`, `impact`, or `trace` operation over a hierarchical target-neutral domain blueprint;
   - `task_local_revision` for prediction/observation comparison and finite model revision;
   - `template_pack` for reusable WorldGuard scaffolding.
3. For unit, mesh, or task-local work, pass the claim to `worldguard.contracts.derive_guard_requirements`; consume its full denominator, unmapped semantics, and fingerprint. Never rederive from prompt metadata. Prediction requires EventGuard plus CausalGuard. Blueprint affected Guards remain explicit and never widen to all.
4. Read the selected capsules in [references/internal-guard-routes.json](references/internal-guard-routes.json) and enforce their inputs, actions, references, triggers, and boundaries.
5. Load only mandatory selected material; a missing reference blocks.

Zero matching task shapes, several matching task shapes, unmapped semantics, incomplete derived Guard coverage, forbidden conditions, and missing inputs remain visible. Do not guess or fall back.

## Local Material Routing

- Unit contract: [references/worldguard-contracts.md](references/worldguard-contracts.md).
- Guard purpose/proof and boundaries: [references/guard-model-contract.md](references/guard-model-contract.md), [references/guard-boundaries.md](references/guard-boundaries.md).
- Mesh and optional handoff: [references/model-mesh.md](references/model-mesh.md), [references/handoff-contracts.md](references/handoff-contracts.md).
- World blueprint: [references/world-blueprint.md](references/world-blueprint.md); load affected Guard material only for explicit `affected_guard_ids`.
- Prediction or task-local revision: [references/task-local-model-deepening.md](references/task-local-model-deepening.md).
- Fact-level support revision: [references/fact-revision.md](references/fact-revision.md).
- Reusable scaffolding: [references/template-packs.md](references/template-packs.md).
- Model authority replacement/audit: [references/model-authority.md](references/model-authority.md).
- Final reporting: [references/closure-report.md](references/closure-report.md).

## First native actions

For unit work, derive the complete Guard set, freeze each Guard's task-local purpose, then run its registered native and semantic owners. For mesh work, first inspect all nodes, edges, owners, freshness, handoffs, expected children, and component statuses. The shared launcher accepts `--contract <path>` or `--mesh <path>`.

For `world_blueprint`, preserve request spans and select one current in-memory operation. `create`/`update`/`check`/`impact`/`trace` bind target/revision/boundary and never write a transport artifact. `create` structures supplied material—it does not discover truth. Check replays exact request/material/semantics, a census source derived without the candidate from frozen raw inputs, and a signed census with its matching discovery receipt. It validates hierarchy, interfaces, bindings, cases, Guard execution, external-test execution, evidence alignment, derivations, and continuous depth. Fixtures, candidate-derived censuses, caller hashes, and identity-only test/evidence labels are not target evidence. See [references/world-blueprint.md](references/world-blueprint.md).

Keep `native_domain_qualified` (candidate consistency) separate from `object_dna_qualified`. Object DNA also requires independent census discovery, a current matching receipt, exact integrated-target coverage, real external-test execution, aligned evidence, and caller trust. Exact-authority trust freezes one revision; producer trust allows its producer, but every revision still needs its own receipt bound to frozen raw inputs. Missing any gate leaves only native modeling. The seven-Guard matrix is a capability fixture, never an integrated object.

Blueprint operations compose bounded in-memory views for queries and replay;
they do not prove behavior, truth, or completeness. Keep native, object-DNA,
and cross-artifact handoff separate. Replay preserves census, test/evidence
receipts, trust roots, and gaps. There is no standalone target-DNA package or
fallback; full projection needs a registered independent producer receipt.

DNA has two boundaries: WorldBlueprint is the target-neutral DNA of an external
world/workflow/experiment/policy, while FlowGuard owns WorldGuard's software-DNA
root. Native qualification is not object-DNA qualification; the latter still
needs an independent census, current target evidence, aligned tests, and trusted
authority. FlowGuard projection is on-demand and receipt-bound; ordinary
blueprint operations do not load it, and a stale provider reports a boundary
without disabling native WorldGuard operations.

For prediction, freeze before observation and follow [references/task-local-model-deepening.md](references/task-local-model-deepening.md). For templates, require the target's current native route receipt and reconcile zero/one/many without ranking.

## Terminals

Preserve `PASS`, `FAIL`, `GAP`, and `BOUNDARY_EXCEEDED` exactly. Structural status, semantic status, provider status, rollout status, predictive license, and task-local terminal remain separate facts.

- `PASS` requires current native execution inside the declared boundary.
- `FAIL` preserves the contradicted invariant/expectation and evidence.
- `GAP` names missing required model inputs, coverage, evidence, or derived Guards.
- `BOUNDARY_EXCEEDED` names the unsupported semantics and affected claims.

For task-local revision, preserve `progress_stalled`, `iteration_limit`, and `external_input_required`; only the same task-local owner may emit `model_closed_for_task` from zero current gaps plus current native depth and independent original/holdout revalidation.

## Hard Gates

- No narrative-only `PASS` and no model self-rating.
- No child Guard skill, alias, fallback, or retry replacement.
- No caller-authored Guard subset, remaining-gap list, progress boolean, or PASS string as authority.
- No family fixture in place of task-local good/bad proof; no `admission_bad` without an exact parser rejection observation.
- No whole-mesh `PASS` from one child or structural-only evidence.
- No predictive license from field presence, a single event, clustered timepoints, aggregate coverage that hides a shallow node/variable, or incomplete scenarios/holdouts/interventions/counterfactuals.
- No semantic provider skip hidden as pass.
- No unknown blueprint member, duplicate owner, schema-free compatibility, unaccounted output, caller-shrunk branch/cache/census, candidate-derived census, missing/foreign/stale discovery, manufactured census trust, unsigned/stale census, denominator mismatch, fixture promoted to target, cross-element derivation reuse, carried cache/catalog body, retired codec, decompression overflow, unregistered adapter, blueprint-issued native PASS, missing target purpose, invented test/evidence identity, unexecuted/foreign-input test, false/foreign-support evidence, missing summary derivation, self-attested projection, caller-signed receipt, widened bundle claim, broken interface/mapping, decorative input, role substitution, stale binding, incomplete impact inventory, widening, or query mutation hidden as closure.
- No template zero-match fallback, ambiguous winner, overlapping field ownership, unresolved placeholder, stale registry, or construction without target-native validation.
- No fact activation as task closure; it returns to the same owner for revalidation.
- No stale model authority or release/install claim from source tests alone.

## Output Requirements

Report:

- selected task shape and typed fact sources;
- complete derived Guard set, its canonical derivation fingerprint, and any unmapped/omitted semantics;
- loaded references and skipped references with reasons;
- `evidence`: each native action, exact terminal/status, contracts, ledgers, receipts, fingerprints, task-local lineage, and template identities when used;
- `failures` and `blockers`: missing inputs, gaps, counterexamples, stale evidence, provider state, and boundary findings;
- for blueprint work, report `native_domain_qualified` and `object_dna_qualified` separately, plus independent-discovery status and receipt fingerprint, census authority/producer fingerprints, caller trust result, claim kind, coverage, external-test design/execution status, evidence design/alignment status, unmapped ids, and first gap;
- `skipped_checks`: what did not run and why;
- `residual_risk`: uncertainty that remains after the checks that did run;
- `claim_boundary`: the boundary separating model evidence, factual truth, installation, Git/tag, and release.

Prompt routing proves only that WorldGuard loaded the right current instructions. Domain execution and current immutable evidence are still required for every substantive claim.
