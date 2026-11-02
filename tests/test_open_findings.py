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
         "(chapter 2) ch2 p1 (e_give_key) needs: Lena is at mainland; ch2 (chapter 2) start of ch2: Lena is at island")


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
    alone = UNMET.replace("ch2 (chapter 2) ", "ch2_slip.yaml ").replace("start of ch2:", "start of ch2_slip.yaml:")
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
            "re-checked by check ch2_slip.yaml: Lena is at mainland just before event e_give_key now") in err.splitlines()
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
    assert item["held"] == ("not re-checked: whether Lena is at mainland before event e_give_key: the event is marked "
                            "actor_state_free (the key changes hands by post)")


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
        "re-checked by mesh-check mesh_slip.yaml: Lena is at mainland just before event e_give_key now",
        "closed: MESH_HANDOFF_STATE_MISMATCH [mesh_slip.yaml] lena_on_island is false at the end of the earlier chapter "
        "but true at the start of the next -- re-checked by mesh-check mesh_slip.yaml: the chapters of hand-over ch1_ch2 "
        "no longer both name lena_on_island"]
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch1_fixed.yaml")
    assert err == ""
    record = _record(story)
    assert record["open"] == [] and len(record["resolved"]) == 2


GONE = "file gone: ch2_slip.yaml no longer exists; it stays open until world ch2 is checked again under its new path"


def _fix_the_start(world):
    """Chapter 2's own slip fixed: Lena starts the chapter on the mainland, where she hands over the key."""
    initial = world["inputs"]["event_model"]["initial_states"]
    initial[initial.index("lena_on_island")] = "lena_on_mainland"


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
    # Deleting the chapter's file is not a fix: the entry stays open and names the path it was last seen at.
    (story / "ch2_slip.yaml").unlink()
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch1_fixed.yaml")
    assert "closed:" not in err
    (item,) = _record(story)["open"]
    assert (item["unit"], item["held"]) == ("ch2_slip.yaml", GONE)
    assert err.splitlines()[1].startswith(f"  {UNMET}") and err.splitlines()[1].endswith(f"; {GONE})")


