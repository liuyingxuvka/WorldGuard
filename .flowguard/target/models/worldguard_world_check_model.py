"""The coarse check lifecycle receives stage contributions and preserves their exit boundary."""
from dataclasses import dataclass,replace
from flowguard import FunctionResult,Invariant,InvariantResult,Workflow
from flowguard.explorer import Explorer
from _world_fixture import CheckRequest,EXTERNAL_INPUTS as REQUESTS,ReplayReport,replay,stage_values,worst
MODEL_ID = 'world_check'
PARENT = 'system'
COMPONENTS = ['qualification']
OUTPUTS = {'status': ('PASS','FAIL','GAP','BOUNDARY_EXCEEDED','error')}
HANDOFF = {'world_input': {'status':'input_status'}, 'world_events': {'status':'events_status'},
           'world_consistency': {'status':'consistency_status'}, 'guard_semantics': {'status':'guard_status'}}
KEEPS = ('row_status','aggregate_status','rows','exit_code','status','terminal')
IMPLEMENTED_BY = {'DeriveGuards': 'worldguard/contracts.py:derive_guard_requirements', 'RunGuards': 'worldguard/qualification.py:qualify_guard_contract', 'EvaluateClaimRows': 'worldguard/claim_binding.py:evaluate_claim_binding', 'Aggregate': 'worldguard/status.py:aggregate_statuses', 'ReportExit': 'worldguard/cli.py:main'}
NOT_MODELED = {'scripts/install_skill.py:installed_differences': 'Filesystem byte comparison is checked by scratch install/check tests; OS file contents are outside this finite world semantics model.', 'scripts/install_skill.py:main': 'Installer filesystem writes are checked by real scratch-copy install/check tests; this finite world semantics model does not model OS filesystem operations.'}
TESTED_BY = {'pass_needs_bound_true_rows': ['tests/test_world_model_language.py:test_a_claim_without_assertions_is_not_bound_to_the_world_model'], 'variants_must_fail': ['tests/test_variants_timeline.py:test_examples_check_their_known_bad_variants_and_catch_a_missing_rule'], 'one_row_per_problem': ['tests/test_qualification.py:test_one_row_per_problem_in_short_and_full_reports'], 'child_status_decides_exit': ['tests/test_cli_module.py:test_cli_runs_the_single_bundled_world_example', 'tests/test_cli_module.py:test_missing_bundled_example_explains_skill_distribution']}
CHILD_RESULTS = {'label': ('PASS', 'PASS', 'PASS', 'PASS'), 'word_time': ('error', '', '', ''), 'duplicate_ids': ('error', '', '', ''), 'tokens_cloned': ('PASS', 'FAIL', 'PASS', 'FAIL'), 'transition_unlinked': ('PASS', 'GAP', 'PASS', 'PASS'), 'scenario_late': ('PASS', 'PASS', 'FAIL', 'FAIL'), 'owned_boundary': ('PASS', 'PASS', 'BOUNDARY_EXCEEDED', 'BOUNDARY_EXCEEDED'), 'uncaught_variant': ('PASS', 'PASS', 'PASS', 'PASS'), 'unbound': ('PASS', 'PASS', 'PASS', 'PASS'), 'false_row': ('PASS', 'PASS', 'PASS', 'PASS'), 'missing_event_time': ('PASS', 'GAP', 'PASS', 'GAP'), 'partial_run_gap': ('PASS', 'PASS', 'GAP', 'GAP'), 'unknown_row': ('PASS', 'PASS', 'PASS', 'PASS'), 'foreign_boundary': ('PASS', 'PASS', 'PASS', 'GAP'), 'boundary_with_fail': ('PASS', 'FAIL', 'BOUNDARY_EXCEEDED', 'FAIL'), 'boundary_with_gap': ('PASS', 'GAP', 'BOUNDARY_EXCEEDED', 'GAP')}
OWN_CASES = ('unbound', 'false_row', 'unknown_row', 'uncaught_variant', 'foreign_boundary', 'boundary_with_fail', 'boundary_with_gap')
CASES = tuple(q for q in REQUESTS if q.case_id in CHILD_RESULTS)

