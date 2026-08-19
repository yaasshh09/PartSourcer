from datetime import datetime, timedelta, timezone

import pytest

from services.quota import QuotaTracker, _next_utc_midnight

pytestmark = pytest.mark.anyio


def at(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


NOON = at(2026, 8, 14, 12, 0)


class Clock:
    def __init__(self, start):
        self.now = start

    def __call__(self):
        return self.now


def test_a_fresh_tracker_is_not_exhausted():
    q = QuotaTracker(now=Clock(at(2026, 8, 12)))
    assert q.is_exhausted("mouser") is False
    assert q.calls_today("mouser") == 0


def test_record_call_counts_within_the_utc_day():
    q = QuotaTracker(now=Clock(at(2026, 8, 12, 9)))
    q.record_call("mouser")
    q.record_call("mouser")
    assert q.calls_today("mouser") == 2
    assert q.calls_today("lcsc") == 0


def test_the_counter_rolls_over_at_the_utc_date_boundary():
    clock = Clock(at(2026, 8, 12, 23, 59))
    q = QuotaTracker(now=clock)
    q.record_call("mouser")
    assert q.calls_today("mouser") == 1
    clock.now = at(2026, 8, 13, 0, 1)
    assert q.calls_today("mouser") == 0


def test_reaching_the_local_daily_limit_reports_exhausted():
    q = QuotaTracker({"mouser": 2}, now=Clock(at(2026, 8, 12)))
    q.record_call("mouser")
    assert q.is_exhausted("mouser") is False
    q.record_call("mouser")
    assert q.is_exhausted("mouser") is True


def test_a_distributor_with_no_configured_limit_never_locally_exhausts():
    q = QuotaTracker({}, now=Clock(at(2026, 8, 12)))
    for _ in range(1000):
        q.record_call("lcsc")
    assert q.is_exhausted("lcsc") is False


async def test_mark_exhausted_holds_until_the_next_utc_midnight():
    clock = Clock(at(2026, 8, 12, 14, 30))
    q = QuotaTracker(now=clock)
    await q.mark_exhausted("mouser")
    assert q.is_exhausted("mouser") is True
    assert q.resets_at("mouser") == at(2026, 8, 13, 0, 0)
    clock.now = at(2026, 8, 12, 23, 59)
    assert q.is_exhausted("mouser") is True


async def test_exhaustion_clears_once_the_boundary_passes():
    clock = Clock(at(2026, 8, 12, 14, 30))
    q = QuotaTracker(now=clock)
    await q.mark_exhausted("mouser")
    clock.now = at(2026, 8, 13, 0, 0)
    assert q.is_exhausted("mouser") is False
    assert q.resets_at("mouser") is None


async def test_marking_at_midnight_exactly_lasts_a_full_day():
    q = QuotaTracker(now=Clock(at(2026, 8, 12, 0, 0)))
    await q.mark_exhausted("mouser")
    assert q.resets_at("mouser") == at(2026, 8, 13, 0, 0)


async def test_exhaustion_is_per_distributor():
    q = QuotaTracker(now=Clock(at(2026, 8, 12)))
    await q.mark_exhausted("mouser")
    assert q.is_exhausted("mouser") is True
    assert q.is_exhausted("digikey") is False


def test_the_detail_string_names_the_reset_time():
    q = QuotaTracker(now=Clock(at(2026, 8, 12)))
    assert "00:00Z" in q.exhaustion_detail("mouser")


class FakeMarkers:
    def __init__(self, loaded=None):
        self.saved: dict[str, datetime] = {}
        self._loaded = loaded or {}

    async def get_quota_markers(self):
        return dict(self._loaded)

    async def put_quota_marker(self, distributor, resets_at):
        self.saved[distributor] = resets_at


async def test_marking_exhausted_persists_the_reset_time():
    markers = FakeMarkers()
    tracker = QuotaTracker(now=lambda: NOON, markers=markers)

    await tracker.mark_exhausted("mouser")

    assert tracker.is_exhausted("mouser") is True
    assert markers.saved["mouser"] == tracker.resets_at("mouser")


async def test_a_loaded_marker_survives_a_restart():
    tomorrow = _next_utc_midnight(NOON)
    tracker = QuotaTracker(now=lambda: NOON, loaded={"mouser": tomorrow})

    assert tracker.is_exhausted("mouser") is True


async def test_a_loaded_marker_past_its_reset_does_not_exhaust():
    tracker = QuotaTracker(now=lambda: NOON,
                           loaded={"mouser": NOON - timedelta(hours=1)})

    assert tracker.is_exhausted("mouser") is False


async def test_a_storage_failure_never_breaks_a_request():
    """The in-process marker is the hot path; persistence is best effort."""
    class Broken:
        async def get_quota_markers(self):
            return {}

        async def put_quota_marker(self, distributor, resets_at):
            raise RuntimeError("disk gone")

    tracker = QuotaTracker(now=lambda: NOON, markers=Broken())

    await tracker.mark_exhausted("mouser")

    assert tracker.is_exhausted("mouser") is True


def test_a_daily_limit_exhausts_without_a_429():
    tracker = QuotaTracker(daily_limits={"mouser": 2}, now=lambda: NOON)
    tracker.record_call("mouser")
    tracker.record_call("mouser")

    assert tracker.is_exhausted("mouser") is True
    assert tracker.is_exhausted("lcsc") is False


class RecordingMarkers:
    """A shared marker store, the way two instances would both see one."""

    def __init__(self, rows=None):
        self.rows = dict(rows or {})
        self.reads = 0

    async def get_quota_markers(self):
        self.reads += 1
        return dict(self.rows)

    async def put_quota_marker(self, distributor, resets_at):
        self.rows[distributor] = resets_at


async def test_one_instances_429_stops_another_instance():
    """The whole point of running more than one process. Without this, every
    instance has to earn its own 429 before it stops calling."""
    clock = Clock(NOON)
    shared = RecordingMarkers()
    first = QuotaTracker(daily_limits={"mouser": 1000}, now=clock,
                         markers=shared)
    second = QuotaTracker(daily_limits={"mouser": 1000}, now=clock,
                          markers=shared)

    await first.mark_exhausted("mouser")
    assert second.is_exhausted("mouser") is False    # has not looked yet

    await second.sync_markers()

    assert second.is_exhausted("mouser") is True


async def test_syncing_markers_is_rate_limited():
    """The counter exists to keep the search path free of I/O, so picking up
    another instance's marker must not add a query to every request."""
    clock = Clock(NOON)
    shared = RecordingMarkers()
    tracker = QuotaTracker(now=clock, markers=shared, marker_ttl_secs=60.0)

    await tracker.sync_markers()
    await tracker.sync_markers()
    await tracker.sync_markers()
    assert shared.reads == 1

    clock.now = NOON + timedelta(seconds=61)
    await tracker.sync_markers()
    assert shared.reads == 2


async def test_syncing_never_shortens_a_marker_this_instance_already_holds():
    clock = Clock(NOON)
    later = _next_utc_midnight(NOON)
    shared = RecordingMarkers({"mouser": NOON + timedelta(minutes=1)})
    tracker = QuotaTracker(now=clock, markers=shared)
    tracker._exhausted_until["mouser"] = later

    await tracker.sync_markers()

    assert tracker.resets_at("mouser") == later


async def test_a_storage_failure_while_syncing_is_survivable():
    """A cache outage must not turn a working search into a failed one."""
    class Broken:
        async def get_quota_markers(self):
            raise RuntimeError("neon is down")

        async def put_quota_marker(self, distributor, resets_at):
            raise RuntimeError("neon is down")

    tracker = QuotaTracker(now=Clock(NOON), markers=Broken())

    await tracker.sync_markers()

    assert tracker.is_exhausted("mouser") is False


async def test_syncing_without_a_store_is_a_no_op():
    tracker = QuotaTracker(now=Clock(NOON))
    await tracker.sync_markers()
    assert tracker.is_exhausted("mouser") is False
