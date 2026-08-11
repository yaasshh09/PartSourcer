from services.matching import normalize_exact


def test_uppercases():
    assert normalize_exact("stm32f103c8t6") == "STM32F103C8T6"


def test_strips_surrounding_whitespace():
    assert normalize_exact("  C8734  ") == "C8734"


def test_removes_internal_whitespace():
    assert normalize_exact("STM32 F103 C8T6") == "STM32F103C8T6"


def test_empty_input_returns_empty():
    assert normalize_exact("   ") == ""
