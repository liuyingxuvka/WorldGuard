## Context

WorldGuard is one product package with one public skill distribution and seven target-owned internal Guard routes. Its author repository also contains SkillGuard maintenance authority for that one skill. The target contract already declares five exact checks and must remain the sole source of domain depth; SkillGuard may supervise execution and evidence but may not add a deeper domain route.

Three repository identities are currently misaligned. The generated SkillGuard authority predates the current 0.4 compiler output, one YAML model differs between the package and bundled skill runtime at the byte level, and a tracked `.agents/skills` tree still contains author-style FlowGuard copies even though project guidance selects the installed global consumer suite. These are maintenance and structure defects, not reasons to change WorldGuard behavior.

The change is local-only. It must preserve parallel work, avoid global installation and publication, keep old evidence immutable, and produce fresh evidence in a new run root.

## Goals / Non-Goals

**Goals:**

- Establish one explicit `unit:worldguard` SkillGuard 0.4 author-maintenance authority with the existing WorldGuard skill as its only member.
- Preserve and execute exactly the five target-declared checks under one frozen validation plan.
- Make the package and bundled skill runtime representations of the fuel-cell model byte-identical.
- Prove that the global FlowGuard consumer is the active project tool surface, then remove obsolete tracked author-style FlowGuard copies and their obsolete suite map.
- Record current FlowGuard structure, test, and development-process evidence for this bounded maintenance change.
- Verify the clean consumer projection without installing or publishing it.

**Non-Goals:**

- Changing WorldGuard runtime behavior, public API, version, seven internal Guard semantics, templates, or domain judgments.
- Adding SkillGuard-authored checks, compatibility readers, migration commands, aliases, or alternate execution paths.
- Installing global skills, editing the FlowGuard repository, publishing packages, or creating Git commits, tags, or releases.
- Deleting or rewriting historical evidence stores.

## Decisions

### Preserve one target-owned five-check contract

The current `contract-source.json` remains the authority for check membership, obligations, subjects, commands, and completion depth. SkillGuard 0.4 directly regenerates only its compiled contract and exact manifest, then supervises those five owners. This is chosen over adding checks because SkillGuard's boundary is evidence supervision, not target-domain design.

### Treat the repository as one maintenance unit

The validation plan binds one unit, one member, five unique execution owners, exact dependencies, and a private fresh receipt root. No receipt crosses maintenance-unit boundaries. This is chosen over per-check or per-copy units because there is only one maintained skill and one declared closure profile.

### Normalize model bytes without semantic migration

The canonical package and bundled runtime YAML are normalized to one exact representation and then verified by raw-content hash. No schema or semantic field changes are admitted. This is chosen over weakening the topology check because byte identity is an existing target-owned contract.

### Remove obsolete FlowGuard author copies after dependency proof

Before removal, repository references, executable imports, tests, documented entrypoints, and the active project record are checked for dependency on `.agents/skills` or `.skillguard/flowguard-suite/suite-map.json`. Removal proceeds only when the installed global FlowGuard consumer is the sole active project surface and no public entrypoint depends on the copies. This is chosen over retaining synchronized duplicates because duplicate author authority caused the present identity ambiguity.

### Keep source, evidence, consumer, installation, and Git identities separate

Fresh validation evidence is written under a new versioned run root. Consumer projection is compared read-only against the installed distribution. No installation or Git publication is inferred from source validation. This prevents a passing source check from being misreported as installation or release completion.

## Risks / Trade-offs

- [A hidden script still references the local FlowGuard copies] → Search tracked and untracked repository surfaces before deletion; block removal if any executable or documented public dependency remains.
- [Line-ending normalization changes model meaning] → Compare parsed content and raw hashes; require semantic equality and exact byte parity before closure.
- [Current generated authority is confused with target authority] → Leave `contract-source.json` and all native WorldGuard checks unchanged; regenerate only compiler-owned files.
- [Fresh receipts accidentally reuse historical evidence] → Use a new persistent run root and exact current input fingerprints; retain older stores untouched.
- [Local validation is mistaken for installation or release] → Report consumer currentness, installation, source, evidence, and Git identities independently and leave installation/publication explicitly not run.

## Migration Plan

1. Upgrade the repository's FlowGuard project record to the installed current engine and audit it.
2. Freeze the existing-model, structure, test, and development-process boundary for the one-skill maintenance unit.
3. Prove no live dependency on the tracked local FlowGuard copies or obsolete suite map.
4. Regenerate current SkillGuard author authority from the unchanged target declaration and create the exact validation plan.
5. Normalize the duplicated YAML model and remove only the proven-obsolete local FlowGuard copies.
6. Execute the five declared checks once under their frozen owners, audit evidence, and compare the clean consumer projection read-only.
7. Validate the OpenSpec package and record all installation, publication, and Git actions as not run.

Rollback remains available through the uncommitted Git worktree: restore only the paths owned by this change. Historical evidence is not part of rollback because it is append-only and the new run root is isolated.
