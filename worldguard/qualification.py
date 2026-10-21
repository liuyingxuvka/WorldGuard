from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from typing import Any

from .contracts import (
    GuardContract,
    claim_semantics,
    derive_guard_requirements,
)
from .guards import GUARD_RUNNERS
from .ledgers import LedgerEntry, ledger_entry
from .reports import GuardResult, GuardedReport
from .semantic import (
    EXECUTOR_REGISTRY,
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
    provider_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    semantic_inputs: dict[str, Any] = field(default_factory=dict)
    rollout_inputs: dict[str, Any] = field(default_factory=dict)
    prior_execution_owner_ids: tuple[str, ...] = ()
    claim_boundary: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> "QualificationContext":
        data = data or {}
        allowed = {
            "node_id",
            "target_id",
            "target_revision",
            "provider_availability",
            "provider_results",
            "semantic_inputs",
            "rollout_inputs",
            "prior_execution_owner_ids",
            "claim_boundary",
        }
        unknown = sorted(set(data).difference(allowed))
        if unknown:
            raise QualificationError(
                "qualification context has unknown fields: " + ", ".join(unknown)
            )
        provider_results = data.get("provider_results", {})
        if not isinstance(provider_results, Mapping):
            raise QualificationError("qualification provider_results must be a mapping")
        invalid_provider_rows = sorted(
            str(key)
            for key, value in provider_results.items()
            if not isinstance(value, Mapping)
        )
        if invalid_provider_rows:
            raise QualificationError(
                "qualification provider_results require mapping rows: "
                + ", ".join(invalid_provider_rows)
            )
        return cls(
            node_id=str(data.get("node_id", "")),
            target_id=str(data.get("target_id", "")),
            target_revision=str(data.get("target_revision", "")),
            provider_availability={
                str(key): bool(value)
                for key, value in dict(data.get("provider_availability", {})).items()
            },
            provider_results={
                str(key): dict(value)
                for key, value in provider_results.items()
            },
            semantic_inputs=dict(data.get("semantic_inputs", {})),
            rollout_inputs=dict(data.get("rollout_inputs", {})),
            prior_execution_owner_ids=tuple(
                str(value) for value in data.get("prior_execution_owner_ids", [])
            ),
            claim_boundary=str(data.get("claim_boundary", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "provider_availability": dict(sorted(self.provider_availability.items())),
            "provider_results": {
                key: self.provider_results[key] for key in sorted(self.provider_results)
            },
            "semantic_inputs": self.semantic_inputs,
            "rollout_inputs": self.rollout_inputs,
            "prior_execution_owner_ids": list(self.prior_execution_owner_ids),
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


def _execution_owner(
    *,
    seen: set[str],
    prior: set[str],
    layer: str,
    node_id: str,
    guard: str,
) -> None:
    owner_id = f"worldguard.{layer}:{node_id}:{guard}"
    if owner_id in seen or owner_id in prior:
        raise QualificationError(f"duplicate execution owner: {owner_id}")
    seen.add(owner_id)


def _stale_provider_receipt(
    *,
    node_id: str,
    guard: str,
    contract: GuardContract,
    evidence: dict[str, Any],
) -> SemanticExecutionReceipt:
    executor = EXECUTOR_REGISTRY[guard]
    return SemanticExecutionReceipt(
        node_id=node_id,
        guard=guard,
        status=SemanticStatus.NOT_RUN,
        provider_status=ProviderStatus.STALE,
        binding=executor.binding,
        findings=[
            {
                "code": "SEM_PROVIDER_EVIDENCE_STALE",
                "message": "The supplied provider evidence does not match the current contract or target revision.",
                "evidence": evidence,
            }
        ],
        skipped_reason="stale_provider_evidence",
    )


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


def _provider_evidence_identity(
    *,
    guard: str,
    receipt: SemanticExecutionReceipt,
    target_id: str,
    target_revision: str,
    contract_fingerprint: str,
    claim_boundary: str,
) -> dict[str, Any]:
    """Derive exact evidence identity from this run's native semantic receipt."""

    receipt_fingerprint = fingerprint_mesh(receipt.to_dict())
    executor_id = receipt.binding.executor_id
    return {
        "evidence_id": f"semantic:{receipt.node_id}:{guard}",
        "provider_id": executor_id,
        "provider_version": executor_id.rsplit(".", 1)[-1],
        "capability_id": f"{executor_id}.execute",
        "content_fingerprint": receipt_fingerprint,
        "receipt_fingerprint": receipt_fingerprint,
        "target_id": target_id,
        "target_revision": target_revision,
        "contract_fingerprint": contract_fingerprint,
        "claim_boundary": claim_boundary,
        "source": "native_execution",
        "validation_status": "current",
        "validation_errors": {},
    }


PROVIDER_EVIDENCE_FIELDS = frozenset(
    {
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
    }
)


def _canonical_fingerprint(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "")))


def _supplied_provider_preflight(
    *,
    guard: str,
    supplied: dict[str, Any],
    target_id: str,
    target_revision: str,
    contract_fingerprint: str,
    claim_boundary: str,
) -> dict[str, Any]:
    executor_id = EXECUTOR_REGISTRY[guard].binding.executor_id
    missing = sorted(PROVIDER_EVIDENCE_FIELDS.difference(supplied))
    unknown = sorted(set(supplied).difference(PROVIDER_EVIDENCE_FIELDS))
    errors: dict[str, Any] = {}
    if missing:
        errors["missing_fields"] = missing
    if unknown:
        errors["unknown_fields"] = unknown
    expected = {
        "provider_id": executor_id,
        "provider_version": executor_id.rsplit(".", 1)[-1],
        "capability_id": f"{executor_id}.execute",
        "target_id": target_id,
        "target_revision": target_revision,
        "contract_fingerprint": contract_fingerprint,
        "claim_boundary": claim_boundary,
    }
    mismatches = {
        field_name: {"expected": expected_value, "observed": supplied.get(field_name)}
        for field_name, expected_value in expected.items()
        if field_name in supplied and supplied.get(field_name) != expected_value
    }
    if mismatches:
        errors["identity_mismatches"] = mismatches
    if "evidence_id" in supplied and not str(supplied.get("evidence_id", "")).strip():
        errors["evidence_id"] = "non_empty_string_required"
    for field_name in ("content_fingerprint", "receipt_fingerprint"):
        if field_name in supplied and not _canonical_fingerprint(supplied[field_name]):
            errors[field_name] = "canonical_sha256_required"
    return errors


def _invalid_provider_evidence(
    supplied: dict[str, Any],
    errors: dict[str, Any],
) -> dict[str, Any]:
    return {
        **{field_name: supplied.get(field_name, "") for field_name in sorted(PROVIDER_EVIDENCE_FIELDS)},
        "source": "supplied_provider",
        "validation_status": "invalid",
        "validation_errors": errors,
        "supplied_evidence": dict(supplied),
    }


def _validated_supplied_provider_evidence(supplied: dict[str, Any]) -> dict[str, Any]:
    return {
        **{field_name: supplied[field_name] for field_name in sorted(PROVIDER_EVIDENCE_FIELDS)},
        "source": "supplied_provider",
        "validation_status": "current",
        "validation_errors": {},
    }


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

    seen_owners: set[str] = set()
    prior_owners = set(context.prior_execution_owner_ids)
    child_results: list[GuardResult] = []
    semantic_receipts: list[SemanticExecutionReceipt] = []
    provider_evidence: dict[str, dict[str, Any]] = {}

    for guard in effective:
        _execution_owner(
            seen=seen_owners,
            prior=prior_owners,
            layer="structural",
            node_id=node_id,
            guard=guard,
        )
        guard_contract = contract.for_guard(
            guard,
            upstream_results=[result.to_dict() for result in child_results],
        )
        child_results.append(GUARD_RUNNERS[guard](guard_contract))

        _execution_owner(
            seen=seen_owners,
            prior=prior_owners,
            layer="semantic",
            node_id=node_id,
            guard=guard,
        )
        supplied_present = guard in context.provider_results
        provider_result = context.provider_results.get(guard, {})
        stale_reasons = (
            _supplied_provider_preflight(
                guard=guard,
                supplied=provider_result,
                target_id=target_id,
                target_revision=target_revision,
                contract_fingerprint=contract_fingerprint,
                claim_boundary=claim_boundary,
            )
            if supplied_present
            else {}
        )
        if supplied_present and stale_reasons:
            receipt = _stale_provider_receipt(
                node_id=node_id,
                guard=guard,
                contract=guard_contract,
                evidence=stale_reasons,
            )
            provider_evidence[guard] = _invalid_provider_evidence(
                provider_result,
                stale_reasons,
            )
        else:
            receipt = execute_semantic(
                node_id=node_id,
                guard=guard,
                contract=guard_contract,
                provider_available=context.provider_availability.get(guard, True),
                coverage_context=context.rollout_inputs,
            )
            if supplied_present:
                receipt_fingerprint = fingerprint_mesh(receipt.to_dict())
                fingerprint_errors: dict[str, Any] = {}
                for field_name in ("content_fingerprint", "receipt_fingerprint"):
                    if provider_result[field_name] != receipt_fingerprint:
                        fingerprint_errors[field_name] = {
                            "expected": receipt_fingerprint,
                            "observed": provider_result[field_name],
                        }
                if fingerprint_errors:
                    receipt = _stale_provider_receipt(
                        node_id=node_id,
                        guard=guard,
                        contract=guard_contract,
                        evidence=fingerprint_errors,
                    )
                    provider_evidence[guard] = _invalid_provider_evidence(
                        provider_result,
                        fingerprint_errors,
                    )
                else:
                    provider_evidence[guard] = _validated_supplied_provider_evidence(
                        provider_result
                    )
            else:
                provider_evidence[guard] = _provider_evidence_identity(
                    guard=guard,
                    receipt=receipt,
                    target_id=target_id,
                    target_revision=target_revision,
                    contract_fingerprint=contract_fingerprint,
                    claim_boundary=claim_boundary,
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
        "provider_evidence": provider_evidence,
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
        "provider_evidence": provider_evidence,
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
        provider_evidence=provider_evidence,
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
