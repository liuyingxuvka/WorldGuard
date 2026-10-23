from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from .status import GuardStatus, coerce_status


@dataclass(frozen=True)
class GuardResult:
    guard: str
    status: GuardStatus
    errors: list[dict[str, Any]] = field(default_factory=list)
    counterexamples: list[dict[str, Any]] = field(default_factory=list)
    missing_slots: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        object.__setattr__(self, "status", coerce_status(self.status))
        if self.status != GuardStatus.PASS and not (self.errors or self.counterexamples or self.missing_slots):
            raise ValueError(f"{self.guard} {self.status} result lacks a problem")

    def to_dict(self):
        return {"guard": self.guard, "status": self.status.value, "errors": self.errors,
                "counterexamples": self.counterexamples, "missing_slots": self.missing_slots}


@dataclass(frozen=True)
class GuardedReport:
    contract_id: str
    status: GuardStatus
    checked: dict[str, Any]
    gaps: list[dict[str, Any]]
    guard_results: list[GuardResult]
    claim_binding: dict[str, Any]
    derived_guards: list[str]
    unmapped_semantics: list[dict[str, Any]]
    scope_limits: list[str] = field(default_factory=list)

    REPORT_FIELDS: ClassVar[frozenset[str]] = frozenset({
        "contract_id", "status", "checked", "gaps", "guard_results", "claim_binding",
        "derived_guards", "unmapped_semantics", "scope_limits"})

    def __post_init__(self):
        object.__setattr__(self, "status", coerce_status(self.status))
        if [result.guard for result in self.guard_results] != self.derived_guards:
            raise ValueError("Guard results must match the derived Guards exactly once")
        if self.status == GuardStatus.PASS and self.gaps:
            raise ValueError("a passing report cannot contain problems")

    @classmethod
    def validate_payload_fields(cls, payload):
        unknown = sorted(set(payload) - cls.REPORT_FIELDS)
        if unknown:
            raise ValueError("qualification report has unknown fields: " + ", ".join(unknown))

    def to_dict(self):
        return {"contract_id": self.contract_id, "status": self.status.value,
                "checked": self.checked, "gaps": self.gaps,
                "guard_results": [result.to_dict() for result in self.guard_results],
                "claim_binding": self.claim_binding, "derived_guards": self.derived_guards,
                "unmapped_semantics": self.unmapped_semantics, "scope_limits": self.scope_limits}
