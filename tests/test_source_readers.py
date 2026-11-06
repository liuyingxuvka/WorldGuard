"""Source-reader probes carried over from v1 plus native ownership and compact-duration boundaries."""
import pytest

from worldguard import source_readers as reader

TIMES = [('At 9:00 Lena finds the brass key.', True, [{540}]),
 ('At 7:40 that evening Ivo locks the door.', True, [{1180}]),
 ('At a quarter past seven Ivo unlocks the archive.', True, [{435, 1155}]),
 ('At a quarter to seven Ivo unlocks the archive.', True, [{1125, 405}]),
 ('At half past six in the evening Lea meets Jonas.', False, [{1110}]),
 ('The doors open at 7.15 pm.', False, [{1155}]),
 ('At nine o’clock that night the band stops.', False, [{1260}]),
 ('At 2:00 that night the alarm rings.', False, [{120}]),
 ('At ten to eight the bus leaves.', False, [{1190, 470}]),
 ('At five to eight people arrive.', False, []),
 ('At 4:30 in the afternoon the guide counts again.', False, [{990}]),
 ('At 9:15 the guide counts.', False, [{555, 1275}]),
 ('At 7:40 pm the ferry leaves.', True, [{1180}]),
 ('Allow at least 25 minutes to change.', True, []),
 ('Between 18:10 and 18:20 Mara waits.', True, [{1090}, {1100}]),
 ('It takes one to two hours.', False, [])]

DATES = [('On 3 March 2026 we reach Brig.', [(2026, 3, 3)]),
 ('On October 3, 2026 we take the boat.', [(2026, 10, 3)]),
 ('We take the boat back on Oct. 6.', [(None, 10, 6)]),
 ('Abfahrt am 04.03.2026.', [(2026, 3, 4)]),
 ('We may 4 times try.', []),
 ('Booked from Oct. 3 to Oct. 5.', [(None, 10, 3), (None, 10, 5)]),
 ('On 03/04/2026 we leave.', [])]

# Expected SI readings: the production reader gets every unit factor from PhysicsGuard.
NUMBERS = [
    ("rated for 1.2 tonnes", None, [(1200., 1200.)]),
    ("the crate, 1\u2009350 kg on the note", None, [(1350., 1350.)]),
    ("the crate, 1 350 kg on the note", None, [(1., 1.), (350., 350.)]),
    ("allow at least 25 minutes", None, [(1500., 1500.)]),
    ("three quarters of an hour", None, [(2700., 2700.)]),
    ("an hour and a half", None, [(5400., 5400.)]),
    ("half an hour", None, [(1800., 1800.)]),
    ("1 h 15 min", None, [(4500., 4500.)]),
    ("two hours and ten minutes", None, [(7800., 7800.)]),
    ("uses 30–35 % of the battery", None, [(.30, .35)]),
    ("between 20 and 25 minutes", None, [(1200., 1500.)]),
    ("between 8 and 10 people", None, [(8., 10.)]),
    ("nine pupils and one teacher", None, [(9., 9.), (1., 1.)]),
    ("nine seats besides the driver’s", None, [(9., 9.)]),
    ("höchstens 1.500 kg", None, [(1500., 1500.)]),
    ("höchstens 1.500 kg", ",", [(1500., 1500.)]),
    ("1,250 kg", None, [(1250., 1250.)]),
    ("1,250 kg", ".", [(1250., 1250.)]),
    ("2,5 t", None, [(2500., 2500.)]),
    ("at 18 km/h", None, [(5., 5.)]),
    ("at 18 kilometres per hour", None, [(5., 5.)]),
    ("At 08:00 nine pupils wait", None, [(9., 9.)]),
]


@pytest.mark.parametrize("text,conv24,expected", TIMES)
def test_worded_and_numeric_clock_readings(text, conv24, expected):
    assert [candidates for candidates, _ in reader.time_mentions(text, conv24)] == expected


@pytest.mark.parametrize("text,expected", DATES)
def test_source_date_spellings(text, expected):
    assert reader.date_mentions(text) == expected


@pytest.mark.parametrize("text,decimal,expected", NUMBERS)
def test_quantity_readings_use_the_physicsguard_unit_owner(text, decimal, expected):
    rows = reader.quantities(text, decimal)
    actual = [(round(row['lo'] * row['factor'], 6), round(row['hi'] * row['factor'], 6)) for row in rows]
    assert actual == expected


@pytest.mark.parametrize("text,expected", [
    ("1h15min", 4500.), ("1h20min", 4800.), ("2h 10min", 7800.),
])
def test_compact_duration_is_read_as_one_quantity(text, expected):
    rows = reader.quantities(text)
    assert len(rows) == 1
    assert rows[0]['readable']
    assert rows[0]['lo'] * rows[0]['factor'] == expected


def test_unlisted_unit_is_visible_without_an_invented_factor():
    rows = reader.quantities("7 furlongs")
    assert len(rows) == 1
    assert rows[0]['unit'] == 'furlongs'
    assert not rows[0]['readable']
    assert rows[0]['dim'] is None


def test_optional_unit_owner_is_explicit_and_not_another_table():
    assert reader.unit_info('unknown', lambda _: None) is None
    rows = reader.quantities('2 h', unit_reader=lambda _: None)
    assert rows[0]['unit'] == 'h'
    assert not rows[0]['readable']


def test_file_decimal_inference_and_ambiguity_are_retained():
    assert reader.decimal_evidence('A 14,6 km leg and a 2.700 m climb') == ','
    assert reader.decimal_evidence('2,6 km and 1.25 km') is None
    assert reader.parse_number('1.500', None) == [1500., 1.5]
    assert reader.parse_number('1.500', ',') == [1500.]


def test_normalization_and_abbreviations_preserve_source_meaning():
    assert reader.norm('A “soft\u00adhyphen”\n— here') == 'A "softhyphen" - here'
    text = 'Dr. Ivo arrives on Oct. 6 at 7.15 a.m. before work. He leaves on Oct. 9 at noon.'
    assert len(reader.sentences(text)) == 2
    assert reader.date_mentions(reader.sentences(text)[0]) == [(None, 10, 6)]
    assert reader.time_mentions(reader.sentences(text)[0]) == [({435}, 0)]


def test_worded_and_compact_duration_without_unit_owner_remain_unreadable():
    for text in ('half an hour', '1h15min', 'an hour and a half to two hours'):
        rows = reader.quantities(text, unit_reader=lambda _: None)
        assert rows
        assert not any(row['readable'] for row in rows)


@pytest.mark.parametrize('text,expected', [
    ('The transfer is -3 kg.', (-3., -3.)),
    ('The transfer is −3 kg.', (-3., -3.)),
    ('The transfer is +3 kg.', (3., 3.)),
    ('The transfer is -1,250 kg.', (-1250., -1250.)),
    ('Between -5 and -3 kg.', (-5., -3.)),
    ('The load is 30-35 kg.', (30., 35.)),
])
def test_quantity_signs_are_not_dropped_and_range_separators_stay_separators(text, expected):
    rows = reader.quantities(text)
    assert len(rows) == 1
    assert (rows[0]['lo'] * rows[0]['factor'], rows[0]['hi'] * rows[0]['factor']) == expected
