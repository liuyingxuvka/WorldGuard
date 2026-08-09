## ADDED Requirements

### Requirement: Installation currentness has one delegated authority

WorldGuard's release-readiness audit SHALL derive the current source consumer projection only through the exact current installed SkillGuard `consumer_distribution_plan` interface and SHALL audit the installed tree only through that installation's `audit_consumer_distribution` interface. It SHALL validate one absolute Codex root and the installed scripts, package, entry module, and relative dependency paths before dynamic loading and SHALL block visibly when that authority is relative, missing, linked, escaped, malformed, or incompatible. An empty `CODEX_HOME` SHALL select the normal user installation rather than the current directory. Any package, authority, API, malformed-result, or serialization failure SHALL produce one canonical blocked machine result rather than traceback-only output. WorldGuard MUST NOT parse or validate the consumer manifest with a second algorithm, recalculate manifest or release hashes, scan a fallback repository checkout, select an older module, or silently downgrade.

#### Scenario: Installed SkillGuard consumer API is unavailable

- **WHEN** the current installed SkillGuard consumer-distribution module or either required read-only interface cannot be resolved from the validated installation path
- **THEN** installation currentness is blocked with the unavailable authority visible
- **AND** no alternate module, local manifest parser, compatibility reader, or source-tree fallback is used

### Requirement: Currentness compares the complete current projection

The audit SHALL first require one version identity across `pyproject.toml`, `VERSION`, the canonical source package, the imported distribution, and the bundled portable runtime. It SHALL compare the canonical source package with the actually imported distribution directly, while consuming the repository's canonical `audit_projection()` result exactly once for source-to-bundled-runtime inventory and raw-byte parity. It MUST NOT rescan or rehash the bundled tree, reconstruct projection differences, or fall back when that owner is unavailable or malformed. It SHALL then require the compiled source contract to identify maintenance unit `unit:worldguard`, exactly one external member `worldguard`, and the current consumer projection. It SHALL compare SkillGuard's source plan and installed audit by exact skill id, release id, and the complete file path/content-hash inventory. Any missing, unexpected, changed, symlinked, author-control, or stale-release member SHALL block currentness with the owning checker's finding and the exact comparison gap preserved.

#### Scenario: Canonical portable projection evidence is malformed

- **WHEN** the sole `audit_projection()` owner is missing, comes from a different path, runs more than once, or returns a malformed or self-inconsistent result
- **THEN** readiness blocks before imported-distribution or installation comparison
- **AND** it performs no alternate bundled-runtime scan, hash comparison, compatibility read, or fallback

#### Scenario: A new consumer file is added after installation

- **WHEN** the current source plan contains a consumer file absent from the installed release
- **THEN** currentness is blocked by both the release-identity mismatch and the exact missing installed-release member

#### Scenario: The installed tree has an unsafe or undeclared path

- **WHEN** SkillGuard reports a symbolic link, unexpected file, or `.skillguard/**` author-control path in the installed tree
- **THEN** WorldGuard preserves that exact SkillGuard finding and blocks currentness

### Requirement: Installation freshness excludes all author-only SkillGuard state

Every inventoried `skills/worldguard/.skillguard/**` component SHALL have `source_only` installation disposition and SHALL be excluded from `projection:installation`. Editing only this author subtree MUST NOT stale an otherwise exact installed consumer. Adding or changing a consumer-projected file MUST stale it. Generated compiled contracts and manifests SHALL be rebuilt from the contract source after source freeze and MUST NOT be hand-edited to simulate closure.

#### Scenario: Only author maintenance state changes

- **WHEN** one or more `.skillguard/**` source files change while the current consumer projection is unchanged
- **THEN** the source release id remains identical to the installed release id
- **AND** installation currentness remains passed

### Requirement: WorldGuard remains one external skill and the audit is read-only

The consumer projection and installation audit SHALL contain exactly one external skill id, `worldguard`. EventGuard, AgentGuard, SpaceGuard, ResourceGuard, CausalGuard, ConflictGuard, and NormGuard SHALL remain internal semantic routes and MUST NOT become installed skills, consumer members, aliases, or alternate entrypoints. A currentness check SHALL call only source planning and installed audit; it MUST NOT build, prepare, activate, write, run smoke, execute a domain route, or launch a SkillGuard validation owner.

#### Scenario: Read-only currentness succeeds

- **WHEN** the source plan and installed audit identify the same complete clean `worldguard` release
- **THEN** currentness passes without changing either tree
- **AND** no smoke, native check, build, activation, or validation execution occurs

### Requirement: Release assets and installation authority remain separate

The frozen release manifest SHALL assign separate identities and roles to the package or source artifact, clean consumer skill distribution, canonical external self-DNA materialization, checksums, and release notes. Installation currentness SHALL consume only the clean consumer projection and its delegated SkillGuard audit. Release verification SHALL independently bind every declared public asset to the same version and frozen candidate. Author-only SkillGuard state, historical validation-plan entries, private receipts, caches, local absolute paths, and transient validation payloads MUST NOT enter the consumer projection or public self-DNA asset and MUST NOT become evidence merely because they are published nearby. Materialization, installation, Git/tag/GitHub Release, and release-asset success MUST NOT increase or substitute for the seven-layer static self-DNA depth.

#### Scenario: External self-DNA asset is current but installation is stale

- **WHEN** the canonical self-DNA export matches the frozen release candidate but the installed consumer inventory differs
- **THEN** the materialization/asset check may pass while installation currentness remains blocked, neither result substitutes for the other, and the static deepest layer remains unchanged

#### Scenario: Historical validation entry names a removed owner

- **WHEN** a retained author-side validation record names an owner or input set outside the current frozen maintenance plan
- **THEN** it remains non-authoritative history or a pending cleanup candidate and cannot license current validation, installation, or release closure

### Requirement: Validation evidence subjects remain independently owned

Domain behavior, public-entry conformance, portable source-to-bundle projection, static self-DNA readiness, external materialization equivalence, test execution, external-resource availability, installation currentness, Git/tag/GitHub Release, and release-asset integrity SHALL retain distinct evidence subjects and execution owners. Similar commands, shared inputs, or one passing parent receipt MUST NOT merge those subjects, authorize cross-substitution, or promote static understanding depth.

#### Scenario: Projection parity and helper conformance both pass

- **WHEN** source-to-bundle parity and portable helper conformance pass on the same files
- **THEN** each result licenses only its declared evidence subject and both remain required when the release plan names both obligations
