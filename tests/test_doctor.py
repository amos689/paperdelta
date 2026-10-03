import importlib.util

from paperdelta.doctor import diagnose, doctor_text
from paperdelta.i18n import language_context
from paperdelta.storage import Project


def test_doctor_checks_real_project_without_writing(project):
    before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    result = diagnose(Project(project))
    assert result["exit_code"] == 0 and result["project_check_exit_code"] == 0
    assert {
        p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()
    } == before
    assert any(
        item["id"] == "configuration" and item["status"] == "ok" for item in result["checks"]
    )


def test_missing_evidence_is_actionable_in_both_languages(project):
    (project / "results/metrics.csv").rename(project / "results/metrics.saved.csv")
    result = diagnose(Project(project))
    assert result["exit_code"] == 2
    with language_context("zh-CN"):
        chinese = doctor_text(result)
    assert "无法读取 results/metrics.csv" in chinese
    assert "数据文件、字段、筛选条件" in chinese
    assert "Cannot read results/metrics.csv" in doctor_text(result)


def test_optional_mcp_becomes_required_only_when_requested(project, monkeypatch):
    real = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda name: None if name == "mcp" else real(name)
    )
    optional = diagnose(Project(project))
    required = diagnose(Project(project), require_mcp=True)
    assert optional["exit_code"] == 0 and required["exit_code"] == 2
    assert next(item for item in optional["checks"] if item["id"] == "mcp")["status"] == "optional"


def test_invalid_configuration_has_translated_validation_details(project):
    (project / "paperdelta.yaml").write_text(
        "schema_version: 1\npaper: {entry: 7}\n", encoding="utf-8"
    )
    result = diagnose(Project(project))
    assert result["exit_code"] == 2
    with language_context("zh-CN"):
        assert "paper.entry：需要字符串" in doctor_text(result)
