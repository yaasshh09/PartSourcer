from services.throttle import RefreshThrottle


class FakeMono:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, secs):
        self.t += secs


def test_first_call_allowed():
    t = RefreshThrottle(cooldown_secs=10, now=FakeMono())
    assert t.allow("lcsc", "k") is True


def test_second_call_within_cooldown_blocked():
    t = RefreshThrottle(cooldown_secs=10, now=FakeMono())
    assert t.allow("lcsc", "k") is True
    assert t.allow("lcsc", "k") is False


def test_call_after_cooldown_allowed():
    mono = FakeMono()
    t = RefreshThrottle(cooldown_secs=10, now=mono)
    assert t.allow("lcsc", "k") is True
    mono.advance(10)          # boundary: 10 >= 10 -> allowed again
    assert t.allow("lcsc", "k") is True


def test_distinct_keys_independent():
    t = RefreshThrottle(cooldown_secs=10, now=FakeMono())
    assert t.allow("lcsc", "a") is True
    assert t.allow("lcsc", "b") is True


def test_a_blocked_refresh_on_one_distributor_leaves_the_others_free():
    clock = {"t": 0.0}
    throttle = RefreshThrottle(10.0, now=lambda: clock["t"])

    assert throttle.allow("mouser", "search:stm32") is True
    assert throttle.allow("mouser", "search:stm32") is False
    assert throttle.allow("lcsc", "search:stm32") is True


def test_the_cooldown_still_expires_per_pair():
    clock = {"t": 0.0}
    throttle = RefreshThrottle(10.0, now=lambda: clock["t"])
    throttle.allow("lcsc", "part:PART-A")

    clock["t"] = 11.0

    assert throttle.allow("lcsc", "part:PART-A") is True
