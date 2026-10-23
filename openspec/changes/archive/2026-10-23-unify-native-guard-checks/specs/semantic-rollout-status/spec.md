# semantic-rollout-status Specification

## Purpose
Keep structural, semantic, provider and rollout status separate so that no layer can stand in for another.
## Requirements
### Requirement: Separate structural and semantic status
WorldGuard SHALL report structural contract status separately from semantic execution and provider availability.

#### Scenario: Shape passes but semantics do not run
- **WHEN** all required fields exist but no semantic executor runs
- **THEN** structural status MAY pass while semantic and rollout status SHALL be `NOT_RUN` or `BOUNDARY_ONLY`

### Requirement: Fail-closed aggregate projection
WorldGuard MUST NOT project semantic pass from structural pass, provider availability, child-local pass, caller-selected Guard subsets.

#### Scenario: Provider unavailable
- **WHEN** a required semantic provider is unavailable
- **THEN** aggregate semantic closure SHALL remain unavailable and the provider status SHALL be visible

### Requirement: Typed semantic input/output binding
Every semantic executor MUST declare the input fields it reads, output fields it writes, supported semantics, and unsupported boundary.

#### Scenario: Unevaluable causal equation
- **WHEN** a causal rule uses an unsupported or incomplete equation
- **THEN** the executor SHALL return an unevaluable finding and SHALL NOT pass the causal model

### Requirement: Known negative semantic probes
WorldGuard SHALL reject missing event axioms, incomplete BDI, RCC8 conflict, resource double consumption, unevaluable causal equations, incomplete conflict, and missing norm conditions.

#### Scenario: Resource double consumption
- **WHEN** two transitions consume the same finite resource beyond the available quantity
- **THEN** resource semantic status SHALL fail with a conservation finding

### Requirement: Native mesh execution report
WorldGuard SHALL preserve node reports, native semantic receipts, provider states, findings and scope limits for every mesh run. Mesh rollout status SHALL equal its native semantic status; no prediction license or coverage receipt is emitted.

#### Scenario: Semantic child cannot execute
- **WHEN** a required provider is unavailable
- **THEN** the report SHALL identify its skipped reason and SHALL remain non-pass

#### Scenario: Supported bounded semantics pass
- **WHEN** all current node checks and mesh findings pass
- **THEN** the mesh MAY report `PASS` only within the model's declared scope
