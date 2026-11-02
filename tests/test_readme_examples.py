"""The READMEs' console examples are real output: each one is run as written and compared with the README's text.

The commands run through the skill's own launcher, on a copy of the fixture folder they name, so the record of open
contradictions they keep lands in the copy and not in the repository. stdout is what the README shows; the record's
lines go to stderr, as the README says further down.
"""
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = "skills/worldguard/scripts/run_worldguard.py"
FIXTURES = "tests/fixtures/trials/lighthouse_key"
LEAD = f"$ python {LAUNCHER} timeline --contract {FIXTURES}/ch2_declared.yaml"
TREE = f"$ python {LAUNCHER} timeline --mesh {FIXTURES}/mesh_slip.yaml"
LIFELINE = f"$ python {LAUNCHER} lifeline --mesh {FIXTURES}/mesh_slip.yaml --of Lena"


def _console(readme, command):
    """The lines one console block shows under `command`, and the text after the block."""
    text = (ROOT / readme).read_text(encoding="utf-8")
    found = [match for match in re.finditer(r"```console\n(.*?)```\n", text, re.S) if match.group(1).splitlines()[0] == command]
    assert len(found) == 1, (readme, command, len(found))
    return found[0].group(1).splitlines()[1:], text[found[0].end():]


def _run(tmp_path, command):
    """Run the README command with its fixture folder replaced by a copy of that folder."""
    copy = shutil.copytree(ROOT / FIXTURES, tmp_path / "lighthouse_key")
    args = [str(copy) + argument[len(FIXTURES):] if argument.startswith(f"{FIXTURES}/") else argument
            for argument in shlex.split(command.removeprefix("$ "))[1:]]
    result = subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return result.stdout.splitlines(), result.stderr.splitlines()


@pytest.mark.parametrize("readme", ["README.md", "README.zh-CN.md"])
def test_the_lead_example_prints_what_the_readme_shows(tmp_path, readme):
    shown, _rest = _console(readme, LEAD)
    out, err = _run(tmp_path, LEAD)
    assert out == shown
    # Only the event that cannot happen is marked; the hand-over that set up the opposing facts is not.
    assert [line.split()[1] for line in out if "!!" in line] == ["e_unlock"]
    assert err[0].startswith("open contradictions (2; kept in ")


@pytest.mark.parametrize("readme", ["README.md", "README.zh-CN.md"])
def test_the_tree_example_starts_as_the_readme_shows(tmp_path, readme):
    shown, _rest = _console(readme, TREE)  # the README shows the first lines of the tree's timeline
    out, _err = _run(tmp_path, TREE)
    assert out[:len(shown)] == shown


@pytest.mark.parametrize("readme", ["README.md", "README.zh-CN.md"])
def test_the_lifeline_example_draws_what_the_readme_shows(tmp_path, readme):
    shown, rest = _console(readme, LIFELINE)
    assert shown == []  # the picture follows in its own mermaid block, then the "Shown" and "Left out" lines
    out, _err = _run(tmp_path, LIFELINE)
    picture = rest.lstrip("\n").split("\n\n", 1)[0].splitlines()
    assert picture[0] == "```mermaid" and out[:len(picture)] == picture
    assert rest.lstrip("\n").split("\n\n", 2)[1].splitlines() == out[len(picture):]
