import pytest
from datetime import datetime, timezone

from models.parametric import ParametricPart
from models.part import PartDetail
from services.datasource import PartDataSource
from services.matcher import (MATCH_MIN_STOCK, dielectric_rank,
                               resistor_candidates, capacitor_candidates,
                               rank_best, find_equivalent)


def rp(lcsc, price, stock, resistance=10000, tol=0.01, power=100, in_stock=True):
    return ParametricPart(lcsc=lcsc, mpn=f"R-{lcsc}", package="0603", stock=stock,
                          price_usd=price, in_stock=in_stock, is_basic=None,
                          is_preferred=None,
                          specs={"resistance": resistance, "tolerance_fraction": tol,
                                 "power_watts": power})


def cp(lcsc, price, stock, cap=1e-07, volt=16, tol=0.1, tc="X7R", in_stock=True):
    return ParametricPart(lcsc=lcsc, mpn=f"C-{lcsc}", package="0402", stock=stock,
                          price_usd=price, in_stock=in_stock, is_basic=None,
                          is_preferred=None,
                          specs={"capacitance_farads": cap, "voltage_rating": volt,
                                 "tolerance_fraction": tol,
                                 "temperature_coefficient": tc})


ORIG_R = rp("C100", price=0.0010, stock=1000)
ORIG_C = cp("C200", price=0.0030, stock=1000)


def test_dielectric_rank_order():
    assert dielectric_rank("Y5V") < dielectric_rank("X5R") < \
        dielectric_rank("X7R") < dielectric_rank("C0G")
    assert dielectric_rank("np0") == dielectric_rank("C0G")
    assert dielectric_rank("weird") is None
    assert dielectric_rank(None) is None


def test_resistor_cheaper_exact_match_qualifies():
    pool = [rp("C1", price=0.0005, stock=5000)]
    out = resistor_candidates(ORIG_R, pool, ORIG_R.price_usd)
    assert [c.lcsc for c in out] == ["C1"]


def test_resistor_excludes_original_and_pricier():
    pool = [rp("C100", price=0.0005, stock=5000),   # the original itself
            rp("C2", price=0.0020, stock=5000)]      # pricier
    assert resistor_candidates(ORIG_R, pool, ORIG_R.price_usd) == []


def test_resistor_rejects_wider_tolerance_and_lower_power():
    pool = [rp("C3", price=0.0005, stock=5000, tol=0.05),   # wider tolerance
            rp("C4", price=0.0005, stock=5000, power=50)]    # lower power
    assert resistor_candidates(ORIG_R, pool, ORIG_R.price_usd) == []


def test_resistor_rejects_wrong_resistance_and_low_stock():
    pool = [rp("C5", price=0.0005, stock=5000, resistance=22000),  # wrong value
            rp("C6", price=0.0005, stock=50),                       # below buffer
            rp("C7", price=0.0005, stock=5000, in_stock=False)]     # not in stock
    assert resistor_candidates(ORIG_R, pool, ORIG_R.price_usd) == []


def test_resistor_accepts_tighter_tolerance_and_higher_power():
    pool = [rp("C8", price=0.0005, stock=5000, tol=0.001, power=250)]
    assert [c.lcsc for c in resistor_candidates(ORIG_R, pool, ORIG_R.price_usd)] == ["C8"]


def test_resistor_rejects_candidate_with_different_package():
    pool = [rp("C1", price=0.0005, stock=5000).model_copy(update={"package": "0402"})]
    assert resistor_candidates(ORIG_R, pool, ORIG_R.price_usd) == []


def test_stock_buffer_boundary():
    below = [rp("C9", price=0.0005, stock=MATCH_MIN_STOCK - 1)]
    at = [rp("C10", price=0.0005, stock=MATCH_MIN_STOCK)]
    assert resistor_candidates(ORIG_R, below, ORIG_R.price_usd) == []
    assert len(resistor_candidates(ORIG_R, at, ORIG_R.price_usd)) == 1


