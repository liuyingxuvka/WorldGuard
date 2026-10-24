"""The seven native Guards over their finite catalog: each good case passes, each bad case fails with exactly its own code."""
from dataclasses import dataclass
from pathlib import Path
import sys

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.guard_catalog import NATIVE_GOOD_CASES, PROTECTED_FAILURE_CLASSES  # noqa: E402

MODEL_ID = 'guard_semantics'
PARENT = 'guards'
COMPONENTS = ['guards']
IMPLEMENTED_BY = {
    'EventGuard': 'worldguard/guards/event_guard.py:run',
    'AgentGuard': 'worldguard/guards/agent_guard.py:run',
    'SpaceGuard': 'worldguard/guards/space_guard.py:run',
    'ResourceGuard': 'worldguard/guards/resource_guard.py:run',
    'CausalGuard': 'worldguard/guards/causal_guard.py:run',
    'ConflictGuard': 'worldguard/guards/conflict_guard.py:run',
    'NormGuard': 'worldguard/guards/norm_guard.py:run',
}
TESTED_BY = {
    'event_guard_failures_keep_their_code': ['tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure',
                                             'tests/guards/test_status_matrix.py:test_guard_status_matrix'],
    'agent_guard_failures_keep_their_code': ['tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure',
                                             'tests/guards/test_status_matrix.py:test_guard_status_matrix'],
    'space_guard_failures_keep_their_code': ['tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure',
                                             'tests/guards/test_status_matrix.py:test_guard_status_matrix'],
    'resource_guard_failures_keep_their_code': ['tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure',
                                             'tests/guards/test_status_matrix.py:test_guard_status_matrix'],
    'causal_guard_failures_keep_their_code': ['tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure',
                                             'tests/guards/test_status_matrix.py:test_guard_status_matrix'],
    'conflict_guard_failures_keep_their_code': ['tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure',
                                             'tests/guards/test_status_matrix.py:test_guard_status_matrix'],
    'norm_guard_failures_keep_their_code': ['tests/test_guard_model_contract.py:test_guard_model_contract_has_one_good_per_guard_and_one_bad_per_failure',
                                             'tests/guards/test_status_matrix.py:test_guard_status_matrix'],
}
GUARDS = ('EventGuard', 'AgentGuard', 'SpaceGuard', 'ResourceGuard', 'CausalGuard', 'ConflictGuard', 'NormGuard')


@dataclass(frozen=True)
class Case:
    case_id: str
    guard: str
    good: bool
    status: str = 'PASS'
    code: str = ''


@dataclass(frozen=True)
class State:
    case: Case | None = None
    status: str = ''
    codes: tuple[str, ...] = ()


CASES = (*(Case(row.case_id, row.guard, True) for row in NATIVE_GOOD_CASES),
         *(Case(row.failure_id, row.guard, False, row.expected_status, row.code) for row in PROTECTED_FAILURE_CLASSES))


class RunGuard:
    """One Guard run on one catalog case: the native status and the codes of its errors."""
    name = 'RunGuard'
    reads = ()
    writes = ('case', 'status', 'codes')
    mutation = ''
    broken_guard = ''

    def apply(self, case, state):
        status, codes = case.status, (() if case.good else (case.code,))
        if not case.good and case.guard == self.broken_guard:
            if self.mutation == 'passes':
                status, codes = 'PASS', ()
            elif self.mutation == 'other_code':
                codes = (case.code + '_OTHER',)
        yield FunctionResult((status, codes), State(case, status, codes), label=status.lower())


def _keeps_code(guard):
    def check(state, trace):
        case = state.case
        if case is None or case.guard != guard:
            return InvariantResult.pass_()
        if case.good and (state.status != 'PASS' or state.codes):
            return InvariantResult.fail(f'{guard} rejected its catalog good case {case.case_id}')
        if not case.good and (state.status != case.status or state.codes != (case.code,)):
            return InvariantResult.fail(f'{guard} bad case {case.case_id} did not fail {case.status} with exactly {case.code}')
        return InvariantResult.pass_()
    return check


