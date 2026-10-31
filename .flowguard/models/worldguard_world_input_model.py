"""world_input: one native command or one stage of check."""
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from _world_fixture import CheckRequest, EXTERNAL_INPUTS as REQUESTS, ReplayReport, replay, stage_values, _terminal_check

MODEL_ID = 'world_input'
PARENT = 'world_check'
COMPONENTS = ['cli']
READS_PARENT = ("request",)
OUTPUTS = {"status": ('PASS', 'error')}
IMPLEMENTED_BY = {'InputDigests': 'worldguard/io.py:input_digests', 'ParseContract': 'worldguard/contracts.py:GuardContract.from_dict', 'RejectRetiredKeys': 'worldguard/contracts.py:_reject_retired_contract_keys', 'MeshSummary': 'worldguard/cli.py:_mesh_summary'}
USES = {"Main": "worldguard/cli.py:main", 'MeshReport': 'worldguard/mesh.py:MeshReport.to_dict'}
TESTED_BY = {'summary_names_its_inputs': ['tests/test_cli_module.py:test_check_reports_input_digests'], 'bad_time_is_input_error': ['tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[story_mut_out/bad_time_yaml-2-error-codes2]', 'tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[story_mut_out/mixed_time_yaml-2-error-codes3]', 'tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[trip_mut2_out/word_time_yaml-2-error-codes4]', 'tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[trip_mut_out/hhmm_yaml-2-error-codes5]', 'tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[trip_mut_out/hhmm_padded_yaml-2-error-codes6]'], 'duplicate_event_id_is_input_error': ['tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[story_mut_out/dup_event_id_yaml-2-error-codes7]'], 'retired_keys_are_input_errors': ['tests/test_contracts.py:test_retired_contract_keys_are_input_errors'], 'mesh_summary_names_its_inputs': ['tests/test_cli_module.py:test_mesh_check_reports_mesh_id_and_input_digests']}
MUTATIONS = {'digest_omits_the_contract': 'summary_names_its_inputs', 'word_times_accepted': 'bad_time_is_input_error', 'duplicate_ids_accepted': 'duplicate_event_id_is_input_error', 'retired_keys_accepted': 'retired_keys_are_input_errors', 'mesh_digest_omits_a_node': 'mesh_summary_names_its_inputs'}
CASES = tuple(q for q in REQUESTS if q.case_id in ('number', 'label', 'iso', 'word_time', 'mixed_time', 'duplicate_ids', 'missing_event_time', 'retired_schema_version', 'retired_run_id', 'retired_dependencies', 'retired_output_requirements', 'retired_target_guard', 'retired_target_guards', 'retired_atoms'))
MESH_ID = 'input-tree'
MESH_FILES = ('mesh.json', 'nodes/world.json')

@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    inputs_missing: bool = False
    status: str = ''
    digests_match: bool = True
    mesh_id: str = MESH_ID
    mesh_files: tuple[str, ...] = MESH_FILES

class Evaluate:
    name = "Evaluate"
    reads = ("request",)
    writes = ('request', 'inputs_missing', 'status', 'digests_match', 'mesh_id', 'mesh_files')
    def __init__(self, mutation=""): self.mutation=mutation
    def apply(self, q, state):
        error = ((q.time_form in {'word','mixed'} and self.mutation!='word_times_accepted')
                 or (q.duplicate_ids and self.mutation!='duplicate_ids_accepted')
                 or (bool(q.retired_key) and self.mutation!='retired_keys_accepted'))
        new=State(q,q.time_form=='missing','error' if error else 'PASS')
        new=replace(new,digests_match=self.mutation!='digest_omits_the_contract')
        if self.mutation=='mesh_digest_omits_a_node':new=replace(new,mesh_files=('mesh.json',))
        yield FunctionResult(new,new,label=q.case_id)

def bad_time_is_input_error(state, trace):
    return _terminal_check(state, lambda request: request.time_form in {"word", "mixed"}, (2, "error"), "Unknown or mixed time escaped the input-error boundary")


