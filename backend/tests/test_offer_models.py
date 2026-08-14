from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from models.offer import (Cheapest, DistributorStatus, Offer, Part,
                          SearchResponse)

T1 = datetime(2026, 8, 8, 9, 14, tzinfo=timezone.utc)
T2 = datetime(2026, 8, 8, 10, 30, tzinfo=timezone.utc)


def offer(distributor="lcsc", price=1.82, tier="exact", as_of=T1, note=None):
    return Offer(distributor=distributor, sku="C8734",
                 mpn_as_listed="STM32F103C8T6", match_tier=tier,
                 match_note=note, stock=12400, in_stock=True,
                 price_usd=price, price_breaks=None, currency="USD",
                 product_url=None, as_of=as_of)


def test_offer_round_trips():
    o = offer()
    assert o.distributor == "lcsc" and o.match_tier == "exact"


def test_unknown_distributor_is_rejected():
    with pytest.raises(ValidationError):
        offer(distributor="farnell")


def test_unknown_match_tier_is_rejected():
    with pytest.raises(ValidationError):
        offer(tier="probably")


def test_part_as_of_is_the_oldest_offer():
    p = Part(mpn_key="STM32F103C8T6", mpn="STM32F103C8T6", brand=None,
             package="LQFP-48", description="", datasheet_url=None,
             offers=[offer(as_of=T2), offer(distributor="mouser", as_of=T1)],
             cheapest=None, cheapest_unavailable_reason="only 1 of 3 sources")
    assert p.as_of == T1


def test_part_with_no_offers_has_null_as_of():
    p = Part(mpn_key="X", mpn="X", brand=None, package="", description="",
             datasheet_url=None, offers=[], cheapest=None,
             cheapest_unavailable_reason="no sources answered")
    assert p.as_of is None


def test_cheapest_records_its_own_basis():
    c = Cheapest(distributor="lcsc", sku="C8734", price_usd=1.82,
                 compared_sources=2, of_sources=3)
    assert (c.compared_sources, c.of_sources) == (2, 3)


def test_distributor_status_states_are_constrained():
    assert DistributorStatus(distributor="mouser", state="quota_exhausted",
                             detail="resets 00:00Z", as_of=None).state == "quota_exhausted"
    with pytest.raises(ValidationError):
        DistributorStatus(distributor="mouser", state="grumpy",
                          detail=None, as_of=None)


def test_search_response_carries_sources():
    r = SearchResponse(page=1, query="stm32", results=[], sources=[
        DistributorStatus(distributor="lcsc", state="ok", detail=None, as_of=T1)])
    assert r.sources[0].state == "ok"
