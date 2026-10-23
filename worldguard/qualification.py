from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .claim_binding import evaluate_claim_binding
from .contracts import GuardContract, GUARD_BOUNDARY_SEMANTICS, SEMANTIC_GUARD_ROUTES, derive_guard_requirements
from .guards import GUARD_RUNNERS
from .reports import GuardedReport
from .status import GuardStatus, aggregate_statuses


class QualificationError(ValueError):
    """A qualification request has invalid current inputs."""


@dataclass(frozen=True)
class QualificationContext:
    node_id: str = ""
    target_id: str = ""
    target_revision: str = ""

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {})
        unknown = sorted(set(data) - {"node_id", "target_id", "target_revision"})
        if unknown:
            raise QualificationError("qualification context has unknown fields: " + ", ".join(unknown))
        return cls(**data)

    def to_dict(self):
        return {"node_id": self.node_id, "target_id": self.target_id, "target_revision": self.target_revision}


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
    for row in rows:
        owners = [guard for guard, boundaries in GUARD_BOUNDARY_SEMANTICS.items() if row["semantic"] in boundaries]
        if owners:
            hints = [f"{guard} (also request {next(key for key, routes in SEMANTIC_GUARD_ROUTES.items() if routes == (guard,))})" for guard in owners]
            row["message"] = f"{row['semantic']} is a boundary id of " + ", ".join(hints)
    return rows


def qualify_guard_contract(contract, *, context=None):
    """Run each derived Guard once and evaluate each declared claim row."""
    if not isinstance(contract, GuardContract):
        contract = GuardContract.from_dict(dict(contract))
    if context is not None and not isinstance(context, QualificationContext):
        QualificationContext.from_dict(context)
    declared = contract.claim.target_guards
    if len(declared) != len(set(declared)):
        raise QualificationError("duplicate declared Guard ownership")
    unknown = sorted(set(declared) - GUARD_RUNNERS.keys())
    if unknown:
        raise QualificationError("unknown declared guards: " + ", ".join(unknown))
    derivation = derive_guard_requirements(contract.claim)
    derived = list(derivation.guard_ids)
    unmapped = _semantic_gap_rows(contract, derivation.unmapped_semantics)
    results = [GUARD_RUNNERS[guard](contract.for_guard(guard)) for guard in derived]
    binding = evaluate_claim_binding(contract)
    gaps = [{"code": "QUALIFICATION_SEMANTIC_UNMAPPED", "status": "GAP", **row} for row in unmapped]
    for result in results:
        for problem in result.errors:
            row = {"code": problem["code"], "guard": result.guard, "status": result.status.value,
                   "message": problem.get("message", "")}
            if result.counterexamples:
                counterexample = result.counterexamples[0]
                steps = counterexample.get("steps", [])
                row["counterexample"] = steps[0] if len(steps) == 1 else counterexample
            if result.missing_slots:
                row["missing_slots"] = result.missing_slots
            gaps.append(row)
    if not binding["bound"]:
        gaps.append({"code": "CLAIM_NOT_BOUND", "status": "GAP",
                     "message": "claim not bound to the world model: add claim.asserts"})
    for row in binding["assertions"]:
        if row["status"] != "PASS":
            gaps.append({"code": "CLAIM_ASSERTION_FALSE" if row["status"] == "FAIL" else "CLAIM_ASSERTION_UNRESOLVED",
                         "claim_row": row["index"], **{k: v for k, v in row.items() if k != "index"}})
    status = aggregate_statuses([*[r.status for r in results], binding["status"], *(["GAP"] if unmapped else [])])
    return GuardedReport(contract_id=contract.contract_id, status=status,
        checked={"guards": derived, "claim_rows": len(binding["assertions"])}, gaps=gaps,
        guard_results=results, claim_binding=binding, derived_guards=derived,
        unmapped_semantics=unmapped, scope_limits=list(contract.world_model.scope_limits))
