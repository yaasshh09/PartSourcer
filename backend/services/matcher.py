"""Equivalent-matcher logic (spec §10, v1 — no ML).

Pure filter/rank helpers here reason over ParametricPart lists with no I/O,
so they are unit-testable without a network. Orchestration (find_equivalent)
is added on top and coordinates the datasource.

Honesty (§5): a candidate is kept only when every checked spec is verified to
satisfy the rule. Missing specs are treated conservatively (rejected when the
original constrains that spec).
"""

import math

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
    orig_rank = dielectric_rank(orig.specs.get("temperature_coefficient"))
    if cap is None:
        return []
    out = []
    for c in pool:
        if c.lcsc == orig.lcsc or c.price_usd >= orig_price:
            continue
        if not _in_stock_ok(c):
            continue
        cc = c.specs.get("capacitance_farads")
        if cc is None or not math.isclose(cc, cap, rel_tol=_REL_TOL):
            continue
        cv = c.specs.get("voltage_rating")
        if volt is not None and (cv is None or cv < volt):   # equal or higher
            continue
        if orig_rank is not None:                            # equal or better
            crank = dielectric_rank(c.specs.get("temperature_coefficient"))
            if crank is None or crank < orig_rank:
                continue
        out.append(c)
    return out


def rank_best(cands: list):
    if not cands:
        return None
    return sorted(cands, key=lambda c: (c.price_usd, -c.stock))[0]
