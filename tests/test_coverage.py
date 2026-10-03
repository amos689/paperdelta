import json
import re
import subprocess
import sys

import pytest

from paperdelta.analysis import check_project
from paperdelta.config import config_text, load_config
from paperdelta.coverage import change_scope
from paperdelta.errors import PaperDeltaError
from paperdelta.html_report import html_report
from paperdelta.i18n import language_context
from paperdelta.onboarding import scan_project
from paperdelta.records import StoredReport
from paperdelta.storage import Project, parse_json


def append_number(root):
    path = root / "paper/appendix.tex"
    path.write_text(
        path.read_text(encoding="utf-8") + "\nThe workshop took place in 2024.\n", encoding="utf-8"
    )
    return path


def year_candidate(store):
    return next(
        item["candidate_id"] for item in scan_project(store)["candidates"] if item["text"] == "2024"
    )


def test_scope_only_limits_unbound_coverage_and_never_suppresses_false_claim(
    project, change_results
):
    append_number(project)
    store = Project(project)
    before = store.read("paperdelta.yaml")
    preview = change_scope(store, action="set", regions=["abstract"], require_complete=True)
    assert preview["status"] == "preview"
    assert store.read("paperdelta.yaml") == before
    assert preview["preview"]["exit_code"] == 0
    assert [item["text"] for item in preview["preview"]["coverage"]["outside_scope_numbers"]] == [
        "2024"
    ]
    saved = change_scope(
        store, action="set", regions=["abstract"], require_complete=True, accept=True
    )
    assert store.read(saved["backup"]) == before
    change_results(project)
    result = check_project(project)
    assert result["exit_code"] == 1
    assert result["coverage"]["mismatch"] == 5
    assert any(item["rule"] == "CLAIM_FALSE" for item in result["diagnostics"])
    restored = change_scope(store, action="clear", accept=True)
    assert restored["preview"]["exit_code"] == 2
    assert len(restored["preview"]["coverage"]["unbound_numbers"]) == 1


def test_exclusion_is_bound_to_context_and_cannot_hide_a_changed_number(project):
    path = append_number(project)
    store = Project(project)
    result = change_scope(
        store,
        action="exclude",
        candidate_id=year_candidate(store),
        name="workshop_year",
        reason="Publication context, not an experimental result.",
        accept=True,
    )
    assert result["preview"]["coverage"]["exclusions"][0]["status"] == "active"
    assert result["preview"]["coverage"]["unbound_numbers"] == []
    path.write_text(
        path.read_text(encoding="utf-8").replace("workshop", "experiment"), encoding="utf-8"
    )
    result = check_project(project)
    assert result["exit_code"] == 2
    assert result["coverage"]["exclusions"][0]["error"] == "EXCLUSION_STALE"
    assert result["coverage"]["unbound_numbers"][0]["text"] == "2024"
    change_scope(store, action="remove-exclusion", name="workshop_year", accept=True)
    assert check_project(project)["coverage"]["exclusions"] == []


def test_an_accepted_binding_cannot_be_excluded_even_after_evidence_changes(
    project, change_results
):
    store = Project(project)
    change_results(project)
    choice = next(item for item in scan_project(store)["candidates"] if item["text"] == "84.1")
    before = store.read("paperdelta.yaml")
    with pytest.raises(PaperDeltaError, match="invalid|overlaps"):
        change_scope(
            store,
            action="exclude",
            candidate_id=choice["candidate_id"],
            name="hide_error",
            reason="This should fail",
            accept=True,
        )
    assert store.read("paperdelta.yaml") == before
    assert check_project(project)["exit_code"] == 1


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_cli_scope_preview_and_bilingual_html_are_complete(project, language):
    append_number(project)
    command = [
        sys.executable,
        "-m",
        "paperdelta",
        "--lang",
        language,
        "-C",
        str(project),
        "scope",
        "set",
        "--file",
        "paper/abstract.tex",
        "--require-complete",
        "--format",
        "json",
    ]
    before = (project / "paperdelta.yaml").read_bytes()
    result = subprocess.run(command, capture_output=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    preview = parse_json(result.stdout)
    assert preview["status"] == "preview"
    assert (project / "paperdelta.yaml").read_bytes() == before
    StoredReport.model_validate(preview["preview"])
    with language_context(language):
        page = html_report(preview["preview"])
    assert "2024" in page and "coverage-outside_scope_numbers" in page
    assert 'lang="' + language + '"' in page
    strings = json.loads(re.search(r'id="report-locales">(.*?)</script>', page).group(1))
    assert "Outside selected numeric scope" in str(strings) and "所选数值范围外" in str(strings)


def test_scope_rejects_nonincluded_file_and_version_one_remains_compatible(project):
    store = Project(project)
    before = store.read("paperdelta.yaml")
    with pytest.raises(PaperDeltaError):
        change_scope(store, action="set", files=["not-in-paper.tex"], accept=True)
    assert store.read("paperdelta.yaml") == before
    config, _ = load_config(store)
    encoded = config_text(config)
    assert "review_scope" not in encoded and "coverage_exclusions" not in encoded
    assert config.schema_version == 1


def test_scope_with_no_matching_region_and_duplicate_aliases_is_not_vacuous_success(project):
    store = Project(project)
    with pytest.raises(PaperDeltaError):
        change_scope(
            store, action="set", files=["paper/appendix.tex"], regions=["table"], accept=True
        )
    with pytest.raises(PaperDeltaError):
        change_scope(
            store, action="set", files=["paper/abstract.tex", "paper/./abstract.tex"], accept=True
        )


def test_exclusion_reason_is_escaped_in_html(project):
    append_number(project)
    store = Project(project)
    result = change_scope(
        store,
        action="exclude",
        candidate_id=year_candidate(store),
        name="year",
        reason="<script>alert(1)</script> quoted context",
        accept=True,
    )
    page = html_report(result["preview"])
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
