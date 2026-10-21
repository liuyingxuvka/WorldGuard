from pathlib import Path

import yaml

from worldguard.contracts import GuardContract, derive_guard_requirements
from worldguard.kernel import run_worldguard

SCENE = Path(__file__).resolve().parent / "fixtures" / "scene_locked_door.yaml"
WORDS = ["after", "then", "permission", "authorized", "may", "will happen", "rafters", "metric distance in meters"]


def test_claim_prose_never_changes_the_verdict() -> None:
    base = yaml.safe_load(SCENE.read_text(encoding="utf-8"))
    base_contract = GuardContract.from_dict(base)
    assert run_worldguard(base_contract).status.value == "PASS"
    for word in WORDS:
        data = {**base, "claim": {**base["claim"], "text": f"{base['claim']['text']} ({word})"}}
        contract = GuardContract.from_dict(data)
        assert run_worldguard(contract).status.value == "PASS", word
        assert derive_guard_requirements(contract.claim).guard_ids == derive_guard_requirements(base_contract.claim).guard_ids


def test_the_story_order_of_resource_transitions_is_checked() -> None:
    data = yaml.safe_load(SCENE.read_text(encoding="utf-8"))
    transitions = data["inputs"]["resources"]["transitions"]
    data["inputs"]["resources"]["transitions"] = [transitions[0], transitions[2], transitions[1]]
    assert run_worldguard(GuardContract.from_dict(data)).status.value == "FAIL"
