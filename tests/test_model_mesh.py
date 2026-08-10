import json

import pytest
import yaml

from worldguard import ModelMeshContract, MeshReport, run_model_mesh
from worldguard.cli import main
from worldguard.status import GuardStatus
from tests.helpers import attach_task_purpose_declarations


@pytest.mark.parametrize(
    "payload",
    [
        {"mesh_id": "m", "semantic_coverage_contract": {}},
        {"mesh_id": "m", "coverage_contract": {}},
        {"mesh_id": "m", "semantic_coverage": {"expected_node_ids": []}},
        {"mesh_id": "m", "semantic_coverage": {"excluded_nodes": []}},
        {"mesh_id": "m", "semantic_coverage": {"per_object_coverage": {}}},
        {"mesh_id": "m", "semantic_coverage": {"expected_child_ids": []}},
        {
            "mesh_id": "m",
            "semantic_coverage": {"horizon": {"timepoint_ids": ["t0"]}},
        },
    ],
)
def test_retired_mesh_fields_fail_instead_of_falling_back(payload):
    with pytest.raises(ValueError, match="retired"):
        ModelMeshContract.from_dict(payload)


def pass_mesh():
    mesh = {
        "mesh_id": "mesh-pass",
        "run_id": "mesh-test",
        "nodes": [
            {
                "model_id": "event-source",
                "model_version": "v1",
                "freshness_status": "current",
                "output_ports": [
                    {"port_id": "ready", "value_type": "fact", "cardinality": "one"},
                    {"port_id": "secret", "value_type": "fact", "cardinality": "one"},
                    {"port_id": "unexpected", "value_type": "fact", "cardinality": "one"},
                ],
                "authority": {"owns": ["event"], "excludes": ["norm"]},
                "contract": {
                    "contract_id": "event-contract",
                    "run_id": "mesh-test",
                    "claim": {
                        "claim_id": "event-claim",
                        "text": "operator starts after precheck",
                        "target_guards": ["EventGuard"],
                        "requested_semantics": ["event"],
                    },
                    "world_model": {"model_id": "event-model", "model_version": "v1"},
                    "inputs": {
                        "events": [
                            {"event_id": "e1", "at": "t0", "initiates": "ready"}
                        ]
                    },
                },
            },
            {
                "model_id": "norm-target",
                "model_version": "v1",
                "freshness_status": "current",
                "input_ports": [
                    {"port_id": "condition", "value_type": "fact", "cardinality": "one"}
                ],
                "authority": {"owns": ["norm"], "excludes": ["resource"]},
                "contract": {
                    "contract_id": "norm-contract",
                    "run_id": "mesh-test",
                    "claim": {
                        "claim_id": "norm-claim",
                        "text": "operator may start",
                        "target_guards": ["NormGuard"],
                        "requested_semantics": ["norm"],
                    },
                    "world_model": {"model_id": "norm-model", "model_version": "v1"},
                    "inputs": {
                        "norms": [
                            {
                                "modality": "permitted",
                                "action": "start",
                                "condition": "precheck_complete",
                            }
                        ],
                    "facts": [
                        {"fact_id": "precheck_complete", "value": True}
                    ],
                    },
                },
            },
        ],
        "edges": [
            {
                "edge_id": "event-to-norm",
                "source_model_id": "event-source",
                "target_model_id": "norm-target",
                "relation": "consumes_output_of",
                "port_mappings": [
                    {
                        "mapping_id": "ready-to-condition",
                        "source_port_id": "ready",
                        "target_port_id": "condition",
                    }
                ],
                "allowed_use": ["ready"],
                "forbidden_use": [],
                "read_only": True,
                "requires_current_source": True,
            }
        ],
    }
    attach_task_purpose_declarations(
        mesh["nodes"][0]["contract"], guards=["EventGuard"]
    )
    attach_task_purpose_declarations(
        mesh["nodes"][1]["contract"], guards=["NormGuard"]
    )
    return mesh


def test_model_mesh_pass_preserves_child_ledgers():
    report = run_model_mesh(pass_mesh())

    assert report.status == GuardStatus.PASS
    assert set(report.node_reports) == {"event-source", "norm-target"}
    assert any(entry.channel == "event" for entry in report.aggregate_ledger)
    assert any(entry.channel == "norm" for entry in report.aggregate_ledger)


def test_child_gap_prevents_mesh_pass_and_preserves_gap_ledger():
    mesh = pass_mesh()
    mesh["nodes"][0]["contract"]["inputs"] = {}

    report = run_model_mesh(mesh)

    assert report.status == GuardStatus.GAP
    assert any(entry.channel == "gap" for entry in report.aggregate_ledger)


def test_authority_excluded_semantic_marks_boundary():
    mesh = pass_mesh()
    mesh["nodes"][1]["authority"]["excludes"] = ["norm"]

    report = run_model_mesh(mesh)

    assert report.status == GuardStatus.BOUNDARY_EXCEEDED
    assert any(finding.code == "MESH_AUTHORITY_EXCLUDED_SEMANTIC" for finding in report.findings)


def test_forbidden_handoff_use_fails_mesh():
    mesh = pass_mesh()
    mesh["edges"][0]["port_mappings"][0]["source_port_id"] = "secret"
    mesh["edges"][0]["forbidden_use"] = ["secret"]

    report = run_model_mesh(mesh)

    assert report.status == GuardStatus.FAIL
    assert any(finding.code == "MESH_FORBIDDEN_DOWNSTREAM_USE" for finding in report.findings)


