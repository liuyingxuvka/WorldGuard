"""Every original rule, bad observation, native binding and old system route has a destination."""
import ast
import json
from pathlib import Path
import pytest
from .contract_cases import TOPICS, module, mutations

ROOT = Path(__file__).resolve().parents[2]
COVERAGE = json.loads(Path(__file__).with_name('coverage.json').read_text())


def assert_anchor(anchor):
    path, _, name = anchor.partition(':')
    name = name.split('[', 1)[0].split('.')[-1]
    definitions = {n.name for n in ast.walk(ast.parse((ROOT/path).read_text()))
                   if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    assert name in definitions, anchor


def test_every_original_rule_variant_and_native_test_link_remains():
    rows = COVERAGE['models']
    assert len(rows) == len(TOPICS) == 9
    assert sum(len(row['rules']) for row in rows) == 40
    assert sum(len(row['bad_variants']) for row in rows) == 45
    assert sum(len(rule['production_tests']) for row in rows for rule in row['rules']) == 58
    for row in rows:
        contract = module(row['topic'])
        assert [rule['id'] for rule in row['rules']] == list(contract.RULE_NAMES)
        assert {v['id']:v['rule'] for v in row['bad_variants']} == mutations(row['topic'])
        assert not row['retired_rules'] and not row['retired_variants']
        for rule in row['rules']:
            for anchor in rule['production_tests']:
                assert_anchor(anchor)
        for binding in row['native_bindings']:
            assert_anchor(binding['target'])
        for anchor in row['uses'].values():
            assert_anchor(anchor)


@pytest.mark.parametrize('route', COVERAGE['system_routes'], ids=lambda row: row['id'])
def test_system_route_anchors(route):
    assert route['source_anchors'], route['id']
    for anchor in route['source_anchors']:
        assert_anchor(anchor)
