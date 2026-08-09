from __future__ import annotations

import ast
import hashlib
import importlib
import importlib.metadata
import importlib.util
import json
import os
import sys
import types
import tomllib
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PACKAGE = ROOT / "worldguard"
BUNDLED_PACKAGE = ROOT / "skills" / "worldguard" / "runtime" / "worldguard"
VERSION_FILE = ROOT / "VERSION"
PYPROJECT_FILE = ROOT / "pyproject.toml"
_CONFIGURED_CODEX_HOME = os.environ.get("CODEX_HOME", "").strip()
CODEX_HOME = (
    Path(_CONFIGURED_CODEX_HOME).expanduser()
    if _CONFIGURED_CODEX_HOME
    else Path.home() / ".codex"
)
HOME_SKILLS = CODEX_HOME / "skills"
PACKAGE_NAME = "worldguard"
TARGET_SKILL_ID = "worldguard"
SOURCE_SKILL = ROOT / "skills" / TARGET_SKILL_ID
INSTALLED_SKILL = HOME_SKILLS / TARGET_SKILL_ID
CONSUMER_RELEASE_FILE = "consumer-release.json"
COMPILED_CONTRACT_FILE = ".skillguard/compiled-contract.json"
SKILLGUARD_CONSUMER_MODULE = "skillguard_v2/consumer_distribution.py"
PORTABLE_RUNTIME_PROJECTION_AUDIT = (
    ROOT / "scripts" / "sync_worldguard_portable_runtime.py"
)
PORTABLE_RUNTIME_PROJECTION_SCHEMA = "worldguard.portable-runtime-projection.v1"
PORTABLE_RUNTIME_DIFFERENCE_KEYS = (
    "missing",
    "extra",
    "byte_drift",
    "eol_only",
    "type_drift",
    "data_drift",
    "missing_directories",
    "extra_directories",
)
CURRENT_AUTHOR_AUTHORITY_FILES = (
    "contract-source.json",
    "compiled-contract.json",
    "check-manifest.json",
)
FORBIDDEN_AUTHOR_V1_FILES = (
    "check_manifest.json",
    "work-contract.json",
    "check.py",
    "checks/check_closure.py",
    "checks/check_evidence.py",
    "checks/check_phase_order.py",
    "checks/check_quality_floor.py",
    "checks/check_route.py",
    "skillguard_closure_policy.json",
    "skillguard_evidence_rules.json",
    "skillguard_manifest.json",
    "skillguard_profile.json",
    "skillguard_skill_contract.json",
    "skillguard_progress_ledger.jsonl",
)
FORBIDDEN_AUTHOR_V1_DIRS = ("ai_judgments", "evidence", "reports", "runs")
RETIREMENT_RECEIPT = "retirement-completion-receipt.json"


class SkillGuardConsumerApiUnavailable(RuntimeError):
    """The one installed SkillGuard consumer-distribution authority is unusable."""


class PortableRuntimeProjectionAuditUnavailable(RuntimeError):
    """The sole WorldGuard portable-runtime projection audit is unusable."""


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _package_inventory(root: Path) -> dict[str, str]:
    if not root.is_dir():
        return {}
    inventory: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if "__pycache__" in relative.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        inventory[relative.as_posix()] = "sha256:" + hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    return inventory


def _declared_module_version(package_root: Path) -> str:
    path = package_root / "__init__.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    versions = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__"
            for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ]
    if len(versions) != 1 or not versions[0]:
        raise RuntimeError("package_version_declaration_invalid")
    return versions[0]


def _is_link_or_junction(path: Path) -> bool:
    junction_check = getattr(path, "is_junction", None)
    return path.is_symlink() or bool(junction_check and junction_check())


def _installed_skillguard_scripts_root() -> Path:
    return CODEX_HOME / "skills" / "skillguard" / "scripts"


