# worldguard-productization Specification

## Purpose
Keep the public package surface small and reproducible from source.
## Requirements
### Requirement: Public Package Surface
The project SHALL define a public package surface through `pyproject.toml`, `README.md`, package data, examples, tests, and ignore rules.

#### Scenario: Public files are present
- **WHEN** the project root is inspected
- **THEN** `pyproject.toml`, `README.md`, `worldguard/`, `skills/worldguard/assets/examples/`, and `tests/` exist.

### Requirement: Route Evidence Exclusion
The public package and Git commit surface SHALL exclude `.flowpilot/`, root-level route `evidence/`, stale repair-v4 evidence, and WG-13 repair checkers as core product files.

#### Scenario: Non-core paths are ignored
- **WHEN** Git status and packaging metadata are inspected
- **THEN** route-local evidence and runtime state are ignored or excluded while copied example fixtures remain available under `skills/worldguard/assets/examples/`.

### Requirement: Local Version Synchronization
The project SHALL support editable local installation and local Git synchronization after implementation.

#### Scenario: Editable install and Git commit
- **WHEN** implementation is complete
- **THEN** `python -m pip install -e .` succeeds, validation commands pass, and a local Git commit records the productized project files.