def test_capacitor_higher_voltage_better_dielectric_qualifies():
    pool = [cp("C1", price=0.0010, stock=5000, volt=25, tc="C0G")]
    assert [c.lcsc for c in capacitor_candidates(ORIG_C, pool, ORIG_C.price_usd)] == ["C1"]


def test_capacitor_rejects_lower_voltage_worse_dielectric_wrong_cap():
    pool = [cp("C2", price=0.0010, stock=5000, volt=10),          # lower voltage
            cp("C3", price=0.0010, stock=5000, tc="Y5V"),          # worse dielectric
            cp("C4", price=0.0010, stock=5000, cap=2.2e-07)]       # wrong capacitance
    assert capacitor_candidates(ORIG_C, pool, ORIG_C.price_usd) == []


def test_capacitor_rejects_candidate_with_different_package():
    pool = [cp("C1", price=0.0010, stock=5000).model_copy(update={"package": "0603"})]
    assert capacitor_candidates(ORIG_C, pool, ORIG_C.price_usd) == []


def test_capacitor_exact_cap_absorbs_fp_noise():
    pool = [cp("C5", price=0.0010, stock=5000, cap=1.0000000000000001e-07)]
    assert len(capacitor_candidates(ORIG_C, pool, ORIG_C.price_usd)) == 1


def test_capacitor_unranked_dielectric_only_matches_own_exact_string():
    orig = cp("C200", price=0.0030, stock=1000, tc="X8R")
    worse = cp("C6", price=0.0010, stock=5000, tc="Y5V")     # ranked but "worse"
    same = cp("C7", price=0.0010, stock=5000, tc="x8r")      # own string, any case
    assert capacitor_candidates(orig, [worse], orig.price_usd) == []
    assert [c.lcsc for c in capacitor_candidates(orig, [same], orig.price_usd)] == ["C7"]


def test_rank_best_price_then_stock():
    a = rp("A", price=0.0005, stock=1000)
    b = rp("B", price=0.0004, stock=10)
    c = rp("C", price=0.0004, stock=9000)
    assert rank_best([a, b, c]).lcsc == "C"   # cheapest, then highest stock
    assert rank_best([]) is None


def test_resistor_rejects_candidate_missing_tolerance():
    pool = [rp("C1", price=0.0005, stock=5000, tol=None)]
    assert resistor_candidates(ORIG_R, pool, ORIG_R.price_usd) == []


def test_resistor_rejects_candidate_missing_power():
    pool = [rp("C1", price=0.0005, stock=5000, power=None)]
    assert resistor_candidates(ORIG_R, pool, ORIG_R.price_usd) == []


def test_resistor_rejects_candidate_missing_resistance():
    pool = [rp("C1", price=0.0005, stock=5000, resistance=None)]
    assert resistor_candidates(ORIG_R, pool, ORIG_R.price_usd) == []


def test_resistor_original_missing_resistance_yields_nothing():
    orig = rp("C100", price=0.0010, stock=1000, resistance=None)
    pool = [rp("C1", price=0.0005, stock=5000)]
    assert resistor_candidates(orig, pool, orig.price_usd) == []


def test_capacitor_rejects_candidate_missing_voltage():
    pool = [cp("C1", price=0.0010, stock=5000, volt=None)]
    assert capacitor_candidates(ORIG_C, pool, ORIG_C.price_usd) == []


def test_capacitor_rejects_candidate_missing_dielectric():
    pool = [cp("C1", price=0.0010, stock=5000, tc=None)]
    assert capacitor_candidates(ORIG_C, pool, ORIG_C.price_usd) == []


def test_capacitor_rejects_candidate_missing_capacitance():
    pool = [cp("C1", price=0.0010, stock=5000, cap=None)]
    assert capacitor_candidates(ORIG_C, pool, ORIG_C.price_usd) == []


def test_capacitor_original_missing_capacitance_yields_nothing():
    orig = cp("C200", price=0.0030, stock=1000, cap=None)
    pool = [cp("C1", price=0.0010, stock=5000)]
    assert capacitor_candidates(orig, pool, orig.price_usd) == []


