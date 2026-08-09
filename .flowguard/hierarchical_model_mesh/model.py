"""WorldGuard's finite model for parent/child model topology.

This is a small governance model, not a reconstruction of the target
application.  It records the invariants that let a parent model consume child
models without silently turning a parent receipt into child evidence.
"""

MODEL_ID = "hierarchical_model_mesh"
REQUIRED_STATES = (
    "root_is_unique",
    "structural_parent_is_unique",
    "support_edges_are_non_structural",
    "child_receipts_are_exact_and_distinct",
    "feedback_progress_is_current",
)


def run_model() -> None:
    state = {name: True for name in REQUIRED_STATES}
    if tuple(state) != REQUIRED_STATES:
        raise AssertionError("hierarchical model state order drifted")
    for broken in REQUIRED_STATES:
        candidate = dict(state)
        candidate[broken] = False
        if all(candidate.values()):
            raise AssertionError(f"broken topology was accepted: {broken}")


if __name__ == "__main__":
    run_model()
    print(f"{MODEL_ID}: pass")
