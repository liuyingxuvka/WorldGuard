"""Copy worldguard/ into the portable skill runtime, or check that the copy is exact.

python scripts/sync_worldguard_portable_runtime.py check   # exit 0 when identical
python scripts/sync_worldguard_portable_runtime.py sync    # replace the copy, then check
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "worldguard"
TARGET = ROOT / "skills" / "worldguard" / "runtime" / "worldguard"
SKIPPED_SUFFIXES = {".pyc", ".pyo"}


def _files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in SKIPPED_SUFFIXES
    }


def differences(source: Path = SOURCE, target: Path = TARGET) -> list[str]:
    left, right = _files(source), _files(target)
    rows = [f"missing: {name}" for name in sorted(set(left) - set(right))]
    rows += [f"extra: {name}" for name in sorted(set(right) - set(left))]
    rows += [
        f"differs: {name}"
        for name in sorted(set(left) & set(right))
        if left[name].read_bytes() != right[name].read_bytes()
    ]
    return rows


def sync(source: Path = SOURCE, target: Path = TARGET) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args not in (["check"], ["sync"]):
        print("usage: python scripts/sync_worldguard_portable_runtime.py {check,sync}", file=sys.stderr)
        return 2
    if args == ["sync"]:
        sync()
    rows = differences()
    for row in rows:
        print(row)
    print("mirror-ok" if not rows else f"{len(rows)} difference(s)")
    return 0 if not rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
