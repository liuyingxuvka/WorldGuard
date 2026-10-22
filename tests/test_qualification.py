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
