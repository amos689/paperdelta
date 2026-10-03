import json
import os
import subprocess
import sys

import pytest

from paperdelta.analysis import check_project
from paperdelta.storage import Project, parse_json


def cli(project, language, *arguments):
    environment = {**os.environ, "PAPERDELTA_LANG": "en", "PYTHONUTF8": "1"}
    return subprocess.run(
        [sys.executable, "-m", "paperdelta", "--lang", language, "-C", str(project), *arguments],
        capture_output=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        (["--help"], "显示程序版本并退出"),
        (["init"], "缺少必填参数"),
        (["check", "--format", "bad"], "无效选项"),
        (["check", "--missing-option"], "无法识别参数"),
        (["check", "--baseline"], "需要一个参数值"),
        (
            ["bind", "--proposal", "none.json", "--accept", "occurrences:x", "--interactive"],
            "不能与参数",
        ),
    ],
)
def test_cli_help_and_argument_failures_are_chinese(project, arguments, expected):
    result = cli(project, "zh-CN", *arguments)
    assert result.returncode == (0 if "--help" in arguments else 2)
    assert expected in result.stdout + result.stderr
    assert "invalid choice:" not in result.stderr
    assert "arguments are required:" not in result.stderr


def test_json_argument_and_core_errors_remain_parseable(project):
    invalid_language = cli(project, "not-a-language", "check", "--format", "json")
    assert invalid_language.returncode == 2 and not invalid_language.stderr
    assert json.loads(invalid_language.stdout)["error"] == "LANGUAGE"
    result = cli(project, "zh-CN", "check", "--format", "json", "--not-an-option")
    record = json.loads(result.stdout)
    assert result.returncode == 2 and not result.stderr
    assert record["error"] == "ARGUMENTS" and "无法识别" in record["display_message"]
    result = cli(project, "zh-CN", "bind", "--proposal", "missing.json", "--format", "json")
    record = json.loads(result.stdout)
    assert result.returncode == 2 and not result.stderr
    assert record["error"] == "FILE_UNAVAILABLE" and "无法读取" in record["display_message"]


def test_preference_changes_do_not_touch_scientific_state(project):
    before = check_project(project)
    result = cli(project, "en", "settings", "--language", "zh-CN", "--format", "json")
    assert result.returncode == 0 and json.loads(result.stdout)["language"] == "zh-CN"
    after = check_project(project)
    before.pop("created_at")
    after.pop("created_at")
    assert before == after
    environment = dict(os.environ)
    environment.pop("PAPERDELTA_LANG", None)
    preference = subprocess.run(
        [sys.executable, "-m", "paperdelta", "-C", str(project), "check"],
        capture_output=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )
    assert preference.returncode == 0 and "已确认绑定" in preference.stdout
    assert "confirmed bindings" in cli(project, "en", "check").stdout


def test_same_patch_in_both_languages_and_structured_write_recovery(project, change_results):
    change_results(project, new=("0.843", "0.845", "0.847"))
    paper_files = {p.relative_to(project): p.read_bytes() for p in project.rglob("*.tex")}
    for language in ("en", "zh-CN"):
        directory = "build/" + language
        check = cli(project, language, "check", "--format", "json", "--report", directory)
        assert check.returncode == 1
        result = cli(
            project,
            language,
            "fix",
            "--report",
            directory + "/report.json",
            "--out",
            "build/" + language + ".json",
            "--format",
            "json",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert json.loads(result.stdout)["command_result_version"] == 1
    english = parse_json(Project(project).text("build/en.json")[0])
    chinese = parse_json(Project(project).text("build/zh-CN.json")[0])
    assert english == chinese
    markdown = (project / "build/zh-CN/report.md").read_text("utf-8")
    assert "已确认绑定" in markdown and "应根据指标" in markdown
    preview = cli(project, "zh-CN", "apply", "build/en.json", "--format", "json")
    assert json.loads(preview.stdout)["status"] == "preview"
    assert all((project / path).read_bytes() == raw for path, raw in paper_files.items())
    applied = cli(project, "zh-CN", "apply", "build/en.json", "--write", "--format", "json")
    assert applied.returncode == 0, applied.stdout + applied.stderr
    transaction = json.loads(applied.stdout)["transaction_id"]
    assert len(transaction) == 32
    restored = cli(project, "en", "recover", transaction, "--write", "--format", "json")
    assert restored.returncode == 0 and json.loads(restored.stdout)["status"] == "reverted"
    assert all((project / path).read_bytes() == raw for path, raw in paper_files.items())
