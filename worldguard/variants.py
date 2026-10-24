"""Finite, in-memory edits to a declared world; paths never refer to files."""
from __future__ import annotations

from copy import deepcopy
import re

_PART = re.compile(r"([^.[\]]+)((?:\[[^\[\]]+\])*)")


def validate_variants(rows):
    if not isinstance(rows, list):
        raise ValueError("variants must be a list")
    seen = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"variant {index} must be a mapping")
        identity = row.get("id")
        unknown = sorted(map(str, set(row) - {"id", "expect", "code", "set", "remove", "add"}))
        if unknown:
            raise ValueError(f"variant {identity!r}: unknown fields {unknown}")
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ValueError(f"variant {identity!r}: id must be nonempty and unique")
        seen.add(identity)
        if not isinstance(row.get("expect", "FAIL"), str) or row.get("expect", "FAIL") not in {"FAIL", "GAP", "BOUNDARY_EXCEEDED"}:
            raise ValueError(f"variant {identity}: unknown expect {row['expect']!r}")
        if "code" in row and (not isinstance(row["code"], str) or not row["code"]):
            raise ValueError(f"variant {identity}: code must be a nonempty string")
        for action in ("set", "add"):
            if not isinstance(row.get(action, {}), dict):
                raise ValueError(f"variant {identity}: {action} must map paths to values")
        if not isinstance(row.get("remove", []), list):
            raise ValueError(f"variant {identity}: remove must be a list of paths")


def _tokens(path):
    if not isinstance(path, str) or not path:
        raise ValueError("a path must be a nonempty string")
    result = []
    position = 0
    while position < len(path):
        match = _PART.match(path, position)
        if not match:
            raise ValueError(f"invalid path {path!r}")
        result.append((False, match[1]))
        result.extend((True, key) for key in re.findall(r"\[([^\[\]]+)\]", match[2]))
        position = match.end()
        if position < len(path):
            if path[position] != "." or position + 1 == len(path):
                raise ValueError(f"invalid path {path!r}")
            position += 1
    return result


def _key(container, token):
    selector, value = token
    if not selector:
        if not isinstance(container, dict) or value not in container:
            raise ValueError(f"path field {value!r} is absent")
        return value
    if not isinstance(container, list):
        raise ValueError(f"path selector [{value}] needs a list")
    if value.isdecimal():
        index = int(value)
        if index >= len(container):
            raise ValueError(f"path index [{value}] is absent")
        return index
    matches = [index for index, row in enumerate(container) if isinstance(row, dict) and
        any((name == "id" or name.endswith("_id")) and str(identity) == value for name, identity in row.items())]
    if len(matches) != 1:
        raise ValueError(f"path selector [{value}] must name exactly one item")
    return matches[0]


def _select_path(data, path):
    tokens = _tokens(path)
    current = data
    for token in tokens[:-1]:
        current = current[_key(current, token)]
    return current, _key(current, tokens[-1])


def apply_variant(data, variant):
    """Return an independent world; invalid paths fail with the variant's id."""
    result = deepcopy(data)
    result.pop("variants", None)
    try:
        for path, value in variant.get("set", {}).items():
            parent, key = _select_path(result, path)
            parent[key] = deepcopy(value)
        for path in variant.get("remove", []):
            parent, key = _select_path(result, path)
            del parent[key]
        for path, values in variant.get("add", {}).items():
            parent, key = _select_path(result, path)
            if not isinstance(parent[key], list) or not isinstance(values, list):
                raise ValueError(f"add path {path!r} and its value must be lists")
            parent[key].extend(deepcopy(values))
    except (TypeError, KeyError, IndexError, ValueError) as exc:
        raise ValueError(f"variant {variant['id']}: {exc}") from exc
    return result
