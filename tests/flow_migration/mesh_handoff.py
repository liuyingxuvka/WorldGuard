"""Finite mesh handoff outcomes, replayed through the real in-process CLI."""
from contextlib import redirect_stdout
from dataclasses import dataclass, replace
import io
import json
from pathlib import Path
import runpy
import shutil
import sys
import tempfile
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
    named_before: bool = True

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

def expected_RunMesh(request, state, mutation='', broken_guard=''):
    failures, gaps, boundaries = ([], [], [])
    if not request.state_matches and (request.named_before or mutation == 'continues_closed_world') and (mutation != 'label_only_handoff'):
        failures.append('MESH_HANDOFF_STATE_MISMATCH')
    if not request.time_forward and mutation != 'time_not_checked':
        failures.append('MESH_HANDOFF_TIME_BACKWARDS')
    if not request.descendant and mutation != 'node_rows_read_any_node':
        gaps.append('CLAIM_ASSERTION_UNRESOLVED')
    if request.child_status != 'PASS' and mutation != 'root_hides_child':
        if request.child_status == 'BOUNDARY_EXCEEDED':
            boundaries.append('EVENT_BOUNDARY_NUMERIC_DYNAMICS')
        else:
            (failures if request.child_status == 'FAIL' else gaps).append('CLAIM_ASSERTION_FALSE' if request.child_status == 'FAIL' else 'CLAIM_ASSERTION_UNRESOLVED')
    if request.planned_node:
        gaps.append('MESH_EXPECTED_NODE_CONTRACT_MISSING')
    if request.cycle and mutation != 'cycles_ignored':
        failures.append('MESH_DEPENDENCY_CYCLE')
    if not request.one_root and mutation != 'multiple_roots_allowed':
        gaps.append('MESH_NOT_ONE_TREE')
    variants_checked = request.has_variant and mutation != 'variants_not_run'
    if variants_checked and (not request.variant_caught):
        gaps.append('VARIANT_NOT_CAUGHT')
    status = 'FAIL' if failures else 'GAP' if gaps else 'BOUNDARY_EXCEEDED' if boundaries else 'PASS'
    code = 0 if status == 'PASS' else 1
    edge_failure = any((code in EDGE_FAILURES for code in failures))
    if mutation == 'root_line_hides_edge_failure':
        root_line = request.child_status if request.child_status != 'PASS' else 'PASS'
        segments = ('',) if edge_failure else ()
    else:
        root_line = status
        segments = ('FAIL',) if edge_failure else ()
    result = State(request, status, code, tuple(sorted(set(failures + gaps + boundaries))), variants_checked, root_line, segments, request.planned_node and mutation != 'root_line_hides_edge_failure')
    return result
EDGE_FAILURES = ('MESH_HANDOFF_STATE_MISMATCH', 'MESH_HANDOFF_TIME_BACKWARDS')

def requires_state(state):
    if state.request:
        expected = not state.request.state_matches and state.request.named_before
        if ('MESH_HANDOFF_STATE_MISMATCH' in state.codes) != expected:
            return False
    return True

def forward_time(state):
    if state.request and (not state.request.time_forward) and ('MESH_HANDOFF_TIME_BACKWARDS' not in state.codes):
        return False
    return True

def descendants_only(state):
    if state.request and (not state.request.descendant) and (state.status != 'GAP' or 'CLAIM_ASSERTION_UNRESOLVED' not in state.codes):
        return False
    return True

def children_preserved(state):
    if state.request and state.request.child_status != 'PASS' and (state.status == 'PASS'):
        return False
    return True

def cycles_fail(state):
    if state.request and state.request.cycle and (state.status != 'FAIL' or 'MESH_DEPENDENCY_CYCLE' not in state.codes):
        return False
    return True

def one_root(state):
    if state.request and (not state.request.one_root):
        if state.status == 'PASS' or 'MESH_NOT_ONE_TREE' not in state.codes:
            return False
    return True

def mesh_variants_must_fail(state):
    if state.request and state.request.has_variant:
        if not state.variants_checked:
            return False
        if not state.request.variant_caught and (state.status == 'PASS' or 'VARIANT_NOT_CAUGHT' not in state.codes):
            return False
    return True

def tree_lines_match_status(state):
    if not state.request:
        return True
    if state.request.one_root and state.root_line != state.status:
        return False
    if any((code in EDGE_FAILURES for code in state.codes)) and 'FAIL' not in state.edge_segments:
        return False
    if state.request.planned_node and (not state.planned_shown):
        return False
    return True
