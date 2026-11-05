"""A typo cannot silently remove a check from a contract."""
import json
from pathlib import Path

import pytest

from worldguard.cli import main
from worldguard.contracts import GuardContract
from worldguard.errors import WorldInputError
from worldguard.io import load_mapping


def test_unknown_contract_top_level_key_is_named():
    with pytest.raises(WorldInputError, match='unknown fields: variant'):
        GuardContract.from_dict({'variant': [{'id': 'missing-check'}]})


def test_original_third_batch_typo_is_invalid_input(tmp_path, capsys):
    root = Path(__file__).parent / 'fixtures/original_sources/batch3/x11_unknown_toplevel_field'
    meta = load_mapping(root / 'seed.yaml')
    data = load_mapping(root / meta['world'])
    target = tmp_path / 'bad.json'
    target.write_text(json.dumps(data))
    assert main(['check', '--contract', str(target), '--json']) == 2
    output = json.loads(capsys.readouterr().out)
    assert output['error']['code'] == 'WORLDGUARD_INPUT_INVALID'
    assert 'variant' in output['error']['message']


def test_source_configuration_is_still_accepted():
    contract = GuardContract.from_dict({'claim': {'requested_semantics': ['event']}, 'texts': {'note': 'note.md'}, 'aliases': {'Lena': ['L']},
                                       'tables': {}, 'decimal': {'note': ','}, 'values': {}})
    assert contract.to_dict()['texts'] == {'note': 'note.md'}
