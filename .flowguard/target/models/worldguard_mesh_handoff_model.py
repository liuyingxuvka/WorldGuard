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
HANDOFF = {'world_check': {'status': ('status', {'PASS':'PASS','FAIL':'FAIL','GAP':'GAP','BOUNDARY_EXCEEDED':'BOUNDARY_EXCEEDED','error':None})}}
PARENT = 'mesh'
COMPONENTS = ['mesh']
IMPLEMENTED_BY = {
    'RunMesh': 'worldguard/mesh.py:run_model_mesh',
    'Continue': 'worldguard/mesh.py:_continues_findings',
    'Descendants': 'worldguard/mesh.py:_descendants',
    'TreeStructure': 'worldguard/mesh.py:_tree_structure',
}
USES = {"Main": "worldguard/cli.py:main"}
TESTED_BY = {
    'continues_requires_matching_state': ['tests/test_model_mesh.py:test_continues_carries_state_and_time'],
    'continues_moves_time_forward': ['tests/test_model_mesh.py:test_continues_trip_cannot_depart_before_prior_arrival'],
    'node_rows_read_descendants_only': ['tests/test_model_mesh.py:test_node_rows_read_descendants_only'],
    'child_non_pass_reaches_root': ['tests/test_model_mesh.py:test_child_failure_reaches_root_even_when_parent_assertion_is_true'],
    'dependency_cycle_fails': ['tests/test_model_mesh.py:test_continues_cycle_fails'],
    'one_root': ['tests/test_model_mesh.py:test_a_mesh_with_two_roots_is_not_one_tree'],
    'mesh_variants_must_fail': ['tests/test_model_mesh.py:test_mesh_variant_must_fail_with_its_code'],
    'tree_lines_match_status': ['tests/test_model_mesh.py:test_tree_lines_show_subtree_and_edge_status'],
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
    planned_node: bool = False


@dataclass(frozen=True)
class State:
    request: Request | None = None
    status: str = ''
    exit_code: int | None = None
    codes: tuple[str, ...] = ()
    variants_checked: bool = False
    root_line: str = ''
    edge_segments: tuple[str, ...] = ()
    planned_shown: bool = False


class RunMesh:
    name = 'RunMesh'
    reads = ()
    writes = ('request', 'status', 'exit_code', 'codes', 'variants_checked', 'root_line', 'edge_segments', 'planned_shown')
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
        if request.planned_node:
            gaps.append('MESH_EXPECTED_NODE_CONTRACT_MISSING')
        if request.cycle and self.mutation != 'cycles_ignored':
            failures.append('MESH_DEPENDENCY_CYCLE')
        if not request.one_root and self.mutation != 'multiple_roots_allowed':
            gaps.append('MESH_NOT_ONE_TREE')
        variants_checked = request.has_variant and self.mutation != 'variants_not_run'
        if variants_checked and not request.variant_caught:
            gaps.append('VARIANT_NOT_CAUGHT')
        status = 'FAIL' if failures else 'GAP' if gaps else 'BOUNDARY_EXCEEDED' if boundaries else 'PASS'
        code = 0 if status == 'PASS' else 1
        edge_failure = any(code in EDGE_FAILURES for code in failures)
        if self.mutation == 'root_line_hides_edge_failure':
            # Today's lines: every node prints only its own status and no edge result.
            root_line = request.child_status if request.child_status != 'PASS' else 'PASS'
            segments = ('',) if edge_failure else ()
        else:
            root_line = status
            segments = ('FAIL',) if edge_failure else ()
        result = State(request, status, code, tuple(sorted(set(failures + gaps + boundaries))), variants_checked,
                       root_line, segments, request.planned_node and self.mutation != 'root_line_hides_edge_failure')
        yield FunctionResult((code, status), result, label=status.lower())


EDGE_FAILURES = ('MESH_HANDOFF_STATE_MISMATCH', 'MESH_HANDOFF_TIME_BACKWARDS')


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


def tree_lines_match_status(state, trace):
    if not state.request:
        return InvariantResult.pass_()
    if state.request.one_root and state.root_line != state.status:
        return InvariantResult.fail('the root line hides the tree status')
    if any(code in EDGE_FAILURES for code in state.codes) and 'FAIL' not in state.edge_segments:
        return InvariantResult.fail('a failing continues edge prints no FAIL on its segment')
    if state.request.planned_node and not state.planned_shown:
        return InvariantResult.fail('a node without a contract is not read as planned')
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant('continues_requires_matching_state', 'preceding end state matches next node start', requires_state),
    Invariant('continues_moves_time_forward', 'continuations do not move backwards', forward_time),
    Invariant('node_rows_read_descendants_only', 'node rows read descendants only', descendants_only),
    Invariant('child_non_pass_reaches_root', 'children keep their non-pass status in the tree', children_preserved),
    Invariant('dependency_cycle_fails', 'dependency cycles fail', cycles_fail),
    Invariant('one_root', 'only one connected parent-child root is a tree', one_root),
    Invariant('mesh_variants_must_fail', 'every tree variant runs and must match its declared failure', mesh_variants_must_fail),
    Invariant('tree_lines_match_status', 'the root line shows the report status, failing continues edges print FAIL, contract-less nodes read planned', tree_lines_match_status),
)
CASES = (Request('chapters_ok_rooted.yaml'), Request('end_state_contradiction.yaml', state_matches=False, one_root=False),
         Request('ch2_resurrects.yaml', state_matches=False, one_root=False), Request('time_backwards.yaml', time_forward=False, one_root=False),
         Request('unrelated', descendant=False, one_root=False), Request('child_fail', child_status='FAIL'), Request('child_gap', child_status='GAP'),
         Request('child_boundary', child_status='BOUNDARY_EXCEEDED'), Request('cycle', cycle=True),
         Request('chapters_ok.yaml', one_root=False), Request('caught_variant', has_variant=True),
         Request('uncaught_variant', has_variant=True, variant_caught=False),
         Request('planned', planned_node=True), Request('edge_time_backwards', time_forward=False))


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
        ('root_line_hides_edge_failure', 'tree_lines_match_status'),
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
                elif request.planned_node:
                    data['nodes'].append({'model_id': 'c'})
                    data['edges'].append({'edge_id': 'root-c', 'from': 'root', 'to': 'c', 'relation': 'parent_child'})
                elif request.case == 'edge_time_backwards':
                    data['nodes'][2]['contract']['inputs']['events'][0]['at'] = 't0'
                    data['nodes'][2]['contract']['claim']['asserts'][0]['at'] = 't0'
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
            lines = result.get('tree', [])
            root_status = lines[0].split()[1] if lines else ''
            if lines and '(tree ' in lines[0]:
                root_status = lines[0].rsplit('(tree ', 1)[1].rstrip(')')
            segments = tuple((part.split() + [''])[1] for line in lines for part in line.split(' -> continues ')[1:])
            if request.one_root and root_status != result['status']:
                mismatches.append(f'{request.case}: root line {lines[:1]} does not show {result["status"]}')
            if set(expected.edge_segments) - set(segments):
                mismatches.append(f'{request.case}: continues segments {segments} lack {expected.edge_segments}')
            if request.planned_node and not any(line.split()[1:] == ['GAP', 'planned'] for line in lines):
                mismatches.append(f'{request.case}: no planned node line in {lines}')
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
