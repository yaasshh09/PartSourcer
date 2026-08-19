"""Equivalent-matcher logic (spec §10, v1, no ML).

Pure filter/rank helpers here reason over ParametricPart lists with no I/O,
so they are unit-testable without a network. Orchestration (find_equivalent)
is added on top and coordinates the datasource.

Honesty (§5): a candidate is kept only when every checked spec is verified to
satisfy the rule. Missing specs are treated conservatively (rejected when the
original constrains that spec).
"""

import asyncio
import math
from datetime import datetime, timezone
from typing import Protocol

from models.equivalent import EquivalentMatch, EquivalentResponse, OriginalRef
from models.parametric import ParametricPart
from models.part import PartDetail
from services.matching import normalize_exact


class MatcherSource(Protocol):
    """What the matcher needs from LCSC, named rather than imported.

    LcscMatcherSource is the only implementation. Stating the contract here
    keeps this module free of a dependency on the shim that satisfies it.

    The three reads are deliberately not interchangeable, because upstream
    hands back different numbers for the same part depending on how it is
    asked (see the price-basis note on find_equivalent):

    - get_part resolves a code to an identity. Its price is never published.
    - list_parametric supplies specs and the ranking basis. Its prices are
      comparable with each other and with nothing else.
    - canonical_part is the one read whose price and stock reach a user, and
      it is the same read the search and detail pages go through.
    """

    async def get_part(self, lcsc_code: str,
                       refresh: bool = False) -> PartDetail | None: ...

    async def canonical_part(self, mpn: str,
                             lcsc_code: str) -> PartDetail | None: ...

    async def list_parametric(self, category: str, package: str,
                              resistance_ohms: float | None = None
                              ) -> list[ParametricPart]: ...

MATCH_MIN_STOCK = 100          # "healthy buffer", not just > 0 (design D5)
_REL_TOL = 1e-6                # float compare for resistance / capacitance
VERIFY_LIMIT = 3               # candidates re-priced before publishing a claim

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


def _in_stock_ok(c: ParametricPart) -> bool:
    return bool(c.in_stock) and c.stock >= MATCH_MIN_STOCK


def _viable(c: ParametricPart, orig: ParametricPart, orig_price: float) -> bool:
    """The gate every candidate clears before its own specs are read.

    Same package is a HARD requirement. It lives here rather than once per
    component type so that a third type added later cannot quietly ship
    without it. A candidate upstream published no price for cannot be shown
    to be cheaper than anything, so it is not a candidate.
    """
    return (c.lcsc != orig.lcsc
            and c.price_usd is not None
            and c.price_usd < orig_price
            and c.package == orig.package
            and _in_stock_ok(c))


def resistor_candidates(orig: ParametricPart, pool: list[ParametricPart],
                        orig_price: float) -> list[ParametricPart]:
    r = orig.specs.get("resistance")
    tol = orig.specs.get("tolerance_fraction")
    power = orig.specs.get("power_watts")
    if r is None:
        return []
    out = []
    for c in pool:
        if not _viable(c, orig, orig_price):
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


def capacitor_candidates(orig: ParametricPart, pool: list[ParametricPart],
                         orig_price: float) -> list[ParametricPart]:
    cap = orig.specs.get("capacitance_farads")
    volt = orig.specs.get("voltage_rating")
    orig_tc = orig.specs.get("temperature_coefficient")
    orig_rank = dielectric_rank(orig_tc)
    if cap is None:
        return []
    out = []
    for c in pool:
        if not _viable(c, orig, orig_price):
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


def rank_candidates(cands: list[ParametricPart]) -> list[ParametricPart]:
    """Cheapest first, then deepest stock.

    Every price here came from one parametric response, so they are
    comparable with each other. That makes this a fair running order, not a
    publishable result: the winner still has to be re-priced before its
    saving is claimed.
    """
    return sorted(cands, key=lambda c: (c.price_usd, -c.stock))


def rank_best(cands: list[ParametricPart]) -> ParametricPart | None:
    ranked = rank_candidates(cands)
    return ranked[0] if ranked else None


