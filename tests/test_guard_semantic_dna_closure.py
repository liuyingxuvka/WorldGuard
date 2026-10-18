from __future__ import annotations

import pytest

from tests.helpers import make_contract
from worldguard.guards import GUARD_RUNNERS
from worldguard.kernel import run_worldguard
from worldguard.semantic import SemanticStatus, execute_semantic
from worldguard.status import GuardStatus


def _semantic(guard: str, inputs: dict):
    contract = make_contract(guard, inputs=inputs)
    return execute_semantic(
        node_id=f"node:{guard}",
        guard=guard,
        contract=contract.for_guard(guard),
        provider_available=True,
    )


def test_event_dangling_transition_state_is_not_structural_or_semantic_green() -> None:
    inputs = {
        "event_model": {
            "states": [
                {"state_id": "waiting", "initial": True, "terminal": False}
            ],
            "transitions": [
                {
                    "transition_id": "go",
                    "source_state": "waiting",
                    "target_state": "missing",
                    "guard": True,
                    "effect": "done",
                }
            ],
        }
    }
    contract = make_contract("EventGuard", inputs=inputs)

    structural = GUARD_RUNNERS["EventGuard"](contract)
    semantic = _semantic("EventGuard", inputs)

    assert structural.status == GuardStatus.FAIL
    assert [row["code"] for row in structural.errors] == [
        "EVENT_DANGLING_TRANSITION_STATE"
    ]
    assert semantic.status == SemanticStatus.FAIL
    assert [row["code"] for row in semantic.findings] == [
        "SEM_EVENT_DANGLING_TRANSITION_STATE"
    ]


def test_event_closed_transition_executes_from_initial_to_target_state() -> None:
    inputs = {
        "event_model": {
            "states": [
                {"state_id": "waiting", "initial": True, "terminal": False},
                {"state_id": "done", "initial": False, "terminal": True},
            ],
            "transitions": [
                {
                    "transition_id": "go",
                    "source_state": "waiting",
                    "target_state": "done",
                    "guard": "ready",
                    "effect": "mark_done",
                }
            ],
            "guard_values": {"ready": True},
        }
    }
    contract = make_contract("EventGuard", inputs=inputs)

    structural = GUARD_RUNNERS["EventGuard"](contract)
    semantic = _semantic("EventGuard", inputs)

    assert structural.status == GuardStatus.PASS
    assert semantic.status == SemanticStatus.PASS
    assert semantic.outputs["executed_transition_ids"] == ["go"]
    assert semantic.outputs["reached_state_ids"] == ["done", "waiting"]


def test_norm_false_condition_fact_is_not_structural_or_semantic_green() -> None:
    inputs = {
        "norms": [
            {
                "norm_id": "allow-start",
                "modality": "permitted",
                "subject_id": "operator",
                "action": "start",
                "condition": "authorized",
            }
        ],
        "facts": [{"fact_id": "authorized", "value": False}],
    }
    contract = make_contract("NormGuard", inputs=inputs)

    structural = GUARD_RUNNERS["NormGuard"](contract)
    semantic = _semantic("NormGuard", inputs)

    assert structural.status == GuardStatus.GAP
    assert [row["code"] for row in structural.errors] == [
        "NORM_CONDITION_NOT_SATISFIED"
    ]
    assert semantic.status == SemanticStatus.GAP
    assert [row["code"] for row in semantic.findings] == [
        "SEM_NORM_CONDITION_NOT_SATISFIED"
    ]


def test_norm_true_condition_fact_qualifies_the_declared_norm() -> None:
    inputs = {
        "norms": [
            {
                "norm_id": "allow-start",
                "modality": "permitted",
                "subject_id": "operator",
                "action": "start",
                "condition": {"fact_id": "authorized", "equals": True},
            }
        ],
        "facts": [{"fact_id": "authorized", "value": True}],
    }
    contract = make_contract("NormGuard", inputs=inputs)

    structural = GUARD_RUNNERS["NormGuard"](contract)
    semantic = _semantic("NormGuard", inputs)

    assert structural.status == GuardStatus.PASS
    assert semantic.status == SemanticStatus.PASS
    assert semantic.outputs == {"evaluated_norms": 1, "condition_facts": 1}


