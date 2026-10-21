## ADDED Requirements

### Requirement: One explicit WorldGuard maintenance authority
The author repository SHALL represent WorldGuard maintenance as exactly one SkillGuard unit whose only member is the WorldGuard skill, while WorldGuard retains all domain-route, semantic, action, and native-check authority.

#### Scenario: Current author authority is inspected
- **WHEN** the repository's SkillGuard author adoption and generated contract are audited
- **THEN** they identify one `unit:worldguard`, one `worldguard` member, and no SkillGuard-authored domain route

### Requirement: Exact target-declared validation ownership
The maintenance unit MUST freeze and supervise exactly the five checks declared by WorldGuard, with one primary execution owner and one evidence subject per check, without adding or reinterpreting completion depth.

#### Scenario: Validation plan is frozen
- **WHEN** WorldGuard maintenance validation begins
- **THEN** the plan contains the five target-declared checks, their exact obligations and subjects, valid dependency order, and no missing, duplicate, or foreign owner

#### Scenario: Declared evidence is incomplete
- **WHEN** any declared check is failed, skipped, stale, blocked, not run, or owned ambiguously
- **THEN** SkillGuard closure remains blocked and does not substitute another check or receipt

### Requirement: Exact package and bundled runtime identity
The canonical WorldGuard package and bundled skill runtime SHALL contain byte-identical copies of every topology-governed runtime artifact, including the fuel-cell world model, without changing its parsed semantics.

#### Scenario: Fuel-cell model identity is verified
- **WHEN** the canonical and bundled fuel-cell model files are compared after normalization
- **THEN** their raw-content hashes and parsed values are identical

### Requirement: Singular FlowGuard project tool surface
The project SHALL use the current installed FlowGuard consumer suite as its sole project tool surface and SHALL NOT retain tracked author-style FlowGuard skill copies or an obsolete local suite map once dependency evidence confirms they have no live owner.

#### Scenario: Obsolete copies have no dependency
- **WHEN** repository imports, scripts, tests, guidance, and public entrypoints are inspected
- **THEN** no active dependency resolves through `.agents/skills` or `.skillguard/flowguard-suite/suite-map.json`, allowing those obsolete copies to be removed

#### Scenario: A live dependency is found
- **WHEN** dependency inspection finds an active executable or public-entrypoint dependency on a proposed removal
- **THEN** removal is blocked until that dependency receives an explicit current owner and replacement

### Requirement: Clean consumer independence
The WorldGuard consumer projection SHALL contain all declared consumer files with exact source parity, SHALL exclude author-only SkillGuard state and prompts, and SHALL remain usable without author receipts, router state, or maintenance commands.

#### Scenario: Consumer projection is compared read-only
- **WHEN** source and installed consumer inventories are compared without installation
- **THEN** required paths and hashes match, prohibited author state is absent, and the result makes no installation or release claim

### Requirement: Bounded local closure
Closure SHALL distinguish source, validation evidence, consumer projection, installation, and Git or release identities, and SHALL leave installation and publication not run unless separately authorized.

#### Scenario: Local maintenance succeeds
- **WHEN** current author compilation, five-check validation, FlowGuard audit, consumer comparison, and evidence audit all succeed
- **THEN** the repository may claim local source and validation closure while reporting installation, commit, push, tag, and release as not run
