---
name: worldguard
description: "Use for checking that a story, trip, plan or process is consistent: write it as a small executable world model (events, agents, places, resources, causes, norms) and bind each claim to it with assertions that are checked. Not for software code or its behavior; use flowguard."
---

# WorldGuard

Write the world as a small executable model (events, agents, places, resources, causes, norms) and bind the claim to it: `claim.asserts` lists what the claim says as checks on the model, for example `{event: e_unlock, before: e_enter}` or `{variable: slack_h, op: ">=", value: 0}`. WorldGuard checks that the model is consistent (including event `requires` and causal `constraints`) and that every assertion holds in it. It never reads the claim sentence; a claim without `asserts` is `GAP` (`CLAIM_NOT_BOUND`). A consistent model is not proof that the world is factually true.

EventGuard, AgentGuard, SpaceGuard, ResourceGuard, CausalGuard, ConflictGuard and NormGuard are internal checks of this one skill. WorldGuard picks them from `claim.requested_semantics` (`event`, `agent`, `spatial`, `resource`, `causal`, `conflict`, `norm`; `predictive` adds EventGuard and CausalGuard) and from the kinds of `claim.asserts`; `claim.target_guards` is optional. Unknown semantics stay visible as a gap.

## Start

The native CLI commands are `check`, `mesh-check` and `timeline`. Every mesh node is checked once; missing node contracts are gaps. A `predictive` request adds event and causal checks without a separate depth or prediction license.

Pick the shape that fits the request and read its reference. Field formats for every Guard, with copyable examples, are in [guard-inputs.md](references/guard-inputs.md); two complete worlds are in `assets/examples/`. Copy one of these worlds and edit its model and assertions to start a check.

| Shape | Use for | Command: `python <skill-root>/scripts/run_worldguard.py ...` | Reference |
|---|---|---|---|
| `unit_contract` | One claim against one world model | `check --contract <file.yaml>` | [worldguard-contracts.md](references/worldguard-contracts.md) |
| `model_mesh` | Several linked models (scenes, trip legs, handoffs) | `mesh-check --mesh <file.yaml>` | [model-mesh.md](references/model-mesh.md) |

Load [model-authority.md](references/model-authority.md) only for questions about which model owns a fact, and [closure-report.md](references/closure-report.md) only as an optional checklist when reporting a mesh.

Use one time kind per world contract: numbers, one label prefix (`t1`, `t2`), ISO dates/times, or
quoted same-day clocks (`"9:40"`). Use ISO dates across days; `t4b` and mixed kinds are input errors.
When event ids repeat across scenarios, qualify event assertions with `scenario`.
A missing event time prevents ordering only its applicable scenarios; independent known failures remain failures.

Scenario values replace equations for those variables. Constraints and unscoped variable assertions
check every scenario, holdout and declared intervention; `scenario` can select an intervention id.
Write interventions as a list; see the CausalGuard example in the input reference.

A derived Guard's declared unsupported boundary yields `BOUNDARY_EXCEEDED`; a boundary belonging only
to an unselected Guard is a gap with a routing hint. Real `FAIL` and missing-input `GAP` take priority.

## Results

Every check returns `PASS`, `FAIL`, `GAP` or `BOUNDARY_EXCEEDED`. Exit code 0 = `PASS`, 1 = non-pass (read `status` and `gaps`), 2 = input error. Keep the four statuses as they are; `PASS` holds only inside the model's declared scope. One node's or one Guard's `PASS` never licenses a whole mesh or a prediction.

`check` prints a short JSON summary with `contract_id`, `status`, `checked` (Guards and claim rows), `gaps` (one row per problem, each with its `code`) and `scope_limits`. `mesh-check` reports checked node and edge counts and identifies each affected node or edge. Add `--json` for full Guard results and claim rows, or the mesh's `nodes`. A false assertion is `CLAIM_ASSERTION_FALSE` with its `observed` value. Report each problem once with its counterexample or missing slots.

Read a world with `timeline --contract <file.yaml> [--scenario <id>]`. Use `variants:` to declare known-bad edits that must produce the expected non-pass status/code; an escaping variant is `VARIANT_NOT_CAUGHT`. Add `source: "chapter 3 paragraph 12"` to events, transfers, assertion rows or mesh nodes to retain their original location. Syntax is in the unit-contract reference.
