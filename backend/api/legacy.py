"""Turning an old-style LCSC code into the canonical MPN the app keys on.

Both /part and /equivalent accept links minted before the app moved to MPN
keys, so the resolution lives here rather than in whichever route happened to
grow it first.

Shape is not proof: the Toshiba 2SC1815 is widely catalogued as C1815, so a
code-shaped string that does not resolve to a SKU falls through to being
treated as an MPN rather than 404ing a real part.
"""

import re

from cache.cached_part_service import CachedPartService
from services.adapters.lcsc import LcscAdapter
from services.matching import normalize_exact

LEGACY_CODE = re.compile(r"C\d+")


async def canonical_mpn(code: str, cached: CachedPartService,
                        lcsc: LcscAdapter) -> str | None:
    """An LCSC code to its canonical MPN, cache first then upstream.

    The cache only knows codes it has already merged, so the upstream call is
    what makes a legacy link work against a cold backend rather than only
    after someone happens to have searched the part.
    """
    part_key = await cached.resolve_sku("lcsc", code)
    if part_key is not None:
        return part_key
    listing = await lcsc.lookup_sku(code)
    return normalize_exact(listing.mpn) if listing is not None else None
