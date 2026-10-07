"""Select complete development values from independent OOXML/PDFium originals.

No product parser or candidate result is used. Rendered pages are reviewed before
the separate gold lock. Unsupported compounds remain single targets.
"""

import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pypdfium2 as pdfium

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "validation/native-v3"
QA = ROOT / "build/native-v3/development"
targets = []
font_boxes = {}
TABLE = (
    "First result/observed-characteristics table in original reading order; "
    "exclude IDs, dates and category labels."
)
PROSE = "First measured abstract/results values; exclude citations and method constants."
FALLBACK = (
    "No main-article result table. Fill table slots using subsequent "
    "measured abstract/results values."
)


def normalized(text):
    output, indices = [], []
    for index, char in enumerate(text):
        char = " " if char.isspace() else char
        if char == " " and output and output[-1] == " ":
            continue
        output.append(char)
        indices.append(index)
    return "".join(output), indices


def value_fields(text, shape):
    if shape == "scalar":
        return {"shape": shape, "value": str(Decimal(text.replace(",", "").replace("−", "-")))}
    if shape == "scientific":
        base, exponent = text.replace("−", "-").split("×10")
        return {"shape": shape, "value": str(Decimal(base + "e" + exponent))}
    return {"shape": shape, "complete_value_required": True}


def pdf(case, page_number, prefix, literal, *, shape="scalar", reason=PROSE):
    page = json.loads((QA / case / "independent-pdf.json").read_text("utf-8"))[page_number - 1]
    text, indices = normalized(page["text"])
    assert text.count(prefix) == 1, (case, page_number, prefix)
    start = text.index(prefix)
    assert literal in prefix, (prefix, literal)
    begin = start + prefix.index(literal)
    first, last = indices[begin], indices[begin + len(literal) - 1] + 1
    chars = [c for c in page["characters"] if first <= c["index"] < last]
    assert "".join(c["text"] for c in chars) == "".join(literal.split())
    box = [
        min(c["bbox"][0] for c in chars),
        min(c["bbox"][1] for c in chars),
        max(c["bbox"][2] for c in chars),
        max(c["bbox"][3] for c in chars),
    ]
    targets.append(
        {
            "case": case,
            "file": "article.pdf",
            "format": "pdf",
            "text": literal,
            "locator": {"page": page_number, "bbox": box},
            "original_character_indices": [c["index"] for c in chars],
            "selection_reason": reason,
            **value_fields(literal, shape),
        }
    )


