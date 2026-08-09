## ADDED Requirements

### Requirement: Blueprint routes load by explicit operation and affected scope
WorldGuard SHALL select the blueprint task shape only from preserved request source spans, exact target/revision/boundary, and one explicit `create`, `update`, `check`, `impact`, `trace`, `bundle-export`, `bundle-verify`, or `bundle-query` operation. `create` SHALL require target-material references; `update` SHALL require a current blueprint identity, explicit change intent, and changed ids; `check` SHALL require the current identity; `impact` SHALL require identity plus changed ids; `trace` SHALL require identity plus a trace target; `bundle-export` SHALL require one current qualified blueprint identity and an explicit destination; `bundle-verify` SHALL require one bundle identity plus an isolated materialization root; and `bundle-query` SHALL require one verified bundle identity, isolated materialization root, exact query kind, and exact member id. After selection it SHALL load the blueprint reference, the requested operation contract, and only the explicitly affected internal Guard references; it MUST NOT load every Guard reference or treat the caller's affected list as proof that native impact analysis ran. Bundle export proves only deterministic portable materialization of the current native-qualified model, bundle verification proves only bundle integrity plus reproducible native replay, and bundle query returns only one frozen verified slice; none of those operations independently proves target factual truth, cross-artifact projection, runtime equivalence, installation, or release.

#### Scenario: Native impact request selects one branch
- **WHEN** a caller requests impact analysis for one current element id
- **THEN** the prompt bundle includes blueprint and impact guidance plus the affected Guard references and excludes unrelated Guard and FlowGuard projection guidance

#### Scenario: Explicit FlowGuard projection is requested
- **WHEN** a caller requests cross-artifact FlowGuard projection after native blueprint qualification
- **THEN** the route loads the projection boundary in addition to the exact affected blueprint material

#### Scenario: Minimal operation label omits model identity
- **WHEN** a caller supplies only `world_blueprint`, `check` or `trace`, and an empty affected-Guard list
- **THEN** prompt composition blocks and names the missing source-span, target, revision, boundary, blueprint/query identity, and operation-specific fields

#### Scenario: Blueprint authoring route is complete
- **WHEN** `create` or `update` carries all exact common and operation-specific inputs
- **THEN** prompt composition selects the single blueprint reference and directs authoring to a following native check without inventing a runtime query alias

#### Scenario: Portable bundle operations stay distinct and bounded
- **WHEN** a caller selects `bundle-export`, `bundle-verify`, or `bundle-query`
- **THEN** prompt composition requires that operation's exact blueprint/bundle, destination/materialization-root, and query-kind/member inputs, dispatches the sole public bundle owner, and states the operation-specific non-truth claim boundary
- **AND** an absent or mixed operation-specific input blocks instead of falling back to `check`, `impact`, `trace`, another bundle operation, or a source-checkout read

### Requirement: Blueprint prompt budgets have fixed enforceable ceilings
The always-loaded WorldGuard skill SHALL remain at or below 12,000 UTF-8 bytes, one blueprint reference SHALL remain at or below 16,000 UTF-8 bytes with at least 1,000 bytes of maintained headroom, and one selected blueprint operation bundle consisting of the entry, blueprint reference, operation guidance, and affected Guard references SHALL remain at or below 70,000 UTF-8 bytes. Validation SHALL report each included component, reference size, and remaining headroom. It MUST preserve required semantics through structural compression and affected-only conditional loading rather than silent truncation.

#### Scenario: Blueprint bundle exceeds its ceiling
- **WHEN** the selected blueprint operation and affected references exceed 70,000 UTF-8 bytes
- **THEN** prompt validation fails with the included component sizes and does not silently truncate a required contract

#### Scenario: Unrelated references would exceed the budget
- **WHEN** the affected blueprint closure fits the budget but loading all Guard references would exceed it
- **THEN** WorldGuard retains the exact affected bundle and excludes unrelated references rather than weakening the selected route

#### Scenario: Blueprint reference loses maintenance headroom
- **WHEN** the blueprint reference exceeds 15,000 UTF-8 bytes even though it remains just below the 16,000-byte outer ceiling
- **THEN** prompt validation fails with the observed reference size and remaining headroom until duplication is structurally compressed without removing identity, interface, binding, depth, query, or claim boundaries
