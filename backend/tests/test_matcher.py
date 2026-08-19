import pytest
from datetime import datetime, timezone

from models.parametric import ParametricPart
from models.part import PartDetail
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


def test_resistor_rejects_an_unpriced_candidate():
    # An upstream row with no price arrives as None. Read as free it would
    # beat every real offer and claim to be 100% cheaper.
    pool = [rp("C9", price=None, stock=5000)]
    assert resistor_candidates(ORIG_R, pool, ORIG_R.price_usd) == []


def test_capacitor_rejects_an_unpriced_candidate():
    pool = [cp("C9", price=None, stock=5000)]
    assert capacitor_candidates(ORIG_C, pool, ORIG_C.price_usd) == []


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


class FakeDS:
    """Duck-typed MatcherSource: the three reads the matcher is allowed.

    canonical_part defaults to echoing the parametric row for a code, which
    is the case where upstream happens to agree with itself. Pass `canonical`
    to make the two bases disagree, which is what upstream really does.
    """

    def __init__(self, detail, parametric, canonical=None):
        self._detail = detail
        self._parametric = parametric   # dict: (category, package) -> list[ParametricPart]
        self._canonical = canonical or {}   # lcsc -> (price, stock) or None
        self.calls = []
        self.canonical_calls = []

    async def get_part(self, lcsc_code, refresh=False):
        return self._detail

    async def canonical_part(self, mpn, lcsc_code, allow_cached=True):
        self.canonical_calls.append(lcsc_code)
        if lcsc_code in self._canonical:
            spec = self._canonical[lcsc_code]
            if spec is None:
                return None
            price, stock = spec
            return detail(lcsc_code, "0603", price, stock, mpn)
        for rows in self._parametric.values():
            for row in rows:
                if row.lcsc == lcsc_code:
                    return detail(lcsc_code, row.package, row.price_usd,
                                  row.stock, mpn)
        if self._detail is not None and self._detail.lcsc == lcsc_code:
            return self._detail
        return None

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
async def test_find_equivalent_unpriced_original_is_an_honest_null():
    # "Cheaper" has no meaning without a price to be cheaper than, and
    # treating the missing one as 0.0 would reject every real candidate
    # for a reason the user cannot see.
    orig_row = rp("C100", price=None, stock=1000)
    cheaper = rp("C1", price=0.0004, stock=900000)
    ds = FakeDS(detail("C100", "0603", None, 1000),
                {("resistors", "0603"): [orig_row, cheaper]})
    resp = await find_equivalent(ds, "C100")
    assert resp.equivalent is None
    assert "no published price" in resp.reason
    assert resp.original.price_usd is None


@pytest.mark.anyio
async def test_find_equivalent_unknown_code_returns_none():
    ds = FakeDS(None, {})
    assert await find_equivalent(ds, "C000000") is None


# --- price basis --------------------------------------------------------
# Upstream hands back different prices and stock for the same part depending
# on which endpoint is asked and how. Measured over 24 real parts, the
# parametric price ran a median 1.5x and up to 6x under the search price for
# the same code in the same minute. So candidates are ranked on parametric
# data and then re-priced on the canonical read before anything is claimed.


@pytest.mark.anyio
async def test_the_original_price_shown_is_the_canonical_one():
    # get_part resolves the code but reads a different query shape, so its
    # price never reaches the response.
    orig_row = rp("C100", price=0.000928, stock=1000)
    cheaper = rp("C1", price=0.0004, stock=900000)
    ds = FakeDS(detail("C100", "0603", 0.0039, 8013731),
                {("resistors", "0603"): [orig_row, cheaper]},
                canonical={"C100": (0.000928, 1000), "C1": (0.0004, 900000)})
    resp = await find_equivalent(ds, "C100")

    assert resp.original.price_usd == 0.000928
    assert resp.original.stock == 1000


@pytest.mark.anyio
async def test_percent_cheaper_is_computed_from_canonical_prices_only():
    # Parametric would say 1 - 0.0004/0.000928 = 57%. The canonical basis
    # says 1 - 0.0008/0.0012 = 33%, and 33 is the honest number.
    orig_row = rp("C100", price=0.000928, stock=1000)
    cheaper = rp("C1", price=0.0004, stock=900000)
    ds = FakeDS(detail("C100", "0603", 0.0039, 8013731),
                {("resistors", "0603"): [orig_row, cheaper]},
                canonical={"C100": (0.0012, 1000), "C1": (0.0008, 900000)})
    resp = await find_equivalent(ds, "C100")

    assert resp.equivalent.percent_cheaper == 33
    assert resp.equivalent.price_usd == 0.0008
    assert "33% cheaper" in resp.equivalent.match_reason


