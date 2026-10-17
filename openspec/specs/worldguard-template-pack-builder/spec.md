# worldguard-template-pack-builder Specification

## Purpose
TBD - created by archiving change add-worldguard-template-pack-builder. Update Purpose after archive.
## Requirements
### Requirement: WorldGuard owns validating template-pack manifests

#### Scenario: Current manifest is admitted
- **WHEN** a manifest's declared schema, fields, owners, native validator ids, and fingerprint match its current content
- **THEN** WorldGuard admits the manifest to the template registry with its exact identity

#### Scenario: Stale manifest is rejected
- **WHEN** any fingerprinted manifest field changes without a matching new manifest fingerprint
- **THEN** WorldGuard rejects the manifest as stale before selection or construction

### Requirement: Candidate selection has deterministic zero, one, and many outcomes
WorldGuard SHALL select template candidates only from normalized explicit applicability facts. Declaration order, filename order, priority scores, and AI preference MUST NOT select a winner.

#### Scenario: No candidate uses the base template
- **WHEN** zero non-base candidates match and exactly one current base template exists for the requested contract kind
- **THEN** selection returns `base_template` with the base pack id and exact selection fingerprint

#### Scenario: One candidate is selected
- **WHEN** exactly one non-base candidate matches the request facts
- **THEN** selection returns `selected` with that candidate id, the base pack id, and exact selection fingerprint

#### Scenario: Multiple candidates block
- **WHEN** more than one non-base candidate matches the same request facts
- **THEN** selection returns `ambiguous`, preserves every matching candidate id, and construction fails without choosing one

#### Scenario: No base template blocks fallback
- **WHEN** no candidate matches and no unique current base template exists for the requested contract kind
- **THEN** construction fails with a typed no-match/base-missing error

### Requirement: Composition enforces exact field ownership
WorldGuard SHALL require each fragment's declared owned field ids to equal the leaf fields discovered from its payload. Composition SHALL reject overlapping ownership, undeclared writes, and contract-kind mismatches; it MUST NOT use last-writer-wins behavior.

#### Scenario: Disjoint fragments compose
- **WHEN** the selected base and candidate fragments have exact declarations and disjoint owned leaf fields
- **THEN** WorldGuard composes them deterministically in canonical pack/fragment identity order

#### Scenario: Overlapping fields block
- **WHEN** two composed fragments claim or write the same leaf field id
- **THEN** WorldGuard rejects composition with the conflicting field and owner ids

#### Scenario: Payload and ownership declaration disagree
- **WHEN** a fragment writes a leaf not in its ownership declaration or declares a leaf it does not write
- **THEN** WorldGuard rejects the manifest before construction

### Requirement: Task-specific content uses explicit slots
WorldGuard SHALL resolve task-specific content only through exact template slots. Missing slot bindings and unused bindings SHALL block; no implicit default may synthesize task identity, Guard purpose, protected failure ids, good/bad cases, world evidence, or mesh evidence.

#### Scenario: All slots resolve
- **WHEN** every discovered slot has exactly one supplied binding and no extra binding is supplied
- **THEN** WorldGuard produces a fully resolved contract dictionary

#### Scenario: Missing or unused binding blocks
- **WHEN** a required slot is absent or a supplied binding is not consumed
- **THEN** WorldGuard rejects the build with the exact missing or unused slot ids

### Requirement: Built instances bind exact fingerprints
WorldGuard SHALL issue a template-instance receipt containing the registry, selection, selected/base pack, slot-binding, output, validator, and final instance fingerprints. Any governed input change SHALL change the affected fingerprint and make prior identity non-current.

#### Scenario: Repeated exact build is stable
- **WHEN** the same current registry, request facts, slot bindings, and validator runtime produce the same output
- **THEN** the resulting instance fingerprint is identical

#### Scenario: Governed input changes identity
- **WHEN** a selected manifest, slot binding, composed output, or validator binding changes
- **THEN** the instance fingerprint changes or the stale input is rejected

### Requirement: Native validators retain semantic authority
Every build SHALL bind and execute the manifest-declared WorldGuard-native validators before returning a ready instance. GuardContract validation SHALL reuse canonical parsing and the existing task-purpose candidate proof for every claim-derived Guard. ModelMeshContract validation SHALL reuse canonical mesh parsing and embedded GuardContract validation. Unknown, missing, or failed validator bindings SHALL block.

