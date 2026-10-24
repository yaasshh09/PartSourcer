"""The KiCad plugin's board reading, without KiCad.

Run with: python -m pytest kicad -q
"""

from urllib.parse import parse_qs, urlparse

from partsourcer.bom import bom_text, bom_url, collect, fields_of


class Field:
    def __init__(self, name, text):
        self.name, self.text = name, text

    def GetName(self):
        return self.name

    def GetText(self):
        return self.text


class Fp8:
    """KiCad 8 and later: real fields, DNP and BOM exclusion flags."""
    def __init__(self, ref, dnp=False, excluded=False, **fields):
        self.ref, self.dnp, self.excluded = ref, dnp, excluded
        self.fields = [Field("Reference", ref), Field("Value", "x")] + [
            Field(k.replace("_", " "), v) for k, v in fields.items()]

    def GetReference(self):
        return self.ref

    def GetFields(self):
        return self.fields

    def IsDNP(self):
        return self.dnp

    def IsExcludedFromBOM(self):
        return self.excluded


class Fp7:
    """KiCad 7: the same data as properties, and no DNP flag."""
    def __init__(self, ref, props):
        self.ref, self.props = ref, props

    def GetReference(self):
        return self.ref

    def GetProperties(self):
        return self.props


def test_counts_parts_by_number_and_keeps_designators():
    lines, missing = collect([Fp8("R1", MPN="0402WGF1002TCE"), Fp8("R2", MPN="0402wgf1002tce"),
                              Fp8("U1", LCSC="C8734"), Fp8("TP1")])
    assert lines == [{"mpn": "0402WGF1002TCE", "qty": 2, "refs": ["R1", "R2"]},
                     {"mpn": "C8734", "qty": 1, "refs": ["U1"]}]
    assert missing == ["TP1"]


def test_a_manufacturer_number_wins_over_an_lcsc_code_and_dnp_parts_are_left_out():
    lines, _ = collect([Fp8("U1", MPN="NE555P", LCSC="C46749"), Fp8("U2", MPN="NE555P", dnp=True),
                        Fp8("U3", MPN="NE555P", excluded=True)])
    assert lines == [{"mpn": "NE555P", "qty": 1, "refs": ["U1"]}]


def test_a_p_slash_n_field_counts_as_a_part_number():
    # KiCad's own CM5 demo board keeps its numbers in "P/N".
    lines, missing = collect([Fp8("U1", **{"P/N": "SN74LVC1G14DBVR"}), Fp8("D1", **{"P/N": ""})])
    assert lines == [{"mpn": "SN74LVC1G14DBVR", "qty": 1, "refs": ["U1"]}]
    assert missing == ["D1"]


def test_kicad_7_properties_are_read_the_same_way():
    assert fields_of(Fp7("C1", {"Manufacturer Part Number": "CL05B104KO5NNNC"})) == {
        "manufacturer part number": "CL05B104KO5NNNC"}
    lines, _ = collect([Fp7("C1", {"Manufacturer Part Number": "CL05B104KO5NNNC"})])
    assert lines[0]["mpn"] == "CL05B104KO5NNNC"


def test_the_url_carries_a_list_the_site_parses_with_designators_whole():
    lines, _ = collect([Fp8("R2", MPN="R10K"), Fp8("R1", MPN="R10K")])
    assert bom_text(lines) == 'MPN,Qty,Designator\nR10K,2,"R1,R2"'
    url = bom_url(lines, boards=5)
    q = parse_qs(urlparse(url).query)
    assert url.startswith("https://part-sourcer.vercel.app/bom?list=")
    assert q["list"] == ['MPN,Qty,Designator\nR10K,2,"R1,R2"'] and q["boards"] == ["5"]
