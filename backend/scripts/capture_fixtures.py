"""Capture real distributor responses as test fixtures.

Run manually with credentials in backend/.env:
    .venv/Scripts/python.exe scripts/capture_fixtures.py

Fixtures are committed. They contain public catalogue data only, never a
key: the script asserts no credential appears in what it writes.
"""

import asyncio
import json
import pathlib
import sys

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures"
QUERIES = ["STM32F103C8T6", "0603 10k resistor", "zzzznotarealpart"]


def write(distributor: str, label: str, payload: object) -> None:
    secrets = [s for s in (settings.mouser_api_key, settings.digikey_client_id,
                           settings.digikey_client_secret) if s]
    blob = json.dumps(payload, indent=2, sort_keys=True)
    for s in secrets:
        assert s not in blob, f"credential leaked into {distributor}/{label}"
    out = FIXTURES / distributor
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{label}.json").write_text(blob, encoding="utf-8")
    print(f"wrote {distributor}/{label}.json")


async def capture_mouser() -> None:
    if not settings.mouser_api_key:
        print("skipping mouser: MOUSER_API_KEY not set")
        return
    async with httpx.AsyncClient(base_url=settings.mouser_base_url,
                                 timeout=20.0) as c:
        for i, q in enumerate(QUERIES):
            resp = await c.post(
                "/api/v1/search/keyword",
                params={"apiKey": settings.mouser_api_key},
                json={"SearchByKeywordRequest": {"keyword": q, "records": 10,
                                                 "startingRecord": 0}})
            write("mouser", f"keyword_{i}", resp.json())


async def capture_digikey() -> None:
    if not (settings.digikey_client_id and settings.digikey_client_secret):
        print("skipping digikey: credentials not set")
        return
    async with httpx.AsyncClient(base_url=settings.digikey_base_url,
                                 timeout=20.0) as c:
        tok = await c.post("/v1/oauth2/token", data={
            "client_id": settings.digikey_client_id,
            "client_secret": settings.digikey_client_secret,
            "grant_type": "client_credentials"})
        tok.raise_for_status()
        access = tok.json()["access_token"]
        headers = {"Authorization": f"Bearer {access}",
                   "X-DIGIKEY-Client-Id": settings.digikey_client_id,
                   "X-DIGIKEY-Locale-Site": "US",
                   "X-DIGIKEY-Locale-Currency": "USD"}
        for i, q in enumerate(QUERIES):
            resp = await c.post("/products/v4/search/keyword", headers=headers,
                                json={"Keywords": q, "Limit": 10, "Offset": 0})
            write("digikey", f"keyword_{i}", resp.json())


async def main() -> None:
    await capture_mouser()
    await capture_digikey()


if __name__ == "__main__":
    asyncio.run(main())
