"""world_compare: one native command or one stage of check."""
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from _world_fixture import CheckRequest, EXTERNAL_INPUTS as REQUESTS, ReplayReport, replay, stage_values, _terminal_check

MODEL_ID = 'world_compare'
PARENT = 'qualification'
IMPLEMENTED_BY = {'CompareObserved': 'worldguard/compare.py:compare_world', 'CopySelectedObservation': 'worldguard/compare.py:compare_with_observed_copy'}
USES = {"Main": "worldguard/cli.py:main"}
TESTED_BY = {'compare_flags_values_outside_tolerance': ['tests/test_compare.py:test_trip_arrival_uses_minutes_and_declared_tolerance'], 'observedcopy_only_selected_event': ['tests/test_compare.py:test_written_observed_copy_shows_the_downstream_break']}
MUTATIONS = {'tolerance_ignored': 'compare_flags_values_outside_tolerance', 'observed_copy_shifts_downstream': 'observedcopy_only_selected_event'}
CASES = tuple(q for q in REQUESTS if q.case_id in ('compare_match', 'compare_mismatch', 'observed_copy'))

@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    status: str = ''
    copied_fields: tuple[str, ...] = ()

class Evaluate:
    name = "Evaluate"
    reads = ("request",)
    writes = ('request', 'status', 'copied_fields')
    def __init__(self, mutation=""): self.mutation=mutation
    def apply(self, q, state):
        status='FAIL' if q.compare_mismatch and self.mutation!='tolerance_ignored' else 'PASS'
        fields=(('event:first:at','event:second:at') if self.mutation=='observed_copy_shifts_downstream' else ('event:first:at',)) if q.observed_copy else ()
        new=State(q,status,fields)
        yield FunctionResult(new,new,label=q.case_id)

def compare_flags_values_outside_tolerance(state, trace):
    return _terminal_check(state, lambda request: request.compare and request.compare_mismatch,
                           (1, "FAIL"), "A supplied observation outside tolerance was accepted")


def observedcopy_only_selected_event(state, trace):
    if state.request is not None and state.request.observed_copy:
        if state.copied_fields != ("event:first:at",):
            return InvariantResult.fail("An observed copy changed a later event, scenario or causal variable")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant('compare_flags_values_outside_tolerance','Observed differences outside tolerance fail',compare_flags_values_outside_tolerance),
    Invariant('observedcopy_only_selected_event','Observed copy only changes the selected event time',observedcopy_only_selected_event),
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
            expected=next(Evaluate().apply(request,State())).new_state.status
            for write_copy in (False,True):
                code,report=replay(request,write_observed=write_copy)
                if (code,report['status'])!=(0 if expected=='PASS' else 1,expected):mismatches.append(f'{request.case_id}: compare exit/status differs')
        except Exception as exc:mismatches.append(f'{request.case_id}: native replay raised {type(exc).__name__}: {exc}')
        checked+=1
    return ReplayReport(checked,mismatches)
