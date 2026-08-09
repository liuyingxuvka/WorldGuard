# Handoff Contracts

Handoff contracts define how one model node may consume another model node's output.

## Required Fields

- `edge_id`
- `source_model_id`
- `target_model_id`
- `relation`
- `port_mappings` with exact `mapping_id`, `source_port_id`, and `target_port_id`
- `allowed_use`
- `forbidden_use`
- `read_only`
- `requires_current_source`

## Rules

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

## Relation Meanings

- `parent_child`: source is a parent or child model boundary.
- `depends_on`: target depends on source evidence.
- `refines`: target narrows or deepens source.
- `replaces`: target replaces source; old source use needs disposition.
- `conflicts_with`: source and target expose incompatible claims.
- `consumes_output_of`: target consumes named source outputs.
- `same_world_version`: source and target belong to the same state/version.
- `supersedes`: source is newer and supersedes target or target's prior evidence.

## Forbidden Shortcuts

- Do not let a child `PASS` become parent `PASS` without mesh closure.
- Do not let a downstream `PASS` repair upstream `GAP`.
- Do not treat stale evidence as current evidence. Migrate and revalidate it to
  the current schema or block the handoff.
