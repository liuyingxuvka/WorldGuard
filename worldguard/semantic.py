from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any, Callable, Mapping

from .contracts import GuardContract


class SemanticStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    GAP = "GAP"
    BOUNDARY_ONLY = "BOUNDARY_ONLY"
    NOT_RUN = "NOT_RUN"


class ProviderStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    NOT_REQUIRED = "NOT_REQUIRED"
    MIXED = "MIXED"


NORM_MODALITIES = frozenset({"permitted", "obligatory", "forbidden", "prohibited"})


def _event_time_key(value: Any) -> tuple[int, Any]:
    """Order event times numerically (t9 before t10) and ISO date-times chronologically."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, float(value))
    text = str(value if value is not None else "").strip()
    match = re.fullmatch(r"[A-Za-z_]*(-?\d+(?:\.\d+)?)", text)
    if match:
        return (0, float(match.group(1)))
    try:
        return (1, datetime.fromisoformat(text.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return (2, text)


def missing_bdi_fields(record: Mapping[str, Any]) -> list[str]:
    """Beliefs and desires must be non-empty; intentions must be present but may be empty."""
    missing = [name for name in ("beliefs", "desires") if not record.get(name)]
    if record.get("intentions") is None:
        missing.append("intentions")
    return missing


def active_norm_conflicts(norms: list[Any]) -> list[dict[str, Any]]:
    """Return (actor, action) groups whose active norms both forbid and permit/require it."""
    groups: dict[tuple[str, str], list[Any]] = {}
    for norm in norms:
        if isinstance(norm, dict):
            key = (str(norm.get("actor", "")), str(norm.get("action", "")))
            groups.setdefault(key, []).append(norm)
    conflicts = []
    for (actor, action), group in sorted(groups.items()):
        modalities = {str(norm.get("modality", "")) for norm in group}
        if modalities & {"forbidden", "prohibited"} and modalities & {"permitted", "obligatory"}:
            conflicts.append({"actor": actor, "action": action, "norms": group})
    return conflicts



@dataclass(frozen=True)
class SemanticBinding:
    executor_id: str
    guard: str
    possible_consumed_input_fields: tuple[str, ...]
    output_fields: tuple[str, ...]
    supported_semantics: tuple[str, ...]
    unsupported_boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "executor_id": self.executor_id,
            "guard": self.guard,
            "possible_consumed_input_fields": list(
                self.possible_consumed_input_fields
            ),
            "output_fields": list(self.output_fields),
            "supported_semantics": list(self.supported_semantics),
            "unsupported_boundary": self.unsupported_boundary,
        }


@dataclass(frozen=True)
class SemanticExecutionReceipt:
    node_id: str
    guard: str
    status: SemanticStatus
    provider_status: ProviderStatus
    binding: SemanticBinding
    findings: list[dict[str, Any]] = field(default_factory=list)
    consumed_inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    skipped_reason: str = ""


    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "guard": self.guard,
            "status": self.status.value,
            "provider_status": self.provider_status.value,
            "binding": self.binding.to_dict(),
            "findings": self.findings,
            "consumed_inputs": self.consumed_inputs,
            "outputs": self.outputs,
            "skipped_reason": self.skipped_reason,
        }


@dataclass(frozen=True)
class NativeDepthReceipt:
    receipt_id: str
    mesh_id: str
    run_id: str
    mesh_fingerprint: str
    structural_checks: list[dict[str, Any]]
    executed_semantic_children: list[str]
    provider_states: dict[str, str]
    findings: list[dict[str, Any]]
    skipped_children: list[dict[str, Any]]
    claim_boundary: str
    receipt_version: str = "worldguard.native_depth.v2"
    generated_at: str = ""
    coverage_fingerprint: str = ""
    predictive_profile: str = "bounded"
    claim_atoms: list[dict[str, Any]] = field(default_factory=list)
    required_guards: dict[str, list[str]] = field(default_factory=dict)
    declared_guards: dict[str, list[str]] = field(default_factory=dict)
    missing_guards: dict[str, list[str]] = field(default_factory=dict)
    expected_model_nodes: list[str] = field(default_factory=list)
    discovered_model_nodes: list[str] = field(default_factory=list)
    declared_model_nodes: list[str] = field(default_factory=list)
    excluded_model_nodes: list[dict[str, Any]] = field(default_factory=list)
    model_node_reconciliation_gaps: list[str] = field(default_factory=list)
    executed_model_nodes: list[str] = field(default_factory=list)
    skipped_model_nodes: list[dict[str, Any]] = field(default_factory=list)
    expected_semantic_children: list[str] = field(default_factory=list)
    quantitative_coverage: dict[str, Any] = field(default_factory=dict)
    predictive_gaps: list[str] = field(default_factory=list)
    predictive_claim_licensed: bool = False


    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "mesh_id": self.mesh_id,
            "run_id": self.run_id,
            "mesh_fingerprint": self.mesh_fingerprint,
            "structural_checks": self.structural_checks,
            "executed_semantic_children": self.executed_semantic_children,
            "provider_states": self.provider_states,
            "findings": self.findings,
            "skipped_children": self.skipped_children,
            "claim_boundary": self.claim_boundary,
            "receipt_version": self.receipt_version,
            "generated_at": self.generated_at,
            "coverage_fingerprint": self.coverage_fingerprint,
            "predictive_profile": self.predictive_profile,
            "claim_atoms": self.claim_atoms,
            "required_guards": self.required_guards,
            "declared_guards": self.declared_guards,
            "missing_guards": self.missing_guards,
            "expected_model_nodes": self.expected_model_nodes,
            "discovered_model_nodes": self.discovered_model_nodes,
            "declared_model_nodes": self.declared_model_nodes,
            "excluded_model_nodes": self.excluded_model_nodes,
            "model_node_reconciliation_gaps": self.model_node_reconciliation_gaps,
            "executed_model_nodes": self.executed_model_nodes,
            "skipped_model_nodes": self.skipped_model_nodes,
            "expected_semantic_children": self.expected_semantic_children,
            "quantitative_coverage": self.quantitative_coverage,
            "predictive_gaps": self.predictive_gaps,
            "predictive_claim_licensed": self.predictive_claim_licensed,
        }


Executor = Callable[[GuardContract], tuple[SemanticStatus, list[dict[str, Any]], dict[str, Any], dict[str, Any]]]


@dataclass(frozen=True)
class SemanticExecutor:
    binding: SemanticBinding
    execute: Executor


def _finding(code: str, message: str, *, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "evidence": evidence or {}}


def _string_values(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [str(key) for key in value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _fluent_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [str(key) for key, active in value.items() if active]
    return _string_values(value)


def _coverage_context(contract: GuardContract) -> dict[str, Any]:
    value = contract.inputs.get("_semantic_coverage") or {}
    return dict(value) if isinstance(value, dict) else {}


def _resolve_event_guard(value: Any, declared_values: Mapping[str, Any]) -> bool | None:
    """Evaluate the deliberately small current EventGuard predicate surface."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if normalized.lower() == "true":
            return True
        if normalized.lower() == "false":
            return False
        declared = declared_values.get(normalized)
        if isinstance(declared, bool):
            return declared
    return None


