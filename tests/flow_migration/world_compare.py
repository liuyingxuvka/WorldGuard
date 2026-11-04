"""world_compare: one native command or one stage of check."""
from dataclasses import dataclass, replace
from ._world_fixture import CheckRequest, EXTERNAL_INPUTS as REQUESTS, replay, stage_values, _terminal_check
MUTATIONS = {'tolerance_ignored': 'compare_flags_values_outside_tolerance', 'observed_copy_shifts_downstream': 'observedcopy_only_selected_event'}
CASES = tuple((q for q in REQUESTS if q.case_id in ('compare_match', 'compare_mismatch', 'observed_copy')))

@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    status: str = ''
    copied_fields: tuple[str, ...] = ()

def expected_Evaluate(q, state, mutation='', broken_guard=''):
    status = 'FAIL' if q.compare_mismatch and mutation != 'tolerance_ignored' else 'PASS'
    fields = (('event:first:at', 'event:second:at') if mutation == 'observed_copy_shifts_downstream' else ('event:first:at',)) if q.observed_copy else ()
    new = State(q, status, fields)
    return new

def compare_flags_values_outside_tolerance(state):
    return _terminal_check(state, lambda request: request.compare and request.compare_mismatch, (1, 'FAIL'), 'A supplied observation outside tolerance was accepted')

def observedcopy_only_selected_event(state):
    if state.request is not None and state.request.observed_copy:
        if state.copied_fields != ('event:first:at',):
            return False
    return True
RULES = (compare_flags_values_outside_tolerance, observedcopy_only_selected_event)

def assert_native_contract():
    mismatches = []
    checked = 0
    for request in CASES:
        expected = expected_Evaluate(request, State()).status
        for write_copy in (False, True):
            code, report = replay(request, write_observed=write_copy)
            if (code, report['status']) != (0 if expected == 'PASS' else 1, expected):
                mismatches.append(f'{request.case_id}: compare exit/status differs')
        checked += 1
    assert not mismatches, mismatches
RULE_NAMES = ('compare_flags_values_outside_tolerance', 'observedcopy_only_selected_event')
