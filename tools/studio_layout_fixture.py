"""Owned layout fixtures for browser review, separate from native-paper scoring."""

import argparse
import io
import sys
from decimal import Decimal
from pathlib import Path

from paperdelta.config import config_text
from paperdelta.models import Config
from paperdelta.onboarding import scan_project
from paperdelta.storage import Project, json_text

ROOT = Path(__file__).resolve().parents[1]


def create(directory, kind):
    sys.path.insert(0, str(ROOT / "tests"))
    from test_pdf_layout import geometry_pdf
    from test_word_layout import notes_document, packed, result_table

    directory.mkdir(parents=True, exist_ok=False)
    if kind == "docx-table":
        from docx import Document

        document = Document()
        result_table(document)
        raw, expected = packed(document), "82.4"
    elif kind == "docx-note":
        raw, expected = notes_document(), "0.4"
    elif kind == "pdf-rotated":
        raw, expected = geometry_pdf(90, True), "84.1"
    else:
        from reportlab.pdfgen.canvas import Canvas

        stream = io.BytesIO()
        canvas = Canvas(stream, pagesize=(600, 800), invariant=1)
        for y in (600, 650, 700):
            canvas.line(30, y, 300, y)
        for x in (30, 300):
            canvas.line(x, 600, x, 700)
        canvas.line(150, 600, 150, 650)
        canvas.drawString(40, 675, "Merged results header")
        canvas.drawString(40, 625, "Ours")
        canvas.drawString(170, 625, "84.1")
        canvas.save()
        raw, expected = stream.getvalue(), "84.1"
    project = Project(directory)
    entry = "paper." + kind.split("-")[0]
    project.write(entry, raw)
    project.write("results.csv", f"id,score\nresult,{expected}\n".encode())
    config = Config.model_validate(
        {
            "schema_version": 4,
            "paper": {"entry": entry},
            "sources": {
                "evidence": {
                    "path": "results.csv",
                    "format": "csv",
                    "primary_key": ["id"],
                    "columns": {"id": "string", "score": "decimal"},
                }
            },
            "metrics": {
                "score": {
                    "source": "evidence",
                    "field": "score",
                    "where": {"id": "result"},
                    "unit": "scalar",
                }
            },
        }
    )
    project.write("paperdelta.yaml", config_text(config).encode())
    candidates = [c for c in scan_project(project)["candidates"] if c["text"] == expected]
    assert len(candidates) == 1
    return {
        "paper": entry,
        "candidate": candidates[0]["candidate_id"],
        "value": expected,
        "changed": str(Decimal(expected) + 1),
        "locator": candidates[0]["locator"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--kind", choices=["docx-table", "docx-note", "pdf-rotated", "pdf-merged"], required=True
    )
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    assert output.is_relative_to(ROOT / "build")
    print(json_text(create(output, args.kind)))


if __name__ == "__main__":
    main()
