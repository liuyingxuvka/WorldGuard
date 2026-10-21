from worldguard.contracts import GuardContract
from worldguard.kernel import run_worldguard
from worldguard.status import GuardStatus



def test_kernel_preserves_upstream_gap_in_aggregate_ledger():
    data = {
            "contract_id": "kernel-gap",
            "run_id": "kernel-test",
                "claim": {
                    "claim_id": "purge",
                    "text": "operator may purge after missing event fact",
                    "target_guards": ["EventGuard", "NormGuard"],
                    "requested_semantics": ["event", "norm"],
                },
            "world_model": {"model_id": "m", "model_version": "v"},
            "inputs": {"norms": [{"modality": "permitted", "action": "purge"}]},
        }
    data
    contract = GuardContract.from_dict(data)

    report = run_worldguard(contract)

    assert report.status == GuardStatus.GAP
    assert any(entry.channel == "gap" for entry in report.aggregate_ledger)
    assert all(entry.read_only_for_downstream for entry in report.aggregate_ledger)


def test_kernel_aggregates_fail_before_gap_and_boundary():
    data = {
            "contract_id": "kernel-fail",
            "run_id": "kernel-test",
                "claim": {
                    "claim_id": "mixed",
                    "text": "Company A may share the full membrane recipe with metric distance",
                    "target_guards": ["SpaceGuard", "ConflictGuard", "NormGuard"],
                    "requested_semantics": ["spatial", "conflict", "norm", "metric_distance"],
                },
            "world_model": {"model_id": "m", "model_version": "v"},
            "inputs": {
                "spatial_relations": [{"at": "t0", "x": "a", "y": "b", "relation": "DC"}],
                "game_model": {"payoffs": [{"joint_action": ["C_block_recipe_release"]}]},
                "norms": [{"modality": "forbidden", "actor": "A", "action": "share_membrane_recipe", "condition": "nda"}, {"modality": "permitted", "actor": "A", "action": "share_membrane_recipe", "condition": "nda"}],
                "facts": [{"fact_id": "nda", "value": True}],
            },
        }
    data
    contract = GuardContract.from_dict(data)

    report = run_worldguard(contract)

    assert report.status == GuardStatus.FAIL
    assert any(entry.status_impact == "supports_fail" for entry in report.aggregate_ledger)
