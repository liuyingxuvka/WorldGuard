from copy import deepcopy
from pathlib import Path
from worldguard.blueprint import blueprint_impact, blueprint_reverse_trace, load_world_blueprint
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/world_blueprint/planning_workflow_three_level.yaml"


def test_skill_entrypoint_has_current_static_contract_sections_and_fields() -> None:
    text = (ROOT / "skills/worldguard/SKILL.md").read_text(encoding="utf-8")
    headings = {
        line.removeprefix("## ").strip()
        for line in text.splitlines()
        if line.startswith("## ")
    }
    assert {
        "Purpose",
        "Entrypoint Scope",
        "Local Material Routing",
        "Entrypoint Acceptance Map",
        "Use When",
        "Do Not Use When",
        "Required Workflow",
        "Hard Gates",
        "Output Requirements",
    } <= headings
    lowered = text.lower()
    for field in (
        "evidence",
        "failures",
        "blockers",
        "skipped_checks",
        "residual_risk",
        "claim_boundary",
    ):
        assert field in lowered
    assert (
        "[references/task-local-model-deepening.md]"
        "(references/task-local-model-deepening.md)"
    ) in text
    assert "`task-local-model-deepening.md`" not in text


def test_blueprint_queries_leave_contract_and_fixture_unchanged() -> None:
    fixture_before = FIXTURE.read_bytes()
    blueprint = load_world_blueprint(FIXTURE)
    contract_before = deepcopy(blueprint.to_dict())

    blueprint_impact(
        blueprint,
        blueprint_fingerprint=blueprint.blueprint_fingerprint,
        changed_ids=["schedule_transition"],
    )
    blueprint_reverse_trace(
        blueprint,
        blueprint_fingerprint=blueprint.blueprint_fingerprint,
        target_id="root_plan_outcome",
    )

    assert blueprint.to_dict() == contract_before
    assert FIXTURE.read_bytes() == fixture_before

