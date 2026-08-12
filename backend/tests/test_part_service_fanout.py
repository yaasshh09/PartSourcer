import asyncio
from datetime import datetime, timezone

import pytest

from services.adapters.base import DistributorAdapter, RawListing, UpstreamError
from services.part_service import PartService
from services.quota import QuotaTracker

pytestmark = pytest.mark.anyio

T0 = datetime(2026, 8, 12, 9, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 8, 12, 9, 5, tzinfo=timezone.utc)


def listing(distributor, mpn="STM32F103C8T6", as_of=T0, price=1.0):
    return RawListing(distributor=distributor, sku=f"{distributor}-1", mpn=mpn,
                      brand=None, package="", description="", stock=10,
                      in_stock=True, price=price, currency="USD",
                      price_breaks=None, datasheet_url=None, product_url=None,
                      as_of=as_of)


class FakeAdapter(DistributorAdapter):
    def __init__(self, name, listings=None, raises=None, delay=0.0):
        self.name = name
        self._listings = listings if listings is not None else [listing(name)]
        self._raises = raises
        self._delay = delay
        self.calls = 0

    async def search(self, query, limit):
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._raises:
            raise self._raises
        return self._listings

    async def lookup_mpn(self, mpn):
        return await self.search(mpn, 10)


def service(adapters, disabled=None, quota=None, timeout=5.0):
    return PartService(adapters={a.name: a for a in adapters},
                       quota=quota or QuotaTracker(),
                       disabled=disabled or {}, timeout_secs=timeout)


def call(a):
    return a.search("stm32", 10)


async def test_two_healthy_sources_both_contribute():
    lcsc, mouser = FakeAdapter("lcsc"), FakeAdapter("mouser")
    listings, sources = await service([lcsc, mouser]).fan_out(call)
    assert len(listings) == 2
    assert [s.state for s in sources] == ["ok", "ok"]


async def test_statuses_are_always_in_distributor_order():
    svc = service([FakeAdapter("digikey"), FakeAdapter("lcsc")])
    _, sources = await svc.fan_out(call)
    assert [s.distributor for s in sources] == ["lcsc", "digikey"]


async def test_a_slow_source_times_out_without_killing_the_others():
    slow = FakeAdapter("mouser", delay=0.20)
    svc = service([FakeAdapter("lcsc"), slow], timeout=0.02)
    listings, sources = await svc.fan_out(call)
    by = {s.distributor: s for s in sources}
    assert by["lcsc"].state == "ok"
    assert by["mouser"].state == "timeout"
    assert len(listings) == 1


async def test_an_unavailable_source_is_reported_and_isolated():
    bad = FakeAdapter("mouser", raises=UpstreamError("unavailable", "boom"))
    listings, sources = await service([FakeAdapter("lcsc"), bad]).fan_out(call)
    by = {s.distributor: s for s in sources}
    assert by["mouser"].state == "unavailable" and "boom" in by["mouser"].detail
    assert len(listings) == 1


async def test_an_upstream_timeout_kind_maps_to_the_timeout_state():
    bad = FakeAdapter("mouser", raises=UpstreamError("timeout", "slow"))
    _, sources = await service([bad]).fan_out(call)
    assert sources[0].state == "timeout"


async def test_a_429_marks_the_tracker_and_reports_quota_exhausted():
    q = QuotaTracker()
    bad = FakeAdapter("mouser", raises=UpstreamError("quota", "429"))
    _, sources = await service([bad], quota=q).fan_out(call)
    assert sources[0].state == "quota_exhausted"
    assert q.is_exhausted("mouser") is True


async def test_an_already_exhausted_distributor_is_never_called():
    q = QuotaTracker()
    q.mark_exhausted("mouser")
    mouser = FakeAdapter("mouser")
    _, sources = await service([FakeAdapter("lcsc"), mouser], quota=q).fan_out(call)
    by = {s.distributor: s for s in sources}
    assert by["mouser"].state == "quota_exhausted"
    assert mouser.calls == 0


async def test_a_disabled_distributor_is_reported_and_never_called():
    svc = service([FakeAdapter("lcsc")],
                  disabled={"digikey": "no credentials configured"})
    _, sources = await svc.fan_out(call)
    by = {s.distributor: s for s in sources}
    assert by["digikey"].state == "disabled"
    assert by["digikey"].detail == "no credentials configured"


async def test_an_ok_status_carries_the_oldest_listing_timestamp():
    a = FakeAdapter("lcsc", listings=[listing("lcsc", as_of=T1),
                                      listing("lcsc", as_of=T0)])
    _, sources = await service([a]).fan_out(call)
    assert sources[0].as_of == T0


async def test_an_ok_source_with_no_results_has_no_timestamp():
    _, sources = await service([FakeAdapter("lcsc", listings=[])]).fan_out(call)
    assert sources[0].state == "ok" and sources[0].as_of is None


async def test_an_unexpected_exception_degrades_instead_of_propagating():
    bad = FakeAdapter("mouser", raises=ValueError("unmapped"))
    listings, sources = await service([FakeAdapter("lcsc"), bad]).fan_out(call)
    by = {s.distributor: s for s in sources}
    assert by["mouser"].state == "unavailable"
    assert len(listings) == 1


async def test_a_successful_call_is_counted_against_the_daily_quota():
    q = QuotaTracker()
    await service([FakeAdapter("lcsc")], quota=q).fan_out(call)
    assert q.calls_today("lcsc") == 1
