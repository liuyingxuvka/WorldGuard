from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

from .ledgers import LedgerEntry
from .semantic import ProviderStatus, SemanticExecutionReceipt, SemanticStatus
from .status import GuardStatus, coerce_status


@dataclass(frozen=True)
class GuardResult:
    result_id: str
    contract_id: str
    guard: str
    status: GuardStatus
    supported_claims: list[str] = field(default_factory=list)
    rejected_claims: list[str] = field(default_factory=list)
    missing_slots: list[dict[str, Any]] = field(default_factory=list)
    boundary_exceeded: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    counterexamples: list[dict[str, Any]] = field(default_factory=list)
    ledgers: dict[str, list[LedgerEntry]] = field(default_factory=dict)
    assumptions_used: list[str] = field(default_factory=list)
    scope_limits: list[str] = field(default_factory=list)
    consumed_inputs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", coerce_status(self.status))
        if self.status != GuardStatus.PASS and not (
            self.missing_slots or self.boundary_exceeded or self.errors or self.counterexamples
        ):
            raise ValueError(f"{self.guard} {self.status} result lacks non-pass evidence")
        if not self.ledgers:
            raise ValueError(f"{self.guard} result lacks ledgers")

    def all_ledgers(self) -> list[LedgerEntry]:
        entries: list[LedgerEntry] = []
        for channel_entries in self.ledgers.values():
            entries.extend(channel_entries)
        return entries

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "contract_id": self.contract_id,
            "guard": self.guard,
            "status": self.status.value,
            "supported_claims": self.supported_claims,
            "rejected_claims": self.rejected_claims,
            "missing_slots": self.missing_slots,
            "boundary_exceeded": self.boundary_exceeded,
            "errors": self.errors,
            "counterexamples": self.counterexamples,
            "ledgers": {
                channel: [entry.to_dict() for entry in entries]
                for channel, entries in self.ledgers.items()
            },
            "assumptions_used": self.assumptions_used,
            "scope_limits": self.scope_limits,
            "consumed_inputs": self.consumed_inputs,
        }


