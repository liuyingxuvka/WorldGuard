# WorldGuard project rules

<!-- flowguard:start -->
## FlowGuard rules for the project agent

1. At session start, look at `python -m flowguard` when the project has intent rules.
2. Before writing a decision, use `python -m flowguard show "what it decides"` to find its existing owner.
3. Write one rule, bind each real home, and add a literal regression row only when a decision has copies, the owner says everywhere, or a bug was fixed. Otherwise stay quiet.
4. After changing a bound decision run `python -m flowguard check`; CI runs `check --all`. Store actual owner words once with `req add`.
<!-- flowguard:end -->

## This repository

FlowGuard is installed from the git tag in the `test` extra of `pyproject.toml` (`python -m pip install -e ".[test]"`); the PyPI package named `flowguard` is a different project. Raise that tag only when this repository uses a newer FlowGuard capability or needs a demonstrated correctness fix in its maintenance workflow; a FlowGuard release alone is no reason to change it or to release this repository.

During development run the affected tests. Before a product release, freeze the source and run the complete native suite once from an environment outside the project; `python -m flowguard check --all` includes that pytest run. Require complete CI on the exact main commit being published. CI runs the suite on Python 3.11 and 3.13, plus the scratch skill byte check. The minimum FlowGuard tag is declared once in the test extra. `docs/development/flow-contracts.md` maps the prior promises and bad observations to real native regressions; ordinary functional behavior stays in direct production tests.

Version numbers are independent for each project; use the same MAJOR.MINOR.PATCH rules:

- At 1.0 and later, incompatible changes to a supported public CLI, skill id, SDK or saved input format raise MAJOR; backward-compatible features raise MINOR; corrections within the existing contract raise PATCH. Internal code volume or a dependency's version is not a version criterion. Never skip a number.
- Before 1.0, keep the unstable status explicit: incompatible public changes raise MINOR and describe migration. Publish 1.0 when declaring a stable contract, not merely because the implementation changed.
- A format consumed by a documented command remains a contract even when generated. Distinguish it from disposable caches. A new required field or changed supported meaning needs a compatibility decision; do not silently reinterpret old material.
- For a changed public surface, retain a small existing valid example and a real counterexample. Explain a corrected old bug separately from a new requirement. Give rejected old material a rebuild path from original inputs; never invent verified results, source digests or evidence fields to make it load.
- Record the release classification and migration in the existing CHANGELOG. Preserve historical commits, tags and releases; append corrections instead of renumbering them. Changes limited to repository policy or maintenance tooling do not by themselves require a product release. Raise a maintenance dependency only for a capability actually used or an evidenced correctness fix required by that workflow, not merely because a new tag exists.

Public saved inputs include documented world/mesh contracts and their original text or table references. Derived timelines do not replace these inputs; preserve unresolved findings and their history when rebuilding generated state.

One route per function: when a step fails, the error reaches the caller or is reported with its text; never a quiet default, a skipped check or a second path. Invalid input raises `WorldInputError` (exit 2); any other error is raised. `tests/test_error_handlers.py` lists every exception handler that can end without raising, per function with its count, its reason and the written rule it serves, and refuses `contextlib.suppress`, warning filters and a `return` inside `finally`; no test or test module may end skipped, expected to fail or cut short (`skip_policy = "forbid"` selects FlowGuard's shared pytest guard).

The skill has no committed runtime copy: `scripts/install_skill.py` copies `worldguard/` into the installed skill.

Domain operations use the portable WorldGuard skill and its native runtime directly. No author-supervision framework or receipt is required.
