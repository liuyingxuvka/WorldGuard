"""The seven native Guards over their finite catalog: each good case passes, each bad case fails with exactly its own code."""
from dataclasses import dataclass
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
from tests.guard_catalog import NATIVE_GOOD_CASES, PROTECTED_FAILURE_CLASSES
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
CASES = (*(Case(row.case_id, row.guard, True) for row in NATIVE_GOOD_CASES), *(Case(row.failure_id, row.guard, False, row.expected_status, row.code) for row in PROTECTED_FAILURE_CLASSES))

def expected_RunGuard(case, state, mutation='', broken_guard=''):
    status, codes = (case.status, () if case.good else (case.code,))
    if not case.good and case.guard == broken_guard:
        if mutation == 'passes':
            status, codes = ('PASS', ())
        elif mutation == 'other_code':
            codes = (case.code + '_OTHER',)
    return State(case, status, codes)

def _keeps_code(guard):

    def check(state):
        case = state.case
        if case is None or case.guard != guard:
            return True
        if case.good and (state.status != 'PASS' or state.codes):
            return False
        if not case.good and (state.status != case.status or state.codes != (case.code,)):
            return False
        return True
    return check
RULES = (_keeps_code('EventGuard'), _keeps_code('AgentGuard'), _keeps_code('SpaceGuard'), _keeps_code('ResourceGuard'), _keeps_code('CausalGuard'), _keeps_code('ConflictGuard'), _keeps_code('NormGuard'))

def assert_native_contract():
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
        expected = expected_RunGuard(case, State())
        actual = (result.status.value, tuple((str(error.get('code', '')) for error in result.errors)))
        if actual != (expected.status, expected.codes):
            mismatches.append(f'{case.case_id}: expected {expected.status}/{expected.codes}, actual {actual}')
    assert not mismatches, mismatches
RULE_NAMES = ('event_guard_failures_keep_their_code', 'agent_guard_failures_keep_their_code', 'space_guard_failures_keep_their_code', 'resource_guard_failures_keep_their_code', 'causal_guard_failures_keep_their_code', 'conflict_guard_failures_keep_their_code', 'norm_guard_failures_keep_their_code')
