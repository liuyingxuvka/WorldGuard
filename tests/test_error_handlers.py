"""The handler list: every exception handler in WorldGuard that can finish without raising, and why it may.

The scan is computed from the source. A handler counts as re-raising only when every path through it ends in a raise,
so `if strict: raise` followed by `return None` is a handler that swallows. A new handler that does not re-raise fails
this test until it is listed here with what it does and why it is needed; a listed one that is gone fails it too.
Every other `except` in worldguard/, scripts/ and skills/ re-raises (most with the input's location added). Injected
faults reach the caller: tests/test_one_route.py.
"""
from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ("worldguard", "scripts", "skills")

NON_RAISING_HANDLERS = {
    # "file:function:caught types": (how many such handlers, what it does and why it may stay)
    "worldguard/cli.py:_run:(OSError, UnicodeError, WorldInputError)": (5,
        "the command boundary for invalid input (one per command): prints WORLDGUARD_INPUT_INVALID with the message and "
        "exits 2. Only WorldInputError and unreadable files are caught; any other error inside WorldGuard is raised. "
        "README: `check` and `mesh-check` exit 2 on invalid input"),
    "worldguard/cli.py:_run:RecordError": (4,
        "the record of open contradictions cannot be read or written: prints WORLDGUARD_RECORD_ERROR with the record path "
        "and the check status and exits 2, so a contradiction is never silently not kept (WG-802: contradictions stay "
        "until resolved)"),
    "worldguard/cli.py:main:BrokenPipeError": (1,
        "the reader closed stdout early (`| head`): one stderr line saying the output is incomplete, exit 141, the shell's "
        "own code for this; it is neither an input error nor a check result"),
    "worldguard/clock.py:_parts:ValueError": (1,
        "asks the standard library whether a text is an ISO date-time; a failed parse is the answer, and a text that "
        "matches no time format is then raised as WorldInputError naming the accepted formats"),
    "worldguard/semantic.py:_evaluate_equations:(TypeError, ValueError, ZeroDivisionError, OverflowError)": (1,
        "a declared causal equation fails on its own values (for example a division by zero); the variable is reported "
        "as `name:ErrorType` and the scenario as unevaluable (CAUSAL_SCENARIO_UNEVALUABLE)"),
    "worldguard/semantic.py:_evaluate_equations:NameError": (1,
        "the equation reads a variable this pass has not computed yet; the next pass retries it, and a variable that "
        "never resolves is reported as `name:unresolved_dependencies`"),
    "worldguard/semantic.py:causal_constraint_findings:(NameError, TypeError, ValueError, ZeroDivisionError, OverflowError)": (1,
        "a declared constraint fails on one scenario's values; that scenario is listed as unevaluable with the error "
        "text (CAUSAL_CONSTRAINT_UNEVALUABLE)"),
    "worldguard/semantic.py:causal_constraint_findings:SyntaxError": (1,
        "a declared constraint is not an expression; it is listed as unevaluable with the accepted form"),
    "worldguard/semantic.py:equation_error:SyntaxError": (1,
        "a declared equation is not an expression; CausalGuard reports it with this reason"),
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
    assert found == {key: sites for key, (sites, _reason) in NON_RAISING_HANDLERS.items()}, \
        "a listed function gained or lost a handler that does not re-raise"
    assert all(len(reason.split()) >= 8 for _sites, reason in NON_RAISING_HANDLERS.values())


def test_nothing_silences_errors_another_way() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in _python_files())
    assert "suppress(" not in text, "contextlib.suppress hides the error the same way an empty handler does"
    assert "warnings.simplefilter" not in text and "filterwarnings" not in text


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


def test_a_skipped_test_fails_the_run(tmp_path) -> None:
    """A test can never pass by being skipped (for example because a handler made its input disappear)."""
    (tmp_path / "conftest.py").write_text((ROOT / "tests" / "conftest.py").read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "test_probe.py").write_text(
        "import pytest\n\ndef test_skipped():\n    pytest.skip('the input was not there')\n\n"
        "@pytest.mark.skip(reason='marked')\ndef test_marked():\n    pass\n\ndef test_fine():\n    pass\n", encoding="utf-8")
    result = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(tmp_path)],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1, result.stdout
    summary = result.stdout.strip().splitlines()[-1]
    assert summary.startswith("1 failed, 1 passed, 1 error") and "skipped" not in summary, summary
    assert result.stdout.count("skipped tests are not allowed") >= 2
