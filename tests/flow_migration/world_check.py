"""The coarse check lifecycle receives stage contributions and preserves their exit boundary."""
from dataclasses import dataclass, replace
from ._world_fixture import CheckRequest, EXTERNAL_INPUTS as REQUESTS, replay, stage_values, worst
CHILD_RESULTS = {'label': ('PASS', 'PASS', 'PASS', 'PASS'), 'word_time': ('error', '', '', ''), 'duplicate_ids': ('error', '', '', ''), 'tokens_cloned': ('PASS', 'FAIL', 'PASS', 'FAIL'), 'transition_unlinked': ('PASS', 'GAP', 'PASS', 'PASS'), 'scenario_late': ('PASS', 'PASS', 'FAIL', 'FAIL'), 'owned_boundary': ('PASS', 'PASS', 'BOUNDARY_EXCEEDED', 'BOUNDARY_EXCEEDED'), 'uncaught_variant': ('PASS', 'PASS', 'PASS', 'PASS'), 'unbound': ('PASS', 'PASS', 'PASS', 'PASS'), 'false_row': ('PASS', 'PASS', 'PASS', 'PASS'), 'missing_event_time': ('PASS', 'GAP', 'PASS', 'GAP'), 'partial_run_gap': ('PASS', 'PASS', 'GAP', 'GAP'), 'unknown_row': ('PASS', 'PASS', 'PASS', 'PASS'), 'foreign_boundary': ('PASS', 'PASS', 'PASS', 'GAP'), 'boundary_with_fail': ('PASS', 'FAIL', 'BOUNDARY_EXCEEDED', 'FAIL'), 'boundary_with_gap': ('PASS', 'GAP', 'BOUNDARY_EXCEEDED', 'GAP')}
OWN_CASES = ('unbound', 'false_row', 'unknown_row', 'uncaught_variant', 'foreign_boundary', 'boundary_with_fail', 'boundary_with_gap')
CHILD_RESULTS.update(actor_state_unchecked=('PASS', 'PASS', 'PASS', 'GAP'), actor_state_free=('PASS', 'PASS', 'PASS', 'PASS'))
OWN_CASES += ('actor_state_unchecked', 'actor_state_free')
CASES = tuple((q for q in REQUESTS if q.case_id in CHILD_RESULTS))

@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    input_status: str = ''
    events_status: str = ''
    consistency_status: str = ''
    guard_status: str = ''
    row_status: str = ''
    aggregate_status: str = ''
    rows: tuple[str, ...] = ()
    exit_code: int | None = None
    status: str = ''
    terminal: bool = False

def expected_TakeRequest(request, state, mutation='', broken_guard=''):
    return State(request=request)

def expected_ReceiveInput(request, state, mutation='', broken_guard=''):
    value = CHILD_RESULTS[state.request.case_id][0]
    return replace(state, input_status=value)

def expected_ReceiveStages(request, state, mutation='', broken_guard=''):
    values = CHILD_RESULTS[state.request.case_id][1:3] if state.input_status != 'error' else ('', '')
    if state.input_status == 'error' and mutation == 'stages_run_after_parse_error':
        values = ('PASS', 'PASS')
    return replace(state, events_status=values[0], consistency_status=values[1])

def expected_RunGuards(request, state, mutation='', broken_guard=''):
    value = CHILD_RESULTS[state.request.case_id][3] if state.input_status != 'error' else ''
    if mutation == 'actor_state_ignored' and state.request.actor_state == 'unchecked':
        value = 'PASS'
    return replace(state, guard_status=value)

def expected_EvaluateClaimRows(request, state, mutation='', broken_guard=''):
    q = state.request
    if state.input_status == 'error':
        value = ''
    elif q.rows == 'none':
        value = 'PASS' if mutation == 'unbound_claim_passes' else 'GAP'
    elif q.rows == 'unknown':
        value = 'GAP'
    elif q.uncaught_variant:
        value = 'PASS' if mutation == 'variants_ignored' else 'GAP'
    elif q.rows == 'false':
        value = 'FAIL'
    elif q.rows == 'order':
        value = state.events_status
    elif q.rows == 'variable':
        value = worst((state.events_status, state.consistency_status))
    else:
        value = 'PASS'
    return replace(state, row_status=value)

def expected_Aggregate(request, state, mutation='', broken_guard=''):
    statuses = [(name, getattr(state, name)) for name in ('events_status', 'consistency_status', 'guard_status', 'row_status')]
    values = [v for _, v in statuses]
    if mutation == 'ignores_gap':
        values = [v for v in values if v != 'GAP']
    value = 'error' if state.input_status == 'error' else worst(values)
    rows = tuple((name + ':' + v for name, v in statuses if v and v != 'PASS'))
    if mutation == 'layered_duplicates' and rows:
        rows += rows[:1]
    return replace(state, aggregate_status=value, rows=rows)

