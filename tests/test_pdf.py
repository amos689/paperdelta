"""PDF positions are compared with authored page geometry, not adapter text dumps."""

import io
from decimal import Decimal
from pathlib import Path

import pytest
import reportlab
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from paperdelta import builder
from paperdelta.agent import AgentSession
from paperdelta.analysis import check_project
from paperdelta.config import config_text
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import language_context
from paperdelta.models import Anchor, Config, PdfRegion
from paperdelta.onboarding import init_project, scan_project
from paperdelta.patches import create_patch
from paperdelta.pdf_document import PdfDocument
from paperdelta.records import PdfLocation, StoredReport, validate_record
from paperdelta.repairs import accept_repairs, propose_repairs, scan_repairs
from paperdelta.reports import text_report, write_reports
from paperdelta.snapshots import create_snapshot
from paperdelta.storage import Project, json_text, sha256
from paperdelta.watch import Watcher

VALUES = ["84.1", "80.9", "3.1", "81.0", "2.5"]
LAYOUTS = [
    "plain",
    "split-draws",
    "small-font",
    "large-font",
    "serif",
    "monospace",
    "bold",
    "italic",
    "chinese",
    "unicode-minus",
    "scientific",
    "thousands",
    "positive-sign",
    "negative-sign",
    "percent",
    "integer",
    "two-columns",
    "three-columns",
    "landscape",
    "letter",
    "a4",
    "multiple-pages",
    "table",
    "table-chinese",
    "table-multiple-pages",
]


def fonts():
    if "STSong-Light" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    if "TestVera" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(
            TTFont("TestVera", str(Path(reportlab.__file__).parent / "fonts/Vera.ttf"))
        )


