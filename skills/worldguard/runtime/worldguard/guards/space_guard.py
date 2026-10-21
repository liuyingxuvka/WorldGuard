from __future__ import annotations

from collections import defaultdict

from worldguard.contracts import GuardContract
from worldguard.status import GuardStatus

from ._helpers import error, requested_semantic_ids, result


_RCC8 = {"DC", "EC", "PO", "EQ", "TPP", "NTPP", "TPPI", "NTPPI"}
_RCC8_CONVERSE = {
    "DC": "DC",
    "EC": "EC",
    "PO": "PO",
    "EQ": "EQ",
    "TPP": "TPPI",
    "NTPP": "NTPPI",
    "TPPI": "TPP",
    "NTPPI": "NTPP",
}


def run(contract: GuardContract):
    guard = "SpaceGuard"
    requested = requested_semantic_ids(contract)
    relations = contract.inputs.get("spatial_relations", [])

    if requested & {"metric_distance", "geometry"}:
        return result(
            contract,
            guard,
            GuardStatus.BOUNDARY_EXCEEDED,
            channel="boundary",
            impact="marks_boundary",
            boundary={"owner": guard, "unsupported_claim_parts": ["metric_geometry"]},
            errors=[error("SPACE_BOUNDARY_METRIC_GEOMETRY", "RCC8 does not own metric distance.")],
        )

    if not relations:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"needed": "rcc8 relation"}],
            errors=[error("SPACE_MISSING_RELATION", "No spatial relation was supplied.")],
        )

    seen = defaultdict(set)
    reflexive_conflicts = []
    malformed = []
    for rel in relations:
        if isinstance(rel, dict):
            key = (rel.get("at"), rel.get("x"), rel.get("y"))
            relation = str(rel.get("relation", "")).upper()
            if not rel.get("x") or not rel.get("y") or relation not in _RCC8:
                malformed.append(rel)
                continue
            seen[key].add(relation)
            if rel.get("x") == rel.get("y") and relation != "EQ":
                reflexive_conflicts.append(
                    {
                        "at": rel.get("at"),
                        "object_id": rel.get("x"),
                        "relation": relation,
                        "expected": "EQ",
                    }
                )
        else:
            malformed.append(rel)
    if malformed:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"needed": "complete RCC8 x/y/relation record"}],
            errors=[
                error(
                    "SPACE_UNEVALUABLE_RCC8",
                    "Every spatial record needs two object ids and a supported RCC8 relation.",
                )
            ],
        )
    if reflexive_conflicts:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="space",
            impact="supports_fail",
            errors=[
                error(
                    "SPACE_RCC8_REFLEXIVITY_CONTRADICTION",
                    "An object related to itself must use RCC8 EQ.",
                )
            ],
            counterexamples=[{"kind": "model_conflict", "steps": reflexive_conflicts}],
        )
    conflicts = [key for key, values in seen.items() if len(values) > 1]
    if conflicts:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="space",
            impact="supports_fail",
            errors=[error("SPACE_RCC8_CONTRADICTION", "Multiple RCC8 base relations conflict.")],
            counterexamples=[{"kind": "model_conflict", "steps": [{"pair": key} for key in conflicts]}],
        )

    converse_conflicts = []
    for (at, x, y), observed in seen.items():
        reverse = seen.get((at, y, x), set())
        if not reverse:
            continue
        expected = {_RCC8_CONVERSE[relation] for relation in observed}
        if reverse != expected:
            converse_conflicts.append(
                {
                    "at": at,
                    "x": x,
                    "y": y,
                    "observed": sorted(observed),
                    "reverse_observed": sorted(reverse),
                    "reverse_expected": sorted(expected),
                }
            )
    if converse_conflicts:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="space",
            impact="supports_fail",
            errors=[
                error(
                    "SPACE_RCC8_CONVERSE_CONTRADICTION",
                    "A declared reverse RCC8 relation must be the exact converse.",
                )
            ],
            counterexamples=[
                {"kind": "model_conflict", "steps": converse_conflicts}
            ],
        )

    return result(
        contract,
        guard,
        GuardStatus.PASS,
        channel="space",
        impact="supports_pass",
        payload={"relation_count": len(relations)},
        supported=True,
        consumed_inputs={"spatial_relations": relations},
    )