def main():
    case = "plosgenetics-1011480"
    for prefix, literal in [
        ("data from 2,940 plasma", "2,940"),
        ("identified 2.5 causal", "2.5"),
        ("captured 36% more", "36"),
        ("average 13% and", "13"),
        ("and 40% more heritability", "40"),
    ]:
        pdf(case, 1, prefix, literal, reason=FALLBACK)
    pdf(case, 5, "at least 86%", "86", reason=FALLBACK)
    pdf(case, 5, "dropped below 10%", "10", reason=FALLBACK)
    pdf(case, 5, "range of 0.8–1.2", "0.8–1.2", shape="range", reason=FALLBACK)
    pdf(case, 6, "clearly above 1.2", "1.2", reason=FALLBACK)
    for prefix, literal in [
        ("below 30% for", "30"),
        ("above 84%", "84"),
        ("always above 72%", "72"),
        ("dropped below 60%", "60"),
        ("clearly above 1.2", "1.2"),
    ]:
        pdf(case, 7, prefix, literal, reason=FALLBACK)
    pdf(case, 7, "range of 0.8–1.0", "0.8–1.0", shape="range", reason=FALLBACK)
    pdf(case, 7, "GWAS of 2,490 unique", "2,490", reason=FALLBACK)

    case = "plosmedicine-1004501"
    table = [
        "1,674 (16.2)",
        "1,385 (13.9)",
        "1,131 (12.0)",
        "6,680 (64.7)",
        "6,634 (66.4)",
        "6,198 (65.7)",
        "1,883 (18.2)",
        "1,968 (19.7)",
        "2,099 (22.3)",
        "842 (8.1)",
        "737 (7.4)",
        "526 (5.6)",
    ]
    for literal in table:
        pdf(case, 8, literal, literal, shape="count_percent", reason=TABLE)
    for prefix, literal in [
        ("total of 29,750 women", "29,750"),
        ("22.3% of women", "22.3"),
        ("17.7% were born", "17.7"),
        ("11.3% had a body", "11.3"),
    ]:
        pdf(case, 1, prefix, literal)

    case = "peerj-pmc11740737"
    rows = [
        ("Intercept 0.534 0.185", ["0.534", "0.185"]),
        ("Congruency (I)a −0.005 0.097 −0.051 0.960", ["−0.005", "0.097", "−0.051", "0.960"]),
        ("Playback No. (2)b −0.051 0.098 −0.522 0.602", ["−0.051", "0.098", "−0.522", "0.602"]),
        ("Year (2021)c 0.001 0.107", ["0.001", "0.107"]),
    ]
    for prefix, values in rows:
        for literal in values:
            pdf(case, 12, prefix, literal, reason=TABLE)
    pdf(case, 1, "presented 26 goats", "26")
    pdf(case, 1, "(17 males and", "17")
    pdf(case, 12, "7.198 ± 1.641", "7.198 ± 1.641", shape="estimate_se")
    pdf(case, 12, "t-ratio = 4.385", "4.385")

    case = "scientific-reports-pmc11782514"
    age_row = "Age 55 28 65 43 43 18 20 29"
    # Equal ages are distinct original positions. Extend the prefix and use its
    # final value rather than asking the product to disambiguate the gold.
    for i, literal in enumerate(["55", "28", "65", "43", "43", "18", "20", "29"]):
        suffix = " ".join(age_row.split()[i + 1 :])
        pdf(
            case,
            3,
            suffix,
            literal,
            reason=TABLE + " Eight observed donor ages; medication codes excluded.",
        )
    for prefix, literal in [
        ("derived from 8 donors", "8"),
        ("(P=0.0002)", "0.0002"),
        ("(P=0.003)", "0.003"),
        ("(P=0.13)", "0.13"),
        ("derived from the 8 donors", "8"),
    ]:
        pdf(
            case,
            6,
            prefix,
            literal,
            reason=PROSE + " Continue after the eight eligible table values.",
        )
    pdf(
        case,
        6,
        "analyzed 600–1200 individual",
        "600–1200",
        shape="range",
        reason=PROSE + " Observed colonoid counts; preserve the complete range.",
    )
    pdf(case, 6, "(P=0.0001)", "0.0001")
    pdf(case, 6, "Colonoids from 6 donors", "6")

    for case in ["plosgenetics-1011480", "plosmedicine-1004501"]:
        data = json.loads((QA / case / "independent-docx.json").read_text("utf-8"))
        count = 0
        for row in data["tables"][0]["rows"][2:]:
            for cell in row["cells"]:
                eligible = cell["cell"] in {3, 4} if "genetics" in case else cell["cell"] > 1
                paragraphs = [p for p in cell["paragraphs"] if p["text"].strip()]
                if not eligible or not paragraphs or count >= 16:
                    continue
                text = "\n".join(p["text"] for p in paragraphs).strip()
                shape = (
                    "scientific"
                    if "genetics" in case
                    else "count_total"
                    if "/" in text
                    else "estimate_ci"
                )
                first = paragraphs[0]
                targets.append(
                    {
                        "case": case,
                        "file": "supplement.docx",
                        "format": "docx",
                        "text": text,
                        "locator": {
                            "part": "word/document.xml",
                            "paragraph": first["paragraph"],
                            "offset": len(first["text"]) - len(first["text"].lstrip()),
                            "last_paragraph": paragraphs[-1]["paragraph"],
                        },
                        "source_cell": {
                            "table": 1,
                            "row": row["row"],
                            "physical_cell": cell["cell"],
                        },
                        "selection_reason": TABLE
                        + (
                            " No measured prose; four prose slots continue the table. "
                            "Preserve full cells across paragraphs."
                        ),
                        **value_fields(text, shape),
                    }
                )
                count += 1
        assert count == 16

    counts = Counter((t["case"], t["file"]) for t in targets)
    assert len(targets) == 96 and set(counts.values()) == {16}
    for index, target in enumerate(targets, 1):
        target["id"] = f"dev-{index:03d}"
        source = CORPUS / "papers" / target["case"] / target["file"]
        target["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        if target["format"] == "pdf":
            with pdfium.PdfDocument(str(source)) as document:
                page = document[target["locator"]["page"] - 1]
                tp = page.get_textpage()
                rects = [
                    tp.get_charbox(i, loose=True) for i in target["original_character_indices"]
                ]
                font_boxes[target["id"]] = [
                    min(b[0] for b in rects),
                    page.get_height() - max(b[3] for b in rects),
                    max(b[2] for b in rects),
                    page.get_height() - min(b[1] for b in rects),
                ]
                tp.close()
                page.close()
    gold = {
        "split": "development",
        "planned_slots": 96,
        "targets": targets,
        "shortfalls": [],
        "annotation": (
            "Developer-selected independent original positions, before product scores "
            "or parser edits. Full compound values remain single targets; no "
            "mantissa/bound fragments count as success."
        ),
    }
    with (CORPUS / "development-gold.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(gold, ensure_ascii=False, indent=2) + "\n")
    with (CORPUS / "development-font-boxes.json").open(
        "x", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write(
            json.dumps(
                {
                    "gold_sha256": hashlib.sha256(
                        (CORPUS / "development-gold.json").read_bytes()
                    ).hexdigest(),
                    "method": (
                        "PDFium loose font boxes at independently selected original "
                        "glyph indices; ink boxes retained."
                    ),
                    "boxes": font_boxes,
                },
                indent=2,
            )
            + "\n"
        )
    print(
        json.dumps({"targets": len(targets), "shapes": dict(Counter(t["shape"] for t in targets))})
    )


if __name__ == "__main__":
    main()
