"""world_input: one native command or one stage of check."""
from dataclasses import dataclass, replace
from ._world_fixture import CheckRequest, EXTERNAL_INPUTS as REQUESTS, replay, stage_values, _terminal_check
MUTATIONS = {'digest_omits_the_contract': 'summary_names_its_inputs', 'word_times_accepted': 'bad_time_is_input_error', 'duplicate_ids_accepted': 'duplicate_event_id_is_input_error', 'retired_keys_accepted': 'retired_keys_are_input_errors', 'mesh_digest_omits_a_node': 'mesh_summary_names_its_inputs'}
CASES = tuple((q for q in REQUESTS if q.case_id in ('number', 'label', 'iso', 'word_time', 'mixed_time', 'duplicate_ids', 'missing_event_time', 'retired_schema_version', 'retired_run_id', 'retired_dependencies', 'retired_output_requirements', 'retired_target_guard', 'retired_target_guards', 'retired_atoms')))
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

def expected_Evaluate(q, state, mutation='', broken_guard=''):
    error = q.time_form in {'word', 'mixed'} and mutation != 'word_times_accepted' or (q.duplicate_ids and mutation != 'duplicate_ids_accepted') or (bool(q.retired_key) and mutation != 'retired_keys_accepted')
    new = State(q, q.time_form == 'missing', 'error' if error else 'PASS')
    new = replace(new, digests_match=mutation != 'digest_omits_the_contract')
    if mutation == 'mesh_digest_omits_a_node':
        new = replace(new, mesh_files=('mesh.json',))
    return new

def bad_time_is_input_error(state):
    return _terminal_check(state, lambda request: request.time_form in {'word', 'mixed'}, (2, 'error'), 'Unknown or mixed time escaped the input-error boundary')

def duplicate_event_id_is_input_error(state):
    return _terminal_check(state, lambda request: request.duplicate_ids, (2, 'error'), 'A duplicate event identity was accepted')

def retired_keys_are_input_errors(state):
    return _terminal_check(state, lambda request: bool(request.retired_key), (2, 'error'), 'A retired contract/claim key escaped the typed input-error boundary')

def summary_names_its_inputs(state):
    return True if state.digests_match else False

def mesh_summary_names_its_inputs(state):
    if state.mesh_id != MESH_ID or state.mesh_files != MESH_FILES:
        return False
    return True
RULES = (mesh_summary_names_its_inputs, summary_names_its_inputs, bad_time_is_input_error, duplicate_event_id_is_input_error, retired_keys_are_input_errors)

def assert_native_contract():
    mismatches = []
    checked = 0
    for request in CASES:
        code, report = replay(request)
        expected = expected_Evaluate(request, State()).status
        actual = stage_values(request, code, report)[0]
        if actual != expected:
            mismatches.append(f'{request.case_id}: stage {expected!r}, native {actual!r}')
        if (code == 2) != (expected == 'error'):
            mismatches.append(f'{request.case_id}: typed input exit disagrees')
        checked += 1
    import hashlib, json, tempfile, io
    from pathlib import Path
    from contextlib import redirect_stdout
    from worldguard.cli import main
    from ._world_fixture import _real_contract
    with tempfile.TemporaryDirectory(prefix='check-inputs-') as directory:
        path = Path(directory) / 'world.json'
        path.write_text(json.dumps(_real_contract(CASES[0])))
        output = io.StringIO()
        with redirect_stdout(output):
            main(['check', '--contract', str(path)])
        report = json.loads(output.getvalue())
        expected = [{'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}]
        if report.get('input_digests') != expected:
            mismatches.append('summary_names_its_inputs: missing or incorrect raw input digest')
        root = Path(directory)
        node = root / 'nodes/world.json'
        node.parent.mkdir()
        contract = _real_contract(CASES[0])
        node.write_text(json.dumps(contract) + '\n')
        mesh = root / 'mesh.json'
        mesh.write_text(json.dumps({'mesh_id': MESH_ID, 'nodes': [{'model_id': 'file', 'contract': 'nodes/world.json'}, {'model_id': 'inline', 'contract': contract}], 'edges': [{'edge_id': 'file-inline', 'from': 'file', 'to': 'inline', 'relation': 'parent_child'}]}, indent=2) + '\n')
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(['mesh-check', '--mesh', str(mesh)])
        report = json.loads(output.getvalue())
        expected = [{'path': p.relative_to(root).as_posix(), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in (mesh, node)]
        keys = {'checked', 'gaps', 'input_digests', 'mesh_id', 'output', 'scope_limits', 'status', 'tree'}
        if code != 0 or report.get('mesh_id') != MESH_ID or report.get('input_digests') != expected or (set(report) != keys):
            mismatches.append(f"mesh_summary_names_its_inputs: native mesh id/raw file digests/compact keys differ; actual id={report.get('mesh_id')!r}, digests={report.get('input_digests')!r}, keys={sorted(report)}")
    assert not mismatches, mismatches
RULE_NAMES = ('mesh_summary_names_its_inputs', 'summary_names_its_inputs', 'bad_time_is_input_error', 'duplicate_event_id_is_input_error', 'retired_keys_are_input_errors')
