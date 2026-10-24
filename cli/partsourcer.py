#!/usr/bin/env python3
"""Check a BOM against PartSourcer from a terminal.

    python partsourcer.py check bom.csv [--boards 5] [--json] [--swaps]

Standard library only, so it runs anywhere Python 3.9+ does. Each line is
priced at its quantity on the same rules the website's BOM check uses: exact
part number, USD, a published price, and enough stock for what you would
actually order. Exit code 0 means every line can be bought, 1 means at least
one cannot, 2 means the check itself failed.
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("PARTSOURCER_API", "https://part-sourcer.vercel.app/api").rstrip("/")
MAX_LINES = 40          # the site's cap; the API allows 60 reads a minute
PRECEDENCE = ["lcsc", "mouser", "digikey"]
LABEL = {"lcsc": "LCSC", "mouser": "Mouser", "digikey": "DigiKey"}

MPN_HEADERS = {"mpn", "part number", "part no", "part #", "manufacturer part number",
               "manufacturer part", "mfr part number", "mfr. part number", "mfr part #", "mfr. #",
               "mfg part number", "mfr pn", "manufacturer part number 1", "lcsc", "lcsc part",
               "lcsc part #", "lcsc part number", "jlcpcb part #", "jlcpcb part"}
QTY_HEADERS = {"qty", "qty.", "quantity", "quantity per pcb", "qty per board"}
REF_HEADERS = {"reference", "references", "ref", "designator", "designators"}
HEADER_WORDS = MPN_HEADERS | QTY_HEADERS | REF_HEADERS | {
    "part", "mfr", "value", "footprint", "description", "comment"}


class CheckFailed(Exception):
    pass


def _header(t):
    t = re.sub(r"[(（][^)）]*[)）]", "", t.lower())
    return t.replace("_", " ").strip()


def _is_qty(t):
    return t.isdigit() and int(t) > 0


def _cells(line):
    sep = next((s for s in ("\t", ",", ";") if s in line), None)
    if sep is None:
        return None, line.split()
    out, cur, quoted = [], "", False
    for ch in line:
        if ch == '"':
            quoted = not quoted
        elif ch == sep and not quoted:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return sep, [c.strip() for c in out]


def parse_bom(text):
    """Same reading as the site: a header row picks the columns, otherwise the
    first cell that is not a quantity is the part. Repeats add up."""
    lines, cols = {}, None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        sep, row = _cells(line)
        lower = [_header(c) for c in row]
        if any(c in HEADER_WORDS for c in lower):
            mpn_col = next((i for i, c in enumerate(lower) if c in MPN_HEADERS),
                           lower.index("part") if "part" in lower else -1)
            if sep and mpn_col < 0:
                raise CheckFailed("The header row names no part number column.")
            cols = {"mpn": mpn_col,
                    "qty": next((i for i, c in enumerate(lower) if c in QTY_HEADERS), -1),
                    "ref": next((i for i, c in enumerate(lower) if c in REF_HEADERS), -1)} if sep else None
            continue
        toks = [t for t in row if t]
        if cols and sep:
            mpn = row[cols["mpn"]] if cols["mpn"] < len(row) else ""
            q = row[cols["qty"]] if 0 <= cols["qty"] < len(row) else ""
            if not _is_qty(q):
                # With no quantity column, one part per designator is the count.
                refs = row[cols["ref"]] if 0 <= cols["ref"] < len(row) else ""
                n = len([r for r in re.split(r"[\s,;]+", refs) if r])
                q = str(n) if cols["qty"] < 0 and n else ""
        else:
            mpn = next((t for t in toks if not _is_qty(t)), "")
            q = next((t for t in toks if _is_qty(t)), "")
        if not mpn:
            continue
        key = mpn.upper()
        lines[key] = lines.get(key, 0) + (int(q) if q else 1)
    return [{"mpn": k, "qty": v} for k, v in lines.items()]


def price_at(offer, qty):
    """(unit, order_qty, total, note) for one offer at a quantity, or None
    when the distributor published no price. Never a zero for a gap."""
    breaks = sorted((b for b in offer.get("price_breaks") or []
                     if b and b.get("price_usd") is not None and b.get("qty", 0) > 0),
                    key=lambda b: b["qty"])
    if breaks:
        if qty < breaks[0]["qty"]:
            b = breaks[0]
            return b["price_usd"], b["qty"], b["price_usd"] * b["qty"], f"minimum order {b['qty']}"
        b = [x for x in breaks if x["qty"] <= qty][-1]
        return b["price_usd"], qty, b["price_usd"] * qty, ""
    if offer.get("price_usd") is None:
        return None
    return offer["price_usd"], qty, offer["price_usd"] * qty, "no quantity breaks published"


def check_line(part, qty):
    usable = [o for o in part.get("offers") or []
              if o.get("match_tier") == "exact" and o.get("currency") == "USD"]
    priced = [(o, p) for o in usable if (p := price_at(o, qty)) is not None]
    if not priced:
        return {"state": "unpriced"}
    fits = [(o, p) for o, p in priced if o.get("in_stock") and o.get("stock", 0) >= p[1]]
    if not fits:
        return {"state": "short", "best_stock": max((o.get("stock") or 0) for o in usable)}

    def rank(f):
        d = f[0]["distributor"]
        return f[1][2], PRECEDENCE.index(d) if d in PRECEDENCE else len(PRECEDENCE)
    o, (unit, order_qty, total, note) = min(fits, key=rank)
    return {"state": "ok", "distributor": o["distributor"], "sku": o.get("sku", ""),
            "unit": unit, "order_qty": order_qty, "total": total, "note": note,
            "stock": o.get("stock", 0), "as_of": o.get("as_of")}


def get_json(path, retries=1):
    req = urllib.request.Request(f"{API}{path}", headers={"Accept": "application/json",
                                                         "User-Agent": "partsourcer-cli"})
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code == 429 and retries:
            time.sleep(min(int(e.headers.get("Retry-After") or 5), 60))
            return get_json(path, retries - 1)
        try:
            detail = json.loads(e.read().decode("utf-8")).get("detail")
        except Exception:                              # noqa: BLE001
            detail = None
        raise CheckFailed(detail or f"HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise CheckFailed(f"Could not reach {API}: {e}") from e


def check(lines, boards=1, swaps=False, fetch=get_json):
    rows = []
    for line in lines:
        qty = line["qty"] * boards
        try:
            data = fetch(f"/part/{urllib.parse.quote(line['mpn'], safe='')}")
        except CheckFailed as e:
            rows.append({"mpn": line["mpn"], "qty": qty, "state": "error", "detail": str(e)})
            continue
        row = {"mpn": line["mpn"], "qty": qty}
        row.update(check_line(data["part"], qty) if data else {"state": "missing"})
        if swaps and data:
            try:
                eq = fetch(f"/equivalent/{urllib.parse.quote(data['part']['mpn_key'], safe='')}")
            except CheckFailed:
                eq = None
            if eq and eq.get("equivalent"):
                e = eq["equivalent"]
                row["swap"] = {"mpn": e["mpn"], "lcsc": e.get("lcsc"),
                               "percent_cheaper": e.get("percent_cheaper"),
                               "reason": e.get("match_reason")}
        rows.append(row)
    return rows


STATE = {"ok": "ok", "short": "not enough stock", "unpriced": "no price",
         "missing": "not found", "error": "could not check"}


def money(v):
    return f"${v:.4f}" if v < 1 else f"${v:.2f}"


def render(rows):
    out = [f"{'MPN':<24} {'QTY':>6}  {'STATUS':<17} {'FROM':<8} {'UNIT':>9} {'TOTAL':>10}  NOTE"]
    total, oldest = 0.0, None
    for r in rows:
        if r["state"] == "ok":
            total += r["total"]
            # Oldest, not newest: the total is only as fresh as its stalest line.
            if r.get("as_of") and (oldest is None or r["as_of"] < oldest):
                oldest = r["as_of"]
            out.append(f"{r['mpn']:<24} {r['qty']:>6}  {'ok':<17} {LABEL.get(r['distributor'], r['distributor']):<8}"
                       f" {money(r['unit']):>9} {money(r['total']):>10}  {r['note']}")
        else:
            extra = r.get("detail") or (f"best stock {r['best_stock']}" if r["state"] == "short" else "")
            out.append(f"{r['mpn']:<24} {r['qty']:>6}  {STATE[r['state']]:<17} {'-':<8} {'-':>9} {'-':>10}  {extra}")
        if r.get("swap"):
            s = r["swap"]
            out.append(f"  -> cheaper drop-in {s['mpn']} ({s.get('lcsc') or 'no LCSC code'}),"
                       f" {s.get('percent_cheaper')}% cheaper: {s.get('reason') or ''}")
    bad = sum(1 for r in rows if r["state"] != "ok")
    out.append("")
    out.append(f"Total for the lines that can be bought: {money(total)}"
               + (f" (read {oldest})" if oldest else ""))
    if bad:
        out.append(f"{bad} of {len(rows)} lines cannot be bought as listed and are left out of the total.")
    out.append("Excludes shipping, tax and import duties. LCSC numbers are a daily snapshot, not live.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="partsourcer", description="Price a BOM against PartSourcer.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="price every line of a BOM file")
    c.add_argument("file", help="CSV, TSV or plain list; '-' reads stdin")
    c.add_argument("--boards", type=int, default=1, help="multiply every quantity by this")
    c.add_argument("--swaps", action="store_true", help="also look for a cheaper drop-in per line")
    c.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = ap.parse_args(argv)
    try:
        if args.file == "-":
            text = sys.stdin.read()
        else:
            with open(args.file, encoding="utf-8-sig") as f:
                text = f.read()
        lines = parse_bom(text)
        if not lines:
            raise CheckFailed("No parts found in that file.")
        if len(lines) > MAX_LINES:
            raise CheckFailed(f"{len(lines)} lines; the limit is {MAX_LINES}. Split the file.")
        rows = check(lines, boards=max(1, args.boards), swaps=args.swaps)
    except (CheckFailed, OSError) as e:
        print(f"partsourcer: {e}", file=sys.stderr)
        return 2
    print(json.dumps({"lines": rows}, indent=2) if args.json else render(rows))
    return 0 if all(r["state"] == "ok" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
