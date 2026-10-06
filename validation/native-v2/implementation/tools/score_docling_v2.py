"""Compare Docling containers at original positions, not equal values elsewhere.

A correctly extracted container is not an identity-preserving PaperDelta binding.
DOCX without original paragraph/offset provenance is explicitly unlocated.
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "validation/native-v2"
NUMBER = re.compile(r"(?<![A-Za-z0-9])[-−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![A-Za-z0-9])")


def top_box(box, height):
    if box.get("coord_origin") == "BOTTOMLEFT":
        return [box["l"], height - box["t"], box["r"], height - box["b"]]
    return [box["l"], box["t"], box["r"], box["b"]]


def score(document, target):
    if target["format"] == "docx":
        return {
            "outcome": "unknown_original_position",
            "reason": "no_OOXML_paragraph_offset_provenance",
        }
    page, ink = target["locator"]["page"], target["locator"]["bbox"]
    size = document["pages"][str(page)]["size"]
    height = size["height"]
    candidates = []
    for item in document["texts"]:
        for provenance in item.get("prov", []):
            if provenance["page_no"] == page:
                candidates.append(
                    ("text", item["self_ref"], item["text"], top_box(provenance["bbox"], height))
                )
    for table in document["tables"]:
        if len(table.get("prov", [])) != 1 or table["prov"][0]["page_no"] != page:
            continue
        for number, cell in enumerate(table["data"]["table_cells"]):
            if cell.get("bbox"):
                candidates.append(
                    (
                        "table_cell",
                        f"{table['self_ref']}/{number}",
                        cell["text"],
                        top_box(cell["bbox"], height),
                    )
                )
    contained = [
        (kind, ref, text)
        for kind, ref, text, box in candidates
        if box[0] - 1.2 <= ink[0]
        and box[2] + 1.2 >= ink[2]
        and box[1] - 2 <= (ink[1] + ink[3]) / 2 <= box[3] + 2
    ]
    matching = [
        (kind, ref)
        for kind, ref, text in contained
        if target["text"] in [m[0] for m in NUMBER.finditer(text)]
    ]
    if len(matching) == 1:
        return {
            "outcome": "extracted_in_original_container",
            "container_kind": matching[0][0],
            "container": matching[0][1],
            "exact_token_position": False,
        }
    return {"outcome": "ambiguous_container" if matching else "not_extracted_at_original_position"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=["development", "held-out"], required=True)
    args = parser.parse_args()
    if args.split == "held-out":
        assert (CORPUS / "held-out-gold-lock.json").exists()
    output = ROOT / "build/native-v2/docling" / (args.split + "-pdfium")
    gold = json.loads((CORPUS / f"{args.split}-gold.json").read_text("utf-8"))
    results = []
    cache = {}
    for target in gold["targets"]:
        filename = f"{target['case']}-{target['format']}.json"
        if filename not in cache:
            path = output / filename
            cache[filename] = json.loads(path.read_text("utf-8")) if path.exists() else None
        verdict = (
            score(cache[filename], target) if cache[filename] else {"outcome": "conversion_failed"}
        )
        results.append(
            {"id": target["id"], "case": target["case"], "format": target["format"], **verdict}
        )
    result = {
        "comparison_scope": (
            "position-scoped extraction containers, not accepted bindings "
            "or exact original token positions"
        ),
        "counts": dict(Counter(item["outcome"] for item in results)),
        "results": results,
    }
    with (output / "scores.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