def test_a_renamed_chapter_keeps_its_contradiction_open_and_takes_it_along(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    (before,) = [item for item in _record(story)["open"] if item["code"] == "EVENT_RELATION_UNMET"]
    (story / "ch2_slip.yaml").rename(story / "ch2_renamed.yaml")
    # The next command on another chapter of the folder (world ch1) neither closes it nor takes it over.
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch1_fixed.yaml")
    assert "closed:" not in err
    (gone,) = [item for item in _record(story)["open"] if item["code"] == "EVENT_RELATION_UNMET"]
    assert (gone["unit"], gone["held"]) == ("ch2_slip.yaml", GONE)

    # The same contradiction checked under the new name: the entry moves there and keeps its history.
    code, _out, err = _run(capsys, "check", "--contract", story / "ch2_renamed.yaml")
    assert code == 1 and "closed:" not in err
    assert ("moved: EVENT_RELATION_UNMET [ch2_renamed.yaml] Lena is not at mainland at 18:00 (at island). -- "
            "ch2_slip.yaml is gone; the same contradiction is in ch2_renamed.yaml") in err.splitlines()
    (moved,) = [item for item in _record(story)["open"] if item["code"] == "EVENT_RELATION_UNMET"]
    assert (moved["unit"], moved["moved_from"], moved["first_seen"], moved["runs"]) == (
        "ch2_renamed.yaml", ["ch2_slip.yaml"], before["first_seen"], 2)
    assert "held" not in moved and moved["established_by"][0]["chapter"] == "ch2_renamed.yaml"

    _edit(story / "ch2_renamed.yaml", _fix_the_start)
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch2_renamed.yaml")
    assert ("closed: EVENT_RELATION_UNMET [ch2_renamed.yaml] Lena is not at mainland at 18:00 (at island). -- "
            "re-checked by check ch2_renamed.yaml: Lena is at mainland just before event e_give_key now") in err.splitlines()
    assert [item["code"] for item in _record(story)["open"]] == ["MESH_HANDOFF_STATE_MISMATCH"]


def test_a_moved_chapter_that_passes_under_its_new_path_closes_only_when_the_person_says_it_moved(tmp_path, capsys,
                                                                                                   monkeypatch):
    story = _story(tmp_path)
    _run(capsys, "check", "--contract", story / "ch2_slip.yaml")
    (story / "chapters").mkdir()
    (story / "ch2_slip.yaml").rename(story / "chapters/ch2.yaml")
    settle = ("if chapters/ch2.yaml is ch2_slip.yaml under a new path, run `worldguard check --contract chapters/ch2.yaml "
              "--takes-over ch2_slip.yaml` in the record's folder")
    # Under its new path the check stops reaching the event: the entry stays open and says both things.
    _edit(story / "chapters/ch2.yaml", lambda world: _event(world, "e_give_key").pop("place"))
    _code, _out, err = _run(capsys, "check", "--contract", story / "chapters/ch2.yaml")
    assert "closed:" not in err and "moved:" not in err
    (item,) = _record(story)["open"]
    assert (item["unit"], item["held"]) == ("ch2_slip.yaml", "file gone: ch2_slip.yaml no longer exists; world ch2 is in "
                                            "chapters/ch2.yaml, not re-checked: GAP EVENT_ACTOR_STATE_UNCHECKED on event "
                                            f"e_give_key; {settle}")

    def place_and_fix(world):
        _event(world, "e_give_key")["place"] = "mainland"
        _fix_the_start(world)
    _edit(story / "chapters/ch2.yaml", place_and_fix)
    # The file passes: that alone does not say it is the moved chapter and not another draft of world ch2.
    _code, _out, err = _run(capsys, "check", "--contract", story / "chapters/ch2.yaml")
    assert "closed:" not in err
    (item,) = _record(story)["open"]
    assert item["held"] == ("file gone: ch2_slip.yaml no longer exists; world ch2 passed in chapters/ch2.yaml (re-checked by "
                            "check ch2.yaml: Lena is at mainland just before event e_give_key now), but a pass in another "
                            f"file does not close it; {settle}")
    # The named command, run in the record's folder, settles it.
    monkeypatch.chdir(story)
    _code, _out, err = _run(capsys, "check", "--contract", "chapters/ch2.yaml", "--takes-over", "ch2_slip.yaml")
    assert err.splitlines() == [
        "taken over: EVENT_RELATION_UNMET [chapters/ch2.yaml] Lena is not at mainland at 18:00 (at island). -- ch2_slip.yaml "
        "is gone; chapters/ch2.yaml takes over its entries, as --takes-over asked",
        "closed: EVENT_RELATION_UNMET [chapters/ch2.yaml] Lena is not at mainland at 18:00 (at island). -- re-checked by "
        "check ch2.yaml: Lena is at mainland just before event e_give_key now"]
    assert _record(story)["open"] == []


def test_a_renamed_tree_keeps_its_handover_open_until_the_tree_is_checked_again(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    (story / "mesh_slip.yaml").rename(story / "lighthouse.yaml")
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch1_fixed.yaml")
    assert "closed:" not in err
    (handoff,) = [item for item in _record(story)["open"] if item["code"] == "MESH_HANDOFF_STATE_MISMATCH"]
    assert handoff["held"] == ("file gone: mesh_slip.yaml no longer exists; it stays open until tree lighthouse is "
                               "checked again under its new path")
    _code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "lighthouse.yaml")
    assert "closed:" not in err
    assert sorted((item["code"], item["unit"]) for item in _record(story)["open"]) == [
        ("EVENT_RELATION_UNMET", "ch2_slip.yaml"), ("MESH_HANDOFF_STATE_MISMATCH", "lighthouse.yaml")]


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


def _strip_relations(world):
    """The reviewer's switch-off: no relations and no actor, place, uses or with on any event."""
    world["world_model"].pop("relations")
    for event in world["inputs"]["events"]:
        for key in ("actor", "with", "place", "uses"):
            event.pop(key, None)


def test_switching_the_relation_check_off_by_removing_its_declarations_keeps_the_entry(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "check", "--contract", story / "ch2_slip.yaml")
    _edit(story / "ch2_slip.yaml", _strip_relations)
    code, out, err = _run(capsys, "check", "--contract", story / "ch2_slip.yaml")
    assert code == 0 and json.loads(out)["status"] == "PASS"  # the check itself passes and says what it did not check
    assert "closed:" not in err
    (item,) = _record(story)["open"]
    assert item["held"] == ("not re-checked: whether Lena is at mainland before event e_give_key: world_model.relations "
                            "declares nothing; the event names no actor")
    assert err.splitlines()[1].endswith(f"; {item['held']})")


def test_an_untimed_event_elsewhere_keeps_the_entry(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "check", "--contract", story / "ch2_slip.yaml")
    _edit(story / "ch2_slip.yaml", lambda world: _event(world, "e_tom_ferry").pop("at"))
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch2_slip.yaml")
    assert "closed:" not in err
    (item,) = [item for item in _record(story)["open"] if item["code"] == "EVENT_RELATION_UNMET"]
    assert item["held"] == ("not re-checked: whether Lena is at mainland before event e_give_key: e_tom_ferry has no at "
                            "time, so the world was not replayed")


def test_an_event_that_no_longer_needs_the_fact_closes_and_says_what_it_needs_now(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "check", "--contract", story / "ch2_slip.yaml")

    def hand_over_on_the_island(world):
        # The story changes: Lena gives the key away on the island, to nobody in particular.
        _event(world, "e_give_key").update(place="island", **{"with": []})
    _edit(story / "ch2_slip.yaml", hand_over_on_the_island)
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch2_slip.yaml")
    assert ("closed: EVENT_RELATION_UNMET [ch2_slip.yaml] Lena is not at mainland at 18:00 (at island). -- re-checked by "
            "check ch2_slip.yaml: event e_give_key no longer needs Lena is at mainland (it now needs: Lena holds key, "
            "Lena is at island)") in err.splitlines()


def test_a_chapter_slip_names_the_event_that_set_up_the_opposing_fact(tmp_path, capsys):
    shutil.copyfile(LIGHTHOUSE / "ch2_declared.yaml", tmp_path / "ch2_declared.yaml")
    _run(capsys, "check", "--contract", tmp_path / "ch2_declared.yaml")
    (key,) = [item for item in _record(tmp_path)["open"] if item.get("subject", "").endswith("object=key")]
    assert key["summary"] == "Lena does not hold key at 21:00 (held by Tom)."
    assert key["established_by"] == [
        {"chapter": "ch2_declared.yaml", "event_id": "e_unlock", "where": "ch2 p3 (e_unlock) needs: Lena holds key"},
        {"chapter": "ch2_declared.yaml", "fact": "tom_has_key", "event_id": "e_give_key",
         "where": "ch2 p1 (e_give_key) makes: Tom holds key"},
        {"chapter": "ch2_declared.yaml", "event_id": "e_give_key", "where": "ch2 p1 (e_give_key) ends: Lena holds key"}]


def _two_places(tmp_path):
    """Lena starts the chapter on the island and on the mainland at once: WORLD_RELATION_CONFLICT."""
    path = tmp_path / "ch2_twice.yaml"
    shutil.copyfile(LIGHTHOUSE / "ch2_fixed.yaml", path)
    _edit(path, lambda world: world["inputs"]["event_model"]["initial_states"].append("lena_on_island"))
    return path


def test_a_conflict_stays_open_when_its_relations_are_removed_and_closes_on_a_real_fix(tmp_path, capsys):
    path = _two_places(tmp_path)
    code, _out, _err = _run(capsys, "check", "--contract", path)
    assert code == 1
    (item,) = [item for item in _record(tmp_path)["open"] if item["code"] == "WORLD_RELATION_CONFLICT"]
    assert item["question"] == ["relation_conflict", "", "at", "Lena"]
    original = path.read_text()
    _edit(path, _strip_relations)
    _code, _out, err = _run(capsys, "check", "--contract", path)
    assert "closed:" not in err
    (item,) = [item for item in _record(tmp_path)["open"] if item["code"] == "WORLD_RELATION_CONFLICT"]
    assert item["held"] == "not re-checked: Lena's places: world_model.relations declares nothing"
    path.write_text(original)
    _edit(path, lambda world: world["inputs"]["event_model"]["initial_states"].remove("lena_on_island"))
    _code, _out, err = _run(capsys, "check", "--contract", path)
    assert any(line.startswith("closed: WORLD_RELATION_CONFLICT") and line.endswith(
        "re-checked by check ch2_twice.yaml: Lena's places never overlap now") for line in err.splitlines())


def test_a_handover_whose_earlier_chapter_lost_its_times_stays_open(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    _edit(story / "ch1_fixed.yaml", lambda world: _event(world, "e_ferry_out").pop("at"))
    _code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "mesh_slip.yaml")
    assert "closed: MESH_HANDOFF" not in err
    (item,) = [item for item in _record(story)["open"] if item["code"] == "MESH_HANDOFF_STATE_MISMATCH"]
    assert item["held"].startswith("not re-checked: GAP MESH_HANDOFF_TIME_MISSING on hand-over ch1_ch2")


def _lamp(tmp_path):
    """The fixed chapter, but the door also needs a lit lamp nobody lights, and the claim says it is lit."""
    path = tmp_path / "ch2_lamp.yaml"
    shutil.copyfile(LIGHTHOUSE / "ch2_fixed.yaml", path)

    def lamp(world):
        _event(world, "e_unlock")["requires"].append("lamp_lit")
        world["claim"]["asserts"].append({"holds": "lamp_lit", "at": "21:00"})
        world.pop("variants", None)
    _edit(path, lamp)
    return path


def test_an_event_check_stays_open_while_the_events_cannot_be_replayed(tmp_path, capsys):
    path = _lamp(tmp_path)
    _run(capsys, "check", "--contract", path)
    (item,) = [item for item in _record(tmp_path)["open"] if item["code"] == "EVENT_PRECONDITION_UNMET"]
    assert item["question"] == ["precondition", "|e_unlock|lamp_lit"]
    _edit(path, lambda world: _event(world, "e_tom_ferry").pop("at"))
    _code, _out, err = _run(capsys, "check", "--contract", path)
    assert "closed: EVENT_PRECONDITION_UNMET" not in err
    (item,) = [item for item in _record(tmp_path)["open"] if item["code"] == "EVENT_PRECONDITION_UNMET"]
    assert item["held"] == "not re-checked: e_unlock: e_tom_ferry has no at time, so the events were not replayed"


def test_an_event_that_no_longer_requires_the_fact_closes_and_says_so(tmp_path, capsys):
    path = _lamp(tmp_path)
    _run(capsys, "check", "--contract", path)
    _edit(path, lambda world: _event(world, "e_unlock")["requires"].remove("lamp_lit"))
    _code, _out, err = _run(capsys, "check", "--contract", path)
    assert ("closed: EVENT_PRECONDITION_UNMET [ch2_lamp.yaml] e_unlock at 21:00 needs lamp_lit -- re-checked by check "
            "ch2_lamp.yaml: e_unlock no longer requires lamp_lit") in err.splitlines()


def test_a_false_claim_row_closes_when_it_holds_or_is_gone_and_says_which(tmp_path, capsys):
    path = _lamp(tmp_path)
    _run(capsys, "check", "--contract", path)
    rows = sorted(item["summary"] for item in _record(tmp_path)["open"] if item["code"] == "CLAIM_ASSERTION_FALSE")
    assert rows == ["claim row 1 is false: at: 21:00, holds: door_unlocked", "claim row 2 is false: at: 21:00, holds: lamp_lit"]

    def light_the_lamp_and_drop_the_claim(world):
        _event(world, "e_unlock")["requires"].remove("lamp_lit")
        world["claim"]["asserts"].pop()
    _edit(path, light_the_lamp_and_drop_the_claim)
    _code, _out, err = _run(capsys, "check", "--contract", path)
    closed = sorted(line for line in err.splitlines() if line.startswith("closed: CLAIM_ASSERTION_FALSE"))
    assert closed == [
        "closed: CLAIM_ASSERTION_FALSE [ch2_lamp.yaml] claim row 1 is false: at: 21:00, holds: door_unlocked -- "
        "re-checked by check ch2_lamp.yaml: claim row 1 (at: 21:00, holds: door_unlocked) holds now",
        "closed: CLAIM_ASSERTION_FALSE [ch2_lamp.yaml] claim row 2 is false: at: 21:00, holds: lamp_lit -- "
        "claim row 2 (at: 21:00, holds: lamp_lit) is no longer in the claim"]


def test_a_gone_file_whose_world_is_in_two_checked_files_is_not_followed(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "check", "--contract", story / "ch2_slip.yaml")
    (story / "ch2_slip.yaml").rename(story / "ch2_a.yaml")
    _edit(story / "ch2_a.yaml", _fix_the_start)
    tree = yaml.safe_load((story / "mesh_slip.yaml").read_text())
    tree["nodes"][1:] = [{"model_id": "a", "contract": "ch2_a.yaml"}, {"model_id": "b", "contract": "ch2_fixed.yaml"}]
    tree["nodes"][0]["contract"]["claim"]["asserts"] = [{"node": "a", "holds": "door_unlocked", "at": "21:00"}]
    tree["edges"] = [{"edge_id": "s1", "from": "story", "to": "a", "relation": "parent_child"},
                     {"edge_id": "s2", "from": "story", "to": "b", "relation": "parent_child"}]
    (story / "two.yaml").write_text(yaml.safe_dump(tree, sort_keys=False))
    # Both chapters of this tree declare world ch2 and both pass: neither is taken for the new path.
    code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "two.yaml")
    assert code == 0 and "closed:" not in err
    (item,) = _record(story)["open"]
    assert item["held"] == ("file gone: ch2_slip.yaml no longer exists; world ch2 is in more than one file this run "
                            "checked (ch2_a.yaml, ch2_fixed.yaml), so it is not followed to any of them; if one of them is "
                            "ch2_slip.yaml under a new path, run `worldguard check --contract <that file> --takes-over "
                            "ch2_slip.yaml` in the record's folder")


