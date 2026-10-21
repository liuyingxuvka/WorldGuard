# WorldGuard ModelMesh

Use ModelMesh when a question depends on more than one model, model version, or model-to-model handoff.

## Core Rule

`GuardContract` is the unit-level check. `ModelMeshContract` is the topology-level check.

Do not report a mesh as `PASS` merely because a child `GuardContract` passed. Mesh closure must also check authority, handoff, freshness, cycles, and child evidence preservation. Each node's contract binds its claim with `claim.asserts` like a unit contract: a false node assertion fails the mesh, and a node claim without assertions is a gap.

## ModelMeshContract Fields

Required canonical fields:

- `mesh_id`
- `schema_version`
- `run_id`
- `nodes`
- `edges`
- `snapshots`
- `provider_availability`: optional per-Guard availability override
- `semantic_coverage`: a `SemanticCoverageContract`; by default `profile: bounded` and every current mesh node is expected. For a predictive claim read [predictive-coverage.md](predictive-coverage.md).

## ModelNode Fields

- `model_id`
- `model_version`
- `model_kind`
- `authority`
- `freshness_status`: `current`, `stale`, or `unknown`
- `input_ports` and `output_ports`: typed `port_id`, `value_type`, and `cardinality` inventories
- `contract`: optional embedded `GuardContract`

## ModelEdge Fields

- `edge_id`
- `source_model_id`
- `target_model_id`
- `relation`
- `port_mappings`: exact `mapping_id`, producer `source_port_id`, and consumer `target_port_id`
- `allowed_use`
- `forbidden_use`
- `read_only`
- `requires_current_source`

`parent_child` and `consumes_output_of` transfer data/state and therefore require at least one exact port mapping. Other relation kinds do not accept transfer mappings. Producer outputs and consumer inputs must exist and have the same type and cardinality. Unknown relations, missing mappings, unknown ports, and incompatible ports are current validation failures; they never become `depends_on` or an untyped handoff. If `allowed_use` is non-empty, transferred producer port ids must stay inside it. A transferred port outside that list is a handoff boundary violation.

## Handoff rules

- Handoffs are read-only.
- Downstream nodes may not mutate upstream reports, fill upstream gaps, delete upstream counterexamples, or relabel upstream statuses.
- If `requires_current_source` is true and the source node is stale or unknown, return `GAP`.
- `parent_child` and `consumes_output_of` require non-empty exact port mappings; other relations reject port mappings.
- Every source port must be a declared source-node output and every target port a declared target-node input with identical type and cardinality.
- If any transferred source port is listed in `forbidden_use`, return `FAIL`.
- If `allowed_use` is non-empty and any transferred source port is outside it, return `BOUNDARY_EXCEEDED`.
- If a source or target node id is missing, return `GAP`.
- Dependency cycles return `FAIL`.
- Missing or unknown relation kinds are rejected before evaluation and never converted to `depends_on`.

## Relation meanings

- `parent_child`: source is a parent or child model boundary.
- `depends_on`: target depends on source evidence.
- `refines`: target narrows or deepens source.
- `replaces`: target replaces source; old source use needs disposition.
- `conflicts_with`: source and target expose incompatible claims.
- `consumes_output_of`: target consumes named source outputs.
- `same_world_version`: source and target belong to the same state/version.
- `supersedes`: source is newer and supersedes target or target's prior evidence.

## WorldStateSnapshot Fields

- `snapshot_id`
- `model_ids`
- `status`
- `notes`

Snapshots are optional metadata for version/state context. They do not replace node freshness or edge handoff checks.

## MeshReport Fields

- `status`, `structural_status`, `semantic_status`, `rollout_status`
- `node_reports`: one unit report per node with an embedded contract
- `findings`: topology, authority, handoff, freshness and cycle findings
- `scope_limits`
- `depth_receipt.predictive_claim_licensed` and `depth_receipt.predictive_gaps` for predictive meshes

The aggregate `status` is conservative: structural `PASS` cannot become aggregate `PASS` when semantic execution did not run, a required provider was unavailable, or an executor reported a gap or boundary. A missing contract on any expected node is a `GAP`.

## Forbidden shortcuts

- Do not let a child `PASS` become parent `PASS` without mesh closure.
- Do not let a downstream `PASS` repair upstream `GAP`.
- Do not treat stale evidence as current evidence. Migrate and revalidate it to
  the current schema or block the handoff.

## Non-Goals

WorldGuard core ModelMesh does not own domain concepts such as chapter, scene, paragraph, literature item, quest, level, or task arc. Upper-layer adapters may translate those concepts into model nodes, edges, and claims.
