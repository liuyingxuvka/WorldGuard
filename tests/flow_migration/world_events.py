"""world_events: one native command or one stage of check."""
from dataclasses import dataclass, replace
from ._world_fixture import CheckRequest, EXTERNAL_INPUTS as REQUESTS, replay, stage_values, _terminal_check
MUTATIONS = {'illegal_event_applies_effects': 'illegal_event_has_no_effect', 'causal_copy_drifts': 'event_times_reach_constraints', 'string_sorted_times': 'clock_times_order_events', 'norms_ignore_events': 'forbidden_event_fails', 'tokens_cloned': 'unique_tokens_stay_unique', 'token_event_drift_ignored': 'tokens_match_events', 'transition_event_link_ignored': 'transitions_name_events', 'space_token_drift_ignored': 'space_matches_tokens'}
CASES = (CheckRequest('illegal_event_effect', rows='illegal_effect'),) + tuple((q for q in REQUESTS if q.case_id in ('clock_good', 'clock_reversed', 'event_clock', 'missing_event_time', 'forbidden_event', 'tokens_cloned', 'token_event_mismatch', 'transition_unlinked', 'space_token_agrees', 'space_token_disjoint', 'space_token_unrelated')))

@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    event_order_correct: bool = True
    status: str = ''
    effect_applied: bool = False

def expected_Evaluate(q, state, mutation='', broken_guard=''):
    order = True if mutation == 'string_sorted_times' and q.time_form == 'clock' else q.event_order_correct
    failure = not order or (q.scm_mode == 'event_clock' and mutation != 'causal_copy_drifts') or (q.forbidden_event and mutation != 'norms_ignore_events') or (q.tokens_cloned and mutation != 'tokens_cloned') or (q.token_event_mismatch and mutation != 'token_event_drift_ignored') or (q.space_token == 'disjoint' and mutation != 'space_token_drift_ignored')
    gap = q.time_form == 'missing' or (q.transition_unlinked and mutation != 'transition_event_link_ignored') or (q.space_token == 'unrelated' and mutation != 'space_token_drift_ignored')
    new = State(q, order, 'FAIL' if failure else 'GAP' if gap else 'PASS')
    if q.case_id == 'illegal_event_effect':
        new = replace(new, status='FAIL', effect_applied=mutation == 'illegal_event_applies_effects')
    return new

def event_times_reach_constraints(state):
    return _terminal_check(state, lambda request: request.scm_mode == 'event_clock', (1, 'FAIL'), 'A timetable edit did not reach its causal constraint')

def clock_times_order_events(state):
    return _terminal_check(state, lambda request: request.time_form == 'clock' and (not request.event_order_correct), (1, 'FAIL'), 'A reversed clock-order precondition/claim did not fail')

def forbidden_event_fails(state):
    return _terminal_check(state, lambda request: request.forbidden_event, (1, 'FAIL'), 'An active prohibition ignored its event')

def unique_tokens_stay_unique(state):
    return _terminal_check(state, lambda request: request.tokens_cloned, (1, 'FAIL'), 'A duplicated unique token passed')

def tokens_match_events(state):
    return _terminal_check(state, lambda request: request.token_event_mismatch, (1, 'FAIL'), 'A token/fluent disagreement at a linked event did not fail')

def transitions_name_events(state):
    return _terminal_check(state, lambda request: request.transition_unlinked, (1, 'GAP'), 'An unlinked resource transition was not named as missing event evidence')

def space_matches_tokens(state):
    disjoint = _terminal_check(state, lambda request: request.space_token == 'disjoint', (1, 'FAIL'), "A single token's place contradicting its spatial region did not fail")
    if not disjoint:
        return disjoint
    return _terminal_check(state, lambda request: request.space_token == 'unrelated', (1, 'GAP'), "A single token's place unrelated to its spatial region was not a gap")

def illegal_event_has_no_effect(state):
    if state.request and state.request.case_id == 'illegal_event_effect' and state.effect_applied:
        return False
    return True
RULES = (illegal_event_has_no_effect, event_times_reach_constraints, clock_times_order_events, forbidden_event_fails, unique_tokens_stay_unique, tokens_match_events, transitions_name_events, space_matches_tokens)

def assert_native_contract():
    mismatches = []
    checked = 0
    for request in CASES:
        if request.case_id == 'illegal_event_effect':
            import tempfile, io, json
            from pathlib import Path
            from contextlib import redirect_stdout
            from worldguard.cli import main
            contract = {'claim': {'claim_id': 'illegal-effect', 'asserts': [{'holds': 'F', 'at': 't2'}]}, 'inputs': {'events': [{'event_id': 'illegal', 'at': 't1', 'requires': 'missing', 'initiates': 'F'}]}}
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'world.json'
                path.write_text(json.dumps(contract))
                output = io.StringIO()
                with redirect_stdout(output):
                    code = main(['check', '--contract', str(path), '--json'])
                report = json.loads(output.getvalue())
            if report['claim_binding']['assertions'][0]['status'] != 'FAIL' or not any((row['code'] == 'CLAIM_ASSERTION_FALSE' and row.get('claim_row') == 0 for row in report.get('gaps', []))):
                mismatches.append('illegal_event_has_no_effect: the illegal initiation still satisfies the later assertion')
        else:
            code, report = replay(request)
        expected = expected_Evaluate(request, State()).status
        actual = stage_values(request, code, report)[1]
        if actual != expected:
            mismatches.append(f'{request.case_id}: stage {expected!r}, native {actual!r}')
        from ._world_fixture import witness_assertions
        witness_assertions(request, report.get('gaps', []))
        if report['status'] != expected:
            mismatches.append(f'{request.case_id}: native status differs from the event contribution')
        checked += 1
    assert not mismatches, mismatches
RULE_NAMES = ('illegal_event_has_no_effect', 'event_times_reach_constraints', 'clock_times_order_events', 'forbidden_event_fails', 'unique_tokens_stay_unique', 'tokens_match_events', 'transitions_name_events', 'space_matches_tokens')
