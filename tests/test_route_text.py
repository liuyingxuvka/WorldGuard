"""Check route content for repeated material, dead references and unknown names."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import re
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from worldguard.cli import main

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/worldguard"
LINKS = re.compile(r"\[[^\]]*\]\(([^\s)]+)\)")
CODES = re.compile(r"`([^`\n]+)`")
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
                try:
                    main(args)
                except SystemExit as error:
                    assert error.code == 0
    return flags


def _slug(heading):
    return re.sub(r"[^\w\s-]", "", heading.lower()).replace(" ", "-")


def _destination(origin, link):
    value = urlsplit(link)
    if value.scheme or value.netloc:
        return None
    path = (origin.parent / unquote(value.path)).resolve() if value.path else origin
    return path, unquote(value.fragment)


def _check(route, texts, flags):
    paragraphs = Counter(
        " ".join(part.split())
        for text in texts.values()
        for part in re.split(r"\n\s*\n", text)
        if len(part.split()) >= 8
    )
    for paragraph, count in paragraphs.items():
        assert count == 1, f"{route}: repeated paragraph: {paragraph}"
    for origin, text in texts.items():
        for link in LINKS.findall(text):
            resolved = _destination(origin, link)
            if resolved is None:
                continue
            target, fragment = resolved
            assert target.exists(), f"{route}: dead link: {link} in {origin}"
            if fragment:
                headings = re.findall(r"^#+ (.+)$", target.read_text(), re.M)
                assert fragment in {
                    _slug(heading) for heading in headings
                }, f"{route}: missing heading: {link} in {origin}"
        for code in CODES.findall(text):
            if code.startswith(
                ("grep ", "git ", "pip ", "python -m pytest", "python -m flowguard")
            ):
                continue
            for option in re.findall(r"--[a-z0-9][\w-]*", code):
                assert option in flags, f"{route}: unknown option: {code}"
            if code.startswith(("references/", "assets/", "scripts/", "agents/")):
                target = SKILL / code.split()[0].split("#", 1)[0]
            elif code.startswith(("worldguard/", "tests/")):
                target = ROOT / code.split()[0].split("#", 1)[0]
            else:
                continue
            if "<" in code or "*" in code:
                continue
            assert target.exists(), f"{route}: missing path: {code}"


def test_route_texts_have_no_repeats_dead_links_or_missing_names():
    flags = _cli_options()
    errors = []
    entry = SKILL / "SKILL.md"
    routes = sorted(
        {
            (entry.parent / urlsplit(link).path).resolve()
            for link in LINKS.findall(entry.read_text())
            if urlsplit(link).path.startswith("references/")
        }
    )
    for route in routes:
        files = {entry, route}
        try:
            for path in files:
                assert path.is_file(), f"{route.name}: missing reference: {path}"
            texts = {path: path.read_text() for path in sorted(files)}
            _check(route.name, texts, flags)
        except AssertionError as error:
            errors.append(str(error))
        print(
            f"route {route.name}: {sum(len(p.read_text()) for p in files if p.is_file())} characters"
        )
    assert not errors, "\n".join(errors)


def test_skill_has_three_references_and_the_model_tree_block():
    references = sorted((SKILL / "references").glob("*.md"))
    assert {path.name for path in references} == {
        "guard-inputs.md",
        "worldguard-contracts.md",
        "model-mesh.md",
    }
    paragraphs = (SKILL / "SKILL.md").read_text().split("\n\n")
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
    text = (SKILL / "SKILL.md").read_text()
    headings = [line for line in text.splitlines() if line.startswith("## ")]
    assert headings[0] == "## Start from the model"
    assert headings.index("## Start from the model") < headings.index("## Choose a command")
    section = text.split("## Start from the model", 1)[1].split("\n## ", 1)[0]
    for word in ("timeline", "asserts", "variants", "continues", "contract", "planned"):
        assert word in section, word
