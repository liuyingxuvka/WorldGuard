# claim-derived-semantic-coverage Specification

## Purpose
Derive required Guards from structured claim semantics and check every current mesh node natively.
## Requirements
### Requirement: One enforced native check
WorldGuard SHALL run `guards/<name>_guard.py:run` once per derived Guard. The checks SHALL include declaration and execution rules, preserve independent failures, and append unsupported boundaries without skipping other checks. Each problem SHALL have exactly one native code and one gap row. Unit reports SHALL contain one final status, checked counts, native Guard results, claim rows, derived Guards, unmapped semantics and scope limits. Mesh reports SHALL preserve node reports and problems with node or edge ids. Parallel status axes, external-provider controls and result attestations SHALL not affect outcomes.

#### Scenario: Caller requests retired controls
- **WHEN** a mesh supplies `closure_profile` or `provider_availability`, or the CLI supplies `--closure-profile`
- **THEN** the request SHALL be rejected before evaluation

#### Scenario: Required token is missing
- **WHEN** any declared resource transition lacks its required colored token
- **THEN** it SHALL fail with its transition and current marking, including the first step

### Requirement: Claim-derived Guard routes
WorldGuard SHALL derive required Guards and semantic routes from structured claim semantics and the kinds of claim assertions, and SHALL always run the complete derived set. Retired alternative selection fields SHALL be input errors.

#### Scenario: Claim semantics are unknown
- **WHEN** a requested semantic maps to no Guard
- **THEN** WorldGuard SHALL report `QUALIFICATION_SEMANTIC_UNMAPPED` as a gap instead of falling back to the caller's Guard list. An unsupported boundary belonging to an already-derived Guard SHALL not be unmapped; a boundary belonging only to an unselected Guard SHALL remain a gap with a hint naming its owner and normal semantic

### Requirement: Every mesh node is checked
WorldGuard SHALL run each mesh node's contract once. A node without a contract SHALL produce `GAP` with `MESH_EXPECTED_NODE_CONTRACT_MISSING`. Caller expected lists and exclusions SHALL NOT remove nodes from checking.

#### Scenario: A node has no contract
- **WHEN** any current mesh node has no embedded `GuardContract`
- **THEN** the aggregate report SHALL remain non-pass and name the missing node

### Requirement: Prediction selects native Guards
`prediction`, `predictive`, `forecast` and `future_outcome` SHALL derive EventGuard and CausalGuard without a separate depth or license calculation.
