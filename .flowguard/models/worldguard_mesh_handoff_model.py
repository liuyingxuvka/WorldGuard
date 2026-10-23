"""Finite mesh handoff outcomes, replayed through the real in-process CLI."""
from contextlib import redirect_stdout
from dataclasses import dataclass, replace
import io
import json
from pathlib import Path
import runpy
import sys
import tempfile

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer

MODEL_ID = 'mesh_handoff'
PARENT = 'worldguard.mesh'
COMPONENTS = ['worldguard.mesh']
IMPLEMENTED_BY = {
    'RunMesh': 'worldguard/mesh.py:run_model_mesh',
    'Continue': 'worldguard/mesh.py:_continues_findings',
    'Descendants': 'worldguard/mesh.py:_descendants',
}
TESTED_BY = {
    'continues_requires_matching_state': ['tests/test_model_mesh.py:test_continues_carries_state_and_time'],
    'continues_moves_time_forward': ['tests/test_model_mesh.py:test_continues_trip_cannot_depart_before_prior_arrival'],
    'node_rows_read_descendants_only': ['tests/test_model_mesh.py:test_node_rows_read_descendants_only'],
    'child_non_pass_reaches_root': ['tests/test_model_mesh.py:test_child_failure_reaches_root_even_when_parent_assertion_is_true'],
    'dependency_cycle_fails': ['tests/test_model_mesh.py:test_continues_cycle_fails'],
}
ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Request:
    case: str
    state_matches: bool = True
    time_forward: bool = True
    descendant: bool = True
    child_status: str = 'PASS'
    cycle: bool = False


@dataclass(frozen=True)
class State:
    request: Request | None = None
    status: str = ''
    exit_code: int | None = None
    codes: tuple[str, ...] = ()


class RunMesh:
    name = 'RunMesh'
    reads = ()
    writes = ('request', 'status', 'exit_code', 'codes')
    mutation = ''

    def apply(self, request, state):
        failures, gaps, boundaries = [], [], []
        if not request.state_matches and self.mutation != 'label_only_handoff':
            failures.append('MESH_HANDOFF_STATE_MISMATCH')
        if not request.time_forward and self.mutation != 'time_not_checked':
            failures.append('MESH_HANDOFF_TIME_BACKWARDS')
        if not request.descendant and self.mutation != 'node_rows_read_any_node':
            gaps.append('CLAIM_ASSERTION_UNRESOLVED')
        if request.child_status != 'PASS' and self.mutation != 'root_hides_child':
            if request.child_status == 'BOUNDARY_EXCEEDED':
                boundaries.append('EVENT_BOUNDARY_NUMERIC_DYNAMICS')
            else:
                (failures if request.child_status == 'FAIL' else gaps).append('CLAIM_ASSERTION_FALSE' if request.child_status == 'FAIL' else 'CLAIM_ASSERTION_UNRESOLVED')
        if request.cycle and self.mutation != 'cycles_ignored':
            failures.append('MESH_DEPENDENCY_CYCLE')
        status = 'FAIL' if failures else 'GAP' if gaps else 'BOUNDARY_EXCEEDED' if boundaries else 'PASS'
        code = 0 if status == 'PASS' else 1
        result = State(request, status, code, tuple(sorted(set(failures + gaps + boundaries))))
        yield FunctionResult((code, status), result, label=status.lower())


def requires_state(state, trace):
    if state.request and not state.request.state_matches and 'MESH_HANDOFF_STATE_MISMATCH' not in state.codes:
        return InvariantResult.fail('continuation ignored different fluent/token state')
    return InvariantResult.pass_()


def forward_time(state, trace):
    if state.request and not state.request.time_forward and 'MESH_HANDOFF_TIME_BACKWARDS' not in state.codes:
        return InvariantResult.fail('target began before source ended')
    return InvariantResult.pass_()


def descendants_only(state, trace):
    if state.request and not state.request.descendant and (state.status != 'GAP' or 'CLAIM_ASSERTION_UNRESOLVED' not in state.codes):
        return InvariantResult.fail('parent read an unrelated node')
    return InvariantResult.pass_()


def children_preserved(state, trace):
    if state.request and state.request.child_status != 'PASS' and state.status == 'PASS':
        return InvariantResult.fail('passing parent hid a non-passing child')
    return InvariantResult.pass_()


