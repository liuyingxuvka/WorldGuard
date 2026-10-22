# worldguard-runtime Specification

## Purpose
Provide the installable `worldguard` package: contracts, seven Guard runners, kernel, ModelMesh, CLI and the fuel-cell toy example.
## Requirements
### Requirement: Installable WorldGuard Runtime
The system SHALL provide an installable Python package named `worldguard` with contract, ledger, Guard runner, Kernel, CLI, ModelMesh, example, and test surfaces.

#### Scenario: Package import works
- **WHEN** a local environment runs `python -c "import worldguard; print(worldguard.__version__)"`
- **THEN** the command succeeds and prints a version string.

#### Scenario: Package import exposes mesh API
- **WHEN** a local environment imports `worldguard`
- **THEN** `ModelMeshContract`, `MeshReport`, and `run_model_mesh` are available from the public runtime API.

### Requirement: Canonical Contract And Result Fields
The runtime SHALL expose canonical `GuardContract`, `GuardResult`, `LedgerEntry`, `GuardedReport`, and `GuardStatus` types with the fields described in the WorldGuard technical specification.

#### Scenario: Non-pass evidence is enforced
- **WHEN** a `GuardResult` is created with `GAP`, `FAIL`, or `BOUNDARY_EXCEEDED`
- **THEN** validation requires missing slots, boundary trace, errors, or counterexamples and rejects unsupported non-pass results.

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

### Requirement: Read-only Kernel Handoff
The Kernel and ModelMesh runtime SHALL preserve upstream results as read-only dependencies and aggregate child ledgers without rewriting child status, missing slots, boundaries, or counterexamples.

#### Scenario: Upstream GAP cannot be repaired downstream
- **WHEN** EventGuard returns `GAP` and NormGuard depends on the missing event fact
- **THEN** the aggregate report remains non-pass and the EventGuard gap remains visible in the aggregate ledger.

#### Scenario: Mesh handoff cannot repair child gap
- **WHEN** a node-level Guard result returns `GAP` and a downstream mesh edge consumes that node
- **THEN** the mesh report remains non-pass and preserves the original child gap ledger.

### Requirement: Fuel-cell Toy Replay
The runtime SHALL provide a fuel-cell toy example replay that verifies schema, handoff, ledgers, expected reports, and no-real-world scope boundaries without claiming real physical, legal, safety, deployment, market, or strategy validity.

#### Scenario: Fuel-cell check succeeds without overclaiming
- **WHEN** `python -m worldguard.examples.fuel_cell --check` runs
- **THEN** the command succeeds, reports all seven Guards, and includes explicit toy-scope limits.

### Requirement: Runtime CLI Checks
The runtime SHALL provide only `check` and `mesh-check` as native CLI commands. To revise a fact, edit the contract and rerun its existing assertions.

#### Scenario: Single contract CLI remains compatible
- **WHEN** `worldguard check --example fuel_cell` runs
- **THEN** the existing fuel-cell toy check still succeeds.

#### Scenario: Mesh CLI runs
- **WHEN** `worldguard mesh-check --mesh <path>` runs
- **THEN** it emits a short JSON summary, and the full JSON `MeshReport` when `--json` is added.

### Requirement: Canonical event clocks and scenario-local identities
Event times and `holds.at` assertions in one contract SHALL use one kind: numeric YAML values,
labels sharing one prefix, ISO dates/date-times with consistent timezone awareness, or quoted same-day
HH:MM[:SS] clocks. Native YAML date/datetime objects SHALL behave as ISO values and serialize in JSON reports.
Unknown times, mixed kinds/prefixes/timezone conventions and duplicate event ids within one scenario
SHALL be input errors. An absent event time SHALL retain the native missing-axiom `GAP`; no clock default or order is inferred. Reusing ids across different scenarios SHALL remain valid. A number is never
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