def _variable_timepoint_map(contract: GuardContract) -> dict[str, list[str]]:
    """Read the one current variable-to-timepoint observation mapping."""

    observations = contract.inputs.get("variable_observations", {})
    if not isinstance(observations, Mapping):
        return {}
    return {
        str(variable_id): sorted(
            {
                str(timepoint_id)
                for timepoint_id in timepoint_ids
                if str(timepoint_id)
            }
        )
        for variable_id, timepoint_ids in sorted(observations.items())
        if str(variable_id) and isinstance(timepoint_ids, list)
    }


def _semantic_consumed_inputs(guard: str, contract: GuardContract, *, variable_timepoints: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """One projection shared by native producers and reusable-source validation."""
    inputs = contract.inputs
    if guard == "EventGuard":
        return {"event_model": inputs.get("event_model", {}), "events": inputs.get("events", []), "variable_observations": variable_timepoints or {}}
    if guard == "CausalGuard":
        return {"causal_model": inputs.get("causal_model", {}), "variable_observations": variable_timepoints or {}}
    if guard == "AgentGuard":
        return {"agent_model": inputs.get("agent_model", {}), "agents": inputs.get("beliefs", {})}
    if guard == "NormGuard":
        return {"norm_model": {"norms": inputs.get("norms", []), "facts": inputs.get("facts", [])}}
    key, default = {"SpaceGuard": ("spatial_relations", []), "ResourceGuard": ("resources", {}), "ConflictGuard": ("game_model", {})}[guard]
    return {key: inputs.get(key, default)}


def _event(contract: GuardContract):
    event_model = contract.inputs.get("event_model", {})
    events = contract.inputs.get("events", [])
    states = event_model.get("states", []) if isinstance(event_model, dict) else []
    transitions = (
        event_model.get("transitions", []) if isinstance(event_model, dict) else []
    )
    variable_timepoints = _variable_timepoint_map(contract)
    consumed = _semantic_consumed_inputs("EventGuard", contract, variable_timepoints=variable_timepoints)
    if not events and not states and not transitions:
        return SemanticStatus.GAP, [_finding("SEM_EVENT_MISSING_EVENTS", "No executable event, state, or transition records were supplied.")], consumed, {}
    contradictory = event_model.get("contradictory_fluents")
    if contradictory:
        return SemanticStatus.FAIL, [_finding("SEM_EVENT_CONTRADICTION", "Declared event fluents are contradictory.", evidence={"contradiction": contradictory})], consumed, {}
    overlapping_fluents = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        overlap = sorted(
            set(_fluent_values(event.get("terminates")))
            & set(_fluent_values(event.get("initiates")))
        )
        if overlap:
            overlapping_fluents.append(
                {
                    "index": index,
                    "event_id": event.get("event_id"),
                    "fluent_ids": overlap,
                }
            )
    if overlapping_fluents:
        return SemanticStatus.FAIL, [
            _finding(
                "SEM_EVENT_FLUENT_TRANSITION_CONTRADICTION",
                "One event cannot both terminate and initiate the same fluent.",
                evidence={"events": overlapping_fluents},
            )
        ], consumed, {}
    missing: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            missing.append({"index": index, "field": "event mapping"})
            continue
        for name in ("event_id", "at"):
            if not event.get(name):
                missing.append({"index": index, "field": name})
        if not any(event.get(name) for name in ("initiates", "terminates", "releases")):
            missing.append({"index": index, "field": "initiation/termination/release axiom"})
    for axiom in event_model.get("missing_axioms", []):
        missing.append({"field": str(axiom)})
    for index, state in enumerate(states):
        if not isinstance(state, dict):
            missing.append({"state": index, "field": "state mapping"})
            continue
        for name in ("state_id", "initial", "terminal"):
            value = state.get(name)
            if (
                (name == "state_id" and not value)
                or (name in {"initial", "terminal"} and not isinstance(value, bool))
            ):
                missing.append({"state": index, "field": name})
    for index, transition in enumerate(transitions):
        if not isinstance(transition, dict):
            missing.append({"transition": index, "field": "transition mapping"})
            continue
        for name in (
            "transition_id",
            "source_state",
            "target_state",
            "guard",
            "effect",
        ):
            if not transition.get(name):
                missing.append({"transition": index, "field": name})
    if missing:
        return SemanticStatus.GAP, [_finding("SEM_EVENT_MISSING_AXIOM", "Event records lack required temporal or fluent axioms.", evidence={"missing": missing})], consumed, {}

    if transitions and not states:
        return SemanticStatus.GAP, [
            _finding(
                "SEM_EVENT_MISSING_STATE_DENOMINATOR",
                "Transitions cannot be executed without the states they reference.",
            )
        ], consumed, {}

    state_id_list = [str(state["state_id"]) for state in states]
    transition_id_list = [str(transition["transition_id"]) for transition in transitions]
    duplicate_state_ids = sorted(
        {state_id for state_id in state_id_list if state_id_list.count(state_id) > 1}
    )
    duplicate_transition_ids = sorted(
        {
            transition_id
            for transition_id in transition_id_list
            if transition_id_list.count(transition_id) > 1
        }
    )
    if duplicate_state_ids or duplicate_transition_ids:
        return SemanticStatus.FAIL, [
            _finding(
                "SEM_EVENT_DUPLICATE_STATE_TRANSITION_ID",
                "State and transition identities must be unique within one event model.",
                evidence={
                    "duplicate_state_ids": duplicate_state_ids,
                    "duplicate_transition_ids": duplicate_transition_ids,
                },
            )
        ], consumed, {}

    declared_state_id_set = set(state_id_list)
    dangling_transitions = [
        {
            "transition_id": transition["transition_id"],
            "unknown_state_ids": sorted(
                {
                    str(transition[name])
                    for name in ("source_state", "target_state")
                    if str(transition[name]) not in declared_state_id_set
                }
            ),
        }
        for transition in transitions
        if any(
            str(transition[name]) not in declared_state_id_set
            for name in ("source_state", "target_state")
        )
    ]
    if dangling_transitions:
        return SemanticStatus.FAIL, [
            _finding(
                "SEM_EVENT_DANGLING_TRANSITION_STATE",
                "Every transition source and target must name a declared state.",
                evidence={"transitions": dangling_transitions},
            )
        ], consumed, {}

    initial_state_ids = {
        str(state["state_id"])
        for state in states
        if state.get("initial") is True
    }
    if transitions and not initial_state_ids:
        return SemanticStatus.GAP, [
            _finding(
                "SEM_EVENT_MISSING_INITIAL_STATE",
                "A bounded state-machine rollout needs at least one initial state.",
            )
        ], consumed, {}

    guard_values = event_model.get("guard_values", {})
    if not isinstance(guard_values, Mapping):
        guard_values = {}
    unresolved_guards = [
        {
            "transition_id": transition["transition_id"],
            "guard": transition["guard"],
        }
        for transition in transitions
        if _resolve_event_guard(transition["guard"], guard_values) is None
    ]
    if unresolved_guards:
        return SemanticStatus.GAP, [
            _finding(
                "SEM_EVENT_UNEVALUABLE_TRANSITION_GUARD",
                "Every transition guard must be a boolean constant or have a declared boolean value.",
                evidence={"transitions": unresolved_guards},
            )
        ], consumed, {}

    coverage = _coverage_context(contract)
    scenario_ids = _string_values(coverage.get("scenario_ids"))
    holdout_ids = _string_values(coverage.get("holdout_scenario_ids"))
    rollout_scenarios = [*scenario_ids, *holdout_ids] or ["default"]
    initial_fluents = set(_fluent_values(event_model.get("initial_states", [])))
    executed_scenarios: list[str] = []
    executed_holdouts: list[str] = []
    observed_timepoints: set[str] = set()
    declared_state_ids = set(state_id_list)
    declared_terminal_state_ids = {
        str(state.get("state_id"))
        for state in states
        if isinstance(state, dict) and state.get("state_id") and state.get("terminal")
    }
    declared_transition_ids: set[str] = set(transition_id_list)
    referenced_transition_state_ids: set[str] = set()
    for transition in transitions:
        if isinstance(transition, dict):
            referenced_transition_state_ids.update(
                str(transition.get(name))
                for name in ("source_state", "target_state")
                if transition.get(name)
            )
    executed_event_ids: set[str] = set()
    initiated_fluent_ids: set[str] = set()
    terminated_fluent_ids: set[str] = set()
    released_fluent_ids: set[str] = set()
    reached_fluent_ids: set[str] = set(initial_fluents)
    active_fluent_ids: set[str] = set()
    reached_state_ids: set[str] = set(initial_state_ids)
    executed_state_ids: set[str] = set(initial_state_ids)
    executed_transition_ids: set[str] = set()
    executed_branch_ids: set[str] = set()
    executed_perturbation_ids: set[str] = set()
    rollout_steps = 0
    final_fluent_ids_by_scenario: dict[str, list[str]] = {}
    for scenario_id in rollout_scenarios:
        active_fluents = set(initial_fluents)
        applicable = [
            event
            for event in events
            if not event.get("scenario_id") or str(event.get("scenario_id")) == scenario_id
        ]
        if not applicable:
            continue
        for event in sorted(applicable, key=lambda item: _event_time_key(item.get("at", ""))):
            rollout_steps += 1
            observed_timepoints.add(str(event.get("at")))
            event_id = str(event.get("event_id"))
            executed_event_ids.add(event_id)
            executed_branch_ids.update(_string_values(event.get("branch_id")))
            executed_perturbation_ids.update(
                _string_values(event.get("perturbation_id"))
            )
            for fluent in _fluent_values(event.get("terminates")):
                terminated_fluent_ids.add(fluent)
                active_fluents.discard(fluent)
            for fluent in _fluent_values(event.get("releases")):
                released_fluent_ids.add(fluent)
                active_fluents.discard(fluent)
            for fluent in _fluent_values(event.get("initiates")):
                initiated_fluent_ids.add(fluent)
                active_fluents.add(fluent)
                reached_fluent_ids.add(fluent)
        final_fluent_ids_by_scenario[scenario_id] = sorted(active_fluents)
        active_fluent_ids.update(active_fluents)
        if scenario_id in holdout_ids:
            executed_holdouts.append(scenario_id)
        elif scenario_id != "default":
            executed_scenarios.append(scenario_id)

    active_state_ids = set(initial_state_ids)
    remaining_transitions = list(transitions)
    for _ in range(max(1, len(transitions))):
        progressed = False
        for transition in list(remaining_transitions):
            source_state = str(transition["source_state"])
            if source_state not in active_state_ids:
                continue
            guard_value = _resolve_event_guard(transition["guard"], guard_values)
            remaining_transitions.remove(transition)
            if guard_value is False:
                continue
            target_state = str(transition["target_state"])
            transition_id = str(transition["transition_id"])
            active_state_ids.discard(source_state)
            active_state_ids.add(target_state)
            reached_state_ids.add(target_state)
            executed_state_ids.update({source_state, target_state})
            executed_transition_ids.add(transition_id)
            rollout_steps += 1
            progressed = True
        if not progressed:
            break
    return SemanticStatus.PASS, [], consumed, {
        "evaluated_events": len(events),
        "evaluated_states": len(states),
        "evaluated_transition_specs": len(transitions),
        "rollout_steps": rollout_steps,
        "observed_timepoints": sorted(observed_timepoints, key=_event_time_key),
        "observed_variable_timepoints": variable_timepoints,
        "executed_scenario_ids": executed_scenarios,
        "executed_holdout_scenario_ids": executed_holdouts,
        "declared_state_ids": sorted(declared_state_ids),
        "declared_terminal_state_ids": sorted(declared_terminal_state_ids),
        "declared_transition_ids": sorted(declared_transition_ids),
        "referenced_transition_state_ids": sorted(
            referenced_transition_state_ids
        ),
        "declared_initial_fluent_ids": sorted(initial_fluents),
        "initiated_fluent_ids": sorted(initiated_fluent_ids),
        "terminated_fluent_ids": sorted(terminated_fluent_ids),
        "released_fluent_ids": sorted(released_fluent_ids),
        "reached_fluent_ids": sorted(reached_fluent_ids),
        "active_fluent_ids": sorted(active_fluent_ids),
        "executed_event_ids": sorted(executed_event_ids),
        "reached_state_ids": sorted(reached_state_ids),
        "executed_state_ids": sorted(executed_state_ids),
        "executed_transition_ids": sorted(executed_transition_ids),
        "executed_branch_ids": sorted(executed_branch_ids),
        "executed_perturbation_ids": sorted(executed_perturbation_ids),
        "final_fluent_ids_by_scenario": final_fluent_ids_by_scenario,
    }


def _agent(contract: GuardContract):
    agent_model = contract.inputs.get("agent_model", {})
    agents = contract.inputs.get("beliefs", {})
    consumed = _semantic_consumed_inputs("AgentGuard", contract)
    if not isinstance(agents, dict) or not agents:
        return SemanticStatus.GAP, [_finding("SEM_AGENT_MISSING_MODEL", "No BDI agent records were supplied.")], consumed, {}
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
        return SemanticStatus.FAIL, [
            _finding(
                "SEM_AGENT_IDENTITY_MISMATCH",
                "Each BDI map key must equal the stable agent_id in its record.",
                evidence={"agents": identity_mismatches},
            )
        ], consumed, {}
    records = agents.values()
    missing = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            missing.append({"agent": index, "fields": ["beliefs", "desires", "intentions"]})
            continue
        absent = missing_bdi_fields(record)
        if absent:
            missing.append({"agent": record.get("agent_id", index), "fields": absent})
    if missing:
        return SemanticStatus.GAP, [_finding("SEM_AGENT_INCOMPLETE_BDI", "One or more agents lack BDI state required for the claim.", evidence={"missing": missing})], consumed, {}
    conflicts = agent_model.get("conflicting_intentions", []) if isinstance(agent_model, dict) else []
    if conflicts:
        return SemanticStatus.FAIL, [_finding("SEM_AGENT_CONFLICTING_INTENTIONS", "The BDI model declares conflicting intentions.", evidence={"conflicts": conflicts})], consumed, {}
    return SemanticStatus.PASS, [], consumed, {
        "evaluated_agents": len(agents),
        "agent_ids": sorted(str(key) for key in agents),
    }


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


def _space(contract: GuardContract):
    relations = contract.inputs.get("spatial_relations", [])
    consumed = _semantic_consumed_inputs("SpaceGuard", contract)
    if not relations:
        return SemanticStatus.GAP, [_finding("SEM_SPACE_MISSING_RCC8", "No RCC8 base relations were supplied.")], consumed, {}
    by_pair: dict[tuple[Any, Any, Any], set[str]] = defaultdict(set)
    ntpp: set[tuple[Any, Any, Any]] = set()
    malformed = []
    reflexive_conflicts = []
    for index, relation in enumerate(relations):
        if not isinstance(relation, dict):
            malformed.append({"index": index, "reason": "not a mapping"})
            continue
        rel = str(relation.get("relation", "")).upper()
        x, y, at = relation.get("x"), relation.get("y"), relation.get("at")
        if rel not in _RCC8 or x is None or y is None:
            malformed.append({"index": index, "relation": rel, "x": x, "y": y})
            continue
        by_pair[(x, y, at)].add(rel)
        if x == y and rel != "EQ":
            reflexive_conflicts.append(
                {
                    "index": index,
                    "at": at,
                    "object_id": x,
                    "relation": rel,
                    "expected": "EQ",
                }
            )
        if rel == "NTPP":
            ntpp.add((x, y, at))
    if malformed:
        return SemanticStatus.GAP, [_finding("SEM_SPACE_UNEVALUABLE_RCC8", "Some RCC8 relations are incomplete or unsupported.", evidence={"relations": malformed})], consumed, {}
    if reflexive_conflicts:
        return SemanticStatus.FAIL, [
            _finding(
                "SEM_SPACE_RCC8_REFLEXIVITY_CONFLICT",
                "An object related to itself must use RCC8 EQ.",
                evidence={"relations": reflexive_conflicts},
            )
        ], consumed, {}
    conflicts = [{"pair": list(pair), "relations": sorted(values)} for pair, values in by_pair.items() if len(values) > 1]
    for (x, y, at), observed in by_pair.items():
        reverse = by_pair.get((y, x, at), set())
        if not reverse:
            continue
        expected = {_RCC8_CONVERSE[relation] for relation in observed}
        if reverse != expected:
            conflicts.append(
                {
                    "pair": [x, y, at],
                    "relations": sorted(observed),
                    "reverse_relations": sorted(reverse),
                    "expected_reverse_relations": sorted(expected),
                    "conflict_kind": "converse",
                }
            )
    for a, b, at in ntpp:
        for b2, c, at2 in ntpp:
            if b2 != b or at2 != at:
                continue
            observed = by_pair.get((a, c, at), set())
            if observed and observed != {"NTPP"}:
                conflicts.append({"chain": [a, b, c], "at": at, "expected": "NTPP", "observed": sorted(observed)})
    if conflicts:
        if any(item.get("conflict_kind") == "converse" for item in conflicts):
            return SemanticStatus.FAIL, [_finding("SEM_SPACE_RCC8_CONVERSE_CONFLICT", "Declared reverse RCC8 relations are inconsistent.", evidence={"conflicts": conflicts})], consumed, {}
        return SemanticStatus.FAIL, [_finding("SEM_SPACE_RCC8_CONFLICT", "RCC8 base relations or NTPP composition are inconsistent.", evidence={"conflicts": conflicts})], consumed, {}
    return SemanticStatus.PASS, [], consumed, {"evaluated_relations": len(relations)}


def _resource(contract: GuardContract):
    resources = contract.inputs.get("resources", {})
    consumed = _semantic_consumed_inputs("ResourceGuard", contract)
    places = resources.get("places", {}) if isinstance(resources, dict) else {}
    transitions = resources.get("transitions", []) if isinstance(resources, dict) else []
    inventory = resources.get("inventory", []) if isinstance(resources, dict) else []
    inventory_output: dict[str, Any] = {}
    if inventory:
        malformed = [
            row
            for row in inventory
            if not isinstance(row, dict)
            or not row.get("resource_id")
            or not row.get("unit")
            or isinstance(row.get("quantity"), bool)
            or not isinstance(row.get("quantity"), (int, float))
            or not math.isfinite(float(row.get("quantity", 0)))
            or float(row.get("quantity", 0)) < 0
        ]
        if malformed:
            return SemanticStatus.GAP, [
                _finding(
                    "SEM_RESOURCE_MISSING_MODEL",
                    "Direct inventory records require stable identity, unit, and non-negative quantity.",
                    evidence={"records": malformed},
                )
            ], consumed, {}
        inventory_output = {
            "evaluated_inventory_records": len(inventory),
            "resource_ids": sorted(str(row["resource_id"]) for row in inventory),
        }
    if not places and not transitions:
        if inventory:
            return SemanticStatus.PASS, [], consumed, inventory_output
        return SemanticStatus.GAP, [_finding("SEM_RESOURCE_MISSING_MODEL", "Places and transitions are required for conservation rollout.")], consumed, {}
    if not places or not transitions:
        return SemanticStatus.GAP, [_finding("SEM_RESOURCE_MISSING_MODEL", "Both places and transitions are required when either transition-system field is declared.")], consumed, inventory_output
    available: dict[tuple[str, str], float] = defaultdict(float)
    demanded: dict[tuple[str, str], float] = defaultdict(float)
    for place, tokens in places.items():
        for token in tokens:
            available[(str(place), str(token.get("color", "")))] += float(token.get("qty", 0))
    # The declared list is a finite ordered firing trace, as in ResourceGuard:
    # each transition consumes its current marking, then produces for later ones.
    for index, transition in enumerate(transitions):
        for need in transition.get("consumes", []):
            key = (str(need.get("place", "")), str(need.get("color", "")))
            quantity = float(need.get("qty", 0))
            demanded[key] += quantity
            if quantity > available[key]:
                evidence = {"transition": transition.get("id"), "place": key[0], "color": key[1], "available": available[key], "demanded": quantity}
                if index == 0:
                    return SemanticStatus.GAP, [_finding("SEM_RESOURCE_MISSING_MODEL", "The first declared transition is not enabled by its initial marking.", evidence=evidence)], consumed, {}
                return SemanticStatus.FAIL, [_finding("SEM_RESOURCE_DOUBLE_CONSUMPTION", "The ordered transitions consume more finite resource than remains available.", evidence={"overspent": [evidence]})], consumed, {}
            available[key] -= quantity
        for produced in transition.get("produces", []):
            available[(str(produced.get("place", "")), str(produced.get("color", "")))] += float(produced.get("qty", 0))
    return SemanticStatus.PASS, [], consumed, {
        **inventory_output,
        "evaluated_transitions": len(transitions),
        "conserved_keys": len(demanded),
    }


_ALLOWED_AST = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.USub,
    ast.UAdd,
)


