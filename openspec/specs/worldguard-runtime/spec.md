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
The runtime SHALL provide CLI entrypoints for both single-contract checks and mesh checks.

#### Scenario: Single contract CLI remains compatible
- **WHEN** `worldguard check --example fuel_cell` runs
- **THEN** the existing fuel-cell toy check still succeeds.

#### Scenario: Mesh CLI runs
- **WHEN** `worldguard mesh-check --mesh <path>` runs
- **THEN** it emits a short JSON summary, and the full JSON `MeshReport` when `--json` is added.
