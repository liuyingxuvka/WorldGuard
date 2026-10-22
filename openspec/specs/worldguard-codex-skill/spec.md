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
- **THEN** the skill instructs Codex to inspect model nodes, authority, handoffs, freshness, and closure instead of reporting whole-mesh PASS from child-local PASS results alone.

### Requirement: Local Runtime Integration
The WorldGuard skill SHALL provide guidance for calling the installed runtime for both single-contract checks and mesh checks.

#### Scenario: Skill helper invokes package
- **WHEN** the skill helper script runs against the fuel-cell example
- **THEN** it imports `worldguard` and returns a JSON check result.

#### Scenario: Skill references mesh helper path
- **WHEN** the local skill is inspected
- **THEN** it includes a `mesh-check` command example and references for ModelMesh, authority, handoff, and closure concepts.

### Requirement: Codex entry is a short shape table
The `worldguard` skill SHALL keep `SKILL.md` to a shape table with the launcher command and reference for each shape, a pointer to the Guard input reference and example worlds, and the result rules (four statuses, exit codes, what to report). Mesh rules SHALL stay in their references and SHALL be loaded only for that shape. New unit checks SHALL start from a copied shipped example world with explicit model fields and assertions.

#### Scenario: Ordinary bounded check enters WorldGuard
- **WHEN** an agent needs one claim checked against one world model
- **THEN** it can write the contract from the Guard input reference and run `check --contract` without loading mesh or predictive references

#### Scenario: Predictive claim needs coverage rules
- **WHEN** a mesh claim is predictive
- **THEN** the agent loads the predictive coverage reference before reporting a predictive license