def test_agent_map_key_must_equal_agent_id() -> None:
    bad_inputs = {
        "beliefs": {
            "alice": {
                "agent_id": "bob",
                "beliefs": ["ready"],
                "desires": ["finish"],
                "intentions": ["act"],
            }
        }
    }
    structural = GUARD_RUNNERS["AgentGuard"](
        make_contract("AgentGuard", inputs=bad_inputs)
    )
    semantic = _semantic("AgentGuard", bad_inputs)
    assert structural.status == GuardStatus.FAIL
    assert [row["code"] for row in structural.errors] == ["AGENT_IDENTITY_MISMATCH"]
    assert semantic.status == SemanticStatus.FAIL
    assert [row["code"] for row in semantic.findings] == [
        "SEM_AGENT_IDENTITY_MISMATCH"
    ]

    good_inputs = {
        "beliefs": {
            "alice": {
                "agent_id": "alice",
                "beliefs": ["ready"],
                "desires": ["finish"],
                "intentions": ["act"],
            }
        }
    }
    assert GUARD_RUNNERS["AgentGuard"](
        make_contract("AgentGuard", inputs=good_inputs)
    ).status == GuardStatus.PASS
    assert _semantic("AgentGuard", good_inputs).status == SemanticStatus.PASS


def test_space_reverse_relation_must_be_exact_rcc8_converse() -> None:
    bad_inputs = {
        "spatial_relations": [
            {"at": "t0", "x": "a", "y": "b", "relation": "EC"},
            {"at": "t0", "x": "b", "y": "a", "relation": "DC"},
        ]
    }
    structural = GUARD_RUNNERS["SpaceGuard"](
        make_contract("SpaceGuard", inputs=bad_inputs)
    )
    semantic = _semantic("SpaceGuard", bad_inputs)
    assert structural.status == GuardStatus.FAIL
    assert [row["code"] for row in structural.errors] == [
        "SPACE_RCC8_CONVERSE_CONTRADICTION"
    ]
    assert semantic.status == SemanticStatus.FAIL
    assert [row["code"] for row in semantic.findings] == [
        "SEM_SPACE_RCC8_CONVERSE_CONFLICT"
    ]

    good_inputs = {
        "spatial_relations": [
            {"at": "t0", "x": "a", "y": "b", "relation": "EC"},
            {"at": "t0", "x": "b", "y": "a", "relation": "EC"},
        ]
    }
    assert GUARD_RUNNERS["SpaceGuard"](
        make_contract("SpaceGuard", inputs=good_inputs)
    ).status == GuardStatus.PASS
    assert _semantic("SpaceGuard", good_inputs).status == SemanticStatus.PASS


def test_resource_inventory_does_not_hide_cumulative_transition_overspend() -> None:
    bad_inputs = {
        "resources": {
            "inventory": [{"resource_id": "fuel", "unit": "unit", "quantity": 1}],
            "places": {"tank": [{"color": "fuel", "qty": 1}]},
            "transitions": [
                {
                    "id": "use-1",
                    "consumes": [{"place": "tank", "color": "fuel", "qty": 1}],
                },
                {
                    "id": "use-2",
                    "consumes": [{"place": "tank", "color": "fuel", "qty": 1}],
                },
            ],
        }
    }
    structural = GUARD_RUNNERS["ResourceGuard"](
        make_contract("ResourceGuard", inputs=bad_inputs)
    )
    semantic = _semantic("ResourceGuard", bad_inputs)
    assert structural.status == GuardStatus.FAIL
    assert [row["code"] for row in structural.errors] == [
        "RESOURCE_CUMULATIVE_OVERCONSUMPTION"
    ]
    assert semantic.status == SemanticStatus.FAIL
    assert [row["code"] for row in semantic.findings] == [
        "SEM_RESOURCE_DOUBLE_CONSUMPTION"
    ]

    good_inputs = {
        "resources": {
            "inventory": [{"resource_id": "fuel", "unit": "unit", "quantity": 1}],
            "places": {"tank": [{"color": "fuel", "qty": 1}]},
            "transitions": [
                {
                    "id": "use-1",
                    "consumes": [{"place": "tank", "color": "fuel", "qty": 1}],
                }
            ],
        }
    }
    assert GUARD_RUNNERS["ResourceGuard"](
        make_contract("ResourceGuard", inputs=good_inputs)
    ).status == GuardStatus.PASS
    assert _semantic("ResourceGuard", good_inputs).status == SemanticStatus.PASS


