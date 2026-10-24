---
name: worldguard
description: "Use for checking that a story, trip, plan or process is consistent: write it as a small executable world model (events, agents, places, resources, causes, norms) and bind each claim to it with assertions that are checked. Not for software code or its behavior; use flowguard."
---

# WorldGuard

Check explicit worlds and `claim.asserts`, never claim prose. Missing assertions
are GAP; a consistent model does not establish factual truth.

## Start from the model

Run `python <skill-root>/scripts/run_worldguard.py ...`. With a world or tree, read it first:
`timeline --contract FILE` or `timeline --mesh FILE` (a tree also `mesh-check --mesh FILE`);
name the claim rows, events and nodes the request concerns and work on them.
For a new story or trip, build the model in five steps:
1. Write the claim rows that must hold (`claim.asserts`).
2. Add only the inputs each row needs: `holds`/`before` -> `events`, `place` -> `resources`, spatial rows -> `spatial_relations`, `variable` -> `causal_model`.
3. Give each must-hold row a `variants:` edit that must fail with its `code`.
4. Several chapters or days: a tree whose root holds only claim rows (`node:` reads descendants), one node each, joined in reading order by `continues`.
5. A chapter or day not written yet is a node without `contract` (`GAP planned`); add the contract once written.
Read it back (`timeline` / `mesh-check`) after every edit.

## The model tree

- Node: one world contract (claim, world_model, inputs); a failing node shows its counterexample: the failed event or constraint with its timeline prefix.
- Parent: a mesh edge `relation: parent_child` (root rows read descendants with `node:`); `continues` hands state and time to the next node.
- Known-bad: `variants:` in a contract or a mesh; each one must fail with its `code`.
- Real binding: `claim.asserts` rows checked against the model; `source:` only points at the original text and is not checked.
- Test binding: `compare --contract|--mesh --observed` checks the plan against what really happened.
- Readback: `timeline` (text; `--json`) and the `tree` lines of `mesh-check`.
- Current vs target: the contract or mesh file is the current model; an edited copy is the target and replaces the file when the same checks pass; a mesh node without `contract` is a planned part (`GAP planned`); `compare --write-observed` writes an as-happened copy whose checks show what reality broke.

## Choose a command

| Request | Arguments | Read |
|---|---|---|
| Check one world | `check --contract world.yaml`; examples: scene, trip | [worldguard-contracts.md](references/worldguard-contracts.md) |
| Check one tree | `mesh-check --mesh mesh.yaml`; example: story | [model-mesh.md](references/model-mesh.md) |
| Compare observations | `compare --contract world.yaml --observed log.yaml`; use `--mesh` for a tree | [worldguard-contracts.md](references/worldguard-contracts.md) |
| Read a world or tree | `timeline --contract world.yaml` or `--mesh mesh.yaml`; examples: scene, trip, story | [worldguard-contracts.md](references/worldguard-contracts.md) |

Copy `assets/examples/` worlds; [guard-inputs.md](references/guard-inputs.md) covers the
seven Guards and the clock, token and space rules. Unknown semantics GAP; retired fields
are input errors. A mesh has one root and only `parent_child` / `continues` edges (`from` / `to`).

## Read the result

FAIL > GAP > BOUNDARY_EXCEEDED > PASS; PASS is scoped and every child contributes. Exit
codes and summary keys: "Results" in worldguard-contracts.md. Report status, codes,
differences or missing inputs, trace and scope limits.
