# WorldGuard Contracts

`GuardContract` checks one claim against one explicit world model. `ModelMeshContract` joins contracts in a tree; see [model-mesh.md](model-mesh.md).

## Unit input

A contract contains `contract_id`, `claim`, `world_model`, `inputs` and optional
`variants`, `texts`, `aliases`, `tables`, `decimal` and `values`. Unknown top-level fields are input errors. The claim has `claim_id`, descriptive `text` (never parsed),
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

Failed preconditions block effects in assertions, timelines and handoffs.
An actor event without `place` and `uses` is `GAP` `EVENT_ACTOR_STATE_UNCHECKED`; a place or thing that `world_model.relations` contradicts at that time is `FAIL` `EVENT_RELATION_UNMET`; `actor_state_free` reasons are listed in `scope_limits`.

Each derived Guard runs once, returning `guard`, `status`, `errors`, `counterexamples`,
`missing_slots`. Boundaries skip no checks. Priority: FAIL > GAP > BOUNDARY_EXCEEDED > PASS.

Summaries contain `contract_id` (unit) or `mesh_id` (tree), `status`, `checked`, `gaps`, `scope_limits`
and CLI `input_digests` (raw contract, node and source files; relative paths, sha256). `checked` names
Guards and claim counts. `--json` adds `guard_results`, `claim_binding`, `derived_guards` and
`unmapped_semantics`. Missing/false/unresolved assertions give `CLAIM_NOT_BOUND` GAP,
`CLAIM_ASSERTION_FALSE` FAIL, or `CLAIM_ASSERTION_UNRESOLVED` GAP.
`check` and `mesh-check` exit 0 on PASS, 1 on any other status and 2 on invalid input.
Invalid input includes unreadable files; internal errors raise their traceback.
A reader that closes the output early (for example `| head`) ends any command with exit 141 and one line on stderr saying the output is incomplete; it is neither an input error nor a result.

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

Variant ids are unique. `expect` defaults to `FAIL`, or use `GAP` / `BOUNDARY_EXCEEDED`; `code` is optional.
`set` replaces existing values, `remove` lists existing paths, `add` maps list paths to appended items.
Paths use dotted keys, numeric indices (`[0]`) or exact `id` / `*_id` values (`[e_give_key]`); invalid or
ambiguous paths are input errors. Each edit runs on an independent copy without its variants. A result
missing its declared status or code gives `VARIANT_NOT_CAUGHT` GAP. `checked.variants` counts local
variants; a mesh separately counts its own variants and `checked.node_variants`.

`timeline --contract <file> [--scenario <id>]` shows claims, sub-models and all codes. Start has all fluents/tokens; later steps show `fluents: +a -b` or `=` and changed token places. `--full` repeats full states; `--json` keeps the whole view. Sources, `!!` codes, variables and other problems remain. `--mesh <file>` labels worlds by node; `--example scene|trip|story` uses skill assets. All applicable events need times.

With `texts: {ch: chapter.md}`, event `source: ch p3 "quoted words"` reads the third non-heading paragraph; `tt r3 arr` reads a CSV data row and column (`tables: {tt: {header_rows: 2}}` for merged headers). `aliases: {Anna: [Dr. Anna]}` supplies names; `decimal: {ch: ','}` resolves numeric convention. Source files enter the input digests. A definite mismatch is red; pronouns and unreadable language are grey. Uncited paragraphs appear in `scope_limits`.

Other numeric inputs use `values: {distance: {paths: [inputs.causal_model.scenarios.base.distance], source: ch p2, unit: km}}`. Quantity conversion uses PhysicsGuard's unit table (`units` extra); without it, grey. `unit: '1'` checks only dimensionless/count values, without understanding noun meanings. Unknown physical units and offset temperature conversions stay grey. Source ranges produce text worlds at both endpoints; explicit text time or actor edits use the existing variant evaluator. Claim rows expose `source_statuses`: id, colour, reason, original `sources` and their `source_digest`. Source paths are relative to the contract/mesh manifest, never the saved report; parent rows bind the target's originals.

`timeline` and tree lines mark claims that pass on AI transcription only. The default summary keeps decisions and counterexamples; `--json` includes the original readings and edits. Optional `source` strings remain labels. Event counterexamples include a timeline `trace`; summaries omit it.

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

Expected values come from the native event times and causal scenario. Name `scenario` unless only one exists;
only supplied observations are compared. ISO/clock differences and `time_tolerance` use minutes;
other clocks and variable tolerances use their own scale. Differences are actual minus expected;
absolute differences control tolerance. `source` is copied unchanged. Exit 0 means all supplied readings
match, 1 means a mismatch, 2 means invalid input, unknown id/scenario or mixed time kinds.
`--write-observed OUT` makes a new copy changing only selected event `at` values; other events and variables
stay unchanged. An existing OUT is an input error. Run `check --contract OUT` to check the resulting world.

For `compare --mesh mesh.yaml --observed log.yaml`, observations use
`nodes: {model_id: {scenario: base, events: {event_id: time}, variables: {name: value}}}`;
shared `time_tolerance`, `tolerance` and `source` may sit outside `nodes`. Rows name their node.
A written tree embeds its resolved contracts and changes only selected event times;
`mesh-check --mesh OUT` checks handoffs and later nodes.
