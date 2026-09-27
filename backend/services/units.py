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
