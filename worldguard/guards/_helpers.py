from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from worldguard.contracts import GUARD_BOUNDARY_SEMANTICS, GuardContract
from worldguard.reports import GuardResult
from worldguard.status import GuardStatus, aggregate_statuses


def requested_semantic_ids(contract: GuardContract) -> set[str]:
    """Return the claim's requested semantic ids; the claim prose is never parsed."""
    values = [*contract.claim.requested_semantics]
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


def append_guard_boundary(
    checked: GuardResult, contract: GuardContract, guard: str,
    boundary_error: Callable[[], dict[str, str]],
) -> GuardResult:
    """Keep the complete native check, then add a requested boundary without hiding its result."""
    if requested_semantic_ids(contract) & GUARD_BOUNDARY_SEMANTICS[guard]:
        return replace(
            checked, status=aggregate_statuses([checked.status, GuardStatus.BOUNDARY_EXCEEDED]),
            errors=[*checked.errors, boundary_error()],
        )
    return checked
