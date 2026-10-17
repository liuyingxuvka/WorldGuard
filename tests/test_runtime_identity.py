"""File-identity regressions independent of any author framework."""
from pathlib import Path
import importlib.util
import shutil

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("runtime_identity", ROOT / "scripts/check_runtime_identity.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def test_current_source_and_plain_installation_are_read_only(tmp_path):
    installed = tmp_path / "worldguard"
    shutil.copytree(ROOT / "skills/worldguard", installed, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    before = AUDIT._files(installed)
    result = AUDIT.audit(ROOT, installed_skill=installed)
    assert result["ok"], result["failures"]
    assert before == AUDIT._files(installed)
    (installed / "SKILL.md").write_text("foreign version")
    assert "installed_skill_bytes_mismatch" in AUDIT.audit(ROOT, installed_skill=installed)["failures"]


def test_package_byte_drift_is_visible(tmp_path):
    package = tmp_path / "worldguard"
    shutil.copytree(ROOT / "worldguard", package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    assert AUDIT.audit(ROOT, package_root=package)["ok"]
    (package / "status.py").write_text("# altered implementation\n")
    assert "package_bytes_mismatch" in AUDIT.audit(ROOT, package_root=package)["failures"]


def test_missing_or_symlink_installation_blocks(tmp_path):
    assert not AUDIT.audit(ROOT, installed_skill=tmp_path / "missing")["ok"]
    link = tmp_path / "link"
    link.symlink_to(ROOT / "skills/worldguard", target_is_directory=True)
    assert not AUDIT.audit(ROOT, installed_skill=link)["ok"]
