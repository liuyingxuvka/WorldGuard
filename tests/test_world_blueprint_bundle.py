from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zlib
from copy import deepcopy
from pathlib import Path

import pytest
import worldguard.blueprint_bundle as bundle_module

from worldguard.blueprint import (
    BlueprintError,
    WorldBlueprintContract,
    compile_behavior_commitment_inventory_cache,
    load_world_blueprint,
)
from worldguard.blueprint_bundle import (
    query_world_blueprint_bundle,
    verify_world_blueprint_bundle,
    write_world_blueprint_bundle,
)
from worldguard.cli import main
from worldguard.semantic import fingerprint_mesh


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/world_blueprint/planning_workflow_three_level.yaml"
SEVEN_GUARD_HANDOFF_FIXTURE = (
    ROOT / "tests/fixtures/world_blueprint/seven_guard_portable_handoff.json"
)
MATRIX_FIXTURE = (
    ROOT / "tests/fixtures/world_blueprint/seven_guard_native_owner_matrix.json"
)

SEVEN_GUARD_CASES = {
    "EventGuard": ("event-pass", "event-overlap-fail"),
    "AgentGuard": ("agent-pass", "agent-conflict-fail"),
    "SpaceGuard": ("space-pass", "space-self-non-eq-fail"),
    "ResourceGuard": ("resource-pass", "resource-missing-model-fail"),
    "CausalGuard": ("causal-pass", "causal-self-cycle-fail"),
    "ConflictGuard": ("conflict-pass", "conflict-duplicate-participant-fail"),
    "NormGuard": ("norm-pass", "norm-unknown-modality-fail"),
}
SEVEN_GUARD_ADMISSION_CASES = (
    "space-third-participant-rejected",
    "resource-negative-rejected",
)


def _refresh_logical_fingerprint(bundle: dict) -> None:
    logical_payload = {
        key: value
        for key, value in bundle.items()
        if key != "logical_bundle_fingerprint"
    }
    bundle["logical_bundle_fingerprint"] = "sha256:" + fingerprint_mesh(
        logical_payload
    )


