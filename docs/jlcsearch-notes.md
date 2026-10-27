# jlcsearch API: Reference & Field Mapping

> Notes on the backend's LCSC data source, written from live requests on
> 2026-07-10. Sample responses live in `docs/api-samples/`.

**Base URL:** `https://jlcsearch.tscircuit.com`

All endpoints read from **one backing database**, the open [`yaqwsx/jlcparts`](https://github.com/yaqwsx/jlcparts) dataset that jlcsearch (tscircuit) serves over HTTP. There is no OpenAPI spec (`/openapi.json` → 404) and no per-part detail endpoint (`/api/component/<id>` variants → 404).

---

## Endpoints (verified)

| Purpose | Endpoint | Method | Key query params | Envelope key |
|---|---|---|---|---|
| Full-text / MPN / LCSC search | `/api/search?q=<query>` | GET | `q` (query), `limit` (max rows). **`page` is ignored.** | `components` |
| Resistor parametric | `/resistors/list.json?package=<pkg>&resistance=<val>` | GET | `package`, `resistance` (e.g. `10k`) | `resistors` |
| Capacitor parametric | `/capacitors/list.json?package=<pkg>` | GET | `package` (and other spec filters) | `capacitors` |

Each response is `{ "<envelope key>": [ {...}, ... ] }`. Parametric endpoints follow the pattern `/<component-type>/list.json`, and the same shape exists for other component types (the equivalent matcher reads them).

### Verified per-item fields

**`/api/search` → `components[]`:**
`lcsc` (int), `mfr` (str = MPN), `package` (str), `is_basic` (bool), `is_preferred` (bool), `description` (str, usually empty), `stock` (int), `price` (float, unit price).

**`/resistors/list.json` → `resistors[]`:**
`lcsc`, `mfr`, `description`, `stock`, `price1` (float), `in_stock` (bool), `resistance` (number, ohms), `tolerance_fraction` (e.g. `0.01` = ±1%), `power_watts`, `package`, `max_overload_voltage`, `number_of_resistors`, `number_of_pins`, `is_potentiometer`, `is_surface_mount`, `is_multi_resistor_chip`, `is_basic`, `is_preferred`, `attributes` (JSON-encoded string).

**`/capacitors/list.json` → `capacitors[]`:**
`lcsc`, `mfr`, `description`, `stock`, `price1`, `in_stock`, `capacitance_farads` (float, e.g. `1e-07` = 100 nF), `tolerance_fraction`, `voltage_rating` (number, V), `package`, `temperature_coefficient` (str, e.g. `X7R`), `lifetime_hours`, `esr_ohms`, `ripple_current_amps`, `is_polarized`, `is_surface_mount`, `capacitor_type`, `is_basic`, `is_preferred`, `attributes` (JSON-encoded string).

---

## Field mapping to our part model

Our search result maps from upstream as follows:

| Our field | Source | Transform / notes |
|---|---|---|
| `lcsc` | `lcsc` (int) | Prefix with `C` → `"C" + str(lcsc)` (e.g. `8734` → `"C8734"`). Upstream is a bare integer. |
| `mpn` | `mfr` | Direct. `mfr` **is the manufacturer part number**, not the maker. |
| `brand` | n/a | **`null`.** No manufacturer-name field exists upstream. Documented gap; do not guess from the MPN prefix. |
| `package` | `package` | Direct (e.g. `"LQFP-48(7x7)"`, `"0402"`). |
| `description` | `description` | Direct, but **usually empty** in this dataset. May compose from specs later if needed. |
| `stock` | `stock` | Direct (int). |
| `price_usd` | `price` (search) / `price1` (parametric) | **Assumed USD**, the field is unlabeled. Flag as an assumption; confirm if the official LCSC API is added later. |
| `datasheet_url` | n/a | **`null`.** Not present anywhere in the API. See fallbacks below. |
| `as_of` | *(none)* | Set by **our backend** to the real fetch time (ISO-8601, UTC). Not provided upstream. |

### `datasheet_url` fallbacks (documented, not used in v1)
- **Product-detail link (derivable):** `https://jlcpcb.com/partdetail/C<lcsc>` returns HTTP 200. This is a **product page, not a datasheet PDF**, so only use it if the UI labels it "product page", never "datasheet". (LCSC's own `lcsc.com/product-detail/...` returned 403, bot-blocked.)
- **jlcparts dataset:** the underlying `yaqwsx/jlcparts` database **does** carry real datasheet URLs; jlcsearch just doesn't expose them over these endpoints. This is the honest long-term source, aligned with the "swap the data layer later" plan.

---

## Gotchas

- **`lcsc` is an integer**, not `"C…"`. Always format with a `C` prefix for our API and for building links.
- **`description` is usually empty**, so don't rely on it for display.
- **`page` is ignored** by `/api/search`; only `limit` narrows the result set. Our `?page=N` pagination must be implemented in **our** layer (e.g. fetch with a limit and slice, or window client-side), not delegated upstream.
- **`attributes` is a JSON-encoded *string***, not a nested object, so it requires a second `json.loads(...)`. Example (resistor): `"{\"Resistance\":\"10Ω\",\"Power(Watts)\":\"62.5mW\",...}"`.
- **`in_stock`** (bool) accompanies parametric rows alongside the numeric `stock`.
- **Price field name differs:** `price` on search, `price1` on parametric endpoints.
- **No per-part detail endpoint**, so `/api/part/<code>` assembles detail from the search/parametric data, not a dedicated upstream detail call.

---

## Data freshness

**None of these endpoints are live-to-the-second.** They all serve the same periodic **jlcparts snapshot**, which is synced from LCSC roughly daily, not a live feed from LCSC's warehouse.

Consequences:
- There is **no "more real-time" endpoint** to choose: same DB, same freshness.
- Our `as_of` timestamp honestly means *"PartSourcer fetched this from jlcsearch at time X"*. It does **not** mean the stock/price is live at X. True freshness is bounded by jlcparts' last upstream sync.
- The UI's "data as of X" note is correct, but must **not** imply the numbers are live-from-LCSC. This is why the caching rule keeps a short TTL on stock/price and a long TTL on specs.

---

## Matcher-relevant fields

The parametric endpoints give clean, filterable specs, the equivalent-matcher's core input:

- **Resistor:** `resistance` (ohms), `tolerance_fraction`, `power_watts`, `package`. Filter via `?package=&resistance=`.
- **Capacitor:** `capacitance_farads`, `voltage_rating` (V), `tolerance_fraction`, `temperature_coefficient` (dielectric, e.g. `X7R`), `package`. Filter via `?package=` only (see gotchas: value filter does NOT work).

These map onto the matcher rules (same package hard requirement; exact resistance/capacitance; equal-or-tighter tolerance; equal-or-higher power/voltage; equal-or-better dielectric).

### Verified upstream constraints (live-probed 2026-07-11)

These four facts hard-shape the matcher design, all confirmed against live upstream:

1. **`limit` is hard-capped at 100** on parametric endpoints. `?limit=1000` and `?limit=100000` both return exactly 100 rows. There is no visible offset/pagination param. **A parametric query can only ever see the top 100 rows** (appears stock-sorted). Consequence: the matcher sees the highest-stock 100 candidates for a given filter, good for finding a cheap in-stock part, but it cannot enumerate an entire package.
2. **`resistance` must be queried in RAW OHMS.** `?resistance=10000` correctly returns 10 kΩ parts (stored `resistance` field = `10000`). `?resistance=10k` is **buggy upstream**: it returns 10 Ω parts (`resistance=10`), silently wrong. Always format the query value as an integer ohm string; never use `k`/`M` suffixes.
3. **The capacitance filter works, but only in farads.** `?capacitance=100nF` returns **0 rows**, while `?capacitance=1e-7` returns the 100nF parts (verified 2026-09-27; this note used to say the filter was broken). Likewise `?resistance=10k` is read as **10 ohms**, so send `10000`. Browse converts typed values in `services/units.py`. The matcher sends `?capacitance=` in farads for its candidate pool and still checks `capacitance_farads` in memory, since upstream matches the filter with some slack (`1e-07`, `1.0000000000000001e-07` and `0.0000001` all return the 100nF rows, checked 2026-10-27).
4. **`lcsc` is ignored as a filter** on parametric endpoints (same as `page` on `/api/search`): `?lcsc=25077` returns the default list, not that part. You cannot look a part up by code parametrically; to read a specific part's specs you must fetch a list it is in and scan for the `lcsc`. The matcher reads the value off the part's description (`10kΩ`, `100nF`) and fetches that value's list first, falling back to the bare `?package=` list. On 2026-10-27 C25804 (10k 0603) was in the `resistance=10000` list and not in the unfiltered 0603 one.

**Also confirmed:** `resistance` is stored in raw ohms (10 kΩ → `10000`); `capacitance_farads` is a float with FP noise (100 nF → `1.0000000000000001e-07`) so exact match needs a relative epsilon; `price1` (not `price`) is the parametric unit-price field; `in_stock` (bool) rides alongside numeric `stock`.

### The price basis problem (live-probed 2026-08-19)

**One part does not have one price upstream. It has at least two, and which
one you get depends on how you asked.** This is the single most important
thing to know before touching pricing here.

Probed against live jlcsearch, all within the same minute:

- `/api/search?q=0603WAF1001T5E&limit=1` returns `price` 0.0039, `stock` 8,013,731.
- The same query at `limit=40` returns `price` 0.000928571, `stock` 15,873,089.
- `/resistors/list.json` returns `price1` 0.000928571 for that same code.

It is not randomness: 20 identical requests give 20 identical answers, per
`(query, limit)` pair. It is also not monotonic in `limit`, so it cannot be
reasoned about as a depth: for that part, limits 2, 10, 30 and 40 give one
record while 1, 5, 19, 20, 21, 25, 39, 50 and 100 give the other. The shape
fits a join or aggregate upstream whose row selection shifts with the query
plan, and `limit` perturbs the plan.

Size of the gap, measured over 15 real 0603 1k resistors: the search price
was never below the parametric price, equal for 3 of 14 and higher for 11,
median 1.48x, max 4.20x. Comparing the detail page's read (`q=<mpn>&limit=40`)
against the parametric price for the same parts, 13 of 14 disagreed, by 1.29x
to 6.06x. Stock diverges just as hard: one part read 3,441,343 parametrically
and 19 on the search path.

It is not only the matcher that this reaches. Search asks upstream with the
user's words and the detail page asks with the MPN, both at `FETCH_DEPTH`, and
measured over 8 realistic queries **39 of 160 search cards (24.4%) disagreed
with their own part page**. It clusters: `LM358` disagreed on 20 of 20 and
`NE555` on 16 of 20, while `STM32F103`, `100nF 0402`, `10k 0805` and `ESP32`
were clean.

**The rule this forces:** never compare or co-display two prices fetched
differently, and never let a second reading quietly replace one a user is
already looking at. A cached offer row is one answer until it expires: nothing
overwrites a fresh row, whoever fetched it, and every surface reads that row.
`?refresh=true` replaces it, and then all surfaces move together. In the backend that means one canonical read,
`LcscMatcherSource.canonical_part`, which goes through `lookup_mpn` at
`FETCH_DEPTH`, exactly as the offer cache behind search and detail does.
Everything a user sees or a percentage is computed from comes from there.
`lookup_sku` still resolves a bare code to an MPN, because nothing else can,
but its price is discarded. Parametric rows still pick and rank candidates,
because only they carry specs, but their prices never reach a user.

Before this rule the equivalent matcher compared a search-path original
against parametric candidates, which inflated every published saving: over 24
real parts the mean claim was 70% where the honest same-basis figure was 52%,
with individual claims of 82% (true 12%), 94% (true 32%) and 26% (true 3%).

**Direct consequence for the v1 matcher:** honest matching is limited to **resistors and capacitors** (the only types with queryable specs). ICs and everything else carry no parametric specs here, so they return `equivalent: null` with a clear reason, never a guessed "similar part." A part's own specs are only recoverable if it appears in the top 100 of its value's list (or, failing a readable value, of its package list); otherwise the matcher honestly reports it could not identify the part's specs.

---

## Getting realtime data

The LCSC side trades live-to-the-second data for a free, open, no-approval,
parametric source. Ways to get live data, in order of fit:

1. **Official LCSC API**: the intended swap. Live LCSC stock and price. Needs an LCSC business account and an application, which is slow, so nothing waits on it. It drops in behind the `DistributorAdapter` interface without rewriting the backend.
2. **Distributor APIs**: Mouser and DigiKey already have their own adapters and answer in real time when credentials are set. **Octopart / Nexar (Altium)** aggregates many distributors in one call, with a free tier capped by monthly queries.
3. **Scraping LCSC directly: do not.** LCSC already bot-blocks it (403).

---

## 2026-10-11: `/api/search` returns unrelated parts

Measured, not guessed. Every fresh (`x-cache: MISS`) answer from `/api/search`
was wrong: 9 of 9 queries. A search for `STM32F103CBT6` came back as two
capacitors, `NE555DR` as connectors and inductors. The only correct answers
left were old Cloudflare cache entries from before the break, which is why the
same query looked right at one `limit` and wrong at another.

Cause, from upstream's own source (`cf-proxy/src/search.ts` and
`cf-proxy/scripts/rebuild-search-index-from-component-catalog.sql`): search
joins `search_index_fts` to `search_index` on `rowid`, and the rebuild script
does `DROP TABLE search_index; CREATE TABLE search_index AS SELECT ...`, which
hands out new rowids. Unless the FTS table is rebuilt after, every text match
lands on whatever row now holds that rowid. Code lookups (`q=C8734`) skip the
join but also came back empty for most parts, so the table itself looks short
of rows. Upstream changed its nightly sync on 2026-10-09 and 10.

The parametric endpoints (`/resistors/list.json` and friends) were fine, so
browse and the matcher's candidate pool are unaffected.

What we do about it: `LcscAdapter.search` drops a row that names none of the
query's words in its MPN, package or description, and reports LCSC as
`unavailable` when every row was unrelated, so the UI says so rather than
showing junk or an empty "no results". The check is deliberately loose (one
word is enough) because upstream also matches category, manufacturer and
attribute text we never receive. `lookup_mpn` is not filtered.

What it still costs while upstream is broken: LCSC drops out of most searches,
a cold part page for an LCSC-only part 404s, and the equivalent matcher's
canonical re-read mostly finds nothing, so it answers with an honest null.

Re-checked 2026-10-25: still broken. `search=STM32F103C8T6` returns three
unrelated parts and `RC0402FR-0710KL` returns none. Code lookups are patchy:
`C8734` resolves, `C25744` (0402WGF1002TCE) and `C307331` return nothing. Live
`/api/equivalent` for 0402WGF1002TCE, CL05B104KO5NNNC and 0603WAF1002T5E all
answer "no LCSC listing". tscircuit/jlcsearch#611 is open with no maintainer
reply.

## 2026-10-24: why equivalents stop at resistors and capacitors

Measured against live `/mosfets`, `/diodes` and `/leds` list endpoints while
scoping equivalents for more part types. The parametric fields are not
reliable enough to call anything a drop-in:

- **MOSFETs.** `continuous_drain_current` disagrees with the same row's own
  `attributes` JSON on 12 of 83 SOT-23 rows, 7 of 54 SOP-8 and 6 of 59
  TO-252 (10 to 14%). Example: 2N7002K has `continuous_drain_current: 0.5`
  while its attributes say `300mA`. N or P channel and RDS(on) exist only in
  the description and the attributes, under two different key spellings in
  the same row. Same package does not settle pinout either.
- **Diodes.** Of 69 SOD-123 parts with Zener part numbers (BZT, MMSZ, BZX),
  33 are flagged `is_zener`. BZT52C5V6 is typed `general_purpose`. Forward and
  reverse voltage are filled on 4 of 100 rows.
- **LEDs.** `/leds/list.json?package=0603` returns 14 rows in total, and
  `forward_voltage` is filled on 1 of them, so a pool is too small to find a
  cheaper match and too sparse to check one.
- **LDOs.** Not attempted: same package does not mean the same pinout
  (SOT-23-5 regulators put enable and bypass on different pins), and nothing
  in the data records it.

A matcher reading these fields would publish wrong drop-ins, so the
equivalent route keeps its honest null for every other type. Revisit with the
official LCSC API or a cleaner source; the attributes JSON would need its own
parser and a per-type spec list before any type is added.
