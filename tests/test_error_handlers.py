"""The handler list: every exception handler in WorldGuard that can finish without raising, why it may, and the rule it serves.

The shared FlowGuard map reads the source once; this file checks WorldGuard policy and the retained scanner examples.
A handler counts as re-raising only when every path through it ends in a raise, so `if strict: raise` followed by
`return None` is a handler that swallows. Each key is listed with the number of such handlers in that function, so a
second quiet handler of the same kind fails too. A new handler that does not re-raise fails this test until it is
listed here with what it does, why it is needed and the written rule it comes from (a file and a sentence that file
must contain); a listed one that is gone fails it too. `contextlib.suppress`, warning filters and a `return`, `break`
or `continue` inside `finally` (which drops the error in flight) are refused outright. Every other `except` re-raises,
most with the input's location added. Injected faults reach the caller: tests/test_one_route.py.
"""
from __future__ import annotations

import ast
from contextlib import closing
import tempfile
from pathlib import Path
import subprocess
import sys
import textwrap
from tests.error_policy import REQUIREMENTS, NON_RAISING_HANDLERS, handler_counts, silencers
from flowguard.structure import build

import pytest

ROOT = Path(__file__).resolve().parents[1]

# The rule each kept handler serves: a file and a sentence it must contain (whitespace is normalised).


def _non_raising_handlers():
    with closing(build(ROOT)) as graph:
        return handler_counts(graph)


def _query_text(tree, query):
    """Read the unchanged AST fixture through the shared source facts, never execute it."""
    with tempfile.TemporaryDirectory(prefix="wg-error-syntax-") as temporary:
        folder = Path(temporary)
        root = folder / "subject"
        root.mkdir()
        (root / "input.py").write_text(ast.unparse(tree) + "\n", encoding="utf-8")
        with closing(build(root, folder / "map.sqlite")) as graph:
            return query(graph)


def _silencers(tree):
    return _query_text(tree, silencers)


def reraises_on_every_path(handler):
    source = "for item in items:\n    try:\n        work()\n" + textwrap.indent(ast.unparse(handler), "    ") + "\n"
    rows = _query_text(ast.parse(source), lambda graph: [row for row in graph.handlers() if row["kind"] == "except"])
    return not min(rows, key=lambda row: row["line"])["non_raising"]


def test_every_non_raising_handler_is_listed_with_a_reason() -> None:
    found = _non_raising_handlers()
    assert not [key for key in found if key.endswith(":BARE") or key.endswith(":Exception") or key.endswith(":BaseException")], \
        "a bare or catch-all handler swallows faults of every kind"
    assert sorted(set(found) - set(NON_RAISING_HANDLERS)) == [], "new handlers that do not re-raise: state why or raise"
    assert sorted(set(NON_RAISING_HANDLERS) - set(found)) == [], "listed handlers that no longer exist: drop them"
    assert found == {key: entry.count for key, entry in NON_RAISING_HANDLERS.items()}, \
        "a listed function gained or lost a handler that does not re-raise"
    assert all(len(entry.reason.split()) >= 8 for entry in NON_RAISING_HANDLERS.values())


def test_every_listed_handler_names_a_written_rule_that_exists() -> None:
    """The rule is quoted from a file in the repository, so the requirement field is checked, not trusted."""
    assert {entry.requirement for entry in NON_RAISING_HANDLERS.values()} <= set(REQUIREMENTS)
    assert set(REQUIREMENTS) <= {entry.requirement for entry in NON_RAISING_HANDLERS.values()}, "a rule no handler uses"
    for key, (path, sentence) in REQUIREMENTS.items():
        text = " ".join((ROOT / path).read_text(encoding="utf-8").split())
        assert " ".join(sentence.split()) in text, f"{key}: {path} does not say: {sentence}"


def test_nothing_silences_errors_another_way() -> None:
    with closing(build(ROOT)) as graph:
        assert silencers(graph) == []


@pytest.mark.parametrize("text", [
    "from warnings import filterwarnings as quiet\n",
    "from contextlib import suppress as quiet\n",
    "import contextlib\nwith contextlib.suppress(KeyError):\n    work()\n",
    "from contextlib import suppress\nwith suppress(OSError):\n    work()\n",
    "import warnings\nwarnings.simplefilter('ignore')\n",
    "import pytest\nquiet = pytest.mark.filterwarnings\n",
    "import pytest\n@pytest.mark.filterwarnings('ignore')\ndef test_x():\n    pass\n",
    "def f():\n    try:\n        work()\n    finally:\n        return None\n",
    "for item in items:\n    try:\n        work()\n    finally:\n        continue\n",
    "from contextlib import suppress as quietly\nwith quietly(KeyError):\n    work()\n",
    "class Quiet:\n    def __enter__(self):\n        return self\n    def __exit__(self, *exc):\n        return True\n",
    "class Maybe:\n    def __exit__(self, kind, value, trace):\n        return kind is KeyError\n",
])
def test_the_silencer_scan_sees_each_form(text) -> None:
    assert _silencers(ast.parse(text))


def test_a_loop_inside_finally_may_break_out_of_itself() -> None:
    assert not _silencers(ast.parse("try:\n    work()\nfinally:\n    for row in rows:\n        break\n"))
    assert not _silencers(ast.parse("import warnings\nreference = warnings.simplefilter\n"))
    assert not _silencers(ast.parse("filterwarnings = 1\nvalue = filterwarnings\n"))
    assert not _silencers(ast.parse("class Closing:\n    def __exit__(self, *exc):\n        self.close()\n        return False\n"))