def _portable_runtime_projection_auditor() -> Any:
    """Load the exact repository-owned projection auditor without a fallback."""

    path = PORTABLE_RUNTIME_PROJECTION_AUDIT
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise PortableRuntimeProjectionAuditUnavailable(
            "canonical_projection_audit_missing"
        ) from exc
    if not resolved.is_file() or _is_link_or_junction(path):
        raise PortableRuntimeProjectionAuditUnavailable(
            "canonical_projection_audit_path_unsafe"
        )
    if os.path.normcase(str(path.absolute())) != os.path.normcase(str(resolved)):
        raise PortableRuntimeProjectionAuditUnavailable(
            "canonical_projection_audit_ancestor_link_forbidden"
        )

    module_name = "_worldguard_portable_runtime_projection_audit"
    prior_module = sys.modules.pop(module_name, None)
    prior_bytecode_policy = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location(module_name, resolved)
        if spec is None or spec.loader is None:
            raise PortableRuntimeProjectionAuditUnavailable(
                "canonical_projection_audit_spec_unavailable"
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        loaded_path = Path(str(getattr(module, "__file__", ""))).resolve(
            strict=True
        )
        if loaded_path != resolved:
            raise PortableRuntimeProjectionAuditUnavailable(
                "canonical_projection_audit_origin_mismatch"
            )
        auditor = getattr(module, "audit_projection", None)
        if not callable(auditor):
            raise PortableRuntimeProjectionAuditUnavailable(
                "canonical_projection_audit_callable_missing"
            )
        return auditor
    except PortableRuntimeProjectionAuditUnavailable:
        raise
    except Exception as exc:
        raise PortableRuntimeProjectionAuditUnavailable(
            f"canonical_projection_audit_load_failed:{type(exc).__name__}"
        ) from exc
    finally:
        sys.dont_write_bytecode = prior_bytecode_policy
        sys.modules.pop(module_name, None)
        if prior_module is not None:
            sys.modules[module_name] = prior_module


def _projection_string_list(value: Any, *, owner: str) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item for item in value
    ):
        raise PortableRuntimeProjectionAuditUnavailable(
            f"canonical_projection_audit_malformed:{owner}"
        )
    return list(value)


def _canonical_projection_audit() -> dict[str, Any]:
    """Call and validate the sole projection auditor exactly once."""

    auditor = _portable_runtime_projection_auditor()
    try:
        raw = auditor(ROOT)
    except Exception as exc:
        raise PortableRuntimeProjectionAuditUnavailable(
            f"canonical_projection_audit_failed:{type(exc).__name__}"
        ) from exc
    if not isinstance(raw, Mapping):
        raise PortableRuntimeProjectionAuditUnavailable(
            "canonical_projection_audit_malformed:not_object"
        )
    report = dict(raw)
    if (
        report.get("schema_version") != PORTABLE_RUNTIME_PROJECTION_SCHEMA
        or report.get("action") != "check"
        or report.get("write_performed") is not False
        or report.get("transaction_state") != "read_only"
        or not isinstance(report.get("ok"), bool)
    ):
        raise PortableRuntimeProjectionAuditUnavailable(
            "canonical_projection_audit_malformed:envelope"
        )
    ok = bool(report["ok"])
    expected_status = "current" if ok else "blocked"
    if report.get("status") != expected_status:
        raise PortableRuntimeProjectionAuditUnavailable(
            "canonical_projection_audit_malformed:status"
        )

    authority = report.get("authority")
    if not isinstance(authority, Mapping) or dict(authority) != {
        "author_source": "worldguard",
        "derived_projection": "skills/worldguard/runtime/worldguard",
        "direction": "author_source_to_derived_projection_only",
    }:
        raise PortableRuntimeProjectionAuditUnavailable(
            "canonical_projection_audit_malformed:authority"
        )

    for owner in ("source_inventory", "projection_inventory"):
        inventory = report.get(owner)
        if not isinstance(inventory, Mapping):
            raise PortableRuntimeProjectionAuditUnavailable(
                f"canonical_projection_audit_malformed:{owner}"
            )
        member_count = inventory.get("member_count")
        if (
            isinstance(member_count, bool)
            or not isinstance(member_count, int)
            or member_count < 0
            or not isinstance(inventory.get("fingerprint"), str)
            or not inventory.get("fingerprint")
        ):
            raise PortableRuntimeProjectionAuditUnavailable(
                f"canonical_projection_audit_malformed:{owner}"
            )

    differences = report.get("differences")
    if not isinstance(differences, Mapping):
        raise PortableRuntimeProjectionAuditUnavailable(
            "canonical_projection_audit_malformed:differences"
        )
    normalized_differences = {
        key: _projection_string_list(differences.get(key), owner=f"differences.{key}")
        for key in PORTABLE_RUNTIME_DIFFERENCE_KEYS
    }
    failures = report.get("failures")
    if not isinstance(failures, list):
        raise PortableRuntimeProjectionAuditUnavailable(
            "canonical_projection_audit_malformed:failures"
        )
    normalized_failures: list[dict[str, Any]] = []
    for index, failure in enumerate(failures):
        if not isinstance(failure, Mapping):
            raise PortableRuntimeProjectionAuditUnavailable(
                f"canonical_projection_audit_malformed:failures.{index}"
            )
        code = failure.get("code")
        if not isinstance(code, str) or not code:
            raise PortableRuntimeProjectionAuditUnavailable(
                f"canonical_projection_audit_malformed:failures.{index}.code"
            )
        paths = _projection_string_list(
            failure.get("paths"), owner=f"failures.{index}.paths"
        )
        normalized_failures.append({"code": code, "paths": paths})
    if ok and (
        normalized_failures
        or any(normalized_differences.values())
        or report["source_inventory"]["member_count"] == 0
    ):
        raise PortableRuntimeProjectionAuditUnavailable(
            "canonical_projection_audit_malformed:contradictory_pass"
        )
    if not ok and not normalized_failures:
        raise PortableRuntimeProjectionAuditUnavailable(
            "canonical_projection_audit_malformed:blocked_without_failure"
        )
    report["differences"] = normalized_differences
    report["failures"] = normalized_failures
    return report


