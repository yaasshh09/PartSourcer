"""Shared upstream error vocabulary and parametric mapping.

The v1 PartDataSource stack lived here. It is gone: LcscAdapter speaks
jlcsearch now, and PartService is what routes see. What remains is what other
modules import from here, and nothing else.
"""

from models.parametric import ParametricPart


class UpstreamError(Exception):
    """Upstream failure, categorized so routes can map to HTTP codes."""

    def __init__(self, kind: str, detail: str):
        super().__init__(detail)
        self.kind = kind  # "timeout" | "unavailable" | "quota"


# Shared by all route handlers: maps UpstreamError.kind -> HTTP status.
# "quota" is a distributor rate limit; PartService turns it into a
# quota_exhausted status rather than an HTTP error.
UPSTREAM_STATUS: dict[str, int] = {
    "timeout": 504, "unavailable": 502, "quota": 502}

def priced(value: float | None) -> float | None:
    """A price we are willing to publish, or None.

    Zero is how every upstream spells "no price here": quote-only parts,
    rows with the field missing, money strings we could not parse. A part
    is never actually free, so a 0.0 that survives to the UI reads as one
    and can be named the cheapest offer.
    """
    return value if value is not None and value > 0 else None


_PARAMETRIC_SPEC_FIELDS = {
    "resistors": ("resistance", "tolerance_fraction", "power_watts"),
    "capacitors": ("capacitance_farads", "voltage_rating", "tolerance_fraction",
                   "temperature_coefficient"),
}


def _to_parametric(raw: dict, category: str) -> ParametricPart:
    """Map one parametric row to ParametricPart (see docs/jlcsearch-notes.md)."""
    fields = _PARAMETRIC_SPEC_FIELDS.get(category, ())
    price = priced(raw.get("price1"))
    return ParametricPart(
        lcsc=f"C{raw['lcsc']}",
        mpn=raw.get("mfr") or "",
        package=raw.get("package") or "",
        stock=raw.get("stock") or 0,
        price_usd=None if price is None else round(price, 4),
        in_stock=bool(raw.get("in_stock")),
        is_basic=raw.get("is_basic"),
        is_preferred=raw.get("is_preferred"),
        specs={f: raw.get(f) for f in fields},
    )
