"""Owned manuscript fixtures for declared statistics, separate from accuracy corpora."""

import argparse
import io
from pathlib import Path

from paperdelta.config import config_text
from paperdelta.models import Config
from paperdelta.onboarding import scan_project
from paperdelta.storage import Project, json_text

ROOT = Path(__file__).resolve().parents[1]
TABLE = "model\tseed\taccuracy\n" + "".join(f"method\t{i}\t{79 + i}\n" for i in range(1, 6))


def create(directory, kind):
    directory.mkdir(parents=True, exist_ok=False)
    project = Project(directory)
    lines = [
        "Model method accuracy: 82.00 ± 1.58 (n = 5).",
        "Model method interval: [80.04, 83.96].",
        "Confidence level: 95%.",
    ]
    if kind == "tex":
        raw = (
            b"Model method accuracy: $82.00 \\pm 1.58 (n = 5)$.\n"
            b"Model method interval: [80.04, 83.96].\n"
            b"Confidence level: 95\\%.\n"
        )
    elif kind == "docx":
        from docx import Document

        document = Document()
        for line in lines:
            document.add_paragraph(line)
        stream = io.BytesIO()
        document.save(stream)
        raw = stream.getvalue()
    else:
        from reportlab.pdfgen import canvas

        stream = io.BytesIO()
        page = canvas.Canvas(stream, pagesize=(620, 420))
        for y, line in zip([350, 315, 280], lines, strict=True):
            page.drawString(30, y, line)
        page.save()
        raw = stream.getvalue()
    entry = "paper." + kind
    project.write(entry, raw)
    project.write("results.tsv", TABLE.encode())
    config = Config.model_validate(
        {
            "schema_version": 5,
            "paper": {"entry": entry},
            "sources": {
                "runs": {
                    "path": "results.tsv",
                    "format": "tsv",
                    "columns": {"model": "string", "seed": "integer", "accuracy": "decimal"},
                    "primary_key": ["model", "seed"],
                }
            },
        }
    )
    project.write("paperdelta.yaml", config_text(config).encode())
    scan = scan_project(project)
    return {
        "paper": entry,
        "source": "results.tsv",
        "mean_sd": [
            item["candidate_id"]
            for item in scan["candidates"]
            if item["text"] in {"82.00", "1.58", "5"}
        ],
        "ci": [
            item["candidate_id"]
            for item in scan["candidates"]
            if item["text"] in {"80.04", "83.96"}
        ],
        "confidence_level": [
            item["candidate_id"] for item in scan["candidates"] if item["text"] == "95"
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--kind", choices=["tex", "docx", "pdf"], required=True)
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    assert output.is_relative_to(ROOT / "build")
    print(json_text(create(output, args.kind)))


if __name__ == "__main__":
    main()