def expected_ReportExit(request, state, mutation='', broken_guard=''):
    status = 'error' if state.input_status == 'error' else state.aggregate_status
    code = 2 if status == 'error' else 0 if status == 'PASS' else 1
    label = {'error': 'input_error', 'PASS': 'passed', 'FAIL': 'failed', 'GAP': 'gap', 'BOUNDARY_EXCEEDED': 'boundary_exceeded'}[status]
    return replace(state, exit_code=code, status=status, terminal=True)

def _terminal_check(state, applies, expected, message):
    if state.terminal and state.request is not None and applies(state.request) and ((state.exit_code, state.status) != expected):
        return False
    return True

def pass_needs_bound_true_rows(state):
    if state.terminal and state.request is not None and (state.status == 'PASS'):
        if state.request.rows in {'none', 'false', 'unknown'} or state.row_status != 'PASS' or state.guard_status != 'PASS':
            return False
    return _terminal_check(state, lambda request: request.rows == 'none', (1, 'GAP'), 'An unbound claim did not remain a gap')

def variants_must_fail(state):
    return _terminal_check(state, lambda request: request.uncaught_variant, (1, 'GAP'), 'An uncaught known-bad variant allowed PASS')

def one_row_per_problem(state):
    if state.terminal and len(state.rows) != len(set(state.rows)):
        return False
    return True

def actor_state_checked(state):
    if state.terminal and state.request.actor_state != 'none':
        expected = ('GAP', 1, 'GAP') if state.request.actor_state == 'unchecked' else ('PASS', 0, 'PASS')
        if (state.guard_status, state.exit_code, state.status) != expected:
            return False
    return True

def child_status_decides_exit(state):
    if not state.terminal:
        return True
    if state.input_status == 'error':
        expected = (2, 'error')
        if state.events_status or state.consistency_status or state.guard_status:
            return False
    else:
        value = worst((state.events_status, state.consistency_status, state.guard_status, state.row_status))
        expected = (0 if value == 'PASS' else 1, value)
    if (state.exit_code, state.status) != expected:
        return False
    return True
RULES = (actor_state_checked, pass_needs_bound_true_rows, variants_must_fail, one_row_per_problem, child_status_decides_exit)
MUTATIONS = {'unbound_claim_passes': 'pass_needs_bound_true_rows', 'variants_ignored': 'variants_must_fail', 'layered_duplicates': 'one_row_per_problem', 'stages_run_after_parse_error': 'child_status_decides_exit', 'ignores_gap': 'child_status_decides_exit', 'actor_state_ignored': 'actor_state_checked'}

def outcome(request, mutation=''):
    state = expected_TakeRequest(request, State())
    state = expected_ReceiveInput(request, state)
    state = expected_ReceiveStages(request, state, mutation)
    state = expected_RunGuards(request, state, mutation)
    state = expected_EvaluateClaimRows(request, state, mutation)
    state = expected_Aggregate(request, state, mutation)
    return expected_ReportExit(request, state)

def assert_native_contract():
    mismatches = []
    checked = 0
    requests = {q.case_id: q for q in CASES}
    for case in dict.fromkeys((*OWN_CASES, *CHILD_RESULTS)):
        request = requests[case]
        code, report = replay(request)
        state = outcome(request)
        if (code, report['status']) != (state.exit_code, state.status):
            mismatches.append(f'{case}: exit/status differs')
        if case in CHILD_RESULTS and stage_values(request, code, report) != CHILD_RESULTS[case]:
            mismatches.append(f'{case}: coarse received values differ from native contributions')
        gaps = report.get('gaps', [])
        if request.actor_state == 'unchecked':
            actor_rows = [row for row in gaps if row['code'] == 'EVENT_ACTOR_STATE_UNCHECKED']
            if len(actor_rows) != 1 or any((actor_rows[0].get(key) != value for key, value in {'status': 'GAP', 'event_id': 'unlock', 'actor': 'Lena', 'source': 'actor fixture', 'missing': ['place', 'uses']}.items())):
                mismatches.append('actor_state_checked: native gap does not name the event, actor and missing place and uses')
        if request.actor_state == 'free':
            if gaps or 'actor_state_free unlock (Lena): the door opens from either side' not in report['scope_limits']:
                mismatches.append('actor_state_checked: native free exemption omitted its reason or did not pass')
        identities = [(row['code'], row.get('guard'), row.get('claim_row'), row.get('variant_id'), row.get('event_id')) for row in gaps]
        if len(identities) != len(set(identities)):
            mismatches.append(f'{case}: one_row_per_problem failed')
        checked += 1
    assert not mismatches, mismatches
RULE_NAMES = ('actor_state_checked', 'pass_needs_bound_true_rows', 'variants_must_fail', 'one_row_per_problem', 'child_status_decides_exit')
