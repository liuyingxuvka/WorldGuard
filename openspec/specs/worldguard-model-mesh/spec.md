# worldguard-model-mesh Specification

## Purpose
Check several linked models together: authority, read-only handoffs, freshness, cycles and preserved child evidence.
## Requirements
### Requirement: ModelMesh Contract
The runtime SHALL expose a generic `ModelMeshContract` that groups model nodes, model edges, and optional world-state snapshots without replacing `GuardContract`.

#### Scenario: Mesh contract loads nodes and edges
- **WHEN** a mapping with `mesh_id`, `nodes`, and `edges` is loaded
- **THEN** the runtime normalizes it into a `ModelMeshContract` with stable node and edge records.

### Requirement: Model Authority Boundary
Each model node SHALL declare an inspectable authority boundary that can mark owned semantics, excluded semantics, and scope limits.

#### Scenario: Node claim exceeds authority
- **WHEN** a node contract requests semantics listed in that node authority's `excludes`
- **THEN** the mesh report returns `BOUNDARY_EXCEEDED` and preserves a boundary finding.

### Requirement: Read-only Handoff Contracts
Model edges SHALL preserve downstream handoff rules, including source, target, relation, allowed use, forbidden use, read-only status, and freshness requirements.

#### Scenario: Forbidden downstream use is blocked
- **WHEN** an edge output reference uses a value listed in `forbidden_use`
- **THEN** the mesh report returns `FAIL` with a concrete handoff finding.

#### Scenario: Downstream use must stay inside allowed use
- **WHEN** `allowed_use` is non-empty and an edge output reference is outside it
- **THEN** the mesh report returns `BOUNDARY_EXCEEDED` with a concrete handoff finding.

### Requirement: Freshness And Version Closure
The mesh checker SHALL prevent stale source models from supporting current downstream claims when an edge requires current source evidence.

#### Scenario: Stale source blocks closure
- **WHEN** an edge has `requires_current_source: true` and the source node is not current
- **THEN** the mesh report returns `GAP` with a stale-source finding.

### Requirement: Dependency Cycle Detection
The mesh checker SHALL reject dependency cycles across mesh edges.

#### Scenario: Cycle is detected
- **WHEN** model edges create a cycle among node ids
- **THEN** the mesh report returns `FAIL` with a cycle finding.

### Requirement: Child Guard Evidence Preservation
The mesh report SHALL preserve child `GuardedReport` statuses and ledgers.

#### Scenario: Child GAP prevents mesh PASS
- **WHEN** any node-level Guard report returns `GAP`
- **THEN** the mesh report remains non-pass and includes the child gap ledger in the aggregate ledger.

### Requirement: Mesh CLI
The CLI SHALL provide `worldguard mesh-check --mesh <path>` for generic mesh checks.

#### Scenario: Mesh check emits JSON
- **WHEN** the CLI runs against a valid mesh file
- **THEN** it prints a short JSON summary containing `status`, gaps and non-pass nodes; adding `--json` emits the full report with `node_reports`, `findings`, and `aggregate_ledger`.
