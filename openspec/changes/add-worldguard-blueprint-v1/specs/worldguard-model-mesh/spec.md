## ADDED Requirements

### Requirement: Mesh consumes canonical node qualification once
Every mesh node SHALL obtain its Guard, semantic, provider, and node-final state from the canonical current qualification report. Mesh aggregation SHALL read those reports and edge conditions without re-running a node's Guard or semantic owner. The read-only mesh aggregator SHALL remain distinct from unit qualification because it owns graph-level coverage, edge, and roll-up obligations rather than node execution.

#### Scenario: Qualified child feeds a dependent node
- **WHEN** a child node has one current qualification report and a downstream node consumes its declared output
- **THEN** mesh evaluation preserves the child report identity and evaluates only the downstream obligations that have not already been executed

#### Scenario: Child qualification is stale
- **WHEN** a node report fingerprint does not match its current contract, provider inputs, or target revision
- **THEN** the mesh marks that node stale and does not rerun it through a hidden secondary path

### Requirement: Relation kinds and port mappings fail closed
Every mesh or blueprint relation SHALL use a registered current relation kind and, when the relation transfers data or state, exact producer-output and consumer-input port ids with compatible types and cardinalities. Unknown relation kinds and missing or incompatible mappings SHALL be validation errors and MUST NOT become `depends_on` or another default relation. Mesh and blueprint relations SHALL retain one parser per public schema because their payloads and evidence subjects differ; they MAY share a proven pure validation primitive, but MUST NOT be collapsed into one global parser, translate through the other schema, or fall back between parsers without complete caller and equivalence evidence.

#### Scenario: Unknown relation kind is parsed
- **WHEN** a mesh edge declares an unregistered relation kind
- **THEN** WorldGuard rejects the edge with its id and unknown kind before evaluation

#### Scenario: Relation ports are incompatible
- **WHEN** an edge maps a producer output to a consumer input with an incompatible type or cardinality
- **THEN** WorldGuard reports the exact port mismatch and does not treat the endpoints alone as a valid handoff

#### Scenario: Blueprint relation is submitted to the mesh parser
- **WHEN** a blueprint dependency payload is supplied directly to the mesh relation parser without an explicit current schema-bound adapter
- **THEN** parsing fails at the schema boundary and does not reinterpret the payload or retry it through another parser
