"""Score licensed native documents against independently locked original positions.

The controlled evidence is synthetic. This is not reproduction of any paper's
experiments. A later run on these same documents is a regression, never a new
held-out measurement. See validation/native-v3/README.md.
"""

import argparse
import hashlib
import importlib.metadata
import json
import platform
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from paperdelta import __version__
from paperdelta.analysis import check_project
from paperdelta.config import config_text
from paperdelta.docx_document import DocxDocument
from paperdelta.errors import PaperDeltaError
from paperdelta.models import Config
from paperdelta.pdf_document import PdfDocument
from paperdelta.storage import Project, json_text

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "validation/native-v3"
OUTCOMES = ("supported", "missed", "mislocated", "unknown")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def implementation():
    import paperdelta

    package = Path(paperdelta.__file__).resolve().parent
    paths = [p for p in package.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    paths += [
        ROOT / "tools/evaluate_native_v3.py",
        ROOT / "tools/prepare_native_v3.py",
        ROOT / "tools/prepare_native_v2.py",
        ROOT / "tools/annotate_native_v3_development.py",
        ROOT / "pyproject.toml",
    ]
    return {
        (
            f"src/paperdelta/{p.relative_to(package).as_posix()}"
            if p.is_relative_to(package)
            else p.relative_to(ROOT).as_posix()
        ): digest(p)
        for p in sorted(paths)
    }


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json_text(value))


def same_place(actual, expected):
    if "paragraph" in expected:
        return all(actual.get(key) == expected[key] for key in ("part", "paragraph", "offset"))
    if actual.get("page") != expected["page"]:
        return False
    a, e = [float(v) for v in actual["bbox"]], expected["bbox"]
    # The default comparison uses independent PDFium font boxes; both original
    # ink boxes and the initially recorded ink-mode scores remain available.
    return (
        abs(a[0] - e[0]) <= 1.2
        and abs(a[2] - e[2]) <= 1.2
        and a[1] - 2 <= (e[1] + e[3]) / 2 <= a[3] + 2
    )


def blocked(document, target):
    expected = target["locator"]
    if target["format"] == "docx":
        return any(
            b.locator.get("part") == expected["part"]
            and b.locator.get("paragraph") == expected["paragraph"]
            and not b.supported
            for b in document.blocks
        )
    return (
        expected["page"] in document.unreliable_pages
        or any(
            not b.supported
            and b.locator.get("page") == expected["page"]
            # Product coordinates retain four decimals. Do not call a known
            # quarantined position a miss solely due to last-digit rounding.
            and b.locator["bbox"][0] - Decimal("0.0001")
            <= Decimal(str(expected["bbox"][0]))
            <= b.locator["bbox"][2] + Decimal("0.0001")
            and b.locator["bbox"][1] - 3
            <= Decimal(str(expected["bbox"][1]))
            <= b.locator["bbox"][3]
            for b in document.blocks
        )
        or any(
            i["code"] in {"PDF_NO_TEXT", "PDF_PAGE_GEOMETRY"}
            and f" {expected['page']} " in str(i["message"])
            for i in document.issues
        )
    )


