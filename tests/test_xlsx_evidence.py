"""Native OOXML cases for exact values and explicit static-table boundaries."""

import io
import zipfile

import pytest

from paperdelta.errors import PaperDeltaError
from paperdelta.xlsx_evidence import NS, PACKAGE_REL, REL, Workbook, read_xlsx


def book(*, data=None, extra="", styles=None, shared=None, relationship=None, entries=None):
    if data is None:
        data = (
            '<row r="1"><c r="A1" t="inlineStr"><is><t>model</t></is></c>'
            '<c r="B1" t="inlineStr"><is><t>accuracy</t></is></c></row>'
            '<row r="2"><c r="A2" t="inlineStr"><is><t>001</t></is></c>'
            '<c r="B2"><v>0.80000000000000000000000000001</v></c></row>'
            '<row r="3" hidden="1"><c r="A3" t="inlineStr"><is><t>1</t></is></c>'
            '<c r="B3"><v>8.01E-1</v></c></row>'
        )
    files = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        "xl/workbook.xml": (
            f'<workbook xmlns="{NS}" xmlns:r="{REL}">'
            '<sheets><sheet name="Results" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": relationship
        or (
            f'<Relationships xmlns="{PACKAGE_REL}">'
            f'<Relationship Id="rId1" Type="{REL}/worksheet" '
            'Target="worksheets/sheet1.xml"/></Relationships>'
        ),
        "xl/worksheets/sheet1.xml": (
            f'<worksheet xmlns="{NS}"><sheetData>{data}</sheetData>{extra}</worksheet>'
        ),
    }
    if styles:
        files["xl/styles.xml"] = styles
    if shared:
        files["xl/sharedStrings.xml"] = shared
    files.update(entries or {})
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, contents in files.items():
            archive.writestr(path, contents)
    return buffer.getvalue()


def test_native_strings_long_decimal_scientific_and_hidden_rows_are_retained():
    raw = book()
    assert list(Workbook(raw).sheets) == ["Results"]
    table = read_xlsx(raw, "Results", "A1:B3")
    assert table.columns == ["model", "accuracy"]
    assert [row["model"].value for row in table.rows] == ["001", "1"]
    assert table.rows[0]["accuracy"].value == "0.80000000000000000000000000001"
    assert table.rows[1]["accuracy"].value == "8.01E-1"
    assert table.rows[0]["accuracy"].address == "B2"
    assert table.rows[0]["model"].kind == "string"


def test_shared_rich_text_and_literal_escape_do_not_include_phonetic_guides():
    shared = (
        f'<sst xmlns="{NS}"><si><r><t>00</t></r><r><t>1</t></r>'
        '<rPh sb="0" eb="3"><t>phonetic</t></rPh></si><si><t>_x005F_x0041_</t></si></sst>'
    )
    raw = book(shared=shared)
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        data = archive.read("xl/worksheets/sheet1.xml").decode()
    data = data.split("<sheetData>")[1].split("</sheetData>")[0]
    data = data.replace(
        '<c r="A2" t="inlineStr"><is><t>001</t></is></c>', '<c r="A2" t="s"><v>0</v></c>'
    )
    data = data.replace(
        '<c r="A3" t="inlineStr"><is><t>1</t></is></c>', '<c r="A3" t="s"><v>1</v></c>'
    )
    table = read_xlsx(book(data=data, shared=shared), "Results", "A1:B3")
    assert [row["model"].value for row in table.rows] == ["001", "_x0041_"]


@pytest.mark.parametrize(
    "reference", ["A1", "A0:B2", "B2:A1", "A1:XFE2", "A1:B1048577", "A1:Z100001"]
)
def test_invalid_or_unbounded_ranges_are_refused(reference):
    with pytest.raises(PaperDeltaError) as error:
        read_xlsx(book(), "Results", reference)
    assert error.value.code == "XLSX_RANGE"


def test_sheet_selection_is_explicit_and_case_sensitive():
    with pytest.raises(PaperDeltaError) as error:
        read_xlsx(book(), "results", "A1:B3")
    assert error.value.code == "XLSX_SHEET"


@pytest.mark.parametrize(
    "formula", ["<f>1+1</f>", '<f t="shared" si="1"/>', '<f t="array" ref="B2:B3">SEQUENCE(2)</f>']
)
def test_formula_caches_never_become_static_evidence(formula):
    with zipfile.ZipFile(io.BytesIO(book())) as archive:
        data = archive.read("xl/worksheets/sheet1.xml").decode()
    data = data.split("<sheetData>")[1].split("</sheetData>")[0]
    data = data.replace('<c r="B2">', '<c r="B2">' + formula)
    with pytest.raises(PaperDeltaError) as error:
        read_xlsx(book(data=data), "Results", "A1:B3")
    assert error.value.code == "XLSX_FORMULA"


