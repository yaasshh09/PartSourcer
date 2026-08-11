"""MPN normalization and match tiers.

normalize_exact produces mpn_key, the canonical part identity used as a
primary key everywhere. SP1 adds normalize_packaging on top of this.
"""

import re

_WHITESPACE = re.compile(r"\s+")


def normalize_exact(mpn: str) -> str:
    """Uppercase, strip, and remove all whitespace. The result is mpn_key."""
    return _WHITESPACE.sub("", mpn.strip().upper())