@pytest.mark.anyio
async def test_a_candidate_that_is_not_cheaper_once_repriced_is_not_offered():
    orig_row = rp("C100", price=0.0010, stock=1000)
    looks_cheaper = rp("C1", price=0.0004, stock=900000)
    ds = FakeDS(detail("C100", "0603", 0.0010, 1000),
                {("resistors", "0603"): [orig_row, looks_cheaper]},
                canonical={"C100": (0.0010, 1000), "C1": (0.0011, 900000)})
    resp = await find_equivalent(ds, "C100")

    assert resp.equivalent is None
    assert "did not confirm" in resp.reason


@pytest.mark.anyio
async def test_a_candidate_with_thin_canonical_stock_is_not_offered():
    # Parametric claimed 3.4M in stock, the canonical read says 19. Quoting
    # "19 in stock" under a healthy-buffer rule would be the overstatement.
    orig_row = rp("C100", price=0.0010, stock=1000)
    looks_deep = rp("C1", price=0.0004, stock=3441343)
    ds = FakeDS(detail("C100", "0603", 0.0010, 1000),
                {("resistors", "0603"): [orig_row, looks_deep]},
                canonical={"C100": (0.0010, 1000), "C1": (0.0004, 19)})
    resp = await find_equivalent(ds, "C100")

    assert resp.equivalent is None
    assert "did not confirm" in resp.reason


@pytest.mark.anyio
async def test_verification_moves_past_a_failing_candidate_to_the_next():
    orig_row = rp("C100", price=0.0010, stock=1000)
    first = rp("C1", price=0.0004, stock=900000)
    second = rp("C2", price=0.0005, stock=800000)
    ds = FakeDS(detail("C100", "0603", 0.0010, 1000),
                {("resistors", "0603"): [orig_row, first, second]},
                canonical={"C100": (0.0010, 1000),
                           "C1": (0.0012, 900000),      # not actually cheaper
                           "C2": (0.0006, 800000)})
    resp = await find_equivalent(ds, "C100")

    assert resp.equivalent.lcsc == "C2"
    assert resp.equivalent.price_usd == 0.0006


@pytest.mark.anyio
async def test_the_cheapest_confirmed_candidate_wins_not_the_first():
    """Parametric order need not survive re-pricing, so all the confirmed
    ones are compared rather than taking whichever verified first."""
    orig_row = rp("C100", price=0.0010, stock=1000)
    ds = FakeDS(detail("C100", "0603", 0.0010, 1000),
                {("resistors", "0603"): [orig_row,
                                         rp("C1", price=0.0004, stock=900000),
                                         rp("C2", price=0.0005, stock=800000)]},
                canonical={"C100": (0.0010, 1000),
                           "C1": (0.0009, 900000),
                           "C2": (0.0002, 800000)})
    resp = await find_equivalent(ds, "C100")

    assert resp.equivalent.lcsc == "C2"


@pytest.mark.anyio
async def test_only_the_top_three_candidates_are_repriced():
    # Re-pricing costs an upstream call each. Measured live, nothing past
    # the third candidate ever verified, so the walk stops there.
    orig_row = rp("C100", price=0.0010, stock=1000)
    pool = [orig_row] + [rp(f"C{i}", price=0.0001 * i, stock=900000)
                         for i in range(1, 6)]
    ds = FakeDS(detail("C100", "0603", 0.0010, 1000),
                {("resistors", "0603"): pool},
                canonical={"C100": (0.0010, 1000),
                           "C1": (0.0011, 900000), "C2": (0.0011, 900000),
                           "C3": (0.0011, 900000), "C4": (0.0002, 900000),
                           "C5": (0.0002, 900000)})
    resp = await find_equivalent(ds, "C100")

    assert resp.equivalent is None
    # Set, not list: the candidate reads run concurrently, so which one lands
    # first is not part of the contract. Which ones get read is.
    assert set(ds.canonical_calls) == {"C100", "C1", "C2", "C3"}
    assert len(ds.canonical_calls) == 4


@pytest.mark.anyio
async def test_a_read_we_could_not_complete_is_not_called_an_absent_price():
    """Upstream answers for a part at one depth and not another, so an empty
    read says nothing about whether the part is priced. Calling it unpriced
    would be a claim we have not earned, and it kills the feature for a part
    that has a perfectly good price."""
    orig_row = rp("C100", price=0.0010, stock=1000)
    cheaper = rp("C1", price=0.0004, stock=900000)
    ds = FakeDS(detail("C100", "0603", 0.0039, 1000),
                {("resistors", "0603"): [orig_row, cheaper]},
                canonical={"C100": None})
    resp = await find_equivalent(ds, "C100")

    assert resp.equivalent is None
    assert resp.original.price_usd is None
    assert "could not be read" in resp.reason
    assert "no published price" not in resp.reason


