"""Rebuild an original PDF/source pair; the installed demo needs no TeX or ReportLab."""

from io import BytesIO
from pathlib import Path

from reportlab.pdfgen.canvas import Canvas

from paperdelta.builder import anchor_for_span, candidate_span
from paperdelta.config import config_text, load_config
from paperdelta.models import Config, Display
from paperdelta.pdf_document import PdfDocument
from paperdelta.storage import Project


def build():
    root = Path(__file__).resolve().parents[1] / "src/paperdelta"
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=(600, 800), invariant=1)
    canvas.setAuthor("amos689")
    canvas.setTitle("PaperDelta: original research review example")
    canvas.setFillColorRGB(0.09, 0.43, 0.40)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(48, 750, "RESEARCH RESULT REVIEW")
    canvas.setFillColorRGB(0.09, 0.17, 0.21)
    canvas.setFont("Helvetica-Bold", 26)
    canvas.drawString(48, 711, "PaperDelta")
    canvas.setFont("Helvetica", 12)
    canvas.drawString(48, 684, "An original example of a research result and its exported paper.")
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(48, 626, "Abstract")
    canvas.setFont("Helvetica", 12)
    canvas.drawString(48, 600, "Our method achieves 84.1% accuracy on Data-A.")
    canvas.drawString(48, 578, "Each reported value is tied to declared experimental evidence.")
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(48, 519, "Results")
    canvas.setFont("Helvetica", 12)
    canvas.drawString(48, 493, "Our method outperforms Baseline on Data-A.")
    canvas.setFont("Helvetica", 10)
    canvas.drawString(48, 452, "Accuracy on the held-out test split (%)")
    canvas.setLineWidth(0.7)
    canvas.setStrokeColorRGB(0.42, 0.53, 0.56)
    for x in (48, 288, 552):
        canvas.line(x, 316, x, 436)
    for y in (316, 356, 396, 436):
        canvas.line(48, y, 552, y)
    for index, (left, right) in enumerate(
        (("Method", "Accuracy"), ("Ours", "84.1"), ("Baseline", "81.0"))
    ):
        canvas.setFont("Helvetica-Bold" if index == 0 else "Helvetica", 12)
        canvas.drawString(62, 410 - index * 40, left)
        canvas.drawString(302, 410 - index * 40, right)
    canvas.setFont("Helvetica", 10)
    canvas.drawString(
        48, 263, "The example is illustrative. It is not a scientific benchmark result."
    )
    canvas.save()
    raw = stream.getvalue()
    pdf = PdfDocument("paper.pdf", raw)
    if pdf.issues:
        raise RuntimeError(pdf.issues)
    template = load_config(Project(root / "demo_word"))[0].model_dump()
    template["schema_version"] = 4
    template["paper"] = {
        "entry": "source.tex",
        "companions": [{"entry": "paper.pdf", "export_of": "source.tex"}],
    }
    template["occurrences"] = {}
    for number in pdf.numbers():
        if "table" in number.locator:
            name = "table_accuracy" if number.locator["row"] == 2 else "table_baseline"
        else:
            name = "abstract_accuracy"
        display = Display(kind="percent", percent_symbol=name == "abstract_accuracy")
        span = candidate_span(pdf, number.to_dict(), display)
        template["occurrences"][name] = {
            "file": "paper.pdf",
            "metric": "baseline" if name.endswith("baseline") else "accuracy",
            "anchor": anchor_for_span(pdf, span).model_dump(),
            "display": display.model_dump(),
        }
    source = (
        b"\\documentclass{article}\n\\begin{document}\n"
        b"Our source accuracy is 84.1\\%. Baseline accuracy is 81.0\\%.\n\\end{document}\n"
    )
    # LaTeX does not need compiling; it is inspected as the declared source.
    from paperdelta.latex import PaperIndex
    from paperdelta.models import Paper

    target = root / "demo_pdf"
    (target / "results").mkdir(parents=True, exist_ok=True)
    (target / "source.tex").write_bytes(source)
    document = PaperIndex(Project(target), Paper(entry="source.tex")).document("source.tex")
    for name, number in zip(
        ("source_accuracy", "source_baseline"), document.numbers(), strict=True
    ):
        display = Display(kind="percent")
        span = candidate_span(document, number.to_dict(), display)
        template["occurrences"][name] = {
            "file": "source.tex",
            "metric": "baseline" if name.endswith("baseline") else "accuracy",
            "anchor": anchor_for_span(document, span).model_dump(),
            "display": display.model_dump(),
        }
    claim = template["claims"]["main_comparison"]
    claim["file"] = "paper.pdf"
    claim["anchor"]["parser"] = pdf.parser
    (target / "paper.pdf").write_bytes(raw)
    (target / "paperdelta.yaml").write_bytes(config_text(Config.model_validate(template)).encode())
    (target / "results/metrics.csv").write_bytes(
        (root / "demo_word/results/metrics.csv").read_bytes()
    )


if __name__ == "__main__":
    build()