def labelled_pdf(case="plain", *, values=VALUES, prefix="Result", shift=0):
    fonts()
    size = (800, 600) if case == "landscape" else (612, 792) if case == "letter" else (600, 800)
    if case == "a4":
        size = (595.2756, 841.8898)
    stream = io.BytesIO()
    canvas = Canvas(stream, pagesize=size, invariant=1)
    canvas.setAuthor("amos689")
    font = {
        "serif": "Times-Roman",
        "monospace": "Courier",
        "bold": "Helvetica-Bold",
        "italic": "Helvetica-Oblique",
        "chinese": "STSong-Light",
        "table-chinese": "STSong-Light",
        "unicode-minus": "TestVera",
    }.get(case, "Helvetica")
    points = 8 if case == "small-font" else 18 if case == "large-font" else 12
    expected = []
    for i, number in enumerate(values):
        page = i + 1 if case in {"multiple-pages", "table-multiple-pages"} else 1
        if i and page > 1:
            canvas.showPage()
        canvas.setFont(font, points)
        if case == "unicode-minus":
            number = "−" + number
        elif case in {"negative-sign", "positive-sign"}:
            number = ("-" if case == "negative-sign" else "+") + number
        elif case == "scientific":
            number += "e-3"
        elif case == "thousands":
            number = "1,0" + ("0" if len(number) < 4 else "") + number
        elif case == "integer":
            number = str(int(Decimal(number) * 10))
        column_count = 2 if case == "two-columns" else 3 if case == "three-columns" else 1
        x = 35 + (i % column_count) * (size[0] / column_count) + shift
        y = size[1] - 65 - (0 if page > 1 else i // column_count) * 40
        label = f"{prefix} {'ABCDE'[i]}: "
        if case == "chinese":
            label = f"模型{'甲乙丙丁戊'[i]}准确率"
        if case.startswith("table"):
            row = 0 if page > 1 else i
            if row == 0:
                for column in (30, 160, 300):
                    canvas.line(column, size[1] - 35, column, size[1] - (95 if page > 1 else 255))
                for row_y in range(35, 96 if page > 1 else 256, 40):
                    canvas.line(30, size[1] - row_y, 300, size[1] - row_y)
                canvas.drawString(40, size[1] - 60, "模型" if case == "table-chinese" else "Model")
                canvas.drawString(
                    170, size[1] - 60, "准确率" if case == "table-chinese" else "Accuracy"
                )
            y = size[1] - 100 - row * 40
            # The table has a 40-point header row and five ordinary data rows.
            if page > 1:
                canvas.line(30, size[1] - 115, 300, size[1] - 115)
                for column in (30, 160, 300):
                    canvas.line(column, size[1] - 95, column, size[1] - 115)
            elif i == 0:
                canvas.line(30, size[1] - 275, 300, size[1] - 275)
                for column in (30, 160, 300):
                    canvas.line(column, size[1] - 255, column, size[1] - 275)
            canvas.drawString(40, y, "ABCDE"[i])
            x, label = 170, ""
        canvas.drawString(x, y, label)
        x += pdfmetrics.stringWidth(label, font, points)
        if case == "split-draws":
            offset = x
            for char in number:
                canvas.drawString(offset, y, char)
                offset += pdfmetrics.stringWidth(char, font, points)
        else:
            canvas.drawString(x, y, number)
        if case == "percent":
            canvas.drawString(x + pdfmetrics.stringWidth(number, font, points), y, "%")
        expected.append(
            {
                "text": number,
                "page": page,
                "left": x,
                "right": x + pdfmetrics.stringWidth(number, font, points),
                "baseline": size[1] - y,
                "page_box": [0, 0, *size],
            }
        )
    canvas.save()
    return stream.getvalue(), expected


@pytest.mark.parametrize("case", LAYOUTS)
def test_authored_pdf_positions_and_anchors(case):
    raw, labels = labelled_pdf(case)
    document = PdfDocument("paper.pdf", raw)
    assert not document.issues
    spans = document.numbers()
    assert len(spans) == len(labels) == 5
    for span, label in zip(spans, labels, strict=True):
        assert span.text == label["text"]
        assert span.locator["page"] == label["page"]
        assert list(map(float, span.locator["page_box"])) == label["page_box"]
        left, top, right, bottom = map(float, span.locator["bbox"])
        assert left == pytest.approx(label["left"], abs=0.01)
        assert right == pytest.approx(label["right"], abs=0.01)
        assert top < label["baseline"] <= bottom
        assert not {"line", "byte_start", "byte_end"} & span.to_dict().keys()
        validate_record(PdfLocation, span.to_dict(), "TEST_POSITION")
        anchor = builder.anchor_for_span(document, span)
        assert document.locate(anchor).to_dict() == span.to_dict()
        if case.startswith("table"):
            assert anchor.table is not None
            assert anchor.table.page == label["page"]
    assert document.hash == sha256(raw)


def unusual_pdf(case):
    stream = io.BytesIO()
    canvas = Canvas(stream, pagesize=(600, 800), invariant=1)
    if case in {"scan", "ocr-layer"}:
        canvas.drawImage(ImageReader(Image.new("RGB", (600, 800), "white")), 0, 0, 600, 800)
    if case == "rotated-page":
        canvas.setPageRotation(90)
    if case == "crop":
        canvas.setCropBox((0, 0, 550, 750))
    if case == "transparent":
        canvas.setFillAlpha(0)
    if case == "white":
        canvas.setFillColorRGB(1, 1, 1)
    if case == "rotated-text":
        canvas.translate(100, 300)
        canvas.rotate(90)
    if case == "invisible":
        text = canvas.beginText(40, 720)
        text.setTextRenderMode(3)
        text.textOut("Result 84.1")
        canvas.drawText(text)
    elif case == "superscript":
        text = canvas.beginText(40, 720)
        text.textOut("Result 10")
        text.setRise(6)
        text.setFont("Helvetica", 8)
        text.textOut("2")
        canvas.drawText(text)
    elif case not in {"scan", "blank"}:
        canvas.drawString(40, 720, "Result 84.1")
    canvas.showPage()
    canvas.save()
    return stream.getvalue()


@pytest.mark.parametrize(
    "case",
    [
        "scan",
        "blank",
        "ocr-layer",
        "rotated-page",
        "crop",
        "invisible",
        "rotated-text",
        "transparent",
        "white",
        "superscript",
    ],
)
def test_unreliable_content_cannot_be_verified(case):
    document = PdfDocument("paper.pdf", unusual_pdf(case))
    assert document.issues
    assert not document.numbers()


def test_parser_identity_is_required_and_changed_identity_invalidates_bindings():
    document = PdfDocument("paper.pdf", labelled_pdf()[0])
    anchor = builder.anchor_for_span(document, document.numbers()[0])
    for parser in (None, "paperdelta-pdf/old"):
        with pytest.raises(PaperDeltaError) as error:
            document.locate(anchor.model_copy(update={"parser": parser}))
        assert error.value.code == "PDF_EXTRACTION_CHANGED"
    table = PdfDocument("paper.pdf", labelled_pdf("table")[0])
    anchor = builder.anchor_for_span(table, table.numbers()[0])
    with pytest.raises(PaperDeltaError, match=".+") as error:
        table.locate(Anchor(table=anchor.table.model_copy(update={"parser": "old"})))
    assert error.value.code == "PDF_EXTRACTION_CHANGED"


def test_region_identity_and_bounds_do_not_hide_remaining_content():
    raw, _ = labelled_pdf()
    region = PdfRegion(name="abstract", page=1, bbox=[20, 40, 300, 85], kind="abstract")
    document = PdfDocument("paper.pdf", raw, [region])
    assert len(document.numbers()) == 5
    assert document.numbers()[0].locator["region"] == "abstract"
    assert document.priority_regions
    for regions in (
        [region, region.model_copy(update={"name": "other"})],
        [region.model_copy(update={"page": 2})],
        [region.model_copy(update={"bbox": [20, 40, 700, 85]})],
    ):
        with pytest.raises(PaperDeltaError) as error:
            PdfDocument("paper.pdf", raw, regions)
        assert error.value.code == "PDF_REGION"
    unruled = PdfDocument("paper.pdf", raw, [region.model_copy(update={"kind": "table"})])
    assert len(unruled.numbers()) == 4
    assert any(issue["code"] == "PDF_COMPLEX_TABLE" for issue in unruled.issues)


def test_partial_number_and_ambiguous_text_are_never_accepted():
    document = PdfDocument("paper.pdf", labelled_pdf()[0])
    with pytest.raises(PaperDeltaError) as error:
        document.validate_numeric_span(document.locate(Anchor(exact="84", parser=document.parser)))
    assert error.value.code == "NUMERIC_SPAN"
    repeated = PdfDocument("paper.pdf", labelled_pdf(values=["84.1"] * 5)[0])
    with pytest.raises(PaperDeltaError) as error:
        repeated.locate(Anchor(exact="84.1", parser=repeated.parser))
    assert error.value.code == "ANCHOR_AMBIGUOUS"


def test_corrupt_or_password_protected_pdf_is_explicit():
    from reportlab.lib.pdfencrypt import StandardEncryption

    stream = io.BytesIO()
    canvas = Canvas(stream, encrypt=StandardEncryption("private"))
    canvas.drawString(20, 20, "Result 84.1")
    canvas.save()
    for raw in (b"%PDF partial write", stream.getvalue()):
        with pytest.raises(PaperDeltaError) as error:
            PdfDocument("paper.pdf", raw)
        assert error.value.code == "PDF_PARSE"


@pytest.fixture
def pdf_project(tmp_path):
    project = Project(tmp_path)
    raw, _ = labelled_pdf()
    project.write("paper.pdf", raw)
    project.write("results.csv", b"model,score\nOurs,84.1\n")
    document = PdfDocument("paper.pdf", raw)
    config = Config.model_validate(
        {
            "schema_version": 4,
            "paper": {"entry": "paper.pdf"},
            "sources": {
                "results": {
                    "path": "results.csv",
                    "format": "csv",
                    "primary_key": ["model"],
                    "columns": {"model": "string", "score": "decimal"},
                }
            },
            "metrics": {
                "accuracy": {
                    "source": "results",
                    "field": "score",
                    "where": {"model": "Ours"},
                    "unit": "scalar",
                }
            },
            "occurrences": {
                "accuracy": {
                    "file": "paper.pdf",
                    "metric": "accuracy",
                    "anchor": builder.anchor_for_span(document, document.numbers()[0]).model_dump(),
                }
            },
        }
    )
    project.write("paperdelta.yaml", config_text(config).encode())
    return project


def test_pdf_check_report_agent_and_read_only_patch(pdf_project):
    project = pdf_project
    before = project.read("paper.pdf")
    report = check_project(project.root)
    assert report["exit_code"] == 0
    assert report["report_schema_version"] == 4
    validate_record(StoredReport, report, "TEST_REPORT")
    assert "bbox" in json_text(report)
    create_snapshot(project, "before", report)
    project.write("results.csv", b"model,score\nOurs,80.9\n")
    report = check_project(project.root)
    assert report["occurrences"]["accuracy"]["status"] == "mismatch"
    assert any(action["kind"] == "update_document" for action in report["actions"])
    with pytest.raises(PaperDeltaError) as error:
        create_patch(project, report)
    assert error.value.code == "DOCUMENT_READ_ONLY"
    for language in ("en", "zh-CN"):
        with language_context(language):
            assert ("page 1" if language == "en" else "第 1 页") in text_report(report)
            write_reports(project, "build/review", report)
            assert AgentSession(project).check_project()["exit_code"] == 1
            assert AgentSession(project).scan_project()["candidates"][0]["format"] == "pdf"
    assert project.read("paper.pdf") == before


def test_pdf_reflow_repair_and_partial_save_recovery(pdf_project):
    project = pdf_project
    report = check_project(project.root)
    create_snapshot(project, "before", report)
    watcher = Watcher(project, debounce=0)
    assert watcher.step(0)["exit_code"] == 0
    project.write("paper.pdf", b"%PDF partial")
    assert watcher.step(1)["exit_code"] == 2
    revised = labelled_pdf(prefix="Updated result", shift=20)[0]
    project.write("paper.pdf", revised)
    assert watcher.step(2)["coverage"]["unknown"] == 1
    candidates = scan_repairs(project, baseline="before")["candidates"]
    candidate = next(item for item in candidates if item["text"] == "84.1")
    proposal = propose_repairs(
        project,
        [
            {
                "binding": "occurrences:accuracy",
                "candidate_id": candidate["candidate_id"],
                "rationale": "Same labelled metric after reflow.",
            }
        ],
        baseline="before",
    )
    accept_repairs(project, proposal, ["occurrences:accuracy"])
    assert watcher.step(3)["coverage"]["pass"] == 1
    watcher.stop()
    assert project.read("paper.pdf") == revised


def test_pdf_init_and_optional_parser_error(tmp_path, monkeypatch):
    import builtins

    project = Project(tmp_path)
    project.write("paper.pdf", labelled_pdf()[0])
    init_project(project, "paper.pdf", [])
    assert scan_project(project)["candidates"][0]["format"] == "pdf"
    original = builtins.__import__

    def no_pdf(name, *args, **kwargs):
        if name == "pdfplumber":
            raise ImportError("optional parser absent")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_pdf)
    report = check_project(tmp_path)
    assert report["exit_code"] == 2
    assert report["diagnostics"][0]["rule"] == "DOCUMENT_DEPENDENCY"
    assert "paperdelta[pdf]" in report["diagnostics"][0]["message"]


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("scenario", ["baseline", "changed", "safe-update"])
def test_bundled_pdf_source_demo(tmp_path, language, scenario):
    from paperdelta.demo import create_demo

    with language_context(language):
        result = create_demo(Project(tmp_path), "pdf-demo", scenario, "pdf")
    assert result["check_exit_code"] == (0 if scenario == "baseline" else 1)
    assert result["patch"] is None
    project = Project(tmp_path / "pdf-demo")
    report = check_project(project.root)
    assert report["report_schema_version"] == 4
    assert len(report["exports"]) == 2
    assert report["exports"][0]["status"] == ("aligned" if scenario == "baseline" else "stale")
    assert "data:image/png;base64," in project.text("review/report.html")[0]


