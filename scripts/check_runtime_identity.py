"""Read-only version, portable-runtime, and optional installation comparison.

This audit does not execute domain models, install packages, or authorize a release.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import tomllib


def _version(package_root: Path) -> str:
    tree = ast.parse((package_root / "__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        ):
            return str(ast.literal_eval(node.value))
    raise ValueError("package version is missing")


def _files(root: Path) -> dict[str, str]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f"missing or unsafe tree: {root}")
    result = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"symlink is not an installation file: {path}")
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if path.is_file():
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not result:
        raise ValueError(f"empty tree: {root}")
    return result


def audit(root: Path, *, installed_skill: Path | None = None, package_root: Path | None = None) -> dict:
    root = root.resolve()
    failures = []
    version = ""
    projection = {}
    try:
        version = _version(root / "worldguard")
        declared = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
        if version != declared or version != (root / "VERSION").read_text().strip():
            failures.append("source_version_mismatch")
        spec = importlib.util.spec_from_file_location(
            "worldguard_portable_auditor", root / "scripts/sync_worldguard_portable_runtime.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        projection = module.audit_projection(root)
        if not projection.get("ok"):
            failures.append("portable_runtime_not_current")
        if package_root is not None and _files(root / "worldguard") != _files(package_root):
            failures.append("package_bytes_mismatch")
        if installed_skill is not None and _files(root / "skills/worldguard") != _files(installed_skill):
            failures.append("installed_skill_bytes_mismatch")
    except (OSError, ValueError, KeyError, SyntaxError, TypeError) as exc:
        failures.append(f"identity_input_invalid:{type(exc).__name__}:{exc}")
    return {
        "ok": not failures,
        "status": "pass" if not failures else "blocked",
        "version": version,
        "failures": failures,
        "portable_projection": projection,
        "installation_checked": installed_skill is not None,
        "package_checked": package_root is not None,
        "claim_boundary": "Exact version and file identity only; no domain execution, installation, Git, or release claim.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--installed-skill", type=Path)
    parser.add_argument("--package-root", type=Path)
    args = parser.parse_args(argv)
    result = audit(args.root, installed_skill=args.installed_skill, package_root=args.package_root)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