def _consumer_distribution_api() -> Any:
    """Load the exact installed read-only consumer API without a source fallback."""

    scripts_root = _installed_skillguard_scripts_root()
    if not CODEX_HOME.is_absolute() or _is_link_or_junction(CODEX_HOME):
        raise SkillGuardConsumerApiUnavailable(
            "installed_skillguard_codex_home_unsafe"
        )
    try:
        resolved_scripts = scripts_root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SkillGuardConsumerApiUnavailable(
            "installed_skillguard_scripts_missing"
        ) from exc
    if os.path.normcase(str(scripts_root.absolute())) != os.path.normcase(
        str(resolved_scripts)
    ):
        raise SkillGuardConsumerApiUnavailable(
            "installed_skillguard_consumer_api_ancestor_link_forbidden"
        )
    module_path = resolved_scripts.joinpath(
        *SKILLGUARD_CONSUMER_MODULE.split("/")
    )
    package_root = module_path.parent
    package_init = package_root / "__init__.py"
    required_paths = (resolved_scripts, package_root, package_init, module_path)
    if any(_is_link_or_junction(path) for path in required_paths):
        raise SkillGuardConsumerApiUnavailable(
            "installed_skillguard_consumer_api_link_forbidden"
        )
    if not resolved_scripts.is_dir() or not package_root.is_dir():
        raise SkillGuardConsumerApiUnavailable(
            "installed_skillguard_consumer_api_directory_missing"
        )
    if not package_init.is_file() or not module_path.is_file():
        raise SkillGuardConsumerApiUnavailable(
            "installed_skillguard_consumer_api_module_missing"
        )
    try:
        resolved_module = module_path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SkillGuardConsumerApiUnavailable(
            "installed_skillguard_consumer_api_module_unresolvable"
        ) from exc
    if resolved_module.parent != package_root.resolve(strict=True):
        raise SkillGuardConsumerApiUnavailable(
            "installed_skillguard_consumer_api_path_escape"
        )

    package_name = "_worldguard_current_skillguard_v2"
    module_name = f"{package_name}.consumer_distribution"
    prior_modules = {
        name: module
        for name, module in tuple(sys.modules.items())
        if name == package_name or name.startswith(f"{package_name}.")
    }
    for name in prior_modules:
        sys.modules.pop(name, None)
    prior_bytecode_policy = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        package = types.ModuleType(package_name)
        package.__file__ = str(package_init)
        package.__package__ = package_name
        package.__path__ = [str(package_root)]
        sys.modules[package_name] = package
        spec = importlib.util.spec_from_file_location(module_name, resolved_module)
        if spec is None or spec.loader is None:
            raise SkillGuardConsumerApiUnavailable(
                "installed_skillguard_consumer_api_spec_unavailable"
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        loaded_path = Path(str(getattr(module, "__file__", ""))).resolve(strict=True)
        if loaded_path != resolved_module:
            raise SkillGuardConsumerApiUnavailable(
                "installed_skillguard_consumer_api_origin_mismatch"
            )
        for name in ("consumer_distribution_plan", "audit_consumer_distribution"):
            if not callable(getattr(module, name, None)):
                raise SkillGuardConsumerApiUnavailable(
                    f"installed_skillguard_consumer_api_missing:{name}"
                )
        resolved_package_root = package_root.resolve(strict=True)
        foreign_dependencies: list[str] = []
        for loaded_name, loaded_module in tuple(sys.modules.items()):
            if loaded_name != package_name and not loaded_name.startswith(
                f"{package_name}."
            ):
                continue
            loaded_file = getattr(loaded_module, "__file__", None)
            try:
                loaded_path = Path(str(loaded_file)).resolve(strict=True)
            except (OSError, RuntimeError):
                foreign_dependencies.append(loaded_name)
                continue
            if not loaded_path.is_relative_to(resolved_package_root):
                foreign_dependencies.append(loaded_name)
        if foreign_dependencies:
            raise SkillGuardConsumerApiUnavailable(
                "installed_skillguard_consumer_api_foreign_dependency:"
                + ",".join(sorted(foreign_dependencies))
            )
        return module
    except SkillGuardConsumerApiUnavailable:
        raise
    except Exception as exc:
        raise SkillGuardConsumerApiUnavailable(
            f"installed_skillguard_consumer_api_load_failed:{type(exc).__name__}"
        ) from exc
    finally:
        sys.dont_write_bytecode = prior_bytecode_policy
        for name in tuple(sys.modules):
            if name == package_name or name.startswith(f"{package_name}."):
                sys.modules.pop(name, None)
        sys.modules.update(prior_modules)


def _check_package_identity() -> dict[str, Any]:
    status: dict[str, Any] = {
        "check": "canonical_package_identity",
        "ok": False,
        "source_version": "",
        "pyproject_version": "",
        "source_module_version": "",
        "bundled_module_version": "",
        "metadata_version": "",
        "module_version": "",
        "module_path": "",
        "import_mode": "unresolved",
        "source_package_root": str(SOURCE_PACKAGE.absolute()),
        "imported_package_root": "",
        "expected_member_count": 0,
        "actual_member_count": 0,
        "missing": [],
        "unexpected": [],
        "changed": [],
        "bundle_missing": [],
        "bundle_unexpected": [],
        "bundle_changed": [],
        "portable_runtime_projection_status": "unresolved",
        "portable_runtime_projection_source_fingerprint": "",
        "portable_runtime_projection_bundle_fingerprint": "",
        "findings": [],
        "claim_boundary": (
            "This check proves that the imported package version and package bytes "
            "match the current repository package and consumes the sole portable-"
            "runtime projection audit for bundle parity. Wheel metadata, "
            "installation transaction, Git, tag, and release identities remain "
            "separate."
        ),
    }
    try:
        projection_audit = _canonical_projection_audit()
        projection_differences = projection_audit["differences"]
        bundle_missing = list(projection_differences["missing"])
        bundle_unexpected = list(projection_differences["extra"])
        bundle_changed = sorted(
            set(projection_differences["byte_drift"])
            | set(projection_differences["eol_only"])
            | set(projection_differences["type_drift"])
        )
        projection_findings = [
            f"portable_runtime_projection_blocked:{failure['code']}"
            for failure in projection_audit["failures"]
        ]
        status.update(
            {
                "bundle_missing": bundle_missing,
                "bundle_unexpected": bundle_unexpected,
                "bundle_changed": bundle_changed,
                "portable_runtime_projection_status": projection_audit["status"],
                "portable_runtime_projection_source_fingerprint": (
                    projection_audit["source_inventory"]["fingerprint"]
                ),
                "portable_runtime_projection_bundle_fingerprint": (
                    projection_audit["projection_inventory"]["fingerprint"]
                ),
                "findings": projection_findings,
            }
        )
        module = importlib.import_module(PACKAGE_NAME)
        raw_module_path = getattr(module, "__file__", None)
        if not isinstance(raw_module_path, str) or not raw_module_path:
            raise RuntimeError("imported_package_file_missing")
        module_path = Path(raw_module_path).resolve(strict=True)
        module_root = module_path.parent
        metadata_version = importlib.metadata.version(PACKAGE_NAME)
        module_version = str(getattr(module, "__version__", ""))
        source_version = VERSION_FILE.read_text(encoding="utf-8").strip()
        pyproject_version = str(
            tomllib.loads(PYPROJECT_FILE.read_text(encoding="utf-8"))["project"][
                "version"
            ]
        )
        source_root = SOURCE_PACKAGE.resolve(strict=True)
        bundled_root = BUNDLED_PACKAGE.resolve(strict=True)
        source_module_version = _declared_module_version(source_root)
        bundled_module_version = _declared_module_version(bundled_root)
        expected_inventory = _package_inventory(source_root)
        actual_inventory = _package_inventory(module_root)
        missing = sorted(set(expected_inventory) - set(actual_inventory))
        unexpected = sorted(set(actual_inventory) - set(expected_inventory))
        changed = sorted(
            path
            for path in set(expected_inventory) & set(actual_inventory)
            if expected_inventory[path] != actual_inventory[path]
        )
        import_mode = (
            "repository-source-projection"
            if module_root == source_root
            else "installed-distribution"
        )
        status.update(
            {
                "ok": (
                    metadata_version
                    == module_version
                    == source_version
                    == pyproject_version
                    == source_module_version
                    == bundled_module_version
                    and projection_audit["ok"]
                    and bool(expected_inventory)
                    and not missing
                    and not unexpected
                    and not changed
                    and not bundle_missing
                    and not bundle_unexpected
                    and not bundle_changed
                ),
                "source_version": source_version,
                "pyproject_version": pyproject_version,
                "source_module_version": source_module_version,
                "bundled_module_version": bundled_module_version,
                "metadata_version": metadata_version,
                "module_version": module_version,
                "module_path": str(module_path),
                "import_mode": import_mode,
                "source_package_root": str(source_root),
                "imported_package_root": str(module_root),
                "expected_member_count": len(expected_inventory),
                "actual_member_count": len(actual_inventory),
                "missing": missing,
                "unexpected": unexpected,
                "changed": changed,
                "bundle_missing": bundle_missing,
                "bundle_unexpected": bundle_unexpected,
                "bundle_changed": bundle_changed,
            }
        )
    except PortableRuntimeProjectionAuditUnavailable as exc:
        status["findings"] = [
            *status["findings"],
            f"portable_runtime_projection_audit_unavailable:{exc}",
        ]
    except Exception as exc:
        status["findings"] = [
            *status["findings"],
            f"package_identity_unavailable:{type(exc).__name__}",
        ]
    return status


def _strict_nonnegative_int(value: Any, *, owner: str) -> tuple[int, list[str]]:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0, [f"{owner}_not_nonnegative_integer"]
    return value, []


def _former_author_residuals(control_root: Path) -> list[str]:
    found = [
        relative
        for relative in FORBIDDEN_AUTHOR_V1_FILES
        if (control_root / relative).is_file()
    ]
    for relative in FORBIDDEN_AUTHOR_V1_DIRS:
        directory = control_root / relative
        if directory.is_dir() and any(path.is_file() for path in directory.rglob("*")):
            found.append(f"{relative}/**")
    if any(
        path.is_file()
        for cache in control_root.rglob("__pycache__")
        for path in cache.rglob("*")
    ):
        found.append("**/__pycache__/**")
    return sorted(found)


def _retirement_receipt_status(
    control_root: Path,
    target_skill_id: str,
) -> dict[str, Any]:
    path = control_root / RETIREMENT_RECEIPT
    if not path.is_file():
        return {
            "ok": False,
            "path": str(path),
            "reason": "expanded_scope_retirement_receipt_missing",
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "path": str(path),
            "reason": f"invalid_retirement_receipt:{exc}",
        }
    if not isinstance(payload, Mapping):
        return {
            "ok": False,
            "path": str(path),
            "reason": "invalid_retirement_receipt:not_object",
        }
    source_scan = payload.get("source_residual_scan")
    installed_scan = payload.get("installed_residual_scan")
    currentness = payload.get("installation_currentness")
    if not all(
        isinstance(value, Mapping)
        for value in (source_scan, installed_scan, currentness)
    ):
        return {
            "ok": False,
            "path": str(path),
            "reason": "invalid_retirement_receipt:nested_shape",
        }
    assert isinstance(source_scan, Mapping)
    assert isinstance(installed_scan, Mapping)
    assert isinstance(currentness, Mapping)
    ok = (
        payload.get("schema_version")
        == "worldguard.skillguard-retirement-completion.current"
        and payload.get("status") == "retired"
        and payload.get("target_skill_id") == target_skill_id
        and source_scan.get("residual_count") == 0
        and installed_scan.get("residual_count") == 0
        and currentness.get("status") == "passed"
    )
    return {
        "ok": ok,
        "path": str(path),
        "receipt_id": payload.get("receipt_id"),
        "target_skill_id": payload.get("target_skill_id"),
        "source_residual_count": source_scan.get("residual_count"),
        "installed_residual_count": installed_scan.get("residual_count"),
        "installation_currentness": currentness.get("status"),
    }


def _source_authority_status(
    skill_root: Path,
    target_skill_id: str,
) -> dict[str, Any]:
    control_root = skill_root / ".skillguard"
    missing = [
        relative
        for relative in CURRENT_AUTHOR_AUTHORITY_FILES
        if not (control_root / relative).is_file()
    ]
    residuals = _former_author_residuals(control_root)
    retirement = _retirement_receipt_status(control_root, target_skill_id)
    return {
        "ok": not missing and not residuals and retirement["ok"],
        "skill_root": str(skill_root),
        "missing_current_authority": missing,
        "former_author_residuals": residuals,
        "retirement_receipt": retirement,
        "claim_boundary": (
            "This check covers only author-side SkillGuard control state in the "
            "maintainer source. That state must not enter the consumer."
        ),
    }


def _consumer_contract_findings(contract: Mapping[str, Any]) -> list[str]:
    findings: list[str] = []
    if contract.get("skill_id") != TARGET_SKILL_ID:
        findings.append("source_contract_skill_id_mismatch")
    if contract.get("maintenance_unit_id") != "unit:worldguard":
        findings.append("source_contract_maintenance_unit_mismatch")
    if contract.get("member_skill_ids") != [TARGET_SKILL_ID]:
        findings.append("source_contract_external_skill_inventory_mismatch")
    projection = contract.get("consumer_projection")
    if not isinstance(projection, Mapping):
        findings.append("source_contract_consumer_projection_missing")
    elif (
        projection.get("projection_id") != "projection:consumer-distribution"
        or projection.get("release_manifest_path") != CONSUMER_RELEASE_FILE
    ):
        findings.append("source_contract_consumer_projection_mismatch")
    impact_plan = contract.get("content_impact_plan")
    if not isinstance(impact_plan, Mapping):
        findings.append("source_contract_content_impact_plan_missing")
    return findings


def _load_consumer_contract(
    source_skill: Path,
) -> tuple[dict[str, Any], list[str], str]:
    path = source_skill / COMPILED_CONTRACT_FILE
    try:
        source_root = source_skill.resolve(strict=True)
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        return {}, [f"source_compiled_contract_unavailable:{type(exc).__name__}"], str(path)
    if _is_link_or_junction(path) or not resolved.is_relative_to(source_root):
        return {}, ["source_compiled_contract_path_unsafe"], str(resolved)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, [f"source_compiled_contract_invalid:{type(exc).__name__}"], str(resolved)
    if not isinstance(payload, dict):
        return {}, ["source_compiled_contract_not_object"], str(resolved)
    return payload, _consumer_contract_findings(payload), str(resolved)


def _consumer_file_rows(
    value: Any,
    *,
    owner: str,
) -> tuple[dict[str, str], list[str]]:
    if not isinstance(value, list):
        return {}, [f"{owner}_files_not_list"]
    rows: dict[str, str] = {}
    findings: list[str] = []
    for row in value:
        if not isinstance(row, Mapping):
            findings.append(f"{owner}_file_row_not_object")
            continue
        relative = str(row.get("path", ""))
        content_hash = str(row.get("content_hash", ""))
        if not relative or not content_hash:
            findings.append(f"{owner}_file_row_incomplete")
            continue
        if relative in rows:
            findings.append(f"{owner}_file_row_duplicate:{relative}")
            continue
        rows[relative] = content_hash
    return rows, findings


def _skillguard_finding_labels(result: Mapping[str, Any], owner: str) -> list[str]:
    labels: list[str] = []
    raw_findings = result.get("findings", [])
    if not isinstance(raw_findings, list):
        return [f"{owner}_findings_not_list"]
    for finding in raw_findings:
        if not isinstance(finding, Mapping):
            labels.append(f"{owner}_finding_not_object")
            continue
        code = str(finding.get("code", "missing_code"))
        path = str(finding.get("path", ""))
        labels.append(f"{owner}:{code}" + (f":{path}" if path else ""))
    return labels


def _skillguard_result_projection(
    result: Mapping[str, Any],
    *,
    include_manifest: bool,
) -> dict[str, Any]:
    if not result:
        return {}
    files, _file_findings = _consumer_file_rows(
        result.get("files"), owner="result_projection"
    )
    projected: dict[str, Any] = {
        "schema_version": str(result.get("schema_version", "")),
        "status": str(result.get("status", "")),
        "skill_id": str(result.get("skill_id", "")),
        "projection_id": str(result.get("projection_id", "")),
        "release_id": str(result.get("release_id", "")),
        "release_manifest_path": str(result.get("release_manifest_path", "")),
        "files": [
            {"path": path, "content_hash": content_hash}
            for path, content_hash in sorted(files.items())
        ],
        "finding_labels": _skillguard_finding_labels(result, "result"),
    }
    member_count = result.get("member_count")
    projected["member_count"] = (
        member_count
        if isinstance(member_count, int) and not isinstance(member_count, bool)
        else None
    )
    if include_manifest:
        raw_manifest = result.get("manifest")
        if isinstance(raw_manifest, Mapping):
            manifest_files, _manifest_findings = _consumer_file_rows(
                raw_manifest.get("files"), owner="manifest_projection"
            )
            projected["manifest"] = {
                "schema_version": str(raw_manifest.get("schema_version", "")),
                "skill_id": str(raw_manifest.get("skill_id", "")),
                "projection_id": str(raw_manifest.get("projection_id", "")),
                "release_id": str(raw_manifest.get("release_id", "")),
                "manifest_hash": str(raw_manifest.get("manifest_hash", "")),
                "files": [
                    {"path": path, "content_hash": content_hash}
                    for path, content_hash in sorted(manifest_files.items())
                ],
            }
        else:
            projected["manifest"] = {}
    return projected


def _consumer_projection_status(
    source_skill: Path,
    installed_skill: Path,
    *,
    consumer_api: Any | None = None,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    findings: list[str] = []
    contract_path = "supplied-read-only-contract"
    current_contract: Mapping[str, Any]
    if contract is None:
        loaded_contract, contract_findings, contract_path = _load_consumer_contract(
            source_skill
        )
        current_contract = loaded_contract
        findings.extend(contract_findings)
    else:
        current_contract = contract
        findings.extend(_consumer_contract_findings(current_contract))

    try:
        api = consumer_api if consumer_api is not None else _consumer_distribution_api()
    except SkillGuardConsumerApiUnavailable as exc:
        findings.append(f"skillguard_consumer_api_unavailable:{exc}")
        api = None

    source_plan: dict[str, Any] = {}
    installed_audit: dict[str, Any] = {}
    if api is not None:
        if not findings:
            try:
                raw_plan = api.consumer_distribution_plan(source_skill, current_contract)
                if not isinstance(raw_plan, Mapping):
                    findings.append("skillguard_source_plan_not_object")
                else:
                    source_plan = dict(raw_plan)
            except Exception as exc:
                findings.append(
                    f"skillguard_source_plan_failed:{type(exc).__name__}"
                )
        try:
            raw_audit = api.audit_consumer_distribution(installed_skill)
            if not isinstance(raw_audit, Mapping):
                findings.append("skillguard_installed_audit_not_object")
            else:
                installed_audit = dict(raw_audit)
        except Exception as exc:
            findings.append(
                f"skillguard_installed_audit_failed:{type(exc).__name__}"
            )

    if not source_plan:
        findings.append("skillguard_source_plan_missing")
    else:
        if source_plan.get("status") != "passed":
            findings.append("skillguard_source_plan_blocked")
        findings.extend(_skillguard_finding_labels(source_plan, "source_plan"))
    if not installed_audit:
        findings.append("skillguard_installed_audit_missing")
    else:
        if installed_audit.get("status") != "passed":
            findings.append("skillguard_installed_audit_blocked")
        findings.extend(_skillguard_finding_labels(installed_audit, "installed_audit"))

    manifest = installed_audit.get("manifest", {})
    if not isinstance(manifest, Mapping):
        manifest = {}
        if installed_audit:
            findings.append("skillguard_installed_manifest_not_object")
    source_files, source_file_findings = _consumer_file_rows(
        source_plan.get("files"), owner="source_plan"
    )
    installed_files, installed_file_findings = _consumer_file_rows(
        manifest.get("files"), owner="installed_manifest"
    )
    if source_plan:
        findings.extend(source_file_findings)
        if not source_files:
            findings.append("skillguard_source_plan_inventory_empty")
        if not str(source_plan.get("release_id", "")):
            findings.append("skillguard_source_plan_release_id_missing")
    if installed_audit:
        findings.extend(installed_file_findings)
        if not installed_files:
            findings.append("skillguard_installed_inventory_empty")
        if not str(installed_audit.get("release_id", "")):
            findings.append("skillguard_installed_release_id_missing")
        if not str(manifest.get("manifest_hash", "")):
            findings.append("skillguard_installed_manifest_hash_missing")
        installed_member_count, member_count_findings = _strict_nonnegative_int(
            installed_audit.get("member_count"), owner="skillguard_installed_member_count"
        )
        findings.extend(member_count_findings)
        if installed_member_count != len(installed_files):
            findings.append("skillguard_installed_member_count_mismatch")
    else:
        installed_member_count = 0

    if source_plan and installed_audit:
        if source_plan.get("skill_id") != TARGET_SKILL_ID:
            findings.append("skillguard_source_plan_skill_id_mismatch")
        if installed_audit.get("skill_id") != TARGET_SKILL_ID:
            findings.append("skillguard_installed_skill_id_mismatch")
        if source_plan.get("release_id") != installed_audit.get("release_id"):
            findings.append("consumer_release_id_not_current")
        for relative in sorted(set(source_files) - set(installed_files)):
            findings.append(f"consumer_file_missing_from_installed_release:{relative}")
        for relative in sorted(set(installed_files) - set(source_files)):
            findings.append(f"consumer_file_unexpected_in_installed_release:{relative}")
        for relative in sorted(set(source_files) & set(installed_files)):
            if source_files[relative] != installed_files[relative]:
                findings.append(f"consumer_file_hash_not_current:{relative}")

    installed_author_control = sorted(
        {
            str(row.get("path", ""))
            for row in installed_audit.get("findings", [])
            if isinstance(row, Mapping)
            and str(row.get("code", ""))
            in {
                "consumer_author_control_name_present",
                "consumer_author_control_path_present",
            }
            and str(row.get("path", ""))
        }
    )
    findings = sorted(set(findings))
    return {
        "ok": not findings,
        "source_skill": str(source_skill.resolve()),
        "installed_skill": str(installed_skill.resolve()),
        "source_contract_path": contract_path,
        "skillguard_api_path": str(getattr(api, "__file__", "")) if api else "",
        "release_id": str(installed_audit.get("release_id", "")),
        "manifest_hash": str(manifest.get("manifest_hash", "")),
        "expected_member_count": len(source_files),
        "source_member_count": len(source_files),
        "installed_member_count": installed_member_count,
        "installed_author_control_paths": installed_author_control,
        "findings": findings,
        "source_plan": _skillguard_result_projection(
            source_plan, include_manifest=False
        ),
        "installed_audit": _skillguard_result_projection(
            installed_audit, include_manifest=True
        ),
        "claim_boundary": (
            "This read-only check delegates source projection planning and installed "
            "tree audit to the exact installed SkillGuard consumer-distribution API, "
            "then compares its skill, release, and complete file identities. It writes "
            "nothing and executes no smoke, domain check, or validation owner."
        ),
    }


def main() -> int:
    try:
        package = _check_package_identity()
    except Exception as exc:  # Keep the machine terminal canonical.
        package = {
            "check": "canonical_package_identity",
            "ok": False,
            "findings": [f"package_identity_unavailable:{type(exc).__name__}"],
        }
    try:
        source_authority = _source_authority_status(SOURCE_SKILL, TARGET_SKILL_ID)
    except Exception as exc:
        source_authority = {
            "ok": False,
            "skill_root": str(SOURCE_SKILL),
            "missing_current_authority": [],
            "former_author_residuals": [],
            "retirement_receipt": {},
            "findings": [f"source_authority_unavailable:{type(exc).__name__}"],
        }
    try:
        consumer_projection = _consumer_projection_status(
            SOURCE_SKILL, INSTALLED_SKILL
        )
    except Exception as exc:
        consumer_projection = {
            "ok": False,
            "source_skill": str(SOURCE_SKILL),
            "installed_skill": str(INSTALLED_SKILL),
            "release_id": "",
            "manifest_hash": "",
            "findings": [
                f"consumer_projection_unavailable:{type(exc).__name__}"
            ],
            "source_plan": {},
            "installed_audit": {},
        }
    ok = package["ok"] and source_authority["ok"] and consumer_projection["ok"]
    result = {
        "artifact_kind": "worldguard_release_readiness_audit",
        "ok": ok,
        "status": "pass" if ok else "blocked",
        "package": package,
        "source_authority": source_authority,
        "consumer_projection": consumer_projection,
        "installation_currentness": {
            "status": "passed" if consumer_projection["ok"] else "blocked",
            "release_id": consumer_projection["release_id"],
            "manifest_hash": consumer_projection["manifest_hash"],
        },
        "failures": [
            label
            for label, status in (
                ("package_identity_not_current", package["ok"]),
                ("source_authority_not_current", source_authority["ok"]),
                ("consumer_projection_not_current", consumer_projection["ok"]),
            )
            if not status
        ],
        "claim_boundary": (
            "Pass proves current package identity, current author-only SkillGuard "
            "control, and one exact clean standalone WorldGuard consumer projection. "
            "It does not prove a real target claim, factual truth, or future AI behavior."
        ),
    }
    try:
        payload = json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    except Exception as exc:
        ok = False
        result = {
            "artifact_kind": "worldguard_release_readiness_audit",
            "ok": False,
            "status": "blocked",
            "failures": [
                f"readiness_machine_output_blocked:{type(exc).__name__}"
            ],
        }
        payload = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)
    print(payload)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
