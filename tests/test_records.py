import copy
import json

import pytest

from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.records import StoredReport, validate_record
from paperdelta.reviews import record_review
from paperdelta.snapshots import create_snapshot, read_snapshot
from paperdelta.storage import Project


def review(project):
    state = check_project(project)["claims"]["main_comparison"]["state_fingerprint"]
    return record_review(
        Project(project), "main_comparison", state, "Test author", "Fixture", attest_reviewed=True
    )


def test_review_tracks_exact_evidence_state_even_if_display_still_matches(project):
    path = review(project)
    assert (project / path).exists()
    assert check_project(project)["claims"]["main_comparison"]["review"] == "reviewed"
    data = project / "results/metrics.csv"
    before = data.read_bytes()
    data.write_bytes(before.replace(b"0.839", b"0.83901"))
    changed = check_project(project)
    assert changed["exit_code"] == 0
    assert changed["claims"]["main_comparison"]["review"] == "superseded"
    data.write_bytes(before)
    restored = check_project(project)["claims"]["main_comparison"]
    assert restored["review"] == "reviewed" and len(restored["matching_reviews"]) == 1


def test_review_does_not_turn_a_false_predicate_green(project, change_results):
    change_results(project)
    review(project)
    report = check_project(project)
    assert report["claims"]["main_comparison"]["review"] == "reviewed"
    assert report["claims"]["main_comparison"]["status"] == "mismatch"
    assert report["exit_code"] == 1
    assert report["occurrences"]["abstract_accuracy"]["suggestion"]["blocked_by"]


def test_review_requires_explicit_attestation(project):
    state = check_project(project)["claims"]["main_comparison"]["state_fingerprint"]
    with pytest.raises(PaperDeltaError) as error:
        record_review(Project(project), "main_comparison", state, "Test author", "")
    assert error.value.code == "REVIEW_ATTESTATION"
    assert not (project / ".paperdelta/reviews").exists()


def test_old_state_cannot_be_recorded_as_current_review(project, change_results):
    state = check_project(project)["claims"]["main_comparison"]["state_fingerprint"]
    change_results(project)
    with pytest.raises(PaperDeltaError) as error:
        record_review(
            Project(project), "main_comparison", state, "Author", "", attest_reviewed=True
        )
    assert error.value.code == "STALE_REVIEW"


def test_corrupted_record_is_reported_not_ignored(project):
    path = project / review(project)
    record = json.loads(path.read_text(encoding="utf-8"))
    record["reviewer"] = "Edited author"
    path.write_text(json.dumps(record), encoding="utf-8")
    report = check_project(project)
    assert report["exit_code"] == 2
    assert any(item["rule"] == "REVIEW_IDENTITY" for item in report["diagnostics"])


@pytest.mark.parametrize("bad", [[], "metric", {"ours": []}, {"ours": {"status": "ok"}}])
def test_malformed_baseline_does_not_crash_checker(project, bad):
    store = Project(project)
    create_snapshot(store, "before", check_project(project))
    baseline = copy.deepcopy(read_snapshot(store, "before"))
    baseline["report"]["metrics"] = bad
    report = check_project(project, baseline=baseline)
    assert report["exit_code"] == 2
    assert any(item["rule"] == "BASELINE_SCHEMA" for item in report["diagnostics"])


def test_boolean_schema_version_is_not_version_one(project):
    path = project / "paperdelta.yaml"
    path.write_text(
        path.read_text().replace("schema_version: 1", "schema_version: true"), encoding="utf-8"
    )
    assert check_project(project)["exit_code"] == 2


@pytest.mark.parametrize(
    "path,value",
    [
        (("occurrences", "abstract_accuracy", "location", "byte_end"), -1),
        (("occurrences", "abstract_accuracy", "location", "byte_end"), 1000000),
        (("occurrences", "abstract_accuracy", "unrecognized"), True),
        (("metrics", "ours", "evidence", 0, "count"), 99),
        (("metrics", "ours", "value"), "NaN"),
        (("coverage", "pass"), 0),
        (("claims", "main_comparison", "review"), "automatically-approved"),
    ],
)
def test_nested_report_contract_rejects_corruption(project, path, value):
    report = check_project(project)
    target = report
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(PaperDeltaError) as error:
        validate_record(StoredReport, report, "REPORT_SCHEMA")
    assert error.value.code == "REPORT_SCHEMA"


def test_report_schema_preserves_aliases_and_exact_json_roundtrip(project):
    from paperdelta.storage import json_text, parse_json

    report = check_project(project)
    validated = StoredReport.model_validate(parse_json(json_text(report)))
    dumped = validated.model_dump(by_alias=True)
    assert dumped["coverage"]["pass"] == 6
    assert "pass_" not in dumped["coverage"]
    assert dumped["metrics"]["ours"]["value"] == "0.841"