def test_unallowed_handoff_use_marks_boundary():
    mesh = pass_mesh()
    mesh["edges"][0]["port_mappings"][0]["source_port_id"] = "unexpected"
    mesh["edges"][0]["allowed_use"] = ["ready"]

    report = run_model_mesh(mesh)

    assert report.status == GuardStatus.BOUNDARY_EXCEEDED
    assert any(finding.code == "MESH_UNALLOWED_DOWNSTREAM_USE" for finding in report.findings)


def test_stale_source_creates_gap_when_current_source_required():
    mesh = pass_mesh()
    mesh["nodes"][0]["freshness_status"] = "stale"

    report = run_model_mesh(mesh)

    assert report.status == GuardStatus.GAP
    assert any(finding.code == "MESH_STALE_SOURCE" for finding in report.findings)


def test_dependency_cycle_fails_mesh():
    mesh = {
        "mesh_id": "cycle-mesh",
        "run_id": "mesh-test",
        "nodes": [{"model_id": "a"}, {"model_id": "b"}],
        "edges": [
            {
                "edge_id": "a-b",
                "source_model_id": "a",
                "target_model_id": "b",
                "relation": "depends_on",
            },
            {
                "edge_id": "b-a",
                "source_model_id": "b",
                "target_model_id": "a",
                "relation": "depends_on",
            },
        ],
    }

    report = run_model_mesh(mesh)

    assert report.status == GuardStatus.FAIL
    assert any(finding.code == "MESH_DEPENDENCY_CYCLE" for finding in report.findings)


def test_unknown_relation_and_missing_transfer_mapping_fail_closed() -> None:
    unknown = pass_mesh()
    unknown["edges"][0]["relation"] = "looks_like_dependency"
    with pytest.raises(ValueError, match="unknown model edge relation"):
        ModelMeshContract.from_dict(unknown)

    missing = pass_mesh()
    missing["edges"][0]["port_mappings"] = []
    with pytest.raises(ValueError, match="requires port_mappings"):
        ModelMeshContract.from_dict(missing)


def test_incompatible_transfer_ports_fail_with_exact_mapping() -> None:
    mesh = pass_mesh()
    mesh["nodes"][1]["input_ports"][0]["value_type"] = "resource"

    report = run_model_mesh(mesh)

    assert report.status == GuardStatus.FAIL
    mismatch = next(
        finding
        for finding in report.findings
        if finding.code == "MESH_INCOMPATIBLE_PORT_MAPPING"
    )
    assert mismatch.evidence["mapping"]["mapping_id"] == "ready-to-condition"


@pytest.mark.parametrize(
    ("mapping_field", "unknown_port", "expected_code"),
    [
        ("source_port_id", "unknown-source", "MESH_UNKNOWN_SOURCE_PORT"),
        ("target_port_id", "unknown-target", "MESH_UNKNOWN_TARGET_PORT"),
    ],
)
def test_unknown_transfer_ports_fail_closed(
    mapping_field: str,
    unknown_port: str,
    expected_code: str,
) -> None:
    mesh = pass_mesh()
    mesh["edges"][0]["port_mappings"][0][mapping_field] = unknown_port

    report = run_model_mesh(mesh)

    assert report.status == GuardStatus.FAIL
    finding = next(item for item in report.findings if item.code == expected_code)
    assert finding.evidence["mapping"][mapping_field] == unknown_port


def test_transfer_port_cardinality_mismatch_fails_closed() -> None:
    mesh = pass_mesh()
    mesh["nodes"][1]["input_ports"][0]["cardinality"] = "many"

    report = run_model_mesh(mesh)

    assert report.status == GuardStatus.FAIL
    mismatch = next(
        finding
        for finding in report.findings
        if finding.code == "MESH_INCOMPATIBLE_PORT_MAPPING"
    )
    assert mismatch.evidence["source_port"]["cardinality"] == "one"
    assert mismatch.evidence["target_port"]["cardinality"] == "many"


@pytest.mark.parametrize(
    ("edge_field", "expected_code"),
    [
        ("source_model_id", "MESH_MISSING_SOURCE_NODE"),
        ("target_model_id", "MESH_MISSING_TARGET_NODE"),
    ],
)
def test_missing_handoff_endpoint_remains_a_visible_gap(
    edge_field: str,
    expected_code: str,
) -> None:
    mesh = pass_mesh()
    mesh["edges"][0][edge_field] = "missing-model"

    report = run_model_mesh(mesh)

    assert report.status == GuardStatus.GAP
    assert any(finding.code == expected_code for finding in report.findings)


def test_edge_boundary_and_type_checks_remain_reachable_together() -> None:
    mesh = pass_mesh()
    mesh["edges"][0]["port_mappings"][0]["source_port_id"] = "secret"
    mesh["edges"][0]["forbidden_use"] = ["secret"]
    mesh["edges"][0]["allowed_use"] = ["ready"]
    mesh["nodes"][1]["input_ports"][0]["value_type"] = "resource"

    report = run_model_mesh(mesh)
    codes = {finding.code for finding in report.findings}

    assert {
        "MESH_FORBIDDEN_DOWNSTREAM_USE",
        "MESH_UNALLOWED_DOWNSTREAM_USE",
        "MESH_INCOMPATIBLE_PORT_MAPPING",
    } <= codes


def test_public_api_exports_model_mesh():
    mesh = ModelMeshContract.from_dict(pass_mesh())
    report = run_model_mesh(mesh)

    assert isinstance(report, MeshReport)


def test_cli_mesh_check_outputs_json(tmp_path, capsys):
    path = tmp_path / "mesh.yaml"
    path.write_text(yaml.safe_dump(pass_mesh()), encoding="utf-8")

    assert main(["mesh-check", "--mesh", str(path)]) == 0
    data = json.loads(capsys.readouterr().out)

    assert data["status"] == "PASS"
    assert set(data["node_reports"]) == {"event-source", "norm-target"}
