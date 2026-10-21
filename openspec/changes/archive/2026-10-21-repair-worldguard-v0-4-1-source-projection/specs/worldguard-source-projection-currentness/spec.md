## ADDED Requirements

### Requirement: Source and bundled runtime are one current projection

WorldGuard SHALL expose the same version and runtime bytes from the source package, bundled skill runtime, and package metadata.

#### Scenario: Source version drifts

- **WHEN** source, bundled runtime, or package metadata differ
- **THEN** currentness and release readiness SHALL fail visibly

### Requirement: Projection repair establishes model authority

WorldGuard SHALL bind repaired projection evidence into one current observed FlowGuard model-system snapshot before broad closure.

#### Scenario: Parity passes but observed authority is absent

- **WHEN** source/bundled checks pass without a current observed model snapshot
- **THEN** broad model and release closure SHALL remain blocked
