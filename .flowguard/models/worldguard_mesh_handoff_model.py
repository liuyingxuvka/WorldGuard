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
PARENT = 'mesh'
COMPONENTS = ['mesh']
IMPLEMENTED_BY = {
    'RunMesh': 'worldguard/mesh.py:run_model_mesh',
    'Continue': 'worldguard/mesh.py:_continues_findings',
    'Descendants': 'worldguard/mesh.py:_descendants',
    'TreeStructure': 'worldguard/mesh.py:_tree_structure',
}
TESTED_BY = {
    'continues_requires_matching_state': ['tests/test_model_mesh.py:test_continues_carries_state_and_time'],
    'continues_moves_time_forward': ['tests/test_model_mesh.py:test_continues_trip_cannot_depart_before_prior_arrival'],
    'node_rows_read_descendants_only': ['tests/test_model_mesh.py:test_node_rows_read_descendants_only'],
    'child_non_pass_reaches_root': ['tests/test_model_mesh.py:test_child_failure_reaches_root_even_when_parent_assertion_is_true'],
    'dependency_cycle_fails': ['tests/test_model_mesh.py:test_continues_cycle_fails'],
    'one_root': ['tests/test_model_mesh.py:test_a_mesh_with_two_roots_is_not_one_tree'],
    'mesh_variants_must_fail': ['tests/test_model_mesh.py:test_mesh_variant_must_fail_with_its_code'],
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
    one_root: bool = True
    has_variant: bool = False
    variant_caught: bool = True


@dataclass(frozen=True)
class State:
    request: Request | None = None
    status: str = ''
    exit_code: int | None = None
    codes: tuple[str, ...] = ()
    variants_checked: bool = False


class RunMesh:
    name = 'RunMesh'
    reads = ()
    writes = ('request', 'status', 'exit_code', 'codes', 'variants_checked')
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
        if not request.one_root and self.mutation != 'multiple_roots_allowed':
            gaps.append('MESH_NOT_ONE_TREE')
        variants_checked = request.has_variant and self.mutation != 'variants_not_run'
        if variants_checked and not request.variant_caught:
            gaps.append('VARIANT_NOT_CAUGHT')
        status = 'FAIL' if failures else 'GAP' if gaps else 'BOUNDARY_EXCEEDED' if boundaries else 'PASS'
        code = 0 if status == 'PASS' else 1
        result = State(request, status, code, tuple(sorted(set(failures + gaps + boundaries))), variants_checked)
        yield FunctionResult((code, status), result, label=status.lower())


def requires_state(state, trace):
    if state.request and not state.request.state_matches and 'MESH_HANDOFF_STATE_MISMATCH' not in state.codes:
        return InvariantResult.fail('continuation ignored different fluent/token state')
    return InvariantResult.pass_()


def forward_time(state, trace):
    if state.request and not state.request.time_forward and 'MESH_HANDOFF_TIME_BACKWARDS' not in state.codes:
        return InvariantResult.fail('next node began before preceding node ended')
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


def one_root(state, trace):
    if state.request and not state.request.one_root:
        if state.status == 'PASS' or 'MESH_NOT_ONE_TREE' not in state.codes:
            return InvariantResult.fail('a disconnected or multi-root mesh passed as one tree')
    return InvariantResult.pass_()


def mesh_variants_must_fail(state, trace):
    if state.request and state.request.has_variant:
        if not state.variants_checked:
            return InvariantResult.fail('the declared tree variant was not executed')
        if not state.request.variant_caught and (state.status == 'PASS' or 'VARIANT_NOT_CAUGHT' not in state.codes):
            return InvariantResult.fail('a tree variant escaped its required failure')
    return InvariantResult.pass_()


INVARIANTS = tuple(Invariant(name, description, check) for name, description, check in (
    ('continues_requires_matching_state', 'preceding end state matches next node start', requires_state),
    ('continues_moves_time_forward', 'continuations do not move backwards', forward_time),
    ('node_rows_read_descendants_only', 'node rows read descendants only', descendants_only),
    ('child_non_pass_reaches_root', 'children keep their non-pass status in the tree', children_preserved),
    ('dependency_cycle_fails', 'dependency cycles fail', cycles_fail),
    ('one_root', 'only one connected parent-child root is a tree', one_root),
    ('mesh_variants_must_fail', 'every tree variant runs and must match its declared failure', mesh_variants_must_fail),
))
CASES = (Request('chapters_ok_rooted.yaml'), Request('end_state_contradiction.yaml', state_matches=False, one_root=False),
         Request('ch2_resurrects.yaml', state_matches=False, one_root=False), Request('time_backwards.yaml', time_forward=False, one_root=False),
         Request('unrelated', descendant=False, one_root=False), Request('child_fail', child_status='FAIL'), Request('child_gap', child_status='GAP'),
         Request('child_boundary', child_status='BOUNDARY_EXCEEDED'), Request('cycle', cycle=True),
         Request('chapters_ok.yaml', one_root=False), Request('caught_variant', has_variant=True),
         Request('uncaught_variant', has_variant=True, variant_caught=False))


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
        ('multiple_roots_allowed', 'one_root'),
        ('variants_not_run', 'mesh_variants_must_fail'),
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
                elif request.has_variant:
                    change = ({'nodes[a].contract.inputs.events[a].initiates': []} if request.variant_caught
                              else {'nodes[a].contract.claim.claim_id': 'same-world-new-label'})
                    data['variants'] = [{'id': request.case, 'code': 'MESH_HANDOFF_STATE_MISMATCH', 'set': change}]
                else:
                    data['edges'].append({'edge_id': 'back', 'from': 'b', 'to': 'a', 'relation': 'continues'})
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
            if request.has_variant:
                variants = result.get('variants', [])
                if (result.get('checked', {}).get('variants') != 1 or len(variants) != 1
                        or variants[0].get('caught') is not request.variant_caught):
                    mismatches.append(f'{request.case}: the native tree variant was not checked with its declared outcome')
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
