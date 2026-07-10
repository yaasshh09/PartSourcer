# jlcsearch API — Reference & Field Mapping

> Real, verified notes for the PartSourcer backend data source. Written from live
> requests on 2026-07-10. Source of truth for building the datasource abstraction
> and `/api/search` (Prompt 3). Sample responses live in `docs/api-samples/`.

**Base URL:** `https://jlcsearch.tscircuit.com`

All endpoints read from **one backing database** — the open [`yaqwsx/jlcparts`](https://github.com/yaqwsx/jlcparts) dataset that jlcsearch (tscircuit) serves over HTTP. There is no OpenAPI spec (`/openapi.json` → 404) and no per-part detail endpoint (`/api/component/<id>` variants → 404).

---

## Endpoints (verified)

| Purpose | Endpoint | Method | Key query params | Envelope key |
|---|---|---|---|---|
| Full-text / MPN / LCSC search | `/api/search?q=<query>` | GET | `q` (query), `limit` (max rows). **`page` is ignored.** | `components` |
| Resistor parametric | `/resistors/list.json?package=<pkg>&resistance=<val>` | GET | `package`, `resistance` (e.g. `10k`) | `resistors` |
| Capacitor parametric | `/capacitors/list.json?package=<pkg>` | GET | `package` (and other spec filters) | `capacitors` |

Each response is `{ "<envelope key>": [ {...}, ... ] }`. Parametric endpoints follow the pattern `/<component-type>/list.json` — the same shape exists for other component types (used later by the equivalent-matcher, Prompt 6).

### Verified per-item fields

**`/api/search` → `components[]`:**
`lcsc` (int), `mfr` (str = MPN), `package` (str), `is_basic` (bool), `is_preferred` (bool), `description` (str, usually empty), `stock` (int), `price` (float, unit price).

**`/resistors/list.json` → `resistors[]`:**
`lcsc`, `mfr`, `description`, `stock`, `price1` (float), `in_stock` (bool), `resistance` (number, ohms), `tolerance_fraction` (e.g. `0.01` = ±1%), `power_watts`, `package`, `max_overload_voltage`, `number_of_resistors`, `number_of_pins`, `is_potentiometer`, `is_surface_mount`, `is_multi_resistor_chip`, `is_basic`, `is_preferred`, `attributes` (JSON-encoded string).

**`/capacitors/list.json` → `capacitors[]`:**
`lcsc`, `mfr`, `description`, `stock`, `price1`, `in_stock`, `capacitance_farads` (float, e.g. `1e-07` = 100 nF), `tolerance_fraction`, `voltage_rating` (number, V), `package`, `temperature_coefficient` (str, e.g. `X7R`), `lifetime_hours`, `esr_ohms`, `ripple_current_amps`, `is_polarized`, `is_surface_mount`, `capacitor_type`, `is_basic`, `is_preferred`, `attributes` (JSON-encoded string).

---

## Field mapping → section-9 schema

Our internal search result (spec §9) maps from upstream as follows:

| Section-9 field | Source | Transform / notes |
|---|---|---|
| `lcsc` | `lcsc` (int) | Prefix with `C` → `"C" + str(lcsc)` (e.g. `8734` → `"C8734"`). Upstream is a bare integer. |
| `mpn` | `mfr` | Direct. `mfr` **is the manufacturer part number**, not the maker. |
| `brand` | — | **`null`.** No manufacturer-name field exists upstream. Documented gap; do not guess from the MPN prefix (honesty, §5). |
| `package` | `package` | Direct (e.g. `"LQFP-48(7x7)"`, `"0402"`). |
| `description` | `description` | Direct, but **usually empty** in this dataset. May compose from specs later if needed. |
| `stock` | `stock` | Direct (int). |
| `price_usd` | `price` (search) / `price1` (parametric) | **Assumed USD** — the field is unlabeled. Flag as an assumption; confirm if the official LCSC API is added later. |
| `datasheet_url` | — | **`null`.** Not present anywhere in the API. See fallbacks below. |
| `as_of` | *(none)* | Set by **our backend** to the real fetch time (ISO-8601, UTC). Not provided upstream. |

### `datasheet_url` fallbacks (documented, not used in v1)
- **Product-detail link (derivable):** `https://jlcpcb.com/partdetail/C<lcsc>` returns HTTP 200. This is a **product page, not a datasheet PDF** — only use it if the UI labels it "product page", never "datasheet" (honesty, §5). (LCSC's own `lcsc.com/product-detail/...` returned 403 — bot-blocked.)
- **jlcparts dataset:** the underlying `yaqwsx/jlcparts` database **does** carry real datasheet URLs; jlcsearch just doesn't expose them over these endpoints. This is the honest long-term source, aligned with the "swap the data layer later" plan.

---

## Gotchas (read before writing the datasource)

- **`lcsc` is an integer**, not `"C…"`. Always format with a `C` prefix for our API and for building links.
- **`description` is usually empty** — don't rely on it for display.
- **`page` is ignored** by `/api/search`; only `limit` narrows the result set. Our `?page=N` pagination (spec §9) must be implemented in **our** layer (e.g. fetch with a limit and slice, or window client-side), not delegated upstream.
- **`attributes` is a JSON-encoded *string***, not a nested object — requires a second `json.loads(...)`. Example (resistor): `"{\"Resistance\":\"10Ω\",\"Power(Watts)\":\"62.5mW\",...}"`.
- **`in_stock`** (bool) accompanies parametric rows alongside the numeric `stock`.
- **Price field name differs:** `price` on search, `price1` on parametric endpoints.
- **No per-part detail endpoint** — Prompt 5 (`/api/part/<code>`) must assemble detail from the search/parametric data, not a dedicated upstream detail call.

---

## Data freshness reality (honesty, §5)

**None of these endpoints are live-to-the-second.** They all serve the same periodic **jlcparts snapshot**, which is synced from LCSC roughly daily — not a live feed from LCSC's warehouse.

Consequences:
- There is **no "more real-time" endpoint** to choose — same DB, same freshness.
- Our `as_of` timestamp honestly means *"PartSourcer fetched this from jlcsearch at time X"* — it does **not** mean the stock/price is live at X. True freshness is bounded by jlcparts' last upstream sync.
- The UI's "data as of X" note is correct, but must **not** imply the numbers are live-from-LCSC. This is why the caching rule keeps a short TTL on stock/price and a long TTL on specs.

---

## Matcher-relevant fields (for Prompt 6)

The parametric endpoints give clean, filterable specs — the equivalent-matcher's core input:

- **Resistor:** `resistance` (ohms), `tolerance_fraction`, `power_watts`, `package`. Filter via `?package=&resistance=`.
- **Capacitor:** `capacitance_farads`, `voltage_rating` (V), `tolerance_fraction`, `temperature_coefficient` (dielectric, e.g. `X7R`), `package`. Filter via `?package=` only (see gotchas — value filter does NOT work).

These map onto the §10 matcher rules (same package hard requirement; exact resistance/capacitance; equal-or-tighter tolerance; equal-or-higher power/voltage; equal-or-better dielectric).

### Verified upstream constraints (live-probed 2026-07-11, Prompt 6 de-risking)

These four facts hard-shape the matcher design — all confirmed against live upstream:

1. **`limit` is hard-capped at 100** on parametric endpoints. `?limit=1000` and `?limit=100000` both return exactly 100 rows. There is no visible offset/pagination param. **A parametric query can only ever see the top 100 rows** (appears stock-sorted). Consequence: the matcher sees the highest-stock 100 candidates for a given filter — good for finding a cheap in-stock part, but it cannot enumerate an entire package.
2. **`resistance` must be queried in RAW OHMS.** `?resistance=10000` correctly returns 10 kΩ parts (stored `resistance` field = `10000`). `?resistance=10k` is **buggy upstream** — it returns 10 Ω parts (`resistance=10`), silently wrong. Always format the query value as an integer ohm string; never use `k`/`M` suffixes.
3. **The capacitor endpoint has NO working capacitance filter.** `?capacitance=100nF` (and variants) returns **0 rows**. Capacitors can only be narrowed by `?package=`; the exact `capacitance_farads` match must be done **in memory** over the ≤100 returned rows.
4. **`lcsc` is ignored as a filter** on parametric endpoints (same as `page` on `/api/search`) — `?lcsc=25077` returns the default list, not that part. You cannot look a part up by code parametrically; to read a specific part's specs you must fetch its `?package=` list and scan for the `lcsc` (only works if it is within the top-100 rows).

**Also confirmed:** `resistance` is stored in raw ohms (10 kΩ → `10000`); `capacitance_farads` is a float with FP noise (100 nF → `1.0000000000000001e-07`) so exact match needs a relative epsilon; `price1` (not `price`) is the parametric unit-price field; `in_stock` (bool) rides alongside numeric `stock`.

**Direct consequence for the v1 matcher:** honest matching is limited to **resistors and capacitors** (the only types with queryable specs). ICs and everything else carry no parametric specs here, so they return `equivalent: null` with a clear reason — never a guessed "similar part." An arbitrary part's own specs are only recoverable if it appears in the top-100 of its package list; otherwise the matcher honestly reports it could not identify the part's specs.

---

## Getting realtime data (upgrade paths — post-v1, out of scope §6)

v1 deliberately trades live-to-the-second data for a free, open, no-approval, parametric source. When realtime is warranted, in order of fit:

1. **Official LCSC API** — the intended swap. Live LCSC stock/price. Needs an LCSC **business account + application/evaluation** (slow — spec §7 says don't block on it). Drops in behind the `PartDataSource` abstraction (Prompt 3) without rewriting the backend.
2. **Distributor / aggregator APIs** — genuinely realtime, but multi-distributor (explicitly **not** in v1, §6):
   - **Digi-Key API** — free developer program, OAuth, real-time stock/price.
   - **Mouser API** — free key, real-time search/stock/price.
   - **Octopart / Nexar API (Altium)** — aggregates many distributors' live data in one call; free tier limited by monthly queries.
3. **Scraping LCSC directly — do not.** Forbidden by spec §15; LCSC already bot-blocks (403).
