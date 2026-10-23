from pathlib import Path

SKILL = Path(__file__).resolve().parents[1] / "skills" / "worldguard"


def test_skill_text_stays_small() -> None:
    assert len((SKILL / "SKILL.md").read_bytes()) <= 6000
    for reference in sorted((SKILL / "references").glob("*.md")):
        assert len(reference.read_bytes()) <= 12000, reference.name


def test_skill_has_three_references_with_a_bounded_total():
    references = sorted((SKILL / 'references').glob('*.md'))
    assert {path.name for path in references} == {'guard-inputs.md', 'worldguard-contracts.md', 'model-mesh.md'}
    assert sum(path.stat().st_size for path in [SKILL / 'SKILL.md', *references]) <= 25000
    paragraphs = (SKILL / 'SKILL.md').read_text().split('\n\n')
    note = next(part for part in paragraphs if 'five abilities' in part)
    assert len(note.splitlines()) <= 6
