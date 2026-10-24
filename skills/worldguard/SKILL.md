---
name: worldguard
description: "Use for checking that a story, trip, plan or process is consistent: write it as a small executable world model (events, agents, places, resources, causes, norms) and bind each claim to it with assertions that are checked. Not for software code or its behavior; use flowguard."
---

# WorldGuard

Check explicit worlds and `claim.asserts`, never claim prose. Missing assertions
are GAP; a consistent model does not establish factual truth.

- Node: one world contract (claim, world_model, inputs); a failing node shows its counterexample: the failed event or constraint with its timeline prefix.
- Parent: a mesh edge `relation: parent_child` (root rows read descendants with `node:`); `continues` hands state and time to the next node.
- Known-bad: `variants:` in a contract or a mesh; each one must fail with its `code`.
- Real binding: `claim.asserts` rows checked against the model; `source:` only points at the original text and is not checked.
- Test binding: `compare --contract|--mesh --observed` checks the plan against what really happened.
- Readback: `timeline` (text; `--json`) and the `tree` lines of `mesh-check`.
- Current vs target: the contract or mesh file is the current model; an edited copy is the target and replaces the file when the same checks pass; `compare --write-observed` writes such a copy from observations.

## Choose a command

Run `python <skill-root>/scripts/run_worldguard.py ...`:

| Request | Arguments | Read |
|---|---|---|
| Check one world | `check --contract world.yaml`; examples: scene, trip | [worldguard-contracts.md](references/worldguard-contracts.md) |
| Check one tree | `mesh-check --mesh mesh.yaml`; example: story | [model-mesh.md](references/model-mesh.md) |
| Compare observations | `compare --contract world.yaml --observed log.yaml`; use `--mesh` for a tree | [worldguard-contracts.md](references/worldguard-contracts.md) |
| Read a world or tree | `timeline --contract world.yaml` or `--mesh mesh.yaml`; examples: scene, trip, story | [worldguard-contracts.md](references/worldguard-contracts.md) |

Copy `assets/examples/` worlds; [guard-inputs.md](references/guard-inputs.md) covers
the seven Guards. Semantics and assertion kinds derive checks; unknown semantics
GAP. Retired fields are input errors: remove the named field.

Use one clock format, quoted clocks and ISO times across days. Event times supply
`t_<event_id>` in causal expressions. Every token transfer names its event when
events exist; same-named places and fluents must agree. A mesh has one root and
only `parent_child` / `continues` edges using `from` / `to`.

## Read the result

Keep FAIL > GAP > BOUNDARY_EXCEEDED > PASS; PASS is scoped. Every child contributes.
Check/mesh exit 0 on PASS, 1 on non-PASS, 2 on invalid input. Compare exits 0 for all
matches, 1 for mismatches, 2 on invalid input. `--write-observed OUT` writes a new
independent world/tree with only compared event times changed; rerun its checks.

Check summaries are short JSON: `contract_id`, `status`, `checked`, `gaps`,
`scope_limits`; mesh summaries also show `tree`. Add `--json` for full reports.
Timeline defaults to text; `--json` preserves the complete view and `--scenario id`
selects a contract scenario. It reads state and problems rather than proving closure.
Report status, codes, observed differences or missing inputs, trace and scope limits.
