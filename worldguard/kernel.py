from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .contracts import GuardContract
from .qualification import QualificationContext, qualify_guard_contract
from .reports import GuardedReport
from .source_readings import attach_readings


def run_worldguard(
    contract: GuardContract | Mapping[str, Any],
    *,
    context: QualificationContext | Mapping[str, Any] | None = None,
) -> GuardedReport:
    """Evaluate one contract through WorldGuard's sole qualification owner."""

    if not isinstance(contract, GuardContract):
        contract = GuardContract.from_dict(contract)
    report = qualify_guard_contract(contract, context=context)
    return attach_readings(contract, report, context=context)
