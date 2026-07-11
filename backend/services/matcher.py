"""Equivalent-matcher logic (spec §10, v1 — no ML).

Pure filter/rank helpers here reason over ParametricPart lists with no I/O,
so they are unit-testable without a network. Orchestration (find_equivalent)
is added on top and coordinates the datasource.

Honesty (§5): a candidate is kept only when every checked spec is verified to
satisfy the rule. Missing specs are treated conservatively (rejected when the
original constrains that spec).
"""

import math
from datetime import datetime, timezone

from models.equivalent import EquivalentMatch, EquivalentResponse, OriginalRef
from models.parametric import ParametricPart
from services.datasource import PartDataSource

MATCH_MIN_STOCK = 100          # "healthy buffer", not just > 0 (design D5)
_REL_TOL = 1e-6                # float compare for resistance / capacitance

_DIELECTRIC_RANK = {
    "Y5V": 0, "Z5U": 0,
    "X5R": 1, "X6S": 1,
    "X7R": 2, "X7S": 2,
    "C0G": 3, "NP0": 3, "NP0/C0G": 3, "C0G/NP0": 3,
}


def dielectric_rank(tc: str | None) -> int | None:
    if not tc:
        return None
    return _DIELECTRIC_RANK.get(tc.upper().strip())


def _in_stock_ok(c) -> bool:
    return bool(c.in_stock) and c.stock >= MATCH_MIN_STOCK


def resistor_candidates(orig, pool, orig_price: float) -> list:
    r = orig.specs.get("resistance")
    tol = orig.specs.get("tolerance_fraction")
    power = orig.specs.get("power_watts")
    if r is None:
        return []
    out = []
    for c in pool:
        if c.lcsc == orig.lcsc or c.price_usd >= orig_price:
            continue
        if c.package != orig.package:   # same package is a HARD requirement
            continue
        if not _in_stock_ok(c):
            continue
        cr = c.specs.get("resistance")
        if cr is None or not math.isclose(cr, r, rel_tol=_REL_TOL):
            continue
        ct = c.specs.get("tolerance_fraction")
        if tol is not None and (ct is None or ct > tol):   # equal or tighter
            continue
        cp = c.specs.get("power_watts")
        if power is not None and (cp is None or cp < power):  # equal or higher
            continue
        out.append(c)
    return out


def capacitor_candidates(orig, pool, orig_price: float) -> list:
    cap = orig.specs.get("capacitance_farads")
    volt = orig.specs.get("voltage_rating")
    orig_tc = orig.specs.get("temperature_coefficient")
    orig_rank = dielectric_rank(orig_tc)
    if cap is None:
        return []
    out = []
    for c in pool:
        if c.lcsc == orig.lcsc or c.price_usd >= orig_price:
            continue
        if c.package != orig.package:   # same package is a HARD requirement
            continue
        if not _in_stock_ok(c):
            continue
        cc = c.specs.get("capacitance_farads")
        if cc is None or not math.isclose(cc, cap, rel_tol=_REL_TOL):
            continue
        cv = c.specs.get("voltage_rating")
        if volt is not None and (cv is None or cv < volt):   # equal or higher
            continue
        ctc = c.specs.get("temperature_coefficient")
        if orig_rank is not None:                            # equal or better
            crank = dielectric_rank(ctc)
            if crank is None or crank < orig_rank:
                continue
        elif orig_tc:   # unranked original: only its own exact string (D7)
            if not ctc or ctc.upper().strip() != orig_tc.upper().strip():
                continue
        out.append(c)
    return out


def rank_best(cands: list):
    if not cands:
        return None
    return sorted(cands, key=lambda c: (c.price_usd, -c.stock))[0]


_NO_TYPE_REASON = ("Equivalent matching in v1 covers resistors and capacitors; "
                   "this part is a different component type (or its specs could "
                   "not be identified), so no verified drop-in equivalent can be "
                   "offered.")
_NO_MATCH_REASON = ("No cheaper in-stock drop-in was found for this part in v1 "
                    "(same package and specs, healthy stock, lower price).")


def _find(parts: list[ParametricPart], lcsc: str) -> ParametricPart | None:
    for p in parts:
        if p.lcsc == lcsc:
            return p
    return None


