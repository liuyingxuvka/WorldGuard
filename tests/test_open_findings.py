"""A contradiction stays on record, with the chapters that set it up, until a check of its file finds it fixed."""
import json
from pathlib import Path
import shutil

import yaml

from worldguard.cli import main

LIGHTHOUSE = Path(__file__).parent / "fixtures/trials/lighthouse_key"
HANDOFF = ("MESH_HANDOFF_STATE_MISMATCH [mesh_slip.yaml] lena_on_island is false at the end of the earlier chapter but "
           "true at the start of the next -- established by ch1 (chapter 1) ch1 p3 (e_ferry_out); "
           "ch2 (chapter 2) start of ch2: lena_on_island holds")
UNMET = ("EVENT_RELATION_UNMET [ch2_slip.yaml] Lena is not at mainland at 18:00 (at island). -- established by ch2 "
         "(chapter 2) ch2 p1")


def _story(tmp_path):
    """The lighthouse tree with the buried slip: chapter 2 starts Lena on the island she left in chapter 1."""
    for name in ("ch1_fixed.yaml", "ch2_slip.yaml", "ch2_fixed.yaml", "mesh_slip.yaml", "mesh.yaml", "ch1.yaml", "ch2.yaml"):
        shutil.copyfile(LIGHTHOUSE / name, tmp_path / name)
    return tmp_path


def _run(capsys, *args):
    code = main(list(map(str, args)))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def _record(folder):
    return json.loads((folder / ".worldguard/open.json").read_text())


