import pytest

from tests.helpers import make_contract
from worldguard.guards import GUARD_RUNNERS
from worldguard.status import GuardStatus


CASES = [
    (
        "EventGuard",
        {
            GuardStatus.PASS: {"inputs": {"events": [{"event_id": "e1", "at": "t0", "initiates": "ready"}]}},
            GuardStatus.FAIL: {"inputs": {"event_model": {"contradictory_fluents": ["hot", "cold"]}}},
            GuardStatus.GAP: {"inputs": {}},
            GuardStatus.BOUNDARY_EXCEEDED: {"requested_semantics": ["event", "numeric_dynamics"]},
        },
    ),
    (
        "AgentGuard",
        {
            GuardStatus.PASS: {"inputs": {"beliefs": {"agent": {"agent_id": "agent", "beliefs": ["b"], "desires": ["d"], "intentions": ["i"]}}}},
            GuardStatus.FAIL: {"inputs": {"beliefs": {"agent": {}}, "agent_model": {"conflicting_intentions": ["i1", "i2"]}}},
            GuardStatus.GAP: {"inputs": {"agent_model": {"missing_beliefs": ["b_missing"]}}},
            GuardStatus.BOUNDARY_EXCEEDED: {"requested_semantics": ["agent", "payoff"]},
        },
    ),
    (
        "SpaceGuard",
        {
            GuardStatus.PASS: {"inputs": {"spatial_relations": [{"at": "t0", "x": "a", "y": "b", "relation": "DC"}]}},
            GuardStatus.FAIL: {
                "inputs": {
                    "spatial_relations": [
                        {"at": "t0", "x": "a", "y": "b", "relation": "DC"},
                        {"at": "t0", "x": "a", "y": "b", "relation": "EC"},
                    ]
                }
            },
            GuardStatus.GAP: {"inputs": {}},
            GuardStatus.BOUNDARY_EXCEEDED: {"requested_semantics": ["spatial", "metric_distance"]},
        },
    ),
    (
        "ResourceGuard",
        {
            GuardStatus.PASS: {
                "inputs": {
                    "resources": {
                        "places": {"tank": [{"color": "h2", "qty": 1}]},
                        "transitions": [{"id": "run", "consumes": [{"place": "tank", "color": "h2", "qty": 1}]}],
                    }
                }
            },
            GuardStatus.FAIL: {
                "inputs": {
                    "resources": {
                        "places": {"tank": [{"color": "h2", "qty": 2}]},
                        "capacities": {"out": 1},
                        "transitions": [
                            {
                                "id": "run",
                                "consumes": [{"place": "tank", "color": "h2", "qty": 1}],
                                "produces": [{"place": "out", "color": "kwh", "qty": 2}],
                            }
                        ],
                    }
                }
            },
            GuardStatus.GAP: {
                "inputs": {
                    "resources": {
                        "places": {"tank": [{"color": "h2", "qty": 0}]},
                        "transitions": [{"id": "run", "consumes": [{"place": "tank", "color": "h2", "qty": 1}]}],
                    }
                }
            },
            GuardStatus.BOUNDARY_EXCEEDED: {"requested_semantics": ["resource", "permission"]},
        },
    ),
    (
        "CausalGuard",
        {
            GuardStatus.PASS: {"inputs": {"causal_model": {"variables": ["x"], "equations": {"x": 1}, "scenarios": {"s1": {}}}}},
            GuardStatus.FAIL: {"inputs": {"causal_model": {"variables": ["x"], "equations": {"x": "f(y)"}, "graph": [["x", "y"], ["y", "x"]]}}},
            GuardStatus.GAP: {"inputs": {"causal_model": {"variables": ["x"], "equations": {}}}},
            GuardStatus.BOUNDARY_EXCEEDED: {"requested_semantics": ["causal", "temporal_story"]},
        },
    ),
    (
        "ConflictGuard",
        {
            GuardStatus.PASS: {"inputs": {"game_model": {"players": ["a"], "actions": ["hold"], "states": ["s"], "transitions": [{"from": "s", "to": "s", "probabilities": [1.0]}], "payoffs": [{"state": "s", "reward": {"a": 1}}]}}},
            GuardStatus.FAIL: {"inputs": {"game_model": {"transitions": [{"probabilities": [0.7, 0.7]}], "payoffs": [{"state": "s"}]}}},
            GuardStatus.GAP: {"inputs": {"game_model": {"payoffs": []}}},
            GuardStatus.BOUNDARY_EXCEEDED: {"requested_semantics": ["conflict", "deontic"]},
        },
    ),
    (
        "NormGuard",
        {
            GuardStatus.PASS: {"text": "operator may start", "inputs": {"norms": [{"modality": "permitted", "action": "start", "condition": "authorized"}], "facts": [{"fact_id": "authorized", "value": True}]}},
            GuardStatus.FAIL: {"inputs": {'norms': [{'modality': 'obligatory', 'actor': 'keeper', 'action': 'stay_silent', 'condition': {'fact_id': 'oath_sworn', 'value': True}}, {'modality': 'forbidden', 'actor': 'keeper', 'action': 'stay_silent', 'condition': {'fact_id': 'flood_coming', 'value': True}}], 'facts': [{'fact_id': 'oath_sworn', 'value': True}, {'fact_id': 'flood_coming', 'value': True}]}},
            GuardStatus.GAP: {"text": "operator may vent", "inputs": {"norms": []}},
            GuardStatus.BOUNDARY_EXCEEDED: {"requested_semantics": ["norm", "physical_enablement"]},
        },
    ),
]


def test_guard_status_matrix():
    """Exercise the explicit finite matrix without a dynamic pytest marker."""

    for guard, cases in CASES:
        runner = GUARD_RUNNERS[guard]
        for expected_status, kwargs in cases.items():
            contract = make_contract(guard, **kwargs)
            result = runner(contract)
            assert result.status == expected_status
            assert result.ledgers


def test_event_guard_treats_scalar_fluent_ids_as_whole_identities() -> None:
    contract = make_contract(
        "EventGuard",
        inputs={
            "events": [
                {
                    "event_id": "e1",
                    "at": "t1",
                    "terminates": "ready",
                    "initiates": "running",
                }
            ]
        },
    )

    result = GUARD_RUNNERS["EventGuard"](contract)

    assert result.status == GuardStatus.PASS
