from datetime import datetime, timezone

from services.quota import QuotaTracker


def at(y, m, d, hh=0, mm=0):
    return datetime(y, m, d, hh, mm, tzinfo=timezone.utc)


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


def test_mark_exhausted_holds_until_the_next_utc_midnight():
    clock = Clock(at(2026, 8, 12, 14, 30))
    q = QuotaTracker(now=clock)
    q.mark_exhausted("mouser")
    assert q.is_exhausted("mouser") is True
    assert q.resets_at("mouser") == at(2026, 8, 13, 0, 0)
    clock.now = at(2026, 8, 12, 23, 59)
    assert q.is_exhausted("mouser") is True


def test_exhaustion_clears_once_the_boundary_passes():
    clock = Clock(at(2026, 8, 12, 14, 30))
    q = QuotaTracker(now=clock)
    q.mark_exhausted("mouser")
    clock.now = at(2026, 8, 13, 0, 0)
    assert q.is_exhausted("mouser") is False
    assert q.resets_at("mouser") is None


def test_marking_at_midnight_exactly_lasts_a_full_day():
    q = QuotaTracker(now=Clock(at(2026, 8, 12, 0, 0)))
    q.mark_exhausted("mouser")
    assert q.resets_at("mouser") == at(2026, 8, 13, 0, 0)


def test_exhaustion_is_per_distributor():
    q = QuotaTracker(now=Clock(at(2026, 8, 12)))
    q.mark_exhausted("mouser")
    assert q.is_exhausted("mouser") is True
    assert q.is_exhausted("digikey") is False


def test_the_detail_string_names_the_reset_time():
    q = QuotaTracker(now=Clock(at(2026, 8, 12)))
    assert "00:00Z" in q.exhaustion_detail("mouser")
