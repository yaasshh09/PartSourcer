# PartSourcer Backend

FastAPI service that finds the cheapest in-stock electronic part and one cheaper
in-stock equivalent, over a swappable data source (jlcsearch in v1).

## Run locally (Windows)

```bash
cd backend
py -3 -m venv .venv                        # first time only (Python 3.11+)
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
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

**Price basis.** Upstream returns different prices and stock for the same part
depending on how it is asked (see `docs/jlcsearch-notes.md`), so this route
never compares two numbers fetched differently. Parametric rows pick and rank
candidates, because only they carry specs. The top three are then re-read
through `canonical_part`, the same `lookup_mpn` at `FETCH_DEPTH` that fills the
offer cache behind search and detail, and must clear both gates again on those
numbers, genuinely cheaper and still above the stock buffer, before a saving is
claimed. Every figure in the response, on both sides, comes from that one read,
so the card agrees with the part's own page. A saving that rounds below 1%
returns a null rather than a 0% claim.

## Configuration (env vars)

Loaded via pydantic-settings from the environment or a local `.env`
(names are case-insensitive; see `config.py`).

| Var | Default | Meaning |
|---|---|---|
| `JLCSEARCH_BASE_URL` | `https://jlcsearch.tscircuit.com` | upstream base URL |
| `REQUEST_TIMEOUT_SECS` | `10.0` | timeout on every upstream call |
| `SPECS_CACHE_TTL_SECS` | `2592000` | unused; a leftover from the v1 cache layer |
| `STOCK_CACHE_TTL_SECS` | `3600` | stock/price freshness (1 hour), and the matcher's pool |
| `CACHE_PRUNE_AFTER_DAYS` | `7` | rows older than this are deleted at startup |
| `CACHE_BACKEND` | `sqlite` | `sqlite` or `postgres`. Anywhere the app runs as more than one process this must be `postgres`, and `DATABASE_URL` becomes required |
| `SQLITE_PATH` | `./partsourcer.db` | cache DB path, ignored when `CACHE_BACKEND=postgres` |
| `CORS_ORIGINS` | `["http://localhost:5173", "http://127.0.0.1:5173"]` | allowed browser origins (set Vercel origin in prod) |
| `REFRESH_COOLDOWN_SECS` | `10.0` | min gap between forced `?refresh=true` upstream hits per key |
| `DATABASE_URL` | unset | Neon Postgres DSN. Powers the history recorder, and the cache too when `CACHE_BACKEND=postgres` |
| `RECORDER_TOKEN` | unset | shared secret for `POST /api/internal/record` (see below) |
| `RECORDER_BATCH_SIZE` | `500` | max watchlist entries walked per recorder run |
| `RECORDER_CONCURRENCY` | `4` | max simultaneous upstream fetches during a run |
| `ENVIRONMENT` | `development` | `development`, `preview` or `production`. Vercel fills this from `VERCEL_ENV` on its own. Anything but `development` turns off `/docs` and holds CORS to HTTPS origins |
| `RATE_LIMIT_REQUESTS` | `60` | requests allowed per client per window, per process |
| `RATE_LIMIT_WINDOW_SECS` | `60.0` | length of that window |
| `RATE_LIMIT_MAX_KEYS` | `4096` | how many clients the limiter tracks before evicting |
| `MAX_REQUEST_BYTES` | `65536` | largest request body accepted, over which the answer is `413` |

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

Every error is `{"detail": "<message>"}`: `404` not found, `413` request body
over `MAX_REQUEST_BYTES`, `422` bad params, `429` rate limited (carries
`Retry-After`), `502` upstream unreachable/malformed, `504` upstream timeout,
`500` internal.

## Security

What is enforced, where it lives, and what it deliberately does not claim.

### Response headers

`security.py` stamps every API response, including the ones the middleware
generates itself: `X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`,
`Cross-Origin-Resource-Policy`, and a `Content-Security-Policy` of
`default-src 'none'` because a JSON API renders, loads and frames nothing.
`Strict-Transport-Security` is added only when the browser's leg of the
connection was TLS, read from `X-Forwarded-Proto`.

The static site gets its own, wider policy from the `headers` block in the
repo-root `vercel.json`: `script-src 'self'` with no `unsafe-inline`, plus the
two Google Fonts hosts the page actually uses. It was checked against the real
production bundle rather than assumed.

> On Vercel the platform already sends its own `Strict-Transport-Security`
> with a longer max-age. Both are strict, so a duplicate is harmless; the
> app-level header is what covers a self-hosted Fly or Render deploy where
> nothing else sets one.

### Rate limiting

`services/ratelimit.py`, a fixed window per client, mounted over everything but
`/health`. The client is identified from headers the platform writes
(`x-vercel-forwarded-for`, `x-real-ip`, `fly-client-ip`, `cf-connecting-ip`)
and never from `X-Forwarded-For`, whose left-most entry is whatever the caller
typed.