RULES = (requires_state, forward_time, descendants_only, children_preserved, cycles_fail, one_root, mesh_variants_must_fail, tree_lines_match_status)
CASES = (Request('chapters_ok_rooted.yaml'), Request('end_state_contradiction.yaml', state_matches=False, one_root=False), Request('ch2_resurrects.yaml', state_matches=False, one_root=False), Request('time_backwards.yaml', time_forward=False, one_root=False), Request('unrelated', descendant=False, one_root=False), Request('child_fail', child_status='FAIL'), Request('child_gap', child_status='GAP'), Request('child_boundary', child_status='BOUNDARY_EXCEEDED'), Request('cycle', cycle=True), Request('chapters_ok.yaml', one_root=False), Request('caught_variant', has_variant=True), Request('uncaught_variant', has_variant=True, variant_caught=False), Request('planned', planned_node=True), Request('edge_time_backwards', time_forward=False), Request('unnamed_fluent', state_matches=False, named_before=False))

def assert_native_contract():
    from worldguard.cli import main
    small_tree = runpy.run_path(str(ROOT / 'tests/test_model_mesh.py'))['continued_tree']
    mismatches = []
    with tempfile.TemporaryDirectory(prefix='mesh-handoff-replay-') as folder:
        fixtures = shutil.copytree(ROOT / 'tests/fixtures/trials/mesh_continues', Path(folder) / 'mesh_continues')
        for request in CASES:
            if request.case.endswith('.yaml'):
                path = fixtures / request.case
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
                elif request.case == 'unnamed_fluent':
                    data['nodes'][2]['contract']['inputs']['event_model']['initial_states'] = ['lit', 'tom_on_mainland']
                elif request.has_variant:
                    change = {'nodes[b].contract.inputs.event_model.initial_states': ['dark']} if request.variant_caught else {'nodes[a].contract.claim.claim_id': 'same-world-new-label'}
                    data['variants'] = [{'id': request.case, 'code': 'MESH_HANDOFF_STATE_MISMATCH', 'set': change}]
                else:
                    data['edges'].append({'edge_id': 'back', 'from': 'b', 'to': 'a', 'relation': 'continues'})
                path = Path(folder) / (request.case + '.json')
                path.write_text(json.dumps(data))
            expected = expected_RunMesh(request, State())
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(['mesh-check', '--mesh', str(path), '--json'])
            result = json.loads(output.getvalue())
            if request.case == 'unnamed_fluent':
                note = 'continues a-b: b starts with tom_on_mainland, which a never names'
                if note not in result['scope_limits']:
                    mismatches.append('unnamed_fluent: the new initial-state assumption is absent from scope_limits')
            codes = {row['code'] for row in result.get('gaps', [])}
            if (code, result['status']) != (expected.exit_code, expected.status) or not set(expected.codes) <= codes:
                mismatches.append(f"{request.case}: expected {expected.status}/{expected.codes}, actual {code}/{result['status']}/{sorted(codes)}")
            lines = result.get('tree', [])
            root_status = lines[0].split()[1] if lines else ''
            if lines and '(tree ' in lines[0]:
                root_status = lines[0].rsplit('(tree ', 1)[1].rstrip(')')
            segments = tuple(((part.split() + [''])[1] for line in lines for part in line.split(' -> continues ')[1:]))
            if request.one_root and root_status != result['status']:
                mismatches.append(f"{request.case}: root line {lines[:1]} does not show {result['status']}")
            if set(expected.edge_segments) - set(segments):
                mismatches.append(f'{request.case}: continues segments {segments} lack {expected.edge_segments}')
            if request.planned_node and (not any((line.split()[1:] == ['GAP', 'planned'] for line in lines))):
                mismatches.append(f'{request.case}: no planned node line in {lines}')
            if request.has_variant:
                variants = result.get('variants', [])
                if result.get('checked', {}).get('variants') != 1 or len(variants) != 1 or variants[0].get('caught') is not request.variant_caught:
                    mismatches.append(f'{request.case}: the native tree variant was not checked with its declared outcome')
    assert not mismatches, mismatches
RULE_NAMES = ('continues_requires_matching_state', 'continues_moves_time_forward', 'node_rows_read_descendants_only', 'child_non_pass_reaches_root', 'dependency_cycle_fails', 'one_root', 'mesh_variants_must_fail', 'tree_lines_match_status')
