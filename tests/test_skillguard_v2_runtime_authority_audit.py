from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_guard_simulation_readiness.py"
PRIMARY_ROOT = ROOT / "skills" / "worldguard"
DEPTH_BRIDGE = PRIMARY_ROOT / ".skillguard/checks/emit_native_depth_evidence.py"
BRIDGE_PATHS = (DEPTH_BRIDGE,)
GUARD_MODEL_CHECK = PRIMARY_ROOT / ".skillguard/checks/check_guard_model_contract.py"


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("guard_v2_authority_audit_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _projection_report(
    *,
    ok: bool = True,
    differences: dict[str, list[str]] | None = None,
    failures: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    projection_differences = {
        "missing": [],
        "extra": [],
        "byte_drift": [],
        "eol_only": [],
        "type_drift": [],
        "data_drift": [],
        "missing_directories": [],
        "extra_directories": [],
    }
    projection_differences.update(differences or {})
    return {
        "schema_version": "worldguard.portable-runtime-projection.v1",
        "action": "check",
        "status": "current" if ok else "blocked",
        "ok": ok,
        "authority": {
            "author_source": "worldguard",
            "derived_projection": "skills/worldguard/runtime/worldguard",
            "direction": "author_source_to_derived_projection_only",
        },
        "source_inventory": {
            "member_count": 2,
            "fingerprint": "sha256:source",
        },
        "projection_inventory": {
            "member_count": 2,
            "fingerprint": "sha256:projection",
        },
        "differences": projection_differences,
        "failures": failures or [],
        "write_performed": False,
        "transaction_state": "read_only",
    }


def _patch_projection_report(
    monkeypatch: pytest.MonkeyPatch,
    audit,
    report: dict[str, object] | None = None,
) -> None:
    monkeypatch.setattr(
        audit,
        "_canonical_projection_audit",
        lambda: report or _projection_report(),
    )


def _write_current_authority(root: Path, target_skill_id: str) -> None:
    control = root / ".skillguard"
    control.mkdir(parents=True)
    (root / "SKILL.md").write_text("current prompt\n", encoding="utf-8")
    for name in ("contract-source.json", "compiled-contract.json", "check-manifest.json"):
        (control / name).write_text(json.dumps({"name": name}), encoding="utf-8")
    (control / "retirement-completion-receipt.json").write_text(
        json.dumps(
            {
                "schema_version": "worldguard.skillguard-retirement-completion.current",
                "status": "retired",
                "target_skill_id": target_skill_id,
                "receipt_id": "retirement-current",
                "source_residual_scan": {"residual_count": 0},
                "installed_residual_scan": {"residual_count": 0},
                "installation_currentness": {"status": "passed"},
            }
        ),
        encoding="utf-8",
    )


def _consumer_contract() -> dict:
    return {
        "skill_id": "worldguard",
        "maintenance_unit_id": "unit:worldguard",
        "member_skill_ids": ["worldguard"],
        "contract_hash": "test-contract",
        "consumer_projection": {
            "projection_id": "projection:consumer-distribution",
            "release_manifest_path": "consumer-release.json",
        },
        "content_impact_plan": {
            "member_root_path": ".",
            "inventory": [],
        },
    }


def _write_clean_consumer(audit, source: Path, installed: Path):
    _write_current_authority(source, "worldguard")
    (source / "runtime").mkdir()
    (source / "runtime" / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
    api = audit._consumer_distribution_api()
    contract = _consumer_contract()
    result = api.build_consumer_distribution(source, installed, contract)
    assert result["status"] == "passed"
    return api, contract


def test_package_identity_accepts_exact_installed_distribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = _load_audit_module()
    source_package = tmp_path / "source" / "worldguard"
    installed_package = tmp_path / "site-packages" / "worldguard"
    for package in (source_package, installed_package):
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            '__version__ = "0.7.2"\n', encoding="utf-8"
        )
        (package / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.7.2\n", encoding="utf-8")
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(
        '[project]\nname = "worldguard"\nversion = "0.7.2"\n',
        encoding="utf-8",
    )
    imported = type(
        "ImportedWorldGuard",
        (),
        {"__file__": str(installed_package / "__init__.py"), "__version__": "0.7.2"},
    )()
    monkeypatch.setattr(audit, "SOURCE_PACKAGE", source_package)
    monkeypatch.setattr(audit, "BUNDLED_PACKAGE", source_package)
    monkeypatch.setattr(audit, "VERSION_FILE", version_file)
    monkeypatch.setattr(audit, "PYPROJECT_FILE", pyproject_file)
    monkeypatch.setattr(audit.importlib, "import_module", lambda _name: imported)
    monkeypatch.setattr(audit.importlib.metadata, "version", lambda _name: "0.7.2")
    _patch_projection_report(monkeypatch, audit)

    status = audit._check_package_identity()

    assert status["ok"] is True
    assert status["import_mode"] == "installed-distribution"
    assert status["missing"] == []
    assert status["unexpected"] == []
    assert status["changed"] == []


def test_package_identity_rejects_distribution_byte_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audit = _load_audit_module()
    source_package = tmp_path / "source" / "worldguard"
    installed_package = tmp_path / "site-packages" / "worldguard"
    for package in (source_package, installed_package):
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            '__version__ = "0.7.2"\n', encoding="utf-8"
        )
    (source_package / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
    (installed_package / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.7.2\n", encoding="utf-8")
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(
        '[project]\nname = "worldguard"\nversion = "0.7.2"\n',
        encoding="utf-8",
    )
    imported = type(
        "ImportedWorldGuard",
        (),
        {"__file__": str(installed_package / "__init__.py"), "__version__": "0.7.2"},
    )()
    monkeypatch.setattr(audit, "SOURCE_PACKAGE", source_package)
    monkeypatch.setattr(audit, "BUNDLED_PACKAGE", source_package)
    monkeypatch.setattr(audit, "VERSION_FILE", version_file)
    monkeypatch.setattr(audit, "PYPROJECT_FILE", pyproject_file)
    monkeypatch.setattr(audit.importlib, "import_module", lambda _name: imported)
    monkeypatch.setattr(audit.importlib.metadata, "version", lambda _name: "0.7.2")
    _patch_projection_report(monkeypatch, audit)

    status = audit._check_package_identity()

    assert status["ok"] is False
    assert status["changed"] == ["engine.py"]


def test_package_identity_rejects_bundled_runtime_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = _load_audit_module()
    source_package = tmp_path / "source" / "worldguard"
    bundled_package = tmp_path / "bundle" / "worldguard"
    installed_package = tmp_path / "site-packages" / "worldguard"
    for package in (source_package, bundled_package, installed_package):
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            '__version__ = "0.7.2"\n', encoding="utf-8"
        )
        (package / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
    (bundled_package / "engine.py").write_text("VALUE = 2\n", encoding="utf-8")
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.7.2\n", encoding="utf-8")
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(
        '[project]\nname = "worldguard"\nversion = "0.7.2"\n',
        encoding="utf-8",
    )
    imported = type(
        "ImportedWorldGuard",
        (),
        {"__file__": str(installed_package / "__init__.py"), "__version__": "0.7.2"},
    )()
    monkeypatch.setattr(audit, "SOURCE_PACKAGE", source_package)
    monkeypatch.setattr(audit, "BUNDLED_PACKAGE", bundled_package)
    monkeypatch.setattr(audit, "VERSION_FILE", version_file)
    monkeypatch.setattr(audit, "PYPROJECT_FILE", pyproject_file)
    monkeypatch.setattr(audit.importlib, "import_module", lambda _name: imported)
    monkeypatch.setattr(audit.importlib.metadata, "version", lambda _name: "0.7.2")
    _patch_projection_report(
        monkeypatch,
        audit,
        _projection_report(
            ok=False,
            differences={"byte_drift": ["engine.py"]},
            failures=[
                {"code": "projection_byte_drift", "paths": ["engine.py"]}
            ],
        ),
    )

    status = audit._check_package_identity()

    assert status["ok"] is False
    assert status["bundle_changed"] == ["engine.py"]


def test_package_identity_rejects_source_version_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = _load_audit_module()
    source_package = tmp_path / "source" / "worldguard"
    installed_package = tmp_path / "site-packages" / "worldguard"
    for package in (source_package, installed_package):
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            '__version__ = "0.7.2"\n', encoding="utf-8"
        )
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.7.2\n", encoding="utf-8")
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(
        '[project]\nname = "worldguard"\nversion = "0.7.6"\n',
        encoding="utf-8",
    )
    imported = type(
        "ImportedWorldGuard",
        (),
        {"__file__": str(installed_package / "__init__.py"), "__version__": "0.7.2"},
    )()
    monkeypatch.setattr(audit, "SOURCE_PACKAGE", source_package)
    monkeypatch.setattr(audit, "BUNDLED_PACKAGE", source_package)
    monkeypatch.setattr(audit, "VERSION_FILE", version_file)
    monkeypatch.setattr(audit, "PYPROJECT_FILE", pyproject_file)
    monkeypatch.setattr(audit.importlib, "import_module", lambda _name: imported)
    monkeypatch.setattr(audit.importlib.metadata, "version", lambda _name: "0.7.2")
    _patch_projection_report(monkeypatch, audit)

    status = audit._check_package_identity()

    assert status["ok"] is False
    assert status["pyproject_version"] == "0.7.6"


def test_package_identity_reports_import_failure_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = _load_audit_module()

    def fail_import(_name):
        raise ModuleNotFoundError("fixture missing package")

    monkeypatch.setattr(audit.importlib, "import_module", fail_import)
    _patch_projection_report(monkeypatch, audit)
    status = audit._check_package_identity()

    assert status["ok"] is False
    assert status["import_mode"] == "unresolved"
    assert status["findings"] == [
        "package_identity_unavailable:ModuleNotFoundError"
    ]


def test_package_identity_rejects_import_without_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = _load_audit_module()
    imported = type("ImportedWorldGuard", (), {"__version__": "0.7.2"})()
    monkeypatch.setattr(audit.importlib, "import_module", lambda _name: imported)
    _patch_projection_report(monkeypatch, audit)

    status = audit._check_package_identity()

    assert status["ok"] is False
    assert status["findings"] == ["package_identity_unavailable:RuntimeError"]


def test_package_identity_calls_projection_audit_once_and_never_inventories_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = _load_audit_module()
    source_package = tmp_path / "source" / "worldguard"
    bundled_package = tmp_path / "bundle" / "worldguard"
    installed_package = tmp_path / "site-packages" / "worldguard"
    for package in (source_package, bundled_package, installed_package):
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(
            '__version__ = "0.7.2"\n', encoding="utf-8"
        )
        (package / "engine.py").write_text("VALUE = 1\n", encoding="utf-8")
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.7.2\n", encoding="utf-8")
    pyproject_file = tmp_path / "pyproject.toml"
    pyproject_file.write_text(
        '[project]\nname = "worldguard"\nversion = "0.7.2"\n',
        encoding="utf-8",
    )
    imported = type(
        "ImportedWorldGuard",
        (),
        {"__file__": str(installed_package / "__init__.py"), "__version__": "0.7.2"},
    )()
    audit_calls: list[Path] = []

    def projection_auditor(repository_root):
        audit_calls.append(Path(repository_root))
        return _projection_report()

    inventory_roots: list[Path] = []
    real_package_inventory = audit._package_inventory

    def package_inventory(root: Path):
        inventory_roots.append(Path(root).resolve())
        return real_package_inventory(root)

    monkeypatch.setattr(audit, "SOURCE_PACKAGE", source_package)
    monkeypatch.setattr(audit, "BUNDLED_PACKAGE", bundled_package)
    monkeypatch.setattr(audit, "VERSION_FILE", version_file)
    monkeypatch.setattr(audit, "PYPROJECT_FILE", pyproject_file)
    monkeypatch.setattr(audit.importlib, "import_module", lambda _name: imported)
    monkeypatch.setattr(audit.importlib.metadata, "version", lambda _name: "0.7.2")
    monkeypatch.setattr(
        audit, "_portable_runtime_projection_auditor", lambda: projection_auditor
    )
    monkeypatch.setattr(audit, "_package_inventory", package_inventory)

    status = audit._check_package_identity()

    assert status["ok"] is True
    assert audit_calls == [audit.ROOT]
    assert inventory_roots == [source_package.resolve(), installed_package.resolve()]
    assert bundled_package.resolve() not in inventory_roots
    assert status["portable_runtime_projection_status"] == "current"
    assert status["portable_runtime_projection_source_fingerprint"] == (
        "sha256:source"
    )
    assert status["portable_runtime_projection_bundle_fingerprint"] == (
        "sha256:projection"
    )


def test_package_identity_blocks_malformed_projection_audit_without_recompute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = _load_audit_module()
    audit_calls: list[Path] = []
    inventory_calls: list[Path] = []
    import_calls: list[str] = []

    def malformed_auditor(repository_root):
        audit_calls.append(Path(repository_root))
        return []

    def forbidden_inventory(root: Path):
        inventory_calls.append(Path(root))
        return {}

    def forbidden_import(name: str):
        import_calls.append(name)
        return object()

    monkeypatch.setattr(
        audit, "_portable_runtime_projection_auditor", lambda: malformed_auditor
    )
    monkeypatch.setattr(audit, "_package_inventory", forbidden_inventory)
    monkeypatch.setattr(audit.importlib, "import_module", forbidden_import)

    status = audit._check_package_identity()

    assert status["ok"] is False
    assert audit_calls == [audit.ROOT]
    assert inventory_calls == []
    assert import_calls == []
    assert status["findings"] == [
        "portable_runtime_projection_audit_unavailable:"
        "canonical_projection_audit_malformed:not_object"
    ]


def test_package_identity_blocks_unavailable_projection_audit_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = _load_audit_module()
    loader_calls = 0
    inventory_calls: list[Path] = []
    import_calls: list[str] = []

    def unavailable_auditor():
        nonlocal loader_calls
        loader_calls += 1
        raise audit.PortableRuntimeProjectionAuditUnavailable(
            "canonical_projection_audit_missing"
        )

    def forbidden_inventory(root: Path):
        inventory_calls.append(Path(root))
        return {}

    def forbidden_import(name: str):
        import_calls.append(name)
        return object()

    monkeypatch.setattr(
        audit, "_portable_runtime_projection_auditor", unavailable_auditor
    )
    monkeypatch.setattr(audit, "_package_inventory", forbidden_inventory)
    monkeypatch.setattr(audit.importlib, "import_module", forbidden_import)

    status = audit._check_package_identity()

    assert status["ok"] is False
    assert loader_calls == 1
    assert inventory_calls == []
    assert import_calls == []
    assert status["findings"] == [
        "portable_runtime_projection_audit_unavailable:"
        "canonical_projection_audit_missing"
    ]


def test_projection_auditor_is_the_exact_repository_owner() -> None:
    audit = _load_audit_module()

    auditor = audit._portable_runtime_projection_auditor()

    assert auditor.__name__ == "audit_projection"
    assert Path(auditor.__code__.co_filename).resolve(strict=True) == (
        ROOT / "scripts" / "sync_worldguard_portable_runtime.py"
    ).resolve(strict=True)


def test_source_authority_blocks_former_author_paths(tmp_path: Path) -> None:
    audit = _load_audit_module()
    skill = tmp_path / "skill"
    _write_current_authority(skill, "target-skill")
    assert audit._source_authority_status(skill, "target-skill")["ok"] is True

    generic = skill / ".skillguard" / "checks" / "check_route.py"
    generic.parent.mkdir(parents=True)
    generic.write_text("raise SystemExit(0)\n", encoding="utf-8")
    status = audit._source_authority_status(skill, "target-skill")
    assert status["ok"] is False
    assert "checks/check_route.py" in status["former_author_residuals"]

    generic.unlink()
    mutable = skill / ".skillguard" / "reports" / "current_closure.json"
    mutable.parent.mkdir(parents=True)
    mutable.write_text("{}\n", encoding="utf-8")
    status = audit._source_authority_status(skill, "target-skill")
    assert status["ok"] is False
    assert "reports/**" in status["former_author_residuals"]


def test_clean_consumer_projection_is_exact_and_author_control_free(
    tmp_path: Path,
) -> None:
    audit = _load_audit_module()
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    api, contract = _write_clean_consumer(audit, source, installed)

    status = audit._consumer_projection_status(
        source, installed, consumer_api=api, contract=contract
    )
    assert status["ok"] is True
    assert status["installed_author_control_paths"] == []
    assert not (installed / ".skillguard").exists()


def test_consumer_projection_rejects_author_control_and_hash_drift(
    tmp_path: Path,
) -> None:
    audit = _load_audit_module()
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    api, contract = _write_clean_consumer(audit, source, installed)

    control = installed / ".skillguard"
    control.mkdir()
    (control / "contract-source.json").write_text("{}\n", encoding="utf-8")
    installed.joinpath("SKILL.md").write_text("changed prompt\n", encoding="utf-8")
    status = audit._consumer_projection_status(
        source, installed, consumer_api=api, contract=contract
    )
    assert status["ok"] is False
    assert any(
        item.startswith("installed_audit:consumer_author_control_path_present:")
        for item in status["findings"]
    )
    assert any(
        item.startswith("installed_audit:consumer_file_hash_mismatch:SKILL.md")
        for item in status["findings"]
    )


def test_consumer_projection_rejects_source_inventory_drift(tmp_path: Path) -> None:
    audit = _load_audit_module()
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    api, contract = _write_clean_consumer(audit, source, installed)
    (source / "alternate_runtime.py").write_text("VALUE = 2\n", encoding="utf-8")

    status = audit._consumer_projection_status(
        source, installed, consumer_api=api, contract=contract
    )
    assert status["ok"] is False
    assert "consumer_release_id_not_current" in status["findings"]
    assert (
        "consumer_file_missing_from_installed_release:alternate_runtime.py"
        in status["findings"]
    )


def test_author_only_source_edit_does_not_stale_consumer_projection(
    tmp_path: Path,
) -> None:
    audit = _load_audit_module()
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    api, contract = _write_clean_consumer(audit, source, installed)

    author_note = source / ".skillguard" / "maintainer-note.json"
    author_note.write_text('{"revision": 1}\n', encoding="utf-8")
    status = audit._consumer_projection_status(
        source, installed, consumer_api=api, contract=contract
    )
    assert status["ok"] is True
    author_note.write_text('{"revision": 2}\n', encoding="utf-8")
    repeated = audit._consumer_projection_status(
        source, installed, consumer_api=api, contract=contract
    )
    assert repeated["ok"] is True
    assert status["release_id"] == repeated["release_id"]


@pytest.mark.parametrize(
    ("code", "path"),
    [
        ("consumer_symlink_forbidden", "runtime/link.py"),
        ("consumer_file_unexpected", "runtime/extra.py"),
        ("consumer_author_control_path_present", ".skillguard/private.json"),
    ],
)
def test_currentness_preserves_delegated_skillguard_path_findings(
    tmp_path: Path,
    code: str,
    path: str,
) -> None:
    audit = _load_audit_module()
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    source.mkdir()
    installed.mkdir()
    files = [{"path": "SKILL.md", "content_hash": "sha256:test"}]

    class BlockedAuditApi:
        __file__ = "installed-skillguard/consumer_distribution.py"

        @staticmethod
        def consumer_distribution_plan(_source, _contract):
            return {
                "status": "passed",
                "skill_id": "worldguard",
                "release_id": "release:test",
                "files": files,
                "findings": [],
            }

        @staticmethod
        def audit_consumer_distribution(_installed):
            return {
                "status": "blocked",
                "skill_id": "worldguard",
                "release_id": "release:test",
                "member_count": 1,
                "findings": [{"code": code, "path": path, "detail": "test"}],
                "manifest": {
                    "files": files,
                    "manifest_hash": "manifest:test",
                },
            }

    status = audit._consumer_projection_status(
        source,
        installed,
        consumer_api=BlockedAuditApi(),
        contract=_consumer_contract(),
    )
    assert status["ok"] is False
    assert f"installed_audit:{code}:{path}" in status["findings"]
    assert "skillguard_installed_audit_blocked" in status["findings"]


def test_currentness_blocks_when_installed_skillguard_api_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit = _load_audit_module()
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    source.mkdir()
    installed.mkdir()
    monkeypatch.setattr(
        audit,
        "_installed_skillguard_scripts_root",
        lambda: tmp_path / "missing-skillguard" / "scripts",
    )

    status = audit._consumer_projection_status(
        source, installed, contract=_consumer_contract()
    )
    assert status["ok"] is False
    assert any(
        item.startswith("skillguard_consumer_api_unavailable:")
        for item in status["findings"]
    )
    assert status["source_plan"] == {}
    assert status["installed_audit"] == {}


def test_currentness_rejects_empty_skillguard_results(tmp_path: Path) -> None:
    audit = _load_audit_module()
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    source.mkdir()
    installed.mkdir()

    class EmptyApi:
        __file__ = "installed-skillguard/consumer_distribution.py"

        @staticmethod
        def consumer_distribution_plan(_source, _contract):
            return {}

        @staticmethod
        def audit_consumer_distribution(_installed):
            return {}

    status = audit._consumer_projection_status(
        source,
        installed,
        consumer_api=EmptyApi(),
        contract=_consumer_contract(),
    )

    assert status["ok"] is False
    assert "skillguard_source_plan_missing" in status["findings"]
    assert "skillguard_installed_audit_missing" in status["findings"]


def test_currentness_rejects_empty_passed_inventories(tmp_path: Path) -> None:
    audit = _load_audit_module()
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    source.mkdir()
    installed.mkdir()

    class EmptyPassedApi:
        __file__ = "installed-skillguard/consumer_distribution.py"

        @staticmethod
        def consumer_distribution_plan(_source, _contract):
            return {
                "status": "passed",
                "skill_id": "worldguard",
                "release_id": "release:test",
                "files": [],
                "findings": [],
            }

        @staticmethod
        def audit_consumer_distribution(_installed):
            return {
                "status": "passed",
                "skill_id": "worldguard",
                "release_id": "release:test",
                "member_count": 0,
                "findings": [],
                "manifest": {"files": [], "manifest_hash": "manifest:test"},
            }

    status = audit._consumer_projection_status(
        source,
        installed,
        consumer_api=EmptyPassedApi(),
        contract=_consumer_contract(),
    )

    assert status["ok"] is False
    assert "skillguard_source_plan_inventory_empty" in status["findings"]
    assert "skillguard_installed_inventory_empty" in status["findings"]


@pytest.mark.parametrize("member_count", ["1", [], {}, True, -1, None])
def test_currentness_rejects_malformed_member_count(
    tmp_path: Path,
    member_count,
) -> None:
    audit = _load_audit_module()
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    source.mkdir()
    installed.mkdir()
    files = [{"path": "SKILL.md", "content_hash": "sha256:test"}]

    class MalformedCountApi:
        __file__ = "installed-skillguard/consumer_distribution.py"

        @staticmethod
        def consumer_distribution_plan(_source, _contract):
            return {
                "status": "passed",
                "skill_id": "worldguard",
                "release_id": "release:test",
                "files": files,
                "findings": [],
            }

        @staticmethod
        def audit_consumer_distribution(_installed):
            return {
                "status": "passed",
                "skill_id": "worldguard",
                "release_id": "release:test",
                "member_count": member_count,
                "findings": [],
                "manifest": {
                    "files": files,
                    "manifest_hash": "manifest:test",
                },
            }

    status = audit._consumer_projection_status(
        source,
        installed,
        consumer_api=MalformedCountApi(),
        contract=_consumer_contract(),
    )

    assert status["ok"] is False
    assert "skillguard_installed_member_count_not_nonnegative_integer" in status[
        "findings"
    ]


def test_currentness_drops_unknown_nonserializable_owner_fields(
    tmp_path: Path,
) -> None:
    audit = _load_audit_module()
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    real_api, contract = _write_clean_consumer(audit, source, installed)

    class ExtendedApi:
        __file__ = real_api.__file__

        @staticmethod
        def consumer_distribution_plan(source_root, current_contract):
            result = dict(
                real_api.consumer_distribution_plan(source_root, current_contract)
            )
            result["unknown_runtime_object"] = object()
            return result

        @staticmethod
        def audit_consumer_distribution(installed_root):
            result = dict(real_api.audit_consumer_distribution(installed_root))
            result["unknown_runtime_object"] = object()
            return result

    status = audit._consumer_projection_status(
        source,
        installed,
        consumer_api=ExtendedApi(),
        contract=contract,
    )

    assert status["ok"] is True
    json.dumps(status, ensure_ascii=False, sort_keys=True, allow_nan=False)


def _tree_snapshot(root: Path) -> dict[str, tuple[bytes, int]]:
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_currentness_calls_only_plan_and_audit_and_writes_nothing(
    tmp_path: Path,
) -> None:
    audit = _load_audit_module()
    source = tmp_path / "source"
    installed = tmp_path / "installed"
    real_api, contract = _write_clean_consumer(audit, source, installed)
    calls: list[str] = []

    class ReadOnlyApi:
        __file__ = real_api.__file__

        @staticmethod
        def consumer_distribution_plan(source_root, current_contract):
            calls.append("consumer_distribution_plan")
            return real_api.consumer_distribution_plan(source_root, current_contract)

        @staticmethod
        def audit_consumer_distribution(installed_root):
            calls.append("audit_consumer_distribution")
            return real_api.audit_consumer_distribution(installed_root)

        @staticmethod
        def build_consumer_distribution(*_args, **_kwargs):
            raise AssertionError("read-only currentness must not build")

    before_source = _tree_snapshot(source)
    before_installed = _tree_snapshot(installed)
    status = audit._consumer_projection_status(
        source,
        installed,
        consumer_api=ReadOnlyApi(),
        contract=contract,
    )
    assert status["ok"] is True
    assert calls == ["consumer_distribution_plan", "audit_consumer_distribution"]
    assert _tree_snapshot(source) == before_source
    assert _tree_snapshot(installed) == before_installed


def test_consumer_api_origin_is_the_current_installed_skillguard_module() -> None:
    audit = _load_audit_module()
    api = audit._consumer_distribution_api()
    expected = (
        audit._installed_skillguard_scripts_root()
        / "skillguard_v2"
        / "consumer_distribution.py"
    ).resolve(strict=True)
    assert Path(api.__file__).resolve(strict=True) == expected
    assert callable(api.consumer_distribution_plan)
    assert callable(api.audit_consumer_distribution)


def test_empty_codex_home_environment_uses_the_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_HOME", "")
    audit = _load_audit_module()
    assert audit.CODEX_HOME == Path.home() / ".codex"


def test_relative_codex_home_blocks_installed_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CODEX_HOME", "relative-codex-home")
    audit = _load_audit_module()
    with pytest.raises(
        audit.SkillGuardConsumerApiUnavailable,
        match="codex_home_unsafe",
    ):
        audit._consumer_distribution_api()


def test_main_emits_one_canonical_block_when_a_section_is_not_serializable(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    audit = _load_audit_module()
    monkeypatch.setattr(
        audit,
        "_check_package_identity",
        lambda: {"ok": True, "raw": object()},
    )
    monkeypatch.setattr(
        audit,
        "_source_authority_status",
        lambda *_args: {"ok": True},
    )
    monkeypatch.setattr(
        audit,
        "_consumer_projection_status",
        lambda *_args: {
            "ok": True,
            "release_id": "release:test",
            "manifest_hash": "manifest:test",
        },
    )

    exit_code = audit.main()
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert captured.err == ""
    assert payload["status"] == "blocked"
    assert payload["failures"] == [
        "readiness_machine_output_blocked:TypeError"
    ]


def test_main_exposes_explicit_terminal_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    audit = _load_audit_module()
    monkeypatch.setattr(
        audit,
        "_check_package_identity",
        lambda: {"ok": True},
    )
    monkeypatch.setattr(
        audit,
        "_source_authority_status",
        lambda *_args: {"ok": True},
    )
    monkeypatch.setattr(
        audit,
        "_consumer_projection_status",
        lambda *_args: {
            "ok": True,
            "release_id": "release:test",
            "manifest_hash": "manifest:test",
        },
    )

    exit_code = audit.main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["status"] == "pass"


def test_author_control_classifier_is_source_only_and_worldguard_is_only_member() -> None:
    contract = json.loads(
        (PRIMARY_ROOT / ".skillguard/contract-source.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["member_skill_ids"] == ["worldguard"]
    overrides = [
        row
        for row in contract["content_role_overrides"]
        if row.get("path") == "skills/worldguard/.skillguard"
    ]
    assert overrides == [
        {
            "path": "skills/worldguard/.skillguard",
            "role": "contract_schema",
            "install_disposition": "source_only",
            "reason": "author_control_never_enters_projection_installation",
        }
    ]
    internal_guards = {
        "EventGuard",
        "AgentGuard",
        "SpaceGuard",
        "ResourceGuard",
        "CausalGuard",
        "ConflictGuard",
        "NormGuard",
    }
    assert internal_guards.isdisjoint(contract["member_skill_ids"])


def test_primary_contract_uses_generic_supervision_and_binds_portable_runtime() -> None:
    contract = json.loads((PRIMARY_ROOT / ".skillguard/contract-source.json").read_text(encoding="utf-8"))
    compiled = json.loads((PRIMARY_ROOT / ".skillguard/compiled-contract.json").read_text(encoding="utf-8"))
    profile = contract["depth_profile"]

    runtime_path = "skills/worldguard/runtime/worldguard"
    assert runtime_path in contract["implementation_paths"]
    assert len(compiled["source_fingerprints"][f"implementation:{runtime_path}"]) == 64
    assert profile["integration_mode"] == "native-integrated"
    assert profile["enforcement_level"] == "enforced"
    assert profile["required_closure_profiles"] == ["enforced"]
    assert contract["closure_profiles"] == [
        {
            "profile_id": "enforced",
            "required_obligation_ids": contract["closure_profiles"][0]["required_obligation_ids"],
        }
    ]
    for forbidden in ("calibration", "coverage_universes", "dimensions"):
        assert forbidden not in profile
        assert forbidden not in contract
    assert not any("calibration" in check["check_id"] for check in contract["checks"])

    checks = {check["check_id"]: check for check in contract["checks"]}
    for check_id in ("check:worldguard:native-depth", "check:worldguard:guard-model-contract"):
        selectors = checks[check_id]["input_selectors"]
        assert any(
            item.get("path") == runtime_path
            or str(item.get("path", "")).startswith(f"{runtime_path}/")
            for item in selectors
        )
    for bridge in BRIDGE_PATHS:
        text = bridge.read_text(encoding="utf-8")
        assert "_activate_bundled_runtime(" in text
        assert "source_root" not in text
        assert "portable_target_runtime" not in text
    assert "sys.path.insert(0, str(RUNTIME_ROOT))" in GUARD_MODEL_CHECK.read_text(encoding="utf-8")
    assert not (PRIMARY_ROOT / "runtime/worldguard/skillguard_current_protocol.py").exists()
    assert not (ROOT / "worldguard/skillguard_current_protocol.py").exists()
    assert not any(
        "skillguard_current_protocol.py" in str(row.get("path", ""))
        for row in contract.get("content_role_overrides", [])
        if isinstance(row, dict)
    )


def test_formal_depth_rejects_missing_bundled_runtime_without_source_fallback(
    tmp_path: Path,
) -> None:
    bridge = _load_module(DEPTH_BRIDGE, "worldguard_depth_bridge_under_test")
    skill_root = tmp_path / "installed-skill"
    skill_root.mkdir()

    with pytest.raises(ValueError, match="bundled WorldGuard runtime"):
        bridge._activate_bundled_runtime(skill_root)


def test_formal_depth_selects_only_the_skill_bundled_runtime(tmp_path: Path) -> None:
    bridge = _load_module(DEPTH_BRIDGE, "worldguard_depth_bridge_runtime_under_test")
    skill_root = tmp_path / "installed-skill"
    package_root = skill_root / "runtime" / "worldguard"
    package_root.mkdir(parents=True)
    for name in ("__init__.py", "execution_depth.py"):
        package_root.joinpath(name).write_text("# bundled\n", encoding="utf-8")

    assert bridge._activate_bundled_runtime(skill_root) == package_root.resolve()
