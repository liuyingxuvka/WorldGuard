## ADDED Requirements

### Requirement: One qualification authority owns unit and mesh evaluation
WorldGuard SHALL derive required Guards, reconcile caller declarations before execution, reject unmapped claim semantics, freeze Guard purpose, execute every required structural and semantic owner exactly once after successful reconciliation, preserve provider evidence, and issue one canonical qualification report. An unexpected caller-declared Guard SHALL produce a typed denominator gap and block all Guard execution for that qualification. The unit runtime and every mesh node SHALL consume this same qualification behavior rather than maintaining separate semantic loops.

#### Scenario: Unit and one-node mesh evaluate the same contract
- **WHEN** the same current contract and provider evidence are evaluated through the unit entry and a one-node mesh
- **THEN** both results contain the same derived Guards, structural results, semantic receipts, provider states, gaps, and final qualification status

#### Scenario: Mesh attempts a second semantic execution
- **WHEN** a mesh node already carries the canonical qualification report for its contract
- **THEN** the mesh consumes the report read-only and does not invoke any structural or semantic owner again

#### Scenario: Compact native-owner matrix covers the Guard family
- **WHEN** one persistent matrix supplies valid current event, agent, RCC8 relation, resource, causal-link, conflict, and norm semantic inputs
- **THEN** the exact owner set is EventGuard, AgentGuard, SpaceGuard, ResourceGuard, CausalGuard, ConflictGuard, and NormGuard; every structural and semantic owner truly executes to PASS; and every deterministic receipt binds its current request, input, result, target, revision, executor, and claim boundary

#### Scenario: Native-owner matrix uses independent positive and negative oracles
- **WHEN** the persistent matrix is used to validate the seven owners
- **THEN** every owner has at least one literal positive case and one literal negative or atomic-admission case, each case freezes the raw observed semantic object, expected owner inputs, bounded result, forbidden synthesis, and declared-versus-executed evidence semantics; the test derives only raw-content identity independently, compares production with those domain oracles, and checks production fingerprints for deterministic canonical form without copying a production-generated transformation into the expected fixture

### Requirement: Canonical qualification report is complete and read-only
The qualification report SHALL separately expose declared and derived Guard sets, omitted and unmapped semantics, structural status, semantic status, provider status, rollout or depth status when applicable, native result and evidence identities, final qualification status, gaps, and claim boundary. Aggregators MUST preserve these fields without rewriting child evidence.

#### Scenario: Structure passes but provider evidence is missing
- **WHEN** all structural Guard checks pass and one required semantic provider has no current evidence
- **THEN** the report preserves structural pass, reports the provider and semantic gap separately, and keeps final qualification non-pass

#### Scenario: Supplied provider result is partial or foreign
- **WHEN** a caller supplies a provider result missing any required identity or mismatching provider/version/capability, target/revision, contract, boundary, content fingerprint, or receipt fingerprint
- **THEN** WorldGuard does not fill defaults, records stale provider evidence, reports semantic `NOT_RUN`, and keeps final qualification non-pass

#### Scenario: No provider result is supplied
- **WHEN** the required native semantic owner executes for the current contract and no reusable provider result was supplied
- **THEN** the native execution receipt is the sole source of provider evidence identity

### Requirement: Blueprint CLI has one operation group
The runtime CLI SHALL expose one `blueprint` group with `check`, `impact`, and `trace` operations. Each operation SHALL emit the corresponding typed, content-addressed result and SHALL reject unsupported operations without trying another command path.

#### Scenario: Blueprint impact operation runs
- **WHEN** a caller supplies a current blueprint, its fingerprint, and one or more changed ids to `worldguard blueprint impact`
- **THEN** the CLI emits the exact affected-closure result in machine-readable form

#### Scenario: Unknown blueprint operation is supplied
- **WHEN** a caller supplies an operation other than `check`, `impact`, or `trace`
- **THEN** the CLI rejects it and does not reinterpret it as another WorldGuard route