def test_causal_equations_need_at_least_one_executable_behavior_obligation() -> None:
    bad_inputs = {
        "causal_model": {
            "variables": ["x"],
            "equations": {"x": 1},
            "graph": [],
        }
    }
    structural = GUARD_RUNNERS["CausalGuard"](
        make_contract("CausalGuard", inputs=bad_inputs)
    )
    semantic = _semantic("CausalGuard", bad_inputs)
    assert structural.status == GuardStatus.GAP
    assert [row["code"] for row in structural.errors] == [
        "CAUSAL_MISSING_BEHAVIOR_OBLIGATION"
    ]
    assert semantic.status == SemanticStatus.GAP
    assert [row["code"] for row in semantic.findings] == [
        "SEM_CAUSAL_MISSING_BEHAVIOR_OBLIGATION"
    ]

    good_inputs = {
        "causal_model": {
            "variables": ["x"],
            "equations": {"x": 1},
            "graph": [],
            "scenarios": {"s1": {}},
        }
    }
    assert GUARD_RUNNERS["CausalGuard"](
        make_contract("CausalGuard", inputs=good_inputs)
    ).status == GuardStatus.PASS
    good_semantic = _semantic("CausalGuard", good_inputs)
    assert good_semantic.status == SemanticStatus.PASS
    assert good_semantic.outputs["executed_scenario_ids"] == ["s1"]


def test_conflict_references_must_close_over_players_states_and_actions() -> None:
    bad_inputs = {
        "game_model": {
            "players": ["alice", "bob"],
            "actions": ["share"],
            "states": ["open"],
            "transitions": [
                {"from": "ghost", "to": "void", "probabilities": [1.0]}
            ],
            "payoffs": [{"player": "mallory", "state": "void", "value": 1}],
        }
    }
    structural = GUARD_RUNNERS["ConflictGuard"](
        make_contract("ConflictGuard", inputs=bad_inputs)
    )
    semantic = _semantic("ConflictGuard", bad_inputs)
    assert structural.status == GuardStatus.FAIL
    assert [row["code"] for row in structural.errors] == [
        "CONFLICT_REFERENCE_CLOSURE"
    ]
    assert semantic.status == SemanticStatus.FAIL
    assert [row["code"] for row in semantic.findings] == [
        "SEM_CONFLICT_REFERENCE_CLOSURE"
    ]

    good_inputs = {
        "game_model": {
            "players": ["alice", "bob"],
            "actions": ["share", "wait"],
            "states": ["open", "resolved"],
            "transitions": [
                {"from": "open", "to": "resolved", "probabilities": [1.0]}
            ],
            "payoffs": [
                {"player": "alice", "state": "resolved", "value": 1},
                {"player": "bob", "state": "resolved", "value": 1},
            ],
        }
    }
    assert GUARD_RUNNERS["ConflictGuard"](
        make_contract("ConflictGuard", inputs=good_inputs)
    ).status == GuardStatus.PASS
    assert _semantic("ConflictGuard", good_inputs).status == SemanticStatus.PASS


@pytest.mark.parametrize(
    ("guard", "inputs", "expected_status"),
    [
        (
            "EventGuard",
            {
                "event_model": {
                    "states": [
                        {
                            "state_id": "waiting",
                            "initial": True,
                            "terminal": False,
                        }
                    ],
                    "transitions": [
                        {
                            "transition_id": "go",
                            "source_state": "waiting",
                            "target_state": "missing",
                            "guard": True,
                            "effect": "done",
                        }
                    ],
                }
            },
            GuardStatus.FAIL,
        ),
        (
            "AgentGuard",
            {
                "beliefs": {
                    "alice": {
                        "agent_id": "bob",
                        "beliefs": ["ready"],
                        "desires": ["finish"],
                        "intentions": ["act"],
                    }
                }
            },
            GuardStatus.FAIL,
        ),
        (
            "SpaceGuard",
            {
                "spatial_relations": [
                    {"at": "t0", "x": "a", "y": "b", "relation": "EC"},
                    {"at": "t0", "x": "b", "y": "a", "relation": "DC"},
                ]
            },
            GuardStatus.FAIL,
        ),
        (
            "ResourceGuard",
            {
                "resources": {
                    "inventory": [
                        {"resource_id": "fuel", "unit": "unit", "quantity": 1}
                    ],
                    "places": {"tank": [{"color": "fuel", "qty": 1}]},
                    "transitions": [
                        {
                            "id": "use-1",
                            "consumes": [
                                {"place": "tank", "color": "fuel", "qty": 1}
                            ],
                        },
                        {
                            "id": "use-2",
                            "consumes": [
                                {"place": "tank", "color": "fuel", "qty": 1}
                            ],
                        },
                    ],
                }
            },
            GuardStatus.FAIL,
        ),
        (
            "CausalGuard",
            {
                "causal_model": {
                    "variables": ["x"],
                    "equations": {"x": 1},
                    "graph": [],
                }
            },
            GuardStatus.GAP,
        ),
        (
            "ConflictGuard",
            {
                "game_model": {
                    "players": ["alice", "bob"],
                    "actions": ["share"],
                    "states": ["open"],
                    "transitions": [
                        {"from": "ghost", "to": "void", "probabilities": [1.0]}
                    ],
                    "payoffs": [
                        {"player": "mallory", "state": "void", "value": 1}
                    ],
                }
            },
            GuardStatus.FAIL,
        ),
        (
            "NormGuard",
            {
                "norms": [
                    {
                        "norm_id": "allow-start",
                        "modality": "permitted",
                        "subject_id": "operator",
                        "action": "start",
                        "condition": "authorized",
                    }
                ],
                "facts": [{"fact_id": "authorized", "value": False}],
            },
            GuardStatus.GAP,
        ),
    ],
)
def test_parent_qualification_cannot_hide_a_guard_semantic_known_bad(
    guard: str,
    inputs: dict,
    expected_status: GuardStatus,
) -> None:
    report = run_worldguard(make_contract(guard, inputs=inputs))

    assert report.status == expected_status
    assert report.structural_status == expected_status
    assert report.semantic_status == SemanticStatus(expected_status.value)
    assert report.rollout_status == SemanticStatus(expected_status.value)
    assert report.depth_state["status"] == expected_status.value
    assert report.gaps
    assert report.semantic_receipts[0].findings


