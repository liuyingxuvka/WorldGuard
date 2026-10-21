from copy import deepcopy
from pathlib import Path
from worldguard.blueprint import blueprint_impact, blueprint_reverse_trace, load_world_blueprint
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/world_blueprint/planning_workflow_three_level.yaml"




def test_blueprint_queries_leave_contract_and_fixture_unchanged() -> None:
    fixture_before = FIXTURE.read_bytes()
    blueprint = load_world_blueprint(FIXTURE)
    contract_before = deepcopy(blueprint.to_dict())

    blueprint_impact(
        blueprint,
        changed_ids=["schedule_transition"],
    )
    blueprint_reverse_trace(
        blueprint,
        target_id="root_plan_outcome",
    )

    assert blueprint.to_dict() == contract_before
    assert FIXTURE.read_bytes() == fixture_before

