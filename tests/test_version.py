import tomllib
from pathlib import Path

import worldguard

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_declared_consistently() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == (ROOT / "VERSION").read_text(encoding="utf-8").strip() == worldguard.__version__


def test_the_readmes_name_the_declared_version() -> None:
    """The version table and the install commands must name a tag that exists: the declared version."""
    tag = "v" + (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    for name in ("README.md", "README.zh-CN.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if line.startswith("| `v")]
        assert rows and all(row.startswith(f"| `{tag}` |") for row in rows), (name, rows)
        tags = [line.split("--branch ")[1].split()[0] for line in text.splitlines() if "git clone" in line and "--branch" in line]
        tags += [line.rsplit("@", 1)[1].rstrip('"') for line in text.splitlines()
                 if "pip install" in line and "WorldGuard.git@" in line]
        assert tags and set(tags) == {tag}, (name, tags)


UNRELEASED_NOTE = {"README.md": "> **Not released yet.** This page describes `main`",
                   "README.zh-CN.md": "> **尚未发布。** 本页描述的是 `main`"}


def _unreleased_entries() -> list[str]:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    if "\n## Unreleased\n" not in text:
        return []
    section = text.split("\n## Unreleased\n", 1)[1].split("\n## ", 1)[0]
    return [line for line in section.splitlines() if line.startswith("- ")]


def test_the_readmes_say_they_describe_unreleased_changes_exactly_while_there_are_some() -> None:
    """The READMEs describe main but install the declared tag; while CHANGELOG lists unreleased changes, the install
    section must say that the tag does not have them. The release that moves the tag removes the note."""
    unreleased = bool(_unreleased_entries())
    for name, note in UNRELEASED_NOTE.items():
        text = (ROOT / name).read_text(encoding="utf-8")
        assert (note in text) is unreleased, (name, unreleased)
        if unreleased:
            tag = "v" + (ROOT / "VERSION").read_text(encoding="utf-8").strip()
            assert f"`{tag}`" in text.split(note, 1)[1].split("\n\n", 1)[0], (name, "the note names the released tag")
