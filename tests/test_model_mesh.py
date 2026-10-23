import json

import pytest
import yaml

from worldguard import GuardContract, ModelMeshContract, MeshReport, derive_required_guards, run_model_mesh
from worldguard.cli import main
from worldguard.status import GuardStatus


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
                        "asserts": [{"holds": "ready", "at": "t0"}],
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
                        "asserts": [{"action": "start", "modality": "permitted"}],
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
    mesh["nodes"][0]["contract"]
    mesh["nodes"][1]["contract"]
    return mesh


def test_model_mesh_pass_preserves_child_ledgers():
    report = run_model_mesh(pass_mesh())

    assert report.status == GuardStatus.PASS
    assert set(report.node_reports) == {"event-source", "norm-target"}
    assert report.node_reports["event-source"].guard_results[0].guard == "EventGuard"
    assert report.node_reports["norm-target"].guard_results[0].guard == "NormGuard"


def test_child_gap_prevents_mesh_pass_and_preserves_gap_ledger():
    mesh = pass_mesh()
    mesh["nodes"][0]["contract"]["inputs"] = {}

    report = run_model_mesh(mesh)

    assert report.status == GuardStatus.GAP
    assert any(row["status"] == "GAP" for row in report.to_dict()["gaps"])


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

    assert main(["mesh-check", "--mesh", str(path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)

    assert data["status"] == "PASS"
    assert set(data["nodes"]) == {"event-source", "norm-target"}


def test_mesh_node_claims_must_be_bound_to_their_models():
    unbound = pass_mesh()
    del unbound["nodes"][1]["contract"]["claim"]["asserts"]
    report = run_model_mesh(unbound)
    assert report.status == GuardStatus.GAP
    assert [gap["code"] for gap in report.node_reports["norm-target"].gaps] == ["CLAIM_NOT_BOUND"]

    contradicted = pass_mesh()
    contradicted["nodes"][1]["contract"]["claim"]["asserts"] = [{"action": "start", "modality": "forbidden"}]
    report = run_model_mesh(contradicted)
    assert report.status == GuardStatus.FAIL


def _claim_atoms_mesh():
    return {'mesh_id': 'predictive-mesh',
     'run_id': 'predictive-test',
     'nodes': [{'model_id': 'world',
                'authority': {'owns': ['event', 'causal']},
                'contract': {'contract_id': 'predictive-contract',
                             'run_id': 'predictive-test',
                             'claim': {'claim_id': 'forecast-claim',
                                       'text': 'forecast state under declared scenarios',
                                       'target_guards': ['EventGuard', 'CausalGuard'],
                                       'atoms': [{'atom_id': 'forecast-atom',
                                                  'text': 'state changes under intervention',
                                                  'requested_semantics': ['event', 'causal'],
                                                  'predictive_intent': True}],
                                       'asserts': [{'holds': 'ready', 'at': 't0'}]},
                             'world_model': {'model_id': 'world-model', 'model_version': 'v1'},
                             'inputs': {'variable_observations': {'y': ['t0', 't1', 't2']},
                                        'events': [{'event_id': 'e0',
                                                    'at': 't0',
                                                    'initiates': 'ready',
                                                    'branch_id': 'b0',
                                                    'perturbation_id': 'p0'},
                                                   {'event_id': 'e1',
                                                    'at': 't1',
                                                    'terminates': 'ready',
                                                    'initiates': 'running'},
                                                   {'event_id': 'e2',
                                                    'at': 't2',
                                                    'initiates': 'running'}],
                                        'causal_model': {'variables': ['y'],
                                                         'equations': {'y': 'x * 2'},
                                                         'exogenous': ['x'],
                                                         'graph': [],
                                                         'scenarios': {'s-base': {'x': 1}},
                                                         'holdout_scenarios': {'s-hold': {'x': 3}},
                                                         'interventions': [{'intervention_id': 'do-y',
                                                                            'scenario_id': 's-base',
                                                                            'set': {'y': 10}}],
                                                         'counterfactuals': [{'counterfactual_id': 'cf-y',
                                                                              'intervention_id': 'do-y',
                                                                              'query': 'y'}]}}}}]}


def test_structured_claim_atoms_derive_required_guards() -> None:
    contract = GuardContract.from_dict(_claim_atoms_mesh()["nodes"][0]["contract"])

    assert derive_required_guards(contract.claim) == ("EventGuard", "CausalGuard")
    assert contract.claim.atoms[0].atom_id == "forecast-atom"
    assert contract.to_dict()["claim"]["atoms"][0]["predictive_intent"] is True


def test_omitted_target_guard_does_not_skip_the_derived_guard_in_a_mesh() -> None:
    mesh = _claim_atoms_mesh()
    mesh["nodes"][0]["contract"]["claim"]["target_guards"] = ["EventGuard"]

    report = run_model_mesh(mesh)

    assert report.status == run_model_mesh(_claim_atoms_mesh()).status
    assert not any(
        finding.code == "MESH_CLAIM_DERIVED_GUARD_MISSING"
        for finding in report.findings
    )
    assert "CausalGuard" in report.node_reports["world"].derived_guards


def test_expected_contractless_node_is_counted_and_blocks_aggregate_pass():
    report = run_model_mesh({"mesh_id": "contractless", "nodes": [{"model_id": "missing-contract"}]})
    assert report.status == GuardStatus.GAP
    assert report.to_dict()["checked"] == {"nodes": 1, "edges": 0}
    assert "missing-contract" not in report.node_reports
    assert any(finding.code == "MESH_EXPECTED_NODE_CONTRACT_MISSING" for finding in report.findings)


def test_retired_semantic_coverage_cli_is_a_typed_input_error(tmp_path, capsys):
    path = tmp_path / "retired.json"
    path.write_text(json.dumps({"mesh_id": "old", "semantic_coverage": {"profile": "bounded"}}))
    assert main(["mesh-check", "--mesh", str(path)]) == 2
    error = json.loads(capsys.readouterr().out)["error"]
    assert error["code"] == "WORLDGUARD_INPUT_INVALID"
    assert error["message"] == "semantic_coverage is retired; every node in the mesh is checked"
