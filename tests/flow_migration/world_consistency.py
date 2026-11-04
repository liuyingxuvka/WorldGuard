"""world_consistency: one native command or one stage of check."""
from dataclasses import dataclass, replace
from ._world_fixture import CheckRequest, EXTERNAL_INPUTS as REQUESTS, replay, stage_values, _terminal_check
MUTATIONS = {'endogenous_seed_dropped': 'scenario_values_reach_constraints', 'interventions_ignored': 'scenario_values_reach_constraints', 'boundary_ranked_as_gap': 'declared_boundary_is_boundary_exceeded'}
CASES = tuple((q for q in REQUESTS if q.case_id in ('label', 'scenario_late', 'intervention_late', 'partial_run_fail', 'partial_run_gap', 'owned_boundary')))

@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    scenario_failed: bool = False
    intervention_failed: bool = False
    status: str = ''

def expected_Evaluate(q, state, mutation='', broken_guard=''):
    scenario = q.scm_mode in {'scenario', 'partial_fail'} and (not (q.scm_mode == 'scenario' and mutation == 'endogenous_seed_dropped'))
    intervention = q.scm_mode == 'intervention' and mutation != 'interventions_ignored'
    status = 'FAIL' if scenario or intervention else 'GAP' if q.scm_mode == 'partial_gap' else 'BOUNDARY_EXCEEDED' if q.boundary == 'owned' else 'PASS'
    if status == 'BOUNDARY_EXCEEDED' and mutation == 'boundary_ranked_as_gap':
        status = 'GAP'
    new = State(q, scenario, intervention, status)
    return new

def scenario_values_reach_constraints(state):
    return _terminal_check(state, lambda request: request.scm_mode in {'scenario', 'intervention', 'partial_fail'}, (1, 'FAIL'), 'A real numerical contradiction disappeared from constraints/claim rows')

def declared_boundary_is_boundary_exceeded(state):
    return _terminal_check(state, lambda request: request.case_id == 'owned_boundary', (1, 'BOUNDARY_EXCEEDED'), 'An owned boundary was misclassified')
RULES = (scenario_values_reach_constraints, declared_boundary_is_boundary_exceeded)

def assert_native_contract():
    mismatches = []
    checked = 0
    for request in CASES:
        code, report = replay(request)
        expected = expected_Evaluate(request, State()).status
        actual = stage_values(request, code, report)[2]
        if actual != expected:
            mismatches.append(f'{request.case_id}: stage {expected!r}, native {actual!r}')
        checked += 1
    assert not mismatches, mismatches
RULE_NAMES = ('scenario_values_reach_constraints', 'declared_boundary_is_boundary_exceeded')
