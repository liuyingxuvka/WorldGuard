"""Suite-wide guards: no test may end skipped, expected to fail or cut short, and running the tests must not leave a
record of open contradictions in the repository.

Each of those endings exits 0, so a check whose input disappeared (for example because a handler swallowed an error)
would look like a passing run. A skip or an expected failure inside a test is a test report; a skip while a module is
collected (`pytest.skip(..., allow_module_level=True)`, `pytest.importorskip`) is a collection report; `pytest.exit`
ends the session early. All of them fail the run.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _records():
    found = {path for base in (ROOT / "tests", ROOT / "skills", ROOT / "worldguard") for path in base.rglob(".worldguard")}
    return found | ({ROOT / ".worldguard"} if (ROOT / ".worldguard").exists() else set())


@pytest.fixture(autouse=True)
def no_record_in_the_repository(request):
    """A test that checks a failing world in place writes `.worldguard/` into the repository; copy the world first."""
    before = _records()
    yield
    added = sorted(str(path.relative_to(ROOT)) for path in _records() - before)
    assert not added, f"{request.node.nodeid} left a record in the repository: {added}"

pytest_plugins = ["flowguard.intent.plugin"]
