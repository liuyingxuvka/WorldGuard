# WorldGuard project rules

<!-- BEGIN FLOWGUARD PROJECT RULES -->

## FlowGuard map and model maintenance

1. Start each session with `python -m flowguard read` before opening source.
2. Before adding behavior, use `python -m flowguard read --find WORDS`; extend its existing owner.
3. Open only the affected component's files (`python -m flowguard read --component ID`).
4. After editing, run `python -m flowguard change`, fix errors, and run the affected tests and models it selects.
5. Re-read each REVIEW component, update its description if behavior changed, then `python -m flowguard map confirm ID`.
6. At final release, freeze the source and run the full suite and `python -m flowguard release` once on that revision (same-SHA CI may provide this); report failures and unrun checks honestly.

Maintenance needs FlowGuard at or above the tag in the `test` extra of `pyproject.toml` (install with `python -m pip install -e ".[test]"`; the PyPI package named `flowguard` is a different project).
Raise that tag only when this repository starts using a newer FlowGuard feature; a FlowGuard release alone is no reason to change it or to release this repository.

<!-- END FLOWGUARD PROJECT RULES -->

In this repository the full suite takes about 30 seconds on this shared host (a load-dependent estimate, not a controlled benchmark): run `python -m pytest -q` instead of a selected subset. The skill has no committed runtime copy: `scripts/install_skill.py` copies `worldguard/` into the installed skill.

Domain operations use the portable WorldGuard skill and its native runtime directly. No author-supervision framework or receipt is required.
