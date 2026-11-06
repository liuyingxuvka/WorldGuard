"""The one WorldGuard exception policy; fixed generated queries own source scanning."""
from collections import Counter
from typing import NamedTuple

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


def handler_key(row):
    return row['file'] + ':' + (row['node'].partition(':')[2] or '<module>') + ':' + (row['type'] or 'BARE')


def handler_rows(graph):
    return [row for row in graph.handlers() if row['kind'] == 'except' and row['non_raising']]


def handler_counts(graph):
    return dict(Counter(handler_key(row) for row in handler_rows(graph)))


def silencers(graph):
    result = [row for row in graph.handlers() if row['kind'] in {'suppress', 'finally', 'exit_method'}]
    names = {'suppress', 'simplefilter', 'filterwarnings', 'catch_warnings'}
    for row in graph.calls(include_reads=True):
        if row.get('read'):
            # The prior policy bans the filterwarnings attribute even before a call,
            # not every ordinary reference to another warning helper.
            if '.' in row['text'] and row['text'].rsplit('.', 1)[-1] == 'filterwarnings':
                result.append(row)
        elif (row['resolved'] or row['text']).rsplit('.', 1)[-1] in names:
            result.append(row)
    # External declaration rows retain an unused alias import without executing it.
    result += [row for row in graph.imports(declarations=True) if row['module'] in {'warnings', 'contextlib'}
               and row['name'] in names]
    return result


def violations(graph):
    rows = [dict(row, node=handler_key(row)) for row in handler_rows(graph)]
    actual = handler_counts(graph)
    for key, expected in NON_RAISING_HANDLERS.items():
        if actual.get(key) != expected.count:
            rows.append(f'handler count {key}: {actual.get(key, 0)} instead of {expected.count}')
    rows += silencers(graph)
    for requirement, (path, sentence) in REQUIREMENTS.items():
        words = ' '.join((graph.root / path).read_text(encoding='utf-8').split())
        if ' '.join(sentence.split()) not in words:
            rows.append(f'{requirement}: {path} no longer states the exception boundary')
    return rows
