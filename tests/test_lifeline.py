"""The discussion picture is computed from the model: one entity, only its declared facts, and a note of what was left out."""
import json
from pathlib import Path

import yaml

from worldguard.cli import main
from worldguard.lifeline import lifeline, render_mermaid
from worldguard.mesh import ModelMeshContract, run_model_mesh

LIGHTHOUSE = Path(__file__).parent / "fixtures/trials/lighthouse_key"


def _picture(capsys, *args):
    code = main(["lifeline", *map(str, args)])
    return code, capsys.readouterr().out


def test_discussing_the_slip_draws_lenas_life_with_the_contradiction_marked(capsys):
    code, out = _picture(capsys, "--mesh", LIGHTHOUSE / "mesh_slip.yaml", "--of", "Lena")
    assert code == 0
    assert out.splitlines() == [
        "```mermaid",
        "flowchart LR",
        '  n0["ch1 start<br/>at island"]',
        '  n1["ch1 e_find_key<br/>at island<br/>holds key"]',
        '  n2["ch1 e_ferry_out<br/>at mainland<br/>holds key"]',
        '  n3["ch2 start<br/>at island<br/>holds key"]',
        '  n4["ch2 e_give_key<br/>at island"]',
        '  n0 -->|"9:00 e_find_key (ch1 p1)"| n1',
        '  n1 -->|"12:00 e_lock (ch1 p2)"| n1',
        '  n1 -->|"14:00 e_ferry_out (ch1 p3)"| n2',
        '  n2 -.->|"continues into ch2 !! MESH_HANDOFF_STATE_MISMATCH"| n3',
        '  n3 -->|"18:00 e_give_key (ch2 p1) !! EVENT_RELATION_UNMET"| n4',
        "  classDef problem stroke:#c00,stroke-width:2px",
        "  class n4 problem",
        "  linkStyle 3,4 stroke:#c00,stroke-width:2px",
        "```",
        "Shown: Lena, 5 boxes, 4 events; each box lists only the declared facts about Lena.",
        "Left out: 2 events without Lena (ch2 e_tom_ferry, ch2 e_unlock); nodes without Lena: story; every fact not about Lena.",
    ]


def test_the_picture_follows_declarations_not_names(capsys):
    _code, plain = _picture(capsys, "--contract", LIGHTHOUSE / "ch2_declared.yaml", "--of", "key")
    text = (LIGHTHOUSE / "ch2_declared.yaml").read_text()
    for old, new in (("lena_has_key", "key_held_by_L"), ("tom_has_key", "key_held_by_T"),
                     ("lena_on_mainland", "L_on_mainland"), ("tom_on_mainland", "T_on_mainland")):
        text = text.replace(old, new)
    world = yaml.safe_load(text)
    from worldguard import GuardContract
    from worldguard.kernel import run_worldguard
    contract = GuardContract.from_dict(world)
    renamed = render_mermaid(lifeline("key", contract=contract, report=run_worldguard(contract)))
    assert renamed + "\n" == plain
    assert '  n1 -->|"21:00 e_unlock (ch2 p3) !! EVENT_RELATION_UNMET"| n2' in plain.splitlines()


def test_long_lives_are_folded_and_the_fold_is_named():
    mesh = ModelMeshContract.from_dict(yaml.safe_load((LIGHTHOUSE / "mesh_slip.yaml").read_text()), base_dir=LIGHTHOUSE)
    view = lifeline("Lena", mesh=mesh, report=run_model_mesh(mesh), limit=4)
    assert len(view["boxes"]) == 4 and view["folded"] == 2
    assert view["boxes"][2]["label"] == "2 more steps" and view["boxes"][2]["problem"] is False
    text = render_mermaid(view)
    assert "2 middle steps folded into one box (add --all to draw them)" in text
    full = lifeline("Lena", mesh=mesh, report=run_model_mesh(mesh), limit=None)
    assert len(full["boxes"]) == 5 and full["folded"] == 0


def test_an_undeclared_world_says_what_the_picture_cannot_show(capsys):
    code, out = _picture(capsys, "--contract", LIGHTHOUSE / "ch2.yaml", "--of", "Lena")
    assert code == 0
    assert '(no declared fact)' in out
    assert out.splitlines()[-1] == ("No world_model.relations name Lena in ch2; declare them to see what it holds and "
                                    "where it is.")


def test_an_unknown_entity_is_an_input_error(capsys):
    code, out = _picture(capsys, "--contract", LIGHTHOUSE / "ch2_declared.yaml", "--of", "Iris")
    assert code == 2
    message = json.loads(out)["error"]["message"]
    assert message == "'Iris' takes part in no event and no declared relation; known: Lena, Tom, island, key, mainland"
