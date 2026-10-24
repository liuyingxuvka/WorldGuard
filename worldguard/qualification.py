from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from copy import deepcopy
from typing import Any

from .claim_binding import evaluate_claim_binding
from .contracts import GuardContract, GUARD_BOUNDARY_SEMANTICS, SEMANTIC_GUARD_ROUTES, derive_guard_requirements
from .guards import GUARD_RUNNERS
from .reports import GuardedReport
from .status import GuardStatus, aggregate_statuses
from .timeline import timeline
from .clock import time_key
from .semantic import _fluent_values, token_replay
from .variants import apply_variant


class QualificationError(ValueError):
    """A qualification request has invalid current inputs."""


@dataclass(frozen=True)
class QualificationContext:
    node_contracts: Mapping[str, GuardContract] | None = field(default=None, repr=False, compare=False)
    descendant_ids: frozenset[str] = frozenset()

    @classmethod
    def from_dict(cls, data):
        data = dict(data or {})
        unknown = sorted(data)
        if unknown:
            raise QualificationError("qualification context has unknown fields: " + ", ".join(unknown))
        return cls()

    def to_dict(self):
        return {}


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
        rows.append(
            {
                "semantic": semantic,
                "affected_claim_ids": [contract.claim.claim_id]
                if semantic in claim_level
                else [],
            }
        )
    for row in rows:
        owners = [guard for guard, boundaries in GUARD_BOUNDARY_SEMANTICS.items() if row["semantic"] in boundaries]
        if owners:
            hints = [f"{guard} (also request {next(key for key, routes in SEMANTIC_GUARD_ROUTES.items() if routes == (guard,))})" for guard in owners]
            row["message"] = f"{row['semantic']} is a boundary id of " + ", ".join(hints)
    return rows


def _counterexample_context(contract, results):
    events = {(str(row.get("scenario_id") or ""), str(row.get("event_id"))): row for row in contract.inputs.get("events", []) if isinstance(row, Mapping)}
    transfers = {str(row.get("id")): row for row in contract.inputs.get("resources", {}).get("transitions", []) if isinstance(row, Mapping)}
    timelines = {}
    updated = []
    for result in results:
        examples = deepcopy(result.counterexamples)
        missing_slots = deepcopy(result.missing_slots)
        for example in [*examples, {"steps": missing_slots}]:
            for step in example.get("steps", []):
                if not isinstance(step, dict):
                    continue
                event_id = str(step.get("event_id"))
                event = events.get((str(step.get("scenario_id") or ""), event_id)) or events.get(("", event_id))
                transfer = transfers.get(str(step.get("transition")))
                referenced = event or transfer or {}
                if referenced.get("source"):
                    step["source"] = referenced["source"]
                if event:
                    scenario = step.get("scenario_id")
                    if scenario not in timelines:
                        try:
                            timelines[scenario] = timeline(contract, scenario=scenario)["steps"]
                        except ValueError:
                            timelines[scenario] = []
                    prefix = []
                    for row in timelines[scenario]:
                        if row["event_id"] is not None:
                            prefix.append({"at": row["at"], "event_id": row["event_id"]})
                        if row["event_id"] == event["event_id"]:
                            step["trace"] = prefix
                            break
        updated.append(replace(result, counterexamples=examples, missing_slots=missing_slots))
    return updated


def _event_token_consistency(contract):
    """Compare the two declared views using the native timeline replay."""
    inputs = contract.inputs
    events = [row for row in inputs.get('events', [])
              if isinstance(row, Mapping) and not row.get('scenario_id')]
    resources = inputs.get('resources', {})
    transitions = resources.get('transitions', [])
    if not events:
        return []
    unlinked = [row.get('id', f'index:{index}') for index, row in enumerate(transitions)
                if isinstance(row, Mapping) and 'event' not in row]
    if unlinked:
        return [{'code': 'RESOURCE_TRANSITION_UNLINKED', 'status': 'GAP',
                 'missing_slots': unlinked,
                 'message': 'every token transition must name the event that fires it'}]
    # A missing clock is already a native EventGuard GAP, never an input error here.
    if any('at' not in event for event in events):
        return []
    initial = inputs.get('event_model', {}).get('initial_states', [])
    known = set(initial) if isinstance(initial, Mapping) else set(_fluent_values(initial))
    for event in events:
        for name in ('requires', 'initiates', 'terminates', 'releases'):
            value = event.get(name)
            known.update(value if isinstance(value, Mapping) else _fluent_values(value))
    names = known & resources.get('places', {}).keys()
    if not names:
        return []
    _, malformed = token_replay(resources, validate=False, events=events)
    if malformed:
        return []
    view = timeline(contract)
    by_time = {}
    for event in events:
        by_time.setdefault(time_key(event['at']), []).append(event)
    uncertainty = set()
    seen_times = set()
    reported = set()
    gaps = []
    trace = []
    for step in view['steps']:
        if step['event_id'] is not None:
            instant = time_key(step['at'])
            if instant not in seen_times:
                group = by_time[instant]
                starts = set().union(*(set(_fluent_values(event.get('initiates'))) for event in group))
                stops = set().union(*(set(_fluent_values(event.get('terminates'))) |
                                      set(_fluent_values(event.get('releases'))) for event in group))
                uncertainty.difference_update(starts | stops)
                uncertainty.update(starts & stops)
                seen_times.add(instant)
            trace.append({'at': step['at'], 'event_id': step['event_id']})
        for place in sorted(names - uncertainty - reported):
            tokens = sum(step.get('tokens', {}).get(place, {}).values())
            holds = place in step['fluents']
            if holds != (tokens >= 1):
                example = {'at': step['at'], 'event_id': step['event_id'], 'place': place,
                           'fluent_holds': holds, 'tokens': tokens, 'trace': list(trace)}
                if step.get('source'):
                    example['source'] = step['source']
                gaps.append({'code': 'WORLD_EVENT_TOKEN_MISMATCH', 'status': 'FAIL',
                             'message': 'a place and fluent with the same name must agree at every step',
                             'counterexample': example})
                reported.add(place)
    return gaps


