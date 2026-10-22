from __future__ import annotations

from copy import deepcopy

import pytest


from worldguard import (
    GuardedReport,
    ModelMeshContract,
    ProviderStatus,
    QualificationContext,
    SemanticStatus,
    qualification_context_for_node,
    run_model_mesh,
    run_worldguard,
)
from worldguard.status import GuardStatus


def _event_contract() -> dict:
    contract = {
        "contract_id": "qualification:event",
        "run_id": "qualification-test",
        "claim": {
            "claim_id": "claim:event",
            "text": "the declared event makes the plan ready",
            "target_guards": ["EventGuard"],
            "requested_semantics": ["event"],
            "asserts": [{"holds": "ready", "at": "t0"}],
        },
        "world_model": {
            "model_id": "event-world",
            "model_version": "revision-1",
        },
        "inputs": {
            "events": [
                {"event_id": "event-ready", "at": "t0", "initiates": "ready"}
            ]
        },
    }
    return contract


def test_unit_and_one_node_mesh_share_one_qualification_shape() -> None:
    contract = _event_contract()
    mesh_contract = ModelMeshContract.from_dict(
        {
            "mesh_id": "qualification-mesh",
            "nodes": [{"model_id": "event-world", "contract": contract}],
        }
    )
    shared_context = qualification_context_for_node(
        mesh_contract,
        mesh_contract.nodes[0],
    )
    assert "guard_purpose_declarations" not in contract
    unit = run_worldguard(contract, context=shared_context)
    mesh = run_model_mesh(mesh_contract)
    node = mesh.node_reports["event-world"]

    assert node.declared_guards == unit.declared_guards == ["EventGuard"]
    assert node.derived_guards == unit.derived_guards == ["EventGuard"]
    assert (
        node.guard_derivation_fingerprint
        == unit.guard_derivation_fingerprint
    )
    assert [result.to_dict() for result in node.child_results] == [
        result.to_dict() for result in unit.child_results
    ]
    assert [receipt.to_dict() for receipt in node.semantic_receipts] == [
        receipt.to_dict() for receipt in unit.semantic_receipts
    ]
    assert node.provider_states == unit.provider_states
    assert node.rollout_status == unit.rollout_status == SemanticStatus.PASS
    assert node.depth_state == unit.depth_state
    assert node.gaps == unit.gaps == []
    assert node.status == unit.status == GuardStatus.PASS
    assert node.qualification_fingerprint == unit.qualification_fingerprint


def test_derived_guard_omission_is_visible_even_when_owner_can_execute() -> None:
    contract = _event_contract()
    contract["claim"]["target_guards"] = []

    report = run_worldguard(contract)

    assert report.derived_guards == ["EventGuard"]
    assert report.omitted_guards == ["EventGuard"]
    assert len(report.child_results) == 1
    assert len(report.semantic_receipts) == 1
    assert report.structural_status == GuardStatus.PASS
    assert report.semantic_status == SemanticStatus.PASS
    assert report.status == GuardStatus.PASS


def test_unmapped_atom_preserves_claim_and_atom_identity() -> None:
    contract = _event_contract()
    contract["claim"] = {
        "claim_id": "claim:unknown",
        "text": "an unregistered semantic claim",
        "target_guards": [],
        "atoms": [
            {
                "atom_id": "atom:unknown",
                "text": "unknown domain relation",
                "requested_semantics": ["unregistered-domain"],
            }
        ],
    }
    assert "guard_purpose_declarations" not in contract

    report = run_worldguard(contract)

    assert report.unmapped_semantics == [
        {
            "semantic": "unregistered-domain",
            "affected_claim_ids": ["claim:unknown"],
            "affected_atom_ids": ["atom:unknown"],
        }
    ]
    assert report.status == GuardStatus.GAP


def test_unavailable_provider_is_a_typed_non_pass() -> None:
    unavailable = run_worldguard(
        _event_contract(),
        context=QualificationContext(
            node_id="event-world",
            provider_availability={"EventGuard": False},
        ),
    )
    assert unavailable.structural_status == GuardStatus.PASS
    assert unavailable.semantic_status == SemanticStatus.NOT_RUN
    assert unavailable.provider_status == ProviderStatus.UNAVAILABLE
    assert unavailable.status == GuardStatus.GAP

