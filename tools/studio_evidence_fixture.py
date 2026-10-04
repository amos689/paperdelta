"""Small native evidence fixtures with exact identities for browser acceptance."""

import argparse
import io
import zipfile
from pathlib import Path

from paperdelta import builder
from paperdelta.batch import create_catalog, inspect_catalog
from paperdelta.experiment_imports import import_evidence
from paperdelta.onboarding import init_project
from paperdelta.storage import Project, json_text

ROOT = Path(__file__).resolve().parents[1]
COLUMNS = {"model": "string", "seed": "integer", "accuracy": "decimal"}
TABLE = "model\tseed\taccuracy\n001\t1\t0.80000000000000000000000000001\n1\t2\t0.9\n"
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def workbook():
    rows = []
    for y, values in enumerate([row.split("\t") for row in TABLE.splitlines()], 1):
        cells = []
        for x, value in enumerate(values):
            address = chr(65 + x) + str(y)
            if y == 1 or x == 0:
                cells.append(f'<c r="{address}" t="inlineStr"><is><t>{value}</t></is></c>')
            else:
                cells.append(f'<c r="{address}"><v>{value}</v></c>')
        rows.append(f'<row r="{y}">{"".join(cells)}</row>')
    stream = io.BytesIO()
    files = {
        "[Content_Types].xml": (
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
            'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-'
            'officedocument.spreadsheetml.worksheet+xml"/></Types>'
        ),
        "_rels/.rels": f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" '
        f'Type="{REL}/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/workbook.xml": f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets>'
        '<sheet name="结果 Results" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": f'<Relationships xmlns="{PKG}"><Relationship Id="rId1" '
        f'Type="{REL}/worksheet" Target="worksheets/sheet1.xml"/>'
        "</Relationships>",
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{NS}"><sheetData>{"".join(rows)}'
        "</sheetData></worksheet>",
    }
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, contents in files.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, contents.encode("utf-8"))
    return stream.getvalue()


def create(directory, kind):
    directory.mkdir(parents=True, exist_ok=False)
    project = Project(directory)
    project.write(
        "paper.tex", b"Model 001 primary accuracy: 80.0\\%.\nModel 1 control accuracy: 90.0\\%.\n"
    )
    source = {
        "path": "results." + kind,
        "format": kind,
        "columns": COLUMNS,
        "primary_key": ["model"],
    }
    if kind == "xlsx":
        project.write(source["path"], workbook())
        source.update(sheet="结果 Results", cell_range="A1:C3")
    else:
        project.write("results.tsv", TABLE.encode("utf-8"))
        if kind == "records":
            local = {**source, "path": "results.tsv", "format": "tsv"}
            request = {"provider": "file", "origin": local["path"], "source": local}
            source = import_evidence(project, request, "results.pdevidence.json")["source"]
            project.path("results.tsv").unlink()
    init_project(project, "paper.tex", [source["path"]])
    draft = builder.add_source(project, builder.start_draft(project), name="results", **source)
    request = {
        "source": "results",
        "fields": ["accuracy"],
        "group_by": ["model"],
        "unit": "fraction",
        "reduce": "unique",
        "expected_count": 1,
        "display": {"kind": "percent", "places": 1, "percent_symbol": True},
    }
    catalog = inspect_catalog(project, create_catalog(project, draft, request))
    targets = []
    for choice in catalog["choices"]:
        observed = "80.0" if choice["definition"]["where"]["model"] == "001" else "90.0"
        location = next(item for item in catalog["locations"] if item["text"] == observed)
        targets.append({"choice_id": choice["choice_id"], "candidate_id": location["candidate_id"]})
    return {"source": source, "request": request, "targets": targets}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--kind", choices=["tsv", "xlsx", "records"], required=True)
    args = parser.parse_args()
    target = (ROOT / args.out).resolve()
    if not target.is_relative_to(ROOT / "build"):
        raise SystemExit("Fixture output must be under build/.")
    print(json_text(create(target, args.kind)), end="")