@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    input_status: str = ''
    events_status: str = ''
    consistency_status: str = ''
    guard_status: str = ''
    row_status: str = ''
    aggregate_status: str = ''
    rows: tuple[str,...] = ()
    exit_code: int | None = None
    status: str = ''
    terminal: bool = False

@dataclass(frozen=True)
class Terminal:
    exit_code: int
    status: str

class TakeRequest:
    name='TakeRequest'
    reads=()
    writes=('request',)
    def apply(self,request,state):
        yield FunctionResult(request,State(request=request),label=request.case_id)

class ReceiveInput:
    name='ReceiveInput'
    reads=('request',)
    writes=('input_status',)
    def apply(self,request,state):
        value=CHILD_RESULTS[state.request.case_id][0]
        yield FunctionResult(value,replace(state,input_status=value),label='received_input')

class ReceiveStages:
    name='ReceiveStages'
    reads=('request','input_status')
    writes=('events_status','consistency_status')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,request,state):
        values=CHILD_RESULTS[state.request.case_id][1:3] if state.input_status!='error' else ('','')
        if state.input_status=='error' and self.defect=='stages_run_after_parse_error':values=('PASS','PASS')
        yield FunctionResult(values,replace(state,events_status=values[0],consistency_status=values[1]),label='received_stages')

class RunGuards:
    name='RunGuards'
    reads=('request','input_status')
    writes=('guard_status',)
    def apply(self,request,state):
        value=CHILD_RESULTS[state.request.case_id][3] if state.input_status!='error' else ''
        yield FunctionResult(value,replace(state,guard_status=value),label='received_guards')

class EvaluateClaimRows:
    name='EvaluateClaimRows'
    reads=('request','input_status','events_status','consistency_status')
    writes=('row_status',)
    def __init__(self,defect=''):self.defect=defect
    def apply(self,request,state):
        q=state.request
        if state.input_status=='error':value=''
        elif q.rows=='none':value='PASS' if self.defect=='unbound_claim_passes' else 'GAP'
        elif q.rows=='unknown':value='GAP'
        elif q.uncaught_variant:value='PASS' if self.defect=='variants_ignored' else 'GAP'
        elif q.rows=='false':value='FAIL'
        elif q.rows=='order':value=state.events_status
        elif q.rows=='variable':value=worst((state.events_status,state.consistency_status))
        else:value='PASS'
        yield FunctionResult(value,replace(state,row_status=value),label='claim_rows_evaluated')

class Aggregate:
    name='Aggregate'
    reads=('input_status','events_status','consistency_status','guard_status','row_status')
    writes=('aggregate_status','rows')
    def __init__(self,defect=''):self.defect=defect
    def apply(self,request,state):
        statuses=[(name,getattr(state,name)) for name in ('events_status','consistency_status','guard_status','row_status')]
        values=[v for _,v in statuses]
        if self.defect=='ignores_gap':values=[v for v in values if v!='GAP']
        value='error' if state.input_status=='error' else worst(values)
        rows=tuple(name+':'+v for name,v in statuses if v and v!='PASS')
        if self.defect=='layered_duplicates' and rows:rows+=rows[:1]
        yield FunctionResult(value,replace(state,aggregate_status=value,rows=rows),label='statuses_aggregated')

class ReportExit:
    name='ReportExit'
    reads=('input_status','aggregate_status')
    writes=('exit_code','status','terminal')
    def apply(self,request,state):
        status='error' if state.input_status=='error' else state.aggregate_status
        code=2 if status=='error' else 0 if status=='PASS' else 1
        label={'error':'input_error','PASS':'passed','FAIL':'failed','GAP':'gap','BOUNDARY_EXCEEDED':'boundary_exceeded'}[status]
        yield FunctionResult(Terminal(code,status),replace(state,exit_code=code,status=status,terminal=True),label=label)

