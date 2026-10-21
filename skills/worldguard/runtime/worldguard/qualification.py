from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from .contracts import (
    GuardContract,
    derive_guard_requirements,
)
from .guards import GUARD_RUNNERS
from .ledgers import LedgerEntry, ledger_entry
from .reports import GuardResult, GuardedReport
from .semantic import (
    ProviderStatus,
    SemanticExecutionReceipt,
    SemanticStatus,
    aggregate_provider_status,
    aggregate_semantic_status,
    execute_semantic,
    fingerprint_mesh,
)
from .status import GuardStatus, aggregate_statuses


class QualificationError(ValueError):
    """Raised when a qualification request cannot have one current owner."""


@dataclass(frozen=True)
class QualificationContext:
    """Explicit current inputs for the sole unit/mesh qualification owner."""

    node_id: str = ""
    target_id: str = ""
    target_revision: str = ""
    provider_availability: dict[str, bool] = field(default_factory=dict)
    semantic_inputs: dict[str, Any] = field(default_factory=dict)
    rollout_inputs: dict[str, Any] = field(default_factory=dict)
    claim_boundary: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "QualificationContext":
        data = data or {}
        allowed = {
            "node_id",
            "target_id",
            "target_revision",
            "provider_availability",
            "semantic_inputs",
            "rollout_inputs",
            "claim_boundary",
        }
        unknown = sorted(set(data).difference(allowed))
        if unknown:
            raise QualificationError(
                "qualification context has unknown fields: " + ", ".join(unknown)
            )
        return cls(
            node_id=str(data.get("node_id", "")),
            target_id=str(data.get("target_id", "")),
            target_revision=str(data.get("target_revision", "")),
            provider_availability={
                str(key): bool(value)
                for key, value in dict(data.get("provider_availability", {})).items()
            },
            semantic_inputs=dict(data.get("semantic_inputs", {})),
            rollout_inputs=dict(data.get("rollout_inputs", {})),
            claim_boundary=str(data.get("claim_boundary", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "provider_availability": dict(sorted(self.provider_availability.items())),
            "semantic_inputs": self.semantic_inputs,
            "rollout_inputs": self.rollout_inputs,
            "claim_boundary": self.claim_boundary,
        }


def _semantic_gap_rows(
    contract: GuardContract,
    unmapped_semantics: tuple[str, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    claim_level = {
        str(value).strip().lower()
        for value in contract.claim.requested_semantics
        if str(value).strip()
    }
    for semantic in unmapped_semantics:
        affected_atoms = sorted(
            atom.atom_id
            for atom in contract.claim.atoms
            if semantic
            in {
                str(value).strip().lower()
                for value in atom.requested_semantics
                if str(value).strip()
            }
        )
        rows.append(
            {
                "semantic": semantic,
                "affected_claim_ids": [contract.claim.claim_id]
                if semantic in claim_level or affected_atoms
                else [],
                "affected_atom_ids": affected_atoms,
            }
        )
    return rows


def _semantic_ledger(
    contract: GuardContract,
    receipt: SemanticExecutionReceipt,
) -> LedgerEntry:
    impact = {
        SemanticStatus.PASS: "supports_pass",
        SemanticStatus.FAIL: "supports_fail",
        SemanticStatus.GAP: "creates_gap",
        SemanticStatus.BOUNDARY_ONLY: "marks_boundary",
        SemanticStatus.NOT_RUN: "creates_gap",
    }[receipt.status]
    channel = {
        SemanticStatus.PASS: "aggregate",
        SemanticStatus.FAIL: "aggregate",
        SemanticStatus.GAP: "gap",
        SemanticStatus.BOUNDARY_ONLY: "boundary",
        SemanticStatus.NOT_RUN: "gap",
    }[receipt.status]
    return ledger_entry(
        run_id=contract.run_id,
        claim_id=contract.claim.claim_id,
        guard=receipt.guard,
        channel=channel,
        status_impact=impact,
        payload=receipt.to_dict(),
        step=f"semantic:{receipt.node_id}:{receipt.guard}",
    )


def _guard_status(status: SemanticStatus) -> GuardStatus:
    if status == SemanticStatus.PASS:
        return GuardStatus.PASS
    if status == SemanticStatus.FAIL:
        return GuardStatus.FAIL
    if status == SemanticStatus.BOUNDARY_ONLY:
        return GuardStatus.BOUNDARY_EXCEEDED
    return GuardStatus.GAP


def _provider_guard_status(status: ProviderStatus) -> GuardStatus:
    if status in {ProviderStatus.AVAILABLE, ProviderStatus.NOT_REQUIRED}:
        return GuardStatus.PASS
    return GuardStatus.GAP


def _claim_boundary(
    contract: GuardContract,
    context: QualificationContext,
    target_id: str,
    target_revision: str,
) -> str:
    if context.claim_boundary:
        return context.claim_boundary
    revision = target_revision or "unversioned"
    return f"target:{target_id}@{revision};claim:{contract.claim.claim_id}"


def qualify_guard_contract(
    contract: GuardContract | Mapping[str, Any],
    *,
    context: QualificationContext | Mapping[str, Any] | None = None,
) -> GuardedReport:
    if not isinstance(contract, GuardContract):
        contract = GuardContract.from_dict(dict(contract))
    if context is None:
        context = QualificationContext()
    elif not isinstance(context, QualificationContext):
        context = QualificationContext.from_dict(context)

    if context.semantic_inputs:
        mismatched = sorted(
            key
            for key, value in context.semantic_inputs.items()
            if key not in contract.inputs or contract.inputs[key] != value
        )
        if mismatched:
            raise QualificationError(
                "semantic inputs do not match the current contract: "
                + ", ".join(mismatched)
            )

    declared = list(contract.claim.target_guards)
    if len(declared) != len(set(declared)):
        raise QualificationError("duplicate declared Guard ownership")
    unknown = sorted(set(declared).difference(GUARD_RUNNERS))
    if unknown:
        raise QualificationError("unknown declared guards: " + ", ".join(unknown))

    guard_derivation = derive_guard_requirements(contract.claim)
    derived = list(guard_derivation.guard_ids)
    omitted = [guard for guard in derived if guard not in declared]
    unexpected = [guard for guard in declared if guard not in derived]
    effective = list(derived)
    unmapped = _semantic_gap_rows(contract, guard_derivation.unmapped_semantics)
    target_id = context.target_id or contract.world_model.model_id or contract.contract_id
    target_revision = context.target_revision or contract.world_model.model_version
    node_id = context.node_id or target_id
    contract_fingerprint = fingerprint_mesh(contract.to_dict())
    target_fingerprint = fingerprint_mesh(
        {"target_id": target_id, "target_revision": target_revision}
    )
    claim_boundary = _claim_boundary(
        contract,
        context,
        target_id,
        target_revision,
    )

    child_results: list[GuardResult] = []
    semantic_receipts: list[SemanticExecutionReceipt] = []

    for guard in effective:
        guard_contract = contract.for_guard(
            guard,
            upstream_results=[result.to_dict() for result in child_results],
        )
        child_results.append(GUARD_RUNNERS[guard](guard_contract))
        receipt = execute_semantic(
            node_id=node_id,
            guard=guard,
            contract=guard_contract,
            provider_available=context.provider_availability.get(guard, True),
            coverage_context=context.rollout_inputs,
        )
        semantic_receipts.append(receipt)

    structural_status = aggregate_statuses(
        [result.status for result in child_results]
    )
    semantic_status = aggregate_semantic_status(semantic_receipts)
    if unmapped and semantic_status != SemanticStatus.FAIL:
        semantic_status = SemanticStatus.GAP
    provider_status = aggregate_provider_status(
        semantic_receipts,
        required=bool(effective),
    )

    rollout_stale = False
    rollout_contract_fingerprint = str(
        context.rollout_inputs.get("contract_fingerprint", "")
    )
    if (
        rollout_contract_fingerprint
        and rollout_contract_fingerprint != contract_fingerprint
    ):
        rollout_status = SemanticStatus.NOT_RUN
        rollout_stale = True
    elif context.rollout_inputs.get("status"):
        rollout_status = SemanticStatus(str(context.rollout_inputs["status"]))
    else:
        rollout_status = semantic_status

    gaps: list[dict[str, Any]] = []
    for row in unmapped:
        gaps.append(
            {
                "gap_id": f"qualification:unmapped-semantic:{row['semantic']}",
                "code": "QUALIFICATION_SEMANTIC_UNMAPPED",
                **row,
            }
        )
    for result in child_results:
        if result.status != GuardStatus.PASS:
            gaps.append(
                {
                    "gap_id": f"qualification:structural:{result.guard}",
                    "code": "QUALIFICATION_STRUCTURAL_NON_PASS",
                    "guard": result.guard,
                    "status": result.status.value,
                    "result_id": result.result_id,
                }
            )
    for receipt in semantic_receipts:
        if receipt.status != SemanticStatus.PASS:
            gaps.append(
                {
                    "gap_id": f"qualification:semantic:{receipt.guard}",
                    "code": "QUALIFICATION_SEMANTIC_NON_PASS",
                    "guard": receipt.guard,
                    "status": receipt.status.value,
                    "provider_status": receipt.provider_status.value,
                    "findings": receipt.findings,
                }
            )
    if rollout_stale:
        gaps.append(
            {
                "gap_id": "qualification:rollout:stale",
                "code": "QUALIFICATION_ROLLOUT_EVIDENCE_STALE",
                "expected_contract_fingerprint": contract_fingerprint,
                "observed_contract_fingerprint": rollout_contract_fingerprint,
            }
        )

    final_axes = [
        structural_status,
        _guard_status(semantic_status),
        _provider_guard_status(provider_status),
        _guard_status(rollout_status),
    ]
    if unmapped:
        final_axes.append(GuardStatus.GAP)
    status = aggregate_statuses(final_axes)

    aggregate_ledger: list[LedgerEntry] = []
    for result in child_results:
        aggregate_ledger.extend(result.all_ledgers())
    aggregate_ledger.extend(
        _semantic_ledger(contract, receipt) for receipt in semantic_receipts
    )
    provider_states = {
        receipt.guard: receipt.provider_status.value for receipt in semantic_receipts
    }
    depth_state = {
        "status": rollout_status.value,
        "source": "qualification_context"
        if context.rollout_inputs
        else "semantic_receipts",
        "inputs": context.rollout_inputs,
    }
    normalized_context = {
        "node_id": node_id,
        "target_id": target_id,
        "target_revision": target_revision,
        "provider_availability": {
            guard: context.provider_availability.get(guard, True)
            for guard in effective
        },
        "semantic_inputs_fingerprint": fingerprint_mesh(contract.inputs),
        "rollout_inputs": context.rollout_inputs,
        "claim_boundary": claim_boundary,
    }
    fingerprint_payload = {
        "contract_fingerprint": contract_fingerprint,
        "guard_derivation_fingerprint": guard_derivation.fingerprint,
        "target_fingerprint": target_fingerprint,
        "context": normalized_context,
        "declared_guards": declared,
        "derived_guards": derived,
        "effective_guards": effective,
        "omitted_guards": omitted,
        "unexpected_guards": unexpected,
        "unmapped_semantics": unmapped,
        "structural_results": [result.to_dict() for result in child_results],
        "semantic_receipts": [receipt.to_dict() for receipt in semantic_receipts],
        "provider_states": provider_states,
        "rollout_status": rollout_status.value,
        "depth_state": depth_state,
        "gaps": gaps,
        "final_status": status.value,
        "claim_boundary": claim_boundary,
    }
    qualification_fingerprint = fingerprint_mesh(fingerprint_payload)

    return GuardedReport(
        status=status,
        structural_status=structural_status,
        semantic_status=semantic_status,
        provider_status=provider_status,
        rollout_status=rollout_status,
        target_id=target_id,
        target_revision=target_revision,
        target_fingerprint=target_fingerprint,
        contract_id=contract.contract_id,
        contract_fingerprint=contract_fingerprint,
        guard_derivation_fingerprint=guard_derivation.fingerprint,
        qualification_fingerprint=qualification_fingerprint,
        declared_guards=declared,
        derived_guards=derived,
        effective_guards=effective,
        omitted_guards=omitted,
        unexpected_guards=unexpected,
        unmapped_semantics=unmapped,
        child_results=child_results,
        semantic_receipts=semantic_receipts,
        provider_states=provider_states,
        depth_state=depth_state,
        gaps=gaps,
        aggregate_ledger=aggregate_ledger,
        scope_limits=list(contract.world_model.scope_limits),
        claim_boundary=claim_boundary,
    )


__all__ = [
    "QualificationContext",
    "QualificationError",
    "qualify_guard_contract",
]
