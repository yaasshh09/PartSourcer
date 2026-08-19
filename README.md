# PartSourcer

**Find the cheapest in-stock part for your PCB in one search.**

PartSourcer is a free, open-source web tool for hardware builders. Search any
electronic component and get stock, price, footprint, and datasheet, each
stamped with when we read it, plus the standout feature: **one cheaper in-stock
equivalent** suggestion, so you can swap a part for a drop-in that costs less
and is actually available.

> **Status:** v1 feature-complete and hosted.
> Frontend <https://partsourcer-1.onrender.com>, backend
> <https://partsourcer.onrender.com>. Both are on Render's free plan, so the
> backend sleeps when idle and the first request after a quiet spell takes
> roughly 20 to 30 seconds to wake it.

> **On "live":** Mouser and DigiKey answer in real time. The LCSC side comes
> from an open jlcparts snapshot that syncs about once a day, so this is not a
> live feed from LCSC's warehouse and the UI never calls it one. Every record
> carries the time we fetched it.

## The cheaper-equivalent moat

Anyone can show a part's price. PartSourcer's differentiator is the
`GET /api/equivalent/<mpn_key>` endpoint: for a given part it finds **one
cheaper, in-stock, drop-in** replacement (same package, matching key specs
within tolerance, healthy stock buffer) and returns a human-readable reason.
The saving is re-checked before it is claimed: candidates are found on
parametric data, then the leaders are re-read the same way the part's own page
reads them, and only a candidate that comes back genuinely cheaper and still
well stocked is offered.

If it cannot verify a real match, it says so honestly (`equivalent: null` with a
reason) rather than guessing. In v1 the matcher covers **resistors and
capacitors** (the component types with queryable parametric specs upstream).
Everything else returns an honest null.

## Architecture

```
Browser  -->  Vercel (React + Vite static site)
   |
   +------>  Render / Fly.io (FastAPI)  ->  jlcsearch API (jlcparts snapshot)
                     |
                     +-- SQLite cache (long TTL for specs, short for stock/price)
```

- **Frontend.** React + Vite SPA. Inline design system, React Router.
- **Backend.** FastAPI (async, Python 3.11+). Each distributor sits behind a
  `DistributorAdapter` (`backend/services/adapters/`), so the official LCSC API
  can be dropped in later without rewriting the app. The older single-source
  `PartDataSource` abstraction was removed when multi-distributor landed.
- **Cache.** SQLite. Specs cache long (they never change); stock and price cache
  short (hours) and refresh on demand. Every cached record keeps an `as_of`
  timestamp, reported honestly to the UI.
- **Data source.** The free, open **jlcsearch** API (tscircuit / jlcparts
  ecosystem). No account or key required. 
  
  >*Note: it is a ~daily jlcparts snapshot, not live LCSC stock and price.*

## Repo layout
```
/
├── backend/     # FastAPI app (see backend/README.md for full detail)
├── frontend/    # React + Vite app
├── docs/        # spec, jlcsearch notes, design docs
└── README.md 
```

---

## Endpoints

| Endpoint | Returns |
|---|---|
| `GET /api/search?q=<query>&page=1` | `{ "page": N, "results": [...] }` with lcsc, mpn, package, description, stock, price, `as_of` |
| `GET /api/part/<lcsc_code>` | Full detail: specs, footprint, pricing and stock breakdown, flags |
| `GET /api/part/<lcsc_code>/equivalent` | `original` plus one cheaper drop-in `equivalent`, or `equivalent: null` with a reason |

Full request and response shapes, error semantics, and config live in
[`backend/README.md`](backend/README.md).

---

## Local development

You will run **two processes**: the backend API and the frontend dev server. The
frontend proxies `/api` to the backend in development, so no CORS setup is needed
locally.

### Backend (Windows)

```bash
cd backend
py -3 -m venv .venv                                   # first time only (Python 3.11+)
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn main:app --reload
```

API at http://127.0.0.1:8000, interactive docs at http://127.0.0.1:8000/docs.
Run the backend tests with `.venv/Scripts/python.exe -m pytest -q`.

### Frontend

```bash
cd frontend
npm install
npm run dev      
```

Other frontend scripts: `npm run build` (production build), `npm test` (Vitest),
`npm run preview` (serve the built site).

---

## Deployment

Frontend goes on **Vercel**. The backend goes on **Render** (free, no card) or
**Fly.io** (always-on, small cost). The same `backend/Dockerfile` builds on
either backend host.

### Frontend on Vercel

1. Import the repo into Vercel and set **Root Directory** to `frontend`.
2. Add a build-time environment variable
   `VITE_API_BASE=https://<your-backend-host>/api`.
