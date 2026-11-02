"""Suite-wide guards: no test may end skipped, expected to fail or cut short, and running the tests must not leave a
record of open contradictions in the repository.

Each of those endings exits 0, so a check whose input disappeared (for example because a handler swallowed an error)
would look like a passing run. A skip or an expected failure inside a test is a test report; a skip while a module is
collected (`pytest.skip(..., allow_module_level=True)`, `pytest.importorskip`) is a collection report; `pytest.exit`
ends the session early. All of them fail the run.
"""
from pathlib import Path
import sys

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


NO_SKIP = "this suite allows no skip, expected failure or early exit: a check that did not run is never reported as fine"
_collected: set[str] = set()
_reported: set[str] = set()
_early_exit: list[str] = []


def _reason(report) -> str:
    text = str(report.longrepr[2]) if isinstance(report.longrepr, tuple) else str(report.longrepr)
    return text.removeprefix("Skipped: ")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    report = (yield).get_result()
    if hasattr(report, "wasxfail"):
        what, reason = "is marked as expected to fail", report.wasxfail or "no reason given"
        del report.wasxfail  # a report that keeps it counts as xfailed or xpassed, not as failed
    elif report.skipped:
        what, reason = "was skipped", _reason(report)
    else:
        return
    report.outcome = "failed"
    report.longrepr = f"{item.nodeid} {what} ({reason}); {NO_SKIP}"


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    report = (yield).get_result()
    if report.skipped:
        report.outcome = "failed"
        report.longrepr = f"{collector.nodeid or collector.path} was skipped while it was collected ({_reason(report)}); {NO_SKIP}"


def pytest_collection_finish(session):
    _collected.update(item.nodeid for item in session.items)


def pytest_runtest_logreport(report):
    _reported.add(report.nodeid)


def pytest_keyboard_interrupt(excinfo):
    if isinstance(excinfo.value, pytest.exit.Exception):
        _early_exit.append(f"pytest.exit({excinfo.value.msg!r})")


def pytest_sessionfinish(session, exitstatus):
    """A run that would exit 0 although it was cut short, or although collected tests never ran, fails."""
    if session.exitstatus != pytest.ExitCode.OK:
        return
    option = session.config.option
    problems = [f"the run was ended early by {name}" for name in _early_exit]
    never_ran = sorted(_collected - _reported)
    if never_ran and not (option.collectonly or getattr(option, "setuponly", False) or getattr(option, "setupplan", False)):
        problems.append(f"{len(never_ran)} collected test(s) never ran ({', '.join(never_ran[:3])})")
    if problems:
        print(f"\n{'; '.join(problems)}; {NO_SKIP}", file=sys.stderr)
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
