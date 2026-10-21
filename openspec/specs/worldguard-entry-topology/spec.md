# worldguard-entry-topology Specification

## Purpose
TBD - created by archiving change enforce-worldguard-single-entry-internal-guard-routes. Update Purpose after archive.
## Requirements
### Requirement: WorldGuard has one public entrypoint
The project SHALL expose exactly one installable Codex skill named `worldguard` and exactly one package console named `worldguard`. EventGuard, AgentGuard, SpaceGuard, ResourceGuard, CausalGuard, ConflictGuard, and NormGuard MUST remain internal WorldGuard routes and MUST NOT be published as child skills, consoles, aliases, or compatibility entrypoints.

#### Scenario: Public entrypoint inventory is verified
- **WHEN** the target-native topology checker inspects project scripts and consumer skill directories
- **THEN** it SHALL find exactly `worldguard` and reject every direct child Guard surface

### Requirement: Seven internal Guards remain complete routes
WorldGuard SHALL retain exactly seven internal Guard routes. Each route MUST bind one claim-derived expectation/prediction boundary, one native Guard runner, one `GuardResult` response, one purpose-contract validation owner, one semantic executor, and the exact terminal Guard statuses `PASS`, `FAIL`, `GAP`, and `BOUNDARY_EXCEEDED`.

#### Scenario: Internal route contract matches runtime
- **WHEN** the topology checker compares the declared route contract with `GUARD_RUNNERS`, `EXECUTOR_REGISTRY`, the Guard status enum, and the Guard purpose inventory
- **THEN** every set and binding SHALL match exactly with no missing, duplicate, or extra Guard

#### Scenario: One internal route loses validation
- **WHEN** a route lacks its semantic executor or purpose-contract validator
- **THEN** the topology check SHALL fail instead of treating another Guard as a replacement

### Requirement: Predictive claims remain Guard-bounded
EventGuard and CausalGuard SHALL participate in predictive closure only through the existing claim-derived predictive-depth contract. AgentGuard, SpaceGuard, ResourceGuard, ConflictGuard, and NormGuard SHALL preserve bounded expectation and constraint checks without independently licensing future prediction.

#### Scenario: Non-predictive Guard returns pass
- **WHEN** a non-predictive internal Guard returns `PASS`
- **THEN** that result SHALL license only its declared bounded semantics and SHALL NOT become predictive evidence

#### Scenario: Predictive request lacks required depth
- **WHEN** prediction is requested and EventGuard or CausalGuard predictive coverage is incomplete
- **THEN** WorldGuard SHALL preserve `GAP` or `BOUNDARY_EXCEEDED` at aggregate closure and SHALL NOT retry through another Guard

### Requirement: Source and consumer runtime topology stay identical
The authoritative runtime and bundled consumer runtime SHALL contain identical internal Guard registry, semantic executor, validation, response, and terminal behavior for this topology.

#### Scenario: Bundled runtime drifts
- **WHEN** any governed runtime file differs between the repository package and `skills/worldguard/runtime/worldguard`

### Requirement: The contracted entry topology has one version identity
The public entry-loading refinement SHALL be frozen as pre-1.0 source version `0.7.1`. Root `VERSION`, package metadata, README source labels, changelog, authoritative runtime `__version__`, and bundled consumer runtime `__version__` SHALL agree before the candidate is published.

#### Scenario: Candidate is checked before installation
- **WHEN** the `0.7.1` candidate topology is validated on its review branch
- **AND** installed projection, Git tag, and GitHub Release identities SHALL each be verified separately before they are claimed

### Requirement: Every internal route publishes a complete admission capsule
Each of the seven internal Guard routes SHALL declare positive applicability semantics, forbidden semantics, required input fields, one first native action, one primary reference path, an optional deepening trigger, and a claim boundary. The topology check SHALL compare those fields with current runtime ownership and reject missing, duplicate, or unresolvable bindings.

#### Scenario: Route capsule is complete
- **WHEN** the internal route registry is audited
- **THEN** every Guard has one complete admission capsule whose paths and owners resolve in the current consumer projection

#### Scenario: Route points to missing reference
- **WHEN** a route's primary or conditionally mandatory reference does not exist
- **THEN** the topology check fails before installation or release