def test_bundle_only_native_handoff_is_deterministic_and_path_independent(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle_path = tmp_path / "exports" / "planning-workflow.bundle.json"

    bundle = write_world_blueprint_bundle(blueprint, bundle_path)
    first = verify_world_blueprint_bundle(
        bundle_path,
        materialization_root=tmp_path / "isolated-a",
    )
    second = verify_world_blueprint_bundle(
        json.loads(bundle_path.read_text(encoding="utf-8")),
        materialization_root=tmp_path / "different" / "isolated-b",
    )

    assert first == second
    assert first["status"] == "PASS"
    assert first["native_handoff_qualified"] is True
    assert first["full_cross_artifact_handoff_qualified"] is False
    assert first["cross_artifact_projection_status"] == "not_run"
    assert first["logical_bundle_fingerprint"] == bundle[
        "logical_bundle_fingerprint"
    ]
    assert set(bundle) == {
        "schema_version",
        "blueprint",
        "cross_artifact_projection",
        "replay_resources",
        "reproducibility_manifest",
        "logical_bundle_fingerprint",
    }
    manifest = bundle["reproducibility_manifest"]
    assert manifest["status"] == {
        "qualification": "PASS",
        "native_handoff_qualified": True,
        "full_cross_artifact_handoff_qualified": False,
        "object_dna_handoff_qualified": False,
        "object_census_authority_status": "valid",
        "object_census_authority_licensed": False,
        "object_census_coverage_complete": True,
        "object_claim_kind": "integrated_target",
        "object_census_first_gap": {
            "code": "object-census-trust-not-licensed",
            "detail": (
                "the signed census is portable and internally valid, but the caller "
                "did not trust its exact authority or producer descriptor fingerprint"
            ),
        },
        "cross_artifact_projection": "not_run",
        "query_derivation": "recomputed",
    }
    assert manifest["first_gap"] is None
    assert manifest["claim_boundary"] == blueprint.declared_boundary
    assert manifest["counts"]["nodes"] == len(blueprint.nodes)
    assert manifest["counts"]["elements"] == len(blueprint.elements)
    assert manifest["counts"]["behavior_cases"] == 18
    assert manifest["counts"]["bindings"] == len(blueprint.bindings)
    assert manifest["counts"]["query_members"] == 173
    assert "catalog" not in manifest
    assert manifest["fingerprints"]["catalog"].startswith("sha256:")
    assert manifest["fingerprints"]["commitment_cache"].startswith("sha256:")
    assert manifest["replay_resource_codec"] == bundle_module._REPLAY_RESOURCE_CODEC
    cache_relative_path = blueprint.commitment_inventory.locator.partition("#")[0]
    assert cache_relative_path not in {
        row["relative_path"] for row in bundle["replay_resources"]
    }
    regenerated_cache = json.loads(
        (tmp_path / "isolated-a" / cache_relative_path).read_text(encoding="utf-8")
    )
    assert regenerated_cache == compile_behavior_commitment_inventory_cache(
        blueprint
    )
    assert first["counts"] == manifest["counts"]
    assert first["first_gap"] is None
    assert first["bundle_utf8_bytes"] <= 262_144
    assert len(
        json.dumps(first, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        + b"\n"
    ) <= 12_288


def test_seven_guard_matrix_uses_the_same_public_bundle_and_query_route(
    tmp_path: Path,
) -> None:
    matrix = json.loads(MATRIX_FIXTURE.read_text(encoding="utf-8"))
    matrix_by_id = {row["case_id"]: row for row in matrix["cases"]}
    blueprint = load_world_blueprint(SEVEN_GUARD_HANDOFF_FIXTURE)
    bundle_path = tmp_path / "seven-guard.bundle.json"
    bundle = write_world_blueprint_bundle(blueprint, bundle_path)
    verification = verify_world_blueprint_bundle(
        bundle_path,
        materialization_root=tmp_path / "seven-guard-verify",
    )

    assert verification["status"] == "PASS"
    assert verification["native_handoff_qualified"] is True
    assert verification["full_cross_artifact_handoff_qualified"] is False
    assert verification["cross_artifact_projection_status"] == "not_run"
    assert verification["first_gap"] is None
    assert bundle_path.stat().st_size <= 262_144
    assert len(
        json.dumps(
            verification,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    ) <= 12_288

    expected_ids = {
        case_id
        for case_ids in SEVEN_GUARD_CASES.values()
        for case_id in case_ids
    }.union(SEVEN_GUARD_ADMISSION_CASES)
    manifest = bundle["reproducibility_manifest"]
    assert "catalog" not in manifest
    assert manifest["fingerprints"]["catalog"].startswith("sha256:")
    assert manifest["fingerprints"]["commitment_cache"].startswith("sha256:")

    for owner_guard, (good_id, bad_id) in SEVEN_GUARD_CASES.items():
        good = query_world_blueprint_bundle(
            bundle_path,
            materialization_root=tmp_path / f"query-{good_id}",
            query_kind="behavior-case",
            member_id=good_id,
        )
        bad = query_world_blueprint_bundle(
            bundle_path,
            materialization_root=tmp_path / f"query-{bad_id}",
            query_kind="behavior-case",
            member_id=bad_id,
        )
        assert good["claim_boundary"] == blueprint.declared_boundary
        assert bad["claim_boundary"] == blueprint.declared_boundary
        assert good["slice"]["case"]["case_kind"] == "known_good"
        assert bad["slice"]["case"]["case_kind"] == "known_bad"
        assert good["slice"]["native_oracle_observation"]["passed"] is True
        assert bad["slice"]["native_oracle_observation"]["passed"] is True
        assert good["slice"]["case"]["oracle_id"] == (
            f"oracle:worldguard:{owner_guard}:known-good"
        )
        assert bad["slice"]["case"]["oracle_id"].startswith(
            f"oracle:worldguard:{owner_guard}:"
        )
        assert good["slice"]["native_execution_receipt_fingerprint"].startswith(
            "sha256:"
        )
        assert bad["slice"]["native_execution_receipt_fingerprint"] == good[
            "slice"
        ]["native_execution_receipt_fingerprint"]
        assert len(
            json.dumps(
                good,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ) <= 12_288
        assert len(
            json.dumps(
                bad,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ) <= 12_288

        matrix_good = matrix_by_id[good_id]
        assert good["slice"]["case"]["inputs"] == matrix_good["oracle"][
            "canonical_owner_inputs"
        ]
        assert good["slice"]["case"]["expected_output"] == matrix_good[
            "oracle"
        ]["output_subset"]
        if bad_id in matrix_by_id:
            matrix_bad = matrix_by_id[bad_id]
            assert bad["slice"]["case"]["inputs"] == matrix_bad["oracle"][
                "canonical_owner_inputs"
            ]
            expected_codes = {
                *matrix_bad["oracle"].get("structural_error_codes", []),
                *matrix_bad["oracle"].get("semantic_finding_codes", []),
            }
            assert bad["slice"]["case"]["expected_code"] in expected_codes

    for case_id in SEVEN_GUARD_ADMISSION_CASES:
        query = query_world_blueprint_bundle(
            bundle_path,
            materialization_root=tmp_path / f"query-{case_id}",
            query_kind="behavior-case",
            member_id=case_id,
        )
        matrix_case = matrix_by_id[case_id]
        observation = query["slice"]["native_oracle_observation"]
        assert query["slice"]["case"]["case_kind"] == "admission_bad"
        assert observation["passed"] is True
        assert observation["observed_status"] == "REJECTED"
        assert observation["observed_code"] == matrix_case["oracle"][
            "admission_error_code"
        ]
        assert matrix_case["oracle"]["type_error"] in observation[
            "observed_details"
        ]["type_errors"]
        assert len(
            json.dumps(
                query,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ) <= 12_288

    causal_element = query_world_blueprint_bundle(
        bundle_path,
        materialization_root=tmp_path / "query-causal-element",
        query_kind="element",
        member_id="matrix_causal_pass",
    )
    assert causal_element["slice"]["native_semantic"]["semantic_fields"][
        "mechanism_claim_scope"
    ] == "graph_only"
    assert causal_element["claim_boundary"] == blueprint.declared_boundary


@pytest.mark.parametrize(
    ("field_name", "replacement", "expected_code"),
    [
        (
            "expected_output",
            {},
            "WORLD_BLUEPRINT_BEHAVIOR_ADMISSION_DETAILS_MISSING",
        ),
        (
            "oracle_id",
            "oracle:caller:self-signed",
            "WORLD_BLUEPRINT_BEHAVIOR_ADMISSION_ORACLE_INVALID",
        ),
        (
            "failure_id",
            "failure:caller:self-signed",
            "WORLD_BLUEPRINT_BEHAVIOR_ADMISSION_FAILURE_INVALID",
        ),
        (
            "state_effect_disposition",
            "unverified",
            "WORLD_BLUEPRINT_BEHAVIOR_ADMISSION_STATE_INVALID",
        ),
    ],
)
def test_admission_bad_contract_is_parser_owned_and_fail_closed(
    field_name: str,
    replacement: object,
    expected_code: str,
) -> None:
    payload = json.loads(
        SEVEN_GUARD_HANDOFF_FIXTURE.read_text(encoding="utf-8")
    )
    payload.pop("blueprint_fingerprint", None)
    admission_case = next(
        case
        for element in payload["elements"]
        for case in element["native_semantic"].get("task_purpose", {}).get(
            "behavior_cases", []
        )
        if case["case_kind"] == "admission_bad"
    )
    admission_case[field_name] = replacement

    with pytest.raises(BlueprintError) as captured:
        WorldBlueprintContract.from_dict(payload)

    assert captured.value.code == expected_code


def test_bundle_only_replay_rejects_resource_byte_tampering(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    tampered = deepcopy(bundle)
    tampered["replay_resources"][0]["content_size"] = 2
    tampered["replay_resources"][0]["content_zlib_base64"] = base64.b64encode(
        zlib.compress(b"{}", level=9)
    ).decode("ascii")
    _refresh_logical_fingerprint(tampered)

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(
            tampered,
            materialization_root=tmp_path / "isolated-tampered",
        )

    assert captured.value.code == "WORLD_BLUEPRINT_BUNDLE_RESOURCE_HASH_MISMATCH"


def test_bundle_only_replay_rejects_retired_commitment_cache_body(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    cache_relative_path = blueprint.commitment_inventory.locator.partition("#")[0]
    content = (FIXTURE.parent / cache_relative_path).read_bytes()
    tampered = deepcopy(bundle)
    tampered["replay_resources"].append(
        {
            "relative_path": cache_relative_path,
            "codec_id": bundle_module._REPLAY_RESOURCE_CODEC_ID,
            "content_sha256": "sha256:" + hashlib.sha256(content).hexdigest(),
            "content_size": len(content),
            "content_zlib_base64": base64.b64encode(
                zlib.compress(content, level=9)
            ).decode("ascii"),
        }
    )
    _refresh_logical_fingerprint(tampered)

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(
            tampered,
            materialization_root=tmp_path / "retired-cache-body",
        )

    assert captured.value.code == "WORLD_BLUEPRINT_BUNDLE_RETIRED_CACHE_BODY_PRESENT"


def test_bundle_only_replay_rejects_stale_regenerated_cache_identity(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    tampered = deepcopy(bundle)
    tampered["reproducibility_manifest"]["fingerprints"][
        "commitment_cache"
    ] = "sha256:" + "0" * 64
    _refresh_logical_fingerprint(tampered)

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(
            tampered,
            materialization_root=tmp_path / "stale-regenerated-cache",
        )

    assert captured.value.code == "WORLD_BLUEPRINT_BUNDLE_COMMITMENT_CACHE_MISMATCH"


def test_bundle_only_replay_rejects_stale_regenerated_catalog_identity(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    tampered = deepcopy(bundle)
    tampered["reproducibility_manifest"]["fingerprints"][
        "catalog"
    ] = "sha256:" + "0" * 64
    _refresh_logical_fingerprint(tampered)

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(
            tampered,
            materialization_root=tmp_path / "stale-regenerated-catalog",
        )

    assert captured.value.code == "WORLD_BLUEPRINT_BUNDLE_MANIFEST_MISMATCH"
    assert captured.value.details["mismatched_fields"] == ["fingerprints"]


@pytest.mark.parametrize("tamper_owner", ["resource", "manifest"])
def test_bundle_only_replay_rejects_noncurrent_codec(
    tmp_path: Path, tamper_owner: str
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    tampered = deepcopy(bundle)
    if tamper_owner == "resource":
        tampered["replay_resources"][0]["codec_id"] = "retired-uncompressed"
    else:
        tampered["reproducibility_manifest"]["replay_resource_codec"][
            "codec_id"
        ] = "retired-uncompressed"
    _refresh_logical_fingerprint(tampered)

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(
            tampered,
            materialization_root=tmp_path / f"codec-{tamper_owner}",
        )

    assert captured.value.code == "WORLD_BLUEPRINT_BUNDLE_RESOURCE_CODEC_MISMATCH"


def test_bundle_only_replay_rejects_truncated_compressed_resource(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    tampered = deepcopy(bundle)
    encoded = tampered["replay_resources"][0]["content_zlib_base64"]
    tampered["replay_resources"][0]["content_zlib_base64"] = encoded[:-4]
    _refresh_logical_fingerprint(tampered)

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(
            tampered,
            materialization_root=tmp_path / "truncated-compressed-resource",
        )

    assert captured.value.code == "WORLD_BLUEPRINT_BUNDLE_RESOURCE_ENCODING_INVALID"


def test_bundle_only_replay_rejects_decompression_bomb(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    bomb = b"0" * (bundle_module._MAX_REPLAY_RESOURCE_BYTES + 2)
    tampered = deepcopy(bundle)
    tampered["replay_resources"][0]["content_size"] = (
        bundle_module._MAX_REPLAY_RESOURCE_BYTES
    )
    tampered["replay_resources"][0]["content_zlib_base64"] = base64.b64encode(
        zlib.compress(bomb, level=9)
    ).decode("ascii")
    _refresh_logical_fingerprint(tampered)

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(
            tampered,
            materialization_root=tmp_path / "decompression-bomb",
        )

    assert (
        captured.value.code
        == "WORLD_BLUEPRINT_BUNDLE_RESOURCE_DECOMPRESSION_LIMIT"
    )


@pytest.mark.parametrize("manifest_field", ["fingerprints", "counts"])
def test_bundle_only_replay_rejects_stale_manifest(
    tmp_path: Path, manifest_field: str
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    tampered = deepcopy(bundle)
    if manifest_field == "fingerprints":
        tampered["reproducibility_manifest"]["fingerprints"][
            "qualification_report"
        ] = "forged-report"
    else:
        tampered["reproducibility_manifest"]["counts"]["elements"] += 1
    _refresh_logical_fingerprint(tampered)

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(
            tampered,
            materialization_root=tmp_path / "isolated-answer-tampered",
        )

    assert captured.value.code == "WORLD_BLUEPRINT_BUNDLE_MANIFEST_MISMATCH"
    assert manifest_field in captured.value.details["mismatched_fields"]


def test_bundle_verify_rejects_nonempty_materialization_root(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    materialization_root = tmp_path / "preexisting-root"
    materialization_root.mkdir()
    (materialization_root / "unknown.json").write_text("{}", encoding="utf-8")

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(
            bundle, materialization_root=materialization_root
        )

    assert (
        captured.value.code
        == "WORLD_BLUEPRINT_BUNDLE_MATERIALIZATION_ROOT_NOT_EMPTY"
    )


def test_bundle_verify_rejects_linked_materialization_root(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    target = tmp_path / "link-target"
    target.mkdir()
    linked_root = tmp_path / "linked-root"
    try:
        linked_root.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        completed = subprocess.run(
            [
                "cmd.exe",
                "/d",
                "/c",
                "mklink",
                "/J",
                str(linked_root),
                str(target),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if completed.returncode != 0:
            pytest.skip(
                "directory links are unavailable: "
                f"symlink={exc}; junction={completed.stderr or completed.stdout}"
            )

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(bundle, materialization_root=linked_root)

    assert (
        captured.value.code
        == "WORLD_BLUEPRINT_BUNDLE_MATERIALIZATION_ROOT_LINKED"
    )


def test_bundle_verify_rejects_escaping_resource_path(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    tampered = deepcopy(bundle)
    tampered["replay_resources"][0]["relative_path"] = "../escape.json"
    _refresh_logical_fingerprint(tampered)

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(
            tampered, materialization_root=tmp_path / "escape-root"
        )

    assert captured.value.code == "WORLD_BLUEPRINT_BUNDLE_RESOURCE_PATH_INVALID"


def test_bundle_verify_rejects_resource_denominator_omission(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    tampered = deepcopy(bundle)
    tampered["replay_resources"].pop()
    _refresh_logical_fingerprint(tampered)

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(
            tampered, materialization_root=tmp_path / "omission-root"
        )

    assert (
        captured.value.code
        == "WORLD_BLUEPRINT_BUNDLE_RESOURCE_DENOMINATOR_MISMATCH"
    )


@pytest.mark.parametrize(
    ("query_kind", "member_id", "identity_field"),
    [
        ("node", "plan_root", "node_id"),
        ("element", "actor_alex", "element_id"),
        (
            "behavior-case",
            "case:actor_alex:good",
            "case_id",
        ),
        ("binding", "actor_alex_native", "binding_id"),
        ("impact", "actor_alex", "operation"),
        ("reverse", "declared_plan_outcome", "operation"),
    ],
)
def test_bundle_by_id_query_returns_only_the_requested_slice(
    tmp_path: Path,
    query_kind: str,
    member_id: str,
    identity_field: str,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )

    result = query_world_blueprint_bundle(
        bundle,
        materialization_root=tmp_path / f"query-{query_kind}",
        query_kind=query_kind,
        member_id=member_id,
    )

    assert result["status"] == "PASS"
    assert result["query_kind"] == query_kind
    assert result["member_id"] == member_id
    if query_kind == "behavior-case":
        assert result["slice"]["case"][identity_field] == member_id
    elif query_kind == "impact":
        assert result["slice"][identity_field] == "impact"
        assert member_id in result["slice"]["materialized_ids"]
        assert "declared_plan_outcome" in result["slice"]["materialized_ids"]
    elif query_kind == "reverse":
        assert result["slice"][identity_field] == "trace"
    else:
        assert result["slice"][identity_field] == member_id
    assert "handoff_answers" not in result
    assert "query_indexes" not in result


@pytest.mark.parametrize(
    ("query_kind", "member_id", "expected_code"),
    [
        ("unknown-kind", "plan_root", "WORLD_BLUEPRINT_BUNDLE_QUERY_KIND_UNKNOWN"),
        ("node", "unknown-node", "WORLD_BLUEPRINT_BUNDLE_QUERY_ID_UNKNOWN"),
        ("impact", "unknown-impact", "WORLD_BLUEPRINT_QUERY_ID_UNKNOWN"),
    ],
)
def test_bundle_by_id_query_rejects_unknown_kind_or_id(
    tmp_path: Path,
    query_kind: str,
    member_id: str,
    expected_code: str,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )

    with pytest.raises(BlueprintError) as captured:
        query_world_blueprint_bundle(
            bundle,
            materialization_root=tmp_path / f"unknown-{query_kind}",
            query_kind=query_kind,
            member_id=member_id,
        )

    assert captured.value.code == expected_code


def test_bundle_query_rejects_an_unqualified_source_before_slice(
    tmp_path: Path,
) -> None:
    payload = load_world_blueprint(FIXTURE).to_dict()
    payload.pop("blueprint_fingerprint")
    for node in payload["nodes"]:
        if node["child_input_mappings"]:
            node["child_input_mappings"].pop()
            break
    unqualified = WorldBlueprintContract.from_dict(
        payload,
        source_root=FIXTURE.parent,
    )
    bundle = write_world_blueprint_bundle(
        unqualified, tmp_path / "unqualified.bundle.json"
    )
    assert bundle["reproducibility_manifest"]["status"]["qualification"] == "GAP"

    with pytest.raises(BlueprintError) as captured:
        query_world_blueprint_bundle(
            bundle,
            materialization_root=tmp_path / "unqualified-query",
            query_kind="node",
            member_id="plan_root",
        )

    assert captured.value.code == "WORLD_BLUEPRINT_QUERY_SOURCE_UNQUALIFIED"
    assert captured.value.details["source_gap_ids"]


@pytest.mark.parametrize(
    "retired_field",
    [
        "qualification_report",
        "query_indexes",
        "fixed_query_answers",
        "handoff_answers",
        "handoff_qualification",
    ],
)
def test_bundle_rejects_duplicate_full_derived_payload_fields(
    tmp_path: Path,
    retired_field: str,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle = write_world_blueprint_bundle(
        blueprint, tmp_path / "planning-workflow.bundle.json"
    )
    tampered = deepcopy(bundle)
    tampered[retired_field] = {"forged": "duplicate derived authority"}
    _refresh_logical_fingerprint(tampered)

    with pytest.raises(BlueprintError) as captured:
        verify_world_blueprint_bundle(
            tampered,
            materialization_root=tmp_path / f"duplicate-{retired_field}",
        )

    assert captured.value.code == "WORLD_BLUEPRINT_BUNDLE_SHAPE_INVALID"
    assert retired_field in captured.value.details["retired_derived_fields"]


@pytest.mark.parametrize(
    "protected_destination",
    [
        FIXTURE,
        FIXTURE.parent / "support" / "tests.json",
    ],
)
def test_bundle_export_cannot_overwrite_blueprint_or_replay_resource(
    protected_destination: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    before = protected_destination.read_bytes()

    with pytest.raises(BlueprintError) as captured:
        write_world_blueprint_bundle(blueprint, protected_destination)

    assert captured.value.code == "WORLD_BLUEPRINT_BUNDLE_DESTINATION_PROTECTED"
    assert protected_destination.read_bytes() == before


def test_bundle_export_rejects_linked_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    destination = tmp_path / "linked.bundle.json"
    real_link_check = bundle_module._is_link_or_reparse

    def linked_destination(path: Path) -> bool:
        return path == destination or real_link_check(path)

    monkeypatch.setattr(
        bundle_module, "_is_link_or_reparse", linked_destination
    )

    with pytest.raises(BlueprintError) as captured:
        write_world_blueprint_bundle(blueprint, destination)

    assert captured.value.code == "WORLD_BLUEPRINT_BUNDLE_DESTINATION_LINKED"
    assert not destination.exists()


def test_bundle_export_partial_temp_write_preserves_existing_destination(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    destination = tmp_path / "existing.bundle.json"
    destination.write_bytes(b"previous-valid-bundle")

    def partial_write(path: Path, content: bytes) -> None:
        path.write_bytes(content[:17])

    monkeypatch.setattr(
        bundle_module, "_write_bundle_temp_file", partial_write
    )

    with pytest.raises(BlueprintError) as captured:
        write_world_blueprint_bundle(blueprint, destination)

    assert (
        captured.value.code
        == "WORLD_BLUEPRINT_BUNDLE_EXPORT_TEMP_VALIDATION_FAILED"
    )
    assert destination.read_bytes() == b"previous-valid-bundle"
    assert not list(
        tmp_path.glob(f".{destination.name}.worldguard-bundle-*.tmp")
    )


def test_bundle_export_and_verify_have_one_public_cli_route(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bundle_path = tmp_path / "cli" / "planning-workflow.bundle.json"

    export_exit = main(
        [
            "blueprint",
            "bundle-export",
            "--blueprint",
            str(FIXTURE),
            "--destination",
            str(bundle_path),
        ]
    )
    export_result = json.loads(capsys.readouterr().out)
    verify_exit = main(
        [
            "blueprint",
            "bundle-verify",
            "--bundle",
            str(bundle_path),
            "--materialization-root",
            str(tmp_path / "cli-isolated"),
        ]
    )
    verify_result = json.loads(capsys.readouterr().out)
    query_exit = main(
        [
            "blueprint",
            "bundle-query",
            "--bundle",
            str(bundle_path),
            "--materialization-root",
            str(tmp_path / "cli-query-isolated"),
            "--kind",
            "node",
            "--id",
            "plan_root",
        ]
    )
    query_result = json.loads(capsys.readouterr().out)

    assert export_exit == verify_exit == query_exit == 0
    assert export_result["native_handoff_qualified"] is True
    assert export_result["object_dna_handoff_qualified"] is False
    assert export_result["object_census_first_gap"]["code"] == (
        "object-census-trust-not-licensed"
    )
    assert export_result["full_cross_artifact_handoff_qualified"] is False
    assert verify_result["native_handoff_qualified"] is True
    assert verify_result["object_dna_handoff_qualified"] is False
    assert verify_result["object_census"]["authority_licensed"] is False
    assert verify_result["cross_artifact_projection_status"] == "not_run"
    assert query_result["query_kind"] == "node"
    assert query_result["object_dna_qualified"] is False
    assert query_result["object_census"]["first_gap"]["code"] == (
        "object-census-trust-not-licensed"
    )
    assert query_result["slice"]["node_id"] == "plan_root"


def test_fresh_process_uses_only_portable_runtime_and_bundle(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(FIXTURE)
    bundle_path = tmp_path / "handoff" / "planning-workflow.bundle.json"
    bundle = write_world_blueprint_bundle(blueprint, bundle_path)
    portable_runtime = tmp_path / "standalone-portable-runtime"
    shutil.copytree(ROOT / "skills/worldguard/runtime", portable_runtime)
    fresh_cwd = tmp_path / "fresh-process"
    fresh_cwd.mkdir()
    verification_root = fresh_cwd / "materialized"
    script = "\n".join(
        [
            "import json",
            "import sys",
            "from pathlib import Path",
            f"forbidden_root = Path({str(ROOT)!r}).resolve()",
            "def reject_source_checkout_reads(event, args):",
            "    if event != 'open' or not args:",
            "        return",
            "    try:",
            "        candidate = Path(args[0]).resolve()",
            "    except (TypeError, OSError):",
            "        return",
            "    if candidate.is_relative_to(forbidden_root):",
            "        raise RuntimeError(f'forbidden source checkout read: {candidate}')",
            "sys.addaudithook(reject_source_checkout_reads)",
            "import worldguard",
            "from worldguard.blueprint_bundle import query_world_blueprint_bundle, verify_world_blueprint_bundle",
            f"runtime_root = Path({str(portable_runtime)!r}).resolve()",
            "module_path = Path(worldguard.__file__).resolve()",
            "assert module_path.is_relative_to(runtime_root), (module_path, runtime_root)",
            "result = verify_world_blueprint_bundle(",
            f"    Path({str(bundle_path)!r}),",
            f"    materialization_root=Path({str(verification_root)!r}),",
            ")",
            "query = query_world_blueprint_bundle(",
            f"    Path({str(bundle_path)!r}),",
            f"    materialization_root=Path({str(fresh_cwd / 'query-materialized')!r}),",
            "    query_kind='behavior-case',",
            "    member_id='case:actor_alex:good',",
            ")",
            "print(json.dumps({'module_path': str(module_path), 'result': result, 'query': query}, sort_keys=True))",
        ]
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(portable_runtime)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    isolated_home = tmp_path / "fresh-home"
    isolated_home.mkdir()
    environment["HOME"] = str(isolated_home)
    environment["USERPROFILE"] = str(isolated_home)
    environment["PWD"] = str(fresh_cwd)
    environment.pop("OLDPWD", None)
    environment.pop("PYTHONHOME", None)
    environment.pop("VIRTUAL_ENV", None)

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=fresh_cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["result"]["logical_bundle_fingerprint"] == bundle[
        "logical_bundle_fingerprint"
    ]
    assert result["result"]["native_handoff_qualified"] is True
    assert result["result"]["full_cross_artifact_handoff_qualified"] is False
    assert result["result"]["cross_artifact_projection_status"] == "not_run"
    assert result["query"]["query_kind"] == "behavior-case"
    assert result["query"]["slice"]["case"]["case_id"] == "case:actor_alex:good"


def test_fresh_process_recovers_all_seven_guard_oracles_without_source_reads(
    tmp_path: Path,
) -> None:
    blueprint = load_world_blueprint(SEVEN_GUARD_HANDOFF_FIXTURE)
    bundle_path = tmp_path / "handoff" / "seven-guard.bundle.json"
    bundle = write_world_blueprint_bundle(blueprint, bundle_path)
    portable_runtime = tmp_path / "standalone-portable-runtime"
    shutil.copytree(ROOT / "skills/worldguard/runtime", portable_runtime)
    fresh_cwd = tmp_path / "fresh-seven-guard-process"
    fresh_cwd.mkdir()
    case_ids = [
        case_id
        for case_pair in SEVEN_GUARD_CASES.values()
        for case_id in case_pair
    ] + list(SEVEN_GUARD_ADMISSION_CASES)
    script = "\n".join(
        [
            "import json",
            "import sys",
            "from pathlib import Path",
            f"forbidden_root = Path({str(ROOT)!r}).resolve()",
            "def reject_source_checkout_reads(event, args):",
            "    if event != 'open' or not args:",
            "        return",
            "    try:",
            "        candidate = Path(args[0]).resolve()",
            "    except (TypeError, OSError):",
            "        return",
            "    if candidate.is_relative_to(forbidden_root):",
            "        raise RuntimeError(f'forbidden source checkout read: {candidate}')",
            "sys.addaudithook(reject_source_checkout_reads)",
            "import worldguard",
            "from worldguard.blueprint_bundle import query_world_blueprint_bundle, verify_world_blueprint_bundle",
            f"runtime_root = Path({str(portable_runtime)!r}).resolve()",
            "module_path = Path(worldguard.__file__).resolve()",
            "assert module_path.is_relative_to(runtime_root), (module_path, runtime_root)",
            "verification = verify_world_blueprint_bundle(",
            f"    Path({str(bundle_path)!r}),",
            f"    materialization_root=Path({str(fresh_cwd / 'verification')!r}),",
            ")",
            f"case_ids = {case_ids!r}",
            "queries = {}",
            "for index, case_id in enumerate(case_ids):",
            "    queries[case_id] = query_world_blueprint_bundle(",
            f"        Path({str(bundle_path)!r}),",
            f"        materialization_root=Path({str(fresh_cwd)!r}) / f'query-{{index}}',",
            "        query_kind='behavior-case',",
            "        member_id=case_id,",
            "    )",
            "summary = {",
            "    case_id: {",
            "        'kind': row['slice']['case']['case_kind'],",
            "        'oracle_id': row['slice']['case']['oracle_id'],",
            "        'boundary': row['claim_boundary'],",
            "        'observation': row['slice']['native_oracle_observation'],",
            "        'receipt': row['slice']['native_execution_receipt_fingerprint'],",
            "    }",
            "    for case_id, row in queries.items()",
            "}",
            "print(json.dumps({'module_path': str(module_path), 'verification': verification, 'cases': summary}, sort_keys=True))",
        ]
    )
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(portable_runtime)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    isolated_home = tmp_path / "fresh-seven-guard-home"
    isolated_home.mkdir()
    environment["HOME"] = str(isolated_home)
    environment["USERPROFILE"] = str(isolated_home)
    environment["PWD"] = str(fresh_cwd)
    environment.pop("OLDPWD", None)
    environment.pop("PYTHONHOME", None)
    environment.pop("VIRTUAL_ENV", None)

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=fresh_cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["verification"]["status"] == "PASS"
    assert result["verification"]["logical_bundle_fingerprint"] == bundle[
        "logical_bundle_fingerprint"
    ]
    assert set(result["cases"]) == set(case_ids)
    for owner_guard, (good_id, bad_id) in SEVEN_GUARD_CASES.items():
        good = result["cases"][good_id]
        bad = result["cases"][bad_id]
        assert good["kind"] == "known_good"
        assert bad["kind"] == "known_bad"
        assert good["oracle_id"] == f"oracle:worldguard:{owner_guard}:known-good"
        assert bad["oracle_id"].startswith(f"oracle:worldguard:{owner_guard}:")
        assert good["observation"]["passed"] is True
        assert bad["observation"]["passed"] is True
        assert good["boundary"] == blueprint.declared_boundary
        assert bad["boundary"] == blueprint.declared_boundary
        assert good["receipt"] == bad["receipt"]
    for case_id in SEVEN_GUARD_ADMISSION_CASES:
        admission = result["cases"][case_id]
        assert admission["kind"] == "admission_bad"
        assert admission["observation"]["passed"] is True
        assert admission["observation"]["observed_status"] == "REJECTED"
        assert admission["boundary"] == blueprint.declared_boundary