class FakeDS(PartDataSource):
    def __init__(self, detail, parametric):
        self._detail = detail
        self._parametric = parametric   # dict: (category, package) -> list[ParametricPart]
        self.calls = []

    async def search(self, query, page, refresh=False):
        return []

    async def get_part(self, lcsc_code, refresh=False):
        return self._detail

    async def list_parametric(self, category, package, resistance_ohms=None):
        self.calls.append((category, package, resistance_ohms))
        return list(self._parametric.get((category, package), []))


def detail(lcsc="C100", package="0603", price=0.0010, stock=1000, mpn="R-orig"):
    return PartDetail(lcsc=lcsc, mpn=mpn, brand=None, package=package,
                      description="", stock=stock, price_usd=price,
                      price_breaks=None, stock_breakdown=None, is_basic=None,
                      is_preferred=None, datasheet_url=None,
                      as_of=datetime.now(timezone.utc))


@pytest.mark.anyio
async def test_find_equivalent_resistor_returns_cheaper_match():
    orig_row = rp("C100", price=0.0010, stock=1000)
    cheaper = rp("C1", price=0.0004, stock=900000)
    ds = FakeDS(detail("C100", "0603", 0.0010, 1000),
                {("resistors", "0603"): [orig_row, cheaper]})
    resp = await find_equivalent(ds, "C100")
    assert resp.equivalent is not None
    assert resp.equivalent.lcsc == "C1"
    assert resp.equivalent.percent_cheaper == 60   # (1 - 0.0004/0.0010)*100
    assert resp.reason is None
    assert "0603" in resp.equivalent.match_reason


@pytest.mark.anyio
async def test_find_equivalent_resistor_missing_original_power_is_honest_null():
    orig_row = rp("C100", price=0.0010, stock=1000, power=None)
    cheaper = rp("C1", price=0.0004, stock=900000)
    ds = FakeDS(detail("C100", "0603", 0.0010, 1000),
                {("resistors", "0603"): [orig_row, cheaper]})
    resp = await find_equivalent(ds, "C100")
    assert resp.equivalent is None
    assert "could not be identified" in resp.reason
    # Never falls through to the misleading "no cheaper drop-in" reason.
    assert "no cheaper" not in resp.reason.lower()


@pytest.mark.anyio
async def test_find_equivalent_ic_returns_null_with_reason():
    ds = FakeDS(detail("C8734", "LQFP-48(7x7)", 1.0371, 214596, mpn="STM32"),
                {})   # not found in resistors or capacitors
    resp = await find_equivalent(ds, "C8734")
    assert resp.equivalent is None
    assert "resistors and capacitors" in resp.reason
    assert resp.original.lcsc == "C8734"


@pytest.mark.anyio
async def test_find_equivalent_passive_but_no_qualifying_candidate():
    orig_row = rp("C100", price=0.0010, stock=1000)
    pricier = rp("C2", price=0.0050, stock=900000)
    ds = FakeDS(detail("C100", "0603", 0.0010, 1000),
                {("resistors", "0603"): [orig_row, pricier]})
    resp = await find_equivalent(ds, "C100")
    assert resp.equivalent is None
    assert resp.reason is not None


@pytest.mark.anyio
async def test_find_equivalent_capacitor_returns_cheaper_match():
    orig_row = cp("C200", price=0.0030, stock=1000)
    cheaper = cp("C1", price=0.0012, stock=500000, volt=25, tc="C0G")
    ds = FakeDS(detail("C200", "0402", 0.0030, 1000, mpn="C-orig"),
                {("capacitors", "0402"): [orig_row, cheaper]})
    resp = await find_equivalent(ds, "C200")
    assert resp.equivalent is not None
    assert resp.equivalent.lcsc == "C1"
    assert resp.equivalent.percent_cheaper == 60   # (1 - 0.0012/0.0030)*100
    assert resp.reason is None
    assert "0402" in resp.equivalent.match_reason
    assert "% cheaper" in resp.equivalent.match_reason


@pytest.mark.anyio
async def test_find_equivalent_unknown_code_returns_none():
    ds = FakeDS(None, {})
    assert await find_equivalent(ds, "C000000") is None
