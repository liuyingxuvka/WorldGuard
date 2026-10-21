---
name: worldguard
description: Check that a story, trip, plan or process world is consistent by writing it as a small executable model (events, agents, places, resources, causes, norms). For code structure use flowguard.
---

# WorldGuard

Write the world as a small executable model (events, agents, places, resources, causes, norms) and let WorldGuard check that the model is consistent. WorldGuard does not read the claim sentence: every fact the claim depends on must be in the model, for example the order of actions as an ordered `resources.transitions` list. A consistent model is not proof that the world is factually true.

EventGuard, AgentGuard, SpaceGuard, ResourceGuard, CausalGuard, ConflictGuard and NormGuard are internal checks of this one skill. WorldGuard picks them from `claim.requested_semantics` (`event`, `agent`, `spatial`, `resource`, `causal`, `conflict`, `norm`; `predictive` adds EventGuard and CausalGuard); `claim.target_guards` is optional. Unknown semantics stay visible as a gap.

## Start

Pick the shape that fits the request and read its reference. Field formats for every Guard, with copyable examples, are in [guard-inputs.md](references/guard-inputs.md); two complete worlds are in `assets/examples/`.

| Shape | Use for | Command: `python <skill-root>/scripts/run_worldguard.py ...` | Reference |
|---|---|---|---|
| `unit_contract` | One claim against one world model | `check --contract <file.yaml>` | [worldguard-contracts.md](references/worldguard-contracts.md) |
| `model_mesh` | Several linked models (scenes, trip legs, handoffs) | `mesh-check --mesh <file.yaml>` | [model-mesh.md](references/model-mesh.md) |
| `world_blueprint` | A hierarchical world model and change impact | `blueprint check`, `blueprint impact`, `blueprint trace` | [world-blueprint.md](references/world-blueprint.md) |
| `task_local_revision` | Compare a frozen prediction with a later observation | `task-model freeze`, `task-model compare`, `task-model revision` | [task-local-model-deepening.md](references/task-local-model-deepening.md) |
| `template_pack` | Optional: scaffold a single-Guard contract | Python API | [template-packs.md](references/template-packs.md) |

Load [fact-revision.md](references/fact-revision.md) only when the support of a fact changes, [model-authority.md](references/model-authority.md) only for questions about which model owns a fact, and [closure-report.md](references/closure-report.md) only as an optional checklist when reporting a mesh.

## Results

Every check returns `PASS`, `FAIL`, `GAP` or `BOUNDARY_EXCEEDED`. Exit code 0 = `PASS`, 1 = non-pass (read `status` and `gaps`), 2 = input error. Keep the four statuses as they are; `PASS` holds only inside the model's declared scope. One node's or one Guard's `PASS` never licenses a whole mesh or a prediction.

Report the status, the gap codes, and for each non-PASS Guard its errors and counterexample. Do not copy fingerprints or receipts.
