# worldguard-productization Specification

## Purpose
Keep the public package surface small and reproducible from source.
## Requirements
### Requirement: Public Package Surface
The project SHALL define a public package surface through `pyproject.toml`, `README.md`, package data, examples, tests, and ignore rules.

#### Scenario: Public files are present
- **WHEN** the project root is inspected
- **THEN** `pyproject.toml`, `README.md`, `worldguard/`, `skills/worldguard/assets/examples/`, and `tests/` exist.

### Requirement: Product Files Only
The repository and package SHALL hold product files only: runtime, skill, examples, tests and specifications. Work logs and evidence or proof folders SHALL live outside the repository and SHALL NOT be reserved in `.gitignore`.

#### Scenario: No work-log or evidence paths
- **WHEN** Git status, `.gitignore` and packaging metadata are inspected
- **THEN** no work log or evidence directory is tracked or reserved, while copied example fixtures remain available under `skills/worldguard/assets/examples/`.

### Requirement: Local Version Synchronization
The project SHALL support editable local installation and local Git synchronization after implementation.

#### Scenario: Editable install and Git commit
- **WHEN** implementation is complete
- **THEN** `python -m pip install -e .` succeeds, validation commands pass, and a local Git commit records the productized project files.
