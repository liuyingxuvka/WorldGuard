"""Keep deleted source blocks from leaving long runs of blank lines."""
from pathlib import Path


def test_python_sources_have_at_most_two_consecutive_blank_lines():
    root = Path(__file__).resolve().parents[1]
    roots = ("worldguard", "tests", "scripts", "skills/worldguard/scripts", ".flowguard/models")
    violations = []
    for directory in roots:
        for path in sorted((root / directory).rglob("*.py")):
            run = 0
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                run = run + 1 if not line.strip() else 0
                if run == 3:
                    violations.append(f"{path.relative_to(root)}:{number}")
    assert not violations, "Three or more consecutive blank lines:\n" + "\n".join(violations)