@pytest.mark.parametrize("variables", [["y", "x"], ["x", "y"]])
def test_causal_pending_endogenous_seed_never_changes_final_equations(variables) -> None:
    inputs = {"causal_model": {
        "variables": variables, "equations": {"x": "2", "y": "x + 1"},
        "graph": [["x", "y"]], "scenarios": {"s": {"x": 100}},
        "holdout_scenarios": {"h": {"x": 200}},
        "interventions": [{"intervention_id": "do-x", "scenario_id": "s", "set": {"x": 7}}],
        "counterfactuals": [{"counterfactual_id": "cf-y", "intervention_id": "do-x", "query": "y"}],
    }}
    report = run_worldguard(make_contract("CausalGuard", inputs=inputs))
    assert report.status == GuardStatus.PASS
    output = report.semantic_receipts[0].outputs
    assert output["scenario_results"]["s"] == {"x": 2, "y": 3}
    assert output["scenario_results"]["h"] == {"x": 2, "y": 3}
    assert output["intervention_results"]["do-x"] == {"x": 7, "y": 8}
    assert output["counterfactual_results"]["cf-y"] == 8


def test_causal_identity_root_and_exogenous_input_remain_available() -> None:
    inputs = {"causal_model": {
        "variables": ["y", "x"], "equations": {"x": "x", "y": "x + z"},
        "exogenous": ["z"], "graph": [["x", "y"]],
        "scenarios": {"s": {"x": 3, "z": 2}},
    }}
    receipt = _semantic("CausalGuard", inputs)
    assert receipt.status == SemanticStatus.PASS
    assert receipt.outputs["scenario_results"]["s"] == {"x": 3, "z": 2, "y": 5}


@pytest.mark.parametrize("equations", [
    {"x": "y + 1", "y": "x + 1"},
    {"x": "x + 1", "y": "x + 1"},
    {"x": "__import__('os')", "y": "x + 1"},
])
def test_causal_seed_cannot_resolve_cycles_or_unsafe_equations(equations) -> None:
    receipt = _semantic("CausalGuard", {"causal_model": {
        "variables": ["x", "y"], "equations": equations, "graph": [],
        "scenarios": {"s": {"x": 1, "y": 2}},
    }})
    assert receipt.status == SemanticStatus.GAP
    assert receipt.findings


def test_resource_ordered_production_enables_later_consumption() -> None:
    resources = {
        "places": {"p1": [{"color": "a", "qty": 1}], "p2": []},
        "capacities": {"p1": 1, "p2": 1},
        "transitions": [
            {"id": "move", "consumes": [{"place": "p1", "color": "a", "qty": 1}], "produces": [{"place": "p2", "color": "a", "qty": 1}]},
            {"id": "return", "consumes": [{"place": "p2", "color": "a", "qty": 1}], "produces": [{"place": "p1", "color": "a", "qty": 1}]},
        ],
    }
    report = run_worldguard(make_contract("ResourceGuard", inputs={"resources": resources}))
    assert report.structural_status == GuardStatus.PASS
    assert report.semantic_status == SemanticStatus.PASS
    resources["transitions"].reverse()
    reversed_report = run_worldguard(make_contract("ResourceGuard", inputs={"resources": resources}))
    assert reversed_report.structural_status == GuardStatus.GAP
    assert reversed_report.semantic_status == SemanticStatus.GAP