def _equation_error(expression: Any, known_names: set[str]) -> str:
    if isinstance(expression, (int, float, bool)):
        return ""
    if not isinstance(expression, str) or not expression.strip():
        return "equation is empty or not a supported scalar expression"
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return "equation is not valid expression syntax"
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST):
            return f"unsupported expression node: {type(node).__name__}"
        if isinstance(node, ast.Name) and node.id not in known_names:
            return f"unknown variable: {node.id}"
    return ""


def _safe_scalar_eval(expression: Any, environment: dict[str, float]) -> float:
    if isinstance(expression, bool):
        return float(expression)
    if isinstance(expression, (int, float)):
        return float(expression)
    tree = ast.parse(str(expression), mode="eval")
    return float(eval(compile(tree, "<worldguard-causal>", "eval"), {"__builtins__": {}}, environment))


def _scenario_records(value: Any) -> dict[str, dict[str, float]]:
    records: dict[str, dict[str, float]] = {}
    if isinstance(value, dict):
        for scenario_id, raw in value.items():
            if isinstance(raw, dict):
                records[str(scenario_id)] = {
                    str(key): float(item) for key, item in raw.items()
                }
    return records


def _evaluate_equations(
    variables: list[str],
    equations: dict[str, Any],
    seed: dict[str, float],
    overrides: dict[str, float] | None = None,
) -> tuple[dict[str, float], list[str]]:
    # A scenario may seed identity roots (x = x), but a pending endogenous
    # value is not an input to another equation until recomputed. Otherwise
    # declaration order can leak a stale seed into the final SCM result.
    identity_roots = {
        variable for variable in variables
        if isinstance(equations.get(variable), str)
        and isinstance((tree := ast.parse(equations[variable], mode="eval")).body, ast.Name)
        and tree.body.id == variable
    }
    environment = {
        key: value for key, value in seed.items()
        if key not in variables or key in identity_roots
    }
    overrides = dict(overrides or {})
    environment.update(overrides)
    remaining = [variable for variable in variables if variable not in overrides]
    errors: list[str] = []
    for _ in range(max(1, len(remaining) + 1)):
        progressed = False
        for variable in list(remaining):
            try:
                environment[variable] = _safe_scalar_eval(equations[variable], environment)
            except (KeyError, NameError):
                continue
            except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
                errors.append(f"{variable}:{type(exc).__name__}")
                remaining.remove(variable)
            else:
                remaining.remove(variable)
                progressed = True
        if not remaining or not progressed:
            break
    errors.extend(f"{variable}:unresolved_dependencies" for variable in remaining)
    return environment, errors


