# claim-derived-semantic-coverage Specification

## Purpose
Derive required Guards from structured claim semantics and check every current mesh node natively.
## Requirements
### Requirement: Target-owned Guard-model prevention contract
WorldGuard SHALL declare, for every registered Guard, the invalid claim class the Guard prevents, the boundary it does not license, and exactly one native good case that passes both the Guard runner and its semantic executor.

#### Scenario: Guard is connected but purpose-free
- **WHEN** a registered Guard lacks a prevention purpose, blocked-claim class, unsupported boundary, or its one native good case
- **THEN** Guard-model adequacy SHALL fail even when the Guard is reachable from the kernel

### Requirement: Finite protected Guard-failure universe
WorldGuard SHALL source-discover every literal Guard-runner error code and per-Guard semantic finding code, SHALL declare exactly one native bad case for every discovered `(Guard, layer, code)`, and SHALL require an oracle that observes the exact expected status and single code.

#### Scenario: Failure class is missing, duplicated, or shallowly represented
- **WHEN** the declared inventory differs from the source-discovered inventory, a failure class has zero or multiple bad cases, or a bad case emits a different status/code set
- **THEN** the native Guard-model contract SHALL fail closed

#### Scenario: Mesh lifecycle failure is encountered
- **WHEN** executor registration or provider availability fails
- **THEN** the failure SHALL remain under mesh/provider lifecycle ownership and SHALL NOT be counted as an individual Guard failure merely to close that Guard's inventory

### Requirement: One enforced semantic closure
WorldGuard SHALL have one current target-native closure behavior in which required semantic execution always runs. The current contract and CLI MUST reject the retired `closure_profile` field and `--closure-profile` selector instead of preserving a structural-only, advisory, bypass, or fallback path.

#### Scenario: Caller requests structural-only closure
- **WHEN** a mesh payload supplies `closure_profile` or the CLI caller supplies `--closure-profile`
- **THEN** WorldGuard SHALL reject the request before evaluation and SHALL NOT issue a structural-only result

#### Scenario: Bounded claim is evaluated
- **WHEN** a claim is bounded rather than predictive
- **THEN** WorldGuard SHALL still execute all required Guard semantics and SHALL limit only the claim boundary, not the validation depth

### Requirement: Claim-derived Guard routes
WorldGuard SHALL derive required Guards and semantic routes from structured claim semantics and the kinds of claim assertions, and SHALL always run the complete derived set. Caller-declared `target_guards` are reported back but SHALL NOT shrink, extend or block the derived set.

#### Scenario: Caller omits a required Guard
- **WHEN** structured claim semantics require a Guard that `target_guards` does not name
- **THEN** WorldGuard SHALL still run that Guard and SHALL report it in `omitted_guards`

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
