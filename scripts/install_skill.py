"""Install the WorldGuard skill into an agent's skills directory.

    python scripts/install_skill.py --target "$CODEX_HOME/skills"            # or ~/.claude/skills
    python scripts/install_skill.py --target "$CODEX_HOME/skills" --dry-run
    python scripts/install_skill.py --target "$CODEX_HOME/skills" --check    # exit 1 if the copy differs

Copies skills/worldguard/ (SKILL.md, references, assets, the launcher and the bundled
runtime) to <target>/worldguard/, replacing an older copy. The launcher needs Python >= 3.11;
YAML world models also need PyYAML (python -m pip install PyYAML), JSON ones do not.
"""

from __future__ import annotations

import argparse
import filecmp
import os
import re
import shutil
import sys
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "skills" / "worldguard"
IGNORED = ("__pycache__", "*.pyc", "*.pyo")


def differences(src: Path, dst: Path) -> list[str]:
    if not dst.is_dir():
        return [f"missing {dst}"]
    out = []
    cmp = filecmp.dircmp(src, dst, ignore=["__pycache__"])
    stack = [(cmp, Path("."))]
    while stack:
        node, rel = stack.pop()
        out += [f"only in source: {rel / n}" for n in node.left_only]
        out += [f"only in target: {rel / n}" for n in node.right_only]
        out += [
            f"differs: {rel / n}"
            for n in node.common_files
            if (Path(node.left) / n).read_bytes() != (Path(node.right) / n).read_bytes()
        ]
        out += [f"type differs: {rel / n}" for n in node.common_funny]
        out += [f"unreadable: {rel / n}" for n in node.funny_files]
        stack += [(sub, rel / name) for name, sub in node.subdirs.items()]
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True, help="skills directory, e.g. $CODEX_HOME/skills")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    # Also accept a literal shell-style path passed through a GUI or quoted command.
    required = re.findall(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))|%([A-Za-z_][A-Za-z0-9_]*)%", args.target)
    missing = [next(part for part in match if part) for match in required
               if not os.environ.get(next(part for part in match if part))]
    if missing:
        parser.error("target environment variable is unset: " + ", ".join(missing))
    target = re.sub(r"%([A-Za-z_][A-Za-z0-9_]*)%", lambda m: os.environ[m[1]], args.target)
    dst = Path(os.path.expandvars(target)).expanduser() / "worldguard"
    if not (SOURCE / "SKILL.md").is_file():
        print(f"skill source not found: {SOURCE}", file=sys.stderr)
        return 2
    diff = differences(SOURCE, dst)
    if args.check:
        print("\n".join(diff) or "installed skill is current")
        return 1 if diff else 0
    if args.dry_run:
        print(f"would copy {SOURCE} -> {dst}" + (f" ({len(diff)} difference(s))" if diff else " (already current)"))
        return 0
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(SOURCE, dst, ignore=shutil.ignore_patterns(*IGNORED))
    print(f"installed {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
