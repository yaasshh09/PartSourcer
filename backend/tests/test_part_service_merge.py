# backend/tests/test_part_service_merge.py
from datetime import datetime, timezone

import pytest

from models.offer import DistributorStatus
from services.adapters.base import RawListing
from services.part_service import PartService
from services.quota import QuotaTracker

pytestmark = pytest.mark.anyio

T0 = datetime(2026, 8, 12, 9, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 8, 12, 9, 30, tzinfo=timezone.utc)


def listing(distributor, mpn, price=1.0, as_of=T0, brand=None, package="",
            description="", datasheet_url=None, in_stock=True, currency="USD"):
    return RawListing(distributor=distributor, sku=f"{distributor}-{mpn}",
                      mpn=mpn, brand=brand, package=package,
                      description=description, stock=10 if in_stock else 0,
                      in_stock=in_stock, price=price, currency=currency,
                      price_breaks=None, datasheet_url=datasheet_url,
                      product_url=None, as_of=as_of)


def ok(*names):
    return [DistributorStatus(distributor=n, state="ok", detail=None, as_of=T0)
            for n in names]


def svc():
    return PartService(adapters={}, quota=QuotaTracker())


def test_the_same_mpn_from_two_distributors_becomes_one_part():
    parts = svc().merge([listing("lcsc", "STM32F103C8T6"),
                         listing("mouser", "stm32f103c8t6")],
                        ok("lcsc", "mouser"))
    assert len(parts) == 1
    assert parts[0].mpn_key == "STM32F103C8T6"
    assert len(parts[0].offers) == 2
    assert all(o.match_tier == "exact" for o in parts[0].offers)


def test_the_offer_records_the_mpn_verbatim_so_a_user_can_audit_it():
    parts = svc().merge([listing("mouser", "stm32f103c8t6")], ok("mouser"))
    assert parts[0].offers[0].mpn_as_listed == "stm32f103c8t6"


def test_a_packaging_variant_folds_into_its_base_part():
    parts = svc().merge([listing("lcsc", "STM32F103C8T6"),
                         listing("mouser", "STM32F103C8T6-TR")],
                        ok("lcsc", "mouser"))
    assert len(parts) == 1
    tiers = {o.distributor: o.match_tier for o in parts[0].offers}
    assert tiers == {"lcsc": "exact", "mouser": "packaging"}
    note = [o.match_note for o in parts[0].offers if o.distributor == "mouser"][0]
    assert "tape and reel" in note and "-TR" in note


def test_an_exact_offer_carries_no_match_note():
    parts = svc().merge([listing("lcsc", "STM32F103C8T6")], ok("lcsc"))
    assert parts[0].offers[0].match_note is None


def test_a_variant_with_no_base_in_the_results_stands_on_its_own():
    parts = svc().merge([listing("mouser", "STM32F103C8T6-TR")], ok("mouser"))
    assert len(parts) == 1
    assert parts[0].mpn_key == "STM32F103C8T6-TR"
    assert parts[0].offers[0].match_tier == "exact"


def test_the_base_is_folded_even_when_the_variant_is_seen_first():
    parts = svc().merge([listing("mouser", "STM32F103C8T6-TR"),
                         listing("lcsc", "STM32F103C8T6")],
                        ok("lcsc", "mouser"))
    assert len(parts) == 1
    assert parts[0].mpn_key == "STM32F103C8T6"


def test_the_part_is_named_by_an_exact_offer_not_a_variant():
    parts = svc().merge([listing("mouser", "STM32F103C8T6-TR"),
                         listing("lcsc", "STM32F103C8T6")],
                        ok("lcsc", "mouser"))
    assert parts[0].mpn == "STM32F103C8T6"


def test_specs_come_from_whichever_distributor_actually_has_them():
    parts = svc().merge(
        [listing("lcsc", "STM32F103C8T6", package="LQFP-48"),
         listing("mouser", "STM32F103C8T6", brand="STMicroelectronics",
                 datasheet_url="https://ds.test/x.pdf", description="ARM MCU")],
        ok("lcsc", "mouser"))
    p = parts[0]
    assert p.brand == "STMicroelectronics"
    assert p.datasheet_url == "https://ds.test/x.pdf"
    assert p.package == "LQFP-48"
    assert p.description == "ARM MCU"


def test_specs_prefer_the_exact_listing_over_a_folded_variant():
    parts = svc().merge(
        [listing("mouser", "STM32F103C8T6-TR", brand="Mouser Listed Brand",
                 package="LQFP-48 reel", description="MCU on tape and reel"),
         listing("lcsc", "STM32F103C8T6", brand="STMicroelectronics",
                 package="LQFP-48", description="ARM MCU")],
        ok("lcsc", "mouser"))
    p = parts[0]
    assert p.brand == "STMicroelectronics"
    assert p.package == "LQFP-48"
    assert p.description == "ARM MCU"


