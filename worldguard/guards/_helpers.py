from __future__ import annotations

from typing import Any

from worldguard.contracts import GuardContract
from worldguard.ledgers import ledger_entry
from worldguard.reports import GuardResult
from worldguard.status import GuardStatus


def requested_semantic_ids(contract: GuardContract) -> set[str]:
    """Return the claim's requested semantic ids; the claim prose is never parsed."""
    values = [*contract.claim.requested_semantics]
    values.extend(item for atom in contract.claim.atoms for item in atom.requested_semantics)
    return {str(value).strip().lower() for value in values if str(value).strip()}

def result(
    contract: GuardContract,
    guard: str,
    status: GuardStatus,
    *,
    channel: str,
    impact: str,
    payload: dict[str, Any] | None = None,
    supported: bool = False,
    missing_slots: list[dict[str, Any]] | None = None,
    boundary: dict[str, Any] | None = None,
    errors: list[dict[str, Any]] | None = None,
    counterexamples: list[dict[str, Any]] | None = None,
    consumed_inputs: dict[str, Any] | None = None,
) -> GuardResult:
    claim_id = contract.claim.claim_id
    entry = ledger_entry(
        run_id=contract.run_id,
        claim_id=claim_id,
        guard=guard,
        channel=channel,
        status_impact=impact,
        payload=payload or {},
    )
    return GuardResult(
        result_id=f"{contract.run_id}:{claim_id}:{guard}",
        contract_id=contract.contract_id,
        guard=guard,
        status=status,
        supported_claims=[claim_id] if supported and status == GuardStatus.PASS else [],
        rejected_claims=[claim_id] if status == GuardStatus.FAIL else [],
        missing_slots=missing_slots or [],
        boundary_exceeded=boundary or {},
        errors=errors or [],
        counterexamples=counterexamples or [],
        ledgers={channel: [entry]},
        scope_limits=contract.world_model.scope_limits,
        consumed_inputs=consumed_inputs or {},
    )


def error(code: str, message: str, severity: str = "blocking") -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message, "source_ref": code}
