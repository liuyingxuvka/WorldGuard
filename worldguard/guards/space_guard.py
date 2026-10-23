from __future__ import annotations

from collections import defaultdict

from worldguard.contracts import GUARD_BOUNDARY_SEMANTICS, GuardContract
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


def _check(contract: GuardContract):
    guard = "SpaceGuard"
    requested = requested_semantic_ids(contract)
    relations = contract.inputs.get("spatial_relations", [])


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

    composition_conflicts = []
    for (at, a, b), observed in seen.items():
        if observed != {"NTPP"}:
            continue
        for (other_at, b2, c), right in seen.items():
            if at == other_at and b == b2 and right == {"NTPP"}:
                end = seen.get((at, a, c))
                if end and end != {"NTPP"}:
                    composition_conflicts.append({"at": at, "chain": [a, b, c], "observed": sorted(end), "expected": "NTPP"})
    if composition_conflicts:
        return result(contract, guard, GuardStatus.FAIL, channel="space", impact="supports_fail",
            errors=[error("SPACE_RCC8_CONTRADICTION", "Declared RCC8 composition is inconsistent.")],
            counterexamples=[{"kind": "model_conflict", "steps": composition_conflicts}])
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


def run(contract: GuardContract):
    """Check the complete native SpaceGuard rules once, then append its boundary."""
    checked = _check(contract)
    if requested_semantic_ids(contract) & GUARD_BOUNDARY_SEMANTICS["SpaceGuard"]:
        from dataclasses import replace
        from worldguard.status import aggregate_statuses
        checked = replace(checked,
            status=aggregate_statuses([checked.status, GuardStatus.BOUNDARY_EXCEEDED]),
            errors=[*checked.errors, error('SPACE_BOUNDARY_METRIC_GEOMETRY', 'RCC8 does not own metric distance.')])
    return checked