@dataclass(frozen=True)
class GuardedReport:
    """The one public qualification result for unit and mesh evaluation."""

    REPORT_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "status",
            "structural_status",
            "semantic_status",
            "provider_status",
            "rollout_status",
            "target_id",
            "target_revision",
            "target_fingerprint",
            "contract_id",
            "contract_fingerprint",
            "guard_derivation_fingerprint",
            "qualification_fingerprint",
            "declared_guards",
            "derived_guards",
            "effective_guards",
            "omitted_guards",
            "unexpected_guards",
            "unmapped_semantics",
            "child_results",
            "semantic_receipts",
            "provider_states",
            "provider_evidence",
            "depth_state",
            "gaps",
            "aggregate_ledger",
            "scope_limits",
            "claim_boundary",
        }
    )

    status: GuardStatus
    structural_status: GuardStatus
    semantic_status: SemanticStatus
    provider_status: ProviderStatus
    rollout_status: SemanticStatus
    target_id: str
    target_revision: str
    target_fingerprint: str
    contract_id: str
    contract_fingerprint: str
    guard_derivation_fingerprint: str
    qualification_fingerprint: str
    declared_guards: list[str]
    derived_guards: list[str]
    effective_guards: list[str]
    omitted_guards: list[str]
    unexpected_guards: list[str]
    unmapped_semantics: list[dict[str, Any]]
    child_results: list[GuardResult]
    semantic_receipts: list[SemanticExecutionReceipt]
    provider_states: dict[str, str]
    provider_evidence: dict[str, dict[str, Any]]
    depth_state: dict[str, Any]
    gaps: list[dict[str, Any]]
    aggregate_ledger: list[LedgerEntry]
    scope_limits: list[str] = field(default_factory=list)
    claim_boundary: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", coerce_status(self.status))
        object.__setattr__(self, "structural_status", coerce_status(self.structural_status))
        object.__setattr__(self, "semantic_status", SemanticStatus(self.semantic_status))
        object.__setattr__(self, "provider_status", ProviderStatus(self.provider_status))
        object.__setattr__(self, "rollout_status", SemanticStatus(self.rollout_status))

        for name in ("declared_guards", "derived_guards", "effective_guards"):
            values = list(getattr(self, name))
            if len(values) != len(set(values)):
                raise ValueError(f"qualification report has duplicate {name}")
        if set(self.omitted_guards) != set(self.derived_guards).difference(self.declared_guards):
            raise ValueError("qualification omitted_guards do not match the derived denominator")
        if set(self.unexpected_guards) != set(self.declared_guards).difference(self.derived_guards):
            raise ValueError("qualification unexpected_guards do not match declarations")
        if self.effective_guards != self.derived_guards:
            raise ValueError("qualification effective_guards must equal the derived Guards")

        child_guards = [result.guard for result in self.child_results]
        semantic_guards = [receipt.guard for receipt in self.semantic_receipts]
        if len(child_guards) != len(set(child_guards)):
            raise ValueError("a structural Guard owner executed more than once")
        if len(semantic_guards) != len(set(semantic_guards)):
            raise ValueError("a semantic Guard owner executed more than once")
        if set(child_guards) != set(self.effective_guards):
            raise ValueError("structural results do not match the effective Guard denominator")
        if set(semantic_guards) != set(self.effective_guards):
            raise ValueError("semantic receipts do not match the effective Guard denominator")
        if set(self.provider_states) != set(self.effective_guards):
            raise ValueError("provider states do not match the effective Guard denominator")
        if set(self.provider_evidence) != set(self.effective_guards):
            raise ValueError("provider evidence does not match the effective Guard denominator")
        for guard, evidence in self.provider_evidence.items():
            required = {
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
                "source",
                "validation_status",
                "validation_errors",
            }
            missing = sorted(required.difference(evidence))
            if missing:
                raise ValueError(
                    f"provider evidence for {guard} lacks identities: "
                    + ", ".join(missing)
                )
            if evidence["validation_status"] not in {"current", "invalid"}:
                raise ValueError(
                    f"provider evidence for {guard} has unknown validation status"
                )
            if evidence["validation_status"] == "current":
                empty = sorted(
                    field_name
                    for field_name in required.difference(
                        {"validation_errors"}
                    )
                    if not str(evidence[field_name]).strip()
                )
                if empty:
                    raise ValueError(
                        f"current provider evidence for {guard} has empty identities: "
                        + ", ".join(empty)
                    )
                for field_name in ("content_fingerprint", "receipt_fingerprint"):
                    value = str(evidence[field_name])
                    if len(value) != 64 or any(
                        character not in "0123456789abcdef" for character in value
                    ):
                        raise ValueError(
                            f"current provider evidence for {guard} has invalid {field_name}"
                        )

        if self.status == GuardStatus.PASS:
            if self.gaps:
                raise ValueError("a passing qualification cannot contain gaps")
            if self.structural_status != GuardStatus.PASS:
                raise ValueError("a passing qualification lacks structural pass")
            if self.semantic_status != SemanticStatus.PASS:
                raise ValueError("a passing qualification lacks semantic pass")
            if self.provider_status not in {
                ProviderStatus.AVAILABLE,
                ProviderStatus.NOT_REQUIRED,
            }:
                raise ValueError("a passing qualification lacks current provider evidence")
            if self.rollout_status != SemanticStatus.PASS:
                raise ValueError("a passing qualification lacks rollout/depth pass")

        if not self.contract_id or not self.contract_fingerprint:
            raise ValueError("qualification report lacks contract identity")
        if not self.guard_derivation_fingerprint:
            raise ValueError("qualification report lacks Guard derivation identity")
        if not self.target_id or not self.target_fingerprint:
            raise ValueError("qualification report lacks target identity")
        if not self.qualification_fingerprint:
            raise ValueError("qualification report lacks result identity")
        if not self.claim_boundary:
            raise ValueError("qualification report lacks claim boundary")

    @classmethod
    def validate_payload_fields(cls, payload: dict[str, Any]) -> None:
        unknown = sorted(set(payload).difference(cls.REPORT_FIELDS))
        if unknown:
            raise ValueError("qualification report has unknown fields: " + ", ".join(unknown))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "structural_status": self.structural_status.value,
            "semantic_status": self.semantic_status.value,
            "provider_status": self.provider_status.value,
            "rollout_status": self.rollout_status.value,
            "target_id": self.target_id,
            "target_revision": self.target_revision,
            "target_fingerprint": self.target_fingerprint,
            "contract_id": self.contract_id,
            "contract_fingerprint": self.contract_fingerprint,
            "guard_derivation_fingerprint": self.guard_derivation_fingerprint,
            "qualification_fingerprint": self.qualification_fingerprint,
            "declared_guards": self.declared_guards,
            "derived_guards": self.derived_guards,
            "effective_guards": self.effective_guards,
            "omitted_guards": self.omitted_guards,
            "unexpected_guards": self.unexpected_guards,
            "unmapped_semantics": self.unmapped_semantics,
            "child_results": [result.to_dict() for result in self.child_results],
            "semantic_receipts": [receipt.to_dict() for receipt in self.semantic_receipts],
            "provider_states": self.provider_states,
            "provider_evidence": self.provider_evidence,
            "depth_state": self.depth_state,
            "gaps": self.gaps,
            "aggregate_ledger": [entry.to_dict() for entry in self.aggregate_ledger],
            "scope_limits": self.scope_limits,
            "claim_boundary": self.claim_boundary,
        }
