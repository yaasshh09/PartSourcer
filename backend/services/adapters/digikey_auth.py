"""DigiKey OAuth2 client-credentials token, cached in process.

Refreshed pre-emptively inside a margin before expiry so a request never
races the boundary, and invalidated on a 401 so one stale token costs one
retry rather than a run of failures.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Callable

import httpx

from services.adapters.base import UpstreamError

TOKEN_REFRESH_MARGIN_SECS = 60


class DigiKeyTokenClient:
    def __init__(self, client: httpx.AsyncClient, client_id: str,
                 client_secret: str,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        self._client = client
        self._id = client_id
        self._secret = client_secret
        self._now = now
        self._token: str | None = None
        self._expires_at: datetime | None = None
        self._lock = asyncio.Lock()

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = None

    def _is_live(self) -> bool:
        if self._token is None or self._expires_at is None:
            return False
        margin = timedelta(seconds=TOKEN_REFRESH_MARGIN_SECS)
        return self._now() < self._expires_at - margin

    async def token(self) -> str:
        if self._is_live():
            return self._token           # type: ignore[return-value]
        async with self._lock:
            if self._is_live():
                return self._token       # type: ignore[return-value]
            await self._fetch()
            return self._token           # type: ignore[return-value]

    async def _fetch(self) -> None:
        try:
            resp = await self._client.post("/v1/oauth2/token", data={
                "client_id": self._id, "client_secret": self._secret,
                "grant_type": "client_credentials"})
        except httpx.TimeoutException as exc:
            raise UpstreamError("timeout", f"digikey auth timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise UpstreamError("unavailable",
                                f"digikey auth unreachable: {exc}") from exc
        if resp.status_code != 200:
            raise UpstreamError(
                "unavailable", f"digikey auth returned HTTP {resp.status_code}")
        try:
            data = resp.json()
            access = data["access_token"]
            expires_in = int(data.get("expires_in", 600))
        except (ValueError, KeyError, TypeError) as exc:
            raise UpstreamError(
                "unavailable", "digikey auth returned a malformed token") from exc
        self._token = access
        self._expires_at = self._now() + timedelta(seconds=expires_in)
