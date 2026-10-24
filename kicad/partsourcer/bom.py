"""Read a board's parts into the list the PartSourcer BOM check takes.

Kept free of pcbnew so it can be tested without KiCad: it only needs objects
with the few footprint methods used below, which KiCad 7, 8 and 9 all have
in one form or another.
"""

from urllib.parse import quote

SITE = "https://part-sourcer.vercel.app"
MAX_LINES = 40     # the site's cap per check

# Part number fields as people name them, best first. An LCSC code works as
# well as a manufacturer number, since the site finds a part by either.
PART_FIELDS = ("mpn", "manufacturer part number", "manufacturer_part_number", "mfr part number",
               "mfr. part #", "mfr pn", "pn", "lcsc", "lcsc part", "lcsc part #",
               "lcsc part number", "jlcpcb part #", "jlc part")


def fields_of(fp) -> dict:
    """Field name to text, lower-cased names. KiCad 8 and later have real
    fields; KiCad 7 keeps the same data as footprint properties."""
    out = {}
    if hasattr(fp, "GetFields"):
        for f in fp.GetFields():
            out[str(f.GetName()).strip().lower()] = str(f.GetText()).strip()
    elif hasattr(fp, "GetProperties"):
        for k, v in dict(fp.GetProperties()).items():
            out[str(k).strip().lower()] = str(v).strip()
    return out


def _skipped(fp) -> bool:
    for name in ("IsDNP", "IsExcludedFromBOM"):
        check = getattr(fp, name, None)
        if check is not None and check():
            return True
    return False


def collect(footprints):
    """(lines, missing): one line per part number with its count and
    designators, and the references that carry no part number at all."""
    lines, missing = {}, []
    for fp in footprints:
        if _skipped(fp):
            continue
        ref = str(fp.GetReference())
        fields = fields_of(fp)
        mpn = next((fields[k] for k in PART_FIELDS if fields.get(k)), "")
        if not mpn or mpn in ("~", "-"):
            missing.append(ref)
            continue
        key = mpn.upper()
        line = lines.setdefault(key, {"mpn": key, "qty": 0, "refs": []})
        line["qty"] += 1
        line["refs"].append(ref)
    return list(lines.values()), sorted(missing)


def bom_text(lines) -> str:
    """CSV with a header the site's parser reads, designators quoted whole."""
    rows = ["MPN,Qty,Designator"]
    for line in lines:
        rows.append(f'{line["mpn"]},{line["qty"]},"{",".join(sorted(line["refs"]))}"')
    return "\n".join(rows)


def bom_url(lines, boards: int = 1, site: str = SITE) -> str:
    extra = f"&boards={boards}" if boards > 1 else ""
    return f"{site.rstrip('/')}/bom?list={quote(bom_text(lines), safe='')}{extra}"