INVARIANTS = (
    Invariant('event_guard_failures_keep_their_code', 'EventGuard: good case passes, each bad case fails with its own code', _keeps_code('EventGuard')),
    Invariant('agent_guard_failures_keep_their_code', 'AgentGuard: good case passes, each bad case fails with its own code', _keeps_code('AgentGuard')),
    Invariant('space_guard_failures_keep_their_code', 'SpaceGuard: good case passes, each bad case fails with its own code', _keeps_code('SpaceGuard')),
    Invariant('resource_guard_failures_keep_their_code', 'ResourceGuard: good case passes, each bad case fails with its own code', _keeps_code('ResourceGuard')),
    Invariant('causal_guard_failures_keep_their_code', 'CausalGuard: good case passes, each bad case fails with its own code', _keeps_code('CausalGuard')),
    Invariant('conflict_guard_failures_keep_their_code', 'ConflictGuard: good case passes, each bad case fails with its own code', _keeps_code('ConflictGuard')),
    Invariant('norm_guard_failures_keep_their_code', 'NormGuard: good case passes, each bad case fails with its own code', _keeps_code('NormGuard')),
)


def explorer(step, names=None):
    invariants = tuple(row for row in INVARIANTS if names is None or row.name in names)
    return Explorer(Workflow((step,)), (State(),), CASES, invariants, progress_steps=0)


def build_explorer():
    return explorer(RunGuard())


def _broken(guard, mutation, invariant):
    step = RunGuard()
    step.broken_guard, step.mutation = guard, mutation
    return explorer(step, {invariant})


def broken_variants():
    return {
        'event_guard_bad_case_passes': _broken('EventGuard', 'passes', 'event_guard_failures_keep_their_code'),
        'agent_guard_bad_case_passes': _broken('AgentGuard', 'passes', 'agent_guard_failures_keep_their_code'),
        'space_guard_bad_case_passes': _broken('SpaceGuard', 'passes', 'space_guard_failures_keep_their_code'),
        'resource_guard_bad_case_passes': _broken('ResourceGuard', 'passes', 'resource_guard_failures_keep_their_code'),
        'causal_guard_bad_case_passes': _broken('CausalGuard', 'passes', 'causal_guard_failures_keep_their_code'),
        'conflict_guard_bad_case_passes': _broken('ConflictGuard', 'passes', 'conflict_guard_failures_keep_their_code'),
        'norm_guard_bad_case_passes': _broken('NormGuard', 'passes', 'norm_guard_failures_keep_their_code'),
        'event_guard_reports_another_code': _broken('EventGuard', 'other_code', 'event_guard_failures_keep_their_code'),
        'resource_guard_reports_another_code': _broken('ResourceGuard', 'other_code', 'resource_guard_failures_keep_their_code'),
    }


class ReplayReport:
    def __init__(self, checked, mismatches):
        self.checked, self.mismatches = checked, tuple(mismatches)
        self.ok = not mismatches

    def format_text(self, max_examples=None):
        return '\n'.join([f'conformance: {self.checked - len(self.mismatches)}/{self.checked}', *self.mismatches[:max_examples]])


def conformance():
    """Replay every catalog case through the real Guard runner; every Guard-owned failure code must have a case."""
    from tests.guard_catalog import _contract, discover_guard_owned_failure_codes
    from worldguard.guards import GUARD_RUNNERS
    mismatches = []
    if set(GUARD_RUNNERS) != set(GUARDS):
        mismatches.append(f'Guard registry {sorted(GUARD_RUNNERS)} differs from the model')
    discovered = {(guard, code) for (guard, _layer), codes in discover_guard_owned_failure_codes().items() for code in codes}
    covered = {(case.guard, case.code) for case in CASES if not case.good}
    if discovered - covered:
        mismatches.append(f'failure codes without a catalog case: {sorted(discovered - covered)}')
    goods = {row.case_id: row for row in NATIVE_GOOD_CASES}
    bads = {row.failure_id: row for row in PROTECTED_FAILURE_CLASSES}
    for case in CASES:
        row = goods.get(case.case_id) if case.good else bads.get(case.case_id)
        semantics = () if case.good else row.semantics
        result = GUARD_RUNNERS[case.guard](_contract(case.case_id, case.guard, row.text, row.inputs, semantics))
        expected = next(RunGuard().apply(case, State())).new_state
        actual = (result.status.value, tuple(str(error.get('code', '')) for error in result.errors))
        if actual != (expected.status, expected.codes):
            mismatches.append(f'{case.case_id}: expected {expected.status}/{expected.codes}, actual {actual}')
    return ReplayReport(len(CASES), mismatches)


if __name__ == '__main__':
    good = build_explorer().explore()
    print(good.format_text())
    caught = []
    for name, variant in broken_variants().items():
        failed = not variant.explore().ok
        caught.append(failed)
        print(f'{name}: {"caught" if failed else "MISSED"}')
    replay = conformance()
    print(replay.format_text())
    raise SystemExit(0 if good.ok and all(caught) and replay.ok else 1)
