# WorldGuard project rules

# FlowGuard rules for the project agent

1. At the start of a session and after any loss of context, run `python -m flowguard status` before anything else.
2. When the owner asks for something, store the owner's own words once, as received: `python -m flowguard req add <file|-> --id <id>`. It stores only words the owner wrote, byte for byte: never a plan, a list or text an AI wrote. When a new owner message replaces an earlier one, add `--supersedes <old id>`; never edit `.flowguard/requests/`.
3. Find code with `python -m flowguard where NAME`; change code and its tests together; run the project's own test command (for example `python -m pytest -q`) and report exactly what you ran and the result.
4. Commit code and tests together in one commit with a message in your own words; add a line `Request: R<n>` when the change answers a stored owner request.
5. Before changing state values, actions, conditions, settings or endings, update the affected `.flowguard/flow/` model first; run `python -m flowguard check`. When explaining a flow, embed the `python -m flowguard show` picture as `![Flow](PATH)` using its returned path. Keep purely functional contracts in direct production tests.

If conflicts remain in a reply, end with “需要你决定” and the relevant question and stored owner words. Repair dead ends and unreachable behavior in code; model/code drift needs reconciliation. A provisional decision applies only to eligible contradictory requested obligations; it does not settle these defects.

## This repository

FlowGuard is installed from the git tag in the `test` extra of `pyproject.toml` (`python -m pip install -e ".[test]"`); the PyPI package named `flowguard` is a different project. Raise that tag only when this repository starts using a newer FlowGuard feature; a FlowGuard release alone is no reason to change it or to release this repository.

The project's test command is `python -m pytest -q`; run all of it before each commit. CI runs it again on Python 3.11 and 3.13, plus `python -m flowguard release` and the skill install check. FlowGuard v1.0.0 is pinned for this migrated workflow. The transfer index in `tests/flow_migration/coverage.json` names every prior rule, deliberate bad observation, production test link and system route; independent functional contracts stay in direct tests, and the finite chapter handoff uses the shared native adapter.

Version numbers: raise the second number for a release with new features and the third number only for small fixes; never skip a number.

One route per function: when a step fails, the error reaches the caller or is reported with its text; never a quiet default, a skipped check or a second path. Invalid input raises `WorldInputError` (exit 2); any other error is raised. `tests/test_error_handlers.py` lists every exception handler that can end without raising, per function with its count, its reason and the written rule it serves, and refuses `contextlib.suppress`, warning filters and a `return` inside `finally`; no test or test module may end skipped, expected to fail or cut short (`tests/conftest.py` turns each into a failure).

The skill has no committed runtime copy: `scripts/install_skill.py` copies `worldguard/` into the installed skill.

Domain operations use the portable WorldGuard skill and its native runtime directly. No author-supervision framework or receipt is required.