_NO_TYPE_REASON = ("Equivalent matching in v1 covers resistors and capacitors; "
                   "this part is a different component type (or its specs could "
                   "not be identified), so no verified drop-in equivalent can be "
                   "offered.")
_NO_MATCH_REASON = ("No cheaper in-stock drop-in was found for this part in v1 "
                    "(same package and specs, healthy stock, lower price).")
_NO_PRICE_REASON = ("This part has no published price upstream, so there is "
                    "nothing for a cheaper equivalent to be cheaper than.")
_TRIVIAL_SAVING_REASON = ("The closest drop-in for this part costs almost "
                          "exactly what it does, so there is nothing worth "
                          "swapping for.")
_UNVERIFIED_REASON = ("Parts matching this one's specs were found, but "
                      "re-reading their prices and stock the same way this "
                      "page reads them did not confirm any is both cheaper "
                      "and well stocked, so none is offered as a swap.")


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


def _resistor_reason(orig, best, pkg, pct, stock) -> str:
    r = _fmt_ohms(orig.specs.get("resistance"))
    tol = best.specs.get("tolerance_fraction")
    tol_s = f", ±{tol * 100:g}%" if tol is not None else ""
    pw = best.specs.get("power_watts")
    pw_s = f", {pw:g} mW" if pw is not None else ""   # field is milliwatts (notes)
    return (f"Same {pkg} package, {r}{tol_s}{pw_s}, "
            f"{stock:,} in stock, {pct}% cheaper")


def _capacitor_reason(orig, best, pkg, pct, stock) -> str:
    cap = _fmt_farads(orig.specs.get("capacitance_farads"))
    v = best.specs.get("voltage_rating")
    v_s = f", {v:g} V" if v is not None else ""
    tc = best.specs.get("temperature_coefficient")
    tc_s = f", {tc}" if tc else ""
    return (f"Same {pkg} package, {cap}{v_s}{tc_s}, "
            f"{stock:,} in stock, {pct}% cheaper")


async def _verify(ds: MatcherSource, ranked: list[ParametricPart],
                  orig_price: float) -> tuple[ParametricPart, float, int] | None:
    """Re-price the leading candidates on the published basis.

    Ranking happens on parametric prices; those are comparable with each
    other but not with anything a user sees elsewhere in the app. So before
    a saving is claimed, the top few candidates are read back through
    canonical_part and held to both gates again on those numbers: genuinely
    cheaper than the original, and genuinely well stocked. Whatever survives
    is described with the very numbers that were checked.

    Only VERIFY_LIMIT candidates are re-read. Measured against live upstream
    data, going deeper than three recovered no further matches.

    All of them are read at once. Every one is needed anyway, since the
    cheapest confirmed candidate wins rather than the first, so running them
    together costs upstream the same requests and saves the user two round
    trips on the slowest route in the app.
    """
    short = ranked[:VERIFY_LIMIT]
    parts = await asyncio.gather(*(ds.canonical_part(c.mpn, c.lcsc)
                                   for c in short))
    best: tuple[ParametricPart, float, int] | None = None
    for cand, part in zip(short, parts):
        if part is None or part.price_usd is None:
            continue
        if part.price_usd >= orig_price or part.stock < MATCH_MIN_STOCK:
            continue
        if best is None or part.price_usd < best[1]:
            best = (cand, part.price_usd, part.stock)
    return best


