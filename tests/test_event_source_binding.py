"""Finite original event bindings: existing native worlds, never an alternate evaluator."""
from copy import deepcopy
from pathlib import Path

import pytest

from worldguard.contracts import GuardContract
from worldguard.kernel import run_worldguard
from tests.test_original_sources import world
from tests.test_original_seed_regression import load_seed, run_seed


def reading(tmp_path, text, *, actor='Anna', at='08:30', with_people=(), pointer='ch p1'):
    (tmp_path / 'chapter.md').write_text(text, encoding='utf-8')
    data = world(actor=actor, at=at, pointer=pointer)
    data['inputs']['events'][0]['with'] = list(with_people)
    data['world_model']['relations'] = {'ben': {'at': ['Ben', 'yard']}}
    report = run_worldguard(GuardContract.from_dict(data, base_dir=tmp_path))
    return report, report.checked['source_readings'][0]


def test_second_departure_changes_the_real_arrival_conclusion():
    folder = Path(__file__).parent / 'fixtures/original_sources/batch3/l01_any_match_second_departure'
    mode, data, _ = load_seed(folder)
    before = deepcopy(data)
    report = run_seed(mode, data, folder)
    assert data == before
    assert report.checked['ai_world_status'] == 'PASS'
    assert report.status.value == 'FAIL'
    assert report.checked['source_readings'][0]['edits']['at'] == '7:10'
    assert {row['status'] for row in report.checked['text_worlds']} == {'FAIL'}
    assert 'SOURCE_TIME_DISAGREES' in {gap['code'] for gap in report.gaps}


def test_correct_second_departure_is_sourced_even_though_the_trip_is_late():
    folder = Path(__file__).parent / 'fixtures/original_sources/batch3/l01_any_match_second_departure'
    mode, data, _ = load_seed(folder)
    data['inputs']['events'][0]['at'] = '07:10'
    report = run_seed(mode, data, folder)
    assert report.checked['source_readings'][0]['sourced']
    assert not any(gap['code'] == 'SOURCE_TIME_DISAGREES' for gap in report.gaps)
    assert report.status.value == 'FAIL'  # The native arithmetic still says 07:30 > 07:25.


@pytest.mark.parametrize('text,at,wanted', [
    ('The train leaves at 08:00 and again at 08:30; Anna takes the second one.', '08:30', None),
    ('The bus departs at 08:00 and 08:30. Anna catches the first bus.', '08:30', '8:00'),
    ('Services leave at 08:00 and 08:30; Anna chooses the latter.', '08:30', None),
    ('Trains leave at 08:00, 08:30 and 09:00; Anna boards the third train.', '09:00', None),
    ('At 08:00 Anna opens the door; at 08:30 Ben closes the gate.', '08:30', '8:00'),
])
def test_explicit_order_and_named_event_have_unique_times(tmp_path, text, at, wanted):
    report, row = reading(tmp_path, text, at=at)
    if wanted is None:
        assert row['sourced']
        assert not any(gap['code'].startswith('SOURCE_') for gap in report.gaps)
    else:
        assert row['edits']['at'] == wanted
        assert 'SOURCE_TIME_DISAGREES' in {gap['code'] for gap in report.gaps}


@pytest.mark.parametrize('text', [
    'Anna can leave at 08:00 or 08:30.',
    'Anna takes the second one.',
    'Services leave at 08:00, 08:10, 08:20 and 08:30; Anna takes the second one.',
])
def test_unbound_choices_are_specific_grey_not_invented_times(tmp_path, text):
    _, row = reading(tmp_path, text)
    assert not row['sourced']
    assert 'at' not in row['edits']
    assert any(field == 'time' and colour == '.' and ('bind' in note or 'time' in note)
               for field, colour, note in row['readings'])


@pytest.mark.parametrize('text,actor,expected_actor', [
    ('At 08:30 the keys are handed to Rosa by Viktor.', 'Rosa', 'Viktor'),
    ('At 08:30 the keys were given to Viktor by Rosa.', 'Rosa', None),
    ('At 08:30 Rosa hands the keys to Viktor.', 'Rosa', None),
    ('At 08:30 Rosa passes the keys to Viktor.', 'Viktor', 'Rosa'),
])
def test_transfer_agent_is_not_just_any_participant(tmp_path, text, actor, expected_actor):
    others = ['Viktor' if actor == 'Rosa' else 'Rosa']
    report, row = reading(tmp_path, text, actor=actor, with_people=others)
    if expected_actor:
        assert row['edits']['actor'] == expected_actor
        assert 'SOURCE_ACTOR_DISAGREES' in {gap['code'] for gap in report.gaps}
    else:
        assert row['sourced']
        assert not any(gap['code'] == 'SOURCE_ACTOR_DISAGREES' for gap in report.gaps)


