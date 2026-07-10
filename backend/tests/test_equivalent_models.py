from datetime import datetime, timezone

from models.parametric import ParametricPart
from models.equivalent import OriginalRef, EquivalentMatch, EquivalentResponse


def test_parametric_part_holds_specs_dict():
    p = ParametricPart(lcsc="C25804", mpn="0603WAF1002T5E", package="0603",
                       stock=37165617, price_usd=0.0008, in_stock=True,
                       is_basic=True, is_preferred=False,
                       specs={"resistance": 10000, "tolerance_fraction": 0.01,
                              "power_watts": 100})
    assert p.specs["resistance"] == 10000
    assert p.in_stock is True


def test_equivalent_response_found():
    resp = EquivalentResponse(
        original=OriginalRef(lcsc="C25804", mpn="R1", package="0603",
                             price_usd=0.0008, stock=100),
        equivalent=EquivalentMatch(lcsc="C1", mpn="R2", price_usd=0.0004,
                                   stock=900000, package="0603",
                                   match_reason="Same 0603, 10 kOhm, 50% cheaper",
                                   percent_cheaper=50),
        reason=None,
        as_of=datetime.now(timezone.utc))
    assert resp.equivalent.percent_cheaper == 50
    assert resp.reason is None


def test_equivalent_response_null():
    resp = EquivalentResponse(
        original=OriginalRef(lcsc="C8734", mpn="STM32", package="LQFP-48(7x7)",
                             price_usd=1.0371, stock=214596),
        equivalent=None,
        reason="Only resistors and capacitors are matched in v1.",
        as_of=datetime.now(timezone.utc))
    assert resp.equivalent is None
    assert "resistors" in resp.reason
