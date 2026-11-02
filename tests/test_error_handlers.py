"""The handler list: every exception handler in WorldGuard that can finish without raising, why it may, and the rule it serves.

The scan is computed from the source of worldguard/, scripts/, skills/, tests/ and .flowguard/ (the legacy models).
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
from pathlib import Path
import subprocess
import sys
import textwrap
from typing import NamedTuple

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("worldguard", "scripts", "skills", "tests", ".flowguard")

# The rule each kept handler serves: a file and a sentence it must contain (whitespace is normalised).
REQUIREMENTS = {
    "exit-codes": ("skills/worldguard/references/worldguard-contracts.md",
                   "`check` and `mesh-check` exit 0 on PASS, 1 on any other status and 2 on invalid input."),
    "closed-reader": ("skills/worldguard/references/worldguard-contracts.md",
                      "A reader that closes the output early (for example `| head`) ends any command with exit 141 and "
                      "one line on stderr saying the output is incomplete; it is neither an input error nor a result."),
    "record-error": ("skills/worldguard/references/model-mesh.md",
                     "A record that cannot be read or written stops the command with `WORLDGUARD_RECORD_ERROR` (exit 2, "
                     "the check status in `details`)."),
    "event-clocks": ("openspec/specs/worldguard-runtime/spec.md",
                     "Unknown times, mixed kinds/prefixes/timezone conventions and duplicate event ids within one "
                     "scenario SHALL be input errors."),
    "causal-catches": ("skills/worldguard/references/guard-inputs.md",
                       "Catches: a constraint that fails (`CAUSAL_CONSTRAINT_VIOLATED`, for example a negative transfer "
                       "time), missing or unsafe equations, cycles, scenarios that fail to evaluate."),
    "causal-order": ("skills/worldguard/references/guard-inputs.md",
                     "Scenario and holdout assignments replace the named variable's equation, independent of "
                     "declaration order; other equations recompute from those values."),
    "constraint-unevaluable": ("CHANGELOG.md",
                               "A causal constraint that divides by zero or compares a non-number is reported as "
                               "`CAUSAL_CONSTRAINT_UNEVALUABLE` instead of crashing."),
}


class H(NamedTuple):
    requirement: str
    reason: str
    count: int = 1


NON_RAISING_HANDLERS = {
    # "file:function:caught types": H(requirement key, what it does and why it may stay, how many in that function)
    "worldguard/cli.py:_run:WorldInputError": H("exit-codes",
        "the command boundary for invalid input, one per command: prints WORLDGUARD_INPUT_INVALID with the message and "
        "exits 2. Only WorldInputError is caught; io.py raises it for a file that cannot be read or decoded, and any "
        "other error inside WorldGuard, an OSError or UnicodeError included, is raised", count=5),
    "worldguard/cli.py:_run:RecordError": H("record-error",
        "the record of open contradictions cannot be read or written: prints WORLDGUARD_RECORD_ERROR with the record path "
        "and the check status and exits 2, so a contradiction is never silently not kept", count=4),
    "worldguard/cli.py:main:BrokenPipeError": H("closed-reader",
        "the reader closed stdout early (`| head`): one stderr line saying the output is incomplete and exit 141, the "
        "shell's own code for this"),
    "worldguard/clock.py:_parts:ValueError": H("event-clocks",
        "asks the standard library whether a text is an ISO date-time; a failed parse is the answer, and a text that "
        "matches no time format is then raised as WorldInputError naming the accepted formats"),
    "worldguard/semantic.py:_evaluate_equations:(TypeError, ValueError, ZeroDivisionError, OverflowError)": H("causal-catches",
        "a declared causal equation fails on its own values (for example a division by zero); the variable is reported "
        "as `name:ErrorType` and the scenario as unevaluable (CAUSAL_SCENARIO_UNEVALUABLE)"),
    "worldguard/semantic.py:_evaluate_equations:NameError": H("causal-order",
        "the equation reads a variable this pass has not computed yet; the next pass retries it, and a variable that "
        "never resolves is reported as `name:unresolved_dependencies`"),
    "worldguard/semantic.py:causal_constraint_findings:(NameError, TypeError, ValueError, ZeroDivisionError, OverflowError)": H(
        "constraint-unevaluable",
        "a declared constraint fails on one scenario's values; that scenario is listed as unevaluable with the error "
        "text (CAUSAL_CONSTRAINT_UNEVALUABLE)"),
    "worldguard/semantic.py:causal_constraint_findings:SyntaxError": H("causal-catches",
        "a declared constraint is not an expression; it is listed as unevaluable with the accepted form"),
    "worldguard/semantic.py:equation_error:SyntaxError": H("causal-catches",
        "a declared equation is not an expression; CausalGuard reports it as an unsafe equation with this reason"),
}


def _outcome(statements, in_loop=False):
    """(can finish normally, can leave by return/break/continue) for a statement list."""
    falls, leaves = True, False
    for statement in statements:
        if not falls:
            break
        statement_falls, statement_leaves = _statement_outcome(statement, in_loop)
        leaves |= statement_leaves
        falls = statement_falls
    return falls, leaves


def _statement_outcome(node, in_loop):
    if isinstance(node, ast.Raise):
        return False, False
    if isinstance(node, ast.Return):
        return False, True
    if isinstance(node, (ast.Break, ast.Continue)):
        return False, not in_loop
    if isinstance(node, ast.If):
        (body_falls, body_leaves), (else_falls, else_leaves) = _outcome(node.body, in_loop), _outcome(node.orelse, in_loop)
        return body_falls or else_falls, body_leaves or else_leaves
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return _outcome(node.body, in_loop)
    if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
        _falls, body_leaves = _outcome(node.body, True)  # the body may run zero times
        _else_falls, else_leaves = _outcome(node.orelse, in_loop)
        return True, body_leaves or else_leaves
    if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
        (body_falls, body_leaves), (else_falls, else_leaves) = _outcome(node.body, in_loop), _outcome(node.orelse, in_loop)
        falls, leaves = body_falls and else_falls, body_leaves or else_leaves
        for handler in node.handlers:
            handler_falls, handler_leaves = _outcome(handler.body, in_loop)
            falls, leaves = falls or handler_falls, leaves or handler_leaves
        if node.finalbody:
            final_falls, final_leaves = _outcome(node.finalbody, in_loop)
            falls, leaves = falls and final_falls, leaves or final_leaves
        return falls, leaves
    if isinstance(node, ast.Match):
        return True, any(_outcome(case.body, in_loop)[1] for case in node.cases)
    return True, False  # plain statements, and nested def/class bodies, which do not run here


def reraises_on_every_path(handler: ast.ExceptHandler) -> bool:
    return _outcome(handler.body) == (False, False)


def _python_files():
    return [path for base in SOURCES for path in sorted((ROOT / base).rglob("*.py")) if "__pycache__" not in path.parts]


def _non_raising_handlers() -> dict[str, int]:
    found: dict[str, int] = {}
    for path in _python_files():
        relative = path.relative_to(ROOT).as_posix()

        def visit(node, names):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visit(child, names + [child.name])
                    continue
                if isinstance(child, ast.ExceptHandler) and not reraises_on_every_path(child):
                    caught = ast.unparse(child.type) if child.type else "BARE"
                    key = f"{relative}:{'.'.join(names) or '<module>'}:{caught}"
                    found[key] = found.get(key, 0) + 1
                visit(child, names)

        visit(ast.parse(path.read_text(encoding="utf-8")), [])
    return found


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


def _silencers(tree: ast.AST) -> list[str]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {"contextlib", "warnings"}:
            found.extend(f"line {node.lineno}: imports {alias.name}" for alias in node.names
                         if alias.name in {"suppress", "simplefilter", "filterwarnings", "catch_warnings"})
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {"__exit__", "__aexit__"}:
            found.extend(f"line {inner.lineno}: {node.name} may return a true value, which swallows the error"
                         for inner in _leaving(ast.Module(body=node.body, type_ignores=[]), in_loop=True)
                         if isinstance(inner, ast.Return) and not (isinstance(inner.value, ast.Constant)
                                                                   and inner.value.value in (None, False)))
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if name in {"suppress", "simplefilter", "filterwarnings", "catch_warnings"}:
                found.append(f"line {node.lineno}: {name}()")
        if isinstance(node, ast.Attribute) and node.attr == "filterwarnings":
            found.append(f"line {node.lineno}: mark.filterwarnings")
        if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
            for statement in node.finalbody:
                found.extend(f"line {inner.lineno}: {type(inner).__name__.lower()} inside finally"
                             for inner in _leaving(statement, in_loop=False))
    return found


def _leaving(node, in_loop):
    """Statements in a `finally` that leave it: a return, or a break/continue of a loop outside the `finally`."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
        return
    if isinstance(node, ast.Return) or isinstance(node, (ast.Break, ast.Continue)) and not in_loop:
        yield node
    for child in ast.iter_child_nodes(node):
        yield from _leaving(child, in_loop or isinstance(node, (ast.For, ast.AsyncFor, ast.While)))