def test_a_file_back_under_its_last_path_no_longer_says_it_is_gone(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "check", "--contract", story / "ch2_slip.yaml")
    (story / "ch2_slip.yaml").rename(story / "ch2_away.yaml")
    _run(capsys, "check", "--contract", story / "ch1_fixed.yaml")
    assert _record(story)["open"][0]["held"] == GONE
    (story / "ch2_away.yaml").rename(story / "ch2_slip.yaml")
    _code, _out, err = _run(capsys, "check", "--contract", story / "ch1_fixed.yaml")
    (item,) = _record(story)["open"]
    assert "held" not in item and "gone_since" not in item and "file gone" not in err


def _declared(tmp_path):
    """Chapter 2 as first drafted (Lena still unlocks the door she gave away) next to the fixed draft of the same world."""
    for name in ("ch2_declared.yaml", "ch2_fixed.yaml"):
        shutil.copyfile(LIGHTHOUSE / name, tmp_path / name)
    return tmp_path


def test_a_pass_in_another_draft_of_the_world_does_not_close_a_gone_files_entries(tmp_path, capsys):
    story = _declared(tmp_path)
    _run(capsys, "check", "--contract", story / "ch2_declared.yaml")
    before = {item["summary"]: item for item in _record(story)["open"]}
    assert len(before) == 2
    (story / "ch2_declared.yaml").rename(story / "chapter2.yaml")
    # ch2_fixed.yaml also declares contract_id ch2 and passes: that is no fix of the renamed file.
    code, _out, err = _run(capsys, "check", "--contract", story / "ch2_fixed.yaml")
    assert code == 0 and "closed:" not in err and "moved:" not in err
    held = {item["held"] for item in _record(story)["open"]}
    assert len(held) == 2 and all(
        text.startswith("file gone: ch2_declared.yaml no longer exists; world ch2 passed in ch2_fixed.yaml (re-checked by "
                        "check ch2_fixed.yaml: event e_unlock no longer needs ")
        and text.endswith("), but a pass in another file does not close it; if ch2_fixed.yaml is ch2_declared.yaml under a "
                          "new path, run `worldguard check --contract ch2_fixed.yaml --takes-over ch2_declared.yaml` in "
                          "the record's folder") for text in held), held
    # The renamed file still has the same contradictions: the entries move there with their history.
    _code, _out, err = _run(capsys, "check", "--contract", story / "chapter2.yaml")
    assert "closed:" not in err and sum(line.startswith("moved: EVENT_RELATION_UNMET [chapter2.yaml]")
                                        for line in err.splitlines()) == 2
    after = _record(story)["open"]
    assert len(after) == 2 and all(
        (item["moved_from"], item["first_seen"], item["runs"]) == (["ch2_declared.yaml"], before[item["summary"]]["first_seen"], 2)
        for item in after)


