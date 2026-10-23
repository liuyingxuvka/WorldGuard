from __future__ import annotations

from worldguard.contracts import GUARD_BOUNDARY_SEMANTICS, GuardContract
from worldguard.status import GuardStatus

from ._helpers import error, requested_semantic_ids, result


def _check(contract: GuardContract):
    guard = "ConflictGuard"
    requested = requested_semantic_ids(contract)
    game_model = contract.inputs.get("game_model", {})
    players = game_model.get("players", [])
    payoffs = game_model.get("payoffs", [])
    transitions = game_model.get("transitions", [])


    duplicate_participants = sorted(
        {participant for participant in players if players.count(participant) > 1}
    )
    if duplicate_participants:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="conflict",
            impact="supports_fail",
            errors=[
                error(
                    "CONFLICT_DUPLICATE_PARTICIPANT",
                    "A finite conflict model requires distinct participant identities.",
                )
            ],
            counterexamples=[
                {"kind": "model_conflict", "steps": duplicate_participants}
            ],
        )

    for transition in transitions:
        probs = transition.get("probabilities")
        if probs and abs(sum(probs) - 1.0) > 0.0001:
            return result(
                contract,
                guard,
                GuardStatus.FAIL,
                channel="conflict",
                impact="supports_fail",
                errors=[error("CONFLICT_INVALID_PROBABILITY", "Transition probabilities do not sum to 1.")],
                counterexamples=[{"kind": "trace", "steps": [transition]}],
            )

    if not payoffs:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"needed": "payoff_vector"}],
            errors=[error("CONFLICT_MISSING_PAYOFF", "Payoff evidence is missing.")],
        )

    actions = game_model.get("actions", [])
    states = game_model.get("states", [])
    missing_components = [
        name
        for name, value in (
            ("players", players),
            ("actions", actions),
            ("states", states),
            ("transitions", transitions),
        )
        if not value
    ]
    if missing_components:
        return result(
            contract,
            guard,
            GuardStatus.GAP,
            channel="gap",
            impact="creates_gap",
            missing_slots=[{"needed": name} for name in missing_components],
            errors=[
                error(
                    "CONFLICT_INCOMPLETE_GAME",
                    "Players, actions, states, transitions, and payoffs are all required.",
                )
            ],
        )

    player_ids = {str(player) for player in players}
    state_ids = {str(state) for state in states}
    action_ids = (
        {
            str(action)
            for owner_actions in actions.values()
            for action in owner_actions
        }
        if isinstance(actions, dict)
        else {str(action) for action in actions}
    )
    reference_errors = []
    if isinstance(actions, dict):
        reference_errors.extend(
            {"kind": "action_owner", "player": str(player)}
            for player in actions
            if str(player) not in player_ids
        )
    for index, transition in enumerate(transitions):
        if not isinstance(transition, dict):
            reference_errors.append({"kind": "transition", "index": index})
            continue
        source = str(
            transition.get("from", transition.get("source_state", transition.get("state", "")))
        )
        target = str(transition.get("to", transition.get("target_state", "")))
        if source not in state_ids or target not in state_ids:
            reference_errors.append(
                {"kind": "transition_state", "index": index, "source": source, "target": target}
            )
        referenced_actions = transition.get(
            "actions", transition.get("joint_action", transition.get("action", []))
        )
        if isinstance(referenced_actions, str):
            referenced_actions = [referenced_actions]
        if isinstance(referenced_actions, dict):
            referenced_actions = list(referenced_actions.values())
        for action in referenced_actions or []:
            if str(action) not in action_ids:
                reference_errors.append(
                    {"kind": "transition_action", "index": index, "action": str(action)}
                )
    for index, payoff in enumerate(payoffs):
        if not isinstance(payoff, dict):
            reference_errors.append({"kind": "payoff", "index": index})
            continue
        if payoff.get("player") and str(payoff["player"]) not in player_ids:
            reference_errors.append(
                {"kind": "payoff_player", "index": index, "player": str(payoff["player"])}
            )
        if payoff.get("state") and str(payoff["state"]) not in state_ids:
            reference_errors.append(
                {"kind": "payoff_state", "index": index, "state": str(payoff["state"])}
            )
        reward = payoff.get("reward", {})
        if isinstance(reward, dict):
            reference_errors.extend(
                {"kind": "reward_player", "index": index, "player": str(player)}
                for player in reward
                if str(player) not in player_ids
            )
    if reference_errors:
        return result(
            contract,
            guard,
            GuardStatus.FAIL,
            channel="conflict",
            impact="supports_fail",
            errors=[
                error(
                    "CONFLICT_REFERENCE_CLOSURE",
                    "Conflict transitions and payoffs must reference declared players, states, and actions.",
                )
            ],
            counterexamples=[{"kind": "model_conflict", "steps": reference_errors}],
        )

    return result(
        contract,
        guard,
        GuardStatus.PASS,
        channel="conflict",
        impact="supports_pass",
        payload={"payoff_count": len(payoffs), "issue": game_model.get("issue"), "player_count": len(players), "state_count": len(states)},
        supported=True,
        consumed_inputs={"game_model": game_model},
    )


def run(contract: GuardContract):
    """Check the complete native ConflictGuard rules once, then append its boundary."""
    checked = _check(contract)
    if requested_semantic_ids(contract) & GUARD_BOUNDARY_SEMANTICS["ConflictGuard"]:
        from dataclasses import replace
        from worldguard.status import aggregate_statuses
        checked = replace(checked,
            status=aggregate_statuses([checked.status, GuardStatus.BOUNDARY_EXCEEDED]),
            errors=[*checked.errors, error('CONFLICT_BOUNDARY_DEONTIC_OBLIGATION', 'ConflictGuard does not own norms.')])
    return checked
