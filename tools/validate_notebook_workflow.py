"""Execute an authored Notebook and actual Quarto PDF render, then detect stale outputs."""

import argparse
import importlib.metadata
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from workflow_fixture import create_fixture

from paperdelta.analysis import check_project
from paperdelta.config import config_text, load_config
from paperdelta.fragments import accept_fragment, preview_fragment
from paperdelta.i18n import language_context
from paperdelta.models import Figure
from paperdelta.notebooks import inspect_notebook
from paperdelta.producer_run import observe_producer_command
from paperdelta.provenance import accept_producer, propose_producer
from paperdelta.records import FigureRecord, validate_record
from paperdelta.reports import write_reports
from paperdelta.revisions import revision_list
from paperdelta.snapshots import create_snapshot, read_snapshot
from paperdelta.storage import json_text, parse_json, sha256

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--quarto", required=True)
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    assert output.is_relative_to(ROOT / "build") and not output.exists()
    output.mkdir(parents=True)
    store = create_fixture(output / "paper")
    quarto = shutil.which(args.quarto) or str(Path(args.quarto).resolve())
    version = subprocess.check_output([quarto, "--version"], text=True, timeout=30).strip()
    specification = {
        "kind": "notebook",
        "source": "analysis.ipynb",
        "inputs": ["observations.csv", "run_notebook.py"],
        "outputs": ["results/metrics.csv"],
        "cells": ["metrics"],
    }
    first = observe_producer_command(
        store,
        specification,
        [sys.executable, "run_notebook.py"],
        "Execute the authored Notebook with a real Jupyter kernel.",
    )
    accept_producer(store, propose_producer(store, "training", first["record"]))
    assert inspect_notebook(store, "analysis.ipynb")["cells"][0]["status"] == "saved_outputs"
    figure = {
        "schema_version": 1,
        "path": "results/figure.svg",
        "output_hash": sha256(store.read("results/figure.svg")),
        "inputs": {"results/metrics.csv": sha256(store.read("results/metrics.csv"))},
        "script": {"path": "analysis.ipynb", "hash": sha256(store.read("analysis.ipynb"))},
        "recorded_at": datetime.now(UTC).isoformat(),
        "method": "manual",
    }
    validate_record(FigureRecord, figure, "FIGURE_RECORD")
    store.write("figure-record.json", json_text(figure).encode())
    config, _ = load_config(store)
    config.figures["accuracy_plot"] = Figure(path="results/figure.svg", record="figure-record.json")
    store.write("paperdelta.yaml", config_text(config).encode())
    fragments = {
        "format": "markdown",
        "path": "generated/results.md",
        "occurrences": ["table_accuracy", "table_baseline"],
    }
    accept_fragment(store, preview_fragment(store, "table", fragments))
    render = {
        "kind": "quarto",
        "source": "paper.qmd",
        "inputs": ["results/metrics.csv", "results/figure.svg"],
        "outputs": ["paper.pdf"],
    }
    rendered = observe_producer_command(
        store,
        render,
        [quarto, "render", "paper.qmd", "--to", "typst", "--no-execute"],
        "Observe actual Quarto/Typst PDF rendering without executing QMD code.",
    )
    accept_producer(store, propose_producer(store, "paper_export", rendered["record"]))
    baseline = check_project(store.root)
    assert baseline["exit_code"] == 2
    assert {item["rule"] for item in baseline["diagnostics"]} == {"MARKDOWN_IMAGE"}
    create_snapshot(store, "workflow-before", baseline)
    original_pdf = store.read("paper.pdf")
    original_figure = store.read("results/figure.svg")
    assert original_pdf.startswith(b"%PDF-") and b"84.1%" in original_figure
    phases = []

    def capture(name):
        counter = store.read(".paperdelta/example-executions.log")
        notebook = store.read("analysis.ipynb")
        report = check_project(store.root, baseline=read_snapshot(store, "workflow-before"))
        assert store.read(".paperdelta/example-executions.log") == counter
        assert store.read("analysis.ipynb") == notebook
        for language in ("en", "zh-CN"):
            with language_context(language):
                write_reports(store, "reports/" + name + "/" + language, report)
        phases.append(
            {
                "phase": name,
                "exit_code": report["exit_code"],
                "coverage": report["coverage"],
                "provenance": report.get("provenance", {}),
                "fragments": report.get("fragments", {}),
                "revisions": revision_list(report),
                "input_hashes": report["input_hashes"],
                "check_executed_code": False,
            }
        )
        return report

    capture("baseline")
    changed = store.read("observations.csv")
    for before, after in [(b"0.839", b"0.807"), (b"0.841", b"0.809"), (b"0.843", b"0.811")]:
        changed = changed.replace(before, after)
    store.write("observations.csv", changed)
    report = capture("input_changed")
    assert report["provenance"]["training"]["status"] == "mismatch"
    rerun = observe_producer_command(
        store,
        specification,
        [sys.executable, "run_notebook.py", "--only", "metrics"],
        "Execute only the metrics cell; intentionally leave the old figure and export.",
    )
    accept_producer(store, propose_producer(store, "training", rerun["record"], replace=True))
    store.write(
        "paper.qmd", store.read("paper.qmd").replace(b"| Ours | 84.1 |", b"| Ours | 80.9 |")
    )
    accept_fragment(store, preview_fragment(store, "table", fragments, replace=True))
    report = capture("table_refreshed_old_figure_and_pdf")
    assert report["metrics"]["accuracy"]["value"] == "0.809"
    assert report["occurrences"]["table_accuracy"]["status"] == "pass"
    assert report["occurrences"]["abstract_accuracy"]["status"] == "mismatch"
    assert report["claims"]["main_comparison"]["status"] == "mismatch"
    assert report["figures"]["accuracy_plot"]["status"] == "mismatch"
    assert report["provenance"]["training"]["status"] == "pass"
    assert report["provenance"]["paper_export"]["status"] == "mismatch"
    assert report["fragments"]["table"]["status"] == "pass"
    assert (
        store.read("paper.pdf") == original_pdf
        and store.read("results/figure.svg") == original_figure
    )
    revisions = {item["subject"]: item for item in revision_list(report)}
    assert revisions["occurrence:table_accuracy"]["action"] == "review_refreshed"
    assert revisions["figure:accuracy_plot"]["kind"] == "figure"
    assert revisions["provenance:paper_export"]["kind"] == "export"
    notebook = parse_json(store.text("analysis.ipynb")[0])
    source = notebook["cells"][0]["source"]
    notebook["cells"][0]["source"] = (
        "".join(source) if isinstance(source, list) else source
    ) + "\n# Deliberate source change without a rerun.\n"
    store.write("analysis.ipynb", json_text(notebook).encode())
    report = capture("code_changed_saved_outputs_unchanged")
    cell = report["provenance"]["training"]["cells"][0]
    assert cell["code_changed"] and not cell["outputs_changed"]
    evidence = {
        "status": "passed",
        "scope": (
            "Authored real Jupyter execution and Quarto/Typst rendering; "
            "not an independent reproducibility or scientific-validity study. "
            "Embedded image content remains explicitly unverified."
        ),
        "host": {"system": platform.system(), "python": platform.python_version()},
        "tools": {
            "quarto": version,
            **{
                name: importlib.metadata.version(name)
                for name in ("paperdelta", "nbclient", "nbformat", "ipykernel")
            },
        },
        "commands": [
            first["record"]["observation"],
            rendered["record"]["observation"],
            rerun["record"]["observation"],
        ],
        "execution_log": store.text(".paperdelta/example-executions.log")[0],
        "phases": phases,
    }
    (output / "evidence.json").write_text(json_text(evidence), encoding="utf-8", newline="\n")
    print(json_text({"status": "passed", "phases": len(phases), "quarto": version}))


if __name__ == "__main__":
    main()
