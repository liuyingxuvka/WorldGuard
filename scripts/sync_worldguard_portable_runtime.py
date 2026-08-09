#!/usr/bin/env python3
"""Audit or explicitly refresh WorldGuard's portable runtime projection.

``worldguard/`` is the only author source.  The package under
``skills/worldguard/runtime/worldguard/`` is a derived, portable projection.
The default/read-only operation never writes; synchronization requires the
explicit ``sync`` subcommand and replaces the projection as one staged tree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = "worldguard.portable-runtime-projection.v1"
INVENTORY_SCHEMA_VERSION = "worldguard.portable-runtime-inventory.v1"
SOURCE_RELATIVE_PATH = Path("worldguard")
PROJECTION_RELATIVE_PATH = Path("skills/worldguard/runtime/worldguard")
ALLOWED_SUFFIX_TYPES = {
    ".py": "python",
    ".json": "data",
    ".yaml": "data",
    ".yml": "data",
}
EXCLUDED_DIRECTORY_NAMES = {"__pycache__"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo"}
STAGE_PREFIX = ".worldguard-portable-stage-"
BACKUP_PREFIX = ".worldguard-portable-backup-"
FAILED_PREFIX = ".worldguard-portable-failed-"


class ProjectionSnapshotChangedAfterDetach(RuntimeError):
    """The detached original contains a peer write absent from the frozen snapshot."""


class ProjectionPathRecreatedAfterDetach(RuntimeError):
    """A peer recreated the canonical projection path after the original moved."""


class ProjectionPathOccupiedBeforeActivation(RuntimeError):
    """A peer created the formerly absent canonical path before activation."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _sha256(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = os.lstat(path)
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    return stat.S_ISLNK(metadata.st_mode) or bool(
        reparse_flag and file_attributes & reparse_flag
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _normalized_eol(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _inventory_fingerprint(entries: list[dict[str, Any]], directories: list[str]) -> str:
    return _sha256(
        _canonical_bytes(
            {
                "schema_version": INVENTORY_SCHEMA_VERSION,
                "entries": entries,
                "directories": directories,
            }
        )
    )


def _empty_snapshot(role: str) -> dict[str, Any]:
    return {
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "role": role,
        "exists": False,
        "entries": [],
        "directories": [],
        "member_count": 0,
        "fingerprint": _inventory_fingerprint([], []),
        "unexpected_suffix": [],
        "symlink_entries": [],
        "path_escape_entries": [],
        "unsupported_entries": [],
        "read_errors": [],
    }


def _scan_tree(root: Path, *, role: str) -> dict[str, Any]:
    """Return a deterministic, non-following inventory of one package tree."""

    snapshot = _empty_snapshot(role)
    if not root.exists() and not root.is_symlink():
        return snapshot
    snapshot["exists"] = True
    if _is_link_or_reparse(root):
        snapshot["symlink_entries"] = ["."]
        try:
            resolved_target = root.resolve(strict=True)
            resolved_parent = root.parent.resolve(strict=True)
            if not _is_within(resolved_target, resolved_parent):
                snapshot["path_escape_entries"] = ["."]
        except (OSError, RuntimeError):
            snapshot["read_errors"] = ["root_link_target_unavailable"]
        return snapshot
    if not root.is_dir():
        snapshot["unsupported_entries"] = ["."]
        return snapshot

    try:
        resolved_root = root.resolve(strict=True)
    except (OSError, RuntimeError):
        snapshot["read_errors"] = ["root_resolution_failed"]
        return snapshot

    entries: list[dict[str, Any]] = []
    directories: list[str] = []
    unexpected_suffix: list[str] = []
    symlink_entries: list[str] = []
    path_escape_entries: list[str] = []
    unsupported_entries: list[str] = []
    read_errors: list[str] = []

    def walk(directory: Path, relative_directory: Path) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError:
            label = relative_directory.as_posix() if relative_directory.parts else "."
            read_errors.append(label)
            return
        for child in children:
            relative = relative_directory / child.name
            relative_text = relative.as_posix()
            path = Path(child.path)
            suffix = path.suffix.lower()
            if _is_link_or_reparse(path):
                symlink_entries.append(relative_text)
                try:
                    resolved_target = path.resolve(strict=True)
                    if not _is_within(resolved_target, resolved_root):
                        path_escape_entries.append(relative_text)
                except (OSError, RuntimeError):
                    read_errors.append(relative_text)
                entries.append(
                    {
                        "path": relative_text,
                        "raw_sha256": None,
                        "size": None,
                        "type": "symlink",
                    }
                )
                continue
            try:
                if child.is_dir(follow_symlinks=False):
                    if child.name in EXCLUDED_DIRECTORY_NAMES:
                        continue
                    directories.append(relative_text)
                    walk(path, relative)
                    continue
                if not child.is_file(follow_symlinks=False):
                    unsupported_entries.append(relative_text)
                    entries.append(
                        {
                            "path": relative_text,
                            "raw_sha256": None,
                            "size": None,
                            "type": "unsupported",
                        }
                    )
                    continue
                if suffix in EXCLUDED_SUFFIXES:
                    continue
                resolved_path = path.resolve(strict=True)
                if not _is_within(resolved_path, resolved_root):
                    path_escape_entries.append(relative_text)
                    entries.append(
                        {
                            "path": relative_text,
                            "raw_sha256": None,
                            "size": None,
                            "type": "path_escape",
                        }
                    )
                    continue
                content = path.read_bytes()
            except (OSError, RuntimeError):
                read_errors.append(relative_text)
                entries.append(
                    {
                        "path": relative_text,
                        "raw_sha256": None,
                        "size": None,
                        "type": "unreadable",
                    }
                )
                continue
            member_type = ALLOWED_SUFFIX_TYPES.get(suffix, "unexpected_suffix")
            if member_type == "unexpected_suffix":
                unexpected_suffix.append(relative_text)
            entries.append(
                {
                    "path": relative_text,
                    "raw_sha256": _sha256(content),
                    "size": len(content),
                    "type": member_type,
                }
            )

    walk(root, Path())
    entries.sort(key=lambda row: row["path"])
    directories.sort()
    snapshot.update(
        {
            "entries": entries,
            "directories": directories,
            "member_count": len(entries),
            "fingerprint": _inventory_fingerprint(entries, directories),
            "unexpected_suffix": sorted(unexpected_suffix),
            "symlink_entries": sorted(symlink_entries),
            "path_escape_entries": sorted(path_escape_entries),
            "unsupported_entries": sorted(unsupported_entries),
            "read_errors": sorted(set(read_errors)),
        }
    )
    return snapshot


def _snapshot_invalid(snapshot: dict[str, Any], *, require_exists: bool) -> bool:
    return bool(
        (require_exists and not snapshot["exists"])
        or snapshot["unexpected_suffix"]
        or snapshot["symlink_entries"]
        or snapshot["path_escape_entries"]
        or snapshot["unsupported_entries"]
        or snapshot["read_errors"]
    )


def _entry_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["path"]): row for row in snapshot["entries"]}


