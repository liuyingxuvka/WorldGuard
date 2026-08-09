import argparse
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = (SKILL_ROOT / "runtime").resolve()
RUNTIME_PACKAGE_ROOT = (RUNTIME_ROOT / "worldguard").resolve()


def _module_origin(module: ModuleType, module_name: str) -> Path:
    origin = getattr(module, "__file__", None)
    if not isinstance(origin, str) or not origin:
        raise RuntimeError(
            f"portable WorldGuard runtime module has no file origin: {module_name}"
        )
    return Path(origin).resolve()


def _require_bundled_origin(module: ModuleType, module_name: str) -> None:
    origin = _module_origin(module, module_name)
    try:
        origin.relative_to(RUNTIME_PACKAGE_ROOT)
    except ValueError as exc:
        raise RuntimeError(
            "portable WorldGuard runtime import escaped bundled root: "
            f"{module_name} -> {origin}"
        ) from exc


def _load_portable_cli_main() -> Callable[[list[str] | None], int]:
    required_files = (
        RUNTIME_PACKAGE_ROOT / "__init__.py",
        RUNTIME_PACKAGE_ROOT / "cli.py",
    )
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise RuntimeError(
            "portable WorldGuard runtime is incomplete; missing: "
            + ", ".join(missing)
        )

    # Select this skill's portable runtime explicitly. A preloaded external
    # package is rejected below; it is never removed and retried as a fallback.
    sys.path.insert(0, str(RUNTIME_ROOT))
    package = importlib.import_module("worldguard")
    _require_bundled_origin(package, "worldguard")
    cli_module = importlib.import_module("worldguard.cli")
    _require_bundled_origin(cli_module, "worldguard.cli")

    for module_name, module in tuple(sys.modules.items()):
        if (
            module is not None
            and (module_name == "worldguard" or module_name.startswith("worldguard."))
        ):
            _require_bundled_origin(module, module_name)

    cli_main = getattr(cli_module, "main", None)
    if not callable(cli_main):
        raise RuntimeError("portable WorldGuard runtime has no callable cli.main")
    return cli_main


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--example", choices=["fuel_cell"], default="")
    parser.add_argument("--contract", default="")
    parser.add_argument("--mesh", default="")
    args = parser.parse_args()

    try:
        if args.example == "fuel_cell":
            cli_arguments = ["check", "--example", "fuel_cell"]
        elif args.contract:
            cli_arguments = ["check", "--contract", args.contract]
        elif args.mesh:
            cli_arguments = ["mesh-check", "--mesh", args.mesh]
        else:
            parser.error("provide --example fuel_cell, --contract <path>, or --mesh <path>")
            return 2

        return _load_portable_cli_main()(cli_arguments)
    except Exception as exc:  # pragma: no cover - helper script surface
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