def test_specs_follow_distributor_precedence_not_input_order():
    parts = svc().merge(
        [listing("mouser", "STM32F103C8T6", brand="Mouser Listed Brand",
                 package="LQFP48", description="MCU, 32-bit"),
         listing("lcsc", "STM32F103C8T6", brand="STMicroelectronics",
                 package="LQFP-48", description="ARM MCU")],
        ok("lcsc", "mouser"))
    p = parts[0]
    assert p.brand == "STMicroelectronics"
    assert p.package == "LQFP-48"
    assert p.description == "ARM MCU"


def test_a_two_step_variant_folds_down_to_the_base_that_really_exists():
    parts = svc().merge([listing("lcsc", "STM32F103C8T6"),
                         listing("mouser", "STM32F103C8T6-TR"),
                         listing("digikey", "STM32F103C8T6-TR-REEL")],
                        ok("lcsc", "mouser", "digikey"))
    assert [p.mpn_key for p in parts] == ["STM32F103C8T6"]
    tiers = {o.distributor: o.match_tier for o in parts[0].offers}
    assert tiers == {"lcsc": "exact", "mouser": "packaging",
                     "digikey": "packaging"}
    note = [o.match_note for o in parts[0].offers
            if o.distributor == "digikey"][0]
    assert "-TR-REEL" in note
    assert parts[0].cheapest.distributor == "lcsc"


def test_a_two_step_variant_stops_at_the_deepest_base_present():
    parts = svc().merge([listing("mouser", "STM32F103C8T6-TR"),
                         listing("digikey", "STM32F103C8T6-TR-REEL")],
                        ok("mouser", "digikey"))
    assert [p.mpn_key for p in parts] == ["STM32F103C8T6-TR"]
    tiers = {o.distributor: o.match_tier for o in parts[0].offers}
    assert tiers == {"mouser": "exact", "digikey": "packaging"}


def test_part_as_of_is_the_oldest_contributing_offer():
    parts = svc().merge([listing("lcsc", "STM32F103C8T6", as_of=T1),
                         listing("mouser", "STM32F103C8T6", as_of=T0)],
                        ok("lcsc", "mouser"))
    assert parts[0].as_of == T0


def test_cheapest_ignores_a_packaging_offer_even_when_it_is_cheaper():
    parts = svc().merge([listing("lcsc", "STM32F103C8T6", price=2.00),
                         listing("mouser", "STM32F103C8T6-TR", price=0.50)],
                        ok("lcsc", "mouser"))
    assert parts[0].cheapest.price_usd == 2.00
    assert parts[0].cheapest.distributor == "lcsc"


def test_a_single_answering_source_yields_no_cheapest_claim():
    parts = svc().merge([listing("lcsc", "STM32F103C8T6")], ok("lcsc"))
    assert parts[0].cheapest is None
    assert "need at least 2" in parts[0].cheapest_unavailable_reason


def test_results_keep_first_seen_order():
    parts = svc().merge([listing("lcsc", "AAA1"), listing("lcsc", "BBB2"),
                         listing("mouser", "AAA1")], ok("lcsc", "mouser"))
    assert [p.mpn_key for p in parts] == ["AAA1", "BBB2"]


def test_a_listing_with_an_unusable_mpn_is_dropped():
    parts = svc().merge([listing("lcsc", "   "), listing("lcsc", "AAA1")],
                        ok("lcsc"))
    assert [p.mpn_key for p in parts] == ["AAA1"]


class FakePages:
    """Returns as many distinct listings as it was asked for, and remembers
    every limit it was asked with."""

    name = "lcsc"

    def __init__(self):
        self.limits = []

    async def search(self, query, limit):
        self.limits.append(limit)
        return [listing("lcsc", f"MPN{i:02d}") for i in range(limit)]

    async def lookup_mpn(self, mpn):
        return await self.search(mpn, 10)


async def test_search_wraps_the_fan_out_in_a_response_envelope():
    fake = FakePages()
    service = PartService(adapters={"lcsc": fake}, quota=QuotaTracker())
    resp = await service.search("stm32", limit=3, page=1)
    assert resp.page == 1 and resp.query == "stm32"
    assert fake.limits == [3]
    assert [p.mpn_key for p in resp.results] == ["MPN00", "MPN01", "MPN02"]
    assert [s.distributor for s in resp.sources] == ["lcsc"]


async def test_a_later_page_returns_that_page_not_the_first_one():
    fake = FakePages()
    service = PartService(adapters={"lcsc": fake}, quota=QuotaTracker())
    resp = await service.search("stm32", limit=3, page=2)
    assert resp.page == 2 and resp.query == "stm32"
    assert fake.limits == [6]        # asked upstream for page * limit rows
    assert [p.mpn_key for p in resp.results] == ["MPN03", "MPN04", "MPN05"]
    assert [s.distributor for s in resp.sources] == ["lcsc"]


async def test_a_page_past_the_end_is_empty_rather_than_wrapping_around():
    class Short(FakePages):
        async def search(self, query, limit):
            self.limits.append(limit)
            return [listing("lcsc", "MPN00")]

    service = PartService(adapters={"lcsc": Short()}, quota=QuotaTracker())
    resp = await service.search("stm32", limit=3, page=2)
    assert resp.page == 2
    assert resp.results == []