def test_array_formula_outside_range_still_blocks_its_cached_spill_cells():
    data = (
        '<row r="1"><c r="A1"><f t="array" ref="A1:A4">SEQUENCE(4)</f><v>1</v></c>'
        '<c r="B1" t="inlineStr"><is><t>value</t></is></c></row>'
        '<row r="2"><c r="A2" t="inlineStr"><is><t>column</t></is></c>'
        '<c r="B2" t="inlineStr"><is><t>metric</t></is></c></row>'
        '<row r="3"><c r="A3"><v>3</v></c><c r="B3"><v>0.8</v></c></row>'
    )
    with pytest.raises(PaperDeltaError) as error:
        read_xlsx(book(data=data), "Results", "A2:B3")
    assert error.value.code == "XLSX_FORMULA"


def test_merged_cells_and_date_display_are_explicitly_unsupported():
    with pytest.raises(PaperDeltaError) as error:
        read_xlsx(
            book(extra='<mergeCells><mergeCell ref="A1:B1"/></mergeCells>'), "Results", "A1:B3"
        )
    assert error.value.code == "XLSX_MERGED"
    styles = (
        f'<styleSheet xmlns="{NS}"><cellXfs count="1"><xf numFmtId="14"/></cellXfs></styleSheet>'
    )
    with pytest.raises(PaperDeltaError) as error:
        read_xlsx(book(styles=styles), "Results", "A1:B3")
    assert error.value.code == "XLSX_DATE"


def test_external_sheet_macros_entities_and_corrupt_archive_are_refused():
    relationship = (
        f'<Relationships xmlns="{PACKAGE_REL}"><Relationship Id="rId1" Type="{REL}/worksheet" '
        'Target="https://example.invalid/remote.xml" TargetMode="External"/></Relationships>'
    )
    for raw in [
        book(relationship=relationship),
        book(entries={"xl/vbaProject.bin": b"not executed"}),
        book(entries={"xl/workbook.xml": '<!DOCTYPE w [<!ENTITY x "expanded">]><w>&x;</w>'}),
        b"not a ZIP archive",
    ]:
        with pytest.raises(PaperDeltaError):
            Workbook(raw)


def test_missing_value_keeps_its_address_and_is_not_changed_to_zero():
    with zipfile.ZipFile(io.BytesIO(book())) as archive:
        data = archive.read("xl/worksheets/sheet1.xml").decode()
    data = data.split("<sheetData>")[1].split("</sheetData>")[0]
    data = data.replace('<c r="B3"><v>8.01E-1</v></c>', "")
    cell = read_xlsx(book(data=data), "Results", "A1:B3").rows[-1]["accuracy"]
    assert cell.value is None and cell.address == "B3" and cell.kind == "missing"


@pytest.mark.parametrize("style", ["-1", "1", "not-an-index"])
def test_invalid_numeric_style_cannot_hide_a_date_format(style):
    with zipfile.ZipFile(io.BytesIO(book())) as archive:
        document = archive.read("xl/worksheets/sheet1.xml").decode()
    document = document.replace('<c r="B2">', f'<c r="B2" s="{style}">')
    with pytest.raises(PaperDeltaError):
        read_xlsx(book(entries={"xl/worksheets/sheet1.xml": document}), "Results", "A1:B3")


def test_non_utf8_doctype_cannot_bypass_xml_guard():
    document = '<?xml version="1.0" encoding="utf-16"?><!DOCTYPE w [<!ENTITY x "x">]><w>&x;</w>'
    with pytest.raises(PaperDeltaError):
        Workbook(book(entries={"xl/workbook.xml": document.encode("utf-16")}))


def test_unknown_localized_builtin_number_format_is_not_assumed_to_be_numeric():
    styles = (
        f'<styleSheet xmlns="{NS}"><cellXfs count="1"><xf numFmtId="66"/></cellXfs></styleSheet>'
    )
    with pytest.raises(PaperDeltaError):
        read_xlsx(book(styles=styles), "Results", "A1:B3")


def test_chart_sheet_does_not_hide_a_supported_static_worksheet():
    workbook = (
        f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets>'
        '<sheet name="Chart" sheetId="1" r:id="rId2"/>'
        '<sheet name="Results" sheetId="2" r:id="rId1"/></sheets></workbook>'
    )
    relationships = (
        f'<Relationships xmlns="{PACKAGE_REL}">'
        f'<Relationship Id="rId1" Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/>'
        f'<Relationship Id="rId2" Type="{REL}/chartsheet" Target="chartsheets/sheet1.xml"/>'
        "</Relationships>"
    )
    raw = book(entries={"xl/workbook.xml": workbook}, relationship=relationships)
    assert list(Workbook(raw).sheets) == ["Results"]
    assert read_xlsx(raw, "Results", "A1:B3").rows[0]["model"].value == "001"
