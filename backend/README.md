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

API at http://127.0.0.1:8000, interactive docs at http://127.0.0.1:8000/docs.

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
{"page": 1, "query": "STM32F103", "results": [
  {"mpn_key": "STM32F103C8T6", "mpn": "STM32F103C8T6", "brand": null,
   "package": "LQFP-48(7x7)", "description": "...", "datasheet_url": null,
   "offers": [
     {"distributor": "lcsc", "sku": "C8734", "mpn_as_listed": "STM32F103C8T6",
      "match_tier": "exact", "match_note": null, "stock": 214596,
      "in_stock": true, "price_usd": 1.0371, "price_breaks": null,
      "currency": "USD", "product_url": "...", "is_basic": false,
      "is_preferred": true, "as_of": "2026-08-14T..."}
   ],
   "cheapest": null, "cheapest_unavailable_reason": "only one source answered",
   "as_of": "2026-08-14T..."}
], "sources": [
  {"distributor": "lcsc", "state": "ok", "detail": null, "as_of": "2026-08-14T..."},
  {"distributor": "mouser", "state": "disabled", "detail": "no credentials configured",
   "as_of": null},
  {"distributor": "digikey", "state": "disabled", "detail": "no credentials configured",
   "as_of": null}
]}
```

A distributor that fails is a `sources` entry, not an error: the response is
still `200`. Only a total failure of every callable distributor is a `502`.

### `GET /api/part/<mpn_key>?refresh=false`
`{"part": {...}, "sources": [...]}`, the same `Part` shape as a search result.
`404` if unknown. A legacy `C<digits>` LCSC code redirects `302` to the
canonical MPN, and so does a key that folds into another part (`X-TR` to `X`).

### `GET /api/equivalent/<mpn_key>`
Returns `original` + one cheaper in-stock drop-in `equivalent`, or
`equivalent: null` with a human `reason`. v1 matches resistors and capacitors
only; every other type returns an honest null (never a guessed "similar part").
A part with no LCSC offer also returns an honest null, because v1 matching
reads LCSC parametric data and cannot verify a drop-in without it.

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
| `DATABASE_URL` | unset | Neon Postgres DSN for the history recorder (see below) |
| `RECORDER_TOKEN` | unset | shared secret for `POST /api/internal/record` (see below) |
| `RECORDER_BATCH_SIZE` | `500` | max watchlist entries walked per recorder run |
| `RECORDER_CONCURRENCY` | `4` | max simultaneous upstream fetches during a run |

## History recorder (SP2a)

Price and stock history cannot be backfilled, so the recorder starts the clock
now and the SP5b price chart reads it later.

**How it works.** The `watchlist` table self-populates: every successful
`GET /api/part/<lcsc_code>` adds that part, keyed by its normalized MPN. A
nightly GitHub Actions cron (`.github/workflows/record-history.yml`, 03:00 UTC)
POSTs to `/api/internal/record`, which walks the watchlist with bounded
concurrency and appends one row per part to `offer_history`. History is
append-only: a recorded price is a fact about a moment and is never rewritten.

**Both env vars are optional, and the feature is off until both are set.**

| State | Behaviour |
|---|---|
| `DATABASE_URL` unset | No history store is built. The app behaves exactly as it did before SP2a, detail views skip the watchlist write, and `POST /api/internal/record` returns `503 {"detail": "recorder is not configured"}`. |
| `RECORDER_TOKEN` unset | Same `503`. A misconfigured deploy fails loudly rather than silently accepting anonymous writes. |
| Both set | The endpoint requires a matching `X-Recorder-Token` header (constant-time compared) and returns `{"recorded": N, "skipped": N, "errors": N}`. A wrong or missing token is `401`. |

`POST /api/internal/record` is not part of the public API. It is not reachable
from a browser: CORS allows `GET` only.

The watchlist write on a detail view is deliberately non-fatal. If Postgres is
unreachable the part detail still returns `200`, because a search tool that
breaks when its analytics database is down is worse than one that quietly
misses a data point.

Generate a token with:

```bash
.venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set the same value as `RECORDER_TOKEN` on the backend host and as the
`RECORDER_TOKEN` GitHub Actions secret. `BACKEND_URL` is the other required
Actions secret.

Live Postgres tests are marked `live` and deselected by default. Run them
against a real database with `DATABASE_URL` set:

```bash
.venv/Scripts/python.exe -m pytest -m live tests/test_history_store_pg.py -v
```

## Errors

Every error is `{"detail": "<message>"}`: `404` not found, `422` bad params,
`502` upstream unreachable/malformed, `504` upstream timeout, `500` internal.

## Data & honesty notes

- LCSC data comes from the free, open **jlcsearch** API, a **~daily jlcparts
  snapshot**, not live LCSC stock/price. `as_of` is our fetch time; the UI shows
  it so freshness is always honest. `Part.as_of` is the **oldest** contributing
  offer, so a fast distributor never makes a record look fresher than its
  stalest component.
- `price_usd` is `null` when the distributor published no price: a quote-only
  part, a missing field, a money string we could not parse. It is never `0.0`,
  which would read as free and could be named the cheapest offer. An offer
  with no price is excluded from the cheapest claim and from the equivalent
  matcher, and the recorder skips it rather than writing a permanent false
  low into price history.
- `brand`, `datasheet_url`, and `price_breaks` are no longer global gaps. They
  are per offer: real for Mouser and DigiKey, `null` for LCSC. `is_basic` and
  `is_preferred` are the mirror case, real for LCSC and `null` elsewhere. A
  part shows the first populated value across its offers rather than inventing
  one.
- `?refresh=true` forces a fresh upstream fetch, throttled per
  (distributor, key) so one distributor's cooldown cannot block another's.

## What's fragile / worth watching

- LCSC data is a ~daily snapshot from a single free community upstream with no
  SLA. Mouser and DigiKey are live but only run when their credentials are set.
- Refresh throttle is in-process, so it does not coordinate across multiple
  workers/instances.
- SQLite cache is single-node; fine for v1, revisit for horizontal scale. The
  whole cache is dropped and rebuilt on a schema-version change, which is safe
  because no source of truth lives there.
- The quota exhaustion marker persists to SQLite, so it survives a restart only
  where the volume does. On Render free the file is ephemeral and the first call
  after a restart earns a fresh 429 that re-marks it.
- Parametric (equivalent-matcher) results are not cached; every equivalent
  lookup hits upstream.