def _causal(contract: GuardContract):
    causal = contract.inputs.get("causal_model", {})
    variable_timepoints = _variable_timepoint_map(contract)
    consumed = _semantic_consumed_inputs("CausalGuard", contract, variable_timepoints=variable_timepoints)
    variables = [str(item) for item in causal.get("variables", [])]
    equations = causal.get("equations", {})
    graph = causal.get("graph", [])
    claim_scope = causal.get("claim_scope", "equation_model")
    if claim_scope == "graph_only":
        malformed = [
            {"index": index, "edge": edge}
            for index, edge in enumerate(graph)
            if not isinstance(edge, (list, tuple))
            or len(edge) != 2
            or any(str(value) not in variables for value in edge)
        ]
        if not variables or not graph or malformed:
            return SemanticStatus.GAP, [
                _finding(
                    "SEM_CAUSAL_MISSING_EQUATIONS",
                    "Graph-only evaluation requires declared variables and exact graph edges.",
                    evidence={"malformed_edges": malformed},
                )
            ], consumed, {}
        return SemanticStatus.PASS, [], consumed, {
            "evaluated_graph_edges": len(graph),
            "evaluated_variable_ids": variables,
            "observed_variable_timepoints": variable_timepoints,
        }
    if not variables or not isinstance(equations, dict):
        return SemanticStatus.GAP, [_finding("SEM_CAUSAL_MISSING_EQUATIONS", "Variables and structural equations are required.")], consumed, {}
    missing = [variable for variable in variables if variable not in equations]
    errors = {variable: _equation_error(equations.get(variable), set(variables) | set(causal.get("exogenous", []))) for variable in variables if variable in equations}
    errors = {key: value for key, value in errors.items() if value}
    if missing or errors:
        return SemanticStatus.GAP, [_finding("SEM_CAUSAL_UNEVALUABLE_EQUATION", "At least one structural equation is missing or outside the supported scalar subset.", evidence={"missing": missing, "errors": errors})], consumed, {}

    coverage = _coverage_context(contract)
    scenarios = _scenario_records(causal.get("scenarios", {}))
    holdouts = _scenario_records(causal.get("holdout_scenarios", {}))
    interventions = causal.get("interventions", [])
    counterfactuals = causal.get("counterfactuals", [])
    if not scenarios and not holdouts and not interventions and not counterfactuals:
        return SemanticStatus.GAP, [
            _finding(
                "SEM_CAUSAL_MISSING_BEHAVIOR_OBLIGATION",
                "An equation-model claim needs at least one declared scenario, holdout, intervention, or counterfactual to execute.",
            )
        ], consumed, {}
    scenario_ids = _string_values(coverage.get("scenario_ids")) or sorted(scenarios)
    holdout_ids = _string_values(coverage.get("holdout_scenario_ids")) or sorted(holdouts)
    scenario_results: dict[str, dict[str, float]] = {}
    execution_errors: list[dict[str, Any]] = []
    executed_scenarios: list[str] = []
    executed_holdouts: list[str] = []
    for scenario_id in scenario_ids:
        if scenario_id not in scenarios:
            continue
        values, row_errors = _evaluate_equations(variables, equations, scenarios[scenario_id])
        if row_errors:
            execution_errors.append({"scenario_id": scenario_id, "errors": row_errors})
            continue
        scenario_results[scenario_id] = values
        executed_scenarios.append(scenario_id)
    for scenario_id in holdout_ids:
        if scenario_id not in holdouts:
            continue
        values, row_errors = _evaluate_equations(variables, equations, holdouts[scenario_id])
        if row_errors:
            execution_errors.append({"scenario_id": scenario_id, "errors": row_errors})
            continue
        scenario_results[scenario_id] = values
        executed_holdouts.append(scenario_id)

    intervention_results: dict[str, dict[str, float]] = {}
    executed_interventions: list[str] = []
    for index, intervention in enumerate(interventions or []):
        if not isinstance(intervention, dict):
            continue
        intervention_id = str(intervention.get("intervention_id", ""))
        scenario_id = str(intervention.get("scenario_id", ""))
        if scenario_id in scenarios:
            seed = scenarios[scenario_id]
        elif scenario_id in holdouts:
            seed = holdouts[scenario_id]
        else:
            seed = {}
        assignments = intervention.get("set", {})
        if not isinstance(assignments, dict) or not seed:
            continue
        values, row_errors = _evaluate_equations(
            variables,
            equations,
            seed,
            {str(key): float(value) for key, value in assignments.items()},
        )
        if row_errors:
            execution_errors.append({"intervention_id": intervention_id, "errors": row_errors})
            continue
        intervention_results[intervention_id] = values
        executed_interventions.append(intervention_id)

    counterfactual_results: dict[str, Any] = {}
    executed_counterfactuals: list[str] = []
    for index, counterfactual in enumerate(counterfactuals or []):
        if not isinstance(counterfactual, dict):
            continue
        counterfactual_id = str(counterfactual.get("counterfactual_id", ""))
        intervention_id = str(counterfactual.get("intervention_id", ""))
        query = str(counterfactual.get("query", ""))
        result = intervention_results.get(intervention_id)
        if not result or query not in result:
            continue
        counterfactual_results[counterfactual_id] = result[query]
        executed_counterfactuals.append(counterfactual_id)

    declared_intervention_ids = [
        str(item.get("intervention_id", ""))
        for item in interventions or []
        if isinstance(item, dict)
    ]
    declared_counterfactual_ids = [
        str(item.get("counterfactual_id", ""))
        for item in counterfactuals or []
        if isinstance(item, dict)
    ]
    missing_executions = {
        "scenario_ids": sorted(set(scenario_ids) - set(executed_scenarios)),
        "holdout_scenario_ids": sorted(set(holdout_ids) - set(executed_holdouts)),
        "intervention_ids": sorted(
            set(declared_intervention_ids) - set(executed_interventions)
        ),
        "counterfactual_ids": sorted(
            set(declared_counterfactual_ids) - set(executed_counterfactuals)
        ),
    }
    missing_executions = {
        key: value for key, value in missing_executions.items() if value
    }
    if execution_errors or missing_executions:
        return SemanticStatus.GAP, [
            _finding(
                "SEM_CAUSAL_ROLLOUT_ERROR",
                "One or more declared causal scenarios could not be evaluated safely.",
                evidence={
                    "errors": execution_errors,
                    "missing_executions": missing_executions,
                },
            )
        ], consumed, {
            "evaluated_equations": len(variables),
            "executed_scenario_ids": executed_scenarios,
            "executed_holdout_scenario_ids": executed_holdouts,
            "executed_intervention_ids": executed_interventions,
            "executed_counterfactual_ids": executed_counterfactuals,
            "observed_variable_timepoints": variable_timepoints,
        }
    return SemanticStatus.PASS, [], consumed, {
        "evaluated_equations": len(variables),
        "executed_scenario_ids": executed_scenarios,
        "executed_holdout_scenario_ids": executed_holdouts,
        "executed_intervention_ids": executed_interventions,
        "executed_counterfactual_ids": executed_counterfactuals,
        "observed_variable_timepoints": variable_timepoints,
        "scenario_results": scenario_results,
        "intervention_results": intervention_results,
        "counterfactual_results": counterfactual_results,
    }


