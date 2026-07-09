"""Standalone exploration of the real jlcsearch API (de-risk step, Prompt 2).

Hits the full-text search endpoint plus the resistor and capacitor parametric
endpoints live, prints their real shapes, and saves truncated sample responses
to docs/api-samples/ for reference. Not imported by the FastAPI app.

Run: backend/.venv/Scripts/python.exe backend/explore_jlcsearch.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE_URL = "https://jlcsearch.tscircuit.com"
SAMPLES_DIR = Path(__file__).resolve().parent.parent / "docs" / "api-samples"
TRUNCATE_TO = 10
TIMEOUT = 15.0

# (path, envelope key holding the list of items, output sample filename)
ENDPOINTS = [
    ("/api/search?q=STM32F103", "components", "search-stm32f103.json"),
    ("/resistors/list.json?package=0402&resistance=10k", "resistors", "resistors-0402-10k.json"),
    ("/capacitors/list.json?package=0402", "capacitors", "capacitors-0402.json"),
]


def explore(client: httpx.Client, path: str, envelope: str, filename: str) -> bool:
    url = BASE_URL + path
    print(f"\n=== GET {path}")
    try:
        resp = client.get(url, timeout=TIMEOUT, follow_redirects=True)
    except httpx.HTTPError as exc:
        print(f"  ERROR: {type(exc).__name__}: {exc}")
        return False

    print(f"  status: {resp.status_code}")
    if resp.status_code != 200:
        print("  non-200 response; skipping")
        return False

    data = resp.json()
    items = data.get(envelope, [])
    print(f"  envelope key: '{envelope}'  items: {len(items)}")
    if not items:
        print("  no items returned")
        return False

    print(f"  first-item fields: {list(items[0].keys())}")
    print(f"  first item: {json.dumps(items[0])}")

    sample = {
        "_source_url": url,
        "_fetched_at": datetime.now(timezone.utc).isoformat(),
        "_original_count": len(items),
        "_note": f"list truncated to first {TRUNCATE_TO} items for readability",
        envelope: items[:TRUNCATE_TO],
    }
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    out = SAMPLES_DIR / filename
    out.write_text(json.dumps(sample, indent=2), encoding="utf-8")
    print(f"  saved -> {out.relative_to(Path(__file__).resolve().parent.parent)}")

    # Machine-checkable "did we get real data": a usable stock and price.
    first = items[0]
    has_stock = isinstance(first.get("stock"), int) and first["stock"] > 0
    has_price = (first.get("price") or first.get("price1")) not in (None, 0)
    if not (has_stock and has_price):
        print("  WARNING: first item missing usable stock/price")
        return False
    return True


def main() -> int:
    results = {}
    with httpx.Client() as client:
        for path, envelope, filename in ENDPOINTS:
            results[path] = explore(client, path, envelope, filename)

    print("\n=== summary")
    for path, ok in results.items():
        print(f"  {'OK ' if ok else 'FAIL'} {path}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
