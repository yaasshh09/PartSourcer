"""MPN normalization and match tiers.

normalize_exact produces mpn_key, the canonical part identity used as a
primary key everywhere. SP1 adds normalize_packaging on top of this.
"""

import re

_WHITESPACE = re.compile(r"\s+")


def normalize_exact(mpn: str) -> str:
    """Uppercase, strip, and remove all whitespace. The result is mpn_key."""
    return _WHITESPACE.sub("", mpn.strip().upper())


# Closed allowlist, ordered longest first so a longer suffix is never
# shadowed by a shorter one that is its tail. Extending this list changes
# what the product will call "the same part", so it is deliberately small
# and every entry carries a test.
PACKAGING_SUFFIXES: tuple[str, ...] = (
    "-BULK", "-REEL", "-T&R", "-TR", "/TR", "-RL", "-CT", "-TB",
)

_SUFFIX_NOTES = {
    "-TR": "tape and reel", "/TR": "tape and reel", "-T&R": "tape and reel",
    "-REEL": "full reel", "-RL": "full reel",
    "-CT": "cut tape", "-TB": "tube", "-BULK": "bulk",
}


def strip_packaging_suffix(mpn_key: str) -> tuple[str, str | None]:
    """Remove at most one allowlisted packaging suffix.

    Returns (base, suffix_removed). Never returns an empty base: a string
    that is nothing but a suffix is left alone, because it is not a part.
    """
    for suffix in PACKAGING_SUFFIXES:
        if mpn_key.endswith(suffix) and len(mpn_key) > len(suffix):
            return mpn_key[: -len(suffix)], suffix
    return mpn_key, None


def normalize_packaging(mpn: str) -> str:
    """normalize_exact, then strip one packaging suffix. Tier 2 key."""
    return strip_packaging_suffix(normalize_exact(mpn))[0]


def packaging_note(suffix: str) -> str:
    """Human-readable reason a tier-2 match was made, naming the rule."""
    return f"{_SUFFIX_NOTES.get(suffix, 'different packaging')} ({suffix})"
