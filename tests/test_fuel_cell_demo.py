from worldguard.examples.fuel_cell import REQUIRED_GUARDS, run_check


def test_fuel_cell_toy_replay_passes():
    result = run_check()

    assert result["ok"] is True
    assert set(result["guards_verified"]) == set(REQUIRED_GUARDS)
    assert result["mismatches"] == []
    assert result["claim_statuses"] == ["PASS", "PASS", "FAIL"]
    assert "no real fuel-cell thermodynamics" in result["toy_boundaries_verified"]