def score_file(output, case, filename, items):
    kind = items[0]["format"]
    source = CORPUS / "papers" / case / filename
    raw = source.read_bytes()
    assert all(t["source_sha256"] == digest(source) for t in items)
    try:
        document = (DocxDocument if kind == "docx" else PdfDocument)(filename, raw)
    except PaperDeltaError as error:
        return [
            {
                "id": t["id"],
                "case": case,
                "format": kind,
                "gold": t["locator"],
                "text": t["text"],
                "outcome": "unknown",
                "reason": error.code,
                "refusal_scope": "entire_document",
            }
            for t in items
        ]
    project = Project(output / case / kind)
    project.write(filename, raw)
    scalar_items = [
        t for t in items if "value" in t and abs(Decimal(t["value"]).as_tuple().exponent) <= 1000
    ]
    data = "id,value\n" + "".join(t["id"] + "," + t["value"] + "\n" for t in scalar_items)
    project.write("results.csv", data.encode())
    config = {
        "schema_version": Config.model_json_schema()["properties"]["schema_version"]["maximum"],
        "paper": {"entry": filename},
        "sources": {
            "synthetic": {
                "path": "results.csv",
                "format": "csv",
                "primary_key": ["id"],
                "columns": {"id": "string", "value": "decimal"},
            }
        },
        "metrics": {},
        "occurrences": {},
    }
    selected, results = [], []
    for target in items:
        result = {
            "id": target["id"],
            "case": case,
            "format": kind,
            "gold": target["locator"],
            "text": target["text"],
        }
        result["shape"] = target["shape"]
        if "value" not in target:
            result.update(
                outcome="unknown",
                reason="complete_compound_contract_unsupported",
                full_target_retained=True,
                fragment_successes_counted=0,
            )
            results.append(result)
            continue
        candidates = [s for s in document.numbers() if same_place(s.locator, target["locator"])]
        if len(candidates) != 1:
            known = blocked(document, target)
            result.update(
                outcome="unknown" if known else "missed",
                reason="blocked_original_location" if known else "no_unique_original_position",
            )
        else:
            span = candidates[0]
            result["actual"] = span.to_dict()
            normalized = span.text.replace(",", "").replace("−", "-")
            normalized = "".join(normalized.split()).translate(
                str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")
            )
            normalized = normalized.replace("×10^", "e").replace("×10", "e")
            if Decimal(normalized) != Decimal(target["value"]):
                result.update(outcome="mislocated", reason="different_token_at_gold_position")
            else:
                try:
                    if abs(Decimal(target["value"]).as_tuple().exponent) > 1000:
                        raise PaperDeltaError(
                            "NUMBER_LIMIT", "Original value exceeds the declared arithmetic bound"
                        )
                    anchor = document.anchor_for_span(span)
                    resolved = document.locate(anchor)
                    if not same_place(resolved.locator, target["locator"]):
                        result.update(outcome="mislocated", reason="anchor_resolved_elsewhere")
                    else:
                        name = target["id"]
                        config["metrics"][name] = {
                            "source": "synthetic",
                            "field": "value",
                            "where": {"id": name},
                            "unit": "scalar",
                        }
                        config["occurrences"][name] = {
                            "metric": name,
                            "file": filename,
                            "anchor": anchor.model_dump(),
                            "display": {
                                "kind": "scientific"
                                if target["shape"] == "scientific"
                                else "decimal",
                                "places": max(
                                    0, len(Decimal(target["value"]).as_tuple().digits) - 1
                                )
                                if target["shape"] == "scientific"
                                else max(0, -Decimal(target["value"]).as_tuple().exponent),
                                "percent_symbol": False,
                            },
                        }
                        result.update(outcome="pending", anchor=anchor.model_dump())
                        selected.append((target, result))
                except PaperDeltaError as error:
                    result.update(outcome="unknown", reason=error.code)
        results.append(result)
    project.write("paperdelta.yaml", config_text(Config.model_validate(config)).encode())
    checked = check_project(project.root)
    increments = {
        t["id"]: Decimal(10) ** max(0, Decimal(t["value"]).adjusted())
        if t["shape"] == "scientific" and Decimal(t["value"])
        else Decimal(1)
        for t in scalar_items
    }
    changed_data = "id,value\n" + "".join(
        t["id"] + "," + str(Decimal(t["value"]) + increments[t["id"]]) + "\n" for t in scalar_items
    )
    project.write("results.csv", changed_data.encode())
    changed = check_project(project.root)
    for target, result in selected:
        name = target["id"]
        before, after = checked["occurrences"][name], changed["occurrences"][name]
        place = all(
            s.get("location") and same_place(s["location"]["locator"], target["locator"])
            for s in (before, after)
        )
        result.update(
            check_status=before["status"],
            changed_evidence_status=after["status"],
            evidence_increment=str(increments[name]),
        )
        if not place:
            result.update(outcome="mislocated", reason="check_location_differs_from_gold")
        elif before["status"] == "pass" and after["status"] == "mismatch":
            result["outcome"] = "supported"
        else:
            result.update(outcome="unknown", reason="controlled_evidence_verdict_unresolved")
    assert project.read(filename) == raw
    save(project.root / "diagnostics.json", document.issues)
    save(project.root / "baseline-report.json", checked)
    save(project.root / "changed-report.json", changed)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument(
        "--split", choices=["development", "held-out", "all"], default="development"
    )
    parser.add_argument("--mode", choices=["regression", "first-held-out"], default="regression")
    parser.add_argument("--out")
    parser.add_argument("--coordinates", choices=["ink", "font"], default="font")
    args = parser.parse_args()
    current = implementation()
    if args.freeze:
        assert not (CORPUS / "held-out-gold.json").exists(), "Freeze before held-out annotation"
        assert (CORPUS / "development-gold-lock.json").exists()
        save(
            CORPUS / "implementation-lock.json",
            {
                "locked_at": datetime.now(UTC).isoformat(),
                "tool_version": __version__,
                "phase": "before held-out native layout/text inspection",
                "protocol_sha256": digest(CORPUS / "protocol-plan.json"),
                "scoring_contract_sha256": digest(CORPUS / "scoring-contract.json"),
                "scoring_amendment_sha256": digest(
                    CORPUS / "scoring-amendment-before-held-out.json"
                ),
                "development_gold_sha256": digest(CORPUS / "development-gold.json"),
                "development_font_boxes_sha256": digest(CORPUS / "development-font-boxes.json"),
                "files": current,
            },
        )
        return 0
    assert args.out
    output = (ROOT / args.out).resolve()
    assert output.is_relative_to(ROOT / "build") and not output.exists()
    output.mkdir(parents=True)
    lock_path = CORPUS / "implementation-lock.json"
    lock = json.loads(lock_path.read_text("utf-8")) if lock_path.exists() else {}
    matches = lock.get("files") == current
    if args.split != "development":
        assert lock, "Freeze implementation before held-out access"
    splits = ["development", "held-out"] if args.split == "all" else [args.split]
    gold = {s: json.loads((CORPUS / (s + "-gold.json")).read_text("utf-8")) for s in splits}
    for split in splits:
        locked = json.loads((CORPUS / (split + "-gold-lock.json")).read_text("utf-8"))
        assert locked["gold_sha256"] == digest(CORPUS / (split + "-gold.json"))
        assert locked["font_boxes_sha256"] == digest(CORPUS / (split + "-font-boxes.json"))
    if args.mode == "first-held-out":
        assert args.split == "held-out" and matches
        annotation = json.loads((CORPUS / "held-out-gold-lock.json").read_text("utf-8"))
        assert annotation["gold_sha256"] == digest(CORPUS / "held-out-gold.json")
        assert annotation["font_boxes_sha256"] == digest(CORPUS / "held-out-font-boxes.json")
        save(
            CORPUS / "first-run-start.json",
            {
                "started_at": datetime.now(UTC).isoformat(),
                "implementation_lock_sha256": digest(CORPUS / "implementation-lock.json"),
                "gold_sha256": annotation["gold_sha256"],
            },
        )
    results = []
    for split, document in gold.items():
        items = document["targets"]
        if args.coordinates == "font":
            font = json.loads((CORPUS / (split + "-font-boxes.json")).read_text("utf-8"))
            assert font["gold_sha256"] == digest(CORPUS / (split + "-gold.json"))
            items = [
                {
                    **t,
                    "locator": {
                        **t["locator"],
                        "ink_bbox": t["locator"]["bbox"],
                        "bbox": font["boxes"][t["id"]],
                    },
                }
                if t["format"] == "pdf"
                else t
                for t in items
            ]
        for case, filename in dict.fromkeys((t["case"], t["file"]) for t in items):
            scores = score_file(
                output,
                case,
                filename,
                [t for t in items if t["case"] == case and t["file"] == filename],
            )
            results.extend({**r, "split": split} for r in scores)
    summary = {
        "mode": args.mode,
        "coordinates": args.coordinates,
        "tool_version": __version__,
        "created_at": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "dependencies": {
            n: importlib.metadata.version(n)
            for n in ("python-docx", "lxml", "pdfplumber", "pdfminer.six")
        },
        "matches_implementation_lock": matches,
        "implementation": current,
        "gold": {s: digest(CORPUS / (s + "-gold.json")) for s in splits},
        "planned_slots": sum(g.get("planned_slots", len(g["targets"])) for g in gold.values()),
        "shortfalls": [item for g in gold.values() for item in g.get("shortfalls", [])],
        "counts": {k: sum(r["outcome"] == k for r in results) for k in OUTCOMES},
        "by_file": [
            {
                "case": c,
                "format": f,
                "counts": dict(
                    Counter(r["outcome"] for r in results if r["case"] == c and r["format"] == f)
                ),
            }
            for c, f in dict.fromkeys((r["case"], r["format"]) for r in results)
        ],
        "results": results,
    }
    save(output / "results.json", summary)
    print(
        json.dumps({"counts": summary["counts"], "targets": len(results), "matches_lock": matches})
    )
    return int(summary["counts"]["mislocated"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
