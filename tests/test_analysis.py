import json
from pathlib import Path

from paperdelta.analysis import check_project
from paperdelta.snapshots import create_snapshot, read_snapshot
from paperdelta.storage import Project


def test_original_paper_has_six_confirmed_checks(project):
    report = check_project(project)
    assert report["exit_code"] == 0
    assert report["coverage"]["confirmed"] == report["coverage"]["pass"] == 6
    assert report["coverage"]["unbound_numbers"] == []
    assert report["coverage"]["unsupported"] == []
    assert report["metrics"]["ours"]["value"] == "0.841"
    assert report["metrics"]["gain"]["value"] == "3.100"


def test_data_only_change_finds_every_affected_span_and_false_claim(project, change_results):
    original_tex = {p.name: p.read_bytes() for p in project.rglob("*.tex")}
    create_snapshot(Project(project), "submitted-v1", check_project(project))
    change_results(project)
    report = check_project(project, baseline=read_snapshot(Project(project), "submitted-v1"))
    assert report["exit_code"] == 1
    assert report["coverage"]["mismatch"] == 5
    assert report["occurrences"]["abstract_accuracy"]["expected"] == r"80.9\%"
    assert report["occurrences"]["gain_text"]["expected"] == "-0.1"
    assert report["claims"]["main_comparison"]["status"] == "mismatch"
    assert {item["metric"] for item in report["changes"]} == {"ours", "gain"}
    assert set(report["changes"][0]["occurrences"]) == {
        "abstract_accuracy",
        "table_accuracy",
        "appendix_accuracy",
    }
    assert all(
        state["suggestion"]["blocked_by"] == ["claim:main_comparison"]
        for state in report["occurrences"].values()
        if "suggestion" in state
    )
    assert original_tex == {p.name: p.read_bytes() for p in project.rglob("*.tex")}


def test_improved_result_can_have_numeric_fixes_without_false_claim(project, change_results):
    change_results(project, new=("0.843", "0.845", "0.847"))
    report = check_project(project)
    assert report["claims"]["main_comparison"]["status"] == "pass"
    assert report["occurrences"]["gain_text"]["expected"] == "3.5"
    assert all(
        not item["suggestion"]["blocked_by"]
        for item in report["occurrences"].values()
        if "suggestion" in item
    )


def test_unrelated_rows_and_order_do_not_invalidate_bound_evidence(project):
    original = check_project(project)
    create_snapshot(Project(project), "before", original)
    baseline = read_snapshot(Project(project), "before")
    path = project / "results/metrics.csv"
    lines = path.read_text(encoding="utf-8").replace("0.500", "0.750").splitlines()
    path.write_text("\n".join([lines[0], *reversed(lines[1:])]) + "\n", encoding="utf-8")
    report = check_project(project, baseline=baseline)
    assert report["exit_code"] == 0
    assert report["changes"] == []
    assert (
        original["input_hashes"]["results/metrics.csv"]
        != report["input_hashes"]["results/metrics.csv"]
    )


def test_rounding_does_not_hide_evidence_changes(project):
    original = check_project(project)
    create_snapshot(Project(project), "before", original)
    path = project / "results/metrics.csv"
    path.write_text(path.read_text().replace("0.839", "0.83901"), encoding="utf-8")
    report = check_project(project, baseline=read_snapshot(Project(project), "before"))
    assert report["exit_code"] == 0
    assert {change["metric"] for change in report["changes"]} == {"ours", "gain"}
    assert report["occurrences"]["abstract_accuracy"]["status"] == "pass"


def test_missing_seed_is_unknown_not_a_smaller_silent_mean(project):
    path = project / "results/metrics.csv"
    path.write_text(path.read_text().replace("Data-A,Ours,test,3,0.843\n", ""), encoding="utf-8")
    report = check_project(project)
    assert report["exit_code"] == 2
    assert report["metrics"]["ours"]["error"] == "SEED_SET"
    assert report["occurrences"]["abstract_accuracy"]["status"] == "unknown"


def test_duplicate_record_never_overwrites_an_earlier_value(project):
    path = project / "results/metrics.csv"
    path.write_text(path.read_text() + "Data-A,Ours,test,1,0.999\n", encoding="utf-8")
    report = check_project(project)
    assert report["exit_code"] == 2
    assert report["metrics"]["ours"]["error"] == "DUPLICATE_RECORD"


def test_same_number_at_multiple_locations_is_not_silently_bound(project):
    path = project / "paper/abstract.tex"
    path.write_text(
        path.read_text() + "Our method achieves 84.1\\% accuracy on Data-A.\n", encoding="utf-8"
    )
    report = check_project(project)
    assert report["exit_code"] == 2
    assert report["occurrences"]["abstract_accuracy"]["error"] == "ANCHOR_AMBIGUOUS"


