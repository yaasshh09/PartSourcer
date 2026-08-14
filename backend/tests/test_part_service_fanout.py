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
    digikey = FakeAdapter("digikey")
    svc = service([FakeAdapter("lcsc"), digikey],
                  disabled={"digikey": "no credentials configured"})
    _, sources = await svc.fan_out(call)
    by = {s.distributor: s for s in sources}
    assert by["digikey"].state == "disabled"
    assert by["digikey"].detail == "no credentials configured"
    assert digikey.calls == 0


async def test_an_ok_status_carries_the_oldest_listing_timestamp():
    a = FakeAdapter("lcsc", listings=[listing("lcsc", as_of=T1),
                                      listing("lcsc", as_of=T0)])
    _, sources = await service([a]).fan_out(call)
    assert sources[0].as_of == T0


async def test_an_unexpected_exception_degrades_instead_of_propagating():
    bad = FakeAdapter("mouser", raises=ValueError("unmapped"))
    listings, sources = await service([FakeAdapter("lcsc"), bad]).fan_out(call)
    by = {s.distributor: s for s in sources}
    assert by["mouser"].state == "unavailable"
    assert len(listings) == 1


async def test_an_unmapped_exception_never_leaks_its_message_into_the_status():
    # httpx puts the request URL in the message, and the Mouser API key
    # travels in the query string, so the message of an exception we did
    # not compose is never safe to publish. Only the type is.
    leaky = RuntimeError(
        "Server error '500 Internal Server Error' for url "
        "'https://api.example.invalid/api/v1/search/keyword?apiKey=SECRET123'")
    bad = FakeAdapter("mouser", raises=leaky)
    _, sources = await service([bad]).fan_out(call)

    status = sources[0]
    assert status.state == "unavailable"
    assert "SECRET123" not in (status.detail or "")
    assert "apiKey" not in (status.detail or "")
    assert "SECRET123" not in str(status.model_dump())
    assert "RuntimeError" in status.detail


async def test_a_successful_call_is_counted_against_the_daily_quota():
    q = QuotaTracker()
    await service([FakeAdapter("lcsc")], quota=q).fan_out(call)
    assert q.calls_today("lcsc") == 1


async def test_sources_are_called_concurrently_not_one_after_another():
    started = asyncio.Event()

    class Waiter(FakeAdapter):
        async def search(self, query, limit):
            started.set()
            return await super().search(query, limit)

    class Blocker(FakeAdapter):
        async def search(self, query, limit):
            await asyncio.wait_for(started.wait(), 1.0)
            return await super().search(query, limit)

    # lcsc runs first in ALL_DISTRIBUTORS order, so it must not finish
    # before mouser has started.
    svc = service([Blocker("lcsc"), Waiter("mouser")])
    listings, sources = await svc.fan_out(call)
    assert [s.state for s in sources] == ["ok", "ok"]


class _RaisingQuota(QuotaTracker):
    """record_call is reached from _call_one AFTER its try block, so an
    error here escapes into gather. Stands in for Task 24's marker I/O."""

    def record_call(self, distributor: str) -> None:
        raise RuntimeError("could not write dsn=postgres://user:hunter2@db/x")


async def test_gather_branch_detail_names_the_type_not_the_message():
    svc = service([FakeAdapter("lcsc")], quota=_RaisingQuota())
    _, statuses = await svc.fan_out(call)

    lcsc = next(s for s in statuses if s.distributor == "lcsc")
    assert lcsc.state == "unavailable"
    assert lcsc.detail == "lcsc failed: RuntimeError"
    assert "hunter2" not in (lcsc.detail or "")


async def test_fan_out_only_calls_the_named_subset():
    lcsc, mouser = FakeAdapter("lcsc"), FakeAdapter("mouser")
    svc = service([lcsc, mouser])

    _, statuses = await svc.fan_out(call, only={"mouser"})

    assert (lcsc.calls, mouser.calls) == (0, 1)
    assert [s.distributor for s in statuses] == ["mouser"]


async def test_an_empty_answer_still_carries_a_timestamp():
    """as_of None on an ok status would make the cache re-ask forever for
    a part a distributor genuinely does not carry."""
    fixed = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)
    svc = PartService(adapters={"lcsc": FakeAdapter("lcsc", [])},
                      quota=QuotaTracker(), now=lambda: fixed)

    _, statuses = await svc.fan_out(call)

    assert statuses[0].state == "ok"
    assert statuses[0].as_of == fixed


async def test_callable_names_excludes_disabled_and_exhausted():
    quota = QuotaTracker()
    quota.mark_exhausted("mouser")
    svc = PartService(
        adapters={"lcsc": FakeAdapter("lcsc", []),
                  "mouser": FakeAdapter("mouser", [])},
        quota=quota, disabled={"digikey": "no credentials configured"})

    assert svc.callable_names() == ["lcsc"]