#### Scenario: GuardContract template passes construction validation
- **WHEN** a resolved GuardContract instance has current task-local purpose declarations and native proof for every claim-derived Guard
- **THEN** the native validators accept its construction and return a content-bound validation receipt

#### Scenario: Template does not decide Guard semantics
- **WHEN** a template attempts to substitute a family default for a missing task purpose/failure proof or omits a claim-derived Guard
- **THEN** the existing WorldGuard-native validator rejects the instance

#### Scenario: Unknown validator blocks
- **WHEN** a manifest names a validator id not registered by WorldGuard
- **THEN** registry admission or build fails without falling back to another validator

### Requirement: Built-in packs cover GuardContract and ModelMeshContract scaffolding
WorldGuard SHALL provide a current base pack for each contract kind and purpose-specific candidate packs whose applicability facts are explicit. Guard-specific packs MAY scaffold only their input shape and validator handoff; they MUST NOT author the task's purpose, selected failures, or oracle evidence.

#### Scenario: Guard-specific positive build
- **WHEN** one Guard-specific fact set matches, all task-owned slots are supplied, and native proof succeeds
- **THEN** WorldGuard builds the GuardContract scaffold, validates it, and records the selected purpose-pack identity

#### Scenario: ModelMesh positive build
- **WHEN** one ModelMesh profile fact set matches and all topology/coverage slots are supplied
- **THEN** WorldGuard builds and canonically validates the ModelMeshContract scaffold with its exact pack and instance fingerprints

### Requirement: Template validation integrates without replacing final closure

#### Scenario: Structurally valid base remains bounded
- **WHEN** a no-match request builds from the base template but lacks semantic evidence for a PASS conclusion
- **THEN** the template receipt remains construction-only and later WorldGuard evaluation preserves GAP or BOUNDARY status

### Requirement: WorldGuard exports an exact target-owned neutral projection
WorldGuard SHALL expose an adapter for `worldguard.template_pack_builder` whose output root contains exactly `schema_version`, `target_id`, `native_owner_id`, `family_id`, `route_id`, `request_fingerprint`, `catalog`, `applicability_results`, and `claim_boundary`. The schema SHALL be `skillguard.target_template_projection.v1`; the request fingerprint SHALL be a lowercase `sha256:` identity. The adapter MUST reject unknown root fields and MUST NOT emit target-side `catalog_digest` or `manifest_digest` fields.

#### Scenario: Current projection is accepted
- **WHEN** the request binds the current native registry identity, exact route, supported contract kind, and explicit fact ids

#### Scenario: Unknown root field blocks
- **WHEN** a caller adds any root field outside the declared projection inventory
- **THEN** the WorldGuard adapter rejects the projection before central compilation

### Requirement: Neutral catalog maps every native family manifest exactly once
For one requested contract kind, WorldGuard SHALL emit an unsealed `skillguard.template_catalog.v1` containing exactly one central template specification per current native manifest of that kind, including the unique native base. Every central template SHALL carry the complete neutral field inventory, a closed JSON-object `parameter_schema`, exact native field ownership, and target-owned fixtures and claim boundaries. `applicability_results` SHALL contain exactly one row for every catalog template.

#### Scenario: Candidate inventory equals the native registry
- **WHEN** the current native registry contains one base and N candidates for the requested contract kind
- **THEN** the catalog and applicability rows contain exactly those N+1 native template ids with no missing, duplicate, or invented member

#### Scenario: Native ambiguity remains ambiguity
- **WHEN** the native selector reports several matching candidate pack ids

### Requirement: Projection freshness stays bound to native identities
The adapter SHALL call the existing native registry validation, selection, and manifest applicability logic. It SHALL bind the request to the current registry and selection fingerprints, map the native manifest fingerprint into `artifacts[].content_template_hash`, and map native builder and validator implementation fingerprints into their central `content_hash` fields.

#### Scenario: Wrong route blocks
- **WHEN** the requested route is not exactly `worldguard.template_pack_builder`
- **THEN** WorldGuard rejects the request without projecting a catalog

#### Scenario: Stale native registry identity blocks
- **WHEN** the caller-supplied native registry fingerprint differs from the registry's current validated fingerprint
- **THEN** WorldGuard rejects the projection as stale before emitting neutral records