def test_nothing_silences_errors_another_way() -> None:
    problems = {path.relative_to(ROOT).as_posix(): _silencers(ast.parse(path.read_text(encoding="utf-8")))
                for path in _python_files()}
    assert {path: rows for path, rows in problems.items() if rows} == {}


@pytest.mark.parametrize("text", [
    "import contextlib\nwith contextlib.suppress(KeyError):\n    work()\n",
    "from contextlib import suppress\nwith suppress(OSError):\n    work()\n",
    "import warnings\nwarnings.simplefilter('ignore')\n",
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
    assert not _silencers(ast.parse("class Closing:\n    def __exit__(self, *exc):\n        self.close()\n        return False\n"))


def test_the_suite_guards_are_loaded_in_this_run(request) -> None:
    """`--noconftest` or `-p no:...` would drop the no-skip hooks and the record guard; then this test fails."""
    plugins = {Path(getattr(plugin, "__file__", "") or "").resolve() for plugin in request.config.pluginmanager.get_plugins()}
    assert (ROOT / "tests" / "conftest.py").resolve() in plugins
    hooks = {impl.function.__module__ for impl in request.config.pluginmanager.hook.pytest_make_collect_report.get_hookimpls()}
    assert any(name.endswith("conftest") for name in hooks)


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
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)],
                            cwd=tmp_path, capture_output=True, text=True)
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
