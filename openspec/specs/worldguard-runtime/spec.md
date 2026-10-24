# worldguard-runtime Specification

## Purpose
Provide the installable `worldguard` package: contracts, seven Guard runners, kernel, one model tree and four CLI commands.
## Requirements
### Requirement: Installable WorldGuard Runtime
The system SHALL provide an installable Python package named `worldguard` with contract, Guard runner, kernel, CLI, model-tree, example and test surfaces.

#### Scenario: Package import works
- **WHEN** a local environment runs `python -c "import worldguard; print(worldguard.__version__)"`
- **THEN** the command succeeds and prints a version string.

#### Scenario: Package import exposes mesh API
- **WHEN** a local environment imports `worldguard`
- **THEN** `ModelMeshContract`, `MeshReport`, and `run_model_mesh` are available from the public runtime API.

### Requirement: Current contract and result fields
A contract SHALL contain `contract_id`, `claim`, `world_model`, `inputs` and optional
`variants`. Claim semantics and assertion kinds SHALL derive Guards; retired keys
SHALL be rejected by presence with an input error naming the key and migration fix.
Results SHALL retain native statuses, errors, counterexamples and missing inputs.

### Requirement: Claims bound to the world model
The runtime SHALL evaluate each `claim.asserts` row against the world model and SHALL NOT read the claim text. A claim without assertions SHALL be `GAP` with gap code `CLAIM_NOT_BOUND`; a false assertion SHALL be `FAIL` with gap code `CLAIM_ASSERTION_FALSE` and the observed model value; an assertion that names something the model does not declare SHALL be `GAP` with `CLAIM_ASSERTION_UNRESOLVED`. EventGuard SHALL check `events[].requires` and CausalGuard SHALL check `causal_model.constraints`.

#### Scenario: A consistent world with a contradicted claim fails
- **WHEN** the locked-door scene is consistent but the claim asserts that Iris entered before Mara unlocked the door
- **THEN** the check is `FAIL` with `CLAIM_ASSERTION_FALSE`

#### Scenario: A model contradiction is caught
- **WHEN** the key is handed over after the door is unlocked, or the ferry leaves before the train arrives
- **THEN** EventGuard reports `EVENT_PRECONDITION_UNMET` or CausalGuard reports `CAUSAL_CONSTRAINT_VIOLATED`

#### Scenario: An unbound claim cannot pass
- **WHEN** a claim has no `asserts`
- **THEN** the check is `GAP` with `CLAIM_NOT_BOUND`

### Requirement: Seven Guard Runners
The runtime SHALL provide EventGuard, AgentGuard, SpaceGuard, ResourceGuard, CausalGuard, ConflictGuard, and NormGuard runners that can each produce `PASS`, `FAIL`, `GAP`, and `BOUNDARY_EXCEEDED` under tests.

#### Scenario: Guard status fixture matrix passes
- **WHEN** the guard fixture tests run
- **THEN** each Guard has at least one passing fixture for all four statuses.

### Requirement: Native evidence survives aggregation
The kernel and tree SHALL preserve child statuses, errors, counterexamples and missing
inputs. A parent assertion SHALL not clear a child's non-pass result.

### Requirement: Runtime CLI Checks
The runtime SHALL provide `check`, `mesh-check`, `timeline` and `compare` as native CLI commands. To revise a fact, edit the contract and rerun its existing assertions.

#### Scenario: Single contract CLI remains compatible
- **WHEN** `worldguard check --example scene` runs
- **THEN** the bundled scene is checked by its native Guards and assertions.

#### Scenario: Mesh CLI runs
- **WHEN** `worldguard mesh-check --mesh <path>` runs
- **THEN** it emits a short JSON summary, and the full JSON `MeshReport` when `--json` is added.

### Requirement: Canonical event clocks and scenario-local identities
Event times and `holds.at` assertions in one contract SHALL use one kind: numeric YAML values,
labels sharing one prefix, ISO dates/date-times with consistent timezone awareness, or quoted same-day
HH:MM[:SS] clocks. Native YAML date/datetime objects SHALL behave as ISO values and serialize in JSON reports.
Unknown times, mixed kinds/prefixes/timezone conventions and duplicate event ids within one scenario
SHALL be input errors. An absent event time SHALL retain the native missing-axiom `GAP`; no clock default or order is inferred. Missing times SHALL prevent ordering only applicable scenarios, including shared events; known failures in independent scenarios SHALL remain failures. Reusing ids across different scenarios SHALL remain valid. A number is never
guessed to be a YAML sexagesimal clock; mixed numeric/clock inputs SHALL explain how to quote clocks.

#### Scenario: A clock-order contradiction fails
- **WHEN** a train arrives at `"10:20"` but a bus requiring its arrival leaves at `"9:40"`
- **THEN** native checking SHALL fail the precondition and the false event-order assertion

#### Scenario: Scoped event assertions remain local
- **WHEN** two scenarios reuse event ids with opposite order
- **THEN** a `scenario` assertion SHALL evaluate that scenario, an ambiguous unscoped order SHALL be a gap,
  and an unknown scenario SHALL not pass using shared or other-scenario events

### Requirement: Scenario and intervention values reach every native check
Scenario and holdout values SHALL replace equations for those variables independent of declaration order.
Other variables SHALL recompute from the assignments. Explicit intervention assignments SHALL take precedence.
One native run owner SHALL execute scenarios, holdouts and interventions for semantic reports, constraints
and variable assertions. Unscoped constraints and variable assertions SHALL check every run; a variable
assertion's `scenario` MAY select a scenario, holdout or intervention id. Counterfactuals SHALL continue to
query the declared intervention result.

