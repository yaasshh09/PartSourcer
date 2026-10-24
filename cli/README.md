# partsourcer CLI

Price a BOM from a terminal on the same rules as the site's BOM check. One
file, standard library only, Python 3.9 or newer.

```bash
python cli/partsourcer.py check bom.csv
python cli/partsourcer.py check bom.csv --boards 10 --swaps
python cli/partsourcer.py check bom.csv --json > priced.json
cat parts.txt | python cli/partsourcer.py check -
```

It reads the same files the site does: KiCad, Altium and JLCPCB exports by
their headers, or a plain list of part numbers with optional quantities.
Each line is priced at its quantity from the cheapest offer that has the part
number exactly, publishes a USD price, and holds enough stock for what you
would actually order (a minimum order counts). Unpriced offers are never
treated as free.

| Exit code | Meaning |
|---|---|
| 0 | every line can be bought |
| 1 | at least one line cannot (not found, no price, not enough stock) |
| 2 | the check itself failed (bad file, API unreachable) |

`PARTSOURCER_API` points it at another deployment, for example
`http://127.0.0.1:8000/api` for a local backend. Lines are read one at a time
and a `429` is retried once after its `Retry-After`, since the API allows 60
reads a minute. At most 40 lines per run, as on the site.

Tests: `python -m pytest cli -q`.