def _conflict(contract: GuardContract):
    game = contract.inputs.get("game_model", {})
    consumed = _semantic_consumed_inputs("ConflictGuard", contract)
    required = [name for name in ("players", "actions", "states", "transitions", "payoffs") if not game.get(name)]
    if required:
        return SemanticStatus.GAP, [_finding("SEM_CONFLICT_INCOMPLETE_GAME", "Conflict rollout requires players, actions, states, transitions, and payoffs.", evidence={"missing": required})], consumed, {}
    players = game.get("players", [])
    duplicate_participants = sorted(
        {
            str(participant)
            for participant in players
            if players.count(participant) > 1
        }
    )
    if duplicate_participants:
        return SemanticStatus.FAIL, [
            _finding(
                "SEM_CONFLICT_DUPLICATE_PARTICIPANT",
                "A finite conflict model requires distinct participant identities.",
                evidence={"participant_ids": duplicate_participants},
            )
        ], consumed, {}
    actions = game.get("actions", [])
    states = game.get("states", [])
    transitions = game.get("transitions", [])
    payoffs = game.get("payoffs", [])
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
        return SemanticStatus.FAIL, [
            _finding(
                "SEM_CONFLICT_REFERENCE_CLOSURE",
                "Conflict transitions and payoffs must reference declared players, states, and actions.",
                evidence={"references": reference_errors},
            )
        ], consumed, {}
    invalid = []
    for transition in transitions:
        probabilities = transition.get("probabilities")
        if probabilities and abs(sum(float(value) for value in probabilities) - 1.0) > 0.0001:
            invalid.append(transition)
    if invalid:
        return SemanticStatus.FAIL, [_finding("SEM_CONFLICT_INVALID_TRANSITION", "Conflict transition probabilities do not sum to one.", evidence={"transitions": invalid})], consumed, {}
    return SemanticStatus.PASS, [], consumed, {
        "evaluated_transitions": len(transitions),
        "issue": game.get("issue"),
    }


