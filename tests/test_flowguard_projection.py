import shutil
from copy import deepcopy
from pathlib import Path

import yaml
import pytest

import worldguard.blueprint as blueprint_module
from worldguard import (
    build_flowguard_projection,
    build_flowguard_provider_profile,
    require_flowguard_toolchain,
    FlowGuardProjectionError,
)
from worldguard.blueprint import check_world_blueprint, WorldBlueprintContract


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/world_blueprint/planning_workflow_three_level.yaml"


def _current_at(payload: dict, source_root: Path) -> WorldBlueprintContract:
    payload = deepcopy(payload)
    payload.pop("blueprint_fingerprint", None)
    return WorldBlueprintContract.from_dict(payload, source_root=source_root)


def test_flowguard_projection_preserves_native_result_without_inventing_provider_proof(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setitem(
        blueprint_module._CROSS_ARTIFACT_PROJECTION_CAPABILITIES,
        (
            "worldguard.flowguard.blueprint-projection",
            "v1",
            "worldguard.flowguard.target-blueprint.v1",
        ),
        {
            "execution_owner_id": "worldguard.flowguard.blueprint-projection-owner",
            "execution_owner_version": "v1",
            "producer_identity_fingerprint": "sha256:"
            + blueprint_module.fingerprint_mesh(
                {
                    "provider_id": "worldguard.flowguard.blueprint-projection",
                    "provider_version": "v1",
                    "provider_capability_id": "worldguard.flowguard.target-blueprint.v1",
                    "execution_owner_id": "worldguard.flowguard.blueprint-projection-owner",
                    "execution_owner_version": "v1",
                }
            ),
        },
    )
    shutil.copytree(FIXTURE.parent / "support", tmp_path / "support")
    blueprint = _current_at(yaml.safe_load(FIXTURE.read_text(encoding="utf-8")), tmp_path)
    report = check_world_blueprint(blueprint)
    projection = build_flowguard_projection(blueprint, report)
    closed = check_world_blueprint(blueprint, cross_artifact_projection=projection)

    assert report.native_domain_qualified is True
    assert projection.status == "gap"
    assert projection.projected_source_ids == ()
    assert projection.unresolved_source_ids == projection.required_source_ids
    assert closed.native_domain_qualified is True
    assert closed.full_domain_qualified is False
    assert closed.cross_artifact_projection is not None
    assert not (tmp_path / "support" / "flowguard-blueprint-projection-receipt.json").exists()
    assert projection.normalized_payload["blueprint"] == blueprint.fingerprint_payload()
    assert projection.terminal_receipt_payload["terminal_status"] == "gap"


def test_flowguard_projection_keeps_full_denominator_unresolved_when_native_model_is_not_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setitem(
        blueprint_module._CROSS_ARTIFACT_PROJECTION_CAPABILITIES,
        (
            "worldguard.flowguard.blueprint-projection",
            "v1",
            "worldguard.flowguard.target-blueprint.v1",
        ),
        {
            "execution_owner_id": "worldguard.flowguard.blueprint-projection-owner",
            "execution_owner_version": "v1",
            "producer_identity_fingerprint": "sha256:"
            + blueprint_module.fingerprint_mesh(
                {
                    "provider_id": "worldguard.flowguard.blueprint-projection",
                    "provider_version": "v1",
                    "provider_capability_id": "worldguard.flowguard.target-blueprint.v1",
                    "execution_owner_id": "worldguard.flowguard.blueprint-projection-owner",
                    "execution_owner_version": "v1",
                }
            ),
        },
    )
    shutil.copytree(FIXTURE.parent / "support", tmp_path / "support")
    payload = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
    payload["bindings"] = [
        row for row in payload["bindings"] if row["binding_id"] != "assignment_test"
    ]
    blueprint = _current_at(payload, tmp_path)
    report = check_world_blueprint(blueprint)
    projection = build_flowguard_projection(blueprint, report)

    assert projection.status == "gap"
    assert projection.projected_source_ids == ()
    assert projection.unresolved_source_ids == projection.required_source_ids


def test_flowguard_provider_profile_requires_an_actual_optional_provider(monkeypatch) -> None:
    import worldguard.flowguard_projection as adapter
    real_import = adapter.importlib.import_module

    def without_optional_provider(name):
        if name == "flowguard.target_system_blueprint":
            raise ModuleNotFoundError(name)
        return real_import(name)

    monkeypatch.setattr(adapter.importlib, "import_module", without_optional_provider)
    with pytest.raises(FlowGuardProjectionError, match="FlowGuard is required"):
        require_flowguard_toolchain()
    with pytest.raises(FlowGuardProjectionError, match="FlowGuard is required"):
        build_flowguard_provider_profile(
            provider_id="worldguard.flowguard.blueprint-projection",
            target_profile="non_code_workflow",
            target_kind="world_behavior",
            layer_plan_id="target-system-layer-plan:non-code-workflow:v1",
            layer_plan_fingerprint="sha256:layer-plan-fingerprint",
            owner_id="worldguard.flowguard.blueprint-projection-owner",
            claim_boundary="WorldGuard supplies an identity projection only.",
        )