### Requirement: Public dispatch preserves distinct qualification and blueprint contracts
The canonical public dispatcher SHALL select exactly one declared operation owner. Ordinary qualification and native blueprint create, update, check, impact, or trace SHALL retain distinct request and result contracts even when they share low-level validation primitives. The kernel facade, package CLI, and portable helper SHALL delegate without independently parsing domain behavior, retrying another route, or converting a failed or unknown request into a different operation.

#### Scenario: Blueprint-shaped input reaches the ordinary qualification entry
- **WHEN** a caller supplies blueprint intent to an ordinary qualification operation without selecting a blueprint operation
- **THEN** dispatch rejects the mismatched contract and does not silently invoke blueprint check or reinterpret the payload

### Requirement: CLI terminal and process exit semantics have one owner
Every canonical CLI operation SHALL derive its machine result, standard-error behavior, and process exit status from one terminal policy bound to the selected operation result. Package and portable entry surfaces SHALL preserve that policy exactly and MUST NOT recompute success independently.

#### Scenario: Completed trace contains a typed gap
- **WHEN** reverse trace completes with valid terminals and one unresolved lineage gap
- **THEN** the canonical result remains a completed gap result and every entry surface returns the same non-success exit semantics without hiding the terminals

### Requirement: The portable runtime has one deterministic projection owner
`worldguard/` SHALL be the sole author source for WorldGuard runtime behavior. `skills/worldguard/runtime/worldguard/` SHALL be a one-way derived portable projection produced only by one explicit source-to-bundle owner. The owner SHALL inventory the complete non-cache source tree by relative path, raw-byte SHA-256, and file type; SHALL expose a read-only check distinct from an explicit sync; and SHALL stage, revalidate, and atomically commit a complete projection. Immediately after detaching the original projection into the transaction backup and before activating staging, it SHALL re-inventory the detached backup against the last frozen projection snapshot. A peer write observed at that boundary SHALL preserve and restore the exact detached tree and return a dedicated blocker rather than activating staging. It MUST NOT silently ignore missing, extra, linked, escaped, type-drifted, EOL-only-drifted, unexpected-suffix, or byte-drifted members, perform implicit generation during import or tests, read behavior back from the bundle, or use an external package as fallback.

#### Scenario: Read-only projection check observes drift
- **WHEN** a source or bundled member is missing, extra, linked, type-drifted, or differs in any raw byte
- **THEN** the check returns a deterministic blocked result containing the exact inventory difference and changes neither tree

#### Scenario: Explicit sync commits one frozen source snapshot
- **WHEN** the source inventory is frozen and the caller explicitly requests synchronization
- **THEN** the complete bundle is built in staging, the source snapshot is rechecked before commit, and either every projected member becomes current or the previous bundle bytes are restored

#### Scenario: A peer writes at the detach boundary
- **WHEN** the projection changes after its final pre-detach scan but before the original tree is detached into the transaction backup
- **THEN** the detached backup refreeze detects the exact change, restores that peer-written tree, reports `projection_snapshot_changed_after_detach`, and does not activate staging

### Requirement: The legacy skill helper is only a portable CLI facade
The installed `run_worldguard_check.py` helper SHALL preserve its documented `--example fuel_cell`, `--contract <path>`, and `--mesh <path>` argument surface only by translating those inputs into the sole bundled `worldguard.cli.main` dispatcher. It SHALL verify the bundled package and every loaded `worldguard.*` module originate under this skill's portable runtime. It MUST NOT execute Guard, contract, mesh, JSON, or exit-decision behavior independently, unload and retry a foreign module, or fall back to an installed or editable WorldGuard package.

The helper's complete conformance suite SHALL be owned with the public-entry/internal-Guard topology evidence. Blueprint-domain evidence MUST NOT execute or claim this facade, and portable-runtime projection evidence SHALL remain limited to source/bundle inventory, transaction, and isolated-import behavior.

#### Scenario: Legacy helper delegates a contract check
- **WHEN** a caller supplies `--contract <path>` to the helper
- **THEN** the helper invokes the bundled CLI's `check --contract <path>` path and preserves the public JSON, stderr, and exit result

#### Scenario: Foreign WorldGuard is already loaded
- **WHEN** any preloaded `worldguard` module originates outside the bundled runtime
- **THEN** the helper fails visibly without unloading, retrying, or executing through that foreign package