def _read_member(root: Path, relative_path: str) -> bytes | None:
    path = root.joinpath(*relative_path.split("/"))
    try:
        if _is_link_or_reparse(path):
            return None
        resolved = path.resolve(strict=True)
        resolved_root = root.resolve(strict=True)
        if not _is_within(resolved, resolved_root):
            return None
        return path.read_bytes()
    except (OSError, RuntimeError):
        return None


def _differences(
    source: dict[str, Any],
    projection: dict[str, Any],
    *,
    source_root: Path,
    projection_root: Path,
) -> dict[str, list[str]]:
    source_entries = _entry_map(source)
    projection_entries = _entry_map(projection)
    source_paths = set(source_entries)
    projection_paths = set(projection_entries)
    missing = sorted(source_paths - projection_paths)
    extra = sorted(projection_paths - source_paths)
    type_drift = sorted(
        path
        for path in source_paths & projection_paths
        if source_entries[path]["type"] != projection_entries[path]["type"]
    )
    changed = sorted(
        path
        for path in source_paths & projection_paths
        if source_entries[path]["raw_sha256"]
        != projection_entries[path]["raw_sha256"]
    )
    eol_only: list[str] = []
    byte_drift: list[str] = []
    for relative_path in changed:
        source_bytes = _read_member(source_root, relative_path)
        projection_bytes = _read_member(projection_root, relative_path)
        if (
            source_bytes is not None
            and projection_bytes is not None
            and _normalized_eol(source_bytes) == _normalized_eol(projection_bytes)
        ):
            eol_only.append(relative_path)
        else:
            byte_drift.append(relative_path)
    data_drift = sorted(
        path
        for path in set(missing) | set(extra) | set(changed) | set(type_drift)
        if source_entries.get(path, projection_entries.get(path, {})).get("type")
        == "data"
        or projection_entries.get(path, {}).get("type") == "data"
    )
    return {
        "missing": missing,
        "extra": extra,
        "byte_drift": sorted(byte_drift),
        "eol_only": sorted(eol_only),
        "type_drift": type_drift,
        "data_drift": data_drift,
        "missing_directories": sorted(
            set(source["directories"]) - set(projection["directories"])
        ),
        "extra_directories": sorted(
            set(projection["directories"]) - set(source["directories"])
        ),
    }