def _norm(contract: GuardContract):
    norms = contract.inputs.get("norms", [])
    facts = contract.inputs.get("facts", [])
    consumed = _semantic_consumed_inputs("NormGuard", contract)
    if not norms:
        return SemanticStatus.GAP, [_finding("SEM_NORM_MISSING_MODEL", "No norms were supplied.")], consumed, {}
    invalid_modalities = sorted(
        {
            str(norm.get("modality", ""))
            for norm in norms
            if isinstance(norm, dict)
            and str(norm.get("modality", "")) not in NORM_MODALITIES
        }
    )
    if invalid_modalities:
        return SemanticStatus.FAIL, [
            _finding(
                "SEM_NORM_MODALITY_UNKNOWN",
                "Norm modality is outside the current deontic enumeration.",
                evidence={
                    "observed": invalid_modalities,
                    "allowed": sorted(NORM_MODALITIES),
                },
            )
        ], consumed, {}
    malformed_facts = [
        {"index": index, "fact": item}
        for index, item in enumerate(facts)
        if not isinstance(item, dict)
        or not item.get("fact_id")
        or not isinstance(item.get("value"), bool)
    ]
    if malformed_facts:
        return SemanticStatus.GAP, [
            _finding(
                "SEM_NORM_UNEVALUABLE_FACT",
                "Norm conditions require facts with stable ids and explicit boolean values.",
                evidence={"facts": malformed_facts},
            )
        ], consumed, {}

    fact_id_list = [str(item["fact_id"]) for item in facts]
    duplicate_fact_ids = sorted(
        {fact_id for fact_id in fact_id_list if fact_id_list.count(fact_id) > 1}
    )
    if duplicate_fact_ids:
        return SemanticStatus.FAIL, [
            _finding(
                "SEM_NORM_DUPLICATE_FACT_ID",
                "A norm model cannot give one fact identity multiple truth values.",
                evidence={"fact_ids": duplicate_fact_ids},
            )
        ], consumed, {}

    fact_values = {str(item["fact_id"]): item["value"] for item in facts}
    missing = []
    active = []
    for index, norm in enumerate(norms):
        condition = norm.get("condition") if isinstance(norm, dict) else None
        needed = ""
        expected: bool | None = None
        if isinstance(condition, str) and condition:
            needed = condition
            expected = True
        elif isinstance(condition, dict):
            needed = str(condition.get("fact_id", ""))
            expected_value = condition.get(
                "equals", condition.get("value", True)
            )
            if isinstance(expected_value, bool):
                expected = expected_value
        if not needed or expected is None or needed not in fact_values:
            missing.append(
                {
                    "norm": index,
                    "condition": condition,
                    "needed_fact": needed or "condition fact",
                }
            )
        elif fact_values[needed] is expected:
            active.append(norm)
    if missing:
        return SemanticStatus.GAP, [_finding("SEM_NORM_MISSING_CONDITION_FACT", "Norm applicability cannot be evaluated without declared condition facts.", evidence={"missing": missing})], consumed, {}
    conflicts = active_norm_conflicts(active)
    if conflicts:
        return SemanticStatus.FAIL, [
            _finding(
                "SEM_NORM_ACTIVE_CONFLICT",
                "Active norms both forbid and permit or require the same action of the same actor.",
                evidence={"conflicts": conflicts},
            )
        ], consumed, {}
    return SemanticStatus.PASS, [], consumed, {"evaluated_norms": len(norms), "condition_facts": len(fact_values)}


