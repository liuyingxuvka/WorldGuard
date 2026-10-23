---
name: worldguard
description: "Use for checking that a story, trip, plan or process is consistent: write it as a small executable world model (events, agents, places, resources, causes, norms) and bind each claim to it with assertions that are checked. Not for software code or its behavior; use flowguard."
---

# WorldGuard

Run a small executable world model and bind each claim to it with `claim.asserts`.
WorldGuard checks the model and those rows; it never reads the claim sentence.
A consistent model does not establish factual truth. Missing assertions are GAP.

A mesh is one model tree: story/trip → chapter/day → scene/segment; each node is a world contract.
Its five abilities are structure (contracts and timeline), counterexamples (failed events or constraints
with their timeline), known-bad variants (`variants:`) that must fail, binding to real material
(`claim.asserts` and `source:`), and binding to tests (assertion rows and variants).
Checks nest along the tree; parent rows may read descendants with `node:`.
Read the checked tree with `python <skill-root>/scripts/run_worldguard.py mesh-check --mesh mesh.yaml --json`.

## Choose a command

Run `python <skill-root>/scripts/run_worldguard.py ...`:

| Request | Arguments | Read |
|---|---|---|
| Check one world | `check --contract world.yaml` | [worldguard-contracts.md](references/worldguard-contracts.md) |
| Check one model tree | `mesh-check --mesh mesh.yaml` | [model-mesh.md](references/model-mesh.md) |
| Compare plan and observations | `compare --contract world.yaml --observed observed.yaml` | [worldguard-contracts.md](references/worldguard-contracts.md) |
| Read back a world | `timeline --contract world.yaml [--scenario id]` | [worldguard-contracts.md](references/worldguard-contracts.md) |

Start from `check --example scene` or `--example trip`, or copy a world from
`assets/examples/`. Load [guard-inputs.md](references/guard-inputs.md) for fields,
copyable input blocks and boundaries of the seven internal Guards: Event, Agent,
Space, Resource, Causal, Conflict and Norm. Claim semantics and assertion kinds
select the checks; `target_guards` cannot shrink that set. Unknown semantics GAP.

Use one clock format per contract, with quoted clocks and ISO times across days.
World events drive `t_<event_id>` in causal expressions and linked token transfers.
Use `variants:` for edits that must fail and `source:` for original text locations.

## Read the result

Keep PASS, FAIL, GAP and BOUNDARY_EXCEEDED distinct. Failures take priority over gaps,
then boundaries, then pass. PASS applies within the stated model scope. Every child
contributes to a mesh; a passing root cannot hide a non-passing child.

Check/mesh exit 0 on PASS, 1 on non-PASS, 2 on invalid input. Compare exits 0 for all
matches, 1 for mismatches, 2 for invalid input. Timeline returns a view, not closure.
Default check summaries contain `status`, `checked`, `gaps`, `scope_limits` and the
contract id where applicable. Add `--json` only when full node/Guard rows are needed.
Report status, each gap's code, and a false assertion's `observed` value or named
missing input, plus scope limits. Use the timeline for the failing event/constraint;
avoid copying internal report fields into prose.