def _failure_rows(
    source: dict[str, Any],
    projection: dict[str, Any],
    differences: dict[str, list[str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def add(code: str, paths: Iterable[str]) -> None:
        values = sorted(set(paths))
        if values:
            rows.append({"code": code, "paths": values})

    if not source["exists"]:
        rows.append({"code": "source_root_missing", "paths": ["."]})
    if not projection["exists"]:
        rows.append({"code": "projection_root_missing", "paths": ["."]})
    for prefix, snapshot in (("source", source), ("projection", projection)):
        add(f"{prefix}_unexpected_suffix", snapshot["unexpected_suffix"])
        add(f"{prefix}_symlink", snapshot["symlink_entries"])
        add(f"{prefix}_path_escape", snapshot["path_escape_entries"])
        add(f"{prefix}_unsupported_entry", snapshot["unsupported_entries"])
        add(f"{prefix}_read_error", snapshot["read_errors"])
    for code in (
        "missing",
        "extra",
        "byte_drift",
        "eol_only",
        "type_drift",
        "data_drift",
        "missing_directories",
        "extra_directories",
    ):
        add(f"projection_{code}", differences[code])
    return sorted(rows, key=lambda row: row["code"])


def audit_projection(repository_root: Path | str) -> dict[str, Any]:
    repository = Path(repository_root).absolute()
    source_root = repository / SOURCE_RELATIVE_PATH
    projection_root = repository / PROJECTION_RELATIVE_PATH
    source = _scan_tree(source_root, role="author_source")
    projection = _scan_tree(projection_root, role="derived_projection")
    differences = _differences(
        source,
        projection,
        source_root=source_root,
        projection_root=projection_root,
    )
    failures = _failure_rows(source, projection, differences)
    ok = not failures and source["member_count"] > 0
    if source["member_count"] == 0 and not any(
        row["code"] == "source_inventory_empty" for row in failures
    ):
        failures.append({"code": "source_inventory_empty", "paths": ["."]})
        failures.sort(key=lambda row: row["code"])
        ok = False
    return {
        "schema_version": SCHEMA_VERSION,
        "action": "check",
        "status": "current" if ok else "blocked",
        "ok": ok,
        "authority": {
            "author_source": SOURCE_RELATIVE_PATH.as_posix(),
            "derived_projection": PROJECTION_RELATIVE_PATH.as_posix(),
            "direction": "author_source_to_derived_projection_only",
        },
        "source_inventory": source,
        "projection_inventory": projection,
        "differences": differences,
        "failures": failures,
        "write_performed": False,
        "transaction_state": "read_only",
        "claim_boundary": (
            "This audit proves raw-byte and inventory parity only for the fixed "
            "WorldGuard author source and portable runtime projection. It does not "
            "prove runtime behavior, installation, Git, tag, or release identity."
        ),
    }


def _safe_transaction_path(path: Path, *, parent: Path, prefixes: Sequence[str]) -> bool:
    try:
        resolved_parent = parent.resolve(strict=True)
        absolute_path = path.absolute()
        absolute_path.parent.resolve(strict=True).relative_to(resolved_parent)
    except (OSError, RuntimeError, ValueError):
        return False
    return absolute_path.parent == parent.absolute() and any(
        absolute_path.name.startswith(prefix) for prefix in prefixes
    )


def _remove_transaction_tree(path: Path, *, parent: Path) -> bool:
    if not path.exists() and not path.is_symlink():
        return True
    if not _safe_transaction_path(
        path,
        parent=parent,
        prefixes=(STAGE_PREFIX, BACKUP_PREFIX, FAILED_PREFIX),
    ):
        return False
    try:
        if _is_link_or_reparse(path):
            path.unlink()
        else:
            shutil.rmtree(path)
    except OSError:
        return False
    return not path.exists() and not path.is_symlink()


def _remove_activated_projection(path: Path, *, parent: Path) -> bool:
    """Remove only the fixed activated projection while restoring prior absence."""

    if path.absolute() != (parent / PROJECTION_RELATIVE_PATH.name).absolute():
        return False
    if path.parent.absolute() != parent.absolute():
        return False
    if not path.exists() and not path.is_symlink():
        return True
    try:
        if _is_link_or_reparse(path):
            path.unlink()
        else:
            shutil.rmtree(path)
    except OSError:
        return False
    return not path.exists() and not path.is_symlink()


def _ancestor_chain_safe(repository: Path, target_parent: Path) -> bool:
    try:
        repository_resolved = repository.resolve(strict=True)
        target_parent.absolute().relative_to(repository.absolute())
    except (OSError, RuntimeError, ValueError):
        return False
    current = repository.absolute()
    if _is_link_or_reparse(current):
        return False
    for part in target_parent.absolute().relative_to(repository.absolute()).parts:
        current = current / part
        if not current.exists() or not current.is_dir() or _is_link_or_reparse(current):
            return False
        try:
            if not _is_within(current.resolve(strict=True), repository_resolved):
                return False
        except (OSError, RuntimeError):
            return False
    return True


def _build_staging_tree(
    *,
    source_root: Path,
    source_snapshot: dict[str, Any],
    staging_root: Path,
) -> None:
    for relative_directory in source_snapshot["directories"]:
        staging_root.joinpath(*relative_directory.split("/")).mkdir(
            parents=True, exist_ok=True
        )
    for row in source_snapshot["entries"]:
        if row["type"] not in {"python", "data"}:
            raise RuntimeError("source_inventory_not_projectable")
        relative_path = str(row["path"])
        source_path = source_root.joinpath(*relative_path.split("/"))
        target_path = staging_root.joinpath(*relative_path.split("/"))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        content = source_path.read_bytes()
        target_path.write_bytes(content)


def _report_from_audit(
    audit: dict[str, Any],
    *,
    status: str,
    write_performed: bool,
    transaction_state: str,
    additional_failures: Iterable[dict[str, Any]] = (),
    recovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = dict(audit)
    report["action"] = "sync"
    report["status"] = status
    report["write_performed"] = write_performed
    report["transaction_state"] = transaction_state
    failures = list(report["failures"]) + list(additional_failures)
    report["failures"] = sorted(failures, key=lambda row: row["code"])
    report["ok"] = status in {"current", "synced"} and not report["failures"]
    if recovery is not None:
        report["recovery"] = recovery
    return report


def _same_tree_snapshot(
    left: dict[str, Any], right: dict[str, Any]
) -> bool:
    """Compare complete inventory state while ignoring only the observer role."""

    return _canonical_bytes(
        {key: value for key, value in left.items() if key != "role"}
    ) == _canonical_bytes(
        {key: value for key, value in right.items() if key != "role"}
    )


def _recovery_payload(
    repository: Path,
    preserved: Iterable[tuple[str, Path]],
) -> dict[str, Any] | None:
    rows: list[dict[str, str]] = []
    for role, path in preserved:
        if not path.exists() and not path.is_symlink():
            continue
        try:
            relative = path.absolute().relative_to(repository.absolute()).as_posix()
        except ValueError:
            continue
        rows.append({"role": role, "path": relative})
    if not rows:
        return None
    return {
        "manual_action_required": True,
        "preserved_paths": rows,
        "claim_boundary": (
            "The transaction preserved every conflicting or unrestored tree at the "
            "listed repository-relative path. It did not merge, overwrite, delete, "
            "or accept peer bytes; a human must choose the disposition."
        ),
    }


def sync_projection(repository_root: Path | str) -> dict[str, Any]:
    """Explicitly project the fixed author tree through a staged directory swap."""

    repository = Path(repository_root).absolute()
    source_root = repository / SOURCE_RELATIVE_PATH
    projection_root = repository / PROJECTION_RELATIVE_PATH
    projection_parent = projection_root.parent
    before = audit_projection(repository)
    source_snapshot = before["source_inventory"]
    if _snapshot_invalid(source_snapshot, require_exists=True) or not source_snapshot[
        "member_count"
    ]:
        return _report_from_audit(
            before,
            status="blocked",
            write_performed=False,
            transaction_state="no_activation",
        )
    if before["ok"]:
        return _report_from_audit(
            before,
            status="current",
            write_performed=False,
            transaction_state="no_activation",
        )
    if not _ancestor_chain_safe(repository, projection_parent):
        return _report_from_audit(
            before,
            status="blocked",
            write_performed=False,
            transaction_state="no_activation",
            additional_failures=(
                {"code": "projection_parent_unsafe", "paths": ["."]},
            ),
        )

    staging_root = Path(
        tempfile.mkdtemp(prefix=STAGE_PREFIX, dir=projection_parent)
    )
    backup_root = projection_parent / f"{BACKUP_PREFIX}{uuid.uuid4().hex}"
    failed_root = projection_parent / f"{FAILED_PREFIX}{uuid.uuid4().hex}"
    original_exists = projection_root.exists() or projection_root.is_symlink()
    original_moved = False
    projection_activated = False
    write_performed = False
    restore_projection_snapshot = before["projection_inventory"]
    staged_snapshot: dict[str, Any] | None = None

    try:
        _build_staging_tree(
            source_root=source_root,
            source_snapshot=source_snapshot,
            staging_root=staging_root,
        )
        staged_snapshot = _scan_tree(staging_root, role="staged_projection")
        if (
            _snapshot_invalid(staged_snapshot, require_exists=True)
            or staged_snapshot["fingerprint"] != source_snapshot["fingerprint"]
        ):
            cleanup_ok = _remove_transaction_tree(
                staging_root, parent=projection_parent
            )
            return _report_from_audit(
                before,
                status="blocked" if cleanup_ok else "cleanup_unconfirmed",
                write_performed=False,
                transaction_state=("no_activation" if cleanup_ok else "cleanup_unconfirmed"),
                additional_failures=(
                    {"code": "staging_projection_mismatch", "paths": ["."]},
                ),
            )

        refreshed_source = _scan_tree(source_root, role="author_source")
        if (
            _snapshot_invalid(refreshed_source, require_exists=True)
            or refreshed_source["fingerprint"] != source_snapshot["fingerprint"]
        ):
            cleanup_ok = _remove_transaction_tree(
                staging_root, parent=projection_parent
            )
            return _report_from_audit(
                before,
                status="blocked" if cleanup_ok else "cleanup_unconfirmed",
                write_performed=False,
                transaction_state=("no_activation" if cleanup_ok else "cleanup_unconfirmed"),
                additional_failures=(
                    {"code": "source_snapshot_changed", "paths": ["."]},
                ),
            )

        refreshed_projection = _scan_tree(
            projection_root, role="derived_projection"
        )
        if _canonical_bytes(refreshed_projection) != _canonical_bytes(
            before["projection_inventory"]
        ):
            cleanup_ok = _remove_transaction_tree(
                staging_root, parent=projection_parent
            )
            return _report_from_audit(
                before,
                status="blocked" if cleanup_ok else "cleanup_unconfirmed",
                write_performed=False,
                transaction_state=("no_activation" if cleanup_ok else "cleanup_unconfirmed"),
                additional_failures=(
                    {"code": "projection_snapshot_changed", "paths": ["."]},
                ),
            )

        if original_exists:
            os.replace(projection_root, backup_root)
            original_moved = True
            write_performed = True
            detached_projection = _scan_tree(
                backup_root, role="derived_projection"
            )
            restore_projection_snapshot = detached_projection
            if _canonical_bytes(detached_projection) != _canonical_bytes(
                before["projection_inventory"]
            ):
                raise ProjectionSnapshotChangedAfterDetach(
                    "projection_snapshot_changed_after_detach"
                )
        if projection_root.exists() or projection_root.is_symlink():
            if original_moved:
                raise ProjectionPathRecreatedAfterDetach(
                    "projection_path_recreated_after_detach"
                )
            raise ProjectionPathOccupiedBeforeActivation(
                "projection_path_occupied_before_activation"
            )
        try:
            os.replace(staging_root, projection_root)
        except OSError as activation_error:
            if original_moved and (
                projection_root.exists() or projection_root.is_symlink()
            ):
                raise ProjectionPathRecreatedAfterDetach(
                    "projection_path_recreated_after_detach"
                ) from activation_error
            if not original_exists and (
                projection_root.exists() or projection_root.is_symlink()
            ):
                raise ProjectionPathOccupiedBeforeActivation(
                    "projection_path_occupied_before_activation"
                ) from activation_error
            raise
        projection_activated = True
        write_performed = True

        after = audit_projection(repository)
        if not after["ok"]:
            raise RuntimeError("post_sync_validation_failed")

        if original_moved and not _remove_transaction_tree(
            backup_root, parent=projection_parent
        ):
            return _report_from_audit(
                after,
                status="cleanup_unconfirmed",
                write_performed=True,
                transaction_state="cleanup_unconfirmed",
                additional_failures=(
                    {"code": "backup_cleanup_failed", "paths": ["."]},
                ),
            )
        return _report_from_audit(
            after,
            status="synced",
            write_performed=True,
            transaction_state="committed",
        )
    except Exception as exc:
        restore_ok = True
        preserve_failed_root = False
        preserve_backup_root = False
        conflict_code = ""
        canonical_recovery_role = ""
        try:
            if original_moved:
                if projection_activated:
                    if projection_root.exists() or projection_root.is_symlink():
                        os.replace(projection_root, failed_root)
                        projection_activated = False
                        failed_snapshot = _scan_tree(
                            failed_root, role="failed_projection"
                        )
                        if staged_snapshot is None or not _same_tree_snapshot(
                            failed_snapshot, staged_snapshot
                        ):
                            preserve_failed_root = True
                            restore_ok = False
                            conflict_code = (
                                "projection_path_changed_after_activation"
                            )
                    else:
                        projection_activated = False
                if projection_root.exists() or projection_root.is_symlink():
                    preserve_backup_root = True
                    restore_ok = False
                    canonical_recovery_role = (
                        "peer_recreated_canonical_projection"
                    )
                    if not conflict_code:
                        conflict_code = (
                            "projection_path_recreated_after_detach"
                        )
                else:
                    os.replace(backup_root, projection_root)
                    original_moved = False
                    if conflict_code:
                        canonical_recovery_role = (
                            "restored_original_projection"
                        )
            elif not original_exists and projection_activated:
                if projection_root.exists() or projection_root.is_symlink():
                    os.replace(projection_root, failed_root)
                    projection_activated = False
                    failed_snapshot = _scan_tree(
                        failed_root, role="failed_projection"
                    )
                    if staged_snapshot is None or not _same_tree_snapshot(
                        failed_snapshot, staged_snapshot
                    ):
                        preserve_failed_root = True
                        restore_ok = False
                        conflict_code = "projection_path_changed_after_activation"
                else:
                    projection_activated = False
            elif not original_exists and (
                projection_root.exists() or projection_root.is_symlink()
            ):
                restore_ok = False
                canonical_recovery_role = "peer_created_canonical_projection"
                conflict_code = "projection_path_occupied_before_activation"
        except OSError:
            restore_ok = False
            preserve_backup_root = original_moved and (
                backup_root.exists() or backup_root.is_symlink()
            )
            preserve_failed_root = (
                failed_root.exists() or failed_root.is_symlink()
            )
            if not conflict_code:
                conflict_code = "projection_rollback_conflict_unresolved"

        cleanup_candidates = [staging_root]
        if not preserve_failed_root:
            cleanup_candidates.append(failed_root)
        if not preserve_backup_root and not original_moved:
            cleanup_candidates.append(backup_root)
        for temporary in cleanup_candidates:
            if temporary.exists() or temporary.is_symlink():
                restore_ok = (
                    _remove_transaction_tree(temporary, parent=projection_parent)
                    and restore_ok
                )
        restored = audit_projection(repository)
        if _canonical_bytes(restore_projection_snapshot) != _canonical_bytes(
            restored["projection_inventory"]
        ):
            restore_ok = False
        failure_code = conflict_code or (
            "projection_snapshot_changed_after_detach"
            if isinstance(exc, ProjectionSnapshotChangedAfterDetach)
            else (
                "projection_path_recreated_after_detach"
                if isinstance(exc, ProjectionPathRecreatedAfterDetach)
                else (
                    "projection_path_occupied_before_activation"
                    if isinstance(exc, ProjectionPathOccupiedBeforeActivation)
                    else f"projection_sync_failed:{type(exc).__name__}"
                )
            )
        )
        recovery_rows: list[tuple[str, Path]] = []
        if canonical_recovery_role:
            recovery_rows.append((canonical_recovery_role, projection_root))
        if backup_root.exists() or backup_root.is_symlink():
            recovery_rows.append(("original_projection_backup", backup_root))
        if failed_root.exists() or failed_root.is_symlink():
            recovery_rows.append(("peer_changed_failed_projection", failed_root))
        if staging_root.exists() or staging_root.is_symlink():
            recovery_rows.append(("staging_cleanup_unconfirmed", staging_root))
        return _report_from_audit(
            restored,
            status="blocked" if restore_ok else "cleanup_unconfirmed",
            write_performed=write_performed,
            transaction_state=("rolled_back_clean" if restore_ok else "cleanup_unconfirmed"),
            additional_failures=(
                {
                    "code": failure_code,
                    "paths": ["."],
                },
            ),
            recovery=_recovery_payload(repository, recovery_rows),
        )


def _emit(report: dict[str, Any]) -> None:
    sys.stdout.buffer.write(_canonical_bytes(report) + b"\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit or explicitly refresh the one-way WorldGuard portable runtime "
            "projection."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("check", "sync"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument(
            "--repository-root",
            type=Path,
            default=Path.cwd(),
            help="WorldGuard repository root (default: current directory).",
        )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = (
        audit_projection(args.repository_root)
        if args.command == "check"
        else sync_projection(args.repository_root)
    )
    _emit(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
