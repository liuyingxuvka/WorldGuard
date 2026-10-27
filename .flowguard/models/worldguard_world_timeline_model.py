"""world_timeline: one native command or one stage of check."""
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from _world_fixture import CheckRequest, EXTERNAL_INPUTS as REQUESTS, ReplayReport, replay, stage_values, _terminal_check

MODEL_ID = 'world_timeline'
PARENT = 'core'
IMPLEMENTED_BY = {'RenderTimeline': 'worldguard/timeline.py:render_timeline_text', 'ShowTimeline': 'worldguard/timeline.py:timeline'}
USES = {"Main": "worldguard/cli.py:main"}
TESTED_BY = {'timeline_shows_changes_after_start': ['tests/test_variants_timeline.py:test_timeline_prints_changes_after_the_start_line'], 'timeline_shows_every_problem': ['tests/test_variants_timeline.py:test_timeline_shows_claims_submodels_and_every_problem']}
MUTATIONS = {'timeline_repeats_full_state': 'timeline_shows_changes_after_start', 'timeline_drops_non_event_problems': 'timeline_shows_every_problem'}
CASES = tuple(q for q in REQUESTS if q.case_id in ('timeline_late_ferry',))

@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    timeline_complete: bool = True
    changes_match: bool = True

class Evaluate:
    name = "Evaluate"
    reads = ("request",)
    writes = ('request', 'timeline_complete', 'changes_match')
    def __init__(self, mutation=""): self.mutation=mutation
    def apply(self, q, state):
        new=State(q,self.mutation!='timeline_drops_non_event_problems',self.mutation!='timeline_repeats_full_state')
        yield FunctionResult(new,new,label=q.case_id)

def timeline_shows_every_problem(state, trace):
    if state.request is not None and state.request.timeline and not state.timeline_complete:
        return InvariantResult.fail("The timeline dropped a problem or claim row of the native report")
    return InvariantResult.pass_()


def timeline_shows_changes_after_start(state, trace):
    return InvariantResult.pass_() if state.changes_match else InvariantResult.fail('The text repeats a full state instead of reversible changes')

INVARIANTS = (
    Invariant('timeline_shows_changes_after_start','Applying printed changes to the start state reconstructs every native timeline state.',timeline_shows_changes_after_start),
    Invariant('timeline_shows_every_problem','The timeline shows every claim row and every problem code of the check',timeline_shows_every_problem),
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
            from _world_fixture import replay_timeline
            replay_timeline(request)
            from _world_fixture import _real_contract
            from worldguard.timeline import timeline, render_timeline_text
            view=timeline(_real_contract(request))
            rows=[line.split('fluents: ',1)[1].split(' | tokens:',1)[0] for line in render_timeline_text(view).splitlines() if 'fluents: ' in line]
            if len(rows)!=len(view['steps']):
                mismatches.append('timeline_shows_changes_after_start: missing steps')
            else:
                state=set() if rows[0]=='-' else set(rows[0].split(', '))
                for index,(row,step) in enumerate(zip(rows,view['steps'])):
                    if index and row!='=':
                        for change in row.split():
                            if change.startswith('+'):state.add(change[1:])
                            elif change.startswith('-'):state.discard(change[1:])
                            else:mismatches.append('timeline_shows_changes_after_start: expected a signed delta')
                    if state!=set(step['fluents']):mismatches.append('timeline_shows_changes_after_start: text cannot reconstruct native JSON')
        except Exception as exc:mismatches.append(f'{request.case_id}: native replay raised {type(exc).__name__}: {exc}')
        checked+=1
    return ReplayReport(checked,mismatches)
