## ADDED Requirements

### Requirement: Qualification axes and final status are independently derived
WorldGuard SHALL derive structural, semantic, provider, rollout or depth, and final qualification statuses from their own declared obligations and evidence. A passing substatus SHALL remain visible but MUST NOT be promoted into another axis or the final qualification status.

#### Scenario: Structural contract passes without required semantic execution
- **WHEN** contract shape and structural Guards pass but a required semantic owner is not executed
- **THEN** structural status remains pass, semantic status is not run or gap, and final qualification is non-pass

#### Scenario: Semantic check passes with stale provider evidence
- **WHEN** a semantic result is locally passing but its required provider evidence is bound to an older target revision
- **THEN** the stale supplied result cannot be reused, semantic status is `NOT_RUN` for the accepted qualification evidence, provider status is stale, and final qualification is non-pass

### Requirement: Semantic status has one canonical Guard-status projection
WorldGuard SHALL own one canonical projection from semantic status into aggregate Guard status and every qualification, mesh, and blueprint owner-terminal composition SHALL consume it. `PASS` SHALL project to `PASS`, `FAIL` to `FAIL`, `BOUNDARY_ONLY` to `BOUNDARY_EXCEEDED`, and `GAP` or `NOT_RUN` to `GAP`. The projection SHALL preserve the independent semantic field and MUST NOT merge structural and semantic axes, reinterpret missing execution as not applicable, or maintain route-local copies.

#### Scenario: Boundary-only semantic evidence enters three aggregate routes
- **WHEN** the same current `BOUNDARY_ONLY` semantic result contributes to unit qualification, mesh rollout, and a blueprint native-owner terminal
- **THEN** all three consume the same canonical projection, preserve semantic `BOUNDARY_ONLY`, and use Guard `BOUNDARY_EXCEEDED` in the applicable aggregate composition

#### Scenario: Semantic execution did not run
- **WHEN** a required semantic owner remains `NOT_RUN`
- **THEN** the canonical projection contributes Guard `GAP` and no route may promote it to pass or not applicable

### Requirement: Not-applicable and not-run are evidence-bound outcomes
An obligation SHALL be `NOT_APPLICABLE` only when current structured semantics prove that the obligation is outside the declared claim boundary. Missing input, unavailable provider, omitted execution, or an unsupported relation SHALL remain `NOT_RUN`, gap, or boundary as appropriate and MUST NOT be relabeled not-applicable.

#### Scenario: Provider is unavailable
- **WHEN** a required semantic provider cannot supply current evidence
- **THEN** WorldGuard reports the provider boundary and unexecuted semantic obligation rather than marking it not applicable

### Requirement: Predictive identity axes have closed applicability dispositions
Every predictive semantic-coverage contract SHALL contain exactly one current disposition for each state, transition, event, fluent, branch, perturbation, intervention, and counterfactual axis. A `required` axis SHALL declare a non-empty expected-id inventory, one axis-compatible native observation field, and a claim boundary; it SHALL pass only when the expected and observed identity sets match. A `not_applicable` axis SHALL declare a concrete reason and claim boundary, SHALL carry no expected identities or observation field, and SHALL pass only when every native output belonging to that identity domain is empty. Event and fluent identities MUST NOT satisfy state or transition execution, an empty required inventory MUST NOT bypass depth, and no missing axis may be synthesized as a passing placeholder.

#### Scenario: Static Event exercise has no state-machine execution
- **WHEN** EventGuard executes event-calculus events and fluent updates but does not execute declared state-machine states or transition specifications
- **THEN** event and fluent remain required on their own native outputs while state and transition are explicit reasoned `not_applicable` dispositions with empty expected and observed identities

#### Scenario: Event and fluent observation fields are crossed
- **WHEN** an event axis names a fluent-specific output or a fluent axis names `executed_event_ids`
- **THEN** WorldGuard rejects the predictive coverage contract before licensing depth

#### Scenario: Not-applicable axis carries identities
- **WHEN** a `not_applicable` axis carries expected ids or its native owner observes ids in that domain
- **THEN** WorldGuard blocks predictive qualification and preserves the exact conflicting axis and ids

#### Scenario: Required axis uses an empty inventory
- **WHEN** a `required` axis supplies an empty expected-id array
- **THEN** WorldGuard rejects the contract instead of treating zero expected and zero observed ids as complete coverage

## MODIFIED Requirements

### Requirement: Installed portable native evaluator authority
Formal WorldGuard depth and calibration checks SHALL load the complete target-native Python runtime projected under the installed skill's `runtime/worldguard` tree. That runtime SHALL derive one-way from the repository's sole `worldguard/` author source through the current deterministic projection owner. Every bundled source SHALL be part of the V2 implementation authority and every depth/calibration input fingerprint. A global package, editable source checkout, retired `.skillguard/runtime` tree, or any other runtime SHALL NOT satisfy formal closure.

#### Scenario: Installed runtime file is absent from the contract
- **WHEN** a bundled native runtime source exists but is absent from implementation authority or any depth/calibration input set
- **THEN** compilation, source audit, installed parity, or formal closure SHALL fail closed

#### Scenario: External checkout can replace the installed evaluator
- **WHEN** the bundled runtime is missing or bypassed and an editable WorldGuard checkout remains importable
- **THEN** formal closure SHALL remain blocked rather than accepting the external import

#### Scenario: Retired installed runtime path remains authoritative
- **WHEN** a current contract, prompt, checker, or consumer tries to load WorldGuard from an installed `.skillguard/runtime` tree
- **THEN** current authority SHALL fail visibly and no alias or compatibility path SHALL redirect it
