"""world_consistency: one native command or one stage of check."""
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from _world_fixture import CheckRequest, EXTERNAL_INPUTS as REQUESTS, ReplayReport, replay, stage_values, _terminal_check

MODEL_ID = 'world_consistency'
PARENT = 'world_check'
COMPONENTS = ['qualification']
READS_PARENT = ("request",)
OUTPUTS = {"status": ('PASS', 'FAIL', 'GAP', 'BOUNDARY_EXCEEDED')}
IMPLEMENTED_BY = {'EvaluateScenarios': 'worldguard/semantic.py:causal_scenario_values'}
USES = {"Main": "worldguard/cli.py:main"}
TESTED_BY = {'scenario_values_reach_constraints': ['tests/test_world_model_language.py:test_scenario_overrides_reach_constraints_and_claim_rows', 'tests/test_world_model_language.py:test_interventions_on_empty_scenarios_reach_constraints_and_claim_rows', 'tests/test_world_model_language.py:test_completed_causal_runs_survive_another_incomplete_run'], 'declared_boundary_is_boundary_exceeded': ['tests/test_qualification.py:test_declared_boundary_trials_keep_their_native_status', 'tests/test_qualification.py:test_each_derived_guard_boundary_is_a_final_boundary[CausalGuard]']}
MUTATIONS = {'endogenous_seed_dropped': 'scenario_values_reach_constraints', 'interventions_ignored': 'scenario_values_reach_constraints', 'boundary_ranked_as_gap': 'declared_boundary_is_boundary_exceeded'}
CASES = tuple(q for q in REQUESTS if q.case_id in ('label', 'scenario_late', 'intervention_late', 'partial_run_fail', 'partial_run_gap', 'owned_boundary'))

@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    scenario_failed: bool = False
    intervention_failed: bool = False
    status: str = ''

class Evaluate:
    name = "Evaluate"
    reads = ("request",)
    writes = ('request', 'scenario_failed', 'intervention_failed', 'status')
    def __init__(self, mutation=""): self.mutation=mutation
    def apply(self, q, state):
        scenario=q.scm_mode in {'scenario','partial_fail'} and not (q.scm_mode=='scenario' and self.mutation=='endogenous_seed_dropped')
        intervention=q.scm_mode=='intervention' and self.mutation!='interventions_ignored'
        status=('FAIL' if scenario or intervention else 'GAP' if q.scm_mode=='partial_gap'
                else 'BOUNDARY_EXCEEDED' if q.boundary=='owned' else 'PASS')
        if status=='BOUNDARY_EXCEEDED' and self.mutation=='boundary_ranked_as_gap':status='GAP'
        new=State(q,scenario,intervention,status)
        yield FunctionResult(new,new,label=q.case_id)

def scenario_values_reach_constraints(state, trace):
    return _terminal_check(state, lambda request: request.scm_mode in {"scenario", "intervention", "partial_fail"}, (1, "FAIL"), "A real numerical contradiction disappeared from constraints/claim rows")


def declared_boundary_is_boundary_exceeded(state, trace):
    return _terminal_check(state, lambda request: request.case_id == "owned_boundary", (1, "BOUNDARY_EXCEEDED"), "An owned boundary was misclassified")


INVARIANTS = (
    Invariant('scenario_values_reach_constraints','Scenario/do contradictions reach constraints and assertions',scenario_values_reach_constraints),
    Invariant('declared_boundary_is_boundary_exceeded','An owned boundary has its own final status',declared_boundary_is_boundary_exceeded),
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
            actual=stage_values(request,code,report)[2]
            if actual!=expected:mismatches.append(f'{request.case_id}: stage {expected!r}, native {actual!r}')
        except Exception as exc:mismatches.append(f'{request.case_id}: native replay raised {type(exc).__name__}: {exc}')
        checked+=1
    return ReplayReport(checked,mismatches)
