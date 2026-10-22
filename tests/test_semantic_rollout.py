from __future__ import annotations

import pytest

from worldguard import ProviderStatus, SemanticStatus, run_model_mesh
from worldguard.cli import main as worldguard_main
from worldguard.status import GuardStatus


def _mesh(guard: str, inputs: dict, *, text: str = "bounded semantic claim", asserts: list | None = None) -> dict:
    semantic = {
        "EventGuard": "event",
        "AgentGuard": "agent",
        "SpaceGuard": "space",
        "ResourceGuard": "resource",
        "CausalGuard": "causal",
        "ConflictGuard": "conflict",
        "NormGuard": "norm",
    }[guard]
    mesh = {
        "mesh_id": f"mesh-{semantic}",
        "run_id": "semantic-test",
        "nodes": [
            {
                "model_id": f"{semantic}-node",
                "authority": {"owns": [semantic]},
                "contract": {
                    "contract_id": f"contract-{semantic}",
                    "run_id": "semantic-test",
                    "claim": {
                        "claim_id": f"claim-{semantic}",
                        "text": text,
                        "target_guards": [guard],
                        "requested_semantics": [semantic],
                        "asserts": asserts or [],
                    },
                    "world_model": {
                        "model_id": f"model-{semantic}",
                        "model_version": "v1",
                    },
                    "inputs": inputs,
                },
            }
        ],
    }
    mesh["nodes"][0]["contract"]
    return mesh


NEGATIVE_PROBES = [
    (
        "EventGuard",
        {"events": [{"event_id": "e1", "at": "t0"}]},
        "SEM_EVENT_MISSING_AXIOM",
    ),
    (
        "AgentGuard",
        {
            "beliefs": {"a1": {"agent_id": "a1", "beliefs": ["ready"]}},
            "agent_model": {},
        },
        "SEM_AGENT_INCOMPLETE_BDI",
    ),
    (
        "SpaceGuard",
        {
            "spatial_relations": [
                {"x": "a", "y": "b", "at": "t0", "relation": "NTPP"},
                {"x": "b", "y": "c", "at": "t0", "relation": "NTPP"},
                {"x": "a", "y": "c", "at": "t0", "relation": "DC"},
            ]
        },
        "SEM_SPACE_RCC8_CONFLICT",
    ),
    (
        "ResourceGuard",
        {
            "resources": {
                "places": {"tank": [{"color": "fuel", "qty": 1}]},
                "transitions": [
                    {"id": "use-1", "consumes": [{"place": "tank", "color": "fuel", "qty": 1}]},
                    {"id": "use-2", "consumes": [{"place": "tank", "color": "fuel", "qty": 1}]},
                ],
            }
        },
        "SEM_RESOURCE_DOUBLE_CONSUMPTION",
    ),
    (
        "CausalGuard",
        {
            "causal_model": {
                "variables": ["x", "y"],
                "equations": {"x": 1, "y": "external_solver(x)"},
                "graph": [["x", "y"]],
            }
        },
        "SEM_CAUSAL_UNEVALUABLE_EQUATION",
    ),
    (
        "ConflictGuard",
        {"game_model": {"payoffs": [{"player": "p1", "value": 1}]}},
        "SEM_CONFLICT_INCOMPLETE_GAME",
    ),
    (
        "NormGuard",
        {"norms": [{"modality": "permitted", "action": "start"}]},
        "SEM_NORM_MISSING_CONDITION_FACT",
    ),
]


def test_known_shallow_semantic_probe_cannot_project_pass():
    """Keep the finite negative-probe matrix statically enumerable."""

    for guard, inputs, expected_code in NEGATIVE_PROBES:
        report = run_model_mesh(_mesh(guard, inputs))

        assert report.semantic_status != SemanticStatus.PASS
        assert report.status != GuardStatus.PASS
        assert expected_code in {
            finding["code"]
            for receipt in report.semantic_receipts
            for finding in receipt.findings
        }


def _valid_event_mesh() -> dict:
    return _mesh(
        "EventGuard",
        {"events": [{"event_id": "e1", "at": "t0", "initiates": "ready"}]},
        asserts=[{"holds": "ready", "at": "t0"}],
    )


def test_valid_bounded_semantic_rollout_reports_distinct_green_components():
    report = run_model_mesh(_valid_event_mesh())

    assert report.structural_status == GuardStatus.PASS
    assert report.semantic_status == SemanticStatus.PASS
    assert report.provider_status == ProviderStatus.AVAILABLE
    assert report.rollout_status == SemanticStatus.PASS
    assert report.status == GuardStatus.PASS
    assert report.depth_receipt is not None
    assert report.depth_receipt.predictive_claim_licensed is False


def test_retired_closure_profile_is_rejected_instead_of_skipping_semantics():
    mesh = _valid_event_mesh()
    mesh["closure_profile"] = "structural_only"

    with pytest.raises(ValueError, match="closure_profile is retired"):
        run_model_mesh(mesh)


@pytest.mark.parametrize("retired_value", ["semantic_rollout", "structural_only"])
def test_retired_closure_profile_cli_selector_is_rejected(retired_value: str):
    with pytest.raises(SystemExit) as error:
        worldguard_main(
            [
                "mesh-check",
                "--mesh",
                "unused.yaml",
                "--closure-profile",
                retired_value,
            ]
        )

    assert error.value.code == 2


def test_provider_unavailable_is_visible_and_fail_closed():
    mesh = _valid_event_mesh()
    mesh["provider_availability"] = {"EventGuard": False}

    report = run_model_mesh(mesh)

    assert report.structural_status == GuardStatus.PASS
    assert report.semantic_status == SemanticStatus.NOT_RUN
    assert report.provider_status == ProviderStatus.UNAVAILABLE
    assert report.status == GuardStatus.GAP
    assert report.semantic_receipts[0].skipped_reason == "provider_unavailable"


def test_native_depth_receipt_binds_model_checks_executors_and_claim_boundary():
    report = run_model_mesh(_valid_event_mesh())

    receipt = report.depth_receipt
    assert receipt is not None
    assert len(receipt.mesh_fingerprint) == 64
    assert receipt.executed_semantic_children == ["event-node:EventGuard"]
    assert receipt.structural_checks == [{"node_id": "event-node", "status": "PASS"}]
    assert "Bounded semantic rollout" in receipt.claim_boundary
