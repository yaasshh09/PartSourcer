from models.parametric import ParametricPart
from services.matcher import (MATCH_MIN_STOCK, dielectric_rank,
                               resistor_candidates, capacitor_candidates,
                               rank_best)


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


def test_capacitor_exact_cap_absorbs_fp_noise():
    pool = [cp("C5", price=0.0010, stock=5000, cap=1.0000000000000001e-07)]
    assert len(capacitor_candidates(ORIG_C, pool, ORIG_C.price_usd)) == 1


def test_rank_best_price_then_stock():
    a = rp("A", price=0.0005, stock=1000)
    b = rp("B", price=0.0004, stock=10)
    c = rp("C", price=0.0004, stock=9000)
    assert rank_best([a, b, c]).lcsc == "C"   # cheapest, then highest stock
    assert rank_best([]) is None
