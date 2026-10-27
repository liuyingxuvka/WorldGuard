# WorldGuard Contracts

`GuardContract` checks one claim against one explicit world model. `ModelMeshContract` joins contracts in one tree; read [model-mesh.md](model-mesh.md) for that shape.

## Unit input

A contract contains `contract_id`, `claim`, `world_model`, `inputs` and optional
`variants`. The claim has `claim_id`, descriptive `text` (never parsed),
`requested_semantics` and `asserts`. The world has `model_id`, `model_version`,
`entities`, `relations`, `assumptions` and `scope_limits`. Contract id defaults to
claim id; model version defaults to `unversioned`. Retired keys are input errors:
remove the named key and put claim semantics in `requested_semantics` or `asserts`.
Supply the inputs each derived Guard uses; [guard-inputs.md](guard-inputs.md) lists them per Guard; missing required inputs GAP.

WorldGuard derives Guards from claim semantics and assertion kinds; `derived_guards`
names the executed set. Prediction selects EventGuard plus CausalGuard. Unknown
semantics stay visible as `QUALIFICATION_SEMANTIC_UNMAPPED`.

Run `check --contract <file.yaml>`, or `run_worldguard(contract)` in Python.

## Results

Each derived Guard runs once, returning `guard`, `status`, `errors`, `counterexamples`,
`missing_slots`. Boundaries skip no checks. Priority: FAIL > GAP > BOUNDARY_EXCEEDED > PASS.

The default summary contains `contract_id`, `status`, `checked`, `gaps` (one row per problem), `scope_limits` and CLI `input_digests`. Digests use relative paths and sha256 of raw bytes. `checked` names the Guards and counts claim rows. Add `--json` for `guard_results`, `claim_binding`, `derived_guards` and `unmapped_semantics`. A missing assertion is `GAP` `CLAIM_NOT_BOUND`; a false assertion is `FAIL` `CLAIM_ASSERTION_FALSE`; an unresolved assertion is `GAP` `CLAIM_ASSERTION_UNRESOLVED`. `check` and `mesh-check` exit 0 on PASS, 1 on any other status and 2 on invalid input.

## Build a world from a story or trip

1. Claim rows that must hold (`claim.asserts`).
2. Only the inputs those rows need (`events`, `resources`, `spatial_relations`, `causal_model`).
3. Per must-hold row one `variants:` edit that must fail with its `code`.
4. Chapters or days: a tree ([model-mesh.md](model-mesh.md)); unwritten ones have no `contract`.
5. `timeline` after each edit. Full trip: `assets/examples/trip_ferry.yaml`.

## Runnable world

Save as `world.yaml`; `check --contract world.yaml` passes and checks its variant:

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

`timeline --contract <file> [--scenario <id>]` prints text: `claim <id> row <n>: … <result>` per claim row, one `agents:`/`space:`/`conflict:`/`norms:` line per declared sub-model, one step per line (fluents, tokens, source, `!!` codes), `variables` (`!!` causal codes), then `problems:` for the rest; every check code appears. `--json` keeps the whole view. `--mesh <file>` labels each world by node id; `--example scene|trip|story` uses skill assets. Ordering needs every applicable event time. It adds no checks.

Optional string `source` fields on events, transitions, assertion rows and mesh nodes survive on their problem rows. They only point to original text; no source content or age is checked. Full event counterexamples include `trace` (time and event id through the failed event); summaries omit the prefix.

## Compare the world with observations

For the world above, save `observed.yaml` below. Run
`compare --contract world.yaml --observed observed.yaml`.
It exits 1: unlock is 0.5 late (tolerance 0.25), entry_gap differs by -0.5.

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
Add `--write-observed OUT` to write a new independent contract with only the
selected observed event occurrences' `at` fields replaced. Variables and other
events stay unchanged; the original file is untouched and an existing OUT is an
input error. Run `check --contract OUT` to see whether actual times break the plan.

For a tree, use `compare --mesh mesh.yaml --observed log.yaml`. Observations have
`nodes: {model_id: {scenario: base, events: {event_id: time}, variables: {name: value}}}`;
shared `time_tolerance`, `tolerance` and `source` may appear outside `nodes`. Every
comparison row names its `node`. A written tree embeds its resolved contracts and
changes only selected observed event times; `mesh-check --mesh OUT` reveals
continuation or later-node failures.
