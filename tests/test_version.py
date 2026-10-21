import tomllib
from pathlib import Path

import worldguard

ROOT = Path(__file__).resolve().parents[1]


def test_version_is_declared_consistently() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["version"] == (ROOT / "VERSION").read_text(encoding="utf-8").strip() == worldguard.__version__