**This is per process.** Each warm instance keeps its own counters, so the real
ceiling is the limit times however many instances are up. That is a brake on
one hammering client and it is not DDoS protection. The key table is bounded
(`RATE_LIMIT_MAX_KEYS`) because an unbounded dict keyed by client address would
turn the limiter itself into the attack.

### Input bounds

`api/validation.py`. These are cost controls, not sanitisers: nothing here is
interpolated into SQL, a shell or markup, so there is no dangerous character to
strip. `q` caps at 200 characters, `page` at 50, and a part key at 128, each
refused before the request can reach the cache or a metered distributor.

### SQL

Every value reaches the database as a bound parameter (`?` on SQLite, `$1` on
Postgres). Three statements interpolate a name into the string: a table name
drawn from a module-level tuple of literals, and two variable-length runs of
`?` placeholders for an `IN` list. `tests/test_repo_hygiene.py` parses the
source and fails if a fourth appears or if either run starts joining values
instead of placeholders.

### Secrets

Every credential is read from the environment by `config.py` and used only
server-side. The frontend has exactly one build-time variable, `VITE_API_BASE`,
which is not a secret; Vite inlines every `VITE_`-prefixed value into public
JavaScript, so nothing else may ever carry that prefix. `httpx` request logging
is pinned to `WARNING` because Mouser takes its API key as a query parameter
and an INFO-level request line would write it into the host's log stream.

The guard tests check that no `.env` but the two examples is tracked, that the
real ones are ignored by pattern, that no example ships a filled-in value, and
that no source file assigns a credential literal.

### What is deliberately absent

- **No accounts, sessions or cookies.** Every endpoint serves the same public
  catalogue data, so there is no per-user authorization to check and no IDOR
  surface. A guard test fails if a `Set-Cookie` ever appears, because the first
  cookie needs `Secure`, `HttpOnly`, `SameSite` and CSRF tokens behind it.
- **No CSRF tokens.** There is no ambient credential for a forged request to
  ride: CORS runs with `allow_credentials=False`, and the one state-changing
  endpoint authenticates on a custom header, which a cross-origin browser
  cannot send without passing a preflight it will fail.
- **No file uploads.** `MAX_REQUEST_BYTES` keeps that door shut rather than
  widening it for a payload nothing accepts.

### The one thing code cannot do

A **Vercel spend cap** is a dashboard setting and there is no repo-side
equivalent. Set it under Settings, Billing, Spend Management. Everything the
app can do about cost it already does: per-distributor daily ceilings
(`MOUSER_DAILY_LIMIT`, `DIGIKEY_DAILY_LIMIT`), a 30 second function timeout in
`vercel.json`, the cache in front of every upstream call, and the rate limit
above.

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
- **One DigiKey offer is one package type.** DigiKey lists a part once per
  package type (cut tape, tape and reel, Digi-Reel, sometimes a MarketPlace
  listing that ships from the supplier), each with its own SKU, ladder and
  stock, while the product-level `QuantityAvailable` is the sum across all of
  them. The adapter picks one variation and reads SKU, price and stock from
  that same one, so the quantity shown is buyable at the price shown. The
  pick is ordered: ordinary before MarketPlace, priced before unpriced,
  stocked before not, then smallest minimum order, then cheapest, then SKU,
  so upstream ordering never decides it. When several variations exist and
  DigiKey gave no per-package quantity, stock is `0` rather than the sum.
- `?refresh=true` forces a fresh upstream fetch, throttled per
  (distributor, key) so one distributor's cooldown cannot block another's. It
  is also the only thing that replaces a still-fresh offer row.
- **One cached offer row is one answer until it expires.** Upstream returns
  different prices for the same part depending on how it is asked, and search
  asks with the user's words while the detail page asks with the MPN, so about
  a quarter of cards used to disagree with their own part page. A fresh row's
  numbers are now kept whoever fetched them, and each response is built from
  what the store kept rather than from what the fetch returned, so a page can
  never quote a number the store does not hold. The equivalent matcher reads
  the same rows and keeps what it quotes for a candidate.
  - Held: `price`, `price_breaks`, `currency`, `stock`, `in_stock`, `as_of`.
    `as_of` rides with them because it is the moment those were read, which is
    exactly what the UI labels it.
  - Not held: what the part *is*. MPN, package, description and links follow
    the newest read, and `part_key` follows the merge that just ran. Freezing
    identity would strand a row under a name the merge had moved past, and the
    offer would go missing from the page.
  - `?refresh=true` replaces the numbers, and every surface then follows.

## Where the cache lives