def test_nested_observer_role_remains_ambiguous(tmp_path):
    report, row = reading(tmp_path, 'At 08:30 Rosa watches Viktor open the door.',
                          actor='Viktor', with_people=['Rosa'])
    assert not row['sourced']
    assert not any(gap['code'] == 'SOURCE_ACTOR_DISAGREES' for gap in report.gaps)


def test_clock_list_order_follows_text_across_numeric_spellings(tmp_path):
    _, row = reading(tmp_path, 'The bus leaves at 8:00 am and again at 08:30; Anna takes the first one.')
    assert row['edits']['at'] == '8:00'


def test_an_explicit_event_quote_selects_one_of_the_actors_times(tmp_path):
    _, row = reading(tmp_path, 'At 08:00 Anna opens the gate. At 08:30 Anna opens the door.',
                     pointer='ch p1 "At 08:30 Anna opens the door."')
    assert row['sourced']
    assert not row['edits']


def test_multiple_passive_agents_are_not_silently_reduced_to_the_first(tmp_path):
    report, row = reading(tmp_path, 'At 08:30 the keys are handed to Rosa by Viktor and Anna.',
                          actor='Rosa', with_people=['Viktor', 'Anna'])
    assert not row['sourced']
    assert 'actor' not in row['edits']
    assert any(field == 'actor' and colour == '.' and 'agent' in note for field, colour, note in row['readings'])
    assert not any(gap['code'] == 'SOURCE_ACTOR_DISAGREES' for gap in report.gaps)


@pytest.mark.parametrize('agent_phrase', ["Viktor's assistant", 'Viktor and a neighbour'])
def test_a_known_name_inside_an_unbound_agent_phrase_does_not_select_an_actor(tmp_path, agent_phrase):
    report, row = reading(tmp_path, f'At 08:30 the keys are handed to Rosa by {agent_phrase}.',
                          actor='Rosa', with_people=['Viktor'])
    assert not row['sourced']
    assert 'actor' not in row['edits']
    assert any(field == 'actor' and colour == '.' for field, colour, _ in row['readings'])
    assert not any(gap['code'] == 'SOURCE_ACTOR_DISAGREES' for gap in report.gaps)


def test_original_passive_role_limit_now_rejects_the_swapped_agent():
    folder = Path(__file__).parent / 'fixtures/original_sources/batch3/l03_passive_roles'
    mode, data, _ = load_seed(folder)
    report = run_seed(mode, data, folder)
    assert report.checked['ai_world_status'] == 'PASS'
    assert report.status.value == 'FAIL'
    assert report.checked['source_readings'][0]['edits']['actor'] == 'Viktor'
    assert 'SOURCE_ACTOR_DISAGREES' in {gap['code'] for gap in report.gaps}


@pytest.mark.parametrize('text,at', [
    ('At a quarter past seven Anna opens the door.', '07:15'),
    ('Between 08:00 and 08:30 Anna waits by the door.', '08:15'),
])
def test_an_ambiguous_clock_or_interval_does_not_assert_an_exact_event_time(tmp_path, text, at):
    report, row = reading(tmp_path, text, at=at)
    assert not row['sourced'] and 'at' not in row['edits']
    assert any(field == 'time' and colour == '.' and ('candidates' in note or 'interval' in note) for field, colour, note in row['readings'])
    assert not any(gap['code'] == 'SOURCE_TIME_DISAGREES' for gap in report.gaps)


def test_excluding_both_clock_candidates_is_red_without_guessing_one(tmp_path):
    report, row = reading(tmp_path, 'At a quarter to seven Anna opens the door.', at='07:15')
    assert 'SOURCE_TIME_DISAGREES' in {gap['code'] for gap in report.gaps}
    assert 'at' not in row['edits']  # Neither 06:45 nor 18:45 is an independently selected correction.
