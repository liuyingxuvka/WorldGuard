from __future__ import annotations

from worldguard.contracts import GUARD_BOUNDARY_SEMANTICS, GuardContract
from worldguard.semantic import missing_bdi_fields
from worldguard.status import GuardStatus

from ._helpers import error, requested_semantic_ids, result


def run(contract: GuardContract):
    guard = "AgentGuard"
    requested = requested_semantic_ids(contract)
    agents = contract.inputs.get("beliefs", {})
    agent_model = contract.inputs.get("agent_model", {})

    if requested & GUARD_BOUNDARY_SEMANTICS[guard]:
        return result(
            contract,
            guard,
            GuardStatus.BOUNDARY_EXCEEDED,
            channel="boundary",
            impact="marks_boundary",
            boundary={"owner": guard, "unsupported_claim_parts": ["non_bdi_semantics"]},
            errors=[error("AGENT_BOUNDARY_NON_BDI", "AgentGuard only owns BDI-style checks.")],
        )

    if agent_model.get("conflicting_intentions"):
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="agent",
            impact="supports_fail",
            errors=[error("AGENT_CONFLICTING_INTENTIONS", "Conflicting intentions are declared.")],
            counterexamples=[{"kind": "model_conflict", "steps": agent_model["conflicting_intentions"]}],
        )

    missing = agent_model.get("missing_beliefs", [])
    if missing or not isinstance(agents, dict) or not agents:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"belief": item} for item in (missing or ["agent beliefs"])],
            errors=[error("AGENT_MISSING_BELIEF", "Required BDI slot is missing.")],
        )

    identity_mismatches = [
        {
            "map_key": str(agent_key),
            "agent_id": record.get("agent_id") if isinstance(record, dict) else None,
        }
        for agent_key, record in agents.items()
        if not isinstance(record, dict)
        or not record.get("agent_id")
        or str(record.get("agent_id")) != str(agent_key)
    ]
    if identity_mismatches:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="agent",
            impact="supports_fail",
            errors=[
                error(
                    "AGENT_IDENTITY_MISMATCH",
                    "Each BDI map key must equal the stable agent_id in its record.",
                )
            ],
            counterexamples=[{"kind": "model_conflict", "steps": identity_mismatches}],
        )

    incomplete = [
        {"agent_id": str(agent_key), "missing": missing_bdi_fields(record)}
        for agent_key, record in agents.items()
        if missing_bdi_fields(record)
    ]
    if incomplete:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=incomplete,
            errors=[
                error(
                    "AGENT_INCOMPLETE_BDI",
                    "Every declared agent needs beliefs, desires, and an intentions list (it may be empty).",
                )
            ],
        )

    return result(
        contract,
        guard,
        GuardStatus.PASS,
        channel="agent",
        impact="supports_pass",
        payload={"agent_count": len(agents), "agent_ids": sorted(str(key) for key in agents)},
        supported=True,
        consumed_inputs={"agents": agents, "agent_model": agent_model},
    )
