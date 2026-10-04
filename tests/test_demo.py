import json
import subprocess
import sys

import pytest

from paperdelta.analysis import check_project
from paperdelta.demo import create_demo
from paperdelta.errors import PaperDeltaError
from paperdelta.patches import apply_patch, recover_transaction
from paperdelta.storage import Project, parse_json


@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("scenario", ["baseline", "changed", "safe-update"])
def test_installed_entry_point_generates_expected_offline_demo(tmp_path, language, scenario):
    process = subprocess.run(
        [
            sys.executable,
            "-m",
            "paperdelta",
            "--lang",
            language,
            "-C",
            str(tmp_path),
            "demo",
            "--out",
            "论文 demo",
            "--scenario",
            scenario,
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert process.returncode == 0, process.stderr + process.stdout
    result = json.loads(process.stdout)
    assert result["check_exit_code"] == (0 if scenario == "baseline" else 1)
    project = Project(tmp_path / result["project"])
    report = parse_json(project.text("review/report.json")[0])
    html = project.text("review/report.html")[0]
    assert f'<html lang="{language}"' in html
    assert report["exit_code"] == result["check_exit_code"]
    assert project.path("paper/figures/accuracy.pdf").is_file()
    if scenario == "changed":
        assert report["claims"]["main_comparison"]["status"] == "mismatch"
        assert report["figures"]["accuracy"]["provenance"] == "dependency_changed"
        assert all(
            o["suggestion"]["blocked_by"]
            for o in report["occurrences"].values()
            if "suggestion" in o
        )
    if scenario == "safe-update":
        original = {
            name: project.read(name) for name in report["input_hashes"] if name.endswith(".tex")
        }
        patch = parse_json(project.text("changes.pdpatch.json")[0])
        assert len(patch["changes"]) == 4
        applied = apply_patch(project, patch)
        assert all(o["status"] == "pass" for o in applied["report"]["occurrences"].values())
        # Numeric edits cannot refresh an out-of-date plot.
        assert applied["report"]["figures"]["accuracy"]["provenance"] == "dependency_changed"
        recover_transaction(project, applied["transaction_id"], write=True)
        assert all(project.read(name) == raw for name, raw in original.items())


def test_demo_never_overwrites_an_existing_destination_or_escapes_project(tmp_path):
    (tmp_path / "existing").mkdir()
    (tmp_path / "existing" / "keep.txt").write_text("keep", "utf-8")
    for path, code in (("existing", "ALREADY_EXISTS"), ("../escape", "UNSAFE_PATH")):
        with pytest.raises(PaperDeltaError) as caught:
            create_demo(Project(tmp_path), path)
        assert caught.value.code == code
    assert (tmp_path / "existing" / "keep.txt").read_text("utf-8") == "keep"
    assert not (tmp_path.parent / "escape").exists()
    create_demo(Project(tmp_path), "new", "baseline")
    assert check_project(tmp_path / "new")["exit_code"] == 0


@pytest.mark.parametrize("kind", ["markdown", "quarto"])
@pytest.mark.parametrize("language", ["en", "zh-CN"])
@pytest.mark.parametrize("scenario", ["baseline", "changed", "safe-update"])
def test_static_source_demos_run_in_both_languages_without_writing_source(
    tmp_path, kind, language, scenario
):
    from importlib.resources import files

    from paperdelta.i18n import language_context

    with language_context(language):
        result = create_demo(Project(tmp_path), "demo", scenario, kind)
    project = Project(tmp_path / "demo")
    source = "paper." + ("md" if kind == "markdown" else "qmd")
    report = parse_json(project.text("review/report.json")[0])
    assert report["report_schema_version"] == 8
    assert result["patch"] is None
    assert project.read(source) == files("paperdelta").joinpath("demo_" + kind, source).read_bytes()
    assert f'<html lang="{language}"' in project.text("review/report.html")[0]
    assert report["exit_code"] == (0 if scenario == "baseline" else 1)
    if scenario == "changed":
        assert report["coverage"]["mismatch"] == 3
        assert report["claims"]["main_comparison"]["status"] == "mismatch"
