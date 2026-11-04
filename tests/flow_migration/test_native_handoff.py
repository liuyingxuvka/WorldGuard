"""The shared adapter compares real production state/time findings in an isolated command."""
from pathlib import Path
import subprocess
import sys


def test_chapter_handoff_uses_native_state_time_and_recovery():
    root = Path(__file__).resolve().parents[2]
    script = '''from pathlib import Path
import sys
from flowguard.flow.adapter import check_trace, trace_calls
from flowguard.flow.checks import check_model
from flowguard.flow.model import load_model
root = Path(sys.argv[1])
graph = check_model(load_model(root/'.flowguard/flow/mesh_handoff.py', root)).graph
assert graph.complete
calls = {(call.action.name, tuple(call.args)):call.index for call in graph.calls}
for state_matches in (True, False):
    for time_forward in (True, False):
        trace = trace_calls(graph, [calls[('configure',(state_matches,time_forward))], calls[('check',())]])
        compared = check_trace(graph, trace)
        assert compared.status == 'conformant', ((state_matches, time_forward), compared.status, compared.reason,
        compared.conformance.format_text() if compared.conformance is not None else '')
trace = trace_calls(graph, [calls[('configure',(False,False))], calls[('check',())],
                            calls[('configure',(True,True))], calls[('check',())]])
compared = check_trace(graph, trace)
assert compared.status == 'conformant', ('recovery', compared.status, compared.reason,
        compared.conformance.format_text() if compared.conformance is not None else '')
print('native chapter state/time contradictions and recovery')
'''
    result = subprocess.run([sys.executable, '-c', script, str(root)], cwd=root,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'native chapter state/time' in result.stdout
