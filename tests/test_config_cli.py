import json
import subprocess
import sys

import pytest

from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.reports import html_report
from paperdelta.snapshots import create_snapshot
from paperdelta.storage import Project, parse_json


@pytest.mark.parametrize(
    "text",
    [
        "schema_version: 1\nschema_version: 2\npaper: {entry: p.tex}\n",
        "schema_version: 1\npaper: {entry: p.tex}\nunknown_field: true\n",
        "!!python/object/apply:os.system ['echo unsafe']",
    ],
)
def test_bad_config_is_rejected(tmp_path, text):
    (tmp_path / "paperdelta.yaml").write_text(text, encoding="utf-8")
    with pytest.raises(PaperDeltaError):
        load_config(Project(tmp_path))


def test_duplicate_json_key_does_not_hide_previous_value():
    with pytest.raises(PaperDeltaError, match="Duplicate"):
        parse_json('{"value":1,"value":2}')


def test_cli_outputs_machine_readable_json_with_correct_exit(project, change_results):
    change_results(project)
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "paperdelta",
            "-C",
            str(project),
            "check",
            "--format",
            "json",
            "--report",
            "build/review",
        ],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 1
    assert json.loads(proc.stdout)["coverage"]["mismatch"] == 5
    assert proc.stderr == ""
    html = (project / "build/review/report.html").read_text(encoding="utf-8")
    assert "paper/abstract.tex:2" in html and "Record identity" in html
    assert "Our method outperforms Baseline" in html


def test_snapshot_is_not_silently_overwritten(project):
    report = check_project(project)
    create_snapshot(Project(project), "v1", report)
    with pytest.raises(PaperDeltaError, match="overwrite"):
        create_snapshot(Project(project), "v1", report)


def test_html_escapes_manuscript_and_evidence_text(project):
    report = check_project(project)
    payload = '</script><img src=x onerror="alert(1)">'
    report["diagnostics"].append(
        {"subject": "project", "severity": "unknown", "rule": "TEST", "message": payload}
    )
    html = html_report(report)
    assert payload not in html
    assert "&lt;/script&gt;&lt;img" in html
    assert "https://" not in html
