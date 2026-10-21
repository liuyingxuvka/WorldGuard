"""WorldGuard family oracle catalog and per-task Guard purpose contracts.

An author-side maintenance tool may supervise this module as one declared
native check, but WorldGuard alone owns the purposes, failure classes, fixtures,
and oracle semantics. The
family inventory is baseline regression authority; every real model child still
requires its own explicit task-model-instance declaration and native proof.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from .contracts import GuardContract
from .guards import GUARD_RUNNERS
from .semantic import EXECUTOR_REGISTRY, SemanticStatus, execute_semantic
from .status import GuardStatus


@dataclass(frozen=True)
class GuardModelPurpose:
    guard: str
    purpose: str
    blocked_claims: tuple[str, ...]
    boundary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "guard": self.guard,
            "purpose": self.purpose,
            "blocked_claims": list(self.blocked_claims),
            "boundary": self.boundary,
        }


@dataclass(frozen=True)
class NativeGoodCase:
    case_id: str
    guard: str
    text: str
    inputs: Mapping[str, Any]
    coverage_context: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "guard": self.guard,
            "text": self.text,
            "inputs": dict(self.inputs),
            "coverage_context": dict(self.coverage_context),
        }


@dataclass(frozen=True)
class ProtectedFailureClass:
    failure_id: str
    guard: str
    layer: str
    code: str
    expected_status: str
    blocked_claim: str
    text: str = ""
    inputs: Mapping[str, Any] = field(default_factory=dict)
    coverage_context: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "guard": self.guard,
            "layer": self.layer,
            "code": self.code,
            "expected_status": self.expected_status,
            "blocked_claim": self.blocked_claim,
            "text": self.text,
            "inputs": dict(self.inputs),
            "coverage_context": dict(self.coverage_context),
        }




GUARD_MODEL_PURPOSES = (
    GuardModelPurpose(
        "EventGuard",
        "Prevent declared event/state/transition claims from passing when records are absent, incomplete, or contradictory.",
        ("event/state/transition existence without an exact record", "dangling or duplicate state/transition identities", "unevaluable declared transition guards", "contradictory fluents", "missing temporal, fluent, or declaration fields"),
        "Arbitrary predicate languages, unbounded terminal reachability, continuous numeric dynamics, physical equations, causality, norms, and resource enablement remain outside EventGuard.",
    ),
    GuardModelPurpose(
        "AgentGuard",
        "Prevent BDI claims from passing when agent identity/state is absent, mismatched, incomplete, or internally conflicting.",
        ("map key and agent_id mismatch", "missing beliefs, desires, or intentions", "conflicting intentions"),
        "Payoff equilibrium, causal effects, resource tokens, and deontic permission remain outside AgentGuard.",
    ),
    GuardModelPurpose(
        "SpaceGuard",
        "Prevent qualitative spatial claims from passing without evaluable and consistent RCC8 relations.",
        ("missing RCC8 relations", "malformed RCC8 relations", "inconsistent RCC8 converse, base relations, or composition"),
        "Metric geometry, sensor fusion, and continuous dynamics remain outside SpaceGuard.",
    ),
    GuardModelPurpose(
        "ResourceGuard",
        "Prevent direct inventory or finite-resource claims from passing without valid declared quantities/an executable resource model or when tokens and capacities are violated.",
        ("invalid direct inventory", "inventory hiding an invalid transition system", "missing places or transitions", "missing colored tokens", "capacity overflow", "combined over-consumption"),
        "Norms, permission, real physics, price, and causality remain outside ResourceGuard.",
    ),
    GuardModelPurpose(
        "CausalGuard",
        "Prevent graph-only or SCM claims from passing with malformed/cyclic graphs or missing, unevaluable, or behaviorally unexercised structural equations.",
        ("malformed declared graph", "missing structural equations", "missing executable behavior obligation", "directed cycles", "unsafe or unresolved scalar rollout"),
        "Mechanism truth, temporal story order, norms, resources, and game payoffs remain outside CausalGuard.",
    ),
    GuardModelPurpose(
        "ConflictGuard",
        "Prevent finite-game claims from passing with incomplete or cross-wired games, invalid probabilities, missing payoffs, or contradictory policy evidence.",
        ("incomplete game models", "foreign player/state/action references", "invalid transition probabilities", "missing payoffs", "policy contradictions"),
        "Deontic permission, physical enablement, and SCM causality remain outside ConflictGuard.",
    ),
    GuardModelPurpose(
        "NormGuard",
        "Prevent deontic claims from passing without applicable norms and facts or when the claim contradicts a prohibition.",
        ("missing norm models", "missing permission or obligation", "missing condition facts", "forbidden-action contradictions"),
        "Physical enablement, resource availability, payoff optimality, and causal effects remain outside NormGuard.",
    ),
)


NATIVE_GOOD_CASES = (
    NativeGoodCase(
        "good:event",
        "EventGuard",
        "a declared event initiates readiness",
        {"events": [{"event_id": "e1", "at": "t0", "initiates": "ready"}]},
    ),
    NativeGoodCase(
        "good:agent",
        "AgentGuard",
        "the agent has a complete BDI state",
        {"beliefs": {"agent": {"agent_id": "agent", "beliefs": ["b"], "desires": ["d"], "intentions": ["i"]}}},
    ),
    NativeGoodCase(
        "good:space",
        "SpaceGuard",
        "the declared regions are disconnected",
        {"spatial_relations": [{"at": "t0", "x": "a", "y": "b", "relation": "DC"}]},
    ),
    NativeGoodCase(
        "good:resource",
        "ResourceGuard",
        "the declared transition has enough finite resource",
        {
            "resources": {
                "places": {"tank": [{"color": "h2", "qty": 2}]},
                "transitions": [{"id": "run", "consumes": [{"place": "tank", "color": "h2", "qty": 1}]}],
            }
        },
    ),
    NativeGoodCase(
        "good:causal",
        "CausalGuard",
        "the scalar SCM equation is complete and evaluable",
        {"causal_model": {"variables": ["y"], "equations": {"y": "x * 2"}, "exogenous": ["x"], "graph": [], "scenarios": {"s1": {"x": 2}}}},
    ),
    NativeGoodCase(
        "good:conflict",
        "ConflictGuard",
        "the finite game is complete and probabilistically valid",
        {
            "game_model": {
                "players": ["a", "b"],
                "actions": {"a": ["hold"], "b": ["hold"]},
                "states": ["s"],
                "transitions": [{"from": "s", "to": "s", "probabilities": [1.0]}],
                "payoffs": [{"state": "s", "reward": {"a": 1, "b": 1}}],
            }
        },
    ),
    NativeGoodCase(
        "good:norm",
        "NormGuard",
        "the operator may start when the declared condition fact holds",
        {
            "norms": [{"modality": "permitted", "action": "start", "condition": "authorized"}],
            "facts": [{"fact_id": "authorized", "value": True}],
        },
    ),
)


def _failure(
    guard: str,
    layer: str,
    code: str,
    status: str,
    blocked_claim: str,
    *,
    text: str = "",
    inputs: Mapping[str, Any] | None = None,
    coverage_context: Mapping[str, Any] | None = None,
) -> ProtectedFailureClass:
    slug = code.lower().replace("_", "-")
    return ProtectedFailureClass(
        failure_id=f"failure:{guard.removesuffix('Guard').lower()}:{layer}:{slug}",
        guard=guard,
        layer=layer,
        code=code,
        expected_status=status,
        blocked_claim=blocked_claim,
        text=text,
        inputs=dict(inputs or {}),
        coverage_context=dict(coverage_context or {}),
    )


PROTECTED_FAILURE_CLASSES = (
    _failure("EventGuard", "guard", "EVENT_BOUNDARY_NUMERIC_DYNAMICS", "BOUNDARY_EXCEEDED", "EventGuard cannot support a numeric-dynamics claim.", text="continuous numeric dynamics"),
    _failure("EventGuard", "guard", "EVENT_MISSING_EVENT_MODEL", "GAP", "An event claim cannot pass without events or an event model."),
    _failure("EventGuard", "guard", "EVENT_CONTRADICTORY_FLUENTS", "FAIL", "Contradictory event fluents must reject the claim.", inputs={"event_model": {"contradictory_fluents": ["hot", "cold"]}}),
    _failure("EventGuard", "guard", "EVENT_FLUENT_TRANSITION_CONTRADICTION", "FAIL", "One event cannot terminate and initiate the same fluent.", inputs={"events": [{"event_id": "e1", "at": "t0", "terminates": ["ready"], "initiates": ["ready"]}]}),
    _failure("EventGuard", "guard", "EVENT_MISSING_INITIATION_AXIOM", "GAP", "A declared event model cannot pass with missing event axioms.", inputs={"event_model": {"missing_axioms": ["initiates"]}}),
    _failure("EventGuard", "guard", "EVENT_DANGLING_TRANSITION_STATE", "FAIL", "A transition cannot name a state outside the declared state denominator.", inputs={"event_model": {"states": [{"state_id": "waiting", "initial": True, "terminal": False}], "transitions": [{"transition_id": "go", "source_state": "waiting", "target_state": "missing", "guard": True, "effect": "done"}]}}),
    _failure("EventGuard", "guard", "EVENT_MISSING_STATE_DENOMINATOR", "GAP", "A transition model cannot qualify without declared states.", inputs={"event_model": {"transitions": [{"transition_id": "go", "source_state": "waiting", "target_state": "done", "guard": True, "effect": "done"}]}}),
    _failure("EventGuard", "guard", "EVENT_DUPLICATE_STATE_TRANSITION_ID", "FAIL", "State and transition ids must be unique.", inputs={"event_model": {"states": [{"state_id": "waiting", "initial": True, "terminal": False}, {"state_id": "waiting", "initial": False, "terminal": True}]}}),
    _failure("EventGuard", "guard", "EVENT_MISSING_INITIAL_STATE", "GAP", "A transition rollout cannot start without an initial state.", inputs={"event_model": {"states": [{"state_id": "waiting", "initial": False, "terminal": False}], "transitions": [{"transition_id": "stay", "source_state": "waiting", "target_state": "waiting", "guard": True, "effect": "wait"}]}}),
    _failure("AgentGuard", "guard", "AGENT_BOUNDARY_NON_BDI", "BOUNDARY_EXCEEDED", "AgentGuard cannot support a payoff-equilibrium claim.", text="payoff equilibrium"),
    _failure("AgentGuard", "guard", "AGENT_CONFLICTING_INTENTIONS", "FAIL", "Conflicting intentions must reject the BDI claim.", inputs={"agent_model": {"conflicting_intentions": ["start", "stop"]}}),
    _failure("AgentGuard", "guard", "AGENT_MISSING_BELIEF", "GAP", "A BDI claim cannot pass without its required belief state.", inputs={"agent_model": {"missing_beliefs": ["ready"]}}),
    _failure("AgentGuard", "guard", "AGENT_IDENTITY_MISMATCH", "FAIL", "A BDI record cannot be owned by a map key different from its agent_id.", inputs={"beliefs": {"alice": {"agent_id": "bob", "beliefs": ["b"], "desires": ["d"], "intentions": ["i"]}}}),
    _failure("AgentGuard", "guard", "AGENT_INCOMPLETE_BDI", "GAP", "A declared agent needs beliefs, desires, and intentions.", inputs={"beliefs": {"alice": {"agent_id": "alice", "beliefs": ["b"], "desires": [], "intentions": ["i"]}}}),
    _failure("SpaceGuard", "guard", "SPACE_BOUNDARY_METRIC_GEOMETRY", "BOUNDARY_EXCEEDED", "SpaceGuard cannot support metric-distance claims.", text="metric distance in meters"),
    _failure("SpaceGuard", "guard", "SPACE_MISSING_RELATION", "GAP", "An RCC8 claim cannot pass without a relation."),
    _failure("SpaceGuard", "guard", "SPACE_RCC8_CONTRADICTION", "FAIL", "Conflicting RCC8 base relations must reject the claim.", inputs={"spatial_relations": [{"at": "t0", "x": "a", "y": "b", "relation": "DC"}, {"at": "t0", "x": "a", "y": "b", "relation": "EQ"}]}),
    _failure("SpaceGuard", "guard", "SPACE_RCC8_REFLEXIVITY_CONTRADICTION", "FAIL", "A non-EQ RCC8 relation from an object to itself must reject the claim.", inputs={"spatial_relations": [{"at": "t0", "x": "a", "y": "a", "relation": "DC"}]}),
    _failure("SpaceGuard", "guard", "SPACE_RCC8_CONVERSE_CONTRADICTION", "FAIL", "Declared reverse RCC8 relations must be exact converses.", inputs={"spatial_relations": [{"at": "t0", "x": "a", "y": "b", "relation": "EC"}, {"at": "t0", "x": "b", "y": "a", "relation": "DC"}]}),
    _failure("SpaceGuard", "guard", "SPACE_UNEVALUABLE_RCC8", "GAP", "A malformed or unsupported RCC8 record cannot qualify.", inputs={"spatial_relations": [{"at": "t0", "x": "a", "y": "b", "relation": "NEAR"}]}),
    _failure("ResourceGuard", "guard", "RESOURCE_BOUNDARY_NORM_AUTHORIZATION", "BOUNDARY_EXCEEDED", "ResourceGuard cannot support a permission claim.", text="permission to run"),
    _failure("ResourceGuard", "guard", "RESOURCE_MISSING_RESOURCE_MODEL", "GAP", "A resource claim cannot pass without places and transitions."),
    _failure("ResourceGuard", "guard", "RESOURCE_MISSING_TOKEN", "GAP", "A transition cannot pass when required colored tokens are absent.", inputs={"resources": {"places": {"tank": [{"color": "h2", "qty": 0}]}, "transitions": [{"id": "run", "consumes": [{"place": "tank", "color": "h2", "qty": 1}]}]}}),
    _failure("ResourceGuard", "guard", "RESOURCE_CAPACITY_OVERFLOW", "FAIL", "A transition that exceeds capacity must reject the claim.", inputs={"resources": {"places": {"tank": [{"color": "h2", "qty": 2}]}, "capacities": {"out": 1}, "transitions": [{"id": "run", "consumes": [{"place": "tank", "color": "h2", "qty": 1}], "produces": [{"place": "out", "color": "kwh", "qty": 2}]}]}}),
    _failure("ResourceGuard", "guard", "RESOURCE_CUMULATIVE_OVERCONSUMPTION", "FAIL", "Inventory presence cannot hide cumulative transition over-consumption.", inputs={"resources": {"inventory": [{"resource_id": "h2", "unit": "unit", "quantity": 1}], "places": {"tank": [{"color": "h2", "qty": 1}]}, "transitions": [{"id": "use-1", "consumes": [{"place": "tank", "color": "h2", "qty": 1}]}, {"id": "use-2", "consumes": [{"place": "tank", "color": "h2", "qty": 1}]}]}}),
    _failure("ResourceGuard", "guard", "RESOURCE_UNEVALUABLE_TOKEN", "GAP", "Malformed resource tokens cannot enter a conservation rollout.", inputs={"resources": {"places": {"tank": [{"color": "h2", "qty": "bad"}]}, "transitions": [{"id": "run", "consumes": []}]}}),
    _failure("ResourceGuard", "guard", "RESOURCE_UNEVALUABLE_TRANSITION", "GAP", "Malformed resource transitions cannot enter a conservation rollout.", inputs={"resources": {"places": {"tank": [{"color": "h2", "qty": 1}]}, "transitions": [{"consumes": []}]}}),
    _failure("CausalGuard", "guard", "CAUSAL_BOUNDARY_TEMPORAL_STORY", "BOUNDARY_EXCEEDED", "CausalGuard cannot promote temporal order alone into SCM evidence.", text="temporal story after an event"),
    _failure("CausalGuard", "guard", "CAUSAL_CYCLE", "FAIL", "A directed cycle must reject the SCM claim.", inputs={"causal_model": {"variables": ["x", "y"], "equations": {"x": 1, "y": 2}, "graph": [["x", "y"], ["y", "x"]]}}),
    _failure("CausalGuard", "guard", "CAUSAL_MISSING_STRUCTURAL_EQUATION", "GAP", "Every declared SCM variable must have a structural equation.", inputs={"causal_model": {"variables": ["x", "y"], "equations": {"x": 1}, "graph": []}}),
    _failure("CausalGuard", "guard", "CAUSAL_MISSING_BEHAVIOR_OBLIGATION", "GAP", "An equation model cannot qualify behavior without a declared executable scenario, holdout, intervention, or counterfactual.", inputs={"causal_model": {"variables": ["x"], "equations": {"x": 1}, "graph": []}}),
    _failure("ConflictGuard", "guard", "CONFLICT_BOUNDARY_DEONTIC_OBLIGATION", "BOUNDARY_EXCEEDED", "ConflictGuard cannot support a deontic obligation.", text="deontic obligation"),
    _failure("ConflictGuard", "guard", "CONFLICT_INVALID_PROBABILITY", "FAIL", "Invalid transition probabilities must reject the finite-game claim.", inputs={"game_model": {"transitions": [{"probabilities": [0.7, 0.7]}], "payoffs": [{"state": "s"}]}}),
    _failure("ConflictGuard", "guard", "CONFLICT_DUPLICATE_PARTICIPANT", "FAIL", "Duplicate participant identities must reject the finite-game claim.", inputs={"game_model": {"players": ["a", "a"], "transitions": [{"probabilities": [1.0]}], "payoffs": [{"state": "s"}]}}),
    _failure("ConflictGuard", "guard", "CONFLICT_MISSING_PAYOFF", "GAP", "A finite-game claim cannot pass without payoff evidence.", inputs={"game_model": {"transitions": []}}),
    _failure("ConflictGuard", "guard", "CONFLICT_REFERENCE_CLOSURE", "FAIL", "Finite-game transitions and payoffs cannot reference undeclared states or players.", inputs={"game_model": {"players": ["alice", "bob"], "actions": ["share"], "states": ["open"], "transitions": [{"from": "ghost", "to": "void", "probabilities": [1.0]}], "payoffs": [{"player": "mallory", "state": "void", "value": 1}]}}),
    _failure("ConflictGuard", "guard", "CONFLICT_INCOMPLETE_GAME", "GAP", "A finite game cannot qualify without players, actions, states, transitions, and payoffs.", inputs={"game_model": {"payoffs": [{"player": "alice", "state": "open", "value": 1}]}}),
    _failure("NormGuard", "guard", "NORM_BOUNDARY_PHYSICAL_ENABLEMENT", "BOUNDARY_EXCEEDED", "NormGuard cannot support physical enablement.", text="physical enablement token"),
    _failure("NormGuard", "guard", "NORM_ACTIVE_CONFLICT", "FAIL", "Active norms that forbid and require the same action of one actor must fail.", inputs={'norms': [{'modality': 'obligatory', 'actor': 'keeper', 'action': 'stay_silent', 'condition': {'fact_id': 'oath_sworn', 'value': True}}, {'modality': 'forbidden', 'actor': 'keeper', 'action': 'stay_silent', 'condition': {'fact_id': 'flood_coming', 'value': True}}], 'facts': [{'fact_id': 'oath_sworn', 'value': True}, {'fact_id': 'flood_coming', 'value': True}]}),
    _failure("NormGuard", "guard", "NORM_MODALITY_UNKNOWN", "FAIL", "A modality outside the current deontic enumeration must fail.", inputs={"norms": [{"modality": "maybe", "action": "start", "condition": "authorized"}], "facts": [{"fact_id": "authorized", "value": True}]}),
    _failure("NormGuard", "guard", "NORM_MISSING_PERMISSION", "GAP", "A permission claim cannot pass without a permission or obligation.", text="operator may vent", inputs={"norms": []}),
    _failure("NormGuard", "guard", "NORM_MISSING_NORM_MODEL", "GAP", "A neutral norm claim cannot pass without a norm model.", text="review the declared norm state", inputs={"norms": []}),
    _failure("NormGuard", "guard", "NORM_MISSING_CONDITION_FACT", "GAP", "A norm cannot qualify without its referenced condition fact.", inputs={"norms": [{"modality": "permitted", "action": "start", "condition": "authorized"}], "facts": [{"fact_id": "different", "value": True}]}),
    _failure("NormGuard", "guard", "NORM_UNEVALUABLE_FACT", "GAP", "A fact without an explicit boolean truth value cannot qualify a norm.", inputs={"norms": [{"modality": "permitted", "action": "start", "condition": "authorized"}], "facts": [{"fact_id": "authorized"}]}),
    _failure("NormGuard", "guard", "NORM_DUPLICATE_FACT_ID", "FAIL", "One fact id cannot carry multiple truth records.", inputs={"norms": [{"modality": "permitted", "action": "start", "condition": "authorized"}], "facts": [{"fact_id": "authorized", "value": True}, {"fact_id": "authorized", "value": False}]}),
    _failure("EventGuard", "semantic", "SEM_EVENT_MISSING_EVENTS", "GAP", "Semantic event execution cannot pass without executable events."),
    _failure("EventGuard", "semantic", "SEM_EVENT_CONTRADICTION", "FAIL", "Semantic event execution must reject contradictory fluents.", inputs={"events": [{"event_id": "e1", "at": "t0", "initiates": "ready"}], "event_model": {"contradictory_fluents": ["hot", "cold"]}}),
    _failure("EventGuard", "semantic", "SEM_EVENT_FLUENT_TRANSITION_CONTRADICTION", "FAIL", "Semantic event execution must reject one event terminating and initiating the same fluent.", inputs={"events": [{"event_id": "e1", "at": "t0", "terminates": ["ready"], "initiates": ["ready"]}]}),
    _failure("EventGuard", "semantic", "SEM_EVENT_MISSING_AXIOM", "GAP", "Semantic event execution cannot pass a record missing time or fluent axioms.", inputs={"events": [{"event_id": "e1"}]}),
    _failure("EventGuard", "semantic", "SEM_EVENT_DANGLING_TRANSITION_STATE", "FAIL", "Semantic transition execution must reject a source or target outside the declared state denominator.", inputs={"event_model": {"states": [{"state_id": "waiting", "initial": True, "terminal": False}], "transitions": [{"transition_id": "go", "source_state": "waiting", "target_state": "missing", "guard": True, "effect": "done"}]}}),
    _failure("EventGuard", "semantic", "SEM_EVENT_MISSING_STATE_DENOMINATOR", "GAP", "Semantic transition execution needs a declared state denominator.", inputs={"event_model": {"transitions": [{"transition_id": "go", "source_state": "waiting", "target_state": "done", "guard": True, "effect": "done"}]}}),
    _failure("EventGuard", "semantic", "SEM_EVENT_DUPLICATE_STATE_TRANSITION_ID", "FAIL", "Semantic transition execution requires unique state and transition ids.", inputs={"event_model": {"states": [{"state_id": "waiting", "initial": True, "terminal": False}, {"state_id": "waiting", "initial": False, "terminal": True}]}}),
    _failure("EventGuard", "semantic", "SEM_EVENT_MISSING_INITIAL_STATE", "GAP", "Semantic transition execution needs an initial state.", inputs={"event_model": {"states": [{"state_id": "waiting", "initial": False, "terminal": False}], "transitions": [{"transition_id": "stay", "source_state": "waiting", "target_state": "waiting", "guard": True, "effect": "wait"}]}}),
    _failure("EventGuard", "semantic", "SEM_EVENT_UNEVALUABLE_TRANSITION_GUARD", "GAP", "Semantic transition execution cannot guess an undeclared guard truth value.", inputs={"event_model": {"states": [{"state_id": "waiting", "initial": True, "terminal": False}], "transitions": [{"transition_id": "stay", "source_state": "waiting", "target_state": "waiting", "guard": "ready", "effect": "wait"}]}}),
    _failure("AgentGuard", "semantic", "SEM_AGENT_MISSING_MODEL", "GAP", "Semantic BDI execution cannot pass without agent records."),
    _failure("AgentGuard", "semantic", "SEM_AGENT_INCOMPLETE_BDI", "GAP", "Semantic BDI execution cannot pass an incomplete BDI record.", inputs={"beliefs": {"agent": {"agent_id": "agent", "beliefs": ["b"], "intentions": ["i"]}}}),
    _failure("AgentGuard", "semantic", "SEM_AGENT_CONFLICTING_INTENTIONS", "FAIL", "Semantic BDI execution must reject conflicting intentions.", inputs={"beliefs": {"agent": {"agent_id": "agent", "beliefs": ["b"], "desires": ["d"], "intentions": ["i"]}}, "agent_model": {"conflicting_intentions": ["start", "stop"]}}),
    _failure("AgentGuard", "semantic", "SEM_AGENT_IDENTITY_MISMATCH", "FAIL", "Semantic BDI execution must reject a map key that differs from agent_id.", inputs={"beliefs": {"alice": {"agent_id": "bob", "beliefs": ["b"], "desires": ["d"], "intentions": ["i"]}}}),
    _failure("SpaceGuard", "semantic", "SEM_SPACE_MISSING_RCC8", "GAP", "Semantic spatial execution cannot pass without RCC8 relations."),
    _failure("SpaceGuard", "semantic", "SEM_SPACE_UNEVALUABLE_RCC8", "GAP", "Semantic spatial execution cannot pass a malformed RCC8 relation.", inputs={"spatial_relations": [{"at": "t0", "x": "a", "y": "b", "relation": "NEAR"}]}),
    _failure("SpaceGuard", "semantic", "SEM_SPACE_RCC8_CONFLICT", "FAIL", "Semantic spatial execution must reject conflicting RCC8 relations.", inputs={"spatial_relations": [{"at": "t0", "x": "a", "y": "b", "relation": "DC"}, {"at": "t0", "x": "a", "y": "b", "relation": "EQ"}]}),
    _failure("SpaceGuard", "semantic", "SEM_SPACE_RCC8_REFLEXIVITY_CONFLICT", "FAIL", "Semantic spatial execution must reject a non-EQ self relation.", inputs={"spatial_relations": [{"at": "t0", "x": "a", "y": "a", "relation": "DC"}]}),
    _failure("SpaceGuard", "semantic", "SEM_SPACE_RCC8_CONVERSE_CONFLICT", "FAIL", "Semantic spatial execution must reject inconsistent declared converses.", inputs={"spatial_relations": [{"at": "t0", "x": "a", "y": "b", "relation": "EC"}, {"at": "t0", "x": "b", "y": "a", "relation": "DC"}]}),
    _failure("ResourceGuard", "semantic", "SEM_RESOURCE_MISSING_MODEL", "GAP", "Semantic resource execution cannot pass without places and transitions."),
    _failure("ResourceGuard", "semantic", "SEM_RESOURCE_DOUBLE_CONSUMPTION", "FAIL", "Semantic inventory validation cannot short-circuit cumulative transition conservation.", inputs={"resources": {"inventory": [{"resource_id": "h2", "unit": "unit", "quantity": 1}], "places": {"tank": [{"color": "h2", "qty": 1}]}, "transitions": [{"id": "use-1", "consumes": [{"place": "tank", "color": "h2", "qty": 1}]}, {"id": "use-2", "consumes": [{"place": "tank", "color": "h2", "qty": 1}]}]}}),
    _failure("CausalGuard", "semantic", "SEM_CAUSAL_MISSING_EQUATIONS", "GAP", "Semantic causal execution cannot pass without variables and equations.", inputs={"causal_model": {"variables": [], "equations": {}, "graph": []}}),
    _failure("CausalGuard", "semantic", "SEM_CAUSAL_UNEVALUABLE_EQUATION", "GAP", "Semantic causal execution cannot pass a missing or unsafe equation.", inputs={"causal_model": {"variables": ["x", "y"], "equations": {"x": 1}, "graph": []}}),
    _failure("CausalGuard", "semantic", "SEM_CAUSAL_ROLLOUT_ERROR", "GAP", "Semantic causal execution cannot pass a declared scenario that fails safe scalar rollout.", inputs={"causal_model": {"variables": ["x"], "equations": {"x": "1 / z"}, "exogenous": ["z"], "graph": [], "scenarios": {"s1": {"z": 0}}}}, coverage_context={"scenario_ids": ["s1"]}),
    _failure("CausalGuard", "semantic", "SEM_CAUSAL_MISSING_BEHAVIOR_OBLIGATION", "GAP", "Semantic causal execution cannot pass an equation model with no executable behavior obligation.", inputs={"causal_model": {"variables": ["x"], "equations": {"x": 1}, "graph": []}}),
    _failure("ConflictGuard", "semantic", "SEM_CONFLICT_INCOMPLETE_GAME", "GAP", "Semantic conflict execution cannot pass an incomplete finite game.", inputs={"game_model": {"players": ["a"], "actions": {"a": ["hold"]}}}),
    _failure("ConflictGuard", "semantic", "SEM_CONFLICT_INVALID_TRANSITION", "FAIL", "Semantic conflict execution must reject invalid transition probabilities.", inputs={"game_model": {"players": ["a", "b"], "actions": {"a": ["hold"], "b": ["hold"]}, "states": ["s"], "transitions": [{"from": "s", "to": "s", "probabilities": [0.7, 0.7]}], "payoffs": [{"state": "s", "reward": {"a": 1, "b": 1}}]}}),
    _failure("ConflictGuard", "semantic", "SEM_CONFLICT_DUPLICATE_PARTICIPANT", "FAIL", "Semantic conflict execution must reject duplicate participant identities.", inputs={"game_model": {"players": ["a", "a"], "actions": ["hold"], "states": ["s"], "transitions": [{"state": "s", "probabilities": [1.0]}], "payoffs": [{"state": "s", "reward": {"a": 1}}]}}),
    _failure("ConflictGuard", "semantic", "SEM_CONFLICT_REFERENCE_CLOSURE", "FAIL", "Semantic conflict execution must reject foreign transition-state and payoff-player references.", inputs={"game_model": {"players": ["alice", "bob"], "actions": ["share"], "states": ["open"], "transitions": [{"from": "ghost", "to": "void", "probabilities": [1.0]}], "payoffs": [{"player": "mallory", "state": "void", "value": 1}]}}),
    _failure("NormGuard", "semantic", "SEM_NORM_MISSING_MODEL", "GAP", "Semantic norm execution cannot pass without norms."),
    _failure("NormGuard", "semantic", "SEM_NORM_MODALITY_UNKNOWN", "FAIL", "Semantic norm execution must reject an unknown modality.", inputs={"norms": [{"modality": "maybe", "action": "start", "condition": "authorized"}], "facts": [{"fact_id": "authorized", "value": True}]}),
    _failure("NormGuard", "semantic", "SEM_NORM_MISSING_CONDITION_FACT", "GAP", "Semantic norm execution cannot pass without condition facts.", inputs={"norms": [{"modality": "permitted", "action": "start", "condition": "authorized"}], "facts": []}),
    _failure("NormGuard", "semantic", "SEM_NORM_ACTIVE_CONFLICT", "FAIL", "Semantic norm execution must reject active norms that forbid and require the same action of one actor.", inputs={'norms': [{'modality': 'obligatory', 'actor': 'keeper', 'action': 'stay_silent', 'condition': {'fact_id': 'oath_sworn', 'value': True}}, {'modality': 'forbidden', 'actor': 'keeper', 'action': 'stay_silent', 'condition': {'fact_id': 'flood_coming', 'value': True}}], 'facts': [{'fact_id': 'oath_sworn', 'value': True}, {'fact_id': 'flood_coming', 'value': True}]}),
    _failure("NormGuard", "semantic", "SEM_NORM_UNEVALUABLE_FACT", "GAP", "Semantic norm execution cannot use a fact without an explicit boolean truth value.", inputs={"norms": [{"modality": "permitted", "action": "start", "condition": "authorized"}], "facts": [{"fact_id": "authorized"}]}),
    _failure("NormGuard", "semantic", "SEM_NORM_DUPLICATE_FACT_ID", "FAIL", "Semantic norm execution must reject duplicate fact identities.", inputs={"norms": [{"modality": "permitted", "action": "start", "condition": "authorized"}], "facts": [{"fact_id": "authorized", "value": True}, {"fact_id": "authorized", "value": False}]}),
)


MESH_RUNTIME_FAILURES = {
    "SEM_EXECUTOR_UNREGISTERED": "Owned by mesh executor registration, not by an individual Guard model.",
    "SEM_PROVIDER_UNAVAILABLE": "Owned by provider availability and mesh rollout lifecycle, not by an individual Guard model.",
}


def _contract(case_id: str, guard: str, text: str, inputs: Mapping[str, Any]) -> GuardContract:
    task_contract_id = f"guard-model-contract:{case_id}"
    run_id = f"guard-model-contract:{case_id}"
    model_instance_id = f"model:{guard.lower()}"
    return GuardContract.from_dict(
        {
            "contract_id": task_contract_id,
            "run_id": run_id,
            "claim": {
                "claim_id": case_id,
                "text": text,
                "target_guards": [guard],
                "requested_semantics": [guard.removesuffix("Guard").lower()],
            },
            "world_model": {"model_id": model_instance_id, "model_version": "v1"},
            "inputs": dict(inputs),
        }
    )


def _literal_codes(path: Path, call_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    codes: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function = node.func
        name = function.id if isinstance(function, ast.Name) else ""
        if name != call_name:
            continue
        value = node.args[0]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            codes.add(value.value)
    return codes


def discover_guard_owned_failure_codes() -> dict[tuple[str, str], set[str]]:
    semantic_path = Path(importlib.import_module("worldguard.semantic").__file__).resolve()
    discovered: dict[tuple[str, str], set[str]] = {}
    semantic_codes = _literal_codes(semantic_path, "_finding")
    for purpose in GUARD_MODEL_PURPOSES:
        runner = GUARD_RUNNERS[purpose.guard]
        guard_path = Path(importlib.import_module(runner.__module__).__file__).resolve()
        discovered[(purpose.guard, "guard")] = _literal_codes(guard_path, "error")
        prefix = f"SEM_{purpose.guard.removesuffix('Guard').upper()}_"
        discovered[(purpose.guard, "semantic")] = {
            code for code in semantic_codes if code.startswith(prefix)
        }
    return discovered


def _failure_key(case: ProtectedFailureClass) -> tuple[str, str, str]:
    return case.guard, case.layer, case.code


def _canonical_fingerprint(payload: Mapping[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _native_oracle_id(case: ProtectedFailureClass) -> str:
    return f"oracle:worldguard:{case.guard}:{case.layer}:{case.code}"










def guard_family_purpose_contract_payload() -> dict[str, Any]:
    return {
        "schema_version": "worldguard.guard_family_purpose_contract.v1",
        "purposes": [item.to_dict() for item in GUARD_MODEL_PURPOSES],
        "good_cases": [item.to_dict() for item in NATIVE_GOOD_CASES],
        "failure_classes": [item.to_dict() for item in PROTECTED_FAILURE_CLASSES],
        "mesh_runtime_failures": MESH_RUNTIME_FAILURES,
    }


def guard_family_purpose_contract_fingerprint() -> str:
    return _canonical_fingerprint(guard_family_purpose_contract_payload())










def _fingerprint() -> str:
    return guard_family_purpose_contract_fingerprint()


def run_guard_model_contract() -> dict[str, Any]:
    """Run every catalog case once; never calibrate the checker inside a case."""
    failures: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    guards = {purpose.guard for purpose in GUARD_MODEL_PURPOSES}
    if guards != set(GUARD_RUNNERS) or guards != set(EXECUTOR_REGISTRY):
        failures.append({"code": "GUARD_PURPOSE_INVENTORY_MISMATCH"})
    good_counts = Counter(case.guard for case in NATIVE_GOOD_CASES)
    if set(good_counts) != guards or any(count != 1 for count in good_counts.values()):
        failures.append({"code": "NATIVE_GOOD_CARDINALITY_MISMATCH"})
    discovered = discover_guard_owned_failure_codes()
    expected = {(guard, layer, code) for (guard, layer), codes in discovered.items() for code in codes}
    declared = [_failure_key(case) for case in PROTECTED_FAILURE_CLASSES]
    if len(declared) != len(set(declared)) or set(declared) != expected:
        failures.append({"code": "PROTECTED_FAILURE_UNIVERSE_MISMATCH"})
    family_fingerprint = guard_family_purpose_contract_fingerprint()
    for case in NATIVE_GOOD_CASES:
        contract = _contract(case.case_id, case.guard, case.text, case.inputs)
        if case.coverage_context:
            contract.inputs["_semantic_coverage"] = dict(case.coverage_context)
        structural = GUARD_RUNNERS[case.guard](contract)
        semantic_status, _, _, _ = EXECUTOR_REGISTRY[case.guard].execute(contract)
        observed = {"case_id": case.case_id, "guard": case.guard,
                    "guard_status": structural.status.value, "semantic_status": semantic_status.value,
                    "family_contract_fingerprint": family_fingerprint}
        observations.append(observed)
        if structural.status is not GuardStatus.PASS or semantic_status is not SemanticStatus.PASS:
            failures.append({"code": "NATIVE_GOOD_REJECTED", **observed})
    for case in PROTECTED_FAILURE_CLASSES:
        contract = _contract(case.failure_id, case.guard, case.text, case.inputs)
        if case.coverage_context:
            contract.inputs["_semantic_coverage"] = dict(case.coverage_context)
        if case.layer == "guard":
            result = GUARD_RUNNERS[case.guard](contract)
            status, codes = result.status.value, [str(row.get("code", "")) for row in result.errors]
        else:
            result, findings, _, _ = EXECUTOR_REGISTRY[case.guard].execute(contract)
            status, codes = result.value, [str(row.get("code", "")) for row in findings]
        observed = {"failure_id": case.failure_id, "guard": case.guard, "layer": case.layer,
                    "expected_status": case.expected_status, "observed_status": status,
                    "expected_code": case.code, "observed_codes": codes,
                    "family_contract_fingerprint": family_fingerprint}
        observations.append(observed)
        if status != case.expected_status or codes != [case.code]:
            failures.append({"code": "NATIVE_BAD_ORACLE_MISMATCH", **observed})
    return {"schema_version": "worldguard.guard_model_contract_report.v1",
            "status": "pass" if not failures else "fail", "ok": not failures,
            "purpose_count": len(guards), "native_good_count": len(NATIVE_GOOD_CASES),
            "protected_failure_count": len(expected), "known_bad_count": len(PROTECTED_FAILURE_CLASSES),
            "executed_case_count": len(observations), "universe_fingerprint": family_fingerprint,
            "purposes": [item.to_dict() for item in GUARD_MODEL_PURPOSES],
            "protected_failures": [item.to_dict() for item in PROTECTED_FAILURE_CLASSES],
            "mesh_runtime_failures": MESH_RUNTIME_FAILURES, "observations": observations, "failures": failures,
            "claim_boundary": "Finite author regression over native Guard-owned reactions only; no task understanding, factual truth, installation or release claim."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the finite WorldGuard Guard-model contract.")
    parser.add_argument("--json", action="store_true", help="Emit the complete JSON report.")
    args = parser.parse_args(argv)
    report = run_guard_model_contract()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"status={report['status']} purposes={report['purpose_count']} "
            f"goods={report['native_good_count']} failures={report['protected_failure_count']} "
            f"known_bads={report['known_bad_count']}"
        )
        for failure in report["failures"]:
            print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
