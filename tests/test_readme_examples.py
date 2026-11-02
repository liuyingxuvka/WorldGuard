"""The READMEs' console examples are real output: each one is run as written and compared with the README's text.

The commands run through the skill's own launcher, on a copy of the fixture files they read, so the record of open
contradictions they keep lands in the copy and not in the repository, and a record an earlier run left next to the
fixtures (it is ignored by git) changes nothing. stdout is what the README shows; the record's lines go to stderr, as
the README says further down.
"""
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys

import pytest
import yaml

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


def _run(tmp_path, command, fixtures=ROOT / FIXTURES):
    """Run the README command on a copy of only the fixture files it reads: the file it names and, for a tree, each
    chapter file the tree names. Nothing else in the folder (an ignored record left by an earlier run) is copied."""
    words = shlex.split(command.removeprefix("$ "))[1:]
    named = [word.removeprefix(f"{FIXTURES}/") for word in words if word.startswith(f"{FIXTURES}/")]
    trees = [words[index + 1].removeprefix(f"{FIXTURES}/") for index, word in enumerate(words) if word == "--mesh"]
    needed = set(named) | {node["contract"] for tree in trees
                           for node in yaml.safe_load((fixtures / tree).read_text(encoding="utf-8"))["nodes"]
                           if isinstance(node.get("contract"), str)}
    copy = tmp_path / "lighthouse_key"
    for name in sorted(needed):
        (copy / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixtures / name, copy / name)
    args = [str(copy / word.removeprefix(f"{FIXTURES}/")) if word.startswith(f"{FIXTURES}/") else word for word in words]
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


def test_a_record_left_in_the_fixture_folder_does_not_change_what_the_examples_print(tmp_path):
    # A checkout where someone ran the README's tree command keeps an ignored record next to the fixtures.
    checkout = shutil.copytree(ROOT / FIXTURES, tmp_path / "checkout" / FIXTURES)
    subprocess.run([sys.executable, LAUNCHER, "timeline", "--mesh", str(checkout / "mesh_slip.yaml")], cwd=ROOT,
                   capture_output=True, check=True)
    assert (checkout / ".worldguard/open.json").is_file()
    shown, _rest = _console("README.md", LEAD)
    out, err = _run(tmp_path / "run", LEAD, fixtures=checkout)
    assert out == shown and err[0].startswith("open contradictions (2; kept in ")


SETTLE = "`check --contract NEW.yaml --takes-over OLD.yaml`"


@pytest.mark.parametrize("readme", ["README.md", "README.zh-CN.md"])
def test_the_rename_sentences_say_what_a_rename_does(tmp_path, readme):
    # The README says: a rename closes nothing; a pass in another file of the world closes nothing either; the command
    # it names settles it. Each part is run here on the lead example's chapter.
    assert SETTLE in (ROOT / readme).read_text(encoding="utf-8")
    folder = tmp_path / "story"
    folder.mkdir()
    for name in ("ch2_declared.yaml", "ch2_fixed.yaml"):
        shutil.copyfile(ROOT / FIXTURES / name, folder / name)

    def run(*args):
        return subprocess.run([sys.executable, str(ROOT / LAUNCHER), *args], cwd=folder, capture_output=True, text=True,
                              encoding="utf-8").stderr

    run("check", "--contract", "ch2_declared.yaml")
    (folder / "ch2_declared.yaml").rename(folder / "chapter2.yaml")
    err = run("check", "--contract", "ch2_fixed.yaml")  # another draft of world ch2 passes
    assert "closed:" not in err and err.count("world ch2 passed in ch2_fixed.yaml") == 2
    command = SETTLE.strip("`").replace("NEW.yaml", "ch2_fixed.yaml").replace("OLD.yaml", "ch2_declared.yaml")
    assert err.count(f"run `worldguard {command}` in the record's folder") == 2
    err = run(*command.split())
    assert err.count("closed: EVENT_RELATION_UNMET [ch2_fixed.yaml]") == 2
