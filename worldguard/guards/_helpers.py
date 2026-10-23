from __future__ import annotations

from typing import Any

from worldguard.contracts import GuardContract
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
    return GuardResult(guard=guard, status=status, errors=errors or [],
                       counterexamples=counterexamples or [], missing_slots=missing_slots or [])


def error(code: str, message: str, severity: str = "blocking") -> dict[str, str]:
    return {"code": code, "severity": severity, "message": message, "source_ref": code}
