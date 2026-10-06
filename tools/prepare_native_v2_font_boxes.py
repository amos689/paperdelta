"""Add PDFium font boxes for the independently selected original glyphs.

Ink boxes and glyph advances differ. Keep both; never change target text, original
location or the initially saved scores. This does not import PaperDelta.
"""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "validation/native-v2"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["development", "held-out"], required=True)
    args = parser.parse_args()
    if args.split == "held-out":
        assert (CORPUS / "implementation-lock.json").exists()
    source = CORPUS / f"{args.split}-gold.json"
    targets = json.loads(source.read_text("utf-8"))["targets"]
    boxes = {}
    for case in dict.fromkeys(t["case"] for t in targets if t["format"] == "pdf"):
        independent = json.loads(
            (ROOT / "build/native-v2" / args.split / case / "independent-pdf.json").read_text(
                "utf-8"
            )
        )
        with pdfium.PdfDocument(str(CORPUS / "papers" / case / "article.pdf")) as doc:
            for target in (t for t in targets if t["case"] == case and t["format"] == "pdf"):
                page = doc[target["locator"]["page"] - 1]
                tp = page.get_textpage()
                ink = target["locator"]["bbox"]
                characters = [
                    c
                    for c in independent[target["locator"]["page"] - 1]["characters"]
                    if c["bbox"][0] >= ink[0] - 0.0001
                    and c["bbox"][1] >= ink[1] - 0.0001
                    and c["bbox"][2] <= ink[2] + 0.0001
                    and c["bbox"][3] <= ink[3] + 0.0001
                ]
                assert "".join(c["text"] for c in characters) == target["text"], target["id"]
                rects = [tp.get_charbox(c["index"], loose=True) for c in characters]
                boxes[target["id"]] = [
                    min(b[0] for b in rects),
                    page.get_height() - max(b[3] for b in rects),
                    max(b[2] for b in rects),
                    page.get_height() - min(b[1] for b in rects),
                ]
                tp.close()
                page.close()
    result = {
        "created_at": datetime.now(UTC).isoformat(),
        "gold_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "method": (
            "PDFium loose=True font boxes at the exact original annotated glyph indices; "
            "original ink boxes preserved."
        ),
        "boxes": boxes,
    }
    with (CORPUS / f"{args.split}-font-boxes.json").open(
        "x", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
