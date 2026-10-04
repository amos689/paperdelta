"""Owned native fixtures for real second-experiment browser workflows."""

from __future__ import annotations

import argparse
import io
from decimal import Decimal
from pathlib import Path

from paperdelta.config import config_text, load_config
from paperdelta.documents import PaperIndex
from paperdelta.models import Anchor, Claim, Predicate, Threshold
from paperdelta.storage import Project
from paperdelta.studio import StudioSession


def manuscript(project, kind, revised=False):
    paragraphs = [
        "Revised measurement =84.1%; updated context." if revised else "Abstract score: 84.1%.",
        "Second result: 84.1%.",
        "Our method outperforms Baseline.",
    ]
    if kind == "tex":
        raw = ("\n".join(paragraphs).replace("%", r"\%") + "\n").encode()
    elif kind == "docx":
        from docx import Document

        document = Document()
        for paragraph in paragraphs:
            document.add_paragraph(paragraph)
        output = io.BytesIO()
        document.save(output)
        raw = output.getvalue()
    else:
        from reportlab.pdfgen.canvas import Canvas

        output = io.BytesIO()
        canvas = Canvas(output, invariant=True)
        for index, paragraph in enumerate(paragraphs):
            canvas.drawString(60, 740 - 40 * index, paragraph)
        canvas.save()
        raw = output.getvalue()
    project.write("paper." + kind, raw)


def create(directory, kind):
    directory.mkdir(parents=True, exist_ok=False)
    project = Project(directory)
    manuscript(project, kind)
    project.write("results.csv", b"model,seed,score\n001,1,0.840\n001,2,0.842\n002,1,0.123\n")
    session = StudioSession(project)

    def call(action, payload):
        return session.execute({"action": action, "revision": session.revision, "payload": payload})

    call("initialize", {"paper": "paper." + kind, "data": ["results.csv"]})
    source = call("source-preview", {"path": "results.csv"})["source"]
    call(
        "source",
        {
            "name": "experiment",
            "path": "results.csv",
            "format": "csv",
            "columns": {"model": "string", "seed": "integer", "score": "decimal"},
            "primary_key": ["model", "seed"],
            "source_hash": source["hash"],
        },
    )
    call(
        "metric",
        {
            "name": "ours",
            "source": "experiment",
            "field": "score",
            "unit": "fraction",
            "reduce": "mean",
            "where": {"model": "001"},
            "expected_count": 2,
            "expected_seeds": ["1", "2"],
        },
    )
    state = call("state", {})["state"]
    call(
        "locations",
        {
            "metric": "ours",
            "candidate_ids": [item["candidate_id"] for item in state["candidates"]],
            "names": ["abstract", "result"],
            "display_kind": "percent",
            "places": 1,
            "percent_symbol": True,
            "rationale": "Model 001, both declared seeds.",
        },
    )
    preview = call("preview", {})["state"]["preview"]
    call(
        "accept",
        {
            "proposal_id": preview["proposal_id"],
            "selected": ["occurrences:abstract", "occurrences:result"],
        },
    )
    config, _ = load_config(project)
    config.claims["comparison"] = Claim(
        file="paper." + kind,
        anchor=Anchor(
            exact="Our method outperforms Baseline.",
            parser=PaperIndex(project, config.paper).document("paper." + kind).parser
            if kind == "pdf"
            else None,
        ),
        predicate=Predicate(
            op="greater_than", left="ours", right=Threshold(value=Decimal("0.81"), unit="fraction")
        ),
    )
    project.write("paperdelta.yaml", config_text(config).encode("utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("kind", choices=["tex", "docx", "pdf"])
    parser.add_argument("--revise", action="store_true")
    arguments = parser.parse_args()
    if arguments.revise:
        manuscript(Project(arguments.directory), arguments.kind, revised=True)
    else:
        create(arguments.directory, arguments.kind)
