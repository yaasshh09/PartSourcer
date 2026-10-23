"""Exchange rates for showing a USD price in another currency.

Display only: every comparison, saving and export stays in USD, the currency
the distributors quote in. The rates are the European Central Bank's daily
reference rates, which carry their own date, and that date goes to the page.
"""

import time

import httpx

SHOWN = ("EUR", "GBP", "INR")
TTL_SECS = 6 * 3600     # ECB publishes once a working day


class FxRates:
    def __init__(self, client: httpx.AsyncClient, base_url: str, now=time.monotonic):
        self._client = client
        self._url = f"{base_url.rstrip('/')}/v1/latest"
        self._now = now
        self._body: dict | None = None
        self._read_at = 0.0

    async def get(self) -> dict:
        if self._body is not None and self._now() - self._read_at < TTL_SECS:
            return self._body
        try:
            resp = await self._client.get(
                self._url, params={"base": "USD", "symbols": ",".join(SHOWN)})
            resp.raise_for_status()
            data = resp.json()
            rates = {k: float(v) for k, v in (data.get("rates") or {}).items()
                     if k in SHOWN and isinstance(v, (int, float)) and v > 0}
            body = {"base": "USD", "date": str(data["date"]), "rates": rates}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            # A dated rate stays true about its date, so the last one is
            # still worth showing. With none at all there is nothing to say.
            if self._body is not None:
                return self._body
            raise
        self._body, self._read_at = body, self._now()
        return body
