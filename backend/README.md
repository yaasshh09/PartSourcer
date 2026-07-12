# PartSourcer Backend

FastAPI service that finds the cheapest in-stock electronic part and one cheaper
in-stock equivalent, over a swappable data source (jlcsearch in v1).

## Run locally (Windows)

```bash
cd backend
py -3 -m venv .venv                        # first time only (Python 3.11+)
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn main:app --reload
```

API at http://127.0.0.1:8000 — interactive docs at http://127.0.0.1:8000/docs.

Run the tests:

```bash
.venv/Scripts/python.exe -m pytest -q
```

## Endpoints

### `GET /health`
`{"status": "ok"}`

### `GET /api/search?q=<query>&page=1&refresh=false`
```bash
curl "http://127.0.0.1:8000/api/search?q=STM32F103"
```
```json
{"page": 1, "results": [
  {"lcsc": "C8734", "mpn": "STM32F103C8T6", "brand": null,
   "package": "LQFP-48(7x7)", "description": "...", "stock": 214596,
   "price_usd": 1.0371, "datasheet_url": null, "as_of": "2026-07-12T..."}
]}
```

### `GET /api/part/<lcsc_code>?refresh=false`
Full detail (adds `price_breaks`, `stock_breakdown`, `is_basic`, `is_preferred`;
`price_breaks`/`stock_breakdown` are `null` in v1). `404` if unknown.

### `GET /api/part/<lcsc_code>/equivalent`
Returns `original` + one cheaper in-stock drop-in `equivalent`, or
`equivalent: null` with a human `reason`. v1 matches resistors and capacitors
only; every other type returns an honest null (never a guessed "similar part").

## Configuration (env vars)

Loaded via pydantic-settings from the environment or a local `.env`
(names are case-insensitive; see `config.py`).

| Var | Default | Meaning |
|---|---|---|
| `JLCSEARCH_BASE_URL` | `https://jlcsearch.tscircuit.com` | upstream base URL |
| `REQUEST_TIMEOUT_SECS` | `10.0` | timeout on every upstream call |
| `SPECS_CACHE_TTL_SECS` | `2592000` | specs freshness (30 days) |
| `STOCK_CACHE_TTL_SECS` | `3600` | stock/price freshness (1 hour) |
| `SQLITE_PATH` | `./partsourcer.db` | cache DB path |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://127.0.0.1:5173"]` | allowed browser origins (set Vercel origin in prod) |
| `REFRESH_COOLDOWN_SECS` | `10.0` | min gap between forced `?refresh=true` upstream hits per key |

## Errors

Every error is `{"detail": "<message>"}`: `404` not found, `422` bad params,
`502` upstream unreachable/malformed, `504` upstream timeout, `500` internal.

## Data & honesty notes

- Data source is the free, open **jlcsearch** API — a **~daily jlcparts
  snapshot**, not live LCSC stock/price. `as_of` is our fetch time; the UI shows
  it so freshness is always honest.
- `brand` and `datasheet_url` are `null` in v1 (absent upstream); they light up
  when the official LCSC API is dropped in behind `PartDataSource`.
- `?refresh=true` forces a fresh upstream fetch, throttled per key.

## What's fragile / worth watching

- Single free community upstream — no SLA; the only data source in v1.
- Data is a ~daily snapshot, not live LCSC.
- Refresh throttle is in-process — it does not coordinate across multiple
  workers/instances.
- SQLite cache is single-node; fine for v1, revisit for horizontal scale.
- Parametric (equivalent-matcher) results are not cached — every equivalent
  lookup hits upstream.
- `brand` / `datasheet_url` remain null until the official LCSC API lands.