def test_extra_declared_guard_is_reported_and_the_derived_set_runs() -> None:
    contract = _event_contract()
    contract["claim"]["target_guards"] = ["EventGuard", "AgentGuard"]

    report = run_worldguard(contract)

    assert report.derived_guards == ["EventGuard"]
    assert report.unexpected_guards == ["AgentGuard"]
    assert report.effective_guards == ["EventGuard"]
    assert [result.guard for result in report.child_results] == ["EventGuard"]
    assert report.status == GuardStatus.PASS


def test_exact_input_repetition_has_stable_qualification_identity() -> None:
    first = run_worldguard(_event_contract())
    second = run_worldguard(deepcopy(_event_contract()))

    assert first.contract_fingerprint == second.contract_fingerprint
    assert (
        first.guard_derivation_fingerprint
        == second.guard_derivation_fingerprint
    )
    assert first.qualification_fingerprint == second.qualification_fingerprint


def test_unknown_report_field_fails_closed() -> None:
    with pytest.raises(ValueError, match="unknown fields"):
        GuardedReport.validate_payload_fields({"status": "PASS", "legacy": {}})


@pytest.mark.parametrize("file,expected", [
    ("sb_metric_distance.yaml", "BOUNDARY_EXCEEDED"),
    ("sb_numeric_dynamics.yaml", "BOUNDARY_EXCEEDED"),
    ("sb_payoff.yaml", "BOUNDARY_EXCEEDED"),
    ("sb_permission.yaml", "BOUNDARY_EXCEEDED"),
    ("trip_boundary.yaml", "BOUNDARY_EXCEEDED"),
    ("trip_boundary_neg.yaml", "FAIL"),
])
def test_declared_boundary_trials_keep_their_native_status(file, expected, capsys):
    import json
    from pathlib import Path
    from worldguard.cli import main
    path = Path(__file__).parent / "fixtures/trials" / file
    assert main(["check", "--contract", str(path), "--json"]) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == expected
    assert not any(gap["code"] == "QUALIFICATION_SEMANTIC_UNMAPPED" for gap in result["gaps"])


from worldguard.contracts import GUARD_BOUNDARY_SEMANTICS


@pytest.mark.parametrize("guard", list(GUARD_BOUNDARY_SEMANTICS))
def test_each_derived_guard_boundary_is_a_final_boundary(guard):
    import re
    from pathlib import Path
    import yaml
    from tests.helpers import GUARD_SEMANTICS, make_contract
    text = (Path(__file__).parents[1] / "skills/worldguard/references/guard-inputs.md").read_text()
    block, assertion = re.search(rf"^## {guard}\n\n```yaml\n(.*?)```\n\nClaim assertion: `(\{{.*?\}})`", text, re.S | re.M).groups()
    contract = make_contract(guard, inputs=yaml.safe_load(block), asserts=[yaml.safe_load(assertion)],
                            requested_semantics=[GUARD_SEMANTICS[guard], sorted(GUARD_BOUNDARY_SEMANTICS[guard])[0]])
    report = run_worldguard(contract)
    assert report.status == GuardStatus.BOUNDARY_EXCEEDED
    assert report.structural_status == GuardStatus.BOUNDARY_EXCEEDED
    assert report.semantic_status == SemanticStatus.PASS
    assert report.claim_binding["status"] == "PASS"
    assert not any(gap["code"] == "QUALIFICATION_SEMANTIC_UNMAPPED" for gap in report.gaps)


def test_boundary_of_an_unselected_guard_remains_unmapped_with_a_hint():
    contract = _event_contract()
    contract["claim"]["requested_semantics"].append("geometry")
    report = run_worldguard(contract)
    assert report.status == GuardStatus.GAP
    assert report.effective_guards == ["EventGuard"]
    gap = next(gap for gap in report.gaps if gap["code"] == "QUALIFICATION_SEMANTIC_UNMAPPED")
    assert gap["semantic"] == "geometry"
    assert "SpaceGuard" in gap["message"] and "request space" in gap["message"]


@pytest.mark.parametrize("broken,expected", [("missing", GuardStatus.GAP), ("contradiction", GuardStatus.FAIL)])
def test_real_native_non_pass_outranks_a_declared_boundary(broken, expected):
    contract = _event_contract()
    contract["claim"]["requested_semantics"].append("numeric_dynamics")
    if broken == "missing":
        contract["inputs"] = {}
    else:
        contract["inputs"]["events"][0]["requires"] = ["not_given"]
    report = run_worldguard(contract)
    assert report.status == expected
    assert report.structural_status == GuardStatus.BOUNDARY_EXCEEDED
    assert not any(gap["code"] == "QUALIFICATION_SEMANTIC_UNMAPPED" for gap in report.gaps)