async def find_equivalent(ds: MatcherSource,
                          lcsc_code: str) -> EquivalentResponse | None:
    """One cheaper drop-in, or an honest null.

    Price basis is the load-bearing detail here. Upstream returns different
    prices and stock for the same part depending on which endpoint is asked
    and how, and the gap is not small: measured over 24 real parts the
    parametric price ran a median 1.5x and up to 6x below the price the
    search path reports for the same code, in the same minute.

    So a price only ever gets compared with another price fetched the same
    way. Parametric data picks and orders candidates; canonical_part, the
    read behind the search and detail pages, supplies every number that is
    published or compared. That keeps the card's figures equal to the ones
    shown for the same part elsewhere, and keeps the percentage defensible.
    """
    original = await ds.get_part(lcsc_code)
    if original is None:
        return None
    now = datetime.now(timezone.utc)

    # get_part resolved the code to an identity. Its price came off a
    # different query shape than the rest of the app reads, so it is dropped
    # here and the publishable numbers are fetched on the canonical path.
    canon = await ds.canonical_part(original.mpn, original.lcsc)
    orig_price = None if canon is None else canon.price_usd
    orig_stock = original.stock if canon is None else canon.stock

    orig_ref = OriginalRef(mpn_key=normalize_exact(original.mpn),
                           lcsc=original.lcsc, distributor="lcsc",
                           mpn=original.mpn, package=original.package,
                           price_usd=orig_price, stock=orig_stock)

    def _null(reason: str) -> EquivalentResponse:
        return EquivalentResponse(original=orig_ref, equivalent=None,
                                  reason=reason, as_of=now)

    async def _publish(cands: list[ParametricPart], orig_row: ParametricPart,
                       reason_fn) -> EquivalentResponse:
        ranked = rank_candidates(cands)
        if not ranked:
            return _null(_NO_MATCH_REASON)
        verified = await _verify(ds, ranked, orig_price)
        if verified is None:
            return _null(_UNVERIFIED_REASON)
        cand, price, stock = verified
        pct = _percent_cheaper(orig_price, price)
        if pct < 1:
            # Cheaper by less than half a rounded percent. True, and useless:
            # the card would shout "CHEAPER EQUIVALENT FOUND" over a 0% badge
            # and two identical prices.
            return _null(_TRIVIAL_SAVING_REASON)
        return EquivalentResponse(
            original=orig_ref,
            equivalent=EquivalentMatch(
                mpn_key=normalize_exact(cand.mpn),
                lcsc=cand.lcsc, mpn=cand.mpn, price_usd=price,
                stock=stock, package=cand.package,
                match_reason=reason_fn(orig_row, cand, original.package,
                                       pct, stock),
                percent_cheaper=pct),
            reason=None, as_of=now)

    if not original.package:
        # Empty package = specs could not be reliably identified; an unfiltered
        # upstream query could otherwise match a different-package candidate.
        return _null(_NO_TYPE_REASON)

    if orig_price is None:
        # Every candidate gate is "cheaper than the original". With no
        # original price there is no comparison to run, and treating the
        # gap as 0.0 would silently reject every real part instead.
        return _null(_NO_PRICE_REASON)

    # Classify as resistor?
    resistors = await ds.list_parametric("resistors", original.package)
    orig_r = _find(resistors, original.lcsc)
    if orig_r is not None:
        if (orig_r.specs.get("resistance") is None
                or orig_r.specs.get("tolerance_fraction") is None
                or orig_r.specs.get("power_watts") is None):
            # Any unreadable key spec on the ORIGINAL means a drop-in can't
            # be verified: honest null, never a guess (strict, confirmed).
            return _null(_NO_TYPE_REASON)
        if orig_r.price_usd is None:
            # The pool is ranked against the original's own parametric price.
            # Without it there is no like-for-like basis to order candidates.
            return _null(_NO_PRICE_REASON)
        pool = await ds.list_parametric(
            "resistors", original.package,
            resistance_ohms=orig_r.specs.get("resistance"))
        return await _publish(
            resistor_candidates(orig_r, pool, orig_r.price_usd),
            orig_r, _resistor_reason)

    # Classify as capacitor?
    caps = await ds.list_parametric("capacitors", original.package)
    orig_c = _find(caps, original.lcsc)
    if orig_c is not None:
        if (orig_c.specs.get("capacitance_farads") is None
                or orig_c.specs.get("voltage_rating") is None
                or not orig_c.specs.get("temperature_coefficient")):
            # Same strict rule for capacitors.
            return _null(_NO_TYPE_REASON)
        if orig_c.price_usd is None:
            return _null(_NO_PRICE_REASON)
        return await _publish(
            capacitor_candidates(orig_c, caps, orig_c.price_usd),
            orig_c, _capacitor_reason)

    return _null(_NO_TYPE_REASON)
