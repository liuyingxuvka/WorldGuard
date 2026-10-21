## Purpose

Provide exact, read-only affected-scope analysis and reverse provenance paths after one current qualification of the source blueprint, so an AI can modify or explain one area without materializing unrelated branches.

## ADDED Requirements

### Requirement: Query source qualification precedes every derived index
After matching the supplied blueprint fingerprint and before building any query index or materializing any closure, every impact or trace operation SHALL run exactly one current `check_world_blueprint` qualification of that source. If the qualification status is not `PASS` or `native_domain_qualified` is false, WorldGuard SHALL reject the complete query with `WORLD_BLUEPRINT_QUERY_SOURCE_UNQUALIFIED`, the blueprint fingerprint, qualification-report fingerprint and status, native-qualification flag, and every source gap id. It MUST NOT return affected members, traced members, terminals, or another successful closure from that source.

#### Scenario: Interface mapping is invalid
- **WHEN** a content-addressed blueprint has a missing or incompatible parent-child mapping and a caller requests impact or trace
- **THEN** WorldGuard preserves the current qualification-report fingerprint and mapping gap ids in `WORLD_BLUEPRINT_QUERY_SOURCE_UNQUALIFIED` before query-index construction

#### Scenario: Cache, binding, native result, or provider evidence is invalid
- **WHEN** the current blueprint qualification finds a stale commitment cache, stale binding, invalid native owner input/result, or unregistered provider observation
- **THEN** impact and trace reject the source identically and do not turn its content fingerprint alone into qualification authority

#### Scenario: Qualified source is queried repeatedly
- **WHEN** the same native-qualified blueprint is supplied to impact or trace
- **THEN** each operation runs one qualification preflight, then uses that one report as its source authority without a second hidden qualification path

### Requirement: Impact analysis computes the exact affected closure
WorldGuard SHALL register every stable public seed class—blueprint/target, node, port, input/output mapping, derivation, element, native semantic object, dependency, binding/resource, declared input/output, and declared gap. After source qualification, it SHALL accept every seed id present in that qualified source and compute the transitive semantic dependents, affected hierarchy ancestors, affected parent-child interfaces, and referenced evidence, tests, native results, and target materials. A declared-gap id remains indexable for structural audit, but the source containing that unresolved gap cannot license a query closure. A changed relation object SHALL affect both declared endpoints before closure, and a changed native semantic object SHALL reach its owning element and exact native-result binding. The result SHALL preserve the path that caused each member to enter the affected closure and SHALL exclude unrelated branches.

#### Scenario: One leaf transition changes
- **WHEN** a leaf transition changes in one branch of a three-level workflow blueprint
- **THEN** impact analysis returns that transition, its semantic dependents, affected ancestor nodes and interfaces, and their bound checks while excluding a sibling branch with no dependency path

#### Scenario: Changed id is unknown
- **WHEN** an impact request contains any id outside the current blueprint inventory, including a mixed known/unknown request
- **THEN** WorldGuard rejects the complete request with every unknown id and computes no partial or whole-blueprint closure

#### Scenario: Dependency relation changes
- **WHEN** a current dependency id is the impact seed
- **THEN** both endpoint elements and the deterministic dependent/interface closure are affected while an unrelated sibling remains excluded

#### Scenario: Declared gap is named as a seed
- **WHEN** the source contains a declared unresolved gap and the caller names that gap id
- **THEN** WorldGuard retains the gap id in its structural index but rejects the unqualified source before publishing impact closure

### Requirement: Reverse trace reaches declared terminal support
WorldGuard SHALL accept only an exact node, node/element port, element, declared output, binding, or material resource as a reverse-trace target. It SHALL trace backward through exact producer, dependency, child-input source, child-output disposition, native execution receipt, material, evidence, test, and native-result edges until it reaches explicit declared-input, binding, or resource terminals. An administrative container, mapping, dependency, native declaration, or gap id MUST NOT be accepted as a trace target. Any visited non-terminal with no producer lineage SHALL become a typed gap. Every returned hop SHALL name the relation and source and target ids, and a trace with gaps SHALL report a non-pass status.

#### Scenario: Top-level output traces to leaf evidence
- **WHEN** a caller traces a root workflow outcome whose dependency graph is complete
- **THEN** WorldGuard returns ordered paths through parent and child ports to the contributing leaf inputs, evidence, tests, and native Guard results

#### Scenario: Source trace edge is broken
- **WHEN** an output depends on an element whose required producer mapping or binding is missing in the source blueprint
- **THEN** source qualification rejects the trace before traversal and preserves the exact source gap ids instead of reporting a partial lineage

#### Scenario: Blueprint container is requested as a trace target
- **WHEN** a caller supplies a blueprint id or another administrative object rather than a traceable domain/interface/support target
- **THEN** WorldGuard rejects the request with `WORLD_BLUEPRINT_TRACE_TARGET_KIND_INVALID` before traversal

#### Scenario: Valid trace has an unresolved lineage
- **WHEN** traversal reaches a non-terminal member with no producer lineage
- **THEN** WorldGuard preserves reached terminals and typed gaps, reports `GAP`, and returns a non-success CLI status

### Requirement: Impact and trace are read-only and content-addressed
The required source qualification and following impact or trace traversal SHALL NOT mutate, repair, rediscover, or execute external providers for the target or blueprint. After qualification, traversal SHALL reuse that report and SHALL NOT rerun qualification through a second path. Each successful result SHALL bind the current blueprint fingerprint, request ids, traversed edge identities, terminal bindings, gaps, and result fingerprint; an unqualified-source rejection SHALL instead bind the qualification-report fingerprint and source gap ids.

#### Scenario: Same query is repeated on the same blueprint
- **WHEN** an identical impact or trace request is evaluated against the same current blueprint fingerprint
- **THEN** the result fingerprint and traversed closure are identical

#### Scenario: Blueprint changes after a query is prepared
- **WHEN** a request carries an older blueprint fingerprint than the current target blueprint
- **THEN** WorldGuard reports the request as stale and does not reuse the old result

### Requirement: Queries materialize only the selected closure
WorldGuard SHALL resolve identity and adjacency metadata before materializing full element, evidence, test, or result payloads, and SHALL materialize only members of the exact affected or reverse-trace closure plus their required context.

#### Scenario: Large blueprint has an unrelated branch
- **WHEN** an impact or trace request touches one bounded branch of a large blueprint
- **THEN** the result identifies the selected member ids and excludes the full payloads of unrelated branches
