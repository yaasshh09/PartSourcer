import pytest

from services.matching import (PACKAGING_SUFFIXES, normalize_exact,
                               normalize_packaging, packaging_note,
                               strip_packaging_suffix)


def test_uppercases():
    assert normalize_exact("stm32f103c8t6") == "STM32F103C8T6"


def test_strips_surrounding_whitespace():
    assert normalize_exact("  C8734  ") == "C8734"


def test_removes_internal_whitespace():
    assert normalize_exact("STM32 F103 C8T6") == "STM32F103C8T6"


def test_empty_input_returns_empty():
    assert normalize_exact("   ") == ""


@pytest.mark.parametrize("suffix", PACKAGING_SUFFIXES)
def test_every_allowlisted_suffix_is_stripped(suffix):
    base, removed = strip_packaging_suffix("STM32F103C8T6" + suffix)
    assert (base, removed) == ("STM32F103C8T6", suffix)


def test_no_suffix_leaves_input_untouched():
    assert strip_packaging_suffix("STM32F103C8T6") == ("STM32F103C8T6", None)


def test_strips_at_most_one_suffix():
    # "-CT-TR" must lose only the trailing "-TR", never both.
    assert strip_packaging_suffix("ABC-CT-TR") == ("ABC-CT", "-TR")


def test_longer_suffix_wins_over_shorter_prefix_of_it():
    # "-T&R" must not be mistaken for "-T" plus junk, and "-REEL" must not
    # lose only "-RL"-shaped fragments.
    assert strip_packaging_suffix("ABC-T&R") == ("ABC", "-T&R")
    assert strip_packaging_suffix("ABC-REEL") == ("ABC", "-REEL")


@pytest.mark.parametrize("mpn", [
    "LM317T",        # trailing T is part of the MPN, not a suffix
    "BC547CTA",      # contains CT but not as a suffix
    "MAX232CPE",     # ends in E
    "ATB",           # bare "TB"-looking string with no separator
    "TR",            # the suffix alone is not a part
])
def test_does_not_strip_from_mpns_that_merely_look_suffixed(mpn):
    assert strip_packaging_suffix(mpn) == (mpn, None)


def test_stripping_never_returns_an_empty_base():
    # A part number that is nothing but a suffix must not normalize to "".
    assert strip_packaging_suffix("-TR") == ("-TR", None)


def test_normalize_packaging_composes_with_normalize_exact():
    assert normalize_packaging("  stm32f103c8t6-tr ") == "STM32F103C8T6"


def test_packaging_note_names_the_rule():
    assert packaging_note("-TR") == "tape and reel (-TR)"
    assert packaging_note("-CT") == "cut tape (-CT)"