def _fmt_ohms(r: float) -> str:
    if r >= 1e6:
        return f"{r / 1e6:g} MOhm"
    if r >= 1e3:
        return f"{r / 1e3:g} kOhm"
    return f"{r:g} Ohm"


def _fmt_farads(f: float) -> str:
    if f >= 1e-6:
        return f"{f * 1e6:g} uF"
    if f >= 1e-9:
        return f"{f * 1e9:g} nF"
    return f"{f * 1e12:g} pF"


def _percent_cheaper(orig_price: float, new_price: float) -> int:
    if orig_price <= 0:
        return 0
    return int(round((1 - new_price / orig_price) * 100))


def _resistor_reason(orig, best, pkg, orig_price) -> str:
    r = _fmt_ohms(orig.specs.get("resistance"))
    tol = best.specs.get("tolerance_fraction")
    tol_s = f", ±{tol * 100:g}%" if tol is not None else ""
    pw = best.specs.get("power_watts")
    pw_s = f", {pw:g} mW" if pw is not None else ""   # field is milliwatts (notes)
    pct = _percent_cheaper(orig_price, best.price_usd)
    return (f"Same {pkg} package, {r}{tol_s}{pw_s}, "
            f"{best.stock:,} in stock — {pct}% cheaper")


def _capacitor_reason(orig, best, pkg, orig_price) -> str:
    cap = _fmt_farads(orig.specs.get("capacitance_farads"))
    v = best.specs.get("voltage_rating")
    v_s = f", {v:g} V" if v is not None else ""
    tc = best.specs.get("temperature_coefficient")
    tc_s = f", {tc}" if tc else ""
    pct = _percent_cheaper(orig_price, best.price_usd)
    return (f"Same {pkg} package, {cap}{v_s}{tc_s}, "
            f"{best.stock:,} in stock — {pct}% cheaper")


async def find_equivalent(ds: PartDataSource,
                          lcsc_code: str) -> EquivalentResponse | None:
    original = await ds.get_part(lcsc_code)
    if original is None:
        return None
    now = datetime.now(timezone.utc)
    orig_ref = OriginalRef(lcsc=original.lcsc, mpn=original.mpn,
                           package=original.package,
                           price_usd=original.price_usd, stock=original.stock)

    def _null(reason: str) -> EquivalentResponse:
        return EquivalentResponse(original=orig_ref, equivalent=None,
                                  reason=reason, as_of=now)

    def _match(best: ParametricPart, reason: str) -> EquivalentResponse:
        return EquivalentResponse(
            original=orig_ref,
            equivalent=EquivalentMatch(
                lcsc=best.lcsc, mpn=best.mpn, price_usd=best.price_usd,
                stock=best.stock, package=best.package, match_reason=reason,
                percent_cheaper=_percent_cheaper(original.price_usd,
                                                 best.price_usd)),
            reason=None, as_of=now)

    if not original.package:
        # Empty package = specs could not be reliably identified; an unfiltered
        # upstream query could otherwise match a different-package candidate.
        return _null(_NO_TYPE_REASON)

    # Classify as resistor?
    resistors = await ds.list_parametric("resistors", original.package)
    orig_r = _find(resistors, original.lcsc)
    if orig_r is not None:
        pool = await ds.list_parametric(
            "resistors", original.package,
            resistance_ohms=orig_r.specs.get("resistance"))
        best = rank_best(resistor_candidates(orig_r, pool, original.price_usd))
        if best is None:
            return _null(_NO_MATCH_REASON)
        return _match(best, _resistor_reason(orig_r, best, original.package,
                                             original.price_usd))

    # Classify as capacitor?
    caps = await ds.list_parametric("capacitors", original.package)
    orig_c = _find(caps, original.lcsc)
    if orig_c is not None:
        best = rank_best(capacitor_candidates(orig_c, caps, original.price_usd))
        if best is None:
            return _null(_NO_MATCH_REASON)
        return _match(best, _capacitor_reason(orig_c, best, original.package,
                                              original.price_usd))

    return _null(_NO_TYPE_REASON)
