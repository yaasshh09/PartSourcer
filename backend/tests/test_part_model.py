"""Unit tests for the PartDetail response model (spec §9 detail)."""

from datetime import datetime, timezone

from models.part import PartDetail

AS_OF = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)


def _make(**over):
    base = dict(lcsc="C8734", mpn="STM32F103C8T6", brand=None,
                package="LQFP-48(7x7)", description="", stock=214596,
                price_usd=1.0371, is_basic=False, is_preferred=True,
                datasheet_url=None, as_of=AS_OF)
    base.update(over)
    return PartDetail(**base)


def test_ladder_and_breakdown_default_to_null():
    d = _make()
    assert d.price_breaks is None
    assert d.stock_breakdown is None


def test_flags_carry_real_booleans():
    d = _make(is_basic=True, is_preferred=False)
    assert d.is_basic is True and d.is_preferred is False


def test_flags_accept_none():
    d = _make(is_basic=None, is_preferred=None)
    assert d.is_basic is None and d.is_preferred is None


def test_serializes_gaps_as_null_json():
    d = _make()
    dumped = d.model_dump(mode="json")
    assert dumped["price_breaks"] is None
    assert dumped["stock_breakdown"] is None
    assert dumped["brand"] is None and dumped["datasheet_url"] is None
    assert dumped["is_basic"] is False and dumped["is_preferred"] is True
