from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sync_worldguard_portable_runtime.py"
SPEC = importlib.util.spec_from_file_location(
    "worldguard_portable_runtime_projection", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
projection = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(projection)


def _roots(repository: Path) -> tuple[Path, Path]:
    source = repository / "worldguard"
    bundled = repository / "skills" / "worldguard" / "runtime" / "worldguard"
    source.mkdir(parents=True)
    bundled.mkdir(parents=True)
    return source, bundled


def _write_current_pair(repository: Path) -> tuple[Path, Path]:
    source, bundled = _roots(repository)
    files = {
        "__init__.py": b'__version__ = "1.2.3"\n',
        "guards/event.py": b"def run():\n    return 'PASS'\n",
        "examples/case.yaml": b"claim: current\nterminal: PASS\n",
        "examples/schema.json": b'{"schema":"current"}\n',
    }
    for relative, content in files.items():
        source_path = source / relative
        bundled_path = bundled / relative
        source_path.parent.mkdir(parents=True, exist_ok=True)
        bundled_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_bytes(content)
        bundled_path.write_bytes(content)
    return source, bundled


def _canonical(report: dict[str, object]) -> bytes:
    return json.dumps(
        report,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def test_read_only_check_is_stable_complete_and_ignores_only_declared_cache(
    tmp_path: Path,
) -> None:
    source, bundled = _write_current_pair(tmp_path)
    (source / "__pycache__").mkdir()
    (source / "__pycache__/ignored.pyc").write_bytes(b"source cache")
    (bundled / "__pycache__").mkdir()
    (bundled / "__pycache__/ignored.pyc").write_bytes(b"bundle cache")
    (source / "loose.pyo").write_bytes(b"ignored source bytecode")
    (bundled / "loose.pyo").write_bytes(b"ignored bundle bytecode")

    first = projection.audit_projection(tmp_path)
    second = projection.audit_projection(tmp_path)

    assert first["ok"] is True
    assert first["status"] == "current"
    assert first["write_performed"] is False
    assert first["transaction_state"] == "read_only"
    assert _canonical(first) == _canonical(second)
    source_rows = first["source_inventory"]["entries"]
    assert [row["path"] for row in source_rows] == [
        "__init__.py",
        "examples/case.yaml",
        "examples/schema.json",
        "guards/event.py",
    ]
    assert {row["type"] for row in source_rows} == {"python", "data"}
    assert all(str(row["raw_sha256"]).startswith("sha256:") for row in source_rows)
    assert all("__pycache__" not in row["path"] for row in source_rows)


def test_check_exposes_missing_extra_raw_eol_data_and_unexpected_suffix(
    tmp_path: Path,
) -> None:
    source, bundled = _write_current_pair(tmp_path)
    (bundled / "__init__.py").write_bytes(b'__version__ = "1.2.3"\r\n')
    (bundled / "guards/event.py").write_bytes(b"def run():\n    return 'FAIL'\n")
    (bundled / "examples/case.yaml").unlink()
    (bundled / "examples/extra.json").write_bytes(b"{}\n")
    (bundled / "rogue.txt").write_text("not package data", encoding="utf-8")

    report = projection.audit_projection(tmp_path)
    failures = {row["code"]: row["paths"] for row in report["failures"]}

    assert report["ok"] is False
    assert report["differences"]["eol_only"] == ["__init__.py"]
    assert report["differences"]["byte_drift"] == ["guards/event.py"]
    assert report["differences"]["missing"] == ["examples/case.yaml"]
    assert report["differences"]["extra"] == [
        "examples/extra.json",
        "rogue.txt",
    ]
    assert report["differences"]["data_drift"] == [
        "examples/case.yaml",
        "examples/extra.json",
    ]
    assert failures["projection_eol_only"] == ["__init__.py"]
    assert failures["projection_byte_drift"] == ["guards/event.py"]
    assert failures["projection_unexpected_suffix"] == ["rogue.txt"]


def test_explicit_sync_replaces_projection_from_source_without_touching_source(
    tmp_path: Path,
) -> None:
    source, bundled = _write_current_pair(tmp_path)
    source_bytes = {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    }
    (bundled / "guards/event.py").write_text("stale\n", encoding="utf-8")
    (bundled / "examples/case.yaml").unlink()
    (bundled / "extra.py").write_text("extra = True\n", encoding="utf-8")
    (bundled / "rogue.txt").write_text("replace this invalid member\n", encoding="utf-8")

    result = projection.sync_projection(tmp_path)

    assert result["ok"] is True
    assert result["status"] == "synced"
    assert result["transaction_state"] == "committed"
    assert result["write_performed"] is True
    assert projection.audit_projection(tmp_path)["ok"] is True
    assert {
        path.relative_to(source).as_posix(): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file()
    } == source_bytes
    assert not (bundled / "extra.py").exists()
    assert not (bundled / "rogue.txt").exists()
    assert (bundled / "examples/case.yaml").read_bytes() == source_bytes[
        "examples/case.yaml"
    ]


def test_source_unexpected_suffix_blocks_sync_before_any_projection_write(
    tmp_path: Path,
) -> None:
    source, bundled = _write_current_pair(tmp_path)
    (source / "notes.txt").write_text("not governed package data", encoding="utf-8")
    before = (bundled / "__init__.py").read_bytes()

    result = projection.sync_projection(tmp_path)

    assert result["ok"] is False
    assert result["transaction_state"] == "no_activation"
    assert result["write_performed"] is False
    assert (bundled / "__init__.py").read_bytes() == before
    assert any(
        row["code"] == "source_unexpected_suffix" for row in result["failures"]
    )


def test_source_snapshot_change_after_staging_blocks_before_projection_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, bundled = _write_current_pair(tmp_path)
    (bundled / "__init__.py").write_text("stale\n", encoding="utf-8")
    before = (bundled / "__init__.py").read_bytes()
    original_scan = projection._scan_tree
    source_scans = 0

    def racing_scan(root: Path, *, role: str) -> dict[str, object]:
        nonlocal source_scans
        if role == "author_source":
            source_scans += 1
            if source_scans == 2:
                (source / "__init__.py").write_text(
                    '__version__ = "changed"\n', encoding="utf-8"
                )
        return original_scan(root, role=role)

    monkeypatch.setattr(projection, "_scan_tree", racing_scan)
    result = projection.sync_projection(tmp_path)

    assert result["ok"] is False
    assert result["transaction_state"] == "no_activation"
    assert result["write_performed"] is False
    assert (bundled / "__init__.py").read_bytes() == before
    assert any(row["code"] == "source_snapshot_changed" for row in result["failures"])


def test_projection_snapshot_change_after_staging_preserves_peer_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, bundled = _write_current_pair(tmp_path)
    (bundled / "__init__.py").write_text("stale\n", encoding="utf-8")
    original_scan = projection._scan_tree
    projection_scans = 0

    def peer_write_scan(root: Path, *, role: str) -> dict[str, object]:
        nonlocal projection_scans
        if role == "derived_projection":
            projection_scans += 1
            if projection_scans == 2:
                (bundled / "peer.py").write_text("peer = True\n", encoding="utf-8")
        return original_scan(root, role=role)

    monkeypatch.setattr(projection, "_scan_tree", peer_write_scan)
    result = projection.sync_projection(tmp_path)

    assert result["ok"] is False
    assert result["transaction_state"] == "no_activation"
    assert result["write_performed"] is False
    assert (bundled / "peer.py").read_text(encoding="utf-8") == "peer = True\n"
    assert any(
        row["code"] == "projection_snapshot_changed" for row in result["failures"]
    )


def test_projection_peer_write_at_detach_is_refrozen_restored_and_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, bundled = _write_current_pair(tmp_path)
    (bundled / "__init__.py").write_text("stale\n", encoding="utf-8")
    real_replace = projection.os.replace
    injected = False

    def peer_write_at_detach(
        source: os.PathLike[str], target: os.PathLike[str]
    ) -> None:
        nonlocal injected
        source_path = Path(source)
        target_path = Path(target)
        if (
            not injected
            and source_path == bundled
            and target_path.name.startswith(projection.BACKUP_PREFIX)
        ):
            (bundled / "peer.py").write_text("peer = True\n", encoding="utf-8")
            injected = True
        real_replace(source, target)

    monkeypatch.setattr(projection.os, "replace", peer_write_at_detach)
    result = projection.sync_projection(tmp_path)

    assert injected is True
    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["transaction_state"] == "rolled_back_clean"
    assert result["write_performed"] is True
    assert (bundled / "peer.py").read_text(encoding="utf-8") == "peer = True\n"
    assert any(
        row["code"] == "projection_snapshot_changed_after_detach"
        for row in result["failures"]
    )
    assert not any(
        str(row["code"]).startswith("projection_sync_failed:")
        for row in result["failures"]
    )
    assert not list(bundled.parent.glob(".worldguard-portable-*-*"))


def test_projection_path_recreated_after_detach_preserves_peer_and_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, bundled = _write_current_pair(tmp_path)
    (bundled / "__init__.py").write_text("stale\n", encoding="utf-8")
    original_bytes = (bundled / "__init__.py").read_bytes()
    real_replace = projection.os.replace
    injected = False

    def recreate_canonical_after_detach(
        source: os.PathLike[str], target: os.PathLike[str]
    ) -> None:
        nonlocal injected
        source_path = Path(source)
        target_path = Path(target)
        real_replace(source, target)
        if (
            not injected
            and source_path == bundled
            and target_path.name.startswith(projection.BACKUP_PREFIX)
        ):
            bundled.mkdir(parents=True)
            (bundled / "peer.py").write_bytes(b"peer after detach\n")
            injected = True

    monkeypatch.setattr(projection.os, "replace", recreate_canonical_after_detach)
    result = projection.sync_projection(tmp_path)

    assert injected is True
    assert result["ok"] is False
    assert result["status"] == "cleanup_unconfirmed"
    assert result["transaction_state"] == "cleanup_unconfirmed"
    assert result["write_performed"] is True
    assert (bundled / "peer.py").read_bytes() == b"peer after detach\n"
    assert not (bundled / "__init__.py").exists()
    assert any(
        row["code"] == "projection_path_recreated_after_detach"
        for row in result["failures"]
    )
    recovery = result["recovery"]
    assert recovery["manual_action_required"] is True
    recovery_rows = {row["role"]: row["path"] for row in recovery["preserved_paths"]}
    assert recovery_rows["peer_recreated_canonical_projection"] == (
        "skills/worldguard/runtime/worldguard"
    )
    backup = tmp_path.joinpath(
        *recovery_rows["original_projection_backup"].split("/")
    )
    assert backup.name.startswith(projection.BACKUP_PREFIX)
    assert (backup / "__init__.py").read_bytes() == original_bytes
    assert not list(bundled.parent.glob(f"{projection.STAGE_PREFIX}*"))
    assert not list(bundled.parent.glob(f"{projection.FAILED_PREFIX}*"))


def test_peer_write_after_activation_preserves_conflict_and_restores_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, bundled = _write_current_pair(tmp_path)
    (bundled / "__init__.py").write_text("stale\n", encoding="utf-8")
    original_tree = {
        path.relative_to(bundled).as_posix(): path.read_bytes()
        for path in bundled.rglob("*")
        if path.is_file()
    }
    real_replace = projection.os.replace
    injected = False

    def write_after_activation(
        source: os.PathLike[str], target: os.PathLike[str]
    ) -> None:
        nonlocal injected
        source_path = Path(source)
        target_path = Path(target)
        real_replace(source, target)
        if (
            not injected
            and source_path.name.startswith(projection.STAGE_PREFIX)
            and target_path == bundled
        ):
            (bundled / "peer.py").write_bytes(b"peer after activation\n")
            injected = True

    monkeypatch.setattr(projection.os, "replace", write_after_activation)
    result = projection.sync_projection(tmp_path)

    assert injected is True
    assert result["ok"] is False
    assert result["status"] == "cleanup_unconfirmed"
    assert result["transaction_state"] == "cleanup_unconfirmed"
    assert result["write_performed"] is True
    assert {
        path.relative_to(bundled).as_posix(): path.read_bytes()
        for path in bundled.rglob("*")
        if path.is_file()
    } == original_tree
    assert any(
        row["code"] == "projection_path_changed_after_activation"
        for row in result["failures"]
    )
    recovery = result["recovery"]
    assert recovery["manual_action_required"] is True
    recovery_rows = {row["role"]: row["path"] for row in recovery["preserved_paths"]}
    assert recovery_rows["restored_original_projection"] == (
        "skills/worldguard/runtime/worldguard"
    )
    conflict = tmp_path.joinpath(
        *recovery_rows["peer_changed_failed_projection"].split("/")
    )
    assert conflict.name.startswith(projection.FAILED_PREFIX)
    assert (conflict / "peer.py").read_bytes() == b"peer after activation\n"
    assert not (bundled / "peer.py").exists()
    assert not list(bundled.parent.glob(f"{projection.STAGE_PREFIX}*"))
    assert not list(bundled.parent.glob(f"{projection.BACKUP_PREFIX}*"))


def test_failed_directory_activation_restores_original_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, bundled = _write_current_pair(tmp_path)
    (bundled / "__init__.py").write_text("stale\n", encoding="utf-8")
    before = {
        path.relative_to(bundled).as_posix(): path.read_bytes()
        for path in bundled.rglob("*")
        if path.is_file()
    }
    real_replace = projection.os.replace
    replace_calls = 0

    def fail_second_replace(source: os.PathLike[str], target: os.PathLike[str]) -> None:
        nonlocal replace_calls
        replace_calls += 1
        if replace_calls == 2:
            raise OSError("injected activation failure")
        real_replace(source, target)

    monkeypatch.setattr(projection.os, "replace", fail_second_replace)
    result = projection.sync_projection(tmp_path)

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["transaction_state"] == "rolled_back_clean"
    assert result["write_performed"] is True
    assert {
        path.relative_to(bundled).as_posix(): path.read_bytes()
        for path in bundled.rglob("*")
        if path.is_file()
    } == before
    assert not list(bundled.parent.glob(".worldguard-portable-*-*"))


def test_post_activation_validation_failure_restores_original_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, bundled = _write_current_pair(tmp_path)
    (bundled / "__init__.py").write_text("stale\n", encoding="utf-8")
    before = {
        path.relative_to(bundled).as_posix(): path.read_bytes()
        for path in bundled.rglob("*")
        if path.is_file()
    }
    original_scan = projection._scan_tree
    projection_scans = 0

    def fail_post_activation_scan(root: Path, *, role: str) -> dict[str, object]:
        nonlocal projection_scans
        observed = original_scan(root, role=role)
        if role == "derived_projection":
            projection_scans += 1
            if projection_scans == 4:
                observed = dict(observed)
                observed["read_errors"] = ["injected-post-activation-error"]
        return observed

    monkeypatch.setattr(projection, "_scan_tree", fail_post_activation_scan)
    result = projection.sync_projection(tmp_path)

    assert result["ok"] is False
    assert result["transaction_state"] == "rolled_back_clean"
    assert {
        path.relative_to(bundled).as_posix(): path.read_bytes()
        for path in bundled.rglob("*")
        if path.is_file()
    } == before
    assert not list(bundled.parent.glob(".worldguard-portable-*-*"))


def test_excluded_bytecode_name_cannot_hide_link_like_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, _ = _write_current_pair(tmp_path)
    masked = source / "masked.pyc"
    masked.write_bytes(b"not trusted bytecode")
    real_link_check = projection._is_link_or_reparse

    def fake_link_check(path: Path) -> bool:
        return path == masked or real_link_check(path)

    monkeypatch.setattr(projection, "_is_link_or_reparse", fake_link_check)
    report = projection.audit_projection(tmp_path)

    assert report["ok"] is False
    assert any(
        row["code"] == "source_symlink" and row["paths"] == ["masked.pyc"]
        for row in report["failures"]
    )


def test_external_symlink_is_visible_as_symlink_and_path_escape(tmp_path: Path) -> None:
    source, _ = _write_current_pair(tmp_path)
    outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
    outside.write_text("outside = True\n", encoding="utf-8")
    link = source / "escape.py"
    try:
        link.symlink_to(outside)
    except OSError as exc:
        outside.unlink(missing_ok=True)
        pytest.skip(f"symlink unavailable: {type(exc).__name__}")
    try:
        report = projection.audit_projection(tmp_path)
        failures = {row["code"]: row["paths"] for row in report["failures"]}
        assert report["ok"] is False
        assert failures["source_symlink"] == ["escape.py"]
        assert failures["source_path_escape"] == ["escape.py"]
        row = next(
            row
            for row in report["source_inventory"]["entries"]
            if row["path"] == "escape.py"
        )
        assert row == {
            "path": "escape.py",
            "raw_sha256": None,
            "size": None,
            "type": "symlink",
        }
    finally:
        link.unlink(missing_ok=True)
        outside.unlink(missing_ok=True)


def test_cli_requires_directional_subcommand_and_emits_stable_json(
    tmp_path: Path,
) -> None:
    _write_current_pair(tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "check",
            "--repository-root",
            str(tmp_path),
        ],
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    assert completed.stdout.endswith(b"\n")
    report = json.loads(completed.stdout)
    assert report["action"] == "check"
    assert report["authority"]["direction"] == (
        "author_source_to_derived_projection_only"
    )
    assert completed.stdout == _canonical(report) + b"\n"

    no_command = subprocess.run(
        [sys.executable, str(SCRIPT), "--repository-root", str(tmp_path)],
        capture_output=True,
        check=False,
    )
    assert no_command.returncode != 0
    assert no_command.stdout == b""