def test_the_suite_guards_are_loaded_in_this_run(request) -> None:
    """`--noconftest` or `-p no:...` would drop the no-skip hooks and the record guard; then this test fails."""
    plugins = {Path(getattr(plugin, "__file__", "") or "").resolve() for plugin in request.config.pluginmanager.get_plugins()}
    assert (ROOT / "tests" / "conftest.py").resolve() in plugins
    hooks = {impl.function.__module__ for impl in request.config.pluginmanager.hook.pytest_make_collect_report.get_hookimpls()}
    assert "flowguard.intent.plugin" in hooks
    assert request.config._flowguard_intent.cfg.skip_policy == "forbid"


def _handler(text):
    source = "for item in items:\n    try:\n        work()\n" + textwrap.indent(textwrap.dedent(text).strip(), "    ") + "\n"
    return next(node for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ExceptHandler))


@pytest.mark.parametrize("text, reraises", [
    ("except KeyError:\n    raise", True),
    ("except KeyError as exc:\n    note(exc)\n    raise ValueError('named') from exc", True),
    ("except KeyError:\n    if strict:\n        raise\n    return None", False),
    ("except KeyError:\n    if strict:\n        raise\n    else:\n        raise ValueError('other')", True),
    ("except KeyError:\n    if quiet:\n        return None\n    raise", False),
    ("except KeyError:\n    for row in rows:\n        raise", False),
    ("except KeyError:\n    for row in rows:\n        continue\n    raise", True),
    ("except KeyError:\n    def later():\n        raise\n    return later", False),
    ("except KeyError:\n    continue", False),
    ("except KeyError:\n    try:\n        cleanup()\n    except OSError:\n        pass\n    raise", True),
    ("except KeyError:\n    with lock:\n        return None", False),
    ("except KeyError:\n    with lock:\n        raise", True),
    ("except KeyError:\n    pass", False),
])
def test_a_handler_reraises_only_when_every_path_raises(text, reraises) -> None:
    assert reraises_on_every_path(_handler(text)) is reraises


def _probe(tmp_path, files):
    """Run pytest on probe files beside a copy of this suite's conftest; (exit code, last summary line, output)."""
    (tmp_path / "conftest.py").write_text((ROOT / "tests" / "conftest.py").read_text(encoding="utf-8"), encoding="utf-8")
    for name, text in files.items():
        (tmp_path / name).write_text(textwrap.dedent(text), encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text('[tool.flowguard]\nskip_policy = "forbid"\n', encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "flowguard.intent.plugin", "-p", "no:cacheprovider", str(tmp_path)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.stdout.strip(), result.stdout + result.stderr
    return result.returncode, result.stdout.strip().splitlines()[-1], result.stdout + result.stderr


def test_a_skipped_test_fails_the_run(tmp_path) -> None:
    """A test can never pass by being skipped (for example because a handler made its input disappear)."""
    code, summary, output = _probe(tmp_path, {"test_probe.py": """
        import pytest

        def test_skipped():
            pytest.skip('the input was not there')

        @pytest.mark.skip(reason='marked')
        def test_marked():
            pass

        @pytest.mark.skipif(True, reason='condition')
        class TestConditional:
            def test_inside(self):
                pass

        def test_fine():
            pass
        """})
    assert code == 1, output
    assert summary.startswith("1 failed, 1 passed, 2 errors") and "skipped" not in summary, summary  # marks fail at setup
    for name in ("test_skipped was skipped (the input was not there)", "test_marked was skipped (marked)",
                 "test_inside was skipped (condition)"):
        assert name in output


@pytest.mark.parametrize("module", [
    "import pytest\npytest.skip('no input here', allow_module_level=True)\n\ndef test_never():\n    pass\n",
    "import pytest\npytest.importorskip('a_module_that_is_not_installed')\n\ndef test_never():\n    pass\n",
], ids=["module-level skip", "importorskip"])
def test_a_module_skipped_while_it_is_collected_fails_the_run(tmp_path, module) -> None:
    code, summary, output = _probe(tmp_path, {"test_gone.py": module, "test_other.py": "def test_fine():\n    pass\n"})
    assert code != 0, output
    assert "skipped" not in summary and "error" in summary, summary
    assert "was skipped while it was collected" in output


def test_an_expected_failure_fails_the_run(tmp_path) -> None:
    """An xfail marker would turn an injected fault into '1 xfailed' and exit 0; a test that passes anyway is no better."""
    code, summary, output = _probe(tmp_path, {"test_probe.py": """
        import pytest

        @pytest.mark.xfail(raises=RuntimeError)
        def test_hides_a_fault():
            raise RuntimeError('injected')

        @pytest.mark.xfail(reason='flaky', strict=False)
        def test_passes_anyway():
            pass

        def test_marks_itself():
            pytest.xfail('not now')
        """})
    assert code == 1, output
    assert summary.startswith("3 failed") and "xfail" not in summary and "xpass" not in summary, summary
    for name in ("test_hides_a_fault is marked as expected to fail", "test_passes_anyway is marked as expected to fail (flaky)",
                 "test_marks_itself is marked as expected to fail (not now)"):
        assert name in output


def test_a_run_cut_short_fails(tmp_path) -> None:
    code, _summary, output = _probe(tmp_path, {"test_probe.py": """
        import pytest

        def test_first():
            pytest.exit('stop here', returncode=0)

        def test_second():
            pass
        """})
    assert code == 1, output
    assert "the run was ended early by pytest.exit('stop here')" in output