def test_form_content_is_unknown_without_discarding_separate_prose():
    stream = io.BytesIO()
    canvas = Canvas(stream, pagesize=(600, 800), invariant=1)
    canvas.beginForm("plot", 0, 0, 100, 100)
    canvas.drawString(5, 50, "Plot 80.9")
    canvas.endForm()
    canvas.drawString(40, 720, "Result 84.1")
    canvas.saveState()
    canvas.translate(100, 100)
    canvas.doForm("plot")
    canvas.restoreState()
    canvas.save()
    document = PdfDocument("paper.pdf", stream.getvalue())
    assert any(issue["code"] == "PDF_FORM_CONTENT" for issue in document.issues)
    assert [item.text for item in document.numbers()] == ["84.1"]


def test_table_region_cannot_cut_or_hide_grid_structure():
    raw = labelled_pdf("table")[0]
    full = PdfRegion(name="results", page=1, bbox=[20, 25, 310, 285], kind="table")
    document = PdfDocument("paper.pdf", raw, [full])
    assert len(document.numbers()) == 5
    anchor = builder.anchor_for_span(document, document.numbers()[0])
    assert anchor.table.region == "results"
    for region in (
        full.model_copy(update={"kind": "text"}),
        full.model_copy(update={"bbox": [20, 25, 310, 140]}),
    ):
        with pytest.raises(PaperDeltaError) as error:
            PdfDocument("paper.pdf", raw, [region])
        assert error.value.code == "PDF_REGION"


