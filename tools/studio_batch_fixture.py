"""Deterministic, annotated multi-metric inputs for real browser acceptance."""

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from paperdelta import builder
from paperdelta.batch import create_catalog, inspect_catalog
from paperdelta.onboarding import init_project
from paperdelta.storage import Project, json_text, parse_json

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["001", "1", "Model-C", "Model-D", "Model-E", "Model-F"]
FIELDS = ["accuracy", "precision", "recall", "f1"]
COLUMNS = {
    "model": "string",
    "split": "string",
    "seed": "integer",
    **{key: "decimal" for key in FIELDS},
}
REQUEST = {
    "source": "results",
    "fields": FIELDS,
    "group_by": ["model"],
    "where": {"split": "test"},
    "unit": "fraction",
    "reduce": "mean",
    "expected_count": 3,
    "seed_column": "seed",
    "expected_seeds": ["1", "2", "3"],
    "display": {"kind": "percent", "places": 1, "percent_symbol": True},
}


def targets(inspection):
    result = []
    for choice in inspection["choices"]:
        model = choice["definition"]["where"]["model"]
        field = choice["definition"]["field"]
        for item in inspection["locations"]:
            row = item["row"].replace(" | ", "&").split("&")[0].strip()
            if row == model and item["column_header"].strip() == field and item["text"] == "80.0":
                result.append(
                    {
                        "model": model,
                        "field": field,
                        "choice_id": choice["choice_id"],
                        "metric_name": choice["metric_name"],
                        "candidate_id": item["candidate_id"],
                    }
                )
    return result


def create(path, kind):
    path.mkdir(parents=True, exist_ok=False)
    project = Project(path)
    rows = [["Model", *FIELDS], *[[model, *["80.0%" for _ in FIELDS]] for model in MODELS]]
    paper = path / ("paper." + kind)
    if kind == "tex":
        paper.write_text(
            "\\begin{tabular}{lrrrr}\n"
            + "\n".join(
                " & ".join(cell.replace("%", "\\%") for cell in row) + " \\\\" for row in rows
            )
            + "\n\\end{tabular}\n",
            encoding="utf-8",
            # Match the original Windows v0.6/v0.8 fixture byte for byte on every host.
            newline="\r\n",
        )
    elif kind == "docx":
        from docx import Document

        document = Document()
        table = document.add_table(rows=len(rows), cols=len(rows[0]))
        table.style = "Table Grid"
        for row, values in zip(table.rows, rows, strict=True):
            for cell, value in zip(row.cells, values, strict=True):
                cell.text = value
        document.save(paper)
    else:
        from reportlab.pdfgen.canvas import Canvas

        canvas = Canvas(str(paper), invariant=True)
        canvas.setFont("Helvetica", 10)
        left, top, width, height = 42, 748, 98, 30
        for index in range(len(rows) + 1):
            canvas.line(
                left, top - index * height, left + len(rows[0]) * width, top - index * height
            )
        for index in range(len(rows[0]) + 1):
            canvas.line(left + index * width, top, left + index * width, top - len(rows) * height)
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                canvas.drawString(left + column * width + 6, top - row * height - 20, value)
        canvas.save()
    project.write(
        "results.csv",
        (
            "model,split,seed,"
            + ",".join(FIELDS)
            + "\n"
            + "".join(
                f"{model},{split},{seed},"
                + ",".join("0.80000000000000000000000000001" for _ in FIELDS)
                + "\n"
                for model in MODELS
                for split in ("test", "train")
                for seed in (1, 2, 3)
            )
        ).encode(),
    )
    init_project(project, paper.name, ["results.csv"])
    draft = builder.add_source(
        project,
        builder.start_draft(project),
        name="results",
        path="results.csv",
        format="csv",
        columns=COLUMNS,
        primary_key=["model", "split", "seed"],
    )
    inspection = inspect_catalog(project, create_catalog(project, draft, REQUEST))
    selected = targets(inspection)
    assert len(selected) == len(MODELS) * len(FIELDS), (kind, len(selected))
    project.write(
        "browser-annotations.json",
        json_text({"source": COLUMNS, "request": REQUEST, "targets": selected}).encode(),
    )
    return {"document": kind, "metrics": len(selected), "positions": len(selected)}


def propose(path, provider):
    project = Project(path)
    catalog = create_catalog(project, builder.start_draft(project), REQUEST)
    selected = targets(inspect_catalog(project, catalog))
    assert selected, "Choose a project with remaining unbound result cells"
    choices = [
        {
            "choice_id": item["choice_id"],
            "candidate_ids": [item["candidate_id"]],
            "rationale": f"{item['model']}, {item['field']}, test split, all three seeds.",
        }
        for item in selected
    ]
    output = provider + "-proposal.json"
    if provider == "cli":
        project.write("cli-request.json", json_text(REQUEST).encode(), exclusive=True)
        project.write("cli-selections.json", json_text(choices).encode(), exclusive=True)
        for arguments in [
            ["scan", "--request", "cli-request.json", "--out", "cli-catalog.json"],
            [
                "propose",
                "--catalog",
                "cli-catalog.json",
                "--selections",
                "cli-selections.json",
                "--out",
                output,
            ],
        ]:
            result = subprocess.run(
                [
                    sys.executable,
                    "-X",
                    "utf8",
                    "-m",
                    "paperdelta",
                    "-C",
                    str(path),
                    "batch",
                    *arguments,
                ],
                capture_output=True,
                encoding="utf-8",
            )
            assert result.returncode == 0, result.stderr
    else:
        import mcp

        from paperdelta.mcp_server import create_server

        async def through_mcp():
            async with mcp.Client(create_server(project)) as client:
                payload = {key: value for key, value in REQUEST.items() if key != "display"}
                payload.update(display_kind="percent", places=1, percent_symbol=True)
                response = await client.call_tool("start_batch_binding", payload)
                assert not response.is_error, response
                session_id = response.structured_content["session_id"]
                for choice in choices:
                    response = await client.call_tool(
                        "select_batch_bindings", {"session_id": session_id, **choice}
                    )
                    assert not response.is_error, response
                response = await client.call_tool(
                    "finish_batch_binding", {"session_id": session_id}
                )
                assert not response.is_error, response
                return response.structured_content["proposal_json"]

        project.write(output, asyncio.run(through_mcp()).encode("utf-8"), exclusive=True)
    proposal = parse_json(project.text(output)[0])
    return {"path": output, "provider": provider, "bindings": list(proposal["rationale"])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--document", choices=["tex", "docx", "pdf"], default="tex")
    parser.add_argument("--proposal", choices=["cli", "mcp"])
    args = parser.parse_args()
    path = (ROOT / args.out).resolve()
    assert path.is_relative_to(ROOT / "build")
    print(
        json.dumps(propose(path, args.proposal) if args.proposal else create(path, args.document))
    )


if __name__ == "__main__":
    main()