def cycles_fail(state, trace):
    if state.request and state.request.cycle and (state.status != 'FAIL' or 'MESH_DEPENDENCY_CYCLE' not in state.codes):
        return InvariantResult.fail('dependency cycle was ignored')
    return InvariantResult.pass_()


INVARIANTS = tuple(Invariant(name, description, check) for name, description, check in (
    ('continues_requires_matching_state', 'source end state matches target start', requires_state),
    ('continues_moves_time_forward', 'continuations do not move backwards', forward_time),
    ('node_rows_read_descendants_only', 'node rows read descendants only', descendants_only),
    ('child_non_pass_reaches_root', 'children keep their non-pass status in the tree', children_preserved),
    ('dependency_cycle_fails', 'dependency cycles fail', cycles_fail),
))
CASES = (Request('chapters_ok.yaml'), Request('end_state_contradiction.yaml', state_matches=False),
         Request('ch2_resurrects.yaml', state_matches=False), Request('time_backwards.yaml', time_forward=False),
         Request('unrelated', descendant=False), Request('child_fail', child_status='FAIL'), Request('child_gap', child_status='GAP'),
         Request('child_boundary', child_status='BOUNDARY_EXCEEDED'), Request('cycle', cycle=True))


def explorer(step, names=None):
    invariants = tuple(row for row in INVARIANTS if names is None or row.name in names)
    return Explorer(Workflow((step,)), (State(),), CASES, invariants, progress_steps=0)


def build_explorer():
    return explorer(RunMesh())


def broken_variants():
    result = {}
    for mutation, invariant in (
        ('label_only_handoff', 'continues_requires_matching_state'),
        ('time_not_checked', 'continues_moves_time_forward'),
        ('node_rows_read_any_node', 'node_rows_read_descendants_only'),
        ('root_hides_child', 'child_non_pass_reaches_root'),
        ('cycles_ignored', 'dependency_cycle_fails'),
    ):
        step = RunMesh()
        step.mutation = mutation
        result[mutation] = explorer(step, {invariant})
    return result


class ReplayReport:
    def __init__(self, checked, mismatches):
        self.checked, self.mismatches = checked, tuple(mismatches)
        self.ok = not mismatches

    def format_text(self, max_examples=None):
        return '\n'.join([f'conformance: {self.checked - len(self.mismatches)}/{self.checked}', *self.mismatches[:max_examples]])


def conformance():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from worldguard.cli import main
    small_tree = runpy.run_path(str(ROOT / 'tests/test_model_mesh.py'))['continued_tree']
    mismatches = []
    with tempfile.TemporaryDirectory(prefix='mesh-handoff-replay-') as folder:
        for request in CASES:
            if request.case.endswith('.yaml'):
                path = ROOT / 'tests/fixtures/trials/mesh_continues' / request.case
            else:
                data = small_tree()
                if request.case == 'unrelated':
                    data['edges'] = [row for row in data['edges'] if row['edge_id'] != 'root-b']
                elif request.case == 'child_fail':
                    data['nodes'][2]['contract']['claim']['asserts'][0]['value'] = False
                elif request.case == 'child_gap':
                    data['nodes'][2]['contract']['claim']['asserts'][0]['holds'] = 'unknown_fluent'
                elif request.case == 'child_boundary':
                    data['nodes'][2]['contract']['claim']['requested_semantics'] = ['event', 'numeric_dynamics']
                else:
                    data['edges'].append({'edge_id': 'back', 'source_model_id': 'b', 'target_model_id': 'a', 'relation': 'continues'})
                path = Path(folder) / (request.case + '.json')
                path.write_text(json.dumps(data))
            expected = next(RunMesh().apply(request, State())).new_state
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(['mesh-check', '--mesh', str(path), '--json'])
            result = json.loads(output.getvalue())
            codes = {row['code'] for row in result.get('gaps', [])}
            if (code, result['status']) != (expected.exit_code, expected.status) or not set(expected.codes) <= codes:
                mismatches.append(f'{request.case}: expected {expected.status}/{expected.codes}, actual {code}/{result["status"]}/{sorted(codes)}')
    return ReplayReport(len(CASES), mismatches)


if __name__ == '__main__':
    good = build_explorer().explore()
    print(good.format_text())
    caught = []
    for name, variant in broken_variants().items():
        failed = not variant.explore().ok
        caught.append(failed)
        print(f'{name}: {"caught" if failed else "MISSED"}')
    replay = conformance()
    print(replay.format_text())
    raise SystemExit(0 if good.ok and all(caught) and replay.ok else 1)