def test_scope_mismatch_is_not_a_valid_comparison(project):
    config = project / "paperdelta.yaml"
    text = config.read_text().replace(
        "scope: {dataset: Data-A, split: test}", "scope: {dataset: Data-A, split: train}"
    )
    config.write_text(text, encoding="utf-8")
    report = check_project(project)
    assert report["exit_code"] == 2
    assert report["claims"]["main_comparison"]["error"] == "SCOPE_MISMATCH"


def test_empty_configuration_does_not_pass(tmp_path):
    (tmp_path / "paper.tex").write_text("Some text.", encoding="utf-8")
    (tmp_path / "paperdelta.yaml").write_text(
        "schema_version: 1\npaper: {entry: paper.tex}\n", encoding="utf-8"
    )
    report = check_project(tmp_path)
    assert report["exit_code"] == 2
    assert any(item["rule"] == "NO_BINDINGS" for item in report["diagnostics"])


def test_json_pointer_keeps_slashes_dots_and_decimal_precision(tmp_path):
    (tmp_path / "result.json").write_text(
        '{"a.b":{"x/y":0.12345678901234567890123456789}}', encoding="utf-8"
    )
    (tmp_path / "paper.tex").write_text("Value: 0.12346.", encoding="utf-8")
    (tmp_path / "paperdelta.yaml").write_text(
        """schema_version: 1
paper: {entry: paper.tex}
sources:
  data: {path: result.json, format: json}
metrics:
  score: {source: data, field: /a.b/x~1y, unit: scalar}
occurrences:
  score:
    file: paper.tex
    anchor: {prefix: 'Value: ', suffix: '.'}
    metric: score
    display: {places: 5}
""",
        encoding="utf-8",
    )
    # A short '.' suffix would cut the decimal at its first dot. Use the exact span.
    config = tmp_path / "paperdelta.yaml"
    config.write_text(
        config.read_text().replace("{prefix: 'Value: ', suffix: '.'}", "{exact: '0.12346'}"),
        encoding="utf-8",
    )
    report = check_project(tmp_path)
    assert report["exit_code"] == 0
    assert report["metrics"]["score"]["value"] == "0.12345678901234567890123456789"


def test_figure_record_requires_unchanged_input_identities(project):
    from paperdelta.storage import json_text, sha256

    (project / "figure.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8"
    )
    (project / "plot.py").write_text(
        "# Original test fixture; never executed by PaperDelta\n", encoding="utf-8"
    )
    record = {
        "schema_version": 1,
        "path": "figure.svg",
        "output_hash": sha256((project / "figure.svg").read_bytes()),
        "inputs": {"results/metrics.csv": sha256((project / "results/metrics.csv").read_bytes())},
        "script": {"path": "plot.py", "hash": sha256((project / "plot.py").read_bytes())},
        "recorded_at": "2026-10-03T00:00:00Z",
        "method": "manual",
    }
    (project / "figure.record.json").write_text(json_text(record), encoding="utf-8")
    config = project / "paperdelta.yaml"
    config.write_text(
        config.read_text()
        + "\nfigures:\n  accuracy: {path: figure.svg, record: figure.record.json}\n",
        encoding="utf-8",
    )
    report = check_project(project)
    assert report["figures"]["accuracy"]["provenance"] == "unchanged_since_record"
    (project / "plot.py").write_text("# changed plotting implementation\n", encoding="utf-8")
    report = check_project(project)
    assert report["figures"]["accuracy"]["provenance"] == "dependency_changed"
    assert report["exit_code"] == 1
    assert json.loads(json_text(report))["figures"]["accuracy"]["record_method"] == "manual"


def test_public_figure_fixture_tracks_data_and_plot_script(project, change_results):
    # Use the same prepared, actually generated assets as the offline demonstration.
    from tools.demo import add_figure

    add_figure(Project(project), Path(__file__).resolve().parents[1])
    initial = check_project(project)
    assert initial["exit_code"] == 0
    assert initial["coverage"]["confirmed"] == 7
    assert initial["coverage"]["unregistered_figures"] == []
    change_results(project)
    changed = check_project(project)
    figure = changed["figures"]["accuracy"]
    assert changed["coverage"]["mismatch"] == 6
    assert figure["provenance"] == "dependency_changed"
    assert "results/metrics.csv" in figure["changed_paths"]
    assert all("accuracy" in group["figures"] for group in changed["impact_groups"])
