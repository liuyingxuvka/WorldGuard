from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "worldguard"


def test_skill_text_stays_small() -> None:
    assert len((SKILL / "SKILL.md").read_bytes()) <= 6000
    for reference in sorted((SKILL / "references").glob("*.md")):
        assert len(reference.read_bytes()) <= 12000, reference.name
