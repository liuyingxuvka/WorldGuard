"""world_events: one native command or one stage of check."""
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from _world_fixture import CheckRequest, EXTERNAL_INPUTS as REQUESTS, ReplayReport, replay, stage_values, _terminal_check

MODEL_ID = 'world_events'
PARENT = 'world_check'
READS_PARENT = ("request",)
OUTPUTS = {"status": ('PASS', 'FAIL', 'GAP')}
IMPLEMENTED_BY = {'ReplayTokens': 'worldguard/semantic.py:token_replay', 'CheckEventTokens': 'worldguard/qualification.py:_event_token_consistency', 'CheckSpaceTokens': 'worldguard/qualification.py:_space_token_consistency'}
USES = {"Main": "worldguard/cli.py:main"}
TESTED_BY = {'event_times_reach_constraints': ['tests/test_world_model_language.py:test_event_times_drive_causal_constraints_without_another_timetable'], 'clock_times_order_events': ['tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively'], 'forbidden_event_fails': ['tests/test_world_model_language.py:test_storm_prohibition_applies_to_the_actual_boat_event'], 'unique_tokens_stay_unique': ['tests/test_world_model_language.py:test_unique_traveler_duplication_fails_and_a_foreign_actor_is_a_gap'], 'tokens_match_events': ['tests/test_world_model_language.py:test_tokens_that_disagree_with_events_fail_at_the_step'], 'transitions_name_events': ['tests/test_world_model_language.py:test_unlinked_transition_is_a_gap_naming_it'], 'space_matches_tokens': ['tests/test_qualification.py:test_space_rows_agree_with_token_places']}
MUTATIONS = {'causal_copy_drifts': 'event_times_reach_constraints', 'string_sorted_times': 'clock_times_order_events', 'norms_ignore_events': 'forbidden_event_fails', 'tokens_cloned': 'unique_tokens_stay_unique', 'token_event_drift_ignored': 'tokens_match_events', 'transition_event_link_ignored': 'transitions_name_events', 'space_token_drift_ignored': 'space_matches_tokens'}
CASES = tuple(q for q in REQUESTS if q.case_id in ('clock_good', 'clock_reversed', 'event_clock', 'missing_event_time', 'forbidden_event', 'tokens_cloned', 'token_event_mismatch', 'transition_unlinked', 'space_token_agrees', 'space_token_disjoint', 'space_token_unrelated'))

@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    event_order_correct: bool = True
    status: str = ''

class Evaluate:
    name = "Evaluate"
    reads = ("request",)
    writes = ('request', 'event_order_correct', 'status')
    def __init__(self, mutation=""): self.mutation=mutation
    def apply(self, q, state):
        order = True if self.mutation=='string_sorted_times' and q.time_form=='clock' else q.event_order_correct
        failure=(not order or q.scm_mode=='event_clock' and self.mutation!='causal_copy_drifts'
                 or q.forbidden_event and self.mutation!='norms_ignore_events'
                 or q.tokens_cloned and self.mutation!='tokens_cloned'
                 or q.token_event_mismatch and self.mutation!='token_event_drift_ignored'
                 or q.space_token=='disjoint' and self.mutation!='space_token_drift_ignored')
        gap=(q.time_form=='missing' or q.transition_unlinked and self.mutation!='transition_event_link_ignored'
             or q.space_token=='unrelated' and self.mutation!='space_token_drift_ignored')
        new=State(q,order,'FAIL' if failure else 'GAP' if gap else 'PASS')
        yield FunctionResult(new,new,label=q.case_id)

def event_times_reach_constraints(state, trace):
    return _terminal_check(state, lambda request: request.scm_mode == "event_clock", (1, "FAIL"), "A timetable edit did not reach its causal constraint")


def clock_times_order_events(state, trace):
    return _terminal_check(state, lambda request: request.time_form == "clock" and not request.event_order_correct, (1, "FAIL"), "A reversed clock-order precondition/claim did not fail")


def forbidden_event_fails(state, trace):
    return _terminal_check(state, lambda request: request.forbidden_event, (1, "FAIL"), "An active prohibition ignored its event")


def unique_tokens_stay_unique(state, trace):
    return _terminal_check(state, lambda request: request.tokens_cloned, (1, "FAIL"), "A duplicated unique token passed")


def tokens_match_events(state, trace):
    return _terminal_check(state, lambda request: request.token_event_mismatch, (1, "FAIL"),
                           "A token/fluent disagreement at a linked event did not fail")


def transitions_name_events(state, trace):
    return _terminal_check(state, lambda request: request.transition_unlinked, (1, "GAP"),
                           "An unlinked resource transition was not named as missing event evidence")


def space_matches_tokens(state, trace):
    disjoint = _terminal_check(state, lambda request: request.space_token == "disjoint", (1, "FAIL"),
                               "A single token's place contradicting its spatial region did not fail")
    if not disjoint.ok:
        return disjoint
    return _terminal_check(state, lambda request: request.space_token == "unrelated", (1, "GAP"),
                           "A single token's place unrelated to its spatial region was not a gap")


INVARIANTS = (
    Invariant('event_times_reach_constraints','One event clock reaches causal constraints',event_times_reach_constraints),
    Invariant('clock_times_order_events','A reversed clock order fails',clock_times_order_events),
    Invariant('forbidden_event_fails','A forbidden actual action fails',forbidden_event_fails),
    Invariant('unique_tokens_stay_unique','A unique color never duplicates',unique_tokens_stay_unique),
    Invariant('tokens_match_events','Every linked event shares one token/fluent state',tokens_match_events),
    Invariant('transitions_name_events','A resource transition must name its event',transitions_name_events),
    Invariant('space_matches_tokens',"A single token's place agrees with the spatial relations declared at the same time",space_matches_tokens),
)

def make(mutation='', names=None):
    return Explorer(Workflow((Evaluate(mutation),)), (State(),), CASES,
                    tuple(rule for rule in INVARIANTS if names is None or rule.name in names),
                    max_sequence_length=1, progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {name: make(name,{rule}) for name,rule in MUTATIONS.items()}

def conformance():
    mismatches=[];checked=0
    for request in CASES:
        try:
            code,report=replay(request)
            expected=next(Evaluate().apply(request,State())).new_state.status
            actual=stage_values(request,code,report)[1]
            if actual!=expected:mismatches.append(f'{request.case_id}: stage {expected!r}, native {actual!r}')
            from _world_fixture import witness_assertions
            witness_assertions(request,report.get('gaps',[]))
            if report['status']!=expected:mismatches.append(f'{request.case_id}: native status differs from the event contribution')
        except Exception as exc:mismatches.append(f'{request.case_id}: native replay raised {type(exc).__name__}: {exc}')
        checked+=1
    return ReplayReport(checked,mismatches)