def qualify_guard_contract(contract, *, context=None):
    """Run each derived Guard once and evaluate each declared claim row."""
    if not isinstance(contract, GuardContract):
        contract = GuardContract.from_dict(dict(contract))
    if context is not None and not isinstance(context, QualificationContext):
        context = QualificationContext.from_dict(context)
    derivation = derive_guard_requirements(contract.claim)
    derived = list(derivation.guard_ids)
    unmapped = _semantic_gap_rows(contract, derivation.unmapped_semantics)
    results = [GUARD_RUNNERS[guard](contract.for_guard(guard)) for guard in derived]
    results = _counterexample_context(contract, results)
    binding = evaluate_claim_binding(contract, node_contracts=context.node_contracts if context else None,
                                     descendant_ids=context.descendant_ids if context else frozenset())
    gaps = [{"code": "QUALIFICATION_SEMANTIC_UNMAPPED", "status": "GAP", **row} for row in unmapped]
    gaps.extend(_event_token_consistency(contract))
    if contract.world_model.entities:
        inputs = contract.inputs
        used = set(inputs.get("beliefs", {})) | set(inputs.get("resources", {}).get("unique", []))
        for event in inputs.get("events", []):
            if not isinstance(event, Mapping):
                continue
            if event.get("actor"):
                used.add(event["actor"])
            used.update(event.get("with", []))
        for relation in inputs.get("spatial_relations", []):
            used.update([relation.get("x"), relation.get("y")])
        missing_entities = sorted(used - contract.world_model.entities.keys() - {None, ""})
        if missing_entities:
            gaps.append({"code": "ENTITY_UNDECLARED", "status": "GAP", "missing_slots": missing_entities,
                         "message": "Used entity ids must be declared in world_model.entities"})
    for result in results:
        for problem in result.errors:
            row = {"code": problem["code"], "guard": result.guard, "status": result.status.value,
                   "message": problem.get("message", "")}
            if result.counterexamples:
                counterexample = result.counterexamples[0]
                steps = counterexample.get("steps", [])
                row["counterexample"] = steps[0] if len(steps) == 1 else counterexample
                if len(steps) == 1 and isinstance(steps[0], dict) and steps[0].get("source"):
                    row["source"] = steps[0]["source"]
            if result.missing_slots:
                row["missing_slots"] = result.missing_slots
                if len(result.missing_slots) == 1 and isinstance(result.missing_slots[0], dict) and result.missing_slots[0].get("source"):
                    row["source"] = result.missing_slots[0]["source"]
            gaps.append(row)
    if not binding["bound"]:
        gaps.append({"code": "CLAIM_NOT_BOUND", "status": "GAP",
                     "message": "claim not bound to the world model: add claim.asserts"})
    for row in binding["assertions"]:
        if row["status"] != "PASS":
            problem = {"code": "CLAIM_ASSERTION_FALSE" if row["status"] == "FAIL" else "CLAIM_ASSERTION_UNRESOLVED",
                       "claim_row": row["index"], **{k: v for k, v in row.items() if k != "index"}}
            if row["assertion"].get("source"):
                problem["source"] = row["assertion"]["source"]
            gaps.append(problem)
    for variant in contract.variants:
        try:
            revised = qualify_guard_contract(apply_variant(contract.to_dict(), variant), context=context)
        except ValueError as exc:
            raise ValueError(f"variant {variant['id']}: {exc}") from exc
        codes = sorted({row["code"] for row in revised.gaps})
        if revised.status.value != variant.get("expect", "FAIL") or (variant.get("code") and variant["code"] not in codes):
            gaps.append({"code": "VARIANT_NOT_CAUGHT", "status": "GAP", "variant_id": variant["id"],
                "expected": variant.get("expect", "FAIL"), "actual": revised.status.value, "codes": codes,
                "expected_code": variant.get("code", "")})
    status = aggregate_statuses([*[r.status for r in results], binding["status"], *[row.get("status", "GAP") for row in gaps]])
    return GuardedReport(contract_id=contract.contract_id, status=status,
        checked={"guards": derived, "claim_rows": len(binding["assertions"]), "variants": len(contract.variants)}, gaps=gaps,
        guard_results=results, claim_binding=binding, derived_guards=derived,
        unmapped_semantics=unmapped, scope_limits=list(contract.world_model.scope_limits))
