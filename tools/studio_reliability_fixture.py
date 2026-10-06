"""Authored multi-value and reviewed-identity fixtures for the real browser."""

import argparse
import io
import sys
from pathlib import Path

from paperdelta.config import config_text
from paperdelta.models import Config
from paperdelta.onboarding import scan_project
from paperdelta.storage import Project, json_text

ROOT = Path(__file__).resolve().parents[1]


def create(directory, kind):
    sys.path.insert(0, str(ROOT / "tests"))
    from test_native_reliability import word_table

    directory.mkdir(parents=True, exist_ok=False)
    expected = "84.1"
    if kind == "docx-omitted":
        raw = word_table([("Ours", "84.1"), ("Baseline", "80.9")], before=1, after=1)
    elif kind == "docx-multivalue":
        raw = word_table([("Ours", "84.1 ± 1.2 (n = 3)")])
        expected = "1.2"
    elif kind == "docx-reviewed":
        raw = word_table([("001", "84.1 ± 1.2"), ("002", "84.1 ± 1.2")])
    else:
        from reportlab.pdfgen.canvas import Canvas

        stream = io.BytesIO()
        canvas = Canvas(stream, pagesize=(600, 800), invariant=1)
        text = canvas.beginText(40, 720)
        text.setFont("Helvetica", 12)
        text.textOut("Magnitude 10")
        text.setRise(6)
        text.setFont("Helvetica", 8)
        text.textOut("2")
        text.setRise(0)
        text.setFont("Helvetica", 12)
        text.textOut("; accuracy 84.1 percent.")
        canvas.drawText(text)
        canvas.save()
        raw = stream.getvalue()
    project = Project(directory)
    entry = "PRIVATE-manuscript." + kind.split("-")[0]
    project.write(entry, raw)
    project.write("PRIVATE-evidence.csv", f"id,score\nresult,{expected}\n".encode())
    config = Config.model_validate(
        {
            "schema_version": 9,
            "paper": {"entry": entry},
            "sources": {
                "evidence": {
                    "path": "PRIVATE-evidence.csv",
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
    candidate = next(c for c in scan_project(project)["candidates"] if c["text"] == expected)
    return {"paper": entry, "candidate": candidate["candidate_id"], "value": expected}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument(
        "--kind",
        required=True,
        choices=[
            "docx-omitted",
            "docx-multivalue",
            "docx-reviewed",
            "pdf-superscript",
        ],
    )
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    assert output.is_relative_to(ROOT / "build")
    print(json_text(create(output, args.kind)))
