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
2. Add only the inputs each row needs: `holds`/`before` -> `events`, `place` -> `resources`, spatial rows -> `spatial_relations`, `variable` -> `causal_model`. An event with an `actor` says where it happens (`place`) and what the actor uses (`uses`, `[]` when nothing), and `world_model.relations` says which fluent means who holds what (`{holds: [Lena, key]}`) and who is where (`{at: [Lena, island]}`); WorldGuard derives those preconditions and replays them (`EVENT_RELATION_UNMET`), so do not rely on `requires` or fluent names for them. A missing place, use or relation is GAP; once any relation is declared every event names its actor; write `actor_state_free: <reason>` when an event truly depends on neither. Read `scope_limits`: it lists what the declarations cannot reach (a world with no actor and no relation; an event changing facts no relation ties to anyone, whose place is then checked only for the people and things it names).
3. Give each must-hold row a `variants:` edit that must fail with its `code`.
4. Several chapters or days: a tree whose root holds only claim rows (`node:` reads descendants), one node each, joined in reading order by `continues`.
5. A chapter or day not written yet is a node without `contract` (`GAP planned`); add the contract once written.
Read it back (`timeline` / `mesh-check`) after every edit.

When one world gets too big, split it into a tree of contracts over time (a root that holds only claim rows, one node per chapter or day, joined in order by continues), and give each world only the inputs its rows need, so only the Guards the target needs run.

## The model tree

- Node: one world contract (claim, world_model, inputs); a failing node shows its counterexample: the failed event or constraint with its timeline prefix.
- Parent: a mesh edge `relation: parent_child` (root rows read descendants with `node:`); `continues` hands state and time to the next node.
- Known-bad: `variants:` in a contract or a mesh; each one must fail with its `code`.
- Real binding: `claim.asserts` rows checked against the model; an event with an actor names its `place` and `uses`, checked against `world_model.relations` (`EVENT_ACTOR_STATE_UNCHECKED`, `EVENT_RELATION_UNMET`, or `actor_state_free: <reason>`); `source:` only points at the original text and is not checked.
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
| Discuss one character, thing or place | `lifeline --mesh mesh.yaml --of Lena` (or `--contract`); example: story `--of key` | [model-mesh.md](references/model-mesh.md) |

Copy `assets/examples/` worlds; [guard-inputs.md](references/guard-inputs.md) covers the
seven Guards and the clock, token and space rules. Unknown semantics GAP; retired fields
are input errors. A mesh has one root and only `parent_child` / `continues` edges (`from` / `to`).

## Discuss with a picture; keep contradictions open

When you discuss the plot with the owner (a contradiction to decide, how someone gets somewhere, an alternative), run
`lifeline --mesh FILE --of <who or what>` and put its Mermaid picture and its "Shown" and "Left out" lines in your reply.
The tool draws it from the declared relations and the replayed events, only for that entity, from its first to its last
appearance; do not draw one by hand. `check`, `mesh-check`, `timeline` and `lifeline` record each FAIL, with the
chapters and sources that established it, in `.worldguard/open.json` (the checked file's folder, or the nearest folder
above it that has one); every later command on a file under that folder prints the open ones on stderr. One closes
only when the check that found it asks the same question of its file again and gets a pass; while that check does not
reach it (no declared relation or actor, an untimed event, a GAP, an `actor_state_free`, a Guard that no longer runs)
it stays open as "not re-checked", so never exempt, strip or delete facts to make one go away. Renaming, moving or
deleting the file closes nothing either: the entry says the file is gone until the same contradiction is found under
the new path, and a pass in another file of the same world closes nothing. Run the `--takes-over` command the entry
names only when the owner confirms that file is the gone one under a new path.
End a reply that leaves one open with it under "still open".

## Read the result

FAIL > GAP > BOUNDARY_EXCEEDED > PASS; PASS is scoped and every child contributes. Exit
codes and summary keys: "Results" in worldguard-contracts.md. Report status, codes,
differences or missing inputs, trace and scope limits.
