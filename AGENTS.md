# WorldGuard project rules

<!-- flowguard:start -->
## FlowGuard rules for the project agent

1. At session start, look at `python -m flowguard` when the project has intent rules.
2. Before writing a decision, use `python -m flowguard show "what it decides"` to find its existing owner.
3. Write one rule, bind each real home, and add a literal regression row only when a decision has copies, the owner says everywhere, or a bug was fixed. Otherwise stay quiet.
4. After changing a bound decision run `python -m flowguard check`; CI runs `check --all`. Store actual owner words once with `req add`.
<!-- flowguard:end -->

## This repository

FlowGuard is installed from the git tag in the `test` extra of `pyproject.toml` (`python -m pip install -e ".[test]"`); the PyPI package named `flowguard` is a different project. Raise that tag only when this repository starts using a newer FlowGuard feature; a FlowGuard release alone is no reason to change it or to release this repository.

The project's test command is `python -m pytest -q`; run all of it before each commit. CI runs it again on Python 3.11 and 3.13, through `python -m flowguard check --all`, plus the skill install check. FlowGuard v2.0.0 is pinned for this workflow after its public tag is available. `docs/development/flow-contracts.md` maps the prior promises and bad observations to real native regressions; ordinary functional behavior stays in direct production tests.

Version numbers: raise the second number for a release with new features and the third number only for small fixes; never skip a number.

One route per function: when a step fails, the error reaches the caller or is reported with its text; never a quiet default, a skipped check or a second path. Invalid input raises `WorldInputError` (exit 2); any other error is raised. `tests/test_error_handlers.py` lists every exception handler that can end without raising, per function with its count, its reason and the written rule it serves, and refuses `contextlib.suppress`, warning filters and a `return` inside `finally`; no test or test module may end skipped, expected to fail or cut short (`skip_policy = "forbid"` selects FlowGuard's shared pytest guard).

The skill has no committed runtime copy: `scripts/install_skill.py` copies `worldguard/` into the installed skill.

Domain operations use the portable WorldGuard skill and its native runtime directly. No author-supervision framework or receipt is required.
