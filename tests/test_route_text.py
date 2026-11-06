"""Check route content for repeated material, dead references and unknown names."""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import pytest

from flowguard.testing import LINKS, check_route_texts

from worldguard.cli import main

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/worldguard"
HELP_ARGS = [["--help"]]


def _cli_options():
    flags = set()
    original = argparse._ActionsContainer.add_argument

    def record(parser, *names, **kwargs):
        flags.update(name for name in names if name.startswith("-"))
        return original(parser, *names, **kwargs)

    with patch.object(argparse._ActionsContainer, "add_argument", record):
        with redirect_stdout(StringIO()):
            for args in HELP_ARGS:
                with pytest.raises(SystemExit) as stop:
                    main(args)
                assert stop.value.code == 0
    return flags


def _check(route, texts, flags):
    check_route_texts(route, texts, flags, skill_root=SKILL, project_root=ROOT,
                      project_prefixes=('worldguard/', 'tests/'))


def _routes():
    entry = SKILL / "SKILL.md"
    return sorted(
        {
            (entry.parent / urlsplit(link).path).resolve()
            for link in LINKS.findall(entry.read_text(encoding='utf-8'))
            if urlsplit(link).path.startswith("references/")
        }
    )


@pytest.mark.parametrize("route", _routes(), ids=lambda path: path.name)
def test_route_texts_have_no_repeats_dead_links_or_missing_names(route):
    """Each route the skill links is its own test, so every broken route is reported."""
    files = {SKILL / "SKILL.md", route}
    for path in files:
        assert path.is_file(), f"{route.name}: missing reference: {path}"
    _check(route.name, {path: path.read_text(encoding='utf-8') for path in sorted(files)}, _cli_options())


def test_skill_has_three_references_and_the_model_tree_block():
    references = sorted((SKILL / "references").glob("*.md"))
    assert {path.name for path in references} == {
        "guard-inputs.md",
        "worldguard-contracts.md",
        "model-mesh.md",
    }
    paragraphs = (SKILL / "SKILL.md").read_text(encoding='utf-8').split("\n\n")
    note = next(part for part in paragraphs if part.startswith("- Node:"))
    assert [line.split(":", 1)[0] for line in note.splitlines()] == [
        "- Node",
        "- Parent",
        "- Known-bad",
        "- Real binding",
        "- Test binding",
        "- Readback",
        "- Current vs target",
    ]


def test_skill_starts_from_the_model():
    text = (SKILL / "SKILL.md").read_text(encoding='utf-8')
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings[0] == "## Start from the model"
    assert headings.index("## Start from the model") < headings.index("## Choose a command")
    section = text.split("## Start from the model", 1)[1].split("\n## ", 1)[0]
    for word in ("timeline", "asserts", "variants", "continues", "contract", "planned"):
        assert word in section, word