3. Vercel auto-detects Vite. The included `frontend/vercel.json` adds an SPA
   catch-all rewrite so deep links (for example `/part/C25531`) and page
   refreshes do not 404.
4. Add the new Vercel origin to `CORS_ORIGINS` on the backend host **before**
   you point anyone at the site. The backend allows exact origins only, with
   no wildcard and no pattern, so until it is listed every API call from the
   new domain is blocked by the browser and the site loads but shows nothing.

> **Preview deployments:** every Vercel preview gets its own hostname
> (`partsourcer-<hash>-<scope>.vercel.app`), and none of them are in
> `CORS_ORIGINS`, so previews cannot reach the API. That is the expected
> behaviour, not a broken build. Test against the production domain, or add a
> specific preview origin to the list while you need it.

### Backend on Render (free, recommended to start)

1. New **Web Service**, connect the repo, set root to `backend`, environment
   **Docker**.
2. Render reads `backend/render.yaml` (health check `/health`, free plan).
3. Set `CORS_ORIGINS` to your Vercel origin (see the env note below).
4. **Heads-up:** the free plan **spins down after ~15 min idle**, so the first
   request after a quiet period takes roughly 30 to 60 seconds to wake the
   container. The SQLite cache is ephemeral here and simply re-warms from
   upstream after each restart, so correctness is unaffected (stale data is
   never served).

### Backend on Fly.io (always-on)

1. `fly launch` uses `backend/fly.toml`, a single always-on machine
   (`min_machines_running=1`, no cold starts) with a persistent volume mounted
   at `/data` so the cache stays warm across restarts.
2. Set `CORS_ORIGINS` to your Vercel origin.
3. Fly requires a card on file. A minimal `shared-cpu-1x` machine plus small
   volume is inexpensive.

### Environment variables

| Var | Where | Value |
|---|---|---|
| `VITE_API_BASE` | Vercel (build-time) | `https://<backend-host>/api` |
| `CORS_ORIGINS` | Backend host | **JSON array**, e.g. `["https://partsourcer.vercel.app"]` |
| `SQLITE_PATH` | Backend host | `/data/partsourcer.db` on Fly, default (ephemeral) on Render |

> **Gotcha:** `CORS_ORIGINS` is parsed as JSON, so it must be a JSON array
> string, `["https://your-app.vercel.app"]`, not a bare or comma-separated
> value. It is also an exact-match allowlist: the scheme, host and any port
> must match what the browser sends, and a trailing slash breaks it. List every
> origin you want to serve, including an old one you are migrating away from if
> you want both live at once. The full backend config table is in
> [`backend/README.md`](backend/README.md).

> **Security:** never put a secret in a `VITE_`-prefixed variable. Vite bakes
> those into the public browser bundle. Server-side secrets (for example a future
> official LCSC API key) belong only in the backend host's environment, never in
> the frontend and never committed.

---

## Honesty principles

These are load-bearing, not marketing:

- **Never fake or stale-serve stock and price.** Every record carries an `as_of`
  timestamp and the UI shows it. If the upstream is down and the cache is stale,
  the API errors rather than lying about freshness.
- **Never overstate a match.** Two parts are only called "equivalent" when the
  package and core specs genuinely match. Unverifiable matches return an honest
  null, never a guess.
- **Never compare two prices fetched differently.** Upstream hands back
  different prices and stock for the same part depending on which endpoint is
  asked and how, by up to 6x, so a cross-basis comparison is not a comparison.
  Candidates are ranked on parametric data and then re-read on the one
  canonical path before any saving is published, and both sides of the
  percentage come from that path. The same rule governs what a page shows: one
  cached offer row is one answer until it expires, nothing overwrites a fresh
  row, and every surface reads that row, so a price cannot change under a user
  who merely clicked through. Details in `docs/jlcsearch-notes.md`.
- **Never invent a price.** A distributor that published no price gives us
  `null`, never `0.0`. A zero would read as free, and it would win the cheapest
  comparison outright. An unpriced offer is excluded from the cheapest claim
  and from the equivalent matcher, and the UI says "no price" rather than
  showing a blank or a `$0.0000`.
- **Show what is missing.** `brand` and `datasheet_url` are absent from
  jlcsearch, so a part only LCSC answered for carries neither. Mouser and
  DigiKey do supply them, so on a merged part they are usually present. The UI
  renders each only where it exists and omits the line entirely otherwise,
  rather than showing a blank row or inventing a placeholder.

## Contributing

Issues and PRs welcome at
[github.com/yaasshh09/PartSourcer](https://github.com/yaasshh09/PartSourcer).
The data layer is intentionally swappable, so the most valuable contribution is
wiring in the official LCSC API behind the existing `DistributorAdapter`
abstraction.

## License

[MIT](LICENSE) © Yash Gupta