def _binding(
    guard: str,
    possible_consumed_input_fields: tuple[str, ...],
    semantics: tuple[str, ...],
    boundary: str,
) -> SemanticBinding:
    return SemanticBinding(
        executor_id=f"worldguard.semantic.{guard.removesuffix('Guard').lower()}.v1",
        guard=guard,
        possible_consumed_input_fields=possible_consumed_input_fields,
        output_fields=("status", "findings", "consumed_inputs", "outputs"),
        supported_semantics=semantics,
        unsupported_boundary=boundary,
    )


EXECUTOR_REGISTRY: dict[str, SemanticExecutor] = {
    "EventGuard": SemanticExecutor(_binding("EventGuard", ("inputs.events", "inputs.event_model.contradictory_fluents", "inputs.event_model.initial_states", "inputs.event_model.missing_axioms", "inputs.event_model.states", "inputs.event_model.transitions", "inputs.event_model.guard_values", "inputs.variable_observations", "mesh.semantic_coverage"), ("event_axiom_completeness", "state_transition_identity_closure", "boolean_guard_evaluation", "fluent_consistency", "bounded_state_and_event_rollout", "scenario_and_holdout_execution", "declared_variable_timepoint_observation"), "arbitrary predicate languages, unbounded temporal theorem proving, and continuous dynamics"), _event),
    "AgentGuard": SemanticExecutor(_binding("AgentGuard", ("inputs.beliefs", "inputs.agent_model"), ("agent_identity_closure", "bdi_completeness", "declared_intention_conflict"), "open-ended planning and belief revision"), _agent),
    "SpaceGuard": SemanticExecutor(_binding("SpaceGuard", ("inputs.spatial_relations",), ("rcc8_base_and_converse_consistency", "ntpp_transitivity"), "metric geometry and full RCC8 closure"), _space),
    "ResourceGuard": SemanticExecutor(_binding("ResourceGuard", ("inputs.resources.inventory", "inputs.resources.places", "inputs.resources.transitions"), ("declared_inventory_validity", "inventory_and_transition_coevaluation", "finite_resource_conservation"), "unbounded colored Petri-net reachability"), _resource),
    "CausalGuard": SemanticExecutor(_binding("CausalGuard", ("inputs.causal_model.variables", "inputs.causal_model.graph", "inputs.causal_model.claim_scope", "inputs.causal_model.equations", "inputs.causal_model.exogenous", "inputs.causal_model.scenarios", "inputs.causal_model.holdout_scenarios", "inputs.causal_model.interventions", "inputs.causal_model.counterfactuals", "inputs.variable_observations", "mesh.semantic_coverage"), ("declared_graph_consistency", "safe_scalar_equation_evaluability", "required_behavior_obligation", "bounded_scenario_rollout", "declared_intervention_execution", "declared_counterfactual_query", "declared_variable_timepoint_observation"), "arbitrary code, external solvers, and causal identification"), _causal),
    "ConflictGuard": SemanticExecutor(_binding("ConflictGuard", ("inputs.game_model.players", "inputs.game_model.actions", "inputs.game_model.states", "inputs.game_model.transitions", "inputs.game_model.payoffs", "inputs.game_model.issue"), ("finite_game_completeness", "player_state_action_reference_closure", "transition_probability"), "equilibrium solving and open-ended strategy search"), _conflict),
    "NormGuard": SemanticExecutor(_binding("NormGuard", ("inputs.norms", "inputs.facts"), ("condition_fact_binding", "boolean_fact_truth_evaluation"), "general deontic theorem proving and legal interpretation"), _norm),
}


