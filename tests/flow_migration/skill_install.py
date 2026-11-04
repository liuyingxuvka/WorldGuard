"""The portable installer checks raw bytes and keeps dry runs read-only."""
from dataclasses import dataclass

@dataclass(frozen=True)
class State:
    checked: bool = False
    dry_clean: bool = True
    exits: tuple[int, ...] = ()
    named: bool = True

def expected_InstallAndCheck(request, state, mutation='', broken_guard=''):
    result = State(True, True, (0, 0 if mutation else 1, 0), True)
    return result

def check_reports_every_difference(state):
    if state.checked and (not state.dry_clean or state.exits != (0, 1, 0) or (not state.named)):
        return False
    return True
RULES = (check_reports_every_difference,)

def assert_native_contract():
    import io, tempfile
    from pathlib import Path
    from contextlib import redirect_stdout
    from scripts import install_skill
    mismatches = []
    with tempfile.TemporaryDirectory(prefix='skill-install-model-') as directory:
        target = Path(directory) / 'skills'
        args = ['--target', str(target)]
        output = io.StringIO()
        with redirect_stdout(output):
            code = install_skill.main(args + ['--dry-run'])
        if code != 0 or target.exists():
            mismatches.append('dry run wrote the destination or failed')
        with redirect_stdout(output):
            code = install_skill.main(args)
        if code != 0:
            mismatches.append('install failed')
        with redirect_stdout(output):
            code = install_skill.main(args + ['--check'])
        if code != 0 or install_skill.installed_differences(target / 'worldguard'):
            mismatches.append('fresh installation differs')
        path = target / 'worldguard/SKILL.md'
        original = path.read_bytes()
        path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
        output = io.StringIO()
        with redirect_stdout(output):
            code = install_skill.main(args + ['--check'])
        if code != 1 or 'differs: SKILL.md' not in output.getvalue():
            mismatches.append('edited byte not reported by name')
        path.write_bytes(original)
        with redirect_stdout(output):
            code = install_skill.main(args + ['--check'])
        if code != 0:
            mismatches.append('restored installation still differs')
    assert not mismatches, mismatches
RULE_NAMES = ('check_reports_every_difference',)
