# WorldGuard Contracts

`GuardContract` checks one claim against one current explicit world model. `ModelMeshContract` adds multi-node topology, authority, freshness, handoffs, and per-node checks; read `model-mesh.md` only for that shape.

## Unit input

A contract needs `claim` and `inputs`; add `world_model` (`model_id`, `model_version`, `assumptions`, `scope_limits`). `contract_id` defaults to the claim id and `model_version` to `unversioned`; `schema_version`, `run_id`, `dependencies` and `output_requirements` have defaults. The claim carries `claim_id`, a descriptive `text` (never parsed), `asserts` (what the claim says, one check on the model per row; the row for each Guard is in [guard-inputs.md](guard-inputs.md)) and structured `requested_semantics` or `atoms` (each atom: `atom_id`, `text`, `requested_semantics`, `predictive_intent`). Supply the input fields consumed by each derived Guard, not every possible field:

| Guard | Current model/input family |
|---|---|
| EventGuard | Events, time/order, fluent changes and declared scenarios |
| AgentGuard | Agents, beliefs, intentions, knowledge |
| SpaceGuard | Spatial objects/relations |
| ResourceGuard | Resources, quantities, units and constraints |
| CausalGuard | Variables, graph/equations, scenarios and declared interventions/counterfactuals |
| ConflictGuard | Agents, actions, payoffs and conflict model |
| NormGuard | Norms, facts and rule priorities |

Field formats and copyable examples: [guard-inputs.md](guard-inputs.md). Missing consumed inputs produce typed gaps.

WorldGuard derives the Guards from the claim semantics and the kinds of `claim.asserts`. `claim.target_guards` is optional: it never shrinks or blocks the derived set; `derived_guards` names the executed set. `claim.target_guard` is retired. Prediction derives EventGuard plus CausalGuard. Unknown semantics do not fall back to the caller's Guard list; they stay visible as `QUALIFICATION_SEMANTIC_UNMAPPED`.

Run a contract with `python <skill-root>/scripts/run_worldguard.py check --contract <file.yaml>`, or `run_worldguard(contract)` in Python.

## Results

Each Guard runs its complete native checks once and returns `guard`, `status`, `errors`, `counterexamples` and `missing_slots`. Boundaries do not skip other checks. Aggregate status preserves the order `FAIL`, `GAP`, `BOUNDARY_EXCEEDED`, `PASS`.

The default summary contains `contract_id`, `status`, `checked`, `gaps` (one row per problem) and `scope_limits`. `checked` names the Guards and counts claim rows. Add `--json` for `guard_results`, `claim_binding`, `derived_guards` and `unmapped_semantics`. A missing assertion is `GAP` `CLAIM_NOT_BOUND`; a false assertion is `FAIL` `CLAIM_ASSERTION_FALSE`; an unresolved assertion is `GAP` `CLAIM_ASSERTION_UNRESOLVED`. Each problem carries its native code and its counterexample or missing slots. Legacy `dependencies` and `output_requirements` input mappings do not change the result.

## Runnable world

Save this as `world.yaml`; `check --contract world.yaml` returns PASS. It has three
events, two claim rows and one variant that must fail:

```yaml
contract_id: door_visit
claim:
  claim_id: entered_after_unlock
  requested_semantics: [event, causal]
  asserts:
    - {event: e_unlock, before: e_enter}
    - {holds: iris_inside, at: t3}
world_model: {scope_limits: [illustrative sequence]}
inputs:
  event_model: {initial_states: [iris_has_key, door_locked]}
  events:
    - {event_id: e_give_key, at: t1, source: paragraph 1, requires: [iris_has_key], initiates: [mara_has_key], terminates: [iris_has_key]}
    - {event_id: e_unlock, at: t2, source: paragraph 2, requires: [mara_has_key, door_locked], initiates: [door_open], terminates: [door_locked]}
    - {event_id: e_enter, at: t3, source: paragraph 3, requires: [door_open], initiates: [iris_inside]}
  causal_model:
    variables: [entry_gap]
    equations: {entry_gap: "t_e_enter - t_e_unlock"}
    scenarios: {base: {}}
    constraints: ["entry_gap >= 0"]
variants:
  - id: key_given_too_late
    code: EVENT_PRECONDITION_UNMET
    set: {"inputs.events[e_give_key].at": t4}
```

## Known-bad variants and the timeline

Each variant id must be unique; `expect` is `FAIL` (default), `GAP` or `BOUNDARY_EXCEEDED`. `code` is optional. `set` replaces existing values, `remove` lists existing fields/items, and `add` maps list paths to lists of appended items. Dot-separated keys, numeric list indices (`[0]`) and exact list ids (`[e_give_key]`, matching `id` or any `_id` field) are supported. Invalid or ambiguous paths are input errors naming the variant. Edits affect an independent in-memory copy with its variants removed. Each result must match status and optional code; otherwise `VARIANT_NOT_CAUGHT` blocks PASS. `checked.variants` gives the count, including for mesh-node contracts.

`timeline --contract <file> [--scenario <id>]` reads the initial state and every event's resulting fluents, token markings and problem codes; `variables` contains completed scalar runs. Linked transfers follow their events; unlinked transfers appear on the last step. Timeline ordering requires each applicable event to have a time. The timeline uses the same native replay functions and introduces no new validation rules.

Optional string `source` fields on events, transitions, assertion rows and mesh nodes survive on their problem rows. Full event counterexamples include `trace` (time and event id through the failed event); summaries omit the prefix.

## Compare the world with observations

Run `python <skill-root>/scripts/run_worldguard.py compare --contract world.yaml --observed observed.yaml`.
For the world above, save this as `observed.yaml`. The command exits 1 and reports
two mismatches: unlock is 0.5 late (tolerance 0.25) and entry_gap differs by -0.5.

```yaml
scenario: base
source: observation log
time_tolerance: 0.25
tolerance: 0.1
events: {e_unlock: t2.5}
variables: {entry_gap: 0.5}
```

Expected values come from the contract's event times and native causal scenario.
A sole causal scenario can be selected implicitly; otherwise name it. Only supplied
observations are compared. ISO/clock differences and time_tolerance use minutes;
numeric/label clocks use their own scale. Variable tolerance uses that variable's unit.
Differences are signed actual minus expected; absolute differences control tolerance.
Output has matches and mismatches with ids, values, differences and tolerances, and
copies optional source unchanged. Exit 0 means all comparisons match, 1 means at
least one mismatch, 2 means an invalid input, unknown id/scenario or mixed time kinds.
To check whether the plan still works at actual times, put those times into a world
scenario and run `check`. Compare creates no frozen artifacts and edits no model.