def test_the_person_says_which_file_takes_over_a_gone_files_entries(tmp_path, capsys):
    story = _declared(tmp_path)
    _run(capsys, "check", "--contract", story / "ch2_declared.yaml")
    first_seen = sorted(item["first_seen"] for item in _record(story)["open"])
    (story / "ch2_declared.yaml").unlink()  # the first draft is dropped; ch2_fixed.yaml is chapter 2 now
    _run(capsys, "check", "--contract", story / "ch2_fixed.yaml")
    assert len(_record(story)["open"]) == 2
    code, _out, err = _run(capsys, "check", "--contract", story / "ch2_fixed.yaml", "--takes-over", story / "ch2_declared.yaml")
    assert code == 0
    lines = err.splitlines()
    assert sum(line.startswith("taken over: EVENT_RELATION_UNMET [ch2_fixed.yaml] ") and line.endswith(
        " -- ch2_declared.yaml is gone; ch2_fixed.yaml takes over its entries, as --takes-over asked") for line in lines) == 2
    assert sum(line.startswith("closed: EVENT_RELATION_UNMET [ch2_fixed.yaml] ") and " -- re-checked by check ch2_fixed.yaml: "
               "event e_unlock no longer needs " in line for line in lines) == 2
    record = _record(story)
    assert record["open"] == [] and sorted(item["first_seen"] for item in record["resolved"]) == first_seen
    assert all(item["moved_from"] == ["ch2_declared.yaml"] for item in record["resolved"])


