"""Suite-wide guards: no test may be skipped, and running the tests must not leave a record of open contradictions
in the repository."""
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


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """A skipped test is a failed test: a check that did not run is never reported as fine."""
    outcome = yield
    report = outcome.get_result()
    if report.skipped and not hasattr(report, "wasxfail"):
        reason = report.longrepr[-1] if isinstance(report.longrepr, tuple) else report.longrepr
        report.outcome = "failed"
        report.longrepr = f"skipped tests are not allowed: {reason}"
