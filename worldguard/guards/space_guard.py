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


# Randell, Cui and Cohn (1992), RCC8 base-relation composition.
_RCC8_COMPOSITION = {
    ('DC', 'DC'): frozenset(['DC', 'EC', 'EQ', 'NTPP', 'NTPPI', 'PO', 'TPP', 'TPPI']),
    ('DC', 'EC'): frozenset(['DC', 'EC', 'NTPP', 'PO', 'TPP']),
    ('DC', 'PO'): frozenset(['DC', 'EC', 'NTPP', 'PO', 'TPP']),
    ('DC', 'TPP'): frozenset(['DC', 'EC', 'NTPP', 'PO', 'TPP']),
    ('DC', 'NTPP'): frozenset(['DC', 'EC', 'NTPP', 'PO', 'TPP']),
    ('DC', 'TPPI'): frozenset(['DC']),
    ('DC', 'NTPPI'): frozenset(['DC']),
    ('EC', 'DC'): frozenset(['DC', 'EC', 'NTPPI', 'PO', 'TPPI']),
    ('EC', 'EC'): frozenset(['DC', 'EC', 'EQ', 'PO', 'TPP', 'TPPI']),
    ('EC', 'PO'): frozenset(['DC', 'EC', 'NTPP', 'PO', 'TPP']),
    ('EC', 'TPP'): frozenset(['EC', 'NTPP', 'PO', 'TPP']),
    ('EC', 'NTPP'): frozenset(['NTPP', 'PO', 'TPP']),
    ('EC', 'TPPI'): frozenset(['DC', 'EC']),
    ('EC', 'NTPPI'): frozenset(['DC']),
    ('PO', 'DC'): frozenset(['DC', 'EC', 'NTPPI', 'PO', 'TPPI']),
    ('PO', 'EC'): frozenset(['DC', 'EC', 'NTPPI', 'PO', 'TPPI']),
    ('PO', 'PO'): frozenset(['DC', 'EC', 'EQ', 'NTPP', 'NTPPI', 'PO', 'TPP', 'TPPI']),
    ('PO', 'TPP'): frozenset(['NTPP', 'PO', 'TPP']),
    ('PO', 'NTPP'): frozenset(['NTPP', 'PO', 'TPP']),
    ('PO', 'TPPI'): frozenset(['DC', 'EC', 'NTPPI', 'PO', 'TPPI']),
    ('PO', 'NTPPI'): frozenset(['DC', 'EC', 'NTPPI', 'PO', 'TPPI']),
    ('TPP', 'DC'): frozenset(['DC']),
    ('TPP', 'EC'): frozenset(['DC', 'EC']),
    ('TPP', 'PO'): frozenset(['DC', 'EC', 'NTPP', 'PO', 'TPP']),
    ('TPP', 'TPP'): frozenset(['NTPP', 'TPP']),
    ('TPP', 'NTPP'): frozenset(['NTPP']),
    ('TPP', 'TPPI'): frozenset(['DC', 'EC', 'EQ', 'PO', 'TPP', 'TPPI']),
    ('TPP', 'NTPPI'): frozenset(['DC', 'EC', 'NTPPI', 'PO', 'TPPI']),
    ('NTPP', 'DC'): frozenset(['DC']),
    ('NTPP', 'EC'): frozenset(['DC']),
    ('NTPP', 'PO'): frozenset(['DC', 'EC', 'NTPP', 'PO', 'TPP']),
    ('NTPP', 'TPP'): frozenset(['NTPP']),
    ('NTPP', 'NTPP'): frozenset(['NTPP']),
    ('NTPP', 'TPPI'): frozenset(['DC', 'EC', 'NTPP', 'PO', 'TPP']),
    ('NTPP', 'NTPPI'): frozenset(['DC', 'EC', 'EQ', 'NTPP', 'NTPPI', 'PO', 'TPP', 'TPPI']),
    ('TPPI', 'DC'): frozenset(['DC', 'EC', 'NTPPI', 'PO', 'TPPI']),
    ('TPPI', 'EC'): frozenset(['EC', 'NTPPI', 'PO', 'TPPI']),
    ('TPPI', 'PO'): frozenset(['NTPPI', 'PO', 'TPPI']),
    ('TPPI', 'TPP'): frozenset(['EQ', 'PO', 'TPP', 'TPPI']),
    ('TPPI', 'NTPP'): frozenset(['NTPP', 'PO', 'TPP']),
    ('TPPI', 'TPPI'): frozenset(['NTPPI', 'TPPI']),
    ('TPPI', 'NTPPI'): frozenset(['NTPPI']),
    ('NTPPI', 'DC'): frozenset(['DC', 'EC', 'NTPPI', 'PO', 'TPPI']),
    ('NTPPI', 'EC'): frozenset(['NTPPI', 'PO', 'TPPI']),
    ('NTPPI', 'PO'): frozenset(['NTPPI', 'PO', 'TPPI']),
    ('NTPPI', 'TPP'): frozenset(['NTPPI', 'PO', 'TPPI']),
    ('NTPPI', 'NTPP'): frozenset(['EQ', 'NTPP', 'NTPPI', 'PO', 'TPP', 'TPPI']),
    ('NTPPI', 'TPPI'): frozenset(['NTPPI']),
    ('NTPPI', 'NTPPI'): frozenset(['NTPPI']),
    ('EQ', 'PO'): frozenset(['PO']),
    ('PO', 'EQ'): frozenset(['PO']),
    ('EQ', 'TPPI'): frozenset(['TPPI']),
    ('TPPI', 'EQ'): frozenset(['TPPI']),
    ('EQ', 'EC'): frozenset(['EC']),
    ('EC', 'EQ'): frozenset(['EC']),
    ('EQ', 'DC'): frozenset(['DC']),
    ('DC', 'EQ'): frozenset(['DC']),
    ('EQ', 'NTPPI'): frozenset(['NTPPI']),
    ('NTPPI', 'EQ'): frozenset(['NTPPI']),
    ('EQ', 'TPP'): frozenset(['TPP']),
    ('TPP', 'EQ'): frozenset(['TPP']),
    ('EQ', 'NTPP'): frozenset(['NTPP']),
    ('NTPP', 'EQ'): frozenset(['NTPP']),
    ('EQ', 'EQ'): frozenset(['EQ']),
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

    # Only declared pairs and their converses participate; no new relation is inferred.
    graph = dict(seen)
    for (at, a, b), values in seen.items():
        graph.setdefault((at, b, a), {_RCC8_CONVERSE[value] for value in values})
    composition_conflicts = []
    for (at, a, b), left in graph.items():
        for (other_at, b2, c), right in graph.items():
            if at != other_at or b != b2 or (at, a, c) not in graph:
                continue
            allowed = set().union(*(_RCC8_COMPOSITION[(r, q)] for r in left for q in right))
            observed = graph[at, a, c]
            if not observed <= allowed:
                composition_conflicts.append({"at": at, "chain": [a, b, c],
                    "relations": [sorted(left), sorted(right), sorted(observed)], "allowed": sorted(allowed)})
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
