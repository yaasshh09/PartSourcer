# PartSourcer

Find the cheapest in-stock part for your PCB in one search.

**Live at [part-sourcer.vercel.app](https://part-sourcer.vercel.app)**

Search any electronic component and get its stock, price, footprint and
datasheet in one place. Every number is stamped with the moment it was read,
so you always know how fresh it is.

## The bit that makes it useful

For a part you searched, PartSourcer looks for **one cheaper drop-in that is
actually in stock**, and tells you why it counts as a match. Same package,
matching specs, real stock, and both prices re-read the same way before any
saving gets claimed.

If it cannot find a genuine match, it says so. It never guesses.

Right now that works for resistors and capacitors, because those are the parts
the open data upstream carries real specs for. Everything else gets an honest
"no match found".

## Some ground rules it sticks to

- No made-up stock or prices. If the data is stale, you get an error, not a
  number pretending to be fresh.
- A part with no published price says "no price", never `$0.00`. A zero would
  read as free and win every comparison.
- Missing fields are left out rather than filled with a placeholder.

## Running it yourself

You need two things going: the API and the site.

**API** (Python 3.11 or newer)

```bash
cd backend
py -3 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m uvicorn main:app --reload
```

Runs on http://127.0.0.1:8000, with docs at `/docs`.

**Site**

```bash
cd frontend
npm install
npm run dev
```

The dev server sends `/api` through to the backend, so there is nothing to
configure.

Tests: `.venv/Scripts/python.exe -m pytest -q` in `backend`, `npm test` in
`frontend`.

## What it is built on

FastAPI and React, both hosted on Vercel, with Postgres behind the price
history. Part data comes from Mouser in real time, plus an open snapshot of
the LCSC catalogue that refreshes about once a day. There is a DigiKey adapter
too, and it switches on once credentials are set.

Each distributor sits behind the same small adapter, so adding another one
does not mean rewriting anything.

```
backend/    the API
frontend/   the site
docs/       notes on the upstream data
```

## Want to help?

Issues and pull requests are welcome. The most useful thing anyone could add
is the official LCSC API behind the existing adapter.

## Licence

[MIT](LICENSE), by Yash Gupta.
