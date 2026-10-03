"""Evaluate frozen real-paper text against explicitly synthetic fault injections.

Author sources are never edited. Every case gets its own retained scratch copy.
Use the development split first. Freeze the protocol before opening the held-out
evaluation; later changes require a new evaluation version, not a silent refreeze.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import platform
import shutil
import sys
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter

import paperdelta
from paperdelta import __version__
from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.patches import apply_patch, create_patch, recover_transaction
from paperdelta.snapshots import create_snapshot, read_snapshot
from paperdelta.storage import Project, json_text, sha256

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests/corpus"
DATA = "_paperdelta_fixture/results.csv"


def protocol_identity():
    files = [
        CORPUS / "active-study.json",
        CORPUS / "manifest.json",
        CORPUS / "annotations.json",
        CORPUS / "scenarios.json",
        Path(__file__),
        *sorted((ROOT / "src/paperdelta").glob("*.py")),
    ]
    return {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()) for path in files}


def verify_implementation():
    """Record checkout hashes only when they match the imported implementation."""
    installed = Path(paperdelta.__file__).resolve().parent
    for path in (ROOT / "src/paperdelta").glob("*.py"):
        if path.read_bytes() != (installed / path.name).read_bytes():
            raise ValueError(f"Imported package differs from the checkout: {path.name}")


def verify_sources(manifest, annotations):
    """Only byte identities and literal contexts, never parser/model predictions."""
    by_id = {item["paper"]: item for item in annotations}
    for paper in manifest["papers"]:
        root = CORPUS / "papers" / paper["id"] / "source"
        for item in paper["files"]:
            raw = (root / item["path"]).read_bytes()
            if sha256(raw) != "sha256:" + item["sha256"] or len(raw) != item["bytes"]:
                raise ValueError(f"Frozen source identity changed: {paper['id']}/{item['path']}")
        binding = by_id[paper["id"]]
        raw = (root / binding["file"]).read_bytes()
        context = binding["prefix"] + binding["value"] + binding["suffix"]
        if raw.decode("utf-8").count(context) != 1:
            raise ValueError(f"Annotation context must be unique: {paper['id']}")


def configuration(paper, binding):
    return {
        "schema_version": 1,
        "paper": {"entry": paper["entry"]},
        "sources": {
            "controlled": {
                "path": DATA,
                "format": "csv",
                "primary_key": ["dataset", "model", "split", "seed"],
                "columns": {
                    "dataset": "string",
                    "model": "string",
                    "split": "string",
                    "seed": "integer",
                    "value": "decimal",
                },
            }
        },
        "metrics": {
            "reported": {
                "source": "controlled",
                "field": "value",
                "where": {"dataset": paper["id"], "model": "target", "split": "test"},
                "reduce": "mean",
                "expected_seeds": [1, 2, 3],
                "unit": "scalar",
            }
        },
        "occurrences": {
            "reported": {
                "file": binding["file"],
                "anchor": {"prefix": binding["prefix"], "suffix": binding["suffix"]},
                "metric": "reported",
                "display": {"kind": "decimal", "places": len(binding["value"].split(".")[1])},
            }
        },
    }


def write_rows(project, rows, omit_column=False):
    buffer = io.StringIO(newline="")
    columns = ["dataset", "model", "split", "seed", "value"]
    if omit_column:
        columns.remove("value")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    project.write(DATA, buffer.getvalue().encode("utf-8"))


def source_rows(paper, value, quantum):
    rows = []
    for model, split in [("target", "test"), ("target", "train"), ("decoy", "test")]:
        for seed in [1, 2, 3]:
            rows.append(
                {
                    "dataset": paper["id"],
                    "model": model,
                    "split": split,
                    "seed": seed,
                    "value": str(value + (seed - 2) * quantum),
                }
            )
    return rows


def run_case(output, paper, binding, scenario):
    case_id = scenario["id"]
    root = output / "cases" / paper["id"] / case_id
    shutil.copytree(CORPUS / "papers" / paper["id"] / "source", root)
    project = Project(root)
    project.write(
        "_paperdelta_fixture/NOTICE.md",
        (
            "# Disposable evaluation copy\n\n"
            f"Original paper: {paper['repository']} at {paper['revision']}.\n"
            f"Paper license: {paper['license']}; "
            "original notices and author lists are retained.\n\n"
            f"This copy is modified for PaperDelta's '{case_id}' test. Its CSV is synthetic "
            "and its numerical/text changes are fault injections, not corrected research "
            "results or a reproduction of the original experiment. The original paper "
            "license continues to apply to derived paper text. There is no author endorsement.\n"
        ).encode(),
    )
    project.write(
        "_paperdelta_fixture/annotation.json",
        json_text({"binding": binding, "scenario": scenario}).encode("utf-8"),
    )
    project.write("paperdelta.yaml", json_text(configuration(paper, binding)).encode("utf-8"))
    value = Decimal(binding["value"])
    quantum = Decimal(1).scaleb(value.as_tuple().exponent)
    rows = source_rows(paper, value, quantum)
    write_rows(project, rows)
    original_tex = {
        path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*.tex")
    }
    baseline = None
    if case_id == "low_bit_change":
        create_snapshot(project, "before", check_project(root))
        baseline = read_snapshot(project, "before")
    delta = quantum / 100 if case_id == "low_bit_change" else quantum * 7
    for row in rows:
        selected = row["model"] == "target" and row["split"] == "test"
        if (
            (
                selected
                and case_id in {"changed_test", "low_bit_change", "patch_roundtrip", "stale_patch"}
            )
            or (row["model"] == "decoy" and case_id == "unrelated_model")
            or (row["split"] == "train" and case_id == "changed_train")
        ):
            row["value"] = str(Decimal(row["value"]) + delta)
    if case_id == "missing_seed":
        rows = rows[1:]
    elif case_id == "duplicate_key":
        rows.append(dict(rows[0]))
    elif case_id == "nonfinite":
        rows[0]["value"] = "NaN"
    elif case_id == "empty_selection":
        rows = [row for row in rows if row["model"] != "target" or row["split"] != "test"]
    write_rows(project, rows, omit_column=case_id == "missing_column")
    full = binding["prefix"] + binding["value"] + binding["suffix"]
    modified = None
    if case_id == "anchor_missing":
        modified = (
            binding["prefix"].replace(" ", " [context rewritten] ", 1)
            + binding["value"]
            + binding["suffix"]
        )
    elif case_id == "ambiguous_anchor":
        # Duplicate the context in a comment, preserving the source's math delimiters.
        # Ambiguity intentionally includes commented-out alternatives.
        modified = full + "\n% Repeated original context: " + full + "\n"
    elif case_id == "unsupported_macro":
        modified = (
            binding["prefix"] + r"\paperdeltaUnknown{" + binding["value"] + "}" + binding["suffix"]
        )
    if modified:
        raw = project.read(binding["file"])
        project.write(binding["file"], raw.replace(full.encode(), modified.encode(), 1))
    report = check_project(root, baseline=baseline)
    state = report["occurrences"].get("reported", {"status": "unknown"})
    result = {
        "paper": paper["id"],
        "split": paper["split"],
        "case": case_id,
        "expected": scenario["expected"],
        "actual": state["status"],
        "error": state.get("error"),
        "project_exit_code": report["exit_code"],
        "project_rules": sorted({item["rule"] for item in report["diagnostics"]}),
        "matched": state["status"] == scenario["expected"],
    }
    if "error" in scenario:
        result["matched"] &= state.get("error") == scenario["error"]
    coverage = report["coverage"]
    result["coverage"] = {
        key: len(value) if isinstance(value, list) else value for key, value in coverage.items()
    }
    if case_id == "low_bit_change":
        result["changed_evidence"] = (
            report["metrics"].get("reported", {}).get("change") == "changed"
        )
        result["matched"] &= result["changed_evidence"]
    if case_id in {"patch_roundtrip", "stale_patch"}:
        try:
            patch = create_patch(project, report, ["reported"])
            if case_id == "stale_patch":
                rows[-1]["value"] = str(value + 1)
                write_rows(project, rows)
                try:
                    apply_patch(project, patch)
                except PaperDeltaError as exc:
                    result["patch_rejected"] = exc.code
                else:
                    result["patch_rejected"] = False
                result["matched"] &= result["patch_rejected"] == "STALE_PATCH"
            else:
                # Independent byte oracle: the one manually annotated context.
                replacement = format(value + delta, f".{len(binding['value'].split('.')[1])}f")
                expected = dict(original_tex)
                expected[binding["file"]] = original_tex[binding["file"]].replace(
                    full.encode(), (binding["prefix"] + replacement + binding["suffix"]).encode(), 1
                )
                applied = apply_patch(project, patch)
                result["outside_bytes_preserved"] = all(
                    project.read(p) == raw for p, raw in expected.items()
                )
                result["rechecked"] = (
                    applied["report"]["occurrences"]["reported"]["status"] == "pass"
                )
                recover_transaction(project, applied["transaction_id"], write=True)
                result["matched"] &= result["outside_bytes_preserved"] and result["rechecked"]
            result["original_tex_restored"] = all(
                project.read(p) == raw for p, raw in original_tex.items()
            )
            result["matched"] &= result["original_tex_restored"]
        except PaperDeltaError as exc:
            result["patch_error"] = exc.code
            result["matched"] = False
    project.write("_paperdelta_fixture/report.json", json_text(report).encode("utf-8"))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split", choices=["development", "held-out", "all"], default="development"
    )
    parser.add_argument("--out", required=True, help="New checkout-relative output directory")
    parser.add_argument("--freeze", action="store_true", help="Write a new protocol lock and exit")
    args = parser.parse_args()
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    annotations = json.loads((CORPUS / "annotations.json").read_text(encoding="utf-8"))["bindings"]
    scenarios = json.loads((CORPUS / "scenarios.json").read_text(encoding="utf-8"))["cases"]
    verify_sources(manifest, annotations)
    verify_implementation()
    study = json.loads((CORPUS / "active-study.json").read_text(encoding="utf-8"))
    if study["kind"] != "regression":
        raise ValueError("This previously observed corpus is now a regression study")
    protocol = protocol_identity()
    lock_path = Project(ROOT).path(study["protocol_lock"])
    if args.freeze:
        with lock_path.open("x", encoding="utf-8") as stream:
            stream.write(
                json_text(
                    {
                        "locked_at": datetime.now(UTC).isoformat(),
                        "study": study,
                        "identities": protocol,
                    }
                )
            )
        print(f"Frozen {study['study_id']} regression protocol; earlier records retained.")
        return 0
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock["identities"] != protocol or lock["study"] != study:
        raise ValueError(
            "Protocol differs from this regression lock; "
            "retain prior results and version a new study"
        )
    output = Project(ROOT).path(args.out)
    output.mkdir(parents=True, exist_ok=False)
    selected = [p for p in manifest["papers"] if args.split == "all" or p["split"] == args.split]
    started = perf_counter()
    outcomes = []
    for paper in selected:
        binding = next(item for item in annotations if item["paper"] == paper["id"])
        for scenario in scenarios:
            try:
                result = run_case(output, paper, binding, scenario)
            except Exception as exc:
                result = {
                    "paper": paper["id"],
                    "split": paper["split"],
                    "case": scenario["id"],
                    "expected": scenario["expected"],
                    "actual": "crash",
                    "matched": False,
                    "exception": f"{type(exc).__name__}: {exc}",
                }
            outcomes.append(result)
        print(
            paper["id"],
            sum(r["matched"] for r in outcomes if r["paper"] == paper["id"]),
            "/",
            len(scenarios),
            flush=True,
        )
    summary = {
        "checked_at": datetime.now(UTC).isoformat(),
        "tool_version": __version__,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "study": study,
        "split": args.split,
        "papers": len(selected),
        "annotated_literals": len(selected),
        "cases": len(outcomes),
        "matched": sum(r["matched"] for r in outcomes),
        "actual_states": dict(Counter(r["actual"] for r in outcomes)),
        "seconds": round(perf_counter() - started, 3),
        "protocol": protocol,
        "scope": (
            "Controlled synthetic fault injection in real licensed source text; correlated "
            "cases around one literal per paper. No whole-paper accuracy, AI mapping accuracy, "
            "user study, or experiment reproduction claim."
        ),
        "outcomes": outcomes,
    }
    (output / "evidence.json").write_text(json_text(summary), encoding="utf-8")
    print(
        json_text(
            {key: value for key, value in summary.items() if key not in {"outcomes", "protocol"}}
        )
    )
    return 0 if summary["matched"] == len(outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