def execute_semantic(
    *,
    node_id: str,
    guard: str,
    contract: GuardContract,
    provider_available: bool,
    coverage_context: dict[str, Any] | None = None,
) -> SemanticExecutionReceipt:

    executor = EXECUTOR_REGISTRY.get(guard)
    if executor is None:
        binding = _binding(guard, (), (), "no WorldGuard-owned semantic executor is registered")
        return SemanticExecutionReceipt(
            node_id=node_id,
            guard=guard,
            status=SemanticStatus.BOUNDARY_ONLY,
            provider_status=ProviderStatus.UNAVAILABLE,
            binding=binding,
            findings=[_finding("SEM_EXECUTOR_UNREGISTERED", "No semantic executor is registered for this guard.")],
            skipped_reason="unregistered_executor",
        )
    if not provider_available:
        return SemanticExecutionReceipt(
            node_id=node_id,
            guard=guard,
            status=SemanticStatus.NOT_RUN,
            provider_status=ProviderStatus.UNAVAILABLE,
            binding=executor.binding,
            findings=[_finding("SEM_PROVIDER_UNAVAILABLE", "The required semantic provider was explicitly marked unavailable.")],
            skipped_reason="provider_unavailable",
        )
    if coverage_context:
        contract = replace(
            contract,
            inputs={**contract.inputs, "_semantic_coverage": dict(coverage_context)},
        )
    status, findings, consumed_inputs, outputs = executor.execute(contract)
    return SemanticExecutionReceipt(
        node_id=node_id,
        guard=guard,
        status=status,
        provider_status=ProviderStatus.AVAILABLE,
        binding=executor.binding,
        findings=findings,
        consumed_inputs=consumed_inputs,
        outputs=outputs,
    )


def aggregate_semantic_status(receipts: list[SemanticExecutionReceipt]) -> SemanticStatus:
    statuses = [receipt.status for receipt in receipts]
    if any(status == SemanticStatus.FAIL for status in statuses):
        return SemanticStatus.FAIL
    if any(status == SemanticStatus.GAP for status in statuses):
        return SemanticStatus.GAP
    if any(status == SemanticStatus.BOUNDARY_ONLY for status in statuses):
        return SemanticStatus.BOUNDARY_ONLY
    if any(status == SemanticStatus.NOT_RUN for status in statuses):
        return SemanticStatus.NOT_RUN
    if statuses and all(status == SemanticStatus.PASS for status in statuses):
        return SemanticStatus.PASS
    return SemanticStatus.NOT_RUN


def aggregate_provider_status(receipts: list[SemanticExecutionReceipt], *, required: bool) -> ProviderStatus:
    if not required:
        return ProviderStatus.NOT_REQUIRED
    statuses = {receipt.provider_status for receipt in receipts}
    if not statuses or statuses == {ProviderStatus.UNAVAILABLE}:
        return ProviderStatus.UNAVAILABLE
    if statuses == {ProviderStatus.STALE}:
        return ProviderStatus.STALE
    if statuses == {ProviderStatus.AVAILABLE}:
        return ProviderStatus.AVAILABLE
    return ProviderStatus.MIXED


def fingerprint_mesh(data: dict[str, Any]) -> str:
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
