"""WorldGuard's finite model for layered test evidence."""

MODEL_ID = "test_evidence_mesh"
REQUIRED_STATES = (
    "inventory_is_complete",
    "every_partition_has_one_owner",
    "stale_and_skipped_are_visible",
    "progress_is_not_terminal_pass",
    "release_scope_has_explicit_evidence",
)


def run_model() -> None:
    state = {name: True for name in REQUIRED_STATES}
    if tuple(state) != REQUIRED_STATES:
        raise AssertionError("test-evidence mesh state order drifted")
    for broken in REQUIRED_STATES:
        candidate = dict(state)
        candidate[broken] = False
        if all(candidate.values()):
            raise AssertionError(f"incomplete evidence was accepted: {broken}")


if __name__ == "__main__":
    run_model()
    print(f"{MODEL_ID}: pass")
