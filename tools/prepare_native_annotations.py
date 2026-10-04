"""Read original documents with OOXML/PDFium only, before PaperDelta scoring."""

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "validation/native-v1"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["development", "held-out"], required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    assert output.is_relative_to(ROOT / "build") and not output.exists()
    if args.split == "held-out":
        assert (CORPUS / "implementation-lock.json").exists()
        assert not (CORPUS / "first-run-start.json").exists()
    sources = json.loads((CORPUS / "sources.json").read_text("utf-8"))
    for item in sources["papers"]:
        if item["split"] != args.split:
            continue
        case = item["id"]
        dest, source = output / case, CORPUS / "papers" / case
        dest.mkdir(parents=True)
        pages = []
        with pdfium.PdfDocument(str(source / "article.pdf")) as document:
            for number, page in enumerate(document, 1):
                textpage = page.get_textpage()
                text, characters = textpage.get_text_range(), []
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
                        "text": text,
                        "characters": characters,
                    }
                )
                textpage.close()
                page.close()
        (dest / "article.txt").write_text(
            "\n".join(f"--- PAGE {p['page']} ---\n{p['text']}" for p in pages),
            "utf-8",
            newline="\n",
        )
        (dest / "independent-pdf.json").write_text(
            json.dumps(pages, ensure_ascii=False), "utf-8", newline="\n"
        )
        with ZipFile(source / "supplement.docx") as archive:
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
                                    {"paragraph": paragraphs[id(p)], "text": "".join(p.itertext())}
                                    for p in cell.findall(W + "p")
                                ],
                                "properties": ET.tostring(cell.find(W + "tcPr"), encoding="unicode")
                                if cell.find(W + "tcPr") is not None
                                else "",
                            }
                        )
                    rows.append({"row": row_number, "cells": cells})
                tables.append({"table": number, "rows": rows})
            prose = [
                {"paragraph": paragraphs[id(p)], "text": "".join(p.itertext())}
                for p in body.findall(W + "p")
            ]
        (dest / "independent-word.json").write_text(
            json.dumps({"tables": tables, "prose": prose}, ensure_ascii=False, indent=2),
            "utf-8",
            newline="\n",
        )
        print(json.dumps({"case": case, "pdf_pages": len(pages), "word_tables": len(tables)}))


if __name__ == "__main__":
    main()
