# claim-derived-semantic-coverage Specification

## Purpose
Derive required Guards from structured claim semantics and check every current mesh node natively.
## Requirements
### Requirement: Target-owned Guard-model prevention contract
WorldGuard SHALL declare, for every registered Guard, the invalid claim class the Guard prevents, the boundary it does not license, and exactly one native good case that passes the sole Guard runner.

#### Scenario: Guard is connected but purpose-free
- **WHEN** a registered Guard lacks a prevention purpose, blocked-claim class, unsupported boundary, or its one native good case
- **THEN** Guard-model adequacy SHALL fail even when the Guard is reachable from the kernel

### Requirement: Finite protected Guard-failure universe
WorldGuard SHALL source-discover every literal Guard-runner error code , SHALL declare exactly one native bad case for every discovered `(Guard, code)`, and SHALL require an oracle that observes the exact expected status and single code.

#### Scenario: Failure class is missing, duplicated, or shallowly represented
- **WHEN** the declared inventory differs from the source-discovered inventory, a failure class has zero or multiple bad cases, or a bad case emits a different status/code set
- **THEN** the native Guard-model contract SHALL fail closed

### Requirement: One enforced native check
WorldGuard SHALL run `guards/<name>_guard.py:run` once per derived Guard. The checks SHALL include declaration and execution rules, preserve independent failures, and append unsupported boundaries without skipping other checks. Each problem SHALL have exactly one native code and one gap row. Unit reports SHALL contain one final status, checked counts, native Guard results, claim rows, derived Guards, unmapped semantics and scope limits. Mesh reports SHALL preserve node reports and problems with node or edge ids. Parallel status axes, external-provider controls and result attestations SHALL not affect outcomes.

#### Scenario: Caller requests retired controls
- **WHEN** a mesh supplies `closure_profile` or `provider_availability`, or the CLI supplies `--closure-profile`
- **THEN** the request SHALL be rejected before evaluation

#### Scenario: Required token is missing
- **WHEN** any declared resource transition lacks its required colored token
- **THEN** it SHALL fail with its transition and current marking, including the first step

### Requirement: Claim-derived Guard routes
WorldGuard SHALL derive required Guards and semantic routes from structured claim semantics and the kinds of claim assertions, and SHALL always run the complete derived set. Caller-declared `target_guards` SHALL NOT shrink, extend or block the derived set.

#### Scenario: Caller omits a required Guard
- **WHEN** structured claim semantics require a Guard that `target_guards` does not name
- **THEN** WorldGuard SHALL still run that Guard and SHALL report it in `derived_guards`

#### Scenario: Claim semantics are unknown
- **WHEN** a requested semantic maps to no Guard
- **THEN** WorldGuard SHALL report `QUALIFICATION_SEMANTIC_UNMAPPED` as a gap instead of falling back to the caller's Guard list. An unsupported boundary belonging to an already-derived Guard SHALL not be unmapped; a boundary belonging only to an unselected Guard SHALL remain a gap with a hint naming its owner and normal semantic

### Requirement: Every mesh node is checked
WorldGuard SHALL run each mesh node's contract once. A node without a contract SHALL produce `GAP` with `MESH_EXPECTED_NODE_CONTRACT_MISSING`. Caller expected lists and exclusions SHALL NOT remove nodes from checking.

#### Scenario: A node has no contract
- **WHEN** any current mesh node has no embedded `GuardContract`
- **THEN** the aggregate report SHALL remain non-pass and name the missing node

### Requirement: Prediction selects native Guards
`prediction`, `predictive`, `forecast`, `future_outcome`, and `ClaimAtom.predictive_intent` SHALL derive EventGuard and CausalGuard without a separate depth or license calculation.