Two implementations behind one `CacheStore` protocol, held to one shared suite
in `tests/test_cache_store_contract.py` so they cannot drift:

- **`SqliteCacheStore`** (default). One file, one lock. Right for local work
  and for any host running exactly one always-on process, and faster than a
  network round trip on every read.
- **`PostgresCacheStore`**. Required anywhere the app runs as several
  processes, which includes every serverless host. Two processes each holding
  their own SQLite file means the same part can quote two different prices
  depending on which one answered, which is the defect the one-cached-row rule
  above exists to prevent, reintroduced by the hosting rather than the code.

Its tables are prefixed `cache_` because this database also holds the history
series, which *is* a source of truth. A cache version bump drops and rebuilds
its own tables, and the prefix keeps that blast radius readable. The rebuild
takes a Postgres advisory lock, so several instances cold-starting together
cannot race each other into querying a table one of them just dropped.

`statement_cache_size=0` on the pool because Neon's pooled endpoint is
PgBouncer in transaction mode, where a prepared statement from one checkout is
gone by the next.

Run the Postgres side against a throwaway database:

```bash
docker run -d --name pg -e POSTGRES_PASSWORD=postgres -p 55432:5432 postgres:16
TEST_PG_DSN=postgresql://postgres:postgres@127.0.0.1:55432/postgres   .venv/Scripts/python.exe -m pytest -m live
```

`TEST_PG_DSN` is deliberately not `DATABASE_URL`: those tests empty every
`cache_` table between cases.

## Quota across instances

The daily counter is per process and always was, described in `quota.py` as an
optimistic guess. The authority is a real HTTP 429, which marks a distributor
exhausted until the next 00:00 UTC and writes that marker to the shared store.

On one process that is the whole story. On several, each instance used to have
to earn its own 429 before it stopped calling, so the overspend was roughly one
wasted call per instance. `QuotaTracker.sync_markers()` now reads the shared
markers at the top of every fan-out, rate limited to one read a minute, so one
instance's 429 stops the rest. It is best effort: a cache outage must not turn
a working search into a failed one.

## What's fragile / worth watching

- LCSC data is a ~daily snapshot from a single free community upstream with no
  SLA. Mouser and DigiKey are live but only run when their credentials are set.
- **Refresh throttle is still in-process, and on Vercel that matters more than
  it did.** `?refresh=true` is the deliberate upstream bypass, bounded to one
  hit per (distributor, key) per `REFRESH_COOLDOWN_SECS`. Each instance keeps
  its own dict, so N instances allow N times that rate, and since serverless
  scales out under load, a client spamming refresh on one part is exactly what
  makes N grow. It is a politeness limit on a free community upstream, not an
  honesty rule, so nothing it does can make the app report a wrong number. The
  fix is the same shape as the quota marker: an atomic claim in the shared
  store (`INSERT ... ON CONFLICT DO UPDATE ... WHERE claimed_at < $cutoff
  RETURNING 1`). It is not done because the decision is made synchronously
  inside `cached_part_service`, and threading an await through that path means
  touching the one-cached-row logic for a non-correctness win.
- The SQLite cache is single-node by nature. That is why `CACHE_BACKEND` exists;
  anything running more than one process must be on `postgres`. The whole cache
  is dropped and rebuilt on a schema-version change, which is safe because no
  source of truth lives there.
- Nothing in the cache evicts on its own, so rows older than
  `CACHE_PRUNE_AFTER_DAYS` are deleted once at startup. That matters only
  where the volume is real: on Render free the file is ephemeral and the whole
  thing is gone every spin-down anyway. The horizon is much longer than the
  offer TTL on purpose, because the offers table doubles as the SKU index
  behind the legacy `C<digits>` redirect and that lookup does not check
  freshness.
- The quota exhaustion marker persists to SQLite, so it survives a restart only
  where the volume does. On Render free the file is ephemeral and the first call
  after a restart earns a fresh 429 that re-marks it.
- The equivalent route is the heaviest one here. It resolves the part, reads a
  parametric pool or two, and re-reads up to three candidates to verify the
  saving. The candidate reads run together, and the pools are cached on the
  short TTL, so a repeat measures about 0.28s against a warm local backend,
  down from 1.8s when nothing was shared and the reads ran in turn. Cold it is
  still roughly 2s. A cached detail lookup, by contrast, is about 3ms.
- Caching the parametric pool is safe only because none of its numbers are
  published: they choose and order candidates, and the winner is re-read on
  the canonical path before any saving is claimed. If that ever changes, this
  cache has to go or move to a much shorter TTL.
- The upstream price for a part is not stable across query shapes, and we
  cannot tell which of the values it returns is the true one. Pinning one read
  makes our numbers reproducible and mutually consistent, not provably right.
  The official LCSC API is the fix, and it is the reason the adapter layer
  exists.
