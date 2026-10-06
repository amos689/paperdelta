from pathlib import Path

import pytest
from test_studio import call, stage_locations, stage_metric
from test_studio import studio_project as studio_project

from paperdelta.analysis import check_project
from paperdelta.html_report import html_report
from paperdelta.i18n import language_context
from paperdelta.sarif import sarif_report
from paperdelta.studio import StudioSession


def test_sarif_uses_real_manuscript_lines_and_original_native_positions(studio_project):
    project, path = studio_project
    session = StudioSession(project)
    stage_metric(session, path)
    stage_locations(session)
    preview = call(session, "preview")["state"]["preview"]
    call(
        session,
        "accept",
        {
            "proposal_id": preview["proposal_id"],
            "selected": [item["binding"] for item in preview["items"]],
        },
    )
    project.write("results.csv", project.read("results.csv").replace(b"0.840", b"0.800"))
    report = check_project(project.root)
    sarif = sarif_report(report)
    source = project.read(path)
    results = sarif["runs"][0]["results"]
    assert len(results) == len(report["diagnostics"])
    for diagnostic, result in zip(report["diagnostics"], results, strict=True):
        assert result["ruleId"] == diagnostic["rule"]
        location = diagnostic.get("location")
        if not location:
            continue
        physical = result["locations"][0]["physicalLocation"]
        if Path(path).suffix in {".tex", ".md", ".qmd"}:
            region = physical["region"]
            line = source.decode().splitlines()[region["startLine"] - 1]
            assert line[region["startColumn"] - 1 : region["endColumn"] - 1] == location["text"]
        else:
            assert "region" not in physical
            assert result["properties"]["nativeLocation"] == location
            anchor = result["properties"]["reportLocation"].partition("#")[2]
            assert f'id="{anchor}"' in html_report(report)
    assert "%E8%AE%BA%E6%96%87" in str(sarif)


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_ci_summary_supports_native_locations_without_fabricating_line_one(
    studio_project, language
):
    from tools.ci_check import ci_summary

    project, path = studio_project
    session = StudioSession(project)
    stage_metric(session, path)
    stage_locations(session)
    preview = call(session, "preview")["state"]["preview"]
    call(
        session,
        "accept",
        {
            "proposal_id": preview["proposal_id"],
            "selected": [item["binding"] for item in preview["items"]],
        },
    )
    project.write("results.csv", project.read("results.csv").replace(b"0.840", b"0.800"))
    report = check_project(project.root)
    with language_context(language):
        text = ci_summary(
            {
                "report": report,
                "context": {
                    "base_commit": "a" * 40,
                    "baseline_status": "unavailable",
                    "policy_changes": [],
                    "configuration": {"status": "unchanged", "sections": [], "settings": []},
                },
            }
        )
    assert path in text
    if Path(path).suffix in {".pdf", ".docx"}:
        assert path + ":1" not in text
