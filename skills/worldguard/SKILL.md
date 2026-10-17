---
name: worldguard
description: Model-first checks for claims about events, agents, space, resources, causality, conflicts, norms, predictions, model meshes, hierarchical world blueprints, task-local reality revision, or WorldGuard template packs. Use when a conclusion must be licensed by an explicit world model and visible evidence boundary.
---

# WorldGuard

Check a world claim against an explicit executable model. Keep model consistency, empirical evidence, factual truth, and software/publication identity separate. Existing models run directly through their native owners; ordinary use needs no checker-purpose declaration or good/bad proof ceremony.

WorldGuard is the single public skill and console. EventGuard, AgentGuard, SpaceGuard, ResourceGuard, CausalGuard, ConflictGuard, and NormGuard are internal semantic owners. A failure preserves its own result; another Guard is not a retry.

## Start

Read [entry-routing.md](references/entry-routing.md). Preserve the request's source spans, claim semantics, model/input identities, requested scope, and missing evidence. Select exactly one shape:

| Shape | Work | Selected reference |
|---|---|---|
| `unit_contract` | One claim and current world model | [worldguard-contracts.md](references/worldguard-contracts.md) |
| `model_mesh` | Multiple nodes, authority, freshness, handoff, coverage | [model-mesh.md](references/model-mesh.md) |
| `world_blueprint` | One in-memory `create`, `update`, `check`, `impact`, or `trace` operation | [world-blueprint.md](references/world-blueprint.md) |
| `task_local_revision` | Frozen prediction, later observation, finite model revision | [task-local-model-deepening.md](references/task-local-model-deepening.md) |
| `template_pack` | Select and compose reusable WorldGuard scaffolding | [template-packs.md](references/template-packs.md) |

For unit, mesh, and task-local claims, call `worldguard.contracts.derive_guard_requirements` and consume its full denominator, unmapped semantics, and fingerprint. `claim.target_guards` cannot shrink that set. Prediction requires EventGuard plus CausalGuard. Read the selected capsules in [internal-guard-routes.json](references/internal-guard-routes.json) and their selected Guard reference. Missing inputs or mandatory references, no matching shape, several shapes, and unknown semantics remain explicit blockers.

## First native action

For a current unit contract, execute `run_worldguard` directly; qualification reconciles the complete Guard set and runs the structural and semantic owners. The portable launcher is `python <skill-root>/scripts/run_worldguard.py check --contract <contract.yaml>`. For mesh, inspect declared nodes/edges and run `mesh-check`; add [handoff-contracts.md](references/handoff-contracts.md) only for handoffs.

For a blueprint, retain the exact target/revision/boundary and operation-specific identity. Read only its selected reference and explicit `affected_guard_ids`. Actual behavior cases and external tests remain executable evidence, not a checker-understanding exercise. Keep `native_domain_qualified` separate from `object_dna_qualified`: the latter needs independent frozen-input census discovery, current signed discovery, caller trust, exact target coverage, real external-test execution, and aligned evidence. Missing object-DNA evidence leaves native modeling available. Optional FlowGuard projection needs its independent registered provider; missing/stale provider remains a boundary.

For prediction, freeze before observing and load task-local deepening. Add [fact-revision.md](references/fact-revision.md) only for fact-support revision. Templates construct and validate shape/routes; follow them with the selected world check. Model-authority and final-reporting references are conditional on those operations.

## Results and limits

Preserve `PASS`, `FAIL`, `GAP`, and `BOUNDARY_EXCEEDED`. Keep structural, semantic, provider, rollout/depth, predictive-license, and task-local results separate. `PASS` requires current native execution within the declared boundary. Preserve missing inputs, contradictions, counterexamples, stale identities, unavailable providers, and unsupported scope.

One child or field presence cannot license a whole mesh or prediction. Preserve each node/variable's current depth, time coverage, branches, perturbations, interventions, counterfactuals, and holdouts where applicable. Blueprint checks preserve hierarchy, interfaces, role-separated bindings, actual behavior/output/effect cases, census trust, and affected-only query semantics. Template zero/many matches, stale identity, overlapping ownership, and unresolved slots block. Fact activation returns to the same task-local owner; only that owner can close a task after zero current gaps and independent original/holdout revalidation. No task modifies global defaults or installed rules.

Report the selected shape/source facts, derived Guard set/fingerprint, native actions and exact statuses, evidence identities and boundaries, failures/gaps, skipped checks, and residual uncertainty. For blueprint work report native and object-DNA qualification separately. Never promote prompt loading, family regression fixtures, source tests, or model consistency into factual truth, installation, or Release evidence.
