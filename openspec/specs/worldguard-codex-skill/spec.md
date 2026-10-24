# worldguard-codex-skill Specification

## Purpose
Ship one small WorldGuard skill that tells an agent how to write a world model, run it, and report the four statuses honestly.
## Requirements
### Requirement: Local WorldGuard Skill
The system SHALL install a local Codex skill named `worldguard` under the user skill directory with valid `SKILL.md` frontmatter and concise usage instructions.

#### Scenario: Skill files exist
- **WHEN** the local skill directory is inspected
- **THEN** `SKILL.md`, references, and a runnable helper script exist under the local Codex skill directory, such as `$CODEX_HOME/skills/worldguard`.

### Requirement: Contract-first Prompt Contract
The WorldGuard skill SHALL instruct Codex to build or inspect a structured `GuardContract` for unit-level checks and a structured `ModelMeshContract` for multi-model checks before giving a PASS/FAIL/GAP/BOUNDARY_EXCEEDED conclusion.

#### Scenario: Narrative-only pass is forbidden
- **WHEN** a user asks whether a claim is valid but provides no model fields
- **THEN** the skill instructs Codex to return `GAP` or ask for missing model fields instead of narrative-only PASS.

#### Scenario: Multi-model pass is not inferred from child pass
- **WHEN** a user asks whether several related models jointly support a claim
- **THEN** the skill instructs Codex to inspect the single-root tree, state/time continuation and every child result instead of reporting whole-mesh PASS from child-local PASS results alone.

### Requirement: Local Runtime Integration
The WorldGuard skill SHALL provide guidance for calling the installed runtime for both single-contract checks and mesh checks.

#### Scenario: Skill helper invokes package
- **WHEN** the skill helper script runs against the scene example
- **THEN** it imports `worldguard` and returns a JSON check result.

#### Scenario: Skill references mesh helper path
- **WHEN** the local skill is inspected
- **THEN** it includes a `mesh-check` command example and references for the model tree and continuation checks.

### Requirement: Codex entry starts from the model, then a short shape table
The `worldguard` skill SHALL start `SKILL.md` with `## Start from the model`: read an existing world or tree back with `timeline` / `mesh-check` first, or build one in five steps (claim rows, the inputs they need, one known-bad variant per claim, a tree for chapters or days, contract-less planned nodes). It SHALL then keep the seven-line model tree block and a shape table with the launcher command and reference for each shape, a pointer to the Guard input reference and example worlds, and the result rules (four statuses, exit codes, what to report). Mesh rules SHALL stay in their references and SHALL be loaded only for that shape. New unit checks SHALL start from a copied shipped example world with explicit model fields and assertions.

#### Scenario: Ordinary bounded check enters WorldGuard
- **WHEN** an agent needs one claim checked against one world model
- **THEN** it can write the contract from the Guard input reference and run `check --contract` without loading mesh references

#### Scenario: Every mesh node is checked
- **WHEN** the agent runs a mesh
- **THEN** it reports missing node contracts and native non-pass results without claiming a separate prediction license

### Requirement: One model tree and three runnable references

The skill SHALL introduce executable worlds with bound assertions using the exact
WorldGuard seven-line shared block from the cross-repository XR-202 plan. It SHALL list check, mesh-check, compare
and timeline with references and native status/exit rules. Only guard-inputs.md,
worldguard-contracts.md and model-mesh.md SHALL remain as references, together with
the entry within 25,000 bytes (entry <= 6,000; each reference <= 12,000). References
SHALL contain runnable inputs for their commands, including variants, observation
comparison and relative mesh contracts. Stable entry name and launcher runtime
resolution SHALL remain unchanged.
