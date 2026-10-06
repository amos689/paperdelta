"""Reproduce developer-selected held-out locations from independent originals.

These selectors were chosen from PDFium/OOXML text, then checked on original
renders, after implementation freeze and before held-out scores. They are not inferred
from PaperDelta candidates. See held-out-gold.json for target shortfalls.
"""

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "build/native-v2/held-out"
CORPUS = ROOT / "validation/native-v2"
NUMBER = re.compile(r"(?<![A-Za-z0-9])[-−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
targets = []


def normalized(text):
    output, indices = [], []
    for index, char in enumerate(text):
        char = " " if char.isspace() else char
        if char == " " and output and output[-1] == " ":
            continue
        output.append(char)
        indices.append(index)
    return "".join(output), indices


def pdf(case, number, prefix, expected, reason):
    page = json.loads((QA / case / "independent-pdf.json").read_text("utf-8"))[number - 1]
    text, indices = normalized(page["text"])
    assert text.count(prefix) == 1, (case, number, prefix)
    start = text.index(prefix)
    found = list(NUMBER.finditer(text, start))[: len(expected)]
    assert [m[0] for m in found] == expected, (case, prefix, [m[0] for m in found], expected)
    for match in found:
        first, last = indices[match.start()], indices[match.end() - 1] + 1
        chars = [c for c in page["characters"] if first <= c["index"] < last]
        assert "".join(c["text"] for c in chars) == match[0]
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
                "text": match[0],
                "locator": {"page": number, "bbox": box},
                "selection_reason": reason,
            }
        )


assert (CORPUS / "implementation-lock.json").is_file()
assert not (CORPUS / "first-run-start.json").exists()
TABLE = "First result table after headers; identifiers, dates and method constants excluded."
PROSE = "First measured abstract/results values, excluding IDs and confidence-level constants."
FALLBACK = "No formal result table; measured result prose or explanatory figure-caption prose."

pdf(
    "plos-0294127",
    7,
    "534: 222/312",
    [
        "534",
        "222",
        "312",
        "68",
        "56",
        "74",
        "65",
        "55",
        "72",
        "15",
        "11",
        "19",
    ],
    TABLE,
)
pdf("plos-0294127", 2, "We found 7 observational", ["7"], PROSE)
pdf("plos-0294127", 2, "n = 3,224", ["3,224", "0.96"], PROSE)
pdf("plos-0294127", 2, "0.86 to 1.06", ["0.86"], PROSE)

pdf(
    "plos-0304516",
    6,
    "Age, mean ± SE",
    [
        "47.43",
        "0.28",
        "40.18",
        "0.40",
        "50.62",
        "0.30",
        "0.0001",
        "28.86",
        "0.11",
        "26.94",
        "0.16",
        "29.71",
    ],
    TABLE,
)
pdf("plos-0304516", 1, "included 8,983 participants", ["8,983", "6,317", "70.3", "3.87"], PROSE)

pdf("plos-0312751", 6, "Collagen-based BG 32", ["32", "29", "3", "26", "24", "2"], TABLE)
pdf("plos-0312751", 6, "mixed with i-PRF 18", ["18", "18", "0", "16", "14", "2"], TABLE)
pdf("plos-0312751", 1, "Out of 1,605 records", ["1,605", "16", "690"], PROSE)
pdf("plos-0312751", 1, "RR: 0.50", ["0.50"], PROSE)

COHERENCE = FALLBACK + (
    " Reported observed coherence-interval bounds, not axis ticks, dates, "
    "figure IDs or the preset significance level."
)
pdf("plos-0324599", 10, "essentially in the 1–4", ["1", "4", "4", "16"], COHERENCE)
pdf("plos-0324599", 10, "frequencies (16–64", ["16", "64", "64", "256"], COHERENCE)
pdf("plos-0324599", 11, "within the 16–64", ["16", "64"], COHERENCE)
pdf("plos-0324599", 11, "from scales 16–64", ["16", "64"], COHERENCE)
pdf("plos-0324599", 11, "relationship in the 16–64", ["16", "64"], COHERENCE)
pdf("plos-0324599", 11, "longer scales (256–512", ["256", "512"], COHERENCE)

pdf("elife-110341", 3, "isolated from 14 healthy", ["14"], FALLBACK)
pdf("elife-110341", 4, "Cumulative data from 14", ["14"], FALLBACK)
pdf("elife-110341", 7, "curation, 11 single", ["11"], FALLBACK)
pdf("elife-110341", 7, "accounting for 10 of 11", ["10", "11"], FALLBACK)
pdf("elife-110341", 7, "detected in 6 of 11", ["6", "11"], FALLBACK)
pdf("elife-110341", 7, "detected in 4 of 11", ["4", "11"], FALLBACK)
pdf("elife-110341", 9, "containing 1.14%", ["1.14"], FALLBACK)
pdf("elife-110341", 11, "identified 2117 such", ["2117"], FALLBACK)
pdf("elife-110341", 15, "visualisation of 11,804", ["11,804"], FALLBACK)
pdf("elife-110341", 16, "n=11,804", ["11,804"], FALLBACK)

