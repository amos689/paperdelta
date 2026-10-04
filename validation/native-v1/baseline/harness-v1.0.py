"""Score explicit native positions and bindings against independent gold."""
import argparse
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

from paperdelta.analysis import check_project
from paperdelta.config import config_text
from paperdelta.docx_document import DocxDocument
from paperdelta.errors import PaperDeltaError
from paperdelta.models import Config
from paperdelta.pdf_document import PdfDocument
from paperdelta.storage import Project

parser = argparse.ArgumentParser()
parser.add_argument("--out", required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parent / "native-v1"
output = Path(args.out).resolve()
assert output.is_relative_to(root.parent) and not output.exists()
output.mkdir(parents=True)
gold_path = root / "development-gold.json"
gold = json.loads(gold_path.read_text("utf-8"))
results = []

def same_place(actual, expected):
    if "paragraph" in expected:
        return all(actual.get(key) == expected[key] for key in ("part", "paragraph", "offset"))
    if actual.get("page") != expected["page"]:
        return False
    # PDFium tight ink boxes lie within pdfminer font boxes. Horizontal endpoints
    # and the centre are checked independently of numeric equality.
    a, e = [float(v) for v in actual["bbox"]], expected["bbox"]
    return (abs(a[0] - e[0]) <= 1.2 and abs(a[2] - e[2]) <= 1.2
            and a[1] - 2 <= (e[1] + e[3]) / 2 <= a[3] + 2)

for case in dict.fromkeys(t["case"] for t in gold["targets"]):
    for filename, kind in [("supplement.docx", "docx"), ("article.pdf", "pdf")]:
        items = [t for t in gold["targets"] if t["case"] == case and t["file"] == filename]
        source = root / "papers" / case / filename
        raw = source.read_bytes()
        assert all(t["source_sha256"] == hashlib.sha256(raw).hexdigest() for t in items)
        document = (DocxDocument if kind == "docx" else PdfDocument)(filename, raw)
        project = Project(output / case / kind)
        project.write(filename, raw)
        project.write("results.csv", ("id,value\n" + "".join(t["id"] + "," + t["value"] + "\n" for t in items)).encode())
        config = {"schema_version": 4, "paper": {"entry": filename},
                  "sources": {"synthetic": {"path": "results.csv", "format": "csv", "primary_key": ["id"], "columns": {"id": "string", "value": "decimal"}}},
                  "metrics": {}, "occurrences": {}}
        selected = []
        for target in items:
            result = {"id": target["id"], "case": case, "format": kind, "gold": target["locator"], "text": target["text"]}
            candidates = [span for span in document.numbers() if same_place(span.locator, target["locator"])]
            if len(candidates) != 1:
                if kind == "docx":
                    blocked = any(b.locator.get("paragraph") == target["locator"]["paragraph"] and not b.supported for b in document.blocks)
                else:
                    blocked = target["locator"]["page"] in document.unreliable_pages or any(
                        not b.supported and b.locator.get("page") == target["locator"]["page"]
                        and b.locator["bbox"][0] <= Decimal(str(target["locator"]["bbox"][0])) <= b.locator["bbox"][2]
                        and b.locator["bbox"][1] - 3 <= Decimal(str(target["locator"]["bbox"][1])) <= b.locator["bbox"][3]
                        for b in document.blocks)
                result.update(outcome="unknown" if blocked else "missed", reason="blocked_original_location" if blocked else "no_unique_original_position")
            else:
                span = candidates[0]
                result["actual"] = span.to_dict()
                if Decimal(span.text.replace(",", "").replace("−", "-")) != Decimal(target["value"]):
                    result.update(outcome="mislocated", reason="different_numeric_token_at_gold_position")
                else:
                    try:
                        anchor = document.anchor_for_span(span)
                        resolved = document.locate(anchor)
                        if not same_place(resolved.locator, target["locator"]):
                            result.update(outcome="mislocated", reason="anchor_resolved_elsewhere")
                        else:
                            name = target["id"]
                            config["metrics"][name] = {"source": "synthetic", "field": "value", "where": {"id": name}, "unit": "scalar"}
                            config["occurrences"][name] = {"metric": name, "file": filename, "anchor": anchor.model_dump(),
                                                            "display": {"kind": "decimal", "places": max(0, -Decimal(target["value"]).as_tuple().exponent), "percent_symbol": False}}
                            result.update(outcome="pending", anchor=anchor.model_dump())
                            selected.append((target, result))
                    except PaperDeltaError as error:
                        result.update(outcome="unknown", reason=error.code)
            results.append(result)
        project.write("paperdelta.yaml", config_text(Config.model_validate(config)).encode())
        checked = check_project(project.root)
        for target, result in selected:
            state = checked["occurrences"][target["id"]]
            correct = state["status"] == "pass" and same_place(state["location"]["locator"], target["locator"])
            result.update(outcome="supported" if correct else "mislocated", check_status=state["status"])
        (output / case / kind / "diagnostics.json").write_text(json.dumps(document.issues, ensure_ascii=False, indent=2), "utf-8")
summary = {"gold_sha256": hashlib.sha256(gold_path.read_bytes()).hexdigest(), "counts": dict(Counter(r["outcome"] for r in results)), "results": results}
(output / "results.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str) + "\n", "utf-8", newline="\n")
print(json.dumps({"counts": summary["counts"], "targets": len(results)}))
