from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
from datetime import date, datetime
from typing import Any


def load_mapping(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        try:
            import yaml
        except ImportError as exc:
            raise ValueError(f"{path}: reading YAML needs PyYAML (python -m pip install PyYAML); JSON input does not") from exc
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise ValueError(f"{path} is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} did not contain a mapping")
    return data


def json_default(value: Any) -> str:
    """Preserve YAML's native ISO date values in JSON reports and input identities."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, default=json_default)


def input_digests(paths, base_dir):
    """Sorted content hashes of raw files, named relative to the contract folder."""
    rows = {Path(os.path.relpath(path, base_dir)).as_posix(): hashlib.sha256(Path(path).read_bytes()).hexdigest()
            for path in paths}
    return [{'path': name, 'sha256': rows[name]} for name in sorted(rows)]
