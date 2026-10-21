from pathlib import Path

from scripts.sync_worldguard_portable_runtime import differences, sync


def test_repository_runtime_copy_is_exact() -> None:
    assert differences() == []


def test_sync_replaces_a_drifted_copy_and_skips_bytecode(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "pkg" / "__pycache__").mkdir(parents=True)
    (source / "pkg" / "a.py").write_text("a = 1\n", encoding="utf-8")
    (source / "pkg" / "__pycache__" / "a.cpython-311.pyc").write_bytes(b"cache")
    sync(source, target)
    assert differences(source, target) == []
    assert not (target / "pkg" / "__pycache__").exists()

    (target / "pkg" / "a.py").write_text("a = 2\n", encoding="utf-8")
    (target / "extra.py").write_text("", encoding="utf-8")
    (source / "pkg" / "b.py").write_text("b = 1\n", encoding="utf-8")
    assert differences(source, target) == ["missing: pkg/b.py", "extra: extra.py", "differs: pkg/a.py"]

    sync(source, target)
    assert differences(source, target) == []