def duplicate_event_id_is_input_error(state, trace):
    return _terminal_check(state, lambda request: request.duplicate_ids, (2, "error"), "A duplicate event identity was accepted")


def retired_keys_are_input_errors(state, trace):
    return _terminal_check(state, lambda request: bool(request.retired_key), (2, "error"),
                           "A retired contract/claim key escaped the typed input-error boundary")


def summary_names_its_inputs(state,trace):
    return InvariantResult.pass_() if state.digests_match else InvariantResult.fail('The check omitted an input digest')

def mesh_summary_names_its_inputs(state,trace):
    if state.mesh_id!=MESH_ID or state.mesh_files!=MESH_FILES:
        return InvariantResult.fail('The mesh summary omitted its id or a file it read')
    return InvariantResult.pass_()

INVARIANTS = (
    Invariant('mesh_summary_names_its_inputs','A mesh-check summary names the mesh id and every file it read with its raw byte digest.',mesh_summary_names_its_inputs),
    Invariant('summary_names_its_inputs','A check summary names every file read with its raw byte digest.',summary_names_its_inputs),
    Invariant('bad_time_is_input_error','Unknown/mixed time exits 2',bad_time_is_input_error),
    Invariant('duplicate_event_id_is_input_error','Duplicate scenario-local ids exit 2',duplicate_event_id_is_input_error),
    Invariant('retired_keys_are_input_errors','Retired keys are rejected by presence',retired_keys_are_input_errors),
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
            actual=stage_values(request,code,report)[0]
            if actual!=expected:mismatches.append(f'{request.case_id}: stage {expected!r}, native {actual!r}')
            if (code==2)!=(expected=='error'):mismatches.append(f'{request.case_id}: typed input exit disagrees')
        except Exception as exc:mismatches.append(f'{request.case_id}: native replay raised {type(exc).__name__}: {exc}')
        checked+=1
    import hashlib,json,tempfile,io
    from pathlib import Path
    from contextlib import redirect_stdout
    from worldguard.cli import main
    from _world_fixture import _real_contract
    with tempfile.TemporaryDirectory(prefix='check-inputs-') as directory:
        path=Path(directory)/'world.json';path.write_text(json.dumps(_real_contract(CASES[0])))
        output=io.StringIO()
        with redirect_stdout(output):main(['check','--contract',str(path)])
        report=json.loads(output.getvalue())
        expected=[{'path':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]
        if report.get('input_digests')!=expected:mismatches.append('summary_names_its_inputs: missing or incorrect raw input digest')
        root=Path(directory);node=root/'nodes/world.json';node.parent.mkdir()
        contract=_real_contract(CASES[0]);node.write_text(json.dumps(contract)+'\n')
        mesh=root/'mesh.json'
        mesh.write_text(json.dumps({'mesh_id':MESH_ID,
            'nodes':[{'model_id':'file','contract':'nodes/world.json'}, {'model_id':'inline','contract':contract}],
            'edges':[{'edge_id':'file-inline','from':'file','to':'inline','relation':'parent_child'}]},indent=2)+'\n')
        output=io.StringIO()
        with redirect_stdout(output):code=main(['mesh-check','--mesh',str(mesh)])
        report=json.loads(output.getvalue())
        expected=[{'path':p.relative_to(root).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in (mesh,node)]
        keys={'checked','gaps','input_digests','mesh_id','output','scope_limits','status','tree'}
        if code!=0 or report.get('mesh_id')!=MESH_ID or report.get('input_digests')!=expected or set(report)!=keys:
            mismatches.append('mesh_summary_names_its_inputs: native mesh id/raw file digests/compact keys differ; '
                              f"actual id={report.get('mesh_id')!r}, digests={report.get('input_digests')!r}, keys={sorted(report)}")
    return ReplayReport(checked+2,mismatches)
