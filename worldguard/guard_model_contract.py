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

from .contracts import GuardContract, GuardPurposeContractBinding
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


class GuardCandidatePurposeError(ValueError):
    """Stable fail-closed rejection raised before a Guard candidate is proved."""

    def __init__(self, code: str, message: str, *, details: Mapping[str, Any] | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.details = dict(details or {})


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
    _failure("ConflictGuard", "guard", "CONFLICT_POLICY_CONTRADICTION", "FAIL", "A declared payoff policy contradiction must reject recipe-sharing support.", text="full membrane recipe", inputs={"game_model": {"payoffs": [{"policy": "C_block_recipe_release"}], "transitions": []}}),
    _failure("ConflictGuard", "guard", "CONFLICT_MISSING_PAYOFF", "GAP", "A finite-game claim cannot pass without payoff evidence.", inputs={"game_model": {"transitions": []}}),
    _failure("ConflictGuard", "guard", "CONFLICT_REFERENCE_CLOSURE", "FAIL", "Finite-game transitions and payoffs cannot reference undeclared states or players.", inputs={"game_model": {"players": ["alice", "bob"], "actions": ["share"], "states": ["open"], "transitions": [{"from": "ghost", "to": "void", "probabilities": [1.0]}], "payoffs": [{"player": "mallory", "state": "void", "value": 1}]}}),
    _failure("ConflictGuard", "guard", "CONFLICT_INCOMPLETE_GAME", "GAP", "A finite game cannot qualify without players, actions, states, transitions, and payoffs.", inputs={"game_model": {"payoffs": [{"player": "alice", "state": "open", "value": 1}]}}),
    _failure("NormGuard", "guard", "NORM_BOUNDARY_PHYSICAL_ENABLEMENT", "BOUNDARY_EXCEEDED", "NormGuard cannot support physical enablement.", text="physical enablement token"),
    _failure("NormGuard", "guard", "NORM_FORBIDDEN_ACTION_CONTRADICTION", "FAIL", "A claimed permission that contradicts a prohibition must fail.", text="Company A may share the full membrane recipe", inputs={"norms": [{"modality": "forbidden", "action": "share_membrane_recipe"}]}),
    _failure("NormGuard", "guard", "NORM_MODALITY_UNKNOWN", "FAIL", "A modality outside the current deontic enumeration must fail.", inputs={"norms": [{"modality": "maybe", "action": "start", "condition": "authorized"}], "facts": [{"fact_id": "authorized", "value": True}]}),
    _failure("NormGuard", "guard", "NORM_MISSING_PERMISSION", "GAP", "A permission claim cannot pass without a permission or obligation.", text="operator may vent", inputs={"norms": []}),
    _failure("NormGuard", "guard", "NORM_MISSING_NORM_MODEL", "GAP", "A neutral norm claim cannot pass without a norm model.", text="review the declared norm state", inputs={"norms": []}),
    _failure("NormGuard", "guard", "NORM_CONDITION_NOT_SATISFIED", "GAP", "A norm cannot support the claim when its declared condition fact is false.", inputs={"norms": [{"modality": "permitted", "action": "start", "condition": "authorized"}], "facts": [{"fact_id": "authorized", "value": False}]}),
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
    _failure("NormGuard", "semantic", "SEM_NORM_CONDITION_NOT_SATISFIED", "GAP", "Semantic norm execution cannot pass when the referenced fact value does not satisfy the condition.", inputs={"norms": [{"modality": "permitted", "action": "start", "condition": "authorized"}], "facts": [{"fact_id": "authorized", "value": False}]}),
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
            "guard_purpose_declarations": [
                build_calibration_task_purpose_declaration(
                    guard,
                    task_contract_id=task_contract_id,
                    run_id=run_id,
                    model_instance_id=model_instance_id,
                )
            ],
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


def build_calibration_task_purpose_declaration(
    guard: str,
    *,
    task_contract_id: str,
    run_id: str,
    model_instance_id: str,
    selected_failure_ids: tuple[str, ...] | list[str] | None = None,
    purpose: str | None = None,
    boundary: str | None = None,
) -> dict[str, Any]:
    """Build an explicit family-fixture declaration for tests and examples only.

    Production callers must supply their own declaration in the target contract;
    `GuardContract.for_guard` never calls this helper as a fallback.
    """

    family_purpose = next(
        (item for item in GUARD_MODEL_PURPOSES if item.guard == guard),
        None,
    )
    if family_purpose is None:
        raise GuardCandidatePurposeError(
            "GUARD_TASK_PURPOSE_GUARD_UNKNOWN",
            "The requested Guard has no WorldGuard-owned oracle catalog.",
            details={"guard": guard},
        )
    catalog = [item for item in PROTECTED_FAILURE_CLASSES if item.guard == guard]
    selected = list(selected_failure_ids or [item.failure_id for item in catalog])
    selected_rows = [item for item in catalog if item.failure_id in selected]
    good = next(item for item in NATIVE_GOOD_CASES if item.guard == guard)
    return {
        "schema_version": "worldguard.task_guard_purpose.v1",
        "declaration_id": f"declaration:{task_contract_id}:{guard}",
        "task_contract_id": task_contract_id,
        "run_id": run_id,
        "model_instance_id": model_instance_id,
        "guard": guard,
        "purpose": purpose or family_purpose.purpose,
        "boundary": boundary or family_purpose.boundary,
        "selected_failure_ids": selected,
        "known_good": {
            "case_id": f"{task_contract_id}:{good.case_id}",
            "text": good.text,
            "inputs": dict(good.inputs),
            "coverage_context": dict(good.coverage_context),
            "expected_guard_status": "PASS",
            "expected_semantic_status": "PASS",
            "native_oracle_id": f"oracle:worldguard:{guard}:known-good",
        },
        "known_bad_cases": [
            {
                "case_id": f"{task_contract_id}:bad:{item.failure_id}",
                "failure_id": item.failure_id,
                "blocked_claim": item.blocked_claim,
                "text": item.text or item.blocked_claim,
                "inputs": dict(item.inputs),
                "coverage_context": dict(item.coverage_context),
                "expected_status": item.expected_status,
                "expected_code": item.code,
                "native_oracle_id": _native_oracle_id(item),
            }
            for item in selected_rows
        ],
        "declaration_sequence": 1,
    }


def _normalize_task_purpose_declaration(
    declaration: Mapping[str, Any],
    *,
    guard: str,
    task_contract_id: str,
    run_id: str,
    model_instance_id: str,
) -> dict[str, Any]:
    catalog = {
        item.failure_id: item
        for item in PROTECTED_FAILURE_CLASSES
        if item.guard == guard
    }
    required_strings = {
        "declaration_id": declaration.get("declaration_id"),
        "purpose": declaration.get("purpose"),
        "boundary": declaration.get("boundary"),
    }
    if (
        declaration.get("schema_version") != "worldguard.task_guard_purpose.v1"
        or declaration.get("guard") != guard
        or declaration.get("task_contract_id") != task_contract_id
        or declaration.get("run_id") != run_id
        or declaration.get("model_instance_id") != model_instance_id
        or declaration.get("declaration_sequence") != 1
        or any(not isinstance(value, str) or not value.strip() for value in required_strings.values())
    ):
        raise GuardCandidatePurposeError(
            "GUARD_TASK_PURPOSE_DECLARATION_INVALID",
            "The task purpose identity, order, purpose, or boundary is incomplete or mismatched.",
            details={
                "guard": guard,
                "task_contract_id": task_contract_id,
                "model_instance_id": model_instance_id,
            },
        )
    selected = declaration.get("selected_failure_ids")
    if (
        not isinstance(selected, list)
        or not selected
        or any(not isinstance(item, str) or not item for item in selected)
        or len(selected) != len(set(selected))
    ):
        raise GuardCandidatePurposeError(
            "GUARD_TASK_PURPOSE_FAILURE_UNIVERSE_EMPTY_OR_DUPLICATE",
            "The task must declare one or more unique failures to prevent.",
            details={"guard": guard},
        )
    unknown = [item for item in selected if item not in catalog]
    if unknown:
        raise GuardCandidatePurposeError(
            "GUARD_TASK_PURPOSE_NATIVE_ORACLE_UNKNOWN",
            "A selected failure has no WorldGuard-owned native oracle.",
            details={"guard": guard, "unknown_failure_ids": unknown},
        )
    good = declaration.get("known_good")
    if not isinstance(good, Mapping):
        raise GuardCandidatePurposeError(
            "GUARD_TASK_PURPOSE_GOOD_PROOF_MISSING",
            "The task declaration requires one task-local native known-good case.",
            details={"guard": guard},
        )
    good_required = ("case_id", "text", "native_oracle_id")
    if (
        any(not isinstance(good.get(key), str) or not str(good.get(key)).strip() for key in good_required)
        or not isinstance(good.get("inputs"), Mapping)
        or not isinstance(good.get("coverage_context", {}), Mapping)
        or good.get("expected_guard_status") != "PASS"
        or good.get("expected_semantic_status") != "PASS"
        or good.get("native_oracle_id") != f"oracle:worldguard:{guard}:known-good"
    ):
        raise GuardCandidatePurposeError(
            "GUARD_TASK_PURPOSE_GOOD_PROOF_INVALID",
            "The task-local known-good case is incomplete or uses the wrong native oracle.",
            details={"guard": guard},
        )
    bad_rows = declaration.get("known_bad_cases")
    if not isinstance(bad_rows, list):
        bad_rows = []
    by_failure: dict[str, list[Mapping[str, Any]]] = {item: [] for item in selected}
    extras: list[str] = []
    for row in bad_rows:
        if not isinstance(row, Mapping):
            extras.append("<non-object>")
            continue
        failure_id = str(row.get("failure_id", ""))
        if failure_id not in by_failure:
            extras.append(failure_id)
            continue
        by_failure[failure_id].append(row)
    if extras or any(len(rows) != 1 for rows in by_failure.values()):
        raise GuardCandidatePurposeError(
            "GUARD_TASK_PURPOSE_BAD_PROOF_CARDINALITY_INVALID",
            "Every selected failure requires exactly one task-local known-bad case and no extras.",
            details={
                "guard": guard,
                "counts": {key: len(value) for key, value in by_failure.items()},
                "extra_failure_ids": extras,
            },
        )
    normalized_bad: list[dict[str, Any]] = []
    for failure_id in selected:
        row = by_failure[failure_id][0]
        target = catalog[failure_id]
        if (
            not isinstance(row.get("case_id"), str)
            or not str(row.get("case_id")).strip()
            or not isinstance(row.get("blocked_claim"), str)
            or not str(row.get("blocked_claim")).strip()
            or not isinstance(row.get("text"), str)
            or not str(row.get("text")).strip()
            or not isinstance(row.get("inputs"), Mapping)
            or not isinstance(row.get("coverage_context", {}), Mapping)
            or row.get("expected_status") != target.expected_status
            or row.get("expected_code") != target.code
            or row.get("native_oracle_id") != _native_oracle_id(target)
        ):
            raise GuardCandidatePurposeError(
                "GUARD_TASK_PURPOSE_BAD_PROOF_INVALID",
                "A task-local known-bad case is incomplete or mismatched with its WorldGuard-native oracle.",
                details={"guard": guard, "failure_id": failure_id},
            )
        normalized_bad.append(
            {
                "case_id": str(row["case_id"]),
                "failure_id": failure_id,
                "blocked_claim": str(row["blocked_claim"]),
                "text": str(row["text"]),
                "inputs": dict(row["inputs"]),
                "coverage_context": dict(row.get("coverage_context", {})),
                "expected_status": target.expected_status,
                "expected_code": target.code,
                "native_oracle_id": _native_oracle_id(target),
            }
        )
    return {
        "schema_version": "worldguard.task_guard_purpose.v1",
        "declaration_id": str(declaration["declaration_id"]),
        "task_contract_id": task_contract_id,
        "run_id": run_id,
        "model_instance_id": model_instance_id,
        "guard": guard,
        "purpose": str(declaration["purpose"]),
        "boundary": str(declaration["boundary"]),
        "selected_failure_ids": list(selected),
        "known_good": {
            "case_id": str(good["case_id"]),
            "text": str(good["text"]),
            "inputs": dict(good["inputs"]),
            "coverage_context": dict(good.get("coverage_context", {})),
            "expected_guard_status": "PASS",
            "expected_semantic_status": "PASS",
            "native_oracle_id": f"oracle:worldguard:{guard}:known-good",
        },
        "known_bad_cases": normalized_bad,
        "declaration_sequence": 1,
    }


def _proof_case_contract(
    declaration: Mapping[str, Any],
    *,
    case_id: str,
    text: str,
    inputs: Mapping[str, Any],
    coverage_context: Mapping[str, Any] | None = None,
) -> GuardContract:
    merged_inputs = dict(inputs)
    if coverage_context:
        merged_inputs["_semantic_coverage"] = dict(coverage_context)
    guard = str(declaration["guard"])
    return GuardContract.from_dict(
        {
            "contract_id": f"proof:{declaration['declaration_id']}:{case_id}:{guard}",
            "run_id": str(declaration["run_id"]),
            "claim": {
                "claim_id": case_id,
                "text": text,
                "target_guards": [guard],
                "requested_semantics": [guard.removesuffix("Guard").lower()],
            },
            "world_model": {
                "model_id": str(declaration["model_instance_id"]),
                "model_version": "task-purpose-proof",
            },
            "inputs": merged_inputs,
        }
    )


def prove_task_purpose_declaration(
    declaration: Mapping[str, Any],
    *,
    guard: str,
    task_contract_id: str,
    run_id: str,
    model_instance_id: str,
) -> dict[str, Any]:
    normalized = _normalize_task_purpose_declaration(
        declaration,
        guard=guard,
        task_contract_id=task_contract_id,
        run_id=run_id,
        model_instance_id=model_instance_id,
    )
    observations: list[dict[str, Any]] = []
    good = normalized["known_good"]
    good_contract = _proof_case_contract(
        normalized,
        case_id=good["case_id"],
        text=good["text"],
        inputs=good["inputs"],
        coverage_context=good["coverage_context"],
    )
    good_guard = GUARD_RUNNERS[guard](good_contract)
    good_semantic_status, good_findings, _, _ = EXECUTOR_REGISTRY[guard].execute(
        good_contract
    )
    good_observation = {
        "case_id": good["case_id"],
        "case_kind": "known_good",
        "guard_status": good_guard.status.value,
        "semantic_status": good_semantic_status.value,
        "guard_codes": [str(item.get("code", "")) for item in good_guard.errors],
        "semantic_codes": [str(item.get("code", "")) for item in good_findings],
        "passed": (
            good_guard.status is GuardStatus.PASS
            and good_semantic_status is SemanticStatus.PASS
        ),
    }
    observations.append(good_observation)
    catalog = {item.failure_id: item for item in PROTECTED_FAILURE_CLASSES}
    for bad in normalized["known_bad_cases"]:
        target = catalog[bad["failure_id"]]
        bad_contract = _proof_case_contract(
            normalized,
            case_id=bad["case_id"],
            text=bad["text"],
            inputs=bad["inputs"],
            coverage_context=bad["coverage_context"],
        )
        if target.layer == "guard":
            result = GUARD_RUNNERS[guard](bad_contract)
            observed_status = result.status.value
            observed_codes = [str(item.get("code", "")) for item in result.errors]
        else:
            status, findings, _, _ = EXECUTOR_REGISTRY[guard].execute(bad_contract)
            observed_status = status.value
            observed_codes = [str(item.get("code", "")) for item in findings]
        observations.append(
            {
                "case_id": bad["case_id"],
                "case_kind": "known_bad",
                "failure_id": bad["failure_id"],
                "native_oracle_id": bad["native_oracle_id"],
                "expected_status": bad["expected_status"],
                "observed_status": observed_status,
                "expected_code": bad["expected_code"],
                "observed_codes": observed_codes,
                "passed": (
                    observed_status == bad["expected_status"]
                    and observed_codes == [bad["expected_code"]]
                ),
            }
        )
    passed = bool(observations) and all(item["passed"] for item in observations)
    receipt = {
        "schema_version": "worldguard.task_guard_purpose_proof.v1",
        "status": "pass" if passed else "fail",
        "declaration_id": normalized["declaration_id"],
        "declaration_fingerprint": _canonical_fingerprint(normalized),
        "guard": guard,
        "model_instance_id": model_instance_id,
        "selected_failure_ids": list(normalized["selected_failure_ids"]),
        "known_good_count": 1,
        "known_bad_count": len(normalized["known_bad_cases"]),
        "observations": observations,
    }
    if not passed:
        raise GuardCandidatePurposeError(
            "GUARD_TASK_PURPOSE_NATIVE_PROOF_FAILED",
            "The task-local known-good/known-bad proof did not match WorldGuard-native reactions.",
            details={"guard": guard, "receipt": receipt},
        )
    return receipt


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


def _guard_purpose_contract_payload(guard: str) -> dict[str, Any]:
    purpose = next((item for item in GUARD_MODEL_PURPOSES if item.guard == guard), None)
    if purpose is None:
        raise GuardCandidatePurposeError(
            "GUARD_CANDIDATE_PURPOSE_MISSING",
            "The requested Guard has no target-owned purpose contract.",
            details={"guard": guard},
        )
    return {
        "schema_version": "worldguard.guard_purpose_contract.v1",
        "purpose": purpose.to_dict(),
        "good_cases": [item.to_dict() for item in NATIVE_GOOD_CASES if item.guard == guard],
        "failure_classes": [
            item.to_dict() for item in PROTECTED_FAILURE_CLASSES if item.guard == guard
        ],
    }


def _current_guard_purpose_contract_binding(
    guard: str,
    *,
    candidate_contract_id: str,
    task_contract_id: str,
    run_id: str,
    model_instance_id: str,
    declaration: Mapping[str, Any],
) -> GuardPurposeContractBinding:
    payload = _guard_purpose_contract_payload(guard)
    normalized = _normalize_task_purpose_declaration(
        declaration,
        guard=guard,
        task_contract_id=task_contract_id,
        run_id=run_id,
        model_instance_id=model_instance_id,
    )
    proof_receipt = prove_task_purpose_declaration(
        normalized,
        guard=guard,
        task_contract_id=task_contract_id,
        run_id=run_id,
        model_instance_id=model_instance_id,
    )
    return GuardPurposeContractBinding(
        schema_version="worldguard.guard_candidate_purpose_binding.v2",
        guard=guard,
        purpose_id=normalized["declaration_id"],
        purpose=normalized["purpose"],
        blocked_claims=tuple(
            item["blocked_claim"] for item in normalized["known_bad_cases"]
        ),
        boundary=normalized["boundary"],
        family_contract_fingerprint=guard_family_purpose_contract_fingerprint(),
        guard_contract_fingerprint=_canonical_fingerprint(payload),
        family_guard_ids=tuple(item.guard for item in GUARD_MODEL_PURPOSES),
        protected_failure_ids=tuple(normalized["selected_failure_ids"]),
        declaration_id=normalized["declaration_id"],
        task_contract_id=task_contract_id,
        run_id=run_id,
        model_instance_id=model_instance_id,
        declaration_fingerprint=_canonical_fingerprint(normalized),
        proof_receipt_fingerprint=_canonical_fingerprint(proof_receipt),
        declaration_payload=normalized,
        proof_receipt=proof_receipt,
        frozen_for_candidate_id=candidate_contract_id,
        purpose_frozen_sequence=1,
        candidate_constructed_sequence=2,
    )


def freeze_guard_purpose_contract(
    guard: str,
    *,
    candidate_contract_id: str,
    task_contract_id: str,
    run_id: str,
    model_instance_id: str,
    declaration: Mapping[str, Any],
) -> GuardPurposeContractBinding:
    """Prove and freeze one explicit task-model-instance declaration."""

    return _current_guard_purpose_contract_binding(
        guard,
        candidate_contract_id=candidate_contract_id,
        task_contract_id=task_contract_id,
        run_id=run_id,
        model_instance_id=model_instance_id,
        declaration=declaration,
    )


def verify_guard_candidate_purpose_contract(
    contract: GuardContract,
    guard: str,
) -> GuardPurposeContractBinding:
    """Reject missing, stale, out-of-order, or shrunken candidate authority."""

    binding = contract.guard_purpose_contract
    if binding is None:
        raise GuardCandidatePurposeError(
            "GUARD_CANDIDATE_PURPOSE_MISSING",
            "The formal Guard candidate does not carry a frozen purpose contract.",
            details={"guard": guard, "candidate_contract_id": contract.contract_id},
        )
    if (
        binding.purpose_frozen_sequence >= binding.candidate_constructed_sequence
        or binding.purpose_frozen_sequence != 1
        or binding.candidate_constructed_sequence != 2
        or binding.frozen_for_candidate_id != contract.contract_id
    ):
        raise GuardCandidatePurposeError(
            "GUARD_CANDIDATE_PURPOSE_ORDER_INVALID",
            "Purpose authority must be frozen for this exact candidate before construction.",
            details={
                "guard": guard,
                "candidate_contract_id": contract.contract_id,
                "frozen_for_candidate_id": binding.frozen_for_candidate_id,
                "purpose_frozen_sequence": binding.purpose_frozen_sequence,
                "candidate_constructed_sequence": binding.candidate_constructed_sequence,
            },
        )

    expected_candidate_id = f"{binding.task_contract_id}:{guard}"
    if (
        binding.guard != guard
        or binding.task_contract_id == ""
        or binding.run_id != contract.run_id
        or binding.model_instance_id != contract.world_model.model_id
        or expected_candidate_id != contract.contract_id
    ):
        raise GuardCandidatePurposeError(
            "GUARD_TASK_PURPOSE_INSTANCE_MISMATCH",
            "The declaration belongs to another task, run, model instance, Guard, or child candidate.",
            details={
                "guard": guard,
                "candidate_contract_id": contract.contract_id,
                "task_contract_id": binding.task_contract_id,
                "model_instance_id": binding.model_instance_id,
            },
        )
    # Verification re-normalizes the exact target declaration and reruns its
    # target-native proof independently of the public candidate constructor.
    expected = _current_guard_purpose_contract_binding(
        guard,
        candidate_contract_id=contract.contract_id,
        task_contract_id=binding.task_contract_id,
        run_id=binding.run_id,
        model_instance_id=binding.model_instance_id,
        declaration=binding.declaration_payload,
    )
    if binding.to_dict() != expected.to_dict():
        raise GuardCandidatePurposeError(
            "GUARD_CANDIDATE_PURPOSE_STALE",
            "The candidate binding does not match the current task declaration, proof, or family oracle catalog.",
            details={
                "guard": guard,
                "expected_family_contract_fingerprint": expected.family_contract_fingerprint,
                "observed_family_contract_fingerprint": binding.family_contract_fingerprint,
            },
        )
    return binding


def _fingerprint() -> str:
    return guard_family_purpose_contract_fingerprint()


def run_guard_model_contract() -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    observations: list[dict[str, Any]] = []
    guards = tuple(purpose.guard for purpose in GUARD_MODEL_PURPOSES)

    if set(guards) != set(GUARD_RUNNERS) or set(guards) != set(EXECUTOR_REGISTRY):
        failures.append(
            {
                "code": "GUARD_PURPOSE_INVENTORY_MISMATCH",
                "expected": sorted(set(GUARD_RUNNERS) | set(EXECUTOR_REGISTRY)),
                "observed": sorted(set(guards)),
            }
        )
    if any(not item.purpose or not item.blocked_claims or not item.boundary for item in GUARD_MODEL_PURPOSES):
        failures.append({"code": "GUARD_PURPOSE_INCOMPLETE"})

    good_counts = Counter(case.guard for case in NATIVE_GOOD_CASES)
    if set(good_counts) != set(guards) or any(count != 1 for count in good_counts.values()):
        failures.append({"code": "NATIVE_GOOD_CARDINALITY_MISMATCH", "counts": dict(good_counts)})

    for case in NATIVE_GOOD_CASES:
        contract = _contract(case.case_id, case.guard, case.text, case.inputs)
        candidate = contract.for_guard(case.guard)
        candidate_binding = verify_guard_candidate_purpose_contract(candidate, case.guard)
        guard_result = GUARD_RUNNERS[case.guard](candidate)
        semantic_result = execute_semantic(
            node_id=f"node:{case.guard.lower()}",
            guard=case.guard,
            contract=candidate,
            provider_available=True,
            coverage_context=dict(case.coverage_context),
        )
        observed = {
            "case_id": case.case_id,
            "guard": case.guard,
            "guard_status": guard_result.status.value,
            "semantic_status": semantic_result.status.value,
            "family_contract_fingerprint": candidate_binding.family_contract_fingerprint,
        }
        observations.append(observed)
        if guard_result.status is not GuardStatus.PASS or semantic_result.status is not SemanticStatus.PASS:
            failures.append({"code": "NATIVE_GOOD_REJECTED", **observed})

    discovered = discover_guard_owned_failure_codes()
    expected_keys = {
        (guard, layer, code)
        for (guard, layer), codes in discovered.items()
        for code in codes
    }
    declared_keys = [_failure_key(case) for case in PROTECTED_FAILURE_CLASSES]
    declared_counts = Counter(declared_keys)
    duplicates = [list(key) for key, count in declared_counts.items() if count != 1]
    if duplicates:
        failures.append({"code": "KNOWN_BAD_CARDINALITY_MISMATCH", "duplicates": duplicates})
    if set(declared_keys) != expected_keys:
        failures.append(
            {
                "code": "PROTECTED_FAILURE_UNIVERSE_MISMATCH",
                "missing": [list(key) for key in sorted(expected_keys - set(declared_keys))],
                "extra": [list(key) for key in sorted(set(declared_keys) - expected_keys)],
            }
        )

    for case in PROTECTED_FAILURE_CLASSES:
        contract = _contract(case.failure_id, case.guard, case.text, case.inputs)
        candidate = contract.for_guard(case.guard)
        candidate_binding = verify_guard_candidate_purpose_contract(candidate, case.guard)
        if case.layer == "guard":
            result = GUARD_RUNNERS[case.guard](candidate)
            observed_status = result.status.value
            observed_codes = [str(item.get("code", "")) for item in result.errors]
        elif case.layer == "semantic":
            receipt = execute_semantic(
                node_id=f"node:{case.guard.lower()}",
                guard=case.guard,
                contract=candidate,
                provider_available=True,
                coverage_context=dict(case.coverage_context),
            )
            observed_status = receipt.status.value
            observed_codes = [str(item.get("code", "")) for item in receipt.findings]
        else:
            failures.append({"code": "UNKNOWN_FAILURE_LAYER", "failure_id": case.failure_id})
            continue
        observed = {
            "failure_id": case.failure_id,
            "guard": case.guard,
            "layer": case.layer,
            "expected_status": case.expected_status,
            "observed_status": observed_status,
            "expected_code": case.code,
            "observed_codes": observed_codes,
            "family_contract_fingerprint": candidate_binding.family_contract_fingerprint,
        }
        observations.append(observed)
        if observed_status != case.expected_status or observed_codes != [case.code]:
            failures.append({"code": "NATIVE_BAD_ORACLE_MISMATCH", **observed})

    status = "pass" if not failures else "fail"
    return {
        "schema_version": "worldguard.guard_model_contract_report.v1",
        "status": status,
        "ok": not failures,
        "purpose_count": len(GUARD_MODEL_PURPOSES),
        "native_good_count": len(NATIVE_GOOD_CASES),
        "protected_failure_count": len(expected_keys),
        "known_bad_count": len(PROTECTED_FAILURE_CLASSES),
        "candidate_binding_count": len(NATIVE_GOOD_CASES) + len(PROTECTED_FAILURE_CLASSES),
        "universe_fingerprint": _fingerprint(),
        "purposes": [item.to_dict() for item in GUARD_MODEL_PURPOSES],
        "protected_failures": [item.to_dict() for item in PROTECTED_FAILURE_CLASSES],
        "mesh_runtime_failures": MESH_RUNTIME_FAILURES,
        "observations": observations,
        "failures": failures,
        "claim_boundary": (
            "This target-native oracle proves that each declared Guard purpose has one native good case "
            "and every literal Guard-owned failure code has exactly one native bad case with an exact "
            "status/code reaction. Mesh provider/registration failures, arbitrary bugs, factual truth, "
            "installation parity, and release closure remain outside this receipt."
        ),
    }


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
