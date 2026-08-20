"""The inbound limiter: counting, window rollover, and its own memory ceiling."""

import pytest

from services.ratelimit import RateLimiter


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_allows_up_to_the_limit_then_rejects():
    limiter = RateLimiter(limit=3, window_secs=60, now=Clock())
    assert [limiter.check("a").allowed for _ in range(3)] == [True, True, True]
    assert limiter.check("a").allowed is False


def test_remaining_counts_down_and_floors_at_zero():
    limiter = RateLimiter(limit=3, window_secs=60, now=Clock())
    assert [limiter.check("a").remaining for _ in range(4)] == [2, 1, 0, 0]


def test_clients_do_not_share_a_budget():
    limiter = RateLimiter(limit=1, window_secs=60, now=Clock())
    assert limiter.check("a").allowed is True
    assert limiter.check("b").allowed is True     # different client, own bucket
    assert limiter.check("a").allowed is False


def test_window_rolls_over_and_the_budget_comes_back():
    clock = Clock()
    limiter = RateLimiter(limit=1, window_secs=60, now=clock)
    assert limiter.check("a").allowed is True
    assert limiter.check("a").allowed is False
    clock.t += 59.9
    assert limiter.check("a").allowed is False    # still the same window
    clock.t += 0.2
    assert limiter.check("a").allowed is True


def test_retry_after_is_whole_seconds_and_never_rounds_down_to_zero():
    """A caller told to wait 0 would come straight back inside the window."""
    clock = Clock()
    limiter = RateLimiter(limit=1, window_secs=60, now=clock)
    limiter.check("a")
    assert limiter.check("a").retry_after == 60
    clock.t += 59.5
    assert limiter.check("a").retry_after == 1


def test_key_table_is_bounded_so_the_limiter_is_not_the_attack():
    """Rotating the source address must not grow the process forever."""
    clock = Clock()
    limiter = RateLimiter(limit=5, window_secs=60, max_keys=10, now=clock)
    for i in range(500):
        limiter.check(f"client-{i}")
    assert len(limiter._windows) <= 10


def test_eviction_drops_expired_windows_before_live_ones():
    clock = Clock()
    limiter = RateLimiter(limit=5, window_secs=60, max_keys=2, now=clock)
    limiter.check("old")
    clock.t += 61                       # "old" has now expired
    limiter.check("live")
    limiter.check("newcomer")
    assert "old" not in limiter._windows
    assert "live" in limiter._windows


@pytest.mark.parametrize("kwargs", [
    {"limit": 0, "window_secs": 60},
    {"limit": 5, "window_secs": 0},
    {"limit": 5, "window_secs": 60, "max_keys": 0},
])
def test_nonsense_configuration_fails_loudly(kwargs):
    with pytest.raises(ValueError):
        RateLimiter(**kwargs)
