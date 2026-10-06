"""Reproduce developer-selected development locations from independent originals.

These selectors were chosen from PDFium/OOXML text, then checked on original
renders, before any PaperDelta v2 scores or parser changes. They are not inferred
from PaperDelta candidates. See development-gold.json for target shortfalls.
"""

import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QA = ROOT / "build/native-v2/development"
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


TABLE = "First result table, original reading order; category IDs and method constants excluded."
PROSE = (
    "First measured abstract/results values; background, dates and reference/figure IDs excluded."
)
FALLBACK = (
    "No measured result table; use first measured "
    "abstract/results/figure-caption prose, including observed sample counts."
)

pdf(
    "plos-0290868",
    7,
    "Pregnant adolescents* 5",
    ["5", "17.4", "3", "18.3", "2", "38", "3", "20.3", "2", "28", "3", "2"],
    TABLE + " Table 3; earlier tables describe the method.",
)
pdf("plos-0290868", 1, "with 39 pregnant", ["39"], PROSE)
pdf("plos-0290868", 7, "including 5 pregnant", ["5", "3"], PROSE)
pdf("plos-0290868", 7, "All 5 of", ["5"], PROSE)

pdf("plos-0303601", 1, "106 relevant studies", ["106", "4,250", "28", "83", "15", "8"], FALLBACK)
pdf("plos-0303601", 6, "total of 11,402 citations", ["11,402", "6,624", "78", "14"], FALLBACK)
pdf("plos-0303601", 6, "and 14 studies were", ["14", "106"], FALLBACK)
pdf("plos-0303601", 6, "Of these 106 studies", ["106", "83", "15", "4,250"], FALLBACK)

pdf("plos-0308906", 5, "301 patients that", ["301"], TABLE)
pdf(
    "plos-0308906",
    5,
    "TSIs in 52",
    ["52", "17.3", "3", "28", "50", "0", "80", "−0.15", "43", "22", "194"],
    TABLE,
)
pdf(
    "plos-0308906",
    5,
    "1073 patients",
    ["1073", "245,158", "56.0"],
    TABLE
    + (
        " Prose has no decimal-digit result values; four prose slots use subsequent"
        " table values. The confidence level is a method constant, excluded."
    ),
)
pdf(
    "plos-0308906",
    5,
    "51.0%–61.0%",
    ["51.0"],
    TABLE + " Fourth fallback slot: measured confidence bound.",
)

pdf(
    "plos-0317954",
    6,
    "Age (year) 33.448",
    [
        "33.448",
        "3.081",
        "32.222",
        "3.108",
        "0.026",
        "33",
        "25.4",
        "25",
        "19.2",
        "58",
        "44.6",
        "0.357",
    ],
    TABLE,
)
pdf("plos-0317954", 2, "sample of 130 ICU", ["130"], PROSE)
pdf("plos-0317954", 6, "consisted of 130 valid", ["130"], PROSE)
pdf("plos-0317954", 6, "n1=67", ["67"], PROSE + " The n1 label is an identity, not a result.")
pdf("plos-0317954", 6, "n2=63", ["63"], PROSE + " The n2 label is an identity, not a result.")

pdf("elife-110428", 2, "183 µm±23 µm", ["183", "23", "0.05"], FALLBACK)
pdf("elife-110428", 3, "75.0% of the wells", ["75.0", "19"], FALLBACK)
pdf("elife-110428", 3, "N=16 wells", ["16", "304"], FALLBACK)
pdf("elife-110428", 4, "7.4±0.4 mM", ["7.4", "0.4", "7.9", "0.4"], FALLBACK)
pdf("elife-110428", 4, "2.9±0.1 μM", ["2.9", "0.1", "1.9", "1.71"], FALLBACK)
pdf("elife-110428", 4, "N=48 wells", ["48"], FALLBACK)

pdf("elife-109903", 3, "comprising 300 genes", ["300"], FALLBACK)
pdf("elife-109903", 3, "n=6 biological", ["6"], FALLBACK)
pdf("elife-109903", 3, "n=7 male control", ["7", "6", "6", "6"], FALLBACK)
pdf("elife-109903", 3, "n=8 control", ["8"], FALLBACK)
pdf("elife-109903", 4, "Only 221 genes", ["221", "3030"], FALLBACK)
pdf("elife-109903", 4, "n=12 Tacr2", ["12"], FALLBACK)
pdf("elife-109903", 4, "n=11 control", ["11", "13"], FALLBACK)
pdf("elife-109903", 4, "n=7 control (LFD)", ["7", "7", "7", "8"], FALLBACK)

word = json.loads((QA / "plos-0303601/independent-word.json").read_text("utf-8"))
selected = 0
for row in word["tables"][0]["rows"][2:]:
    for cell in row["cells"]:
        if cell["cell"] not in {3, 7}:
            continue
        for p in cell["paragraphs"]:
            for match in NUMBER.finditer(p["text"]):
                if selected >= 16:
                    break
                targets.append(
                    {
                        "case": "plos-0303601",
                        "file": "supplement.docx",
                        "format": "docx",
                        "text": match[0],
                        "locator": {
                            "part": "word/document.xml",
                            "paragraph": p["paragraph"],
                            "offset": match.start(),
                        },
                        "source_cell": {
                            "table": 1,
                            "row": row["row"],
                            "physical_cell": cell["cell"],
                        },
                        "selection_reason": TABLE
                        + (
                            " Sample size and observed MMAT appraisal scores. No result prose; "
                            "remaining four slots continue the table."
                        ),
                    }
                )
                selected += 1
assert selected == 16

for index, item in enumerate(targets, 1):
    item["id"] = f"dev-{index:03d}"
    item["value"] = str(Decimal(item["text"].replace(",", "").replace("−", "-")))
    item["source_sha256"] = hashlib.sha256(
        (CORPUS / "papers" / item["case"] / item["file"]).read_bytes()
    ).hexdigest()
assert len(targets) == 112
draft = {
    "split": "development",
    "planned_slots": 160,
    "targets": targets,
    "annotation": (
        "Developer selected using independent OOXML and PDFium geometry. Visual "
        "verification is recorded separately before gold lock. No PaperDelta "
        "candidates/scores used."
    ),
    "shortfalls": [
        {
            "case": "plos-0290868",
            "file": "supplement.docx",
            "missing": 16,
            "reason": "Qualitative key informant interview guide; no measured numerical results.",
        },
        {
            "case": "plos-0308906",
            "file": "supplement.docx",
            "missing": 16,
            "reason": "Search terms; no measured numerical results.",
        },
        {
            "case": "plos-0317954",
            "file": "supplement.docx",
            "missing": 16,
            "reason": (
                "Survey instrument; scale constants and question/reference IDs are not "
                "measured results."
            ),
        },
    ],
}
path = ROOT / "build/native-v2/development-gold-draft.json"
with path.open("x", encoding="utf-8", newline="\n") as stream:
    stream.write(json.dumps(draft, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"targets": len(targets), "shortfall": 48}))
