"""The portable installer checks raw bytes and keeps dry runs read-only."""
from dataclasses import dataclass
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from _world_fixture import ReplayReport

MODEL_ID = "skill_install"
PARENT = "installer"
IMPLEMENTED_BY = {"Install": "scripts/install_skill.py:main", "Differences": "scripts/install_skill.py:installed_differences"}
TESTED_BY = {"check_reports_every_difference": ["tests/test_cli_module.py:test_install_skill_copies_the_skill_and_the_launcher_writes_no_bytecode"]}

@dataclass(frozen=True)
class State:
    checked: bool = False
    dry_clean: bool = True
    exits: tuple[int, ...] = ()
    named: bool = True

class InstallAndCheck:
    name = "InstallAndCheck"
    reads = ()
    writes = ("checked", "dry_clean", "exits", "named")
    def __init__(self, broken=False):self.broken=broken
    def apply(self, request, state):
        result=State(True,True,(0,0 if self.broken else 1,0),True)
        yield FunctionResult(result,result,label="install, edit, restore")

def check_reports_every_difference(state, trace):
    if state.checked and (not state.dry_clean or state.exits!=(0,1,0) or not state.named):
        return InvariantResult.fail("An edited installed file was missed or a dry run wrote files")
    return InvariantResult.pass_()

INVARIANTS = (Invariant("check_reports_every_difference","Dry runs write nothing and byte changes are named until restored.",check_reports_every_difference),)
def make(broken=False):
    return Explorer(Workflow((InstallAndCheck(broken),)),(State(),),("install",),INVARIANTS,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {"check_misses_an_edited_copy":make(True)}

def conformance():
    import io,tempfile
    from pathlib import Path
    from contextlib import redirect_stdout
    from scripts import install_skill
    mismatches=[]
    with tempfile.TemporaryDirectory(prefix="skill-install-model-") as directory:
        target=Path(directory)/"skills"
        args=["--target",str(target)]
        output=io.StringIO()
        with redirect_stdout(output):code=install_skill.main(args+["--dry-run"])
        if code!=0 or target.exists():mismatches.append("dry run wrote the destination or failed")
        with redirect_stdout(output):code=install_skill.main(args)
        if code!=0:mismatches.append("install failed")
        with redirect_stdout(output):code=install_skill.main(args+["--check"])
        if code!=0 or install_skill.installed_differences(target/"worldguard"):mismatches.append("fresh installation differs")
        path=target/"worldguard/SKILL.md";original=path.read_bytes()
        path.write_bytes(bytes([original[0]^1])+original[1:])
        output=io.StringIO()
        with redirect_stdout(output):code=install_skill.main(args+["--check"])
        if code!=1 or "differs: SKILL.md" not in output.getvalue():mismatches.append("edited byte not reported by name")
        path.write_bytes(original)
        with redirect_stdout(output):code=install_skill.main(args+["--check"])
        if code!=0:mismatches.append("restored installation still differs")
    return ReplayReport(5,mismatches)
