---
name: worldguard
description: "Use for checking that a story, trip, plan or process is consistent: write it as a small executable world model (events, agents, places, resources, causes, norms) and bind each claim to it with assertions that are checked. Not for software code or its behavior; use flowguard."
---

# WorldGuard

Check explicit worlds and cited original passages. Missing `claim.asserts` are GAP;
a consistent model does not establish factual truth or arbitrary prose understanding.

## Start from the model

Run `python <skill-root>/scripts/run_worldguard.py ...`. With a world or tree, read it first:
`timeline --contract FILE` or `timeline --mesh FILE` (a tree also `mesh-check --mesh FILE`);
name the claim rows, events and nodes the request concerns and work on them.
For a new story or trip, build the model in five steps:
1. Write the claim rows that must hold (`claim.asserts`). Declare original files with `texts: {ch: chapter.md}`; each event uses a pointer such as `source: ch p3 "quoted words"` or `tt r3 arr`, not an unchecked description. Use aliases only for known names. See [source and value inputs](references/worldguard-contracts.md).
2. Add only the inputs each row needs: `holds`/`before` -> `events`, `place` -> `resources`, spatial rows -> `spatial_relations`, `variable` -> `causal_model`. An event with an `actor` says where it happens (`place`) and what the actor uses (`uses`, `[]` when nothing), and `world_model.relations` says which fluent means who holds what (`{holds: [Lena, key]}`) and who is where (`{at: [Lena, island]}`); WorldGuard derives those preconditions and replays them (`EVENT_RELATION_UNMET`), so do not rely on `requires` or fluent names for them. A missing place, use or relation is GAP; once any relation is declared every event names its actor; write `actor_state_free: <reason>` when an event truly depends on neither. Read `scope_limits`: it lists what the declarations cannot reach (a world with no actor and no relation; an event changing facts no relation ties to anyone, whose place is then checked only for the people and things it names).
3. Give each must-hold row a `variants:` edit that must fail with its `code`.
4. Several chapters or days: a tree whose root holds only claim rows (`node:` reads descendants), one node each, joined in reading order by `continues`.
5. A chapter or day not written yet is a node without `contract` (`GAP planned`); add the contract once written.
Read it back (`timeline` / `mesh-check`) after every edit.

## The model tree

- Node: one world contract (claim, world_model, inputs); a failing node shows its counterexample: the failed event or constraint with its timeline prefix.
- Parent: a mesh edge `relation: parent_child` (root rows read descendants with `node:`); `continues` hands state and time to the next node.
- Known-bad: `variants:` in a contract or a mesh; each one must fail with its `code`.
- Real binding: claims use the model; actor events declare `place`, `uses` and their relations. With `texts`, source pointers check the original time, named participants, codes and quantities; definite differences are red, unreadable parts grey. The text edits are also checked through the real world evaluator.
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

For a plot discussion run `lifeline --mesh FILE --of ENTITY` and include its generated Mermaid picture,
"Shown" and "Left out" lines. Do not draw a substitute. `check`, `mesh-check`, `timeline` and `lifeline`
keep failures in `.worldguard/open.json` beside the checked file or in its nearest ancestor record.
A matching check closes a finding only after re-checking it. Missing declarations, untimed events,
GAP or `actor_state_free` leave it not re-checked. Do not remove facts to close it.
A renamed or missing file stays open; a matching failure in exactly one file of the same world moves
its record, preserving history. A pass in another draft does not close it. Use the record's
`--takes-over` command only when the owner confirms that file is the missing one under a new path.
End a reply with any remaining contradictions under "still open".

## Read the result

FAIL > GAP > BOUNDARY_EXCEEDED > PASS; PASS is scoped and every child contributes. Exit
codes and summary keys: "Results" in worldguard-contracts.md. Report status, codes,
differences or missing inputs, trace and scope limits.
