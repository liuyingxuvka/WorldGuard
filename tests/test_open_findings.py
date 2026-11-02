"""A contradiction found in a tree stays on record, with the chapters that set it up, until a check of that tree resolves it."""
import json
from pathlib import Path
import shutil

import yaml

from worldguard.cli import main

LIGHTHOUSE = Path(__file__).parent / "fixtures/trials/lighthouse_key"


def _story(tmp_path):
    """The lighthouse tree with the buried slip: chapter 2 starts Lena on the island she left in chapter 1."""
    for name in ("ch1_fixed.yaml", "ch2_slip.yaml", "ch2_fixed.yaml", "mesh_slip.yaml"):
        shutil.copyfile(LIGHTHOUSE / name, tmp_path / name)
    return tmp_path


def _run(capsys, *args):
    code = main(list(map(str, args)))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_a_buried_contradiction_is_still_shown_two_sessions_later(tmp_path, capsys):
    story = _story(tmp_path)
    code, out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert code == 1
    assert set(json.loads(out)) == {"checked", "gaps", "input_digests", "mesh_id", "output", "scope_limits", "status", "tree"}
    record = json.loads((story / ".worldguard/open.json").read_text())
    (handoff,) = [item for item in record["open"] if item["code"] == "MESH_HANDOFF_STATE_MISMATCH"]
    assert handoff["established_by"] == [
        {"chapter": "ch1", "source": "chapter 1", "event_id": "e_ferry_out", "where": "ch1 p3 (e_ferry_out)"},
        {"chapter": "ch2", "source": "chapter 2", "where": "start of ch2: lena_on_island holds"}]
    line = ("MESH_HANDOFF_STATE_MISMATCH [mesh_slip.yaml] lena_on_island is false at the end of the earlier chapter but "
            "true at the start of the next -- established by ch1 (chapter 1) ch1 p3 (e_ferry_out); "
            "ch2 (chapter 2) start of ch2: lena_on_island holds")
    assert line in err

    # Session 2 works on another chapter only; session 3 reads a timeline. Neither re-runs the tree.
    code, out, err = _run(capsys, "check", "--contract", story / "ch1_fixed.yaml")
    assert code == 0 and json.loads(out)["status"] == "PASS"
    assert line in err
    code, out, _err = _run(capsys, "timeline", "--contract", story / "ch1_fixed.yaml")
    assert code == 0
    assert out.splitlines()[0].startswith("open contradictions (2, recorded by mesh-check")
    assert any(line in row for row in out.splitlines()[1:3])
    assert len(json.loads((story / ".worldguard/open.json").read_text())["open"]) == 2


def test_only_a_check_of_the_same_tree_closes_it_and_says_how(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    other = yaml.safe_load((story / "mesh_slip.yaml").read_text())
    other["nodes"][2]["contract"] = "ch2_fixed.yaml"
    (story / "mesh_other.yaml").write_text(yaml.safe_dump(other))
    code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_other.yaml")
    assert code == 0 and "closed:" not in err and "open contradictions (2," in err

    chapter = yaml.safe_load((story / "ch2_slip.yaml").read_text())
    initial = chapter["inputs"]["event_model"]["initial_states"]
    initial[initial.index("lena_on_island")] = "lena_on_mainland"
    (story / "ch2_slip.yaml").write_text(yaml.safe_dump(chapter))
    code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert code == 0
    assert sorted(line.split(" [")[0] for line in err.splitlines()) == [
        "closed: EVENT_RELATION_UNMET", "closed: MESH_HANDOFF_STATE_MISMATCH"]
    assert all(line.endswith("-- no longer found") for line in err.splitlines())
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch1_fixed.yaml")
    assert err == ""
    record = json.loads((story / ".worldguard/open.json").read_text())
    assert record["open"] == [] and len(record["resolved"]) == 2


def test_removing_the_chapter_is_not_called_a_fix(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    mesh = yaml.safe_load((story / "mesh_slip.yaml").read_text())
    mesh["nodes"] = mesh["nodes"][:2]
    mesh["edges"] = mesh["edges"][:1]
    (story / "mesh_slip.yaml").write_text(yaml.safe_dump(mesh))
    _code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert sorted(err.splitlines()) == sorted(
        line for line in err.splitlines() if line.endswith("-- its chapter or event is no longer in the tree"))
    assert len(err.splitlines()) == 2


def test_a_record_that_cannot_be_read_or_written_is_reported(tmp_path, capsys):
    story = _story(tmp_path)
    (story / ".worldguard").mkdir()
    (story / ".worldguard/open.json").write_text("[]")
    code, out, _err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert code == 2 and "is not a WorldGuard record of open contradictions" in out
    shutil.rmtree(story / ".worldguard")
    (story / ".worldguard").write_text("not a folder")
    code, out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert code == 1 and json.loads(out)["status"] == "FAIL"
    assert err.startswith("worldguard: could not record open contradictions in ")


def test_a_passing_tree_writes_nothing(tmp_path, capsys):
    story = _story(tmp_path)
    mesh = yaml.safe_load((story / "mesh_slip.yaml").read_text())
    mesh["nodes"][2]["contract"] = "ch2_fixed.yaml"
    (story / "mesh_slip.yaml").write_text(yaml.safe_dump(mesh))
    code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert code == 0 and err == ""
    assert not (story / ".worldguard").exists()
