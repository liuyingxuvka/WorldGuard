from __future__ import annotations

import hashlib
import json
import runpy
import shutil
import zlib
import base64
from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from tests.object_census_fixtures import (
    OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR_FINGERPRINT,
    signed_object_census,
    signed_object_census_from_source,
)
from worldguard.blueprint import (
    BlueprintBinding,
    BlueprintError,
    WorldBlueprintContract,
    _binding_receipt_fingerprint,
    check_world_blueprint,
    compile_behavior_commitment_inventory_cache,
    load_world_blueprint,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests/fixtures/world_blueprint"
PLANNING_FIXTURE = FIXTURE_ROOT / "planning_workflow_three_level.yaml"
POLICY_FIXTURE = FIXTURE_ROOT / "policy_access_execution.yaml"
SEVEN_GUARD_FIXTURE = FIXTURE_ROOT / "seven_guard_portable_handoff.json"
FIXTURE_COMPILER = ROOT / "scripts/refresh_world_blueprint_external_dna_fixtures.py"


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
    )


def _file_fingerprint(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


ZERO_SHA256 = "sha256:" + "0" * 64


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _value_fingerprint(value: object) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _input_ref(payload: dict, input_kind: str) -> dict:
    return next(
        row
        for row in payload["commitment_inventory"]["input_refs"]
        if row["input_kind"] == input_kind
    )


def _contract(payload: dict, *, source_root: Path) -> WorldBlueprintContract:
    current = deepcopy(payload)
    current.pop("blueprint_fingerprint", None)
    return WorldBlueprintContract.from_dict(current, source_root=source_root)


def _renew_signed_census(
    payload: dict,
    *,
    source_root: Path,
) -> dict:
    source_ref = _input_ref(payload, "target_object_census_source")
    source = _read_json(source_root / source_ref["locator"])
    census_ref = _input_ref(payload, "target_object_census_authority")
    census_path = source_root / census_ref["locator"]
    input_fingerprints = {
        input_kind: _input_ref(payload, input_kind)["content_fingerprint"]
        for input_kind in (
            "request_contract",
            "target_material",
            "target_object_census_source",
            "target_semantic_authority",
        )
    }
    record = signed_object_census_from_source(
        source,
        input_fingerprints=input_fingerprints,
    )
    _write_json(census_path, record)
    census_ref["content_fingerprint"] = _file_fingerprint(census_path)
    return record


def _refresh_binding_receipt(
    payload: dict,
    *,
    source_root: Path,
    binding_id: str,
) -> None:
    binding = next(row for row in payload["bindings"] if row["binding_id"] == binding_id)
    path_text, separator, selector = binding["locator"].partition("#")
    path = source_root / path_text
    content: bytes
    if separator:
        content = _canonical_json_bytes(_read_json(path)[selector])
    else:
        content = path.read_bytes()
    binding["content_fingerprint"] = "sha256:" + hashlib.sha256(content).hexdigest()
    candidate = BlueprintBinding.from_dict(
        {**binding, "receipt_fingerprint": ZERO_SHA256}
    )
    binding["receipt_fingerprint"] = _binding_receipt_fingerprint(candidate)


def _refresh_commitment_cache(payload: dict, *, source_root: Path) -> None:
    cache_path = source_root / payload["commitment_inventory"]["locator"]
    contract = _contract(payload, source_root=source_root)
    _write_json(cache_path, compile_behavior_commitment_inventory_cache(contract))


@pytest.mark.parametrize("fixture", [PLANNING_FIXTURE, POLICY_FIXTURE])
def test_integrated_target_has_separate_candidate_and_object_dna_qualification(
    fixture: Path,
) -> None:
    blueprint = load_world_blueprint(fixture)
    default_report = check_world_blueprint(blueprint)

    assert default_report.status == "PASS"
    assert default_report.native_domain_qualified is True
    assert default_report.object_dna_qualified is False
    assert default_report.object_census["authority_status"] == "valid"
    assert default_report.object_census["coverage_complete"] is True
    assert default_report.object_census["independent_discovery_current"] is True
    assert default_report.object_census["test_execution_status"] == "passed"
    assert default_report.object_census["evidence_alignment_status"] == "aligned"
    assert default_report.object_census["authority_licensed"] is False
    assert default_report.object_census["first_gap"]["code"] == (
        "object-census-trust-not-licensed"
    )

    authority_report = check_world_blueprint(
        blueprint,
        trusted_object_census_authority_fingerprints=[
            default_report.object_census["authority_fingerprint"]
        ],
    )
    producer_report = check_world_blueprint(
        blueprint,
        trusted_object_census_producer_descriptor_fingerprints=[
            OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR_FINGERPRINT
        ],
    )

    assert authority_report.object_dna_qualified is True
    assert authority_report.object_census["first_gap"] is None
    assert producer_report.object_dna_qualified is True
    assert producer_report.object_census["producer_revision_licensed"] is True
    assert producer_report.object_census["first_gap"] is None
    for receipt in producer_report.object_census[
        "external_test_execution_receipts"
    ]:
        assert receipt["terminal_status"] == "PASS"
        assert receipt["target_id"] == blueprint.target_id
        assert receipt["target_revision"] == blueprint.target_revision
        assert receipt["inputs_fingerprint"].startswith("sha256:")
        assert receipt["oracle_fingerprint"].startswith("sha256:")
        assert receipt["result_fingerprint"].startswith("sha256:")
        assert receipt["producer_id"]
        assert receipt["freshness_status"] == "current"


def test_seven_guard_matrix_is_explicitly_a_capability_fixture_not_object_dna() -> None:
    report = check_world_blueprint(
        load_world_blueprint(SEVEN_GUARD_FIXTURE),
        trusted_object_census_producer_descriptor_fingerprints=[
            OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR_FINGERPRINT
        ],
    )

    assert report.status == "PASS"
    assert report.native_domain_qualified is True
    assert report.object_dna_qualified is False
    assert report.object_census["producer_trusted"] is True
    assert report.object_census["producer_revision_licensed"] is False
    assert report.object_census["authority_licensed"] is False
    assert report.object_census["independent_discovery_status"] == (
        "candidate_consistency"
    )
    assert report.object_census["object_claim_kind"] == (
        "oracle_carrying_capability_fixture"
    )
    assert report.object_census["first_gap"]["code"] == (
        "object-claim-kind-not-integrated-target"
    )


def test_stale_signed_census_blocks_changed_target_input(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(FIXTURE_ROOT, fixture_root)
    payload = yaml.safe_load(
        (fixture_root / PLANNING_FIXTURE.name).read_text(encoding="utf-8")
    )
    material_ref = _input_ref(payload, "target_material")
    material_path = fixture_root / material_ref["locator"]
    material = _read_json(material_path)
    material["workflow_record_assignment"]["task"] = "changed-without-census-renewal"
    _write_json(material_path, material)
    material_ref["content_fingerprint"] = _file_fingerprint(material_path)

    report = check_world_blueprint(_contract(payload, source_root=fixture_root))

    gap = next(
        row
        for row in report.gaps
        if row.code == "WORLD_BLUEPRINT_OBJECT_CENSUS_DENOMINATOR_MISMATCH"
    )
    assert gap.evidence["input_fingerprint_mismatches"]["target_material"]
    assert report.native_domain_qualified is False
    assert report.object_dna_qualified is False


def test_fixture_census_source_is_compiled_only_from_raw_request_and_target(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(FIXTURE_ROOT, fixture_root)
    compiler = runpy.run_path(str(FIXTURE_COMPILER))[
        "_compile_census_source_from_raw_inputs"
    ]
    request_path = fixture_root / "support/behavior-request-contract.json"
    material_path = fixture_root / "support/target-material.json"
    first_source_path = fixture_root / "support/discovered-a.json"
    second_source_path = fixture_root / "support/discovered-b.json"

    first = compiler(
        request_path=request_path,
        material_path=material_path,
        census_source_path=first_source_path,
    )

    candidate_path = fixture_root / PLANNING_FIXTURE.name
    candidate = yaml.safe_load(candidate_path.read_text(encoding="utf-8"))
    candidate["elements"] = candidate["elements"][:-1]
    candidate_path.write_text(yaml.safe_dump(candidate), encoding="utf-8")
    semantic_path = fixture_root / "support/target-semantic-authority.json"
    semantic = _read_json(semantic_path)
    semantic["elements"] = semantic["elements"][:-1]
    _write_json(semantic_path, semantic)

    second = compiler(
        request_path=request_path,
        material_path=material_path,
        census_source_path=second_source_path,
    )

    assert first == second
    assert first_source_path.read_bytes() == second_source_path.read_bytes()

    request = _read_json(request_path)
    request["object_census"]["members"][0]["owner_node_id"] = (
        "raw_request_owned_node"
    )
    _write_json(request_path, request)
    changed = compiler(
        request_path=request_path,
        material_path=material_path,
        census_source_path=fixture_root / "support/discovered-changed.json",
    )
    assert changed != first

    material = _read_json(material_path)
    material["foreign_unrequested_material"] = {}
    _write_json(material_path, material)
    with pytest.raises(ValueError, match="raw request/target object-census discovery"):
        compiler(
            request_path=request_path,
            material_path=material_path,
            census_source_path=fixture_root / "support/discovered-invalid.json",
        )


@pytest.mark.parametrize("mutation", ["inverse_expected_output", "foreign_inputs"])
def test_external_test_bytes_cannot_pass_without_exact_executable_contract(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(FIXTURE_ROOT, fixture_root)
    payload = yaml.safe_load(
        (fixture_root / PLANNING_FIXTURE.name).read_text(encoding="utf-8")
    )
    tests_path = fixture_root / "support/tests.json"
    tests = _read_json(tests_path)
    check = tests["check_assignment"]
    if mutation == "inverse_expected_output":
        check["oracle"]["expected_output"]["executed_transition_ids"] = [
            "foreign_transition"
        ]
    else:
        check["inputs"]["event_model"]["guard_values"] = {
            "foreign_guard": True
        }
    _write_json(tests_path, tests)
    _refresh_binding_receipt(
        payload,
        source_root=fixture_root,
        binding_id="assignment_test",
    )
    _refresh_commitment_cache(payload, source_root=fixture_root)

    report = check_world_blueprint(
        _contract(payload, source_root=fixture_root),
        trusted_object_census_producer_descriptor_fingerprints=[
            OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR_FINGERPRINT
        ],
    )

    gap = next(
        row
        for row in report.gaps
        if row.code == "WORLD_BLUEPRINT_EXTERNAL_TEST_EXECUTION_FAILED"
        and row.binding_id == "assignment_test"
    )
    assert gap.evidence["reason"] == "external_test_contract_mismatch"
    assert report.object_census["test_execution_status"] == "failed_or_not_run"
    assert report.object_dna_qualified is False


@pytest.mark.parametrize(
    "mutation", ["observed_false", "foreign_supports", "wrong_observation"]
)
def test_external_evidence_bytes_require_semantic_alignment(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(FIXTURE_ROOT, fixture_root)
    payload = yaml.safe_load(
        (fixture_root / PLANNING_FIXTURE.name).read_text(encoding="utf-8")
    )
    evidence_path = fixture_root / "support/evidence.json"
    evidence = _read_json(evidence_path)
    observation = evidence["evidence_assignment"]
    if mutation == "observed_false":
        observation["observed"] = False
    elif mutation == "foreign_supports":
        observation["supports"] = "foreign_element"
    else:
        observation["observation"] = "Support was observed somewhere else."
    _write_json(evidence_path, evidence)
    _refresh_binding_receipt(
        payload,
        source_root=fixture_root,
        binding_id="assignment_evidence",
    )
    _refresh_commitment_cache(payload, source_root=fixture_root)

    report = check_world_blueprint(
        _contract(payload, source_root=fixture_root),
        trusted_object_census_producer_descriptor_fingerprints=[
            OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR_FINGERPRINT
        ],
    )

    assert any(
        row.code == "WORLD_BLUEPRINT_EXTERNAL_EVIDENCE_SEMANTIC_MISMATCH"
        and row.binding_id == "assignment_evidence"
        for row in report.gaps
    )
    assert report.object_census["evidence_alignment_status"] == (
        "misaligned_or_not_run"
    )
    assert report.object_dna_qualified is False


def test_census_signature_or_authority_fingerprint_tampering_is_visible(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(FIXTURE_ROOT, fixture_root)
    payload = yaml.safe_load(
        (fixture_root / PLANNING_FIXTURE.name).read_text(encoding="utf-8")
    )
    census_ref = _input_ref(payload, "target_object_census_authority")
    census_path = fixture_root / census_ref["locator"]
    census = _read_json(census_path)
    census["authority"]["authority_revision"] = "tampered-revision"
    _write_json(census_path, census)
    census_ref["content_fingerprint"] = _file_fingerprint(census_path)

    report = check_world_blueprint(_contract(payload, source_root=fixture_root))

    assert any(
        row.code == "WORLD_BLUEPRINT_OBJECT_CENSUS_AUTHORITY_INVALID"
        for row in report.gaps
    )
    assert report.object_census["authority_status"] == "invalid"
    assert report.object_dna_qualified is False


@pytest.mark.parametrize("field", ["producer_id", "signing_key_id"])
def test_census_key_or_producer_change_invalidates_signature_and_trust(
    tmp_path: Path,
    field: str,
) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(FIXTURE_ROOT, fixture_root)
    payload = yaml.safe_load(
        (fixture_root / PLANNING_FIXTURE.name).read_text(encoding="utf-8")
    )
    census_ref = _input_ref(payload, "target_object_census_authority")
    census_path = fixture_root / census_ref["locator"]
    census = _read_json(census_path)
    census["producer_descriptor"][field] = f"foreign-{field}"
    _write_json(census_path, census)
    census_ref["content_fingerprint"] = _file_fingerprint(census_path)

    report = check_world_blueprint(
        _contract(payload, source_root=fixture_root),
        trusted_object_census_producer_descriptor_fingerprints=[
            OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR_FINGERPRINT
        ],
    )

    assert report.object_census["authority_status"] == "invalid"
    assert report.object_census["producer_revision_licensed"] is False
    assert report.object_dna_qualified is False


def test_signed_discovery_receipt_cannot_name_a_foreign_source(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(FIXTURE_ROOT, fixture_root)
    payload = yaml.safe_load(
        (fixture_root / PLANNING_FIXTURE.name).read_text(encoding="utf-8")
    )
    census_ref = _input_ref(payload, "target_object_census_authority")
    census_path = fixture_root / census_ref["locator"]
    authority = _read_json(census_path)["authority"]
    receipt = authority["discovery_receipt"]
    receipt["source_id"] = "foreign-object-census-source"
    receipt["receipt_fingerprint"] = _value_fingerprint(
        {
            key: value
            for key, value in receipt.items()
            if key != "receipt_fingerprint"
        }
    )
    _write_json(census_path, signed_object_census(authority))
    census_ref["content_fingerprint"] = _file_fingerprint(census_path)

    report = check_world_blueprint(
        _contract(payload, source_root=fixture_root),
        trusted_object_census_producer_descriptor_fingerprints=[
            OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR_FINGERPRINT
        ],
    )

    gap = next(
        row
        for row in report.gaps
        if row.code == "WORLD_BLUEPRINT_OBJECT_CENSUS_DENOMINATOR_MISMATCH"
    )
    assert "discovery_source_id" in gap.evidence["source_identity_mismatches"]
    assert report.object_census["producer_revision_licensed"] is False
    assert report.object_dna_qualified is False


def test_candidate_derived_coherent_shrink_and_resign_is_not_producer_licensed(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(FIXTURE_ROOT, fixture_root)
    payload = _read_json(fixture_root / SEVEN_GUARD_FIXTURE.name)
    original_census = _read_json(
        fixture_root
        / _input_ref(payload, "target_object_census_authority")["locator"]
    )
    original_authority_fingerprint = original_census["authority_fingerprint"]

    payload["elements"] = [
        row for row in payload["elements"] if row["element_id"] != "matrix_causal_pass"
    ]
    payload["bindings"] = [
        row
        for row in payload["bindings"]
        if row["subject_element_id"] != "matrix_causal_pass"
    ]
    plan_root = next(row for row in payload["nodes"] if row["node_id"] == "plan_root")
    plan_root["owned_element_ids"] = [
        value for value in plan_root["owned_element_ids"] if value != "matrix_causal_pass"
    ]

    request_ref = _input_ref(payload, "request_contract")
    request_path = fixture_root / request_ref["locator"]
    request = _read_json(request_path)
    request["semantic_authority"]["required_element_ids"].remove("matrix_causal_pass")
    request["semantic_authority"]["required_guard_owner_ids"].remove("CausalGuard")
    request_source = request["object_census"]
    request_source["members"] = [
        row for row in request_source["members"]
        if row["element_id"] != "matrix_causal_pass"
    ]
    request_source["required_guard_owner_ids"].remove("CausalGuard")
    request_source["object_claim_kind"] = "integrated_target"
    _write_json(request_path, request)
    request_ref["content_fingerprint"] = _file_fingerprint(request_path)

    semantic_ref = _input_ref(payload, "target_semantic_authority")
    semantic_path = fixture_root / semantic_ref["locator"]
    semantic = _read_json(semantic_path)
    semantic["elements"] = [
        row for row in semantic["elements"] if row["element_id"] != "matrix_causal_pass"
    ]
    _write_json(semantic_path, semantic)
    semantic_ref["content_fingerprint"] = _file_fingerprint(semantic_path)

    source_ref = _input_ref(payload, "target_object_census_source")
    source_path = fixture_root / source_ref["locator"]
    _write_json(source_path, request_source)
    source_ref["content_fingerprint"] = _file_fingerprint(source_path)
    renewed_census = _renew_signed_census(payload, source_root=fixture_root)
    assert renewed_census["authority_fingerprint"] != original_authority_fingerprint

    _refresh_commitment_cache(payload, source_root=fixture_root)
    contract = _contract(payload, source_root=fixture_root)

    frozen_authority_report = check_world_blueprint(
        contract,
        trusted_object_census_authority_fingerprints=[
            original_authority_fingerprint
        ],
    )
    delegated_producer_report = check_world_blueprint(
        contract,
        trusted_object_census_producer_descriptor_fingerprints=[
            OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR_FINGERPRINT
        ],
    )

    assert frozen_authority_report.object_dna_qualified is False
    assert frozen_authority_report.object_census["authority_licensed"] is False
    assert delegated_producer_report.object_dna_qualified is False
    assert delegated_producer_report.object_census[
        "producer_revision_licensed"
    ] is False
    assert delegated_producer_report.object_census["first_gap"]["code"] == (
        "object-census-independent-discovery-not-current"
    )


def test_fixed_raw_request_and_target_block_candidate_owner_shrink(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(FIXTURE_ROOT, fixture_root)
    payload = _read_json(fixture_root / SEVEN_GUARD_FIXTURE.name)
    original_authority_fingerprint = _read_json(
        fixture_root
        / _input_ref(payload, "target_object_census_authority")["locator"]
    )["authority_fingerprint"]

    causal_element = next(
        row for row in payload["elements"] if row["element_id"] == "matrix_causal_pass"
    )
    causal_element["required_binding_roles"] = []
    payload["bindings"] = [
        row
        for row in payload["bindings"]
        if row["subject_element_id"] != "matrix_causal_pass"
    ]

    semantic_ref = _input_ref(payload, "target_semantic_authority")
    semantic_path = fixture_root / semantic_ref["locator"]
    semantic = _read_json(semantic_path)
    causal = next(
        row for row in semantic["elements"] if row["element_id"] == "matrix_causal_pass"
    )
    causal["required_guard_owner_id"] = "not_applicable"
    causal["required_executor_id"] = "worldguard.world-element.applicability.v1"
    causal["required_executor_version"] = "v1"
    causal["binding_responsibilities"] = []
    causal["not_applicable_responsibilities"] = [
        {"role": role, "reason": "candidate-declared not applicable"}
        for role in ("evidence", "native_result", "target_material", "test_check")
    ]
    _write_json(semantic_path, semantic)
    semantic_ref["content_fingerprint"] = _file_fingerprint(semantic_path)
    _renew_signed_census(payload, source_root=fixture_root)

    report = check_world_blueprint(
        _contract(payload, source_root=fixture_root),
        trusted_object_census_authority_fingerprints=[
            original_authority_fingerprint
        ],
    )

    assert any(
        row.code == "WORLD_BLUEPRINT_OBJECT_CENSUS_DENOMINATOR_MISMATCH"
        for row in report.gaps
    )
    assert report.native_domain_qualified is False
    assert report.object_dna_qualified is False


@pytest.mark.parametrize("mutation", ["wrong_target", "reused_id"])
def test_semantic_derivation_cannot_cross_owners_or_reuse_another_element_id(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture_root = tmp_path / "fixture"
    shutil.copytree(FIXTURE_ROOT, fixture_root)
    payload = yaml.safe_load(
        (fixture_root / PLANNING_FIXTURE.name).read_text(encoding="utf-8")
    )
    semantic_ref = _input_ref(payload, "target_semantic_authority")
    semantic_path = fixture_root / semantic_ref["locator"]
    semantic = _read_json(semantic_path)
    allocation = next(
        row for row in semantic["elements"] if row["element_id"] == "allocation_summary"
    )
    if mutation == "wrong_target":
        allocation["derivation_responsibilities"][0]["target_element_id"] = (
            "plan_outcome"
        )
    else:
        governance = next(
            row
            for row in semantic["elements"]
            if row["element_id"] == "governance_summary"
        )
        governance["derivation_responsibilities"][0]["derivation_id"] = (
            allocation["derivation_responsibilities"][0]["derivation_id"]
        )
    _write_json(semantic_path, semantic)
    semantic_ref["content_fingerprint"] = _file_fingerprint(semantic_path)

    report = check_world_blueprint(_contract(payload, source_root=fixture_root))

    gap = next(
        row
        for row in report.gaps
        if row.code == "WORLD_BLUEPRINT_TARGET_SEMANTIC_AUTHORITY_INVALID"
    )
    assert gap.evidence["code"] in {
        "WORLD_BLUEPRINT_TARGET_SEMANTIC_DERIVATION_DENOMINATOR_INVALID",
        "WORLD_BLUEPRINT_TARGET_SEMANTIC_AUTHORITY_DENOMINATOR_INVALID",
    }
    assert report.object_dna_qualified is False


def test_in_memory_object_census_claim_boundary() -> None:
    blueprint = load_world_blueprint(PLANNING_FIXTURE)
    trusted = [OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR_FINGERPRINT]
    report = check_world_blueprint(
        blueprint,
        trusted_object_census_producer_descriptor_fingerprints=trusted,
    )

    assert report.object_dna_qualified is True
    assert report.object_census["authority_licensed"] is True
    assert report.object_census["coverage_complete"] is True
    assert report.object_census["first_gap"] is None


def test_transport_replay_is_retired_even_with_a_trust_context() -> None:
    trusted = [OBJECT_CENSUS_TEST_PRODUCER_DESCRIPTOR_FINGERPRINT]
    import worldguard.blueprint_bundle as bundle_module

    with pytest.raises(BlueprintError) as caught:
        bundle_module.verify_world_blueprint_bundle(
            load_world_blueprint(PLANNING_FIXTURE),
            trusted_object_census_producer_descriptor_fingerprints=trusted,
        )
    assert caught.value.code == "WORLD_BLUEPRINT_NATIVE_DIRECTORY_ONLY"


def test_runtime_and_portable_projection_do_not_contain_test_private_key() -> None:
    marker = "_TEST_CENSUS_PRIVATE_EXPONENT_HEX"
    for package_root in (
        ROOT / "worldguard",
        ROOT / "skills/worldguard/runtime/worldguard",
    ):
        for path in package_root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".json", ".yaml", ".yml"}:
                assert marker not in path.read_text(encoding="utf-8")
