"""Independently extract the preselected native-v2 originals for annotation.

No PaperDelta code is imported. Held-out access requires the implementation lock.
This prepares annotation material, not gold or scores.
"""

import argparse
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "validation/native-v2"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def word_text(paragraph):
    return "".join(
        node.text or "" if node.tag == W + "t" else "\t" if node.tag == W + "tab" else "\n"
        for node in paragraph.iter()
        if node.tag in {W + "t", W + "tab", W + "br", W + "cr"}
    )


def extract_word(path):
    with ZipFile(path) as archive:
        body = ET.fromstring(archive.read("word/document.xml")).find(W + "body")
        paragraphs = {id(p): n for n, p in enumerate(body.iter(W + "p"), 1)}
        tables = []
        for number, table in enumerate(body.iter(W + "tbl"), 1):
            rows = []
            for row_number, row in enumerate(table.findall(W + "tr"), 1):
                cells = []
                for column, cell in enumerate(row.findall(W + "tc"), 1):
                    cells.append(
                        {
                            "cell": column,
                            "paragraphs": [
                                {"paragraph": paragraphs[id(p)], "text": word_text(p)}
                                for p in cell.findall(W + "p")
                            ],
                            "properties": ET.tostring(cell.find(W + "tcPr"), encoding="unicode")
                            if cell.find(W + "tcPr") is not None
                            else "",
                        }
                    )
                rows.append({"row": row_number, "cells": cells})
            tables.append({"table": number, "rows": rows})
        return {
            "tables": tables,
            "prose": [
                {"paragraph": paragraphs[id(p)], "text": word_text(p)}
                for p in body.findall(W + "p")
            ],
        }


def extract_pdf(path):
    pages = []
    with pdfium.PdfDocument(str(path)) as document:
        for number, page in enumerate(document, 1):
            textpage = page.get_textpage()
            characters = []
            for index in range(textpage.count_chars()):
                char = textpage.get_text_range(index, 1)
                if not char.strip():
                    continue
                try:
                    left, bottom, right, top = textpage.get_charbox(index)
                except pdfium.PdfiumError:
                    continue
                characters.append(
                    {
                        "index": index,
                        "text": char,
                        "bbox": [
                            left,
                            page.get_height() - top,
                            right,
                            page.get_height() - bottom,
                        ],
                    }
                )
            pages.append(
                {
                    "page": number,
                    "width": page.get_width(),
                    "height": page.get_height(),
                    "text": textpage.get_text_range(),
                    "characters": characters,
                }
            )
            textpage.close()
            page.close()
    return pages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", required=True, choices=["development", "held-out"])
    args = parser.parse_args()
    if args.split == "held-out":
        assert (CORPUS / "implementation-lock.json").is_file(), "Implementation must be frozen"
        assert not (CORPUS / "first-heldout.json").exists(), (
            "Use frozen originals after first score"
        )
    output = ROOT / "build/native-v2" / args.split
    assert not output.exists(), "Do not overwrite independent annotation material"
    for item in json.loads((CORPUS / "sources.json").read_text("utf-8"))["papers"]:
        if item["split"] != args.split:
            continue
        dest = output / item["id"]
        dest.mkdir(parents=True)
        for filename, metadata in item["files"].items():
            source = CORPUS / "papers" / item["id"] / filename
            assert hashlib.sha256(source.read_bytes()).hexdigest() == metadata["sha256"]
            if filename.endswith(".pdf"):
                pages = extract_pdf(source)
                (dest / "article.txt").write_text(
                    "\n".join(f"--- PAGE {p['page']} ---\n{p['text']}" for p in pages), "utf-8"
                )
                result, name = pages, "independent-pdf.json"
            else:
                result, name = extract_word(source), "independent-word.json"
                (dest / "word.txt").write_text(
                    "\n".join(
                        [f"PROSE p{p['paragraph']} {p['text']}" for p in result["prose"]]
                        + [
                            f"TABLE {t['table']} ROW {r['row']} CELL {c['cell']} "
                            f"p{p['paragraph']}: {p['text']}"
                            for t in result["tables"]
                            for r in t["rows"]
                            for c in r["cells"]
                            for p in c["paragraphs"]
                            if p["text"]
                        ]
                    ),
                    "utf-8",
                )
            (dest / name).write_text(json.dumps(result, ensure_ascii=False), "utf-8")
            print(
                json.dumps(
                    {
                        "case": item["id"],
                        "file": filename,
                        "units": len(result) if isinstance(result, list) else len(result["tables"]),
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
