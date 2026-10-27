"""Engineering numbers in and out, so the unit traps live in one place.

Upstream reads `resistance=10k` as 10 ohms and returns nothing at all for
`capacitance=100nF`, both with HTTP 200. Everything a person types goes
through parse_si, and what goes upstream is a plain number.
"""

import re

_PREFIX = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "µ": 1e-6, "m": 1e-3,
           "": 1.0, "k": 1e3, "K": 1e3, "M": 1e6}

# 4k7 means 4.7k: the prefix letter stands in for the decimal point.
_NUMBER = re.compile(r"^(\d+(?:\.\d+)?|\.\d+)([pnuµmkKM]?)(\d*)$")

# unit -> (what it is, suffixes a person might type, an example to suggest)
_UNITS = {
    "ohm": ("resistance", ("ohms", "ohm", "Ω"), "10k or 4k7"),
    "F": ("capacitance", ("f",), "100n or 2.2u"),
    "V": ("voltage", ("v",), "3.3 or 30V"),
    "A": ("current", ("a",), "2 or 500m"),
}

MAX_LEN = 24


def parse_si(text: str, unit: str) -> float:
    what, suffixes, example = _UNITS[unit]
    shown = text.strip()[:MAX_LEN]
    error = ValueError(f"'{shown}' is not a {what}. Try something like {example}.")
    if len(text) > MAX_LEN:
        raise error
    s = text.strip().replace(" ", "")
    for suffix in suffixes:
        if len(s) > len(suffix) and s.lower().endswith(suffix.lower()):
            s = s[:-len(suffix)]
            break
    m = _NUMBER.match(s)
    if m is None:
        raise error
    whole, prefix, tail = m.groups()
    if tail and (not prefix or "." in whole):
        raise error
    number = float(f"{whole}.{tail}") if tail else float(whole)
    # Nine significant digits drops binary noise (4.7 * 1000 is
    # 4700.000000000001) without touching any value a person could type.
    return float(f"{number * _PREFIX[prefix]:.9g}")


_SCALE = ((1e6, "M"), (1e3, "k"), (1.0, ""), (1e-3, "m"), (1e-6, "u"),
          (1e-9, "n"), (1e-12, "p"))


def fmt_si(value: float, unit: str) -> str:
    for scale, prefix in _SCALE:
        if abs(value) >= scale:
            return f"{value / scale:g} {prefix}{unit}"
    return f"{value:g} {unit}"


def fmt_ohms(r: float) -> str:
    if r >= 1e6:
        return f"{r / 1e6:g} MOhm"
    if r >= 1e3:
        return f"{r / 1e3:g} kOhm"
    return f"{r:g} Ohm"


def fmt_farads(f: float) -> str:
    if f >= 1e-6:
        return f"{f * 1e6:g} uF"
    if f >= 1e-9:
        return f"{f * 1e9:g} nF"
    return f"{f * 1e12:g} pF"


# A capacitance as people type it: 0.1uF, 100 nF, 0.1u, 4n7. A bare prefix
# with no F counts only when nothing but one digit follows it, so 1N4148,
# 2N2222 and ATmega328P are never read as values.
_CAP_TYPED = re.compile(
    r"(?<![\w.])(?:(\d+(?:\.\d+)?|\.\d+)\s?([pnuµ])[fF]|(\d+(?:\.\d+)?|\.\d+)([pnuµ])(\d?))(?![\w.])",
    re.IGNORECASE)


def _cap_spelling(m: re.Match) -> str:
    if m.group(1) is not None:
        typed = m.group(1) + m.group(2).lower()
    else:
        # A bare whole number like 100n already substring-matches 100nF
        # upstream, and adding the F would drop 100nH inductors from the
        # results, so only the forms upstream gets wrong are rewritten.
        if "." not in m.group(3) and not m.group(5):
            return m.group(0)
        typed = m.group(3) + m.group(4).lower() + m.group(5)
    try:
        farads = parse_si(typed, "F")
    except ValueError:
        return m.group(0)
    return fmt_farads(farads).replace(" ", "")


# A value as LCSC writes it in a description: 10kΩ, 100mΩ, 4.7uF, 1µF.
# Case matters here (mΩ is milli, MΩ is mega), and one right after a ± is a
# tolerance, not the part's value.
_DESC_VALUE = {
    "ohm": re.compile(r"(?<![\w.±])(\d+(?:\.\d+)?)([mkM]?)Ω"),
    "F": re.compile(r"(?<![\w.±])(\d+(?:\.\d+)?)([pnuµm]?)F(?![a-zA-Z])"),
}


def value_in_description(description: str, unit: str) -> float | None:
    """The one value a description names in this unit, or None.

    Two different values means there is no telling which is the part's, so
    that is None too rather than a guess.
    """
    found = {float(f"{float(n) * _PREFIX[p]:.9g}")
             for n, p in _DESC_VALUE[unit].findall(description or "")}
    return found.pop() if len(found) == 1 else None


def spell_query(query: str) -> str:
    """Rewrite capacitances in a search the way LCSC lists them.

    Upstream splits a query on anything that is not a letter or digit and
    substring-matches each piece, so 0.1uF becomes "1uf" and finds 1uF and
    10uF parts. LCSC writes the same part as 100nF, so that is what is sent.
    Resistances are left alone: 4k7 already appears in many MPNs, and 4.7k
    would split into a looser "7k".
    """
    return _CAP_TYPED.sub(_cap_spelling, query)
