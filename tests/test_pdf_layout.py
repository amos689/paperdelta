"""Independent authored geometry and raster checks for original PDF coordinates."""

import base64
import io
from copy import deepcopy
from decimal import Decimal

import pytest
from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from paperdelta.analysis import check_project
from paperdelta.models import PdfRegion
from paperdelta.onboarding import init_project
from paperdelta.pdf_document import PdfDocument
from paperdelta.pdf_previews import pdf_previews
from paperdelta.storage import Project


def geometry_pdf(rotation=0, offset=False):
    stream = io.BytesIO()
    canvas = Canvas(stream, pagesize=(600, 800), invariant=1)
    canvas.drawString(150, 500, "Result 84.1")
    canvas.drawString(20, 50, "Outside crop 99.9")
    canvas.save()
    writer = PdfWriter()
    page = writer.add_page(PdfReader(stream).pages[0])
    dx, dy = (50, 100) if offset else (0, 0)
    if offset:
        page.add_transformation(Transformation().translate(dx, dy))
    page.mediabox = RectangleObject((dx, dy, 600 + dx, 800 + dy))
    page.cropbox = RectangleObject((100 + dx, 200 + dy, 500 + dx, 700 + dy))
    page.rotate(rotation)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def expected_point(x, y, rotation):
    # Authored crop: 400 x 500 points, top-left origin.
    return {0: (x, y), 90: (500 - y, x), 180: (400 - x, 500 - y), 270: (y, 400 - x)}[rotation]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("offset", [False, True])
def test_rotated_cropped_offset_positions_align_with_original_raster(tmp_path, rotation, offset):
    raw = geometry_pdf(rotation, offset)
    doc = PdfDocument("p.pdf", raw)
    assert [s.text for s in doc.numbers()] == ["84.1"]
    span = doc.numbers()[0]
    assert doc.locate(doc.anchor_for_span(span)) == span
    width, height = (500, 400) if rotation in (90, 270) else (400, 500)
    assert list(map(float, span.locator["page_box"])) == [0, 0, width, height]
    x = 50 + stringWidth("Result ", "Helvetica", 12)
    points = [
        expected_point(a, b, rotation)
        for a in (x, x + stringWidth("84.1", "Helvetica", 12))
        for b in (190.484, 202.484)
    ]
    expected = [
        min(p[0] for p in points),
        min(p[1] for p in points),
        max(p[0] for p in points),
        max(p[1] for p in points),
    ]
    assert list(map(float, span.locator["bbox"])) == pytest.approx(expected, abs=0.01)
    project = Project(tmp_path)
    project.write("p.pdf", raw)
    init_project(project, "p.pdf", [])
    report = check_project(tmp_path)
    item = pdf_previews(project, report)["pages"][0]
    assert "image" in item, item
    image = Image.open(io.BytesIO(base64.b64decode(item["image"].split(",")[1])))
    assert image.width / image.height == pytest.approx(width / height, abs=0.005)
    selected = image.crop(tuple(round(v * image.width / width) for v in expected)).convert("L")
    assert sum(v < 100 for v in selected.tobytes()) > 25
    assert project.read("p.pdf") == raw
    # A visual-coordinate ROI must select the same token after inverse rotation.
    region = PdfRegion(
        name="result",
        page=1,
        bbox=list(
            map(
                Decimal,
                map(
                    str,
                    [
                        max(0, expected[0] - 70),
                        max(0, expected[1] - 70),
                        min(width, expected[2] + 70),
                        min(height, expected[3] + 70),
                    ],
                ),
            )
        ),
        kind="text",
    )
    in_region = PdfDocument("p.pdf", raw, [region]).numbers()[0]
    assert in_region.locator["region"] == "result"
    assert in_region.locator["bbox"] == span.locator["bbox"]


def clipped_pdf(case):
    stream = io.BytesIO()
    canvas = Canvas(stream, pagesize=(600, 800), invariant=1)
    canvas.saveState()
    path = canvas.beginPath()
    if case == "curved":
        path.circle(40, 700, 10)
    else:
        path.rect(30, 680, 250 if case == "visible" else 35, 80)
    canvas.clipPath(path, stroke=0, fill=0)
    canvas.drawString(40, 720, "Result 84.1")
    canvas.restoreState()
    canvas.drawString(40, 620, "Baseline 80.9")
    canvas.save()
    return stream.getvalue()


@pytest.mark.parametrize("case", ["visible", "partial", "curved"])
def test_clipping_is_scoped_and_does_not_join_truncated_digits(case):
    doc = PdfDocument("p.pdf", clipped_pdf(case))
    assert [s.text for s in doc.numbers()] == (["84.1", "80.9"] if case == "visible" else ["80.9"])
    if case != "visible":
        assert any(i["code"] == "PDF_UNRELIABLE_TEXT" for i in doc.issues)


@pytest.mark.parametrize("case", ["alpha", "invisible", "text-clip"])
def test_hidden_text_state_does_not_leak_after_restore(case):
    stream = io.BytesIO()
    canvas = Canvas(stream, pagesize=(600, 800), invariant=1)
    canvas.saveState()
    if case == "alpha":
        canvas.setFillAlpha(0)
    text = canvas.beginText(40, 720)
    text.setTextRenderMode({"alpha": 0, "invisible": 3, "text-clip": 7}[case])
    text.textOut("Hidden 84.1")
    canvas.drawText(text)
    canvas.restoreState()
    canvas.drawString(40, 620, "Visible 80.9")
    canvas.save()
    doc = PdfDocument("p.pdf", stream.getvalue())
    assert [s.text for s in doc.numbers()] == ["80.9"]


def test_changed_source_never_reuses_a_previous_preview(tmp_path):
    project = Project(tmp_path)
    project.write("p.pdf", geometry_pdf())
    init_project(project, "p.pdf", [])
    report = check_project(tmp_path)
    project.write("p.pdf", geometry_pdf(90))
    assert all("image" not in p for p in pdf_previews(project, deepcopy(report))["pages"])


def test_text_clipping_remains_unknown_until_graphics_state_is_restored():
    stream = io.BytesIO()
    canvas = Canvas(stream, pagesize=(600, 800), invariant=1)
    text = canvas.beginText(40, 720)
    text.setTextRenderMode(7)
    text.textOut("Mask")
    canvas.drawText(text)
    text = canvas.beginText(40, 620)
    text.setTextRenderMode(0)
    text.textOut("Clipped 84.1")
    canvas.drawText(text)
    canvas.save()
    assert not PdfDocument("p.pdf", stream.getvalue()).numbers()
