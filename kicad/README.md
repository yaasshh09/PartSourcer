# PartSourcer for KiCad

A PCB editor action plugin. One click reads the part number of every
footprint on the open board, counts them, and opens the PartSourcer BOM check
in your browser with the list filled in. There every line is priced at its
quantity across LCSC, Mouser and DigiKey, cheaper drop-ins can be found, and a
JLCPCB assembly BOM can be downloaded, since the designators come along.

## Install

Copy the `partsourcer` folder into KiCad's plugin folder, then in the PCB
editor use Tools > External Plugins > Refresh Plugins.

| OS | Plugin folder (KiCad 8; use 7.0, 9.0 or 10.0 for those versions) |
|---|---|
| Windows | `Documents\KiCad\8.0\scripting\plugins` |
| macOS | `~/Documents/KiCad/8.0/scripting/plugins` |
| Linux | `~/.local/share/kicad/8.0/scripting/plugins` |

The button "Price this board on PartSourcer" appears on the toolbar and under
Tools > External Plugins.

## What it reads

The first of these fields that has a value, case-insensitive: `MPN`,
`Manufacturer Part Number`, `Mfr Part Number`, `Mfr. Part #`, `Mfr PN`, `PN`,
`P/N`, `Part Number`, `LCSC`, `LCSC Part`, `LCSC Part #`, `LCSC Part Number`, `JLCPCB Part #`.
Footprints marked DNP or excluded from the BOM are skipped, and any without a
part number are listed in a message so nothing is left out silently. The site
checks up to 40 different parts at a time, so a bigger board opens more than
one page.

Nothing is sent anywhere until the browser opens the page, and the list
travels in the address, so it shows up in browser history.

Tests (no KiCad needed): `python -m pytest kicad -q`. The board reading has
also been run under KiCad 10.0.4's own Python on its StickHub and CM5 demo
boards, which is where the `P/N` field came from. The toolbar button itself
has not been clicked in a running KiCad yet.
