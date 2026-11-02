# WorldGuard project rules

# FlowGuard rules for the project agent

1. At the start of a session and after any loss of context, run `python -m flowguard status` before anything else.
2. When the owner asks for something, store the owner's own words once, as received: `python -m flowguard req add <file|-> --id <id>`. It stores only words the owner wrote, byte for byte: never a plan, a list or text an AI wrote. When a new owner message replaces an earlier one, add `--supersedes <old id>`; never edit `.flowguard/requests/`.
3. Find code with `python -m flowguard where NAME`; change code and its tests together; run the project's own test command (for example `python -m pytest -q`) and report exactly what you ran and the result.
4. Commit code and tests together in one commit with a message in your own words; add a line `Request: R<n>` when the change answers a stored owner request. The legacy map, `.flowguard/models/` and the target commands need no upkeep.

## This repository

FlowGuard is installed from the git tag in the `test` extra of `pyproject.toml` (`python -m pip install -e ".[test]"`); the PyPI package named `flowguard` is a different project. Raise that tag only when this repository starts using a newer FlowGuard feature; a FlowGuard release alone is no reason to change it or to release this repository.

The project's test command is `python -m pytest -q`; the whole suite takes seconds, so run all of it before each commit. CI runs it again on Python 3.11 and 3.13, plus `python -m flowguard map check --root . --strict`, `python -m flowguard release` and the skill install check. If a legacy model in `.flowguard/models/` fails after a change, fix the code or edit that model file directly.

Version numbers: raise the second number for a release with new features and the third number only for small fixes; never skip a number.

The skill has no committed runtime copy: `scripts/install_skill.py` copies `worldguard/` into the installed skill.

Domain operations use the portable WorldGuard skill and its native runtime directly. No author-supervision framework or receipt is required.
