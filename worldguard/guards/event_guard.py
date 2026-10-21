from __future__ import annotations

from worldguard.contracts import GuardContract
from worldguard.semantic import event_precondition_failures
from worldguard.status import GuardStatus

from ._helpers import error, requested_semantic_ids, result


def _fluent_ids(value) -> set[str]:
    if value in (None, ""):
        return set()
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        return {str(key) for key, active in value.items() if active}
    if isinstance(value, (list, tuple, set)):
        return {str(item) for item in value if str(item)}
    return {str(value)}


def _duplicate_ids(values: list[str]) -> list[str]:
    return sorted({value for value in values if values.count(value) > 1})


def run(contract: GuardContract):
    guard = "EventGuard"
    requested = requested_semantic_ids(contract)
    events = contract.inputs.get("events", [])
    event_model = contract.inputs.get("event_model", {})
    states = event_model.get("states", []) if isinstance(event_model, dict) else []
    transitions = (
        event_model.get("transitions", []) if isinstance(event_model, dict) else []
    )

    if requested & {"numeric_dynamics", "thermodynamics", "continuous_dynamics"}:
        return result(
            contract,
            guard,
            GuardStatus.BOUNDARY_EXCEEDED,
            channel="boundary",
            impact="marks_boundary",
            boundary={"owner": guard, "unsupported_claim_parts": ["numeric_dynamics"]},
            errors=[error("EVENT_BOUNDARY_NUMERIC_DYNAMICS", "EventGuard does not own numeric dynamics.")],
        )

    if not events and not states and not transitions and not event_model:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"needed": "inputs.events or inputs.event_model metadata"}],
            errors=[error("EVENT_MISSING_EVENT_MODEL", "No event model was supplied.")],
        )

    if event_model.get("contradictory_fluents"):
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="event",
            impact="supports_fail",
            errors=[error("EVENT_CONTRADICTORY_FLUENTS", "Contradictory fluents are declared.")],
            counterexamples=[{"kind": "trace", "steps": event_model.get("contradictory_fluents", [])}],
        )

    overlapping_fluents = []
    for event in events:
        if not isinstance(event, dict):
            continue
        terminates = _fluent_ids(event.get("terminates"))
        initiates = _fluent_ids(event.get("initiates"))
        overlap = sorted(terminates & initiates)
        if overlap:
            overlapping_fluents.append(
                {"event_id": event.get("event_id"), "fluent_ids": overlap}
            )
    if overlapping_fluents:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="event",
            impact="supports_fail",
            errors=[
                error(
                    "EVENT_FLUENT_TRANSITION_CONTRADICTION",
                    "One event cannot both terminate and initiate the same fluent.",
                )
            ],
            counterexamples=[{"kind": "trace", "steps": overlapping_fluents}],
        )

    missing = list(event_model.get("missing_axioms", []))
    for state in states:
        if (
            not isinstance(state, dict)
            or not state.get("state_id")
            or not isinstance(state.get("initial"), bool)
            or not isinstance(state.get("terminal"), bool)
        ):
            missing.append("complete state identity/initial/terminal record")
    for transition in transitions:
        if not isinstance(transition, dict) or any(
            not transition.get(field_name)
            for field_name in (
                "transition_id",
                "source_state",
                "target_state",
                "guard",
                "effect",
            )
        ):
            missing.append("complete transition source/target/guard/effect record")
    if missing:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"needed": item} for item in missing],
            errors=[error("EVENT_MISSING_INITIATION_AXIOM", "Required event axiom is missing.")],
        )

    if transitions and not states:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"needed": "declared state denominator for transitions"}],
            errors=[
                error(
                    "EVENT_MISSING_STATE_DENOMINATOR",
                    "Transitions cannot be qualified without the states they reference.",
                )
            ],
        )

    state_ids = [str(state["state_id"]) for state in states]
    transition_ids = [str(transition["transition_id"]) for transition in transitions]
    duplicate_states = _duplicate_ids(state_ids)
    duplicate_transitions = _duplicate_ids(transition_ids)
    if duplicate_states or duplicate_transitions:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="event",
            impact="supports_fail",
            errors=[
                error(
                    "EVENT_DUPLICATE_STATE_TRANSITION_ID",
                    "State and transition identities must be unique within one event model.",
                )
            ],
            counterexamples=[
                {
                    "kind": "model_conflict",
                    "steps": [
                        {
                            "duplicate_state_ids": duplicate_states,
                            "duplicate_transition_ids": duplicate_transitions,
                        }
                    ],
                }
            ],
        )

    state_id_set = set(state_ids)
    dangling = [
        {
            "transition_id": transition["transition_id"],
            "source_state": transition["source_state"],
            "target_state": transition["target_state"],
            "unknown_state_ids": sorted(
                {
                    str(transition[name])
                    for name in ("source_state", "target_state")
                    if str(transition[name]) not in state_id_set
                }
            ),
        }
        for transition in transitions
        if any(
            str(transition[name]) not in state_id_set
            for name in ("source_state", "target_state")
        )
    ]
    if dangling:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="event",
            impact="supports_fail",
            errors=[
                error(
                    "EVENT_DANGLING_TRANSITION_STATE",
                    "Every transition source and target must name a declared state.",
                )
            ],
            counterexamples=[{"kind": "trace", "steps": dangling}],
        )

    if transitions and not any(state["initial"] for state in states):
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"needed": "at least one initial state"}],
            errors=[
                error(
                    "EVENT_MISSING_INITIAL_STATE",
                    "A bounded state-machine rollout needs at least one initial state.",
                )
            ],
        )

    unmet = event_precondition_failures(events, event_model.get("initial_states", []))
    if unmet:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="event",
            impact="supports_fail",
            errors=[error("EVENT_PRECONDITION_UNMET", "An event happens while a fluent it requires does not hold.")],
            counterexamples=[{"kind": "trace", "steps": unmet}],
        )

    return result(
        contract,
        guard,
        GuardStatus.PASS,
        channel="event",
        impact="supports_pass",
        payload={
            "events_observed": len(events),
            "states_observed": len(states),
            "transitions_observed": len(transitions),
            "state_ids": state_ids,
            "transition_ids": transition_ids,
        },
        supported=True,
        consumed_inputs={"events": events, "event_model": event_model},
    )
