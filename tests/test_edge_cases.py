import json

import pytest

from paperdelta.analysis import check_project
from paperdelta.storage import Project, sha256


def test_derived_values_and_claims_are_in_source_metric_impact_group(project):
    report = check_project(project)
    group = next(group for group in report["impact_groups"] if group["metric"] == "ours")
    assert set(group["metrics"]) == {"ours", "gain"}
    assert set(group["occurrences"]) == {
        "abstract_accuracy",
        "table_accuracy",
        "appendix_accuracy",
        "gain_text",
    }
    assert group["claims"] == ["main_comparison"]
    assert group["sources"] == ["results/metrics.csv"]


def test_unregistered_figure_is_visible_and_blocks_complete_coverage(project):
    store = Project(project)
    file = "paper/abstract.tex"
    store.write(file, store.read(file) + b"\n\\includegraphics{missing-plot}\n")
    report = check_project(project)
    assert report["exit_code"] == 0
    assert report["coverage"]["unregistered_figures"][0]["reason"] == "missing or ambiguous"
    config = "paperdelta.yaml"
    store.write(config, store.read(config) + b"\nrequire_complete_coverage: true\n")
    strict = check_project(project)
    assert strict["exit_code"] == 2
    assert any(item["rule"] == "INCOMPLETE_COVERAGE" for item in strict["diagnostics"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("script", {"path": [], "hash": "bad"}),
        ("inputs", {"data.csv": []}),
        ("method", "automatically-certified"),
        ("schema_version", True),
        ("recorded_at", "not a date"),
        ("output_hash", []),
    ],
)
def test_malformed_figure_records_produce_unknown_instead_of_crashing(project, field, value):
    store = Project(project)
    store.write("figure.svg", b"<svg/>")
    store.write("plot.py", b"# Never executed.\n")
    record = {
        "schema_version": 1,
        "path": "figure.svg",
        "output_hash": sha256(b"<svg/>"),
        "inputs": {"results/metrics.csv": sha256(store.read("results/metrics.csv"))},
        "script": {"path": "plot.py", "hash": sha256(store.read("plot.py"))},
        "recorded_at": "2026-10-03T00:00:00Z",
        "method": "manual",
    }
    record[field] = value
    store.write("figure.record.json", json.dumps(record).encode())
    store.write(
        "paperdelta.yaml",
        store.read("paperdelta.yaml")
        + b"\nfigures:\n  example: {path: figure.svg, record: figure.record.json}\n",
    )
    report = check_project(project)
    assert report["exit_code"] == 2
    assert report["figures"]["example"]["error"] == "FIGURE_RECORD"


def test_csv_huge_header_is_a_diagnostic(project):
    store = Project(project)
    store.write("results/metrics.csv", b"x" * 140000 + b"\n")
    report = check_project(project)
    assert report["exit_code"] == 2
    assert report["metrics"]["ours"]["error"] == "INVALID_CSV"


def test_integer_literal_limit_is_reported(project):
    store = Project(project)
    data = store.read("results/metrics.csv").replace(b"test,1,", b"test," + b"9" * 5000 + b",")
    store.write("results/metrics.csv", data)
    report = check_project(project)
    assert report["exit_code"] == 2
    assert report["metrics"]["ours"]["error"] == "NUMBER_LIMIT"


def test_numeric_metric_cannot_silently_reinterpret_string_column(project):
    store = Project(project)
    store.write(
        "paperdelta.yaml",
        store.read("paperdelta.yaml").replace(b"accuracy: decimal", b"accuracy: string"),
    )
    report = check_project(project)
    assert report["exit_code"] == 2
    assert report["metrics"]["ours"]["error"] == "COLUMN_TYPE"
