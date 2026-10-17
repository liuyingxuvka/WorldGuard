"""The authority model retains current input, owner and execution order."""
import importlib.util
from pathlib import Path
import sys
import pytest

PATH = Path(__file__).resolve().parents[1] / ".flowguard/behavior_commitment_ledger/model.py"
SPEC = importlib.util.spec_from_file_location("worldguard_authority_model", PATH)
MODEL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODEL
SPEC.loader.exec_module(MODEL)


def test_native_result_requires_current_owner_and_order():
    state = MODEL.Authority("template_selection")
    with pytest.raises(ValueError):
        MODEL.transition(state, "record_native_result", "PASS")
    state = MODEL.transition(state, "bind_current_input")
    with pytest.raises(ValueError):
        MODEL.transition(state, "select_native_route", "foreign")
    state = MODEL.transition(state, "select_native_route", "template_selection")
    assert MODEL.transition(state, "record_native_result", "GAP").native_status == "GAP"


def test_fact_authority_never_closes_the_task():
    state = MODEL.Authority("fact_revision", True, "fact_revision", True, "PASS")
    with pytest.raises(ValueError, match="task-local"):
        MODEL.transition(state, "close_task")
    assert MODEL.run_model()["ok"]
