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
