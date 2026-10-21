## MODIFIED Requirements

### Requirement: Source and consumer runtime topology stay identical
`worldguard/` SHALL be the sole author runtime. `skills/worldguard/runtime/worldguard/` SHALL be its complete one-way derived portable projection. The canonical portable-runtime projection owner SHALL define the only source/bundle inventory and raw-byte parity algorithm. The internal topology evidence owner SHALL run the complete topology checker tests plus the complete legacy-helper facade tests because both establish the one public-entry shape. It SHALL validate Guard registry, route, semantic-input, prompt, current-runtime ownership, and sole-CLI dispatch semantics only; it MUST NOT maintain a second suffix list, normalized-text hash, or source/bundle denominator. Blueprint and isolated-import checks MAY consume the canonical projection result, but MUST NOT reconstruct parity independently.

#### Scenario: Bundled runtime drifts
- **WHEN** any projected file, directory, type, link boundary, or raw byte differs between `worldguard/` and `skills/worldguard/runtime/worldguard/`
- **THEN** the canonical projection check SHALL fail before SkillGuard maintenance closure
- **AND** neither the topology checker nor a blueprint test SHALL attempt to normalize, repair, or independently reclassify that drift

#### Scenario: Runtime topology is reviewed
- **WHEN** the internal topology checker validates the seven Guard routes and their semantic input ownership
- **THEN** it SHALL report only topology and route findings and SHALL identify portable projection parity as a separately owned obligation

#### Scenario: The legacy helper is reviewed as an entry surface
- **WHEN** the helper's documented example, contract, and mesh arguments are validated
- **THEN** the same entry-topology owner SHALL run the full helper conformance suite against the real direct-field mesh fixture and prove delegation to the sole bundled CLI
- **AND** the blueprint-domain owner SHALL neither execute nor claim that helper behavior

## ADDED Requirements

### Requirement: All public facades share one portable-origin admission owner
Package CLI, kernel facade, bundled module execution, and the documented portable helper SHALL use one current portable-origin admission rule before delegation. The rule SHALL prove the selected runtime and every loaded `worldguard.*` module originate beneath the declared source or bundled authority for that entry surface. A foreign, mixed, linked, escaped, or ambiguous runtime SHALL fail visibly; no facade may unload and retry, search another checkout, select a historical entrypoint, or act as an independent dispatcher.

#### Scenario: Historical validation or helper entry remains on disk
- **WHEN** an older helper, validation-plan entry, or import route still exists but is not the current declared public owner
- **THEN** it contributes no runtime or evidence authority and no current entry surface may dispatch through it as fallback

### Requirement: Public entrypoints preserve one terminal result and exit policy
Every facade SHALL preserve the selected canonical operation's JSON result, standard error, and exit decision. A facade MUST NOT turn a typed gap, boundary, invalid request, or blocked result into success, and MUST NOT derive a second exit policy from partial fields.

#### Scenario: Package CLI and portable helper receive the same blocked request
- **WHEN** both entry surfaces dispatch the same frozen request to the same canonical operation owner
- **THEN** they expose equivalent machine result, error channel, and non-success exit behavior