@pytest.mark.anyio
async def test_a_part_upstream_really_did_not_price_says_so():
    orig_row = rp("C100", price=0.0010, stock=1000)
    cheaper = rp("C1", price=0.0004, stock=900000)
    ds = FakeDS(detail("C100", "0603", 0.0039, 1000),
                {("resistors", "0603"): [orig_row, cheaper]},
                canonical={"C100": (None, 1000)})
    resp = await find_equivalent(ds, "C100")

    assert resp.equivalent is None
    assert "no published price" in resp.reason


@pytest.mark.anyio
async def test_the_reason_quotes_the_verified_stock_not_the_parametric_one():
    orig_row = rp("C100", price=0.0010, stock=1000)
    cheaper = rp("C1", price=0.0004, stock=3441343)
    ds = FakeDS(detail("C100", "0603", 0.0010, 1000),
                {("resistors", "0603"): [orig_row, cheaper]},
                canonical={"C100": (0.0010, 1000), "C1": (0.0004, 5102062)})
    resp = await find_equivalent(ds, "C100")

    assert "5,102,062 in stock" in resp.equivalent.match_reason
    assert resp.equivalent.stock == 5102062


@pytest.mark.anyio
async def test_capacitors_are_verified_on_the_same_basis():
    orig_row = cp("C200", price=0.0030, stock=1000)
    cheaper = cp("C1", price=0.0012, stock=500000, volt=25, tc="C0G")
    ds = FakeDS(detail("C200", "0402", 0.0030, 1000, mpn="C-orig"),
                {("capacitors", "0402"): [orig_row, cheaper]},
                canonical={"C200": (0.0020, 1000), "C1": (0.0015, 500000)})
    resp = await find_equivalent(ds, "C200")

    assert resp.equivalent.price_usd == 0.0015
    assert resp.equivalent.percent_cheaper == 25


@pytest.mark.anyio
async def test_a_saving_that_rounds_to_nothing_is_not_sold_as_a_swap():
    orig_row = rp("C100", price=0.0010, stock=1000)
    barely = rp("C1", price=0.0009, stock=900000)
    ds = FakeDS(detail("C100", "0603", 0.0010, 1000),
                {("resistors", "0603"): [orig_row, barely]},
                canonical={"C100": (0.001000, 1000), "C1": (0.000999, 900000)})
    resp = await find_equivalent(ds, "C100")

    assert resp.equivalent is None
    assert "almost exactly" in resp.reason


@pytest.mark.anyio
async def test_a_one_percent_saving_still_counts():
    orig_row = rp("C100", price=0.0010, stock=1000)
    cheaper = rp("C1", price=0.0009, stock=900000)
    ds = FakeDS(detail("C100", "0603", 0.0010, 1000),
                {("resistors", "0603"): [orig_row, cheaper]},
                canonical={"C100": (0.0010, 1000), "C1": (0.00099, 900000)})
    resp = await find_equivalent(ds, "C100")

    assert resp.equivalent is not None
    assert resp.equivalent.percent_cheaper == 1


@pytest.mark.anyio
async def test_one_failing_candidate_does_not_sink_the_whole_request():
    """The other two verified fine. Answering with an error page instead of
    the match we confirmed would throw away good work over one bad read."""
    class Flaky(FakeDS):
        async def canonical_part(self, mpn, lcsc_code, allow_cached=True):
            if lcsc_code == "C1":
                raise RuntimeError("upstream fell over")
            return await super().canonical_part(mpn, lcsc_code, allow_cached)

    orig_row = rp("C100", price=0.0010, stock=1000)
    ds = Flaky(detail("C100", "0603", 0.0010, 1000),
               {("resistors", "0603"): [orig_row,
                                        rp("C1", price=0.0004, stock=900000),
                                        rp("C2", price=0.0005, stock=800000)]},
               canonical={"C100": (0.0010, 1000), "C2": (0.0006, 800000)})

    resp = await find_equivalent(ds, "C100")

    assert resp.equivalent is not None
    assert resp.equivalent.lcsc == "C2"


@pytest.mark.anyio
async def test_every_candidate_failing_is_an_honest_null_not_an_error():
    class AllFail(FakeDS):
        async def canonical_part(self, mpn, lcsc_code, allow_cached=True):
            if lcsc_code == "C100":
                return await super().canonical_part(mpn, lcsc_code, allow_cached)
            raise RuntimeError("upstream fell over")

    orig_row = rp("C100", price=0.0010, stock=1000)
    ds = AllFail(detail("C100", "0603", 0.0010, 1000),
                 {("resistors", "0603"): [orig_row,
                                          rp("C1", price=0.0004, stock=900000)]},
                 canonical={"C100": (0.0010, 1000)})

    resp = await find_equivalent(ds, "C100")

    assert resp.equivalent is None
    assert "did not confirm" in resp.reason