def _edit(path, change):
    data = yaml.safe_load(path.read_text())
    change(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _event(contract, event_id):
    return next(row for row in contract["inputs"]["events"] if row["event_id"] == event_id)


def test_a_buried_contradiction_is_still_shown_two_sessions_later(tmp_path, capsys):
    story = _story(tmp_path)
    code, out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert code == 1
    assert set(json.loads(out)) == {"checked", "gaps", "input_digests", "mesh_id", "output", "scope_limits", "status", "tree"}
    record = _record(story)
    (handoff,) = [item for item in record["open"] if item["code"] == "MESH_HANDOFF_STATE_MISMATCH"]
    assert handoff["unit"] == "mesh_slip.yaml" and handoff["edge_id"] == "ch1_ch2"
    assert handoff["established_by"] == [
        {"chapter": "ch1", "source": "chapter 1", "event_id": "e_ferry_out", "where": "ch1 p3 (e_ferry_out)"},
        {"chapter": "ch2", "source": "chapter 2", "where": "start of ch2: lena_on_island holds"}]
    (unmet,) = [item for item in record["open"] if item["code"] == "EVENT_RELATION_UNMET"]
    assert unmet["unit"] == "ch2_slip.yaml" and unmet["event_id"] == "e_give_key"
    assert any(line.startswith(f"  {HANDOFF}") for line in err.splitlines())
    assert any(line.startswith(f"  {UNMET}") for line in err.splitlines())

    # Session 2 works on another chapter only; session 3 reads a timeline. Neither re-checks the slip.
    code, out, err = _run(capsys, "check", "--contract", story / "ch1_fixed.yaml")
    assert code == 0 and json.loads(out)["status"] == "PASS"
    assert any(line.startswith(f"  {HANDOFF}") for line in err.splitlines())
    code, out, err = _run(capsys, "timeline", "--contract", story / "ch1_fixed.yaml")
    assert code == 0
    assert out.splitlines()[0].startswith("world ch1")  # the timeline itself; the record goes to stderr
    assert err.splitlines()[0].startswith("open contradictions (2; kept in ")
    assert len(_record(story)["open"]) == 2


def test_a_contradiction_found_by_check_alone_is_kept(tmp_path, capsys):
    story = _story(tmp_path)
    code, _out, err = _run(capsys, "check", "--contract", story / "ch2_slip.yaml")
    alone = UNMET.replace("established by ch2 (chapter 2) ch2 p1", "established by ch2_slip.yaml ch2 p1")
    assert code == 1 and any(line.startswith(f"  {alone}") for line in err.splitlines())
    (item,) = _record(story)["open"]
    assert (item["unit"], item["found_by"]) == ("ch2_slip.yaml", "check ch2_slip.yaml")
    # The tree finds the same contradiction in the same file: one entry, seen twice.
    _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    entries = [entry for entry in _record(story)["open"] if entry["code"] == "EVENT_RELATION_UNMET"]
    assert len(entries) == 1 and entries[0]["runs"] == 2


def test_a_chapter_in_a_subfolder_sees_the_trees_record_and_can_close_its_own_entry(tmp_path, capsys):
    story = _story(tmp_path)
    chapters = story / "chapters"
    chapters.mkdir()
    for name in ("ch1_fixed.yaml", "ch2_slip.yaml"):
        (story / name).rename(chapters / name)
    _edit(story / "mesh_slip.yaml", lambda mesh: [node.update(contract=f"chapters/{node['contract']}")
                                                  for node in mesh["nodes"] if isinstance(node.get("contract"), str)])
    _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert not (chapters / ".worldguard").exists()
    code, _out, err = _run(capsys, "check", "--contract", chapters / "ch1_fixed.yaml")
    assert code == 0 and "EVENT_RELATION_UNMET [chapters/ch2_slip.yaml]" in err

    # Chapter 2's own slip is fixed: Lena starts the chapter on the mainland, where she hands over the key.
    def fix(world):
        initial = world["inputs"]["event_model"]["initial_states"]
        initial[initial.index("lena_on_island")] = "lena_on_mainland"
    _edit(chapters / "ch2_slip.yaml", fix)
    code, _out, err = _run(capsys, "check", "--contract", chapters / "ch2_slip.yaml")
    assert ("closed: EVENT_RELATION_UNMET [chapters/ch2_slip.yaml] Lena is not at mainland at 18:00 (at island). -- "
            "re-checked by check ch2_slip.yaml: event e_give_key passes now") in err.splitlines()
    assert [item["code"] for item in _record(story)["open"]] == ["MESH_HANDOFF_STATE_MISMATCH"]


def test_a_check_that_stopped_running_does_not_close_the_contradiction(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    # Deleting the place turns the FAIL into a GAP: the check no longer runs on that event.
    _edit(story / "ch2_slip.yaml", lambda world: _event(world, "e_give_key").pop("place"))
    _code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert "closed:" not in err
    (item,) = [item for item in _record(story)["open"] if item["code"] == "EVENT_RELATION_UNMET"]
    assert item["held"] == "not re-checked: GAP EVENT_ACTOR_STATE_UNCHECKED on event e_give_key"
    assert any(UNMET in line and line.endswith("; not re-checked: GAP EVENT_ACTOR_STATE_UNCHECKED on event e_give_key)")
               for line in err.splitlines())
    # An exemption is not a fix either.
    _edit(story / "ch2_slip.yaml", lambda world: _event(world, "e_give_key").update(
        place="mainland", actor_state_free="the key changes hands by post"))
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch2_slip.yaml")
    assert "closed:" not in err
    (item,) = [item for item in _record(story)["open"] if item["code"] == "EVENT_RELATION_UNMET"]
    assert item["held"] == ("not re-checked: event e_give_key is marked actor_state_free "
                            "(the key changes hands by post)")


def test_a_guard_that_no_longer_runs_does_not_close_its_finding(tmp_path, capsys):
    story = _story(tmp_path)
    code, _out, _err = _run(capsys, "check", "--contract", story / "ch2.yaml")
    assert code == 1
    (item,) = [item for item in _record(story)["open"] if item["code"] == "EVENT_PRECONDITION_UNMET"]
    assert item["guard"] == "EventGuard"
    # Asking for no event checks makes the row disappear; it is not a fix.
    def no_event_checks(world):
        world["claim"].update(requested_semantics=["causal"], asserts=[{"variable": "x", "op": ">=", "value": 0}])
        world["inputs"]["causal_model"] = {"variables": ["x"], "equations": {"x": "1"}, "scenarios": {"base": {}}}
        world.pop("variants", None)
        for event in world["inputs"]["events"]:
            event.pop("actor"), event.pop("with", None)  # no actor-state row stands in for the dropped Guard
    _edit(story / "ch2.yaml", no_event_checks)
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch2.yaml")
    assert "closed:" not in err
    (item,) = [item for item in _record(story)["open"] if item["code"] == "EVENT_PRECONDITION_UNMET"]
    assert item["held"] == "not re-checked: EventGuard does not run on ch2.yaml now"


def test_a_real_fix_closes_it_once_and_says_how(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    other = yaml.safe_load((story / "mesh_slip.yaml").read_text())
    other["nodes"][2]["contract"] = "ch2_fixed.yaml"
    (story / "mesh_other.yaml").write_text(yaml.safe_dump(other))
    code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_other.yaml")
    assert code == 0 and "closed:" not in err and "open contradictions (2;" in err

    def fix(chapter):
        initial = chapter["inputs"]["event_model"]["initial_states"]
        initial[initial.index("lena_on_island")] = "lena_on_mainland"
    _edit(story / "ch2_slip.yaml", fix)
    code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert code == 0
    assert sorted(err.splitlines()) == [
        "closed: EVENT_RELATION_UNMET [ch2_slip.yaml] Lena is not at mainland at 18:00 (at island). -- "
        "re-checked by mesh-check mesh_slip.yaml: event e_give_key passes now",
        "closed: MESH_HANDOFF_STATE_MISMATCH [mesh_slip.yaml] lena_on_island is false at the end of the earlier chapter "
        "but true at the start of the next -- re-checked by mesh-check mesh_slip.yaml: hand-over ch1_ch2 passes now"]
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch1_fixed.yaml")
    assert err == ""
    record = _record(story)
    assert record["open"] == [] and len(record["resolved"]) == 2


def test_removing_the_chapter_closes_the_handover_but_not_the_chapters_own_slip(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")

    def drop(mesh):
        mesh["nodes"] = mesh["nodes"][:2]
        mesh["edges"] = mesh["edges"][:1]
    _edit(story / "mesh_slip.yaml", drop)
    _code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert [line for line in err.splitlines() if line.startswith("closed:")] == [
        "closed: MESH_HANDOFF_STATE_MISMATCH [mesh_slip.yaml] lena_on_island is false at the end of the earlier chapter "
        "but true at the start of the next -- hand-over ch1_ch2 is no longer in mesh_slip.yaml"]
    assert [item["code"] for item in _record(story)["open"]] == ["EVENT_RELATION_UNMET"]
    (story / "ch2_slip.yaml").unlink()
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch1_fixed.yaml")
    assert err.splitlines() == [
        "closed: EVENT_RELATION_UNMET [ch2_slip.yaml] Lena is not at mainland at 18:00 (at island). -- "
        "ch2_slip.yaml no longer exists"]


def test_a_record_that_cannot_be_read_or_written_stops_the_command(tmp_path, capsys):
    story = _story(tmp_path)
    (story / ".worldguard").mkdir()
    (story / ".worldguard/open.json").write_text("[]")
    code, out, _err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert code == 2
    error = json.loads(out)["error"]
    assert error["code"] == "WORLDGUARD_RECORD_ERROR" and "is not a WorldGuard record of open contradictions" in error["message"]
    shutil.rmtree(story / ".worldguard")
    (story / ".worldguard").write_text("not a folder")
    code, out, _err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert code == 2
    error = json.loads(out)["error"]
    assert error["code"] == "WORLDGUARD_RECORD_ERROR" and error["details"]["check_status"] == "FAIL"
    assert "could not write" in error["message"]


def test_a_passing_tree_writes_nothing(tmp_path, capsys):
    story = _story(tmp_path)
    _edit(story / "mesh_slip.yaml", lambda mesh: mesh["nodes"][2].update(contract="ch2_fixed.yaml"))
    code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert code == 0 and err == ""
    assert not (story / ".worldguard").exists()
