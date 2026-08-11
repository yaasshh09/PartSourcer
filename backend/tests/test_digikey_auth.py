from datetime import datetime, timedelta, timezone

import httpx
import pytest

from services.adapters.base import UpstreamError
from services.adapters.digikey_auth import DigiKeyTokenClient

pytestmark = pytest.mark.anyio

T0 = datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc)


class Clock:
    def __init__(self):
        self.now = T0

    def __call__(self):
        return self.now

    def advance(self, secs):
        self.now = self.now + timedelta(seconds=secs)


def token_client(clock, responses):
    calls = {"n": 0}

    def handler(request):
        i = min(calls["n"], len(responses) - 1)
        calls["n"] += 1
        status, payload = responses[i]
        return httpx.Response(status, json=payload)

    c = httpx.AsyncClient(transport=httpx.MockTransport(handler),
                          base_url="https://api.digikey.test")
    return DigiKeyTokenClient(c, "id", "secret", now=clock), calls


async def test_fetches_a_token_on_first_use():
    clock = Clock()
    tc, calls = token_client(clock, [(200, {"access_token": "A", "expires_in": 600})])
    assert await tc.token() == "A"
    assert calls["n"] == 1


async def test_reuses_a_live_token():
    clock = Clock()
    tc, calls = token_client(clock, [(200, {"access_token": "A", "expires_in": 600})])
    await tc.token()
    clock.advance(100)
    assert await tc.token() == "A"
    assert calls["n"] == 1


async def test_refreshes_before_expiry_not_after():
    clock = Clock()
    tc, calls = token_client(clock, [
        (200, {"access_token": "A", "expires_in": 600}),
        (200, {"access_token": "B", "expires_in": 600})])
    await tc.token()
    clock.advance(600 - 30)          # inside the 60s refresh margin
    assert await tc.token() == "B"
    assert calls["n"] == 2


async def test_invalidate_forces_a_refresh():
    clock = Clock()
    tc, _ = token_client(clock, [
        (200, {"access_token": "A", "expires_in": 600}),
        (200, {"access_token": "B", "expires_in": 600})])
    await tc.token()
    tc.invalidate()
    assert await tc.token() == "B"


async def test_auth_failure_raises_unavailable():
    clock = Clock()
    tc, _ = token_client(clock, [(401, {"error": "invalid_client"})])
    with pytest.raises(UpstreamError) as exc:
        await tc.token()
    assert exc.value.kind == "unavailable"


async def test_malformed_token_response_raises():
    clock = Clock()
    tc, _ = token_client(clock, [(200, {"nope": 1})])
    with pytest.raises(UpstreamError):
        await tc.token()
