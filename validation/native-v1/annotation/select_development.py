"""Development gold selected from rendered originals and independent extraction."""
import hashlib
import json
import re
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "native-v1"
NUMBER = re.compile(r"(?<![A-Za-z0-9])[-−]?(?:(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|\.\d+)")
targets = []

def word(case, paragraph, offset, text, explanation):
    targets.append({"case": case, "file": "supplement.docx", "format": "docx", "text": text,
                    "value": str(Decimal(text.replace(",", "").replace("−", "-"))),
                    "locator": {"part": "word/document.xml", "paragraph": paragraph, "offset": offset},
                    "selection_reason": explanation})

def word_table(case, count, *, start_row=2, columns=None):
    data = json.loads((ROOT / "qa" / case / "independent-word.json").read_text("utf-8"))
    selected = 0
    for row in data["tables"][0]["rows"][start_row - 1:]:
        for cell in row["cells"]:
            if columns and cell["cell"] not in columns:
                continue
            for p in cell["paragraphs"]:
                for match in NUMBER.finditer(p["text"]):
                    word(case, p["paragraph"], match.start(), match[0],
                         f"First result table; physical row {row['row']}, cell {cell['cell']}. Dates and row identifiers are not measurement values.")
                    targets[-1]["source_cell"] = {"table": 1, "row": row["row"], "physical_cell": cell["cell"]}
                    selected += 1
                    if selected == count:
                        return
    raise AssertionError("Unrecorded target shortfall")

word_table("climate-repetition", 12, columns=[2, 3, 4, 5, 6])
climate = json.loads((ROOT / "qa/climate-repetition/independent-word.json").read_text("utf-8"))
note = next(p for p in climate["prose"] if p["paragraph"] == 51)
word("climate-repetition", 51, note["text"].index(".03"), ".03", "First numerical result in explanatory note.")
paragraph = next(p for p in climate["prose"] if p["paragraph"] == 224)
start = paragraph["text"].index("F(1, 774)")
for match in list(NUMBER.finditer(paragraph["text"], start))[:3]:
    word("climate-repetition", 224, match.start(), match[0], "Following result prose: F degrees of freedom and statistic; experiment/table labels excluded.")
word_table("science-journalism", 16, start_row=3, columns=[4, 5])
for target in targets:
    if target["case"] == "science-journalism":
        target["selection_reason"] += " Prose has no measured results; four prose slots use the following table values."

def pdf_range(case, page_number, prefix, count, *, skip=0, explanation):
    pages = json.loads((ROOT / "qa" / case / "independent-pdf.json").read_text("utf-8"))
    page = pages[page_number - 1]
    start = page["text"].index(prefix)
    assert page["text"].count(prefix) == 1, prefix
    matches = list(NUMBER.finditer(page["text"], start))[skip:skip + count]
    assert len(matches) == count
    for match in matches:
        chars = [c for c in page["characters"] if match.start() <= c["index"] < match.end()]
        assert "".join(c["text"] for c in chars) == match[0], (prefix, match[0], chars)
        box = [min(c["bbox"][0] for c in chars), min(c["bbox"][1] for c in chars),
               max(c["bbox"][2] for c in chars), max(c["bbox"][3] for c in chars)]
        targets.append({"case": case, "file": "article.pdf", "format": "pdf", "text": match[0],
                        "value": str(Decimal(match[0].replace(",", "").replace("−", "-"))),
                        "locator": {"page": page_number, "bbox": box},
                        "selection_reason": explanation})

pdf_range("climate-repetition", 7, "Intercept 2.88", 12, explanation="First twelve result tokens in Table 1 after the header, row-major; includes CI endpoints and the printed p threshold.")
for prefix in ["alpha = .91", "alpha = .83", ".81 for", "90% of participants"]:
    pdf_range("climate-repetition", 6, prefix, 1, explanation="First numerical measured results in Results prose; experiment IDs excluded.")
pdf_range("science-journalism", 11, "Belgium 55", 1, explanation="Table 5 is the first results table; preceding tables describe methods. Date/month categories excluded.")
pdf_range("science-journalism", 11, "12 3 1,142", 8, explanation="Continue first result row after categorical month values; include range endpoints and page counts.")
pdf_range("science-journalism", 11, "Italy 628", 1, explanation="Next result row in Table 5, before categorical month values.")
pdf_range("science-journalism", 11, "182 7 414", 2, explanation="Next result row after categorical month values, completing twelve table targets.")
pdf_range("science-journalism", 11, "between 55 to 728", 4, explanation="First four measured results in Results prose. Abstract contains dates but no numerical measurement; table labels and dates excluded.")

for index, item in enumerate(targets, 1):
    item["id"] = f"dev-{index:03d}"
    item["source_sha256"] = hashlib.sha256((ROOT / "papers" / item["case"] / item["file"]).read_bytes()).hexdigest()
assert len(targets) == 64
out = ROOT / "development-gold.json"
assert not out.exists(), "Do not overwrite original annotations"
out.write_text(json.dumps({"split": "development", "annotation": "Developer annotations, selected without PaperDelta output and visually checked against native renders.", "targets": targets}, ensure_ascii=False, indent=2) + "\n", "utf-8", newline="\n")
print(json.dumps({"targets": len(targets), "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}))
