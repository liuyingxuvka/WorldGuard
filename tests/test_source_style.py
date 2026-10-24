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


def _one_statement_per_line_violations(path, text):
    import ast
    lines = text.splitlines()
    tree = ast.parse(text, filename=str(path))
    starts = {}
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.stmt):
            starts.setdefault(node.lineno, []).append(node)
        if isinstance(node, ast.ExceptHandler) and node.body and node.body[0].lineno == node.lineno:
            violations.append(node.lineno)
        for name in ("orelse", "finalbody"):
            body = getattr(node, name, None)
            if isinstance(node, ast.stmt) and body:
                head = lines[body[0].lineno - 1].strip()
                if head.startswith(("else:", "finally:")):
                    violations.append(body[0].lineno)
    violations.extend(number for number, nodes in starts.items() if len(nodes) > 1)
    violations.extend(number for number, line in enumerate(lines, 1) if len(line) > 160)
    return sorted(set(violations))


def test_python_sources_put_one_statement_per_line():
    root = Path(__file__).resolve().parents[1]
    violations = []
    for path in sorted((root / "worldguard").rglob("*.py")):
        found = _one_statement_per_line_violations(path, path.read_text(encoding="utf-8"))
        violations.extend(f"{path.relative_to(root)}:{number}" for number in found)
    assert not violations, "Several statements on one line or a line over 160 characters:\n" + "\n".join(violations)
