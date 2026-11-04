"""All retained rule identities, original bad observations and actual native fixtures."""
import pytest
from .contract_cases import TOPICS, cases, expected, module, mutations

RULES = [(topic, name) for topic in TOPICS for name in module(topic).RULE_NAMES]
BAD = [(topic, name, rule) for topic in TOPICS for name, rule in mutations(topic).items()]


@pytest.mark.parametrize('topic', TOPICS)
def test_native_contract(topic):
    module(topic).assert_native_contract()


@pytest.mark.parametrize('topic,name', RULES, ids=[f'{topic}:{name}' for topic, name in RULES])
def test_independent_rule(topic, name):
    contract = module(topic)
    predicate = contract.RULES[contract.RULE_NAMES.index(name)]
    assert all(predicate(expected(topic, case)) for case in cases(topic)), (topic, name)


@pytest.mark.parametrize('topic,mutation,rule', BAD, ids=[f'{topic}:{name}' for topic, name, _rule in BAD])
def test_rejects_original_bad_facts(topic, mutation, rule):
    contract = module(topic)
    predicate = contract.RULES[contract.RULE_NAMES.index(rule)]
    assert any(not predicate(expected(topic, case, mutation)) for case in cases(topic)), (topic, mutation, rule)
