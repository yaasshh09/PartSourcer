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

_PARAMETRIC_SPEC_FIELDS = {
    "resistors": ("resistance", "tolerance_fraction", "power_watts"),
    "capacitors": ("capacitance_farads", "voltage_rating", "tolerance_fraction",
                   "temperature_coefficient"),
}


def _to_parametric(raw: dict, category: str) -> ParametricPart:
    """Map one parametric row to ParametricPart (see docs/jlcsearch-notes.md)."""
    fields = _PARAMETRIC_SPEC_FIELDS.get(category, ())
    return ParametricPart(
        lcsc=f"C{raw['lcsc']}",
        mpn=raw.get("mfr") or "",
        package=raw.get("package") or "",
        stock=raw.get("stock") or 0,
        price_usd=round(raw.get("price1") or 0.0, 4),
        in_stock=bool(raw.get("in_stock")),
        is_basic=raw.get("is_basic"),
        is_preferred=raw.get("is_preferred"),
        specs={f: raw.get(f) for f in fields},
    )