#### Scenario: A delayed return invalidates the trip
- **WHEN** a scenario or intervention overrides the bus arrival to leave negative transfer time
- **THEN** the native constraint and claim row SHALL fail, naming the run and observed value

#### Scenario: Malformed interventions are input errors
- **WHEN** interventions are not a list of mappings with unique nonempty ids, declared scenario ids and
  finite numeric assignments to known variables or exogenous inputs, or run ids collide
- **THEN** the CLI SHALL return input error 2 rather than skipping or overwriting a run

### Requirement: Declared Guard boundaries preserve the four statuses
One shared per-Guard boundary-semantics table SHALL own the existing unsupported semantic ids.
Required Guards SHALL be derived before boundary ids are removed from unmapped semantics. Only the
boundary of at least one already-derived Guard SHALL be treated as a boundary; an unselected Guard's
boundary SHALL remain an unmapped gap with an owner/semantic hint. All seven Guard runners SHALL read
the shared table. The status priority SHALL remain `FAIL` > `GAP` > `BOUNDARY_EXCEEDED` > `PASS`.

#### Scenario: Only a selected Guard boundary is exceeded
- **WHEN** a well-formed supported model has true assertions and requests a derived Guard's unsupported boundary
- **THEN** final status SHALL be `BOUNDARY_EXCEEDED`, exit 1, without an unmapped-semantic gap

#### Scenario: A real failure or missing input accompanies a boundary
- **WHEN** the model also has a real failed native check or unresolved required input
- **THEN** the final result SHALL retain `FAIL` or `GAP` respectively

### Requirement: User world variants and readable state
A unit contract MAY declare unique known-bad variants with expected FAIL, GAP or BOUNDARY_EXCEEDED status, optional native problem code and in-memory set/remove/add edits. Every check SHALL run each variant without recursively applying variants. Status or code mismatches SHALL produce GAP VARIANT_NOT_CAUGHT; malformed paths, ids or expectations SHALL produce input error 2 naming the variant. Paths SHALL support exact map keys, list indices and unique id selectors. No edit SHALL change the source file or original contract.

The timeline command SHALL read initial state, time-ordered events, fluents, token markings, problem codes and scalar runs using the same native replay owners. Source strings on events, transfers, assertion rows and nodes SHALL survive on related problems. Full event counterexamples SHALL retain their path prefixes; summaries SHALL remain concise.

### Requirement: Native world observation comparison

`compare --contract --observed` SHALL derive expected event times and scenario
variable values from the contract, compare only supplied observations and return
matches/mismatches with signed actual-minus-expected differences and tolerances.
ISO/clock time differences SHALL use minutes; label/numeric clocks their own scale.
Unknown ids/scenarios, ambiguous scenarios for variables, mixed time kinds and
invalid tolerances SHALL be input errors (exit 2). All matches SHALL exit 0 and any
mismatch SHALL exit 1 with value_outside_tolerance. Optional source SHALL be copied.
The comparison SHALL not edit the input. `--write-observed OUT` SHALL write an independent copy
changing only selected observed event occurrences' `at` fields, refuse an existing output and
leave variable values unchanged. The same behavior SHALL apply to mesh observations grouped by
`nodes`, and each comparison row SHALL name its node.

### Requirement: Single-copy story and trip examples

`check --example` SHALL accept scene and trip. Scene/trip SHALL resolve
only the skill's bundled world files, first beside the repository package and then
beside the installed runtime. Missing files SHALL return an input error explaining
that examples ship with the skill. `mesh-check --example story` SHALL load the bundled tree.
The repository mesh example SHALL contain a summary root, two parts and continues
state handoff with `from` / `to` and only `parent_child` / `continues` edges.

### Requirement: Events and token places agree
When unscoped events and resource transitions coexist, every transition SHALL name
its unscoped event. Missing links, some or all, SHALL produce contract-level GAP
`RESOURCE_TRANSITION_UNLINKED` with the actual transition ids; incorrect explicit
links SHALL remain input errors. Complete links SHALL replay by canonical event time
and keep list order within one event. Resource-only worlds SHALL retain list order.
A known fluent also declared as a place SHALL agree initially and after every event:
truth iff at least one token. The first mismatch per name SHALL FAIL with
`WORLD_EVENT_TOKEN_MISMATCH`, its time, event, place, truth, tokens and trace prefix.
A single token color (declared unique or with total one at that time) SHALL agree
with every `NTPP`/`TPP`/`EQ`/`DC`/`EC` spatial row naming it at the same time, using
the containment closure and declared disjointness of that instant's rows: a place
disjoint from the row's region, or inside a `DC`/`EC` region, SHALL FAIL
`WORLD_SPACE_TOKEN_MISMATCH`; an unrelated place SHALL be GAP
`WORLD_SPACE_TOKEN_UNRELATED`, each with `at`, `x`, `token_place`, `spatial_region`
and `relation`, regardless of requested semantics.
Checks SHALL run regardless of claim-derived Guards; same-time uncertainty and native
missing-time GAP semantics SHALL remain visible without inventing definite facts.

### Requirement: Readable timeline
Timeline SHALL default to text with each claim row and its result, one line per
declared agent, space, conflict and norm sub-model, state, tokens, sources and problem
codes per step, causal codes on the variables line and a `problems:` section for every
other problem, so that its problem codes equal the check's; it SHALL add no checks.
`--json` SHALL preserve the complete view with `claims`, `submodels` and `problems`.
Mesh world blocks SHALL start with their node id. `--mesh` SHALL read the whole tree and
`--example scene|trip|story` SHALL resolve bundled skill assets. `--scenario` SHALL
apply only to a single contract. Source strings SHALL remain unchecked pointers to
original text, without content qualification or age checks.
