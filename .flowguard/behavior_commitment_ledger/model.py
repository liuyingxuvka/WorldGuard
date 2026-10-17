"""Executable bounded authority model; current code/test ownership lives in map.json.

This model tracks current input -> native route -> executed result. It never
uses saved test receipts as a prerequisite for ordinary domain work.
"""
from dataclasses import dataclass, replace

MODEL_ID = "behavior_commitment_ledger"

@dataclass(frozen=True)
class Authority:
    owner: str
    current_input: bool = False
    route: str = ""
    executed: bool = False
    native_status: str = "NOT_RUN"
    task_closed: bool = False


def transition(state: Authority, action: str, value: str = "") -> Authority:
    if action == "bind_current_input":
        return replace(state, current_input=True)
    if action == "select_native_route":
        if not state.current_input or value != state.owner:
            raise ValueError("one current target-owned route is required")
        return replace(state, route=value)
    if action == "record_native_result":
        if state.route != state.owner or value not in {"PASS", "FAIL", "GAP", "BOUNDARY_EXCEEDED"}:
            raise ValueError("native execution needs its selected owner and a typed result")
        return replace(state, executed=True, native_status=value)
    if action == "close_task":
        if state.owner == "fact_revision":
            raise ValueError("fact activation returns to the task-local owner")
        raise ValueError("this authority model never substitutes for task closure")
    raise ValueError("unknown authority action")


def run_model() -> dict:
    for owner in ("current_input_authority", "template_selection", "fact_revision"):
        initial = Authority(owner)
        bound = transition(initial, "bind_current_input")
        selected = transition(bound, "select_native_route", owner)
        result = transition(selected, "record_native_result", "PASS")
        assert result.executed and not result.task_closed
        for state, action, value in ((initial, "select_native_route", owner),
                                     (bound, "select_native_route", "foreign"),
                                     (initial, "record_native_result", "PASS"),
                                     (result, "close_task", "")):
            try:
                transition(state, action, value)
            except ValueError:
                pass
            else:
                raise AssertionError("invalid ownership/order was accepted")
    return {"ok": True, "owners": 3, "claim_boundary": "Finite authority and order model only."}
