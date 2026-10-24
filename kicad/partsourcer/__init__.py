"""PartSourcer for KiCad: price the open board's parts in one click.

An action plugin for the PCB editor. It reads each footprint's part number
field, counts the parts, and opens the PartSourcer BOM check in the browser
with the list filled in, where every line is priced at its quantity and the
JLCPCB assembly BOM can be downloaded. Nothing is sent anywhere until the
browser opens the page.
"""

import webbrowser

try:
    import pcbnew
    import wx
except ImportError:          # imported outside KiCad, for instance by the tests
    pcbnew = None

from .bom import MAX_LINES, bom_url, collect

if pcbnew is not None:
    class PartSourcerPlugin(pcbnew.ActionPlugin):
        def defaults(self):
            self.name = "Price this board on PartSourcer"
            self.category = "BOM"
            self.description = ("Open the PartSourcer BOM check with every part number "
                                "on this board, counted and with designators.")
            self.show_toolbar_button = True

        def Run(self):
            lines, missing = collect(pcbnew.GetBoard().GetFootprints())
            if not lines:
                wx.MessageBox("No footprint has a part number field (MPN, Manufacturer Part "
                              "Number or LCSC). Add one in the schematic and update the PCB.",
                              "PartSourcer")
                return
            chunks = [lines[i:i + MAX_LINES] for i in range(0, len(lines), MAX_LINES)]
            notes = []
            if missing:
                shown = ", ".join(missing[:20]) + (" and more" if len(missing) > 20 else "")
                notes.append(f"{len(missing)} parts have no part number and are left out: {shown}.")
            if len(chunks) > 1:
                notes.append(f"{len(lines)} different parts is over the site's {MAX_LINES} "
                             f"per check, so it opens {len(chunks)} pages.")
            if notes:
                wx.MessageBox("\n\n".join(notes), "PartSourcer")
            for chunk in chunks:
                webbrowser.open(bom_url(chunk))

    PartSourcerPlugin().register()
