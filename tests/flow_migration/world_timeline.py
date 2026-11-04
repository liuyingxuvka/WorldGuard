"""world_timeline: one native command or one stage of check."""
from dataclasses import dataclass, replace
from ._world_fixture import CheckRequest, EXTERNAL_INPUTS as REQUESTS, replay, stage_values, _terminal_check
MUTATIONS = {'timeline_repeats_full_state': 'timeline_shows_changes_after_start', 'timeline_drops_non_event_problems': 'timeline_shows_every_problem'}
CASES = tuple((q for q in REQUESTS if q.case_id in ('timeline_late_ferry',)))

@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    timeline_complete: bool = True
    changes_match: bool = True

def expected_Evaluate(q, state, mutation='', broken_guard=''):
    new = State(q, mutation != 'timeline_drops_non_event_problems', mutation != 'timeline_repeats_full_state')
    return new

def timeline_shows_every_problem(state):
    if state.request is not None and state.request.timeline and (not state.timeline_complete):
        return False
    return True

def timeline_shows_changes_after_start(state):
    return True if state.changes_match else False
RULES = (timeline_shows_changes_after_start, timeline_shows_every_problem)

def assert_native_contract():
    mismatches = []
    checked = 0
    for request in CASES:
        from ._world_fixture import replay_timeline
        replay_timeline(request)
        from ._world_fixture import _real_contract
        from worldguard.timeline import timeline, render_timeline_text
        view = timeline(_real_contract(request))
        rows = [line.split('fluents: ', 1)[1].split(' | tokens:', 1)[0] for line in render_timeline_text(view).splitlines() if 'fluents: ' in line]
        if len(rows) != len(view['steps']):
            mismatches.append('timeline_shows_changes_after_start: missing steps')
        else:
            state = set() if rows[0] == '-' else set(rows[0].split(', '))
            for index, (row, step) in enumerate(zip(rows, view['steps'])):
                if index and row != '=':
                    for change in row.split():
                        if change.startswith('+'):
                            state.add(change[1:])
                        elif change.startswith('-'):
                            state.discard(change[1:])
                        else:
                            mismatches.append('timeline_shows_changes_after_start: expected a signed delta')
                if state != set(step['fluents']):
                    mismatches.append('timeline_shows_changes_after_start: text cannot reconstruct native JSON')
        checked += 1
    assert not mismatches, mismatches
RULE_NAMES = ('timeline_shows_changes_after_start', 'timeline_shows_every_problem')
