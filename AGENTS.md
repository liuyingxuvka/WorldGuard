# WorldGuard project rules

1. Read the current map with `python -m flowguard read` before non-trivial changes.
2. Find the existing owner before adding behavior; keep one canonical implementation in `worldguard/`.
3. Update affected model/code/test bindings and run `python -m flowguard change`.
4. Run the selected ordinary tests and executable models; report actual failures and skipped boundaries.
5. Re-read and confirm affected components; stale input or model pointers never become current by relabeling results.
6. Before release run `python -m flowguard release` and the full project suite once; synchronize portable runtime only from canonical source.

Domain operations use the portable WorldGuard skill and its native runtime directly. No author-supervision framework or receipt is required.

Maintenance needs FlowGuard from the owner's repository: `python -m pip install -e ".[test]"`. Its minimum version is declared once, in `pyproject.toml`; the PyPI package named `flowguard` is a different project.
