"""Rebuild owned static Markdown/Quarto demos and an explicit source/PDF example."""

from pathlib import Path

from paperdelta.builder import anchor_for_span, candidate_span
from paperdelta.config import config_text, load_config
from paperdelta.markdown_document import MarkdownDocument
from paperdelta.models import Config, Display
from paperdelta.storage import Project

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src/paperdelta"
SOURCE = (
    b"# PaperDelta: evidence-linked source review\n\n"
    b"## Abstract\n\n"
    b"Our method achieves **84.1%** accuracy on Data-A.\n\n"
    b"## Results\n\n"
    b"Our method outperforms Baseline on Data-A.\n\n"
    b"| Method | Accuracy (%) |\n"
    b"| :--- | ---: |\n"
    b"| Ours | 84.1 |\n"
    b"| Baseline | 81.0 |\n\n"
    b"This authored example demonstrates review. It is not a scientific benchmark.\n"
)


def build():
    template = load_config(Project(PACKAGE / "demo_word"))[0].model_dump()
    data = (PACKAGE / "demo_word/results/metrics.csv").read_bytes()
    for kind, extension in (("markdown", "md"), ("quarto", "qmd")):
        project = Project(PACKAGE / ("demo_" + kind))
        file = "paper." + extension
        document = MarkdownDocument(file, SOURCE, kind)
        assert not document.issues
        value = {**template, "schema_version": 8, "paper": {"entry": file}, "occurrences": {}}
        value["claims"] = {
            "main_comparison": {
                **template["claims"]["main_comparison"],
                "file": file,
            }
        }
        for name, number in zip(
            ("abstract_accuracy", "table_accuracy", "table_baseline"),
            document.numbers(),
            strict=True,
        ):
            display = Display(kind="percent", percent_symbol=name == "abstract_accuracy")
            span = candidate_span(document, number.to_dict(), display)
            value["occurrences"][name] = {
                "file": file,
                "metric": "baseline" if name.endswith("baseline") else "accuracy",
                "anchor": anchor_for_span(document, span).model_dump(),
                "display": display.model_dump(),
            }
        project.write(file, SOURCE)
        project.write("results/metrics.csv", data)
        project.write("paperdelta.yaml", config_text(Config.model_validate(value)).encode())

    # Independent authored example: declared editable sources and an original PDF.
    project = Project(ROOT / "examples/static-manuscript")
    project.write("paper.qmd", SOURCE)
    project.write("results/metrics.csv", data)
    appendix = b"# Supplement\n\nThe shared accuracy is 84.1%.\n"
    project.write("appendix.md", appendix)
    value["paper"]["companions"] = [
        {"entry": "appendix.md"},
        {"entry": "export.pdf", "export_of": "paper.qmd"},
    ]
    document = MarkdownDocument("appendix.md", appendix)
    display = Display(kind="percent")
    span = candidate_span(document, document.numbers()[0].to_dict(), display)
    value["occurrences"]["supplement_accuracy"] = {
        "file": "appendix.md",
        "metric": "accuracy",
        "anchor": anchor_for_span(document, span).model_dump(),
        "display": display.model_dump(),
    }
    from paperdelta.pdf_document import PdfDocument

    pdf_bytes = (PACKAGE / "demo_pdf/paper.pdf").read_bytes()
    pdf = PdfDocument("export.pdf", pdf_bytes)
    for number in pdf.numbers():
        name = (
            ("table_accuracy" if number.locator["row"] == 2 else "table_baseline")
            if "table" in number.locator
            else "abstract_accuracy"
        )
        display = Display(kind="percent", percent_symbol=name == "abstract_accuracy")
        span = candidate_span(pdf, number.to_dict(), display)
        value["occurrences"]["export_" + name] = {
            "file": "export.pdf",
            "metric": "baseline" if name.endswith("baseline") else "accuracy",
            "anchor": anchor_for_span(pdf, span).model_dump(),
            "display": display.model_dump(),
        }
    project.write("export.pdf", pdf_bytes)
    project.write("paperdelta.yaml", config_text(Config.model_validate(value)).encode())


if __name__ == "__main__":
    build()
