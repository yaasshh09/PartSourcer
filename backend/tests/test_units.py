"""parse_si turns what a person types into the plain number upstream needs.

Upstream reads resistance=10k as 10 ohms and returns nothing for
capacitance=100nF, both with HTTP 200, so these are the tests that stop a
browse filter from quietly showing the wrong parts.
"""

import pytest

from services.units import fmt_farads, fmt_ohms, fmt_si, parse_si, spell_query


@pytest.mark.parametrize("text,unit,expected", [
    ("10k", "ohm", 10000),
    ("10K", "ohm", 10000),
    ("4k7", "ohm", 4700),
    ("4.7", "ohm", 4.7),
    ("0", "ohm", 0),
    ("1M", "ohm", 1_000_000),
    ("10kΩ", "ohm", 10000),
    ("10k ohm", "ohm", 10000),
    ("100n", "F", 1e-7),
    ("100nF", "F", 1e-7),
    ("2.2u", "F", 2.2e-6),
    ("2.2µF", "F", 2.2e-6),
    ("3.3", "V", 3.3),
    ("3.3V", "V", 3.3),
    ("500m", "A", 0.5),
    ("500mA", "A", 0.5),
    (".5", "A", 0.5),
])
def test_parses_engineering_notation(text, unit, expected):
    assert parse_si(text, unit) == expected


def test_milli_and_mega_are_different_things():
    assert parse_si("1m", "ohm") == 0.001
    assert parse_si("1M", "ohm") == 1_000_000


@pytest.mark.parametrize("text,unit", [
    ("", "ohm"), ("abc", "ohm"), ("-1", "ohm"), ("inf", "V"), ("nan", "V"),
    ("10V", "ohm"), ("1e-7", "F"), ("4.5k7", "ohm"), ("k7", "ohm"),
    ("100N", "F"), ("1" * 40, "ohm"),
])
def test_rejects_anything_else(text, unit):
    with pytest.raises(ValueError):
        parse_si(text, unit)


def test_the_error_says_what_to_type_and_does_not_echo_a_wall_of_text():
    with pytest.raises(ValueError) as exc:
        parse_si("x" * 5000, "ohm")
    msg = str(exc.value)
    assert "10k" in msg and len(msg) < 200


def test_float_noise_is_rounded_away():
    # 4.7 * 1000 is 4700.000000000001 in binary. Upstream wants 4700.
    assert parse_si("4k7", "ohm") == 4700
    assert parse_si("100n", "F") == 1e-7


@pytest.mark.parametrize("value,unit,expected", [
    (3.3, "V", "3.3 V"), (30, "V", "30 V"), (0.025, "A", "25 mA"),
    (4.2, "A", "4.2 A"), (0, "V", "0 V"), (0.115, "A", "115 mA"),
])
def test_fmt_si(value, unit, expected):
    assert fmt_si(value, unit) == expected


def test_moved_formatters_are_unchanged():
    assert fmt_ohms(10000) == "10 kOhm"
    assert fmt_ohms(4.7) == "4.7 Ohm"
    assert fmt_farads(1e-7) == "100 nF"
    assert fmt_farads(2.2e-6) == "2.2 uF"


@pytest.mark.parametrize("typed,sent", [
    ("0.1uF 0402", "100nF 0402"),
    (".1uf", "100nF"),
    ("100n 0402", "100nF 0402"),
    ("100 nF", "100nF"),
    ("4n7", "4.7nF"),
    ("4700pF", "4.7nF"),
    ("10u 25V", "10uF 25V"),
    ("1000uF", "1000uF"),
    ("100NF", "100nF"),
    # Part numbers and other units are left exactly as typed.
    ("1N4148", "1N4148"),
    ("2N2222", "2N2222"),
    ("4N35", "4N35"),
    ("ATmega328P", "ATmega328P"),
    ("100uH", "100uH"),
    ("STM32F103", "STM32F103"),
    ("10k 0805", "10k 0805"),
])
def test_spell_query_writes_capacitance_the_way_lcsc_lists_it(typed, sent):
    assert spell_query(typed) == sent
