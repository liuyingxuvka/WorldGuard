# semantic-rollout-status Specification

## Purpose
TBD - created by archiving change separate-structural-pass-from-semantic-rollout. Update Purpose after archive.
## Requirements
### Requirement: Separate structural and semantic status
WorldGuard SHALL report structural contract status separately from semantic execution and provider availability.

#### Scenario: Shape passes but semantics do not run
- **WHEN** all required fields exist but no semantic executor runs
- **THEN** structural status MAY pass while semantic and rollout status SHALL be `NOT_RUN` or `BOUNDARY_ONLY`

### Requirement: Fail-closed aggregate projection
WorldGuard MUST NOT project semantic or predictive pass from structural pass, provider availability, child-local pass, caller-selected Guard subsets, or an incomplete expected coverage universe.

#### Scenario: Provider unavailable
- **WHEN** a required semantic provider is unavailable
- **THEN** aggregate semantic closure SHALL remain unavailable and the provider status SHALL be visible

#### Scenario: Predictive coverage is incomplete
- **WHEN** local semantic checks pass but required nodes, Guards, scenarios, horizon, branches, perturbations, interventions, counterfactuals, or holdout evidence are missing
- **THEN** bounded local findings MAY remain visible but aggregate predictive closure SHALL remain `GAP` or `BOUNDARY_EXCEEDED`

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

### Requirement: Native WorldGuard depth receipt
WorldGuard SHALL emit a receipt containing structural checks, claim atoms, required and executed semantic children, provider states, bindings, findings, discovered/declared/excluded model-node reconciliation, expected/skipped nodes, scenario/horizon/branch/perturbation coverage, per-variable/signal temporal child coverage, native dynamic-floor receipts, predictive gaps, a predictive-license decision, and aggregate claim boundary bound to the current mesh fingerprint.

#### Scenario: Structural-only request
- **WHEN** the caller explicitly requests structural-only validation
- **THEN** the receipt SHALL identify every skipped semantic child and SHALL NOT claim semantic rollout or prediction

#### Scenario: Bounded semantic pass
- **WHEN** a narrow supported executor checks only its declared local subset
- **THEN** the receipt SHALL preserve semantic `PASS` if appropriate but SHALL distinguish it from predictive readiness

### Requirement: Installed portable native evaluator authority

#### Scenario: Installed runtime file is absent from the contract
- **WHEN** a bundled native runtime source exists but is absent from implementation authority or any depth/calibration input set
- **THEN** compilation, source audit, installed parity, or formal closure SHALL fail closed

#### Scenario: External checkout can replace the installed evaluator
- **WHEN** the bundled runtime is missing or bypassed and an editable WorldGuard checkout remains importable
- **THEN** formal scheduled-production closure SHALL remain blocked rather than accepting the external import