def test_merged_cells_are_not_silently_flattened_to_prose():
    stream = io.BytesIO()
    canvas = Canvas(stream, pagesize=(600, 800), invariant=1)
    for y in (600, 650, 700):
        canvas.line(30, y, 300, y)
    for x in (30, 300):
        canvas.line(x, 600, x, 700)
    canvas.line(150, 600, 150, 650)
    canvas.drawString(40, 675, "Merged header")
    canvas.drawString(40, 625, "Ours")
    canvas.drawString(170, 625, "84.1")
    canvas.save()
    document = PdfDocument("paper.pdf", stream.getvalue())
    assert any(issue["code"] == "PDF_COMPLEX_TABLE" for issue in document.issues)
    assert not document.numbers()


def test_pdf_batch_keeps_header_and_row_identity(tmp_path):
    from paperdelta.batch import build_proposal, create_catalog, inspect_catalog
    from paperdelta.onboarding import accept_bindings

    project = Project(tmp_path)
    raw = labelled_pdf("table")[0]
    project.write("paper.pdf", raw)
    project.write(
        "results.csv",
        (
            "model,Accuracy\n"
            + "\n".join(f"{name},{value}" for name, value in zip("ABCDE", VALUES, strict=True))
        ).encode(),
    )
    init_project(project, "paper.pdf", ["results.csv"])
    draft = builder.add_source(
        project,
        builder.start_draft(project),
        name="results",
        path="results.csv",
        format="csv",
        columns={"model": "string", "Accuracy": "decimal"},
        primary_key=["model"],
    )
    catalog = create_catalog(
        project,
        draft,
        {
            "source": "results",
            "fields": ["Accuracy"],
            "group_by": ["model"],
            "unit": "scalar",
            "reduce": "unique",
            "expected_count": 1,
            "display": {"kind": "decimal", "places": 1},
        },
    )
    preview = inspect_catalog(project, catalog)
    selections = []
    for choice in preview["choices"]:
        model = choice["definition"]["where"]["model"]
        location = next(
            item for item in preview["locations"] if item["row"].split("|")[0].strip() == model
        )
        assert location["column_header"] == "Accuracy"
        selections.append(
            {
                "choice_id": choice["choice_id"],
                "candidate_ids": [location["candidate_id"]],
                "rationale": "Explicit row and metric column.",
            }
        )
    proposal = build_proposal(project, catalog, selections)
    accept_bindings(project, proposal, list(proposal["rationale"]))
    assert check_project(tmp_path)["coverage"]["pass"] == 5
    assert project.read("paper.pdf") == raw


def test_pdf_mcp_preserves_page_coordinates_and_does_not_write(pdf_project):
    import asyncio

    mcp = pytest.importorskip("mcp")
    from paperdelta.mcp_server import create_server

    before = {
        p.relative_to(pdf_project.root): p.read_bytes()
        for p in pdf_project.root.rglob("*")
        if p.is_file()
    }

    async def run():
        async with mcp.Client(create_server(pdf_project)) as client:
            result = await client.call_tool("check_project")
            assert not result.is_error
            location = result.structured_content["occurrences"]["accuracy"]["location"]
            assert location["format"] == "pdf"
            assert location["locator"]["page"] == 1
            assert len(location["locator"]["bbox"]) == 4
            result = await client.call_tool("scan_project")
            assert not result.is_error
            assert result.structured_content["candidates"][0]["format"] == "pdf"

    asyncio.run(run())
    assert before == {
        p.relative_to(pdf_project.root): p.read_bytes()
        for p in pdf_project.root.rglob("*")
        if p.is_file()
    }
