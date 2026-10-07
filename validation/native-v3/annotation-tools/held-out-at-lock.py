"""Annotate unseen originals after the native-v3 implementation freeze.

Only independent PDFium/OOXML data is consulted. No product parser is imported.
Rendered pages must be inspected and a separate gold lock written before scoring.
"""

import hashlib
import json
from collections import Counter
from decimal import Decimal

import annotate_native_v3_development as original
import pypdfium2 as pdfium


def value_fields(text, shape):
    if shape == "scientific" and "e" in text:
        return {"shape": shape, "value": str(Decimal("".join(text.split())))}
    return old_value_fields(text, shape)


old_value_fields = original.value_fields


def main():
    original.QA = original.ROOT / "build/native-v3/held-out"
    original.value_fields = value_fields
    original.targets.clear()
    pdf, targets = original.pdf, original.targets
    fallback = original.FALLBACK + " Observed sample sizes in result captions are eligible."
    case = "plosgenetics-1011507"
    for prefix, literal in [("(3 males and 1 female)", "3"), ("and 1 female)", "1")]:
        pdf(case, 5, prefix, literal, reason=fallback)
    for literal in ["1.94 e -06", "5.13 e -05"]:
        pdf(case, 5, literal, literal, shape="scientific", reason=fallback)
    for prefix, literal in [
        ("only 4 heterozygous females", "4"),
        ("and 2 hemizygous males were found", "2"),
        ("among 39 blastocysts", "39"),
    ]:
        pdf(case, 5, prefix, literal, reason=fallback)
    for prefix, literal in [
        ("found 120 differentially", "120"),
        ("(N = 10 embryos per embryo genotype)", "10"),
        ("(N = 9 WT,", "9"),
        ("9 WT, 10 OgtT931del/Y", "10"),
    ]:
        pdf(case, 7, prefix, literal, reason=fallback)
    pdf(case, 8, "with 2/3 of the genes", "2/3", shape="fraction", reason=fallback)
    pdf(case, 8, "and 90% of the", "90", reason=fallback)
    for prefix, literal in [
        ("N = 20 WT crosses", "20"),
        ("crosses, 8 OgtY851A/+", "8"),
        ("and 6 OgtY851A/Y851A", "6"),
    ]:
        pdf(case, 10, prefix, literal, reason=fallback)

    case = "plosmedicine-1004504"
    for literal in [
        "24,123 (33.7)",
        "41,297 (52.4)",
        "17,202 (24.0)",
        "6,034 (7.7)",
        "7,907 (11.0)",
        "6,681 (8.5)",
        "48,721 (68.1)",
        "55,165 (70.0)",
        "10,904 (15.2)",
        "12,706 (16.1)",
        "2,546 (3.6)",
        "2,713 (3.4)",
    ]:
        pdf(case, 8, literal, literal, shape="count_percent", reason=original.TABLE)
    for page, prefix, literal in [
        (1, "(N = 150,370)", "150,370"),
        (1, "(N = 358,548)", "358,548"),
        (2, "from 33.7% in period 1", "33.7"),
        (2, "to 52.4% in period 2", "52.4"),
    ]:
        pdf(case, page, prefix, literal)

    case = "peerj-pmc11748422"
    for prefix, literal, shape in [
        ("Rtemp = −0.923,", "−0.923", "scalar"),
        ("Rtemp = −0.923, p < 0.001;", "< 0.001", "inequality"),
        ("RpH = −0.445,", "−0.445", "scalar"),
        ("RpH = −0.445, p < 0.001)", "< 0.001", "inequality"),
        ("R = 0.702,", "0.702", "scalar"),
        ("R = 0.702, p < 0.001)", "< 0.001", "inequality"),
        ("pH of 4.23–6.08", "4.23–6.08", "range"),
        ("R = −0.689,", "−0.689", "scalar"),
        ("R = −0.689, p < 0.001)", "< 0.001", "inequality"),
        ("R = 0.622,", "0.622", "scalar"),
        ("R = 0.622, p = 0.031)", "0.031", "scalar"),
        ("R = 0.829,", "0.829", "scalar"),
        ("R = 0.829, p < 0.001)", "< 0.001", "inequality"),
    ]:
        pdf(case, 7, prefix, literal, shape=shape, reason=original.FALLBACK)
    for prefix, literal, shape in [
        ("HCBH = 21.81,", "21.81", "scalar"),
        ("HCBH = 21.81, p < 0.001;", "< 0.001", "inequality"),
        ("HBG = 14.75,", "14.75", "scalar"),
    ]:
        pdf(case, 8, prefix, literal, shape=shape, reason=original.FALLBACK)

    case = "scientific-reports-pmc11782508"
    pdf(case, 1, "(1500–1700 cm−1)", "1500–1700", shape="range", reason=original.FALLBACK)
    for prefix, literal in [
        ("for azurin was about 0.54", "0.54"),
        ("revealed 99.65% similarity", "99.65"),
        ("theoretical pI of 6.39", "6.39"),
        ("aliphatic index of 84.32", "84.32"),
        ("(GRAVY) of -0.099", "-0.099"),
        ("97% probability", "97"),
        ("observed after 36 h", "36"),
        ("ratio of approximately 0.54", "0.54"),
    ]:
        pdf(case, 2, prefix, literal, reason=original.FALLBACK)
    for prefix, literal, shape in [
        ("approximately 14 kDa", "14", "scalar"),
        ("observed at 1657–1650", "1657–1650", "range"),
        ("and 1550–1540", "1550–1540", "range"),
        ("between 1400 and 1000", "1400 and 1000", "range"),
        ("observed at 3439", "3439", "scalar"),
        ("and 3429", "3429", "scalar"),
        ("approximately 8.0 keV", "8.0", "scalar"),
    ]:
        pdf(case, 3, prefix, literal, shape=shape, reason=original.FALLBACK)

    case = "plosmedicine-1004504"
    data = json.loads((original.QA / case / "independent-docx.json").read_text("utf-8"))
    for row in data["tables"][0]["rows"]:
        if row["row"] not in {4, 5, 6, 8}:
            continue
        for cell in row["cells"]:
            if cell["cell"] < 3:
                continue
            paragraphs = [p for p in cell["paragraphs"] if p["text"].strip()]
            assert len(paragraphs) == 1
            paragraph = paragraphs[0]
            text = paragraph["text"].strip()
            shape = "interval" if ";" in text else "scalar"
            targets.append(
                {
                    "case": case,
                    "file": "supplement.docx",
                    "format": "docx",
                    "text": text,
                    "locator": {
                        "part": "word/document.xml",
                        "paragraph": paragraph["paragraph"],
                        "offset": len(paragraph["text"]) - len(paragraph["text"].lstrip()),
                        "last_paragraph": paragraph["paragraph"],
                    },
                    "source_cell": {"table": 1, "row": row["row"], "physical_cell": cell["cell"]},
                    "selection_reason": original.TABLE
                    + " No measured prose; continue table for four remaining slots.",
                    **value_fields(text, shape),
                }
            )
    counts = Counter((t["case"], t["file"]) for t in targets)
    assert len(targets) == 80 and set(counts.values()) == {16}
    boxes = {}
    for index, target in enumerate(targets, 1):
        target["id"] = f"held-{index:03d}"
        source = original.CORPUS / "papers" / target["case"] / target["file"]
        target["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        if target["format"] != "pdf":
            continue
        with pdfium.PdfDocument(str(source)) as document:
            page = document[target["locator"]["page"] - 1]
            tp = page.get_textpage()
            rects = [tp.get_charbox(i, loose=True) for i in target["original_character_indices"]]
            boxes[target["id"]] = [
                min(b[0] for b in rects),
                page.get_height() - max(b[3] for b in rects),
                max(b[2] for b in rects),
                page.get_height() - min(b[1] for b in rects),
            ]
            tp.close()
            page.close()
    gold = {
        "split": "held-out",
        "planned_slots": 96,
        "targets": targets,
        "shortfalls": [
            {
                "case": "plosgenetics-1011507",
                "file": "supplement.docx",
                "eligible_targets": 0,
                "unfilled_slots": 16,
                "reason": "Allele-description table contains mutation identifiers, targeted exons, genomic coordinates and sequences, not measured outcomes. Original retained; no replacement.",
            }
        ],
        "annotation": "Developer-selected independent original positions after implementation freeze and before held-out product scores. Complete compounds are single targets, not fragment successes.",
    }
    path = original.CORPUS / "held-out-gold.json"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(gold, ensure_ascii=False, indent=2) + "\n")
    with (original.CORPUS / "held-out-font-boxes.json").open(
        "x", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write(
            json.dumps(
                {
                    "gold_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "method": "PDFium loose font boxes at independent original glyph indices; ink boxes retained.",
                    "boxes": boxes,
                },
                indent=2,
            )
            + "\n"
        )
    print(
        json.dumps(
            {
                "targets": len(targets),
                "unfilled_slots": 16,
                "shapes": dict(Counter(t["shape"] for t in targets)),
            }
        )
    )


if __name__ == "__main__":
    main()
