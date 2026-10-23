from __future__ import annotations

import pytest

from tests.helpers import make_contract
from worldguard.guards import GUARD_RUNNERS
from worldguard.kernel import run_worldguard
from worldguard.semantic import causal_scenario_values, _resolve_event_guard
from worldguard.status import GuardStatus


def _semantic(guard: str, inputs: dict):
    return GUARD_RUNNERS[guard](make_contract(guard, inputs=inputs))


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
    assert semantic.status == GuardStatus.FAIL
    assert [row["code"] for row in semantic.errors] == [
        "EVENT_DANGLING_TRANSITION_STATE"
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
    assert semantic.status == GuardStatus.PASS
    assert _resolve_event_guard("ready", inputs["event_model"]["guard_values"]) is True
    inputs["event_model"]["guard_values"] = {}
    unresolved = _semantic("EventGuard", inputs)
    assert unresolved.status == GuardStatus.GAP
    assert [row["code"] for row in unresolved.errors] == ["EVENT_UNEVALUABLE_TRANSITION_GUARD"]


def test_norm_false_condition_fact_makes_the_norm_inactive() -> None:
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

    assert structural.status == GuardStatus.PASS
    assert semantic.status == GuardStatus.PASS


def test_active_norm_conflict_fails_and_inactive_prohibition_does_not() -> None:
    inputs = {'norms': [{'modality': 'obligatory', 'actor': 'keeper', 'action': 'stay_silent', 'condition': {'fact_id': 'oath_sworn', 'value': True}}, {'modality': 'forbidden', 'actor': 'keeper', 'action': 'stay_silent', 'condition': {'fact_id': 'flood_coming', 'value': True}}], 'facts': [{'fact_id': 'oath_sworn', 'value': True}, {'fact_id': 'flood_coming', 'value': True}]}
    structural = GUARD_RUNNERS["NormGuard"](make_contract("NormGuard", inputs=inputs))
    semantic = _semantic("NormGuard", inputs)
    assert structural.status == GuardStatus.FAIL
    assert [row["code"] for row in structural.errors] == ["NORM_ACTIVE_CONFLICT"]
    assert semantic.status == GuardStatus.FAIL
    assert [row["code"] for row in semantic.errors] == ["NORM_ACTIVE_CONFLICT"]
    inactive = {'norms': [{'modality': 'forbidden', 'actor': 'pilot', 'action': 'leave_harbor', 'condition': {'fact_id': 'storm_uncleared', 'value': True}}, {'modality': 'permitted', 'actor': 'pilot', 'action': 'leave_harbor', 'condition': {'fact_id': 'storm_cleared', 'value': True}}], 'facts': [{'fact_id': 'storm_uncleared', 'value': False}, {'fact_id': 'storm_cleared', 'value': True}]}
    assert GUARD_RUNNERS["NormGuard"](make_contract("NormGuard", inputs=inactive)).status == GuardStatus.PASS
    assert _semantic("NormGuard", inactive).status == GuardStatus.PASS


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
    assert semantic.status == GuardStatus.PASS
    assert semantic.errors == []


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
    assert semantic.status == GuardStatus.FAIL
    assert [row["code"] for row in semantic.errors] == [
        "AGENT_IDENTITY_MISMATCH"
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
    assert _semantic("AgentGuard", good_inputs).status == GuardStatus.PASS


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
    assert semantic.status == GuardStatus.FAIL
    assert [row["code"] for row in semantic.errors] == [
        "SPACE_RCC8_CONVERSE_CONTRADICTION"
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
    assert _semantic("SpaceGuard", good_inputs).status == GuardStatus.PASS


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
    assert semantic.status == GuardStatus.FAIL
    assert [row["code"] for row in semantic.errors] == [
        "RESOURCE_CUMULATIVE_OVERCONSUMPTION"
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
    assert _semantic("ResourceGuard", good_inputs).status == GuardStatus.PASS


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
    assert semantic.status == GuardStatus.GAP
    assert [row["code"] for row in semantic.errors] == [
        "CAUSAL_MISSING_BEHAVIOR_OBLIGATION"
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
    assert good_semantic.status == GuardStatus.PASS
    assert causal_scenario_values(good_inputs["causal_model"]) == {"s1": {"x": 1}}


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
    assert semantic.status == GuardStatus.FAIL
    assert [row["code"] for row in semantic.errors] == [
        "CONFLICT_REFERENCE_CLOSURE"
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
    assert _semantic("ConflictGuard", good_inputs).status == GuardStatus.PASS


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
        ("NormGuard", {'norms': [{'modality': 'obligatory', 'actor': 'keeper', 'action': 'stay_silent', 'condition': {'fact_id': 'oath_sworn', 'value': True}}, {'modality': 'forbidden', 'actor': 'keeper', 'action': 'stay_silent', 'condition': {'fact_id': 'flood_coming', 'value': True}}], 'facts': [{'fact_id': 'oath_sworn', 'value': True}, {'fact_id': 'flood_coming', 'value': True}]}, GuardStatus.FAIL),
    ],
)
def test_parent_qualification_cannot_hide_a_guard_semantic_known_bad(
    guard: str,
    inputs: dict,
    expected_status: GuardStatus,
) -> None:
    report = run_worldguard(make_contract(guard, inputs=inputs))

    assert report.status == expected_status
    assert report.guard_results[0].status == expected_status
    assert report.gaps
    assert report.guard_results[0].errors


@pytest.mark.parametrize("variables", [["y", "x"], ["x", "y"]])
def test_scenario_value_overrides_the_equation_in_any_declaration_order(variables) -> None:
    inputs = {"causal_model": {
        "variables": variables, "equations": {"x": "2", "y": "x + 1"},
        "graph": [["x", "y"]], "scenarios": {"s": {"x": 100}},
        "holdout_scenarios": {"h": {"x": 200}},
        "interventions": [{"intervention_id": "do-x", "scenario_id": "s", "set": {"x": 7}}],
        "counterfactuals": [{"counterfactual_id": "cf-y", "intervention_id": "do-x", "query": "y"}],
    }}
    report = run_worldguard(make_contract("CausalGuard", inputs=inputs, asserts=[{"variable": "y", "op": "==", "value": 101, "scenario": "s"}, {"variable": "y", "op": "==", "value": 201, "scenario": "h"}, {"variable": "y", "op": "==", "value": 8, "scenario": "do-x"}]))
    assert report.status == GuardStatus.PASS
    output = causal_scenario_values(inputs["causal_model"])
    assert output["s"] == {"x": 100, "y": 101}
    assert output["h"] == {"x": 200, "y": 201}
    assert output["do-x"] == {"x": 7, "y": 8}
    assert output["do-x"]["y"] == 8


def test_causal_identity_root_and_exogenous_input_remain_available() -> None:
    inputs = {"causal_model": {
        "variables": ["y", "x"], "equations": {"x": "x", "y": "x + z"},
        "exogenous": ["z"], "graph": [["x", "y"]],
        "scenarios": {"s": {"x": 3, "z": 2}},
    }}
    receipt = _semantic("CausalGuard", inputs)
    assert receipt.status == GuardStatus.PASS
    assert causal_scenario_values(inputs["causal_model"])["s"] == {"x": 3, "z": 2, "y": 5}


@pytest.mark.parametrize("equations", [
    {"x": "y + 1", "y": "x + 1"},
    {"x": "x + 1", "y": "x + 1"},
    {"x": "__import__('os')", "y": "x + 1"},
])
def test_causal_seed_cannot_resolve_cycles_or_unsafe_equations(equations) -> None:
    receipt = _semantic("CausalGuard", {"causal_model": {
        "variables": ["x", "y"], "equations": equations, "graph": [],
        "scenarios": {"s": {}},
    }})
    assert receipt.status == GuardStatus.GAP
    assert receipt.errors


def test_resource_ordered_production_enables_later_consumption() -> None:
    resources = {
        "places": {"p1": [{"color": "a", "qty": 1}], "p2": []},
        "capacities": {"p1": 1, "p2": 1},
        "transitions": [
            {"id": "move", "consumes": [{"place": "p1", "color": "a", "qty": 1}], "produces": [{"place": "p2", "color": "a", "qty": 1}]},
            {"id": "return", "consumes": [{"place": "p2", "color": "a", "qty": 1}], "produces": [{"place": "p1", "color": "a", "qty": 1}]},
        ],
    }
    report = run_worldguard(make_contract("ResourceGuard", inputs={"resources": resources}, asserts=[{"place": "p1", "qty": 1}]))
    assert report.status == GuardStatus.PASS
    resources["transitions"].reverse()
    reversed_report = run_worldguard(make_contract("ResourceGuard", inputs={"resources": resources}))
    assert reversed_report.status == GuardStatus.FAIL
    assert reversed_report.guard_results[0].errors[0]["code"] == "RESOURCE_MISSING_TOKEN"


def test_empty_intentions_are_valid_and_a_missing_intentions_key_is_a_gap() -> None:
    bystander = {"agent_id": "porter", "beliefs": ["ship_docked"], "desires": ["rest"], "intentions": []}
    inputs = {"beliefs": {"porter": bystander}}
    assert GUARD_RUNNERS["AgentGuard"](make_contract("AgentGuard", inputs=inputs)).status == GuardStatus.PASS
    assert _semantic("AgentGuard", inputs).status == GuardStatus.PASS

    missing = {"beliefs": {"porter": {key: value for key, value in bystander.items() if key != "intentions"}}}
    structural = GUARD_RUNNERS["AgentGuard"](make_contract("AgentGuard", inputs=missing))
    assert structural.status == GuardStatus.GAP
    assert [row["code"] for row in structural.errors] == ["AGENT_INCOMPLETE_BDI"]
    assert structural.missing_slots == [{"agent_id": "porter", "missing": ["intentions"]}]
    semantic = _semantic("AgentGuard", missing)
    assert semantic.status == GuardStatus.GAP
    assert [row["code"] for row in semantic.errors] == ["AGENT_INCOMPLETE_BDI"]