def _terminal_check(state, applies, expected, message):
    if state.terminal and state.request is not None and applies(state.request) and (state.exit_code, state.status) != expected:
        return InvariantResult.fail(message)
    return InvariantResult.pass_()


def pass_needs_bound_true_rows(state, trace):
    if state.terminal and state.request is not None and state.status == "PASS":
        if state.request.rows in {"none", "false", "unknown"} or state.row_status != "PASS" or state.guard_status != "PASS":
            return InvariantResult.fail("PASS lacks bound true rows and a passing world")
    return _terminal_check(state, lambda request: request.rows == "none", (1, "GAP"), "An unbound claim did not remain a gap")


def variants_must_fail(state, trace):
    return _terminal_check(state, lambda request: request.uncaught_variant, (1, "GAP"), "An uncaught known-bad variant allowed PASS")


def one_row_per_problem(state,trace):
    if state.terminal and len(state.rows)!=len(set(state.rows)):
        return InvariantResult.fail('A native problem was repeated as layered or pointer rows')
    return InvariantResult.pass_()

def child_status_decides_exit(state,trace):
    if not state.terminal:return InvariantResult.pass_()
    if state.input_status=='error':
        expected=(2,'error')
        if state.events_status or state.consistency_status or state.guard_status:
            return InvariantResult.fail('Stages received values after a parse error')
    else:
        value=worst((state.events_status,state.consistency_status,state.guard_status,state.row_status))
        expected=(0 if value=='PASS' else 1,value)
    if (state.exit_code,state.status)!=expected:
        return InvariantResult.fail('The received child and Guard contributions do not decide the exit')
    return InvariantResult.pass_()

INVARIANTS = (
    Invariant('pass_needs_bound_true_rows','Only bound true rows in a passing world can pass',pass_needs_bound_true_rows),
    Invariant('variants_must_fail','A known-bad variant that escapes prevents PASS',variants_must_fail),
    Invariant('one_row_per_problem','Each native problem has one report row',one_row_per_problem),
    Invariant('child_status_decides_exit','The received stage and Guard statuses decide the exit; parse errors receive no later stages.',child_status_decides_exit),
)
MUTATIONS = {'unbound_claim_passes':'pass_needs_bound_true_rows','variants_ignored':'variants_must_fail',
             'layered_duplicates':'one_row_per_problem','stages_run_after_parse_error':'child_status_decides_exit','ignores_gap':'child_status_decides_exit'}

def workflow(defect=''):
    return Workflow((TakeRequest(),ReceiveInput(),ReceiveStages(defect),RunGuards(),EvaluateClaimRows(defect),Aggregate(defect),ReportExit()))
def make(defect='',names=None):
    return Explorer(workflow(defect),(State(),),CASES,tuple(rule for rule in INVARIANTS if names is None or rule.name in names),
                    max_sequence_length=1,terminal_predicate=lambda value,state,trace:state.terminal,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {name:make(name,{rule}) for name,rule in MUTATIONS.items()}

def outcome(request):
    value,state=request,State()
    for step in workflow().blocks:
        result=next(step.apply(value,state));value,state=result.output,result.new_state
    return state

def conformance():
    mismatches=[];checked=0;requests={q.case_id:q for q in CASES}
    for case in (*OWN_CASES,*CHILD_RESULTS):
        request=requests[case]
        try:
            code,report=replay(request);state=outcome(request)
            if (code,report['status'])!=(state.exit_code,state.status):mismatches.append(f'{case}: exit/status differs')
            if case in CHILD_RESULTS and stage_values(request,code,report)!=CHILD_RESULTS[case]:mismatches.append(f'{case}: coarse received values differ from native contributions')
            gaps=report.get('gaps',[])
            identities=[(row['code'],row.get('guard'),row.get('claim_row'),row.get('variant_id')) for row in gaps]
            if len(identities)!=len(set(identities)):mismatches.append(f'{case}: one_row_per_problem failed')
        except Exception as exc:mismatches.append(f'{case}: native replay raised {type(exc).__name__}: {exc}')
        checked+=1
    return ReplayReport(checked,mismatches)
