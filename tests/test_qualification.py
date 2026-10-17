from __future__ import annotations

from copy import deepcopy

import pytest


from worldguard import (
    GuardedReport,
    ModelMeshContract,
    ProviderStatus,
    QualificationContext,
    QualificationError,
    SemanticStatus,
    qualification_context_for_node,
    run_model_mesh,
    run_worldguard,
)
from worldguard.status import GuardStatus
import worldguard.qualification as qualification_module


def _event_contract() -> dict:
    contract = {
        "contract_id": "qualification:event",
        "run_id": "qualification-test",
        "claim": {
            "claim_id": "claim:event",
            "text": "the declared event makes the plan ready",
            "target_guards": ["EventGuard"],
            "requested_semantics": ["event"],
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


def _supplied_provider_result(report) -> dict:
    evidence = report.provider_evidence["EventGuard"]
    return {
        key: evidence[key]
        for key in (
            "evidence_id",
            "provider_id",
            "provider_version",
            "capability_id",
            "content_fingerprint",
            "receipt_fingerprint",
            "target_id",
            "target_revision",
            "contract_fingerprint",
            "claim_boundary",
        )
    }


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
    assert node.provider_evidence == unit.provider_evidence
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
    assert report.status == GuardStatus.GAP


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


def test_unavailable_and_stale_provider_evidence_are_typed_non_passes() -> None:
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
    assert unavailable.provider_evidence["EventGuard"]["evidence_id"]
    assert unavailable.provider_evidence["EventGuard"]["content_fingerprint"]
    assert unavailable.status == GuardStatus.GAP

    stale = run_worldguard(
        _event_contract(),
        context=QualificationContext(
            node_id="event-world",
            provider_results={
                "EventGuard": {
                    "contract_fingerprint": "0" * 64,
                    "target_revision": "revision-0",
                }
            },
        ),
    )
    assert stale.semantic_status == SemanticStatus.NOT_RUN
    assert stale.provider_status == ProviderStatus.STALE
    assert stale.semantic_receipts[0].skipped_reason == "stale_provider_evidence"
    assert (
        stale.provider_evidence["EventGuard"]["contract_fingerprint"]
        == "0" * 64
    )
    assert stale.provider_evidence["EventGuard"]["validation_status"] == "invalid"
    assert "missing_fields" in stale.provider_evidence["EventGuard"]["validation_errors"]
    assert "expected_contract_fingerprint" not in stale.provider_evidence["EventGuard"]
    assert stale.status == GuardStatus.GAP


def test_exact_supplied_provider_result_is_accepted_without_field_defaults() -> None:
    native = run_worldguard(_event_contract())
    supplied = _supplied_provider_result(native)

    report = run_worldguard(
        _event_contract(),
        context=QualificationContext(
            node_id="event-world",
            target_id="event-world",
            target_revision="revision-1",
            provider_results={"EventGuard": supplied},
        ),
    )

    assert report.status == GuardStatus.PASS
    assert report.provider_evidence["EventGuard"]["source"] == "supplied_provider"
    assert report.provider_evidence["EventGuard"]["validation_status"] == "current"
    assert _supplied_provider_result(report) == supplied


@pytest.mark.parametrize(
    ("mutation", "expected_error"),
    [
        ({"provider_version": None}, "missing_fields"),
        ({"provider_id": "foreign.provider.v1"}, "identity_mismatches"),
        ({"capability_id": "foreign.capability"}, "identity_mismatches"),
        ({"target_revision": "revision-0"}, "identity_mismatches"),
        ({"claim_boundary": "another claim"}, "identity_mismatches"),
        ({"content_fingerprint": "0" * 64}, "content_fingerprint"),
        ({"receipt_fingerprint": "f" * 64}, "receipt_fingerprint"),
    ],
)
def test_partial_foreign_stale_and_fake_provider_results_are_not_run(
    mutation: dict,
    expected_error: str,
) -> None:
    native = run_worldguard(_event_contract())
    supplied = _supplied_provider_result(native)
    for field_name, value in mutation.items():
        if value is None:
            supplied.pop(field_name)
        else:
            supplied[field_name] = value

    report = run_worldguard(
        _event_contract(),
        context=QualificationContext(
            node_id="event-world",
            target_id="event-world",
            target_revision="revision-1",
            provider_results={"EventGuard": supplied},
        ),
    )

    assert report.semantic_receipts[0].status == SemanticStatus.NOT_RUN
    assert report.provider_status == ProviderStatus.STALE
    assert report.provider_evidence["EventGuard"]["validation_status"] == "invalid"
    assert expected_error in report.provider_evidence["EventGuard"]["validation_errors"]
    assert report.status == GuardStatus.GAP


def test_partial_supplied_provider_result_is_blocked_before_semantic_execution(
    monkeypatch,
) -> None:
    def forbidden_execution(**kwargs):
        raise AssertionError("semantic execution must not start for partial provider evidence")

    monkeypatch.setattr(qualification_module, "execute_semantic", forbidden_execution)
    report = run_worldguard(
        _event_contract(),
        context=QualificationContext(
            node_id="event-world",
            provider_results={"EventGuard": {"evidence_id": "partial"}},
        ),
    )
    assert report.semantic_status == SemanticStatus.NOT_RUN
    assert report.provider_status == ProviderStatus.STALE


def test_unexpected_declared_guard_blocks_all_execution(monkeypatch) -> None:
    contract = _event_contract()
    contract["claim"]["target_guards"] = ["EventGuard", "AgentGuard"]
    contract

    def forbidden_execution(*args, **kwargs):
        raise AssertionError("no owner may execute after an unexpected Guard declaration")

    monkeypatch.setattr(qualification_module, "execute_semantic", forbidden_execution)
    monkeypatch.setitem(qualification_module.GUARD_RUNNERS, "EventGuard", forbidden_execution)
    monkeypatch.setitem(qualification_module.GUARD_RUNNERS, "AgentGuard", forbidden_execution)

    report = run_worldguard(contract)

    assert report.derived_guards == ["EventGuard"]
    assert report.unexpected_guards == ["AgentGuard"]
    assert report.effective_guards == []
    assert report.child_results == []
    assert report.semantic_receipts == []
    assert report.provider_evidence == {}
    assert any(
        gap["code"] == "QUALIFICATION_DECLARED_GUARD_UNEXPECTED"
        and gap["guard"] == "AgentGuard"
        for gap in report.gaps
    )
    assert report.status == GuardStatus.GAP


def test_exact_input_repetition_has_stable_qualification_identity() -> None:
    first = run_worldguard(_event_contract())
    second = run_worldguard(deepcopy(_event_contract()))

    assert first.contract_fingerprint == second.contract_fingerprint
    assert (
        first.guard_derivation_fingerprint
        == second.guard_derivation_fingerprint
    )
    assert first.qualification_fingerprint == second.qualification_fingerprint


def test_duplicate_execution_attempt_and_unknown_report_field_fail_closed() -> None:
    with pytest.raises(QualificationError, match="duplicate execution owner"):
        run_worldguard(
            _event_contract(),
            context=QualificationContext(
                node_id="event-world",
                prior_execution_owner_ids=(
                    "worldguard.structural:event-world:EventGuard",
                ),
            ),
        )

    with pytest.raises(ValueError, match="unknown fields"):
        GuardedReport.validate_payload_fields({"status": "PASS", "legacy": {}})
