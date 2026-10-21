"""Run the WorldGuard CLI from this skill.

An installed skill carries the worldguard package in runtime/ (scripts/install_skill.py copies it
there). Inside the WorldGuard repository the skill has no runtime copy; the launcher then imports
the repository package two levels above the skill directory.
"""

from __future__ import annotations

from pathlib import Path
import sys


sys.dont_write_bytecode = True
RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "runtime"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if (RUNTIME_ROOT / "worldguard" / "__init__.py").is_file():
    sys.path.insert(0, str(RUNTIME_ROOT))
elif (REPOSITORY_ROOT / "worldguard" / "__init__.py").is_file():
    sys.path.insert(0, str(REPOSITORY_ROOT))
else:
    raise SystemExit("WorldGuard runtime is missing; reinstall the skill from its repository.")

from worldguard.cli import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
