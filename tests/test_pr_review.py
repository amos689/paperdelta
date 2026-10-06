from copy import deepcopy

import pytest
from test_ci_wrapper import _commit_baseline
from test_ci_wrapper import git_repo as git_repo

from paperdelta.analysis import check_project
from paperdelta.config import config_text, load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import language_context
from paperdelta.storage import Project
from tools.ci_check import ci_summary, run_ci


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_ci_never_reads_checkout_metadata_as_paper_evidence(project, git_repo, language):
    base, _ = _commit_baseline(project, git_repo)
    store = Project(project)
    config, _ = load_config(store)
    source = next(iter(config.sources.values()))
    source.path = ".git/synthetic-credentials.csv"
    store.write(source.path, b"private_token\nDO_NOT_INCLUDE_THIS_SENTINEL\n")
    store.write("paperdelta.yaml", config_text(config).encode())
    with language_context(language):
        result = run_ci(project, base, "submitted-v1", "build/restricted")
    assert result["report"]["exit_code"] == 2
    assert any(d["rule"] == "CI_PRIVATE_PATH" for d in result["report"]["diagnostics"])
    for name in ("report.json", "report.html", "report.sarif", "ci-summary.md"):
        assert b"DO_NOT_INCLUDE_THIS_SENTINEL" not in store.read("build/restricted/" + name)
    with pytest.raises(PaperDeltaError) as error:
        run_ci(project, base, "submitted-v1", "build/restricted", ".git/config")
    assert error.value.code == "CI_PRIVATE_PATH"
    with pytest.raises(PaperDeltaError) as error:
        run_ci(project, base, "submitted-v1", ".git")
    assert error.value.code == "CI_PRIVATE_PATH"


def test_pr_changes_distinguish_fixed_missing_and_removed_checks(project, change_results, git_repo):
    change_results(project)
    base, _ = _commit_baseline(project, git_repo)
    config, _ = load_config(Project(project))
    del config.occurrences["table_accuracy"]
    Project(project).write("paperdelta.yaml", config_text(config).encode())
    result = run_ci(project, base, "submitted-v1", "build/ci")
    delta = result["context"]["finding_changes"]
    assert delta["counts"]["removed_bindings"] == 1
    assert delta["counts"]["resolved_failures"] == 0
    assert delta["removed_bindings"][0]["subject"] == "occurrence:table_accuracy"
    assert delta["removed_bindings"][0]["before"] == "mismatch"
    assert "Removed bindings" in ci_summary(result)


def test_only_corrected_evidence_with_same_contract_resolves_old_failure(
    project, change_results, git_repo
):
    original = (project / "results/metrics.csv").read_bytes()
    change_results(project)
    base, _ = _commit_baseline(project, git_repo)
    (project / "results/metrics.csv").write_bytes(original)
    result = run_ci(project, base, "submitted-v1", "build/fixed")
    delta = result["context"]["finding_changes"]
    assert delta["counts"]["resolved_failures"] >= 5
    assert delta["counts"]["unverified"] == 0
    (project / "results/metrics.csv").unlink()
    missing = run_ci(project, base, "submitted-v1", "build/missing")
    changes = missing["context"]["finding_changes"]
    assert changes["counts"]["resolved_failures"] == 0
    assert changes["counts"]["unverified"] >= 5


def test_data_only_pr_shows_all_changes_and_no_baseline_does_not_invent_history(
    project, change_results, git_repo
):
    base, _ = _commit_baseline(project, git_repo)
    change_results(project)
    result = run_ci(project, base, "submitted-v1", "build/new")
    delta = result["context"]["finding_changes"]
    assert delta["counts"]["added_failures"] >= 5
    assert result["context"]["configuration"]["status"] == "unchanged"
    unknown = run_ci(project, base, "absent", "build/no-history")
    changes = unknown["context"]["finding_changes"]
    assert changes["comparison"] == "unavailable"
    assert changes["counts"]["added_failures"] == 0
    assert changes["counts"]["current_failures_without_baseline"] >= 5


def test_changed_metric_contract_does_not_claim_scientific_resolution(project):
    from paperdelta.pr_review import review_delta

    before = check_project(project)
    before["occurrences"]["abstract_accuracy"]["status"] = "mismatch"
    after = deepcopy(before)
    after["occurrences"]["abstract_accuracy"]["status"] = "pass"
    changes = {
        "status": "changed",
        "sections": [{"section": "metrics", "added": [], "removed": [], "changed": ["ours"]}],
        "settings": [],
    }
    delta = review_delta(
        after, {"name": "old", "report": before}, changes, same_baseline_contract=True
    )
    assert delta["counts"]["resolved_failures"] == 0
    assert any(
        item["subject"] == "occurrence:abstract_accuracy" for item in delta["changed_contracts"]
    )


def test_removed_stale_generation_and_fragment_records_never_count_as_resolved(project, git_repo):
    from test_fragments import spec
    from test_provenance import setup_notebook

    from paperdelta.fragments import accept_fragment, preview_fragment
    from paperdelta.provenance import accept_producer

    store, _, proposal = setup_notebook(project)
    accept_producer(store, proposal)
    accept_fragment(store, preview_fragment(store, "results", spec()))
    store.write("observations.csv", b"sample,value\na,2\n")
    store.write(spec()["path"], b"Manual change makes the fragment stale.\n")
    base, _ = _commit_baseline(project, git_repo)
    config, _ = load_config(store)
    config.provenance = {}
    config.fragments = {}
    store.write("paperdelta.yaml", config_text(config).encode())
    result = run_ci(project, base, "submitted-v1", "build/removed-workflows")
    delta = result["context"]["finding_changes"]
    removed = {item["subject"]: item for item in delta["removed_bindings"]}
    for subject in ("provenance:training", "fragment:results"):
        assert removed[subject]["before"] == "mismatch"
    assert delta["counts"]["resolved_failures"] == 0