pdf("elife-110200", 3, "total of 63 Gb", ["63"], FALLBACK)
pdf("elife-110200", 3, "lack 24 genera", ["24"], FALLBACK)
pdf("elife-110200", 5, "encompasses a 115-kb", ["115"], FALLBACK)
pdf("elife-110200", 5, "shares only 82–83%", ["82", "83"], FALLBACK)
pdf("elife-110200", 7, "modest (<10-", ["10"], FALLBACK)
pdf("elife-110200", 7, "representing ~80%", ["80"], FALLBACK)
pdf("elife-110200", 7, "For D and E, n = 6", ["6"], FALLBACK)

# Preserve a scientific value as one original position, including its raised
# exponent. Do not turn its mantissa/base/exponent into separate measurements.
page = json.loads((QA / "elife-110200/independent-pdf.json").read_text("utf-8"))[7]
text, indices = normalized(page["text"])
literal = "3 × 104"
prefix = "is present at ~" + literal
assert text.count(prefix) == 1
start = text.index(prefix) + len("is present at ~")
first, last = indices[start], indices[start + len(literal) - 1] + 1
chars = [c for c in page["characters"] if first <= c["index"] < last]
targets.append(
    {
        "case": "elife-110200",
        "file": "article.pdf",
        "format": "pdf",
        "text": "".join(c["text"] for c in chars),
        "value": "30000",
        "locator": {
            "page": 8,
            "bbox": [
                min(c["bbox"][0] for c in chars),
                min(c["bbox"][1] for c in chars),
                max(c["bbox"][2] for c in chars),
                max(c["bbox"][3] for c in chars),
            ],
        },
        "selection_reason": FALLBACK + " One complete measured scientific-notation value.",
    }
)
pdf("elife-110200", 8, "successfully replaced ~80%", ["80"], FALLBACK)
pdf("elife-110200", 8, "nearly 100-fold", ["100"], FALLBACK)
pdf("elife-110200", 10, "present at 5- to 10-fold", ["5", "10"], FALLBACK)
pdf("elife-110200", 10, "n = 4 mice/sample", ["4"], FALLBACK)
pdf("elife-110200", 10, "n = 8 mice per strain", ["8"], FALLBACK)
pdf("elife-110200", 12, "n = 4", ["4"], FALLBACK)


def word_value(case, table, row, cell, paragraph, expected, reason):
    word = json.loads((QA / case / "independent-word.json").read_text("utf-8"))
    p = next(
        p
        for t in word["tables"]
        if t["table"] == table
        for r in t["rows"]
        if r["row"] == row
        for c in r["cells"]
        if c["cell"] == cell
        for p in c["paragraphs"]
        if p["paragraph"] == paragraph
    )
    match = next(NUMBER.finditer(p["text"]))
    assert match[0] == expected
    targets.append(
        {
            "case": case,
            "file": "supplement.docx",
            "format": "docx",
            "text": match[0],
            "locator": {
                "part": "word/document.xml",
                "paragraph": paragraph,
                "offset": match.start(),
            },
            "source_cell": {"table": table, "row": row, "physical_cell": cell},
            "selection_reason": reason,
        }
    )


values = [
    (7, "7"),
    (8, "29"),
    (10, "7"),
    (11, "37"),
    (13, "10"),
    (14, "51"),
    (16, "79"),
    (17, "219"),
    (19, "5"),
    (20, "39"),
    (22, "60"),
    (23, "275"),
    (25, "7"),
    (26, "14"),
    (28, "6"),
    (29, "19"),
]
for index, (paragraph, value) in enumerate(values):
    word_value(
        "plos-0304516",
        1,
        index // 2 + 3,
        index % 2 + 2,
        paragraph,
        value,
        TABLE + " No prose results; four prose slots continue the result table.",
    )
word_value("plos-0312751", 1, 16, 3, 58, "9", TABLE + " Observed cases stated in exclusion reason.")

for index, item in enumerate(targets, 1):
    item["id"] = f"held-{index:03d}"
    if "value" not in item:
        item["value"] = str(Decimal(item["text"].replace(",", "").replace("−", "-")))
    item["source_sha256"] = hashlib.sha256(
        (CORPUS / "papers" / item["case"] / item["file"]).read_bytes()
    ).hexdigest()
assert len(targets) == 110, len(targets)
draft = {
    "split": "held-out",
    "planned_slots": 160,
    "targets": targets,
    "annotation": (
        "Independent PDFium/OOXML plus original render inspection, after production "
        "freeze and before first score. Developer annotation, not independent humans."
    ),
    "shortfalls": [
        {
            "case": "plos-0294127",
            "file": "supplement.docx",
            "missing": 16,
            "reason": "Excluded-study bibliography and reasons; no measured result values.",
        },
        {
            "case": "plos-0312751",
            "file": "supplement.docx",
            "missing": 15,
            "reason": (
                "Excluded-study bibliography; one observed sample-count value. Dates, study IDs "
                "and protocol follow-up periods excluded."
            ),
        },
        {
            "case": "plos-0324599",
            "file": "supplement.docx",
            "missing": 16,
            "reason": (
                "Data-description dictionary; dates and source metadata are not measured results."
            ),
        },
        {
            "case": "elife-110341",
            "file": "article.pdf",
            "missing": 3,
            "reason": (
                "Thirteen eligible literal measured numbers in result prose/captions; graph ticks, "
                "method thresholds, IDs and results from cited background work excluded."
            ),
        },
    ],
}
with (ROOT / "build/native-v2/held-out-gold-draft.json").open("x", encoding="utf-8") as stream:
    json.dump(draft, stream, ensure_ascii=False, indent=2)
print(json.dumps({"targets": len(targets), "unfilled_slots": 50}))
