"""Recheck the four historical PDF misses without changing frozen ink-box gold."""

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import evaluate_native_v2 as evaluator
import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "validation/native-v1"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    assert output.is_relative_to(ROOT / "build") and not output.exists()
    output.mkdir(parents=True)
    gold = json.loads((CORPUS / "held-out-gold.json").read_text("utf-8"))
    targets = [
        t
        for t in gold["targets"]
        if t["id"]
        in {
            "held-061",
            "held-062",
            "held-063",
            "held-064",
        }
    ]
    assert len(targets) == 4
    source = CORPUS / "papers/pet-repeatability/article.pdf"
    original = hashlib.sha256(source.read_bytes()).hexdigest()
    independent = []
    with pdfium.PdfDocument(str(source)) as document:
        page = document[1]
        textpage = page.get_textpage()
        height = page.get_height()
        for target in targets:
            ink = target["locator"]["bbox"]
            indices = []
            for i in range(textpage.count_chars()):
                if textpage.get_text_range(i, 1).isspace():
                    continue
                left, bottom, right, top = textpage.get_charbox(i)
                if (
                    left >= ink[0] - 0.001
                    and right <= ink[2] + 0.001
                    and height - top >= ink[1] - 0.001
                    and height - bottom <= ink[3] + 0.001
                ):
                    indices.append(i)
            text = "".join(textpage.get_text_range(i, 1) for i in indices)
            assert text == target["text"], (target["id"], text)
            boxes = [textpage.get_charbox(i, loose=True) for i in indices]
            bounds = [
                min(b[0] for b in boxes),
                height - max(b[3] for b in boxes),
                max(b[2] for b in boxes),
                height - min(b[1] for b in boxes),
            ]
            independent.append(
                {
                    "id": target["id"],
                    "glyph_indices": indices,
                    "original_ink_bbox": ink,
                    "independent_font_bbox": bounds,
                }
            )
            target["locator"] = {"page": 2, "ink_bbox": ink, "bbox": bounds}
        textpage.close()
        page.close()
    evaluator.CORPUS = CORPUS
    results = evaluator.score_file(output, "pet-repeatability", "article.pdf", targets)
    assert hashlib.sha256(source.read_bytes()).hexdigest() == original
    receipt = {
        "created_at": datetime.now(UTC).isoformat(),
        "source_sha256": original,
        "gold_sha256": hashlib.sha256((CORPUS / "held-out-gold.json").read_bytes()).hexdigest(),
        "scope": "Regression of four previously observed misses; not fresh held-out evidence.",
        "coordinate_note": "Exact original PDFium glyphs, compared using independent font boxes.",
        "independent_locations": independent,
        "results": results,
        "counts": {k: sum(t["outcome"] == k for t in results) for k in evaluator.OUTCOMES},
    }
    evaluator.save(output / "results.json", receipt)
    print(json.dumps(receipt["counts"]))
    assert all(t["outcome"] == "supported" for t in results)


if __name__ == "__main__":
    main()
