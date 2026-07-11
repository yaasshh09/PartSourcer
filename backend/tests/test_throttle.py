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
    assert t.allow("k") is True


def test_second_call_within_cooldown_blocked():
    t = RefreshThrottle(cooldown_secs=10, now=FakeMono())
    assert t.allow("k") is True
    assert t.allow("k") is False


def test_call_after_cooldown_allowed():
    mono = FakeMono()
    t = RefreshThrottle(cooldown_secs=10, now=mono)
    assert t.allow("k") is True
    mono.advance(10)          # boundary: 10 >= 10 -> allowed again
    assert t.allow("k") is True


def test_distinct_keys_independent():
    t = RefreshThrottle(cooldown_secs=10, now=FakeMono())
    assert t.allow("a") is True
    assert t.allow("b") is True
