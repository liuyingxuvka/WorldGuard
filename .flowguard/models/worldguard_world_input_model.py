"""world_input: one native command or one stage of check."""
from dataclasses import dataclass, replace
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from _world_fixture import CheckRequest, EXTERNAL_INPUTS as REQUESTS, ReplayReport, replay, stage_values, _terminal_check

MODEL_ID = 'world_input'
PARENT = 'world_check'
READS_PARENT = ("request",)
OUTPUTS = {"status": ('PASS', 'error')}
IMPLEMENTED_BY = {'ParseContract': 'worldguard/contracts.py:GuardContract.from_dict', 'RejectRetiredKeys': 'worldguard/contracts.py:_reject_retired_contract_keys'}
USES = {"Main": "worldguard/cli.py:main"}
TESTED_BY = {'bad_time_is_input_error': ['tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[story_mut_out/bad_time.yaml-2-error-codes2]', 'tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[story_mut_out/mixed_time.yaml-2-error-codes3]', 'tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[trip_mut2_out/word_time.yaml-2-error-codes4]', 'tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[trip_mut_out/hhmm.yaml-2-error-codes5]', 'tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[trip_mut_out/hhmm_padded.yaml-2-error-codes6]'], 'duplicate_event_id_is_input_error': ['tests/test_event_time_order.py:test_trial_time_contracts_are_checked_natively[story_mut_out/dup_event_id.yaml-2-error-codes7]'], 'retired_keys_are_input_errors': ['tests/test_contracts.py:test_retired_contract_keys_are_input_errors']}
MUTATIONS = {'word_times_accepted': 'bad_time_is_input_error', 'duplicate_ids_accepted': 'duplicate_event_id_is_input_error', 'retired_keys_accepted': 'retired_keys_are_input_errors'}
CASES = tuple(q for q in REQUESTS if q.case_id in ('number', 'label', 'iso', 'word_time', 'mixed_time', 'duplicate_ids', 'missing_event_time', 'retired_schema_version', 'retired_run_id', 'retired_dependencies', 'retired_output_requirements', 'retired_target_guard', 'retired_target_guards', 'retired_atoms'))

@dataclass(frozen=True)
class State:
    request: CheckRequest | None = None
    inputs_missing: bool = False
    status: str = ''

class Evaluate:
    name = "Evaluate"
    reads = ("request",)
    writes = ('request', 'inputs_missing', 'status')
    def __init__(self, mutation=""): self.mutation=mutation
    def apply(self, q, state):
        error = ((q.time_form in {'word','mixed'} and self.mutation!='word_times_accepted')
                 or (q.duplicate_ids and self.mutation!='duplicate_ids_accepted')
                 or (bool(q.retired_key) and self.mutation!='retired_keys_accepted'))
        new=State(q,q.time_form=='missing','error' if error else 'PASS')
        yield FunctionResult(new,new,label=q.case_id)

def bad_time_is_input_error(state, trace):
    return _terminal_check(state, lambda request: request.time_form in {"word", "mixed"}, (2, "error"), "Unknown or mixed time escaped the input-error boundary")


def duplicate_event_id_is_input_error(state, trace):
    return _terminal_check(state, lambda request: request.duplicate_ids, (2, "error"), "A duplicate event identity was accepted")


def retired_keys_are_input_errors(state, trace):
    return _terminal_check(state, lambda request: bool(request.retired_key), (2, "error"),
                           "A retired contract/claim key escaped the typed input-error boundary")


INVARIANTS = (
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
    return ReplayReport(checked,mismatches)