def test_takes_over_refuses_what_it_cannot_do(tmp_path, capsys):
    story = _declared(tmp_path)
    _run(capsys, "check", "--contract", story / "ch2_declared.yaml")
    shutil.copyfile(LIGHTHOUSE / "ch1_fixed.yaml", story / "ch1_fixed.yaml")

    def refused(*args):
        code, out, _err = _run(capsys, "check", "--contract", *args)
        assert code == 2
        error = json.loads(out)["error"]
        assert error["code"] == "WORLDGUARD_INPUT_INVALID"
        return error["message"]
    assert "that file still exists" in refused(story / "ch2_fixed.yaml", "--takes-over", story / "ch2_declared.yaml")
    (story / "ch2_declared.yaml").unlink()
    assert "no open contradiction" in refused(story / "ch2_fixed.yaml", "--takes-over", story / "nothing.yaml")
    assert "world ch1" in refused(story / "ch1_fixed.yaml", "--takes-over", story / "ch2_declared.yaml")
    assert len(_record(story)["open"]) == 2  # a refused command changes nothing


def test_a_gone_file_whose_contradiction_is_in_two_checked_files_is_not_followed(tmp_path, capsys):
    story = _story(tmp_path)
    _run(capsys, "check", "--contract", story / "ch2_slip.yaml")
    (before,) = _record(story)["open"]
    shutil.copyfile(story / "ch2_slip.yaml", story / "a.yaml")  # a copy of the chapter ...
    (story / "ch2_slip.yaml").rename(story / "b.yaml")          # ... and the chapter itself, renamed
    tree = yaml.safe_load((story / "mesh_slip.yaml").read_text())
    tree["nodes"][1:] = [{"model_id": "a", "contract": "a.yaml"}, {"model_id": "b", "contract": "b.yaml"}]
    tree["nodes"][0]["contract"]["claim"]["asserts"] = [{"node": "a", "holds": "door_unlocked", "at": "21:00"}]
    tree["edges"] = [{"edge_id": "s1", "from": "story", "to": "a", "relation": "parent_child"},
                     {"edge_id": "s2", "from": "story", "to": "b", "relation": "parent_child"}]
    (story / "two.yaml").write_text(yaml.safe_dump(tree, sort_keys=False))
    # Both files have the same contradiction: neither is taken for the new path, and the entry names both.
    _code, _out, err = _run(capsys, "mesh-check", "--mesh", story / "two.yaml")
    assert "moved:" not in err and "closed:" not in err
    (gone,) = [item for item in _record(story)["open"] if item["unit"] == "ch2_slip.yaml"]
    assert gone["held"] == ("file gone: ch2_slip.yaml no longer exists; the same contradiction is found in more than one "
                            "file of world ch2 this run checked (a.yaml, b.yaml), so it is not followed to any of them; if "
                            "one of them is ch2_slip.yaml under a new path, run `worldguard check --contract <that file> "
                            "--takes-over ch2_slip.yaml` in the record's folder")
    assert sorted(item["unit"] for item in _record(story)["open"]) == ["a.yaml", "b.yaml", "ch2_slip.yaml"]
    # The person names the real rename: its entry keeps the gone file's history, and the copy keeps its own.
    _code, _out, err = _run(capsys, "check", "--contract", story / "b.yaml", "--takes-over", story / "ch2_slip.yaml")
    entries = {item["unit"]: item for item in _record(story)["open"]}
    assert sorted(entries) == ["a.yaml", "b.yaml"]
    assert (entries["b.yaml"]["first_seen"], entries["b.yaml"]["moved_from"]) == (before["first_seen"], ["ch2_slip.yaml"])
    assert "moved_from" not in entries["a.yaml"]
