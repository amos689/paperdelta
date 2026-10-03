import ast
import asyncio
from copy import deepcopy
from pathlib import Path

import pytest

from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError, error_message
from paperdelta.i18n import (
    Message,
    catalog,
    current_language,
    language_context,
    msg,
    resolve_language,
    translated,
    validate_catalogs,
)
from paperdelta.models import Config
from paperdelta.storage import Project, fingerprint, json_text


def test_catalogs_cover_registered_runtime_messages_and_preserve_placeholders():
    assert validate_catalogs() == []
    root = Path(__file__).resolve().parents[1] / "src/paperdelta"
    keys = set()
    for source in root.glob("*.py"):
        for node in ast.walk(ast.parse(source.read_text("utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in {"msg", "tr", "Message"}
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                keys.add(node.args[0].value)
    assert keys <= catalog("en").keys()
    assert keys <= catalog("zh-CN").keys()


@pytest.mark.parametrize(
    ("requested", "environment", "preferences", "system", "expected"),
    [
        ("en", {"PAPERDELTA_LANG": "zh-CN"}, {}, "zh_CN", "en"),
        (None, {"PAPERDELTA_LANG": "zh-CN"}, {"language": "en"}, "en_US", "zh-CN"),
        ("auto", {}, {"language": "zh-CN"}, "en_US", "zh-CN"),
        (None, {}, {}, "zh_CN.UTF-8", "zh-CN"),
        (None, {}, {}, "Chinese (Simplified)_China.936", "zh-CN"),
        (None, {}, {}, "en_AU.UTF-8", "en"),
        (None, {}, {}, "fr_FR.UTF-8", "en"),
    ],
)
def test_language_precedence(requested, environment, preferences, system, expected):
    assert (
        resolve_language(
            requested, environ=environment, preferences=preferences, system_locale=system
        )
        == expected
    )


def test_explicit_unknown_language_is_rejected():
    with pytest.raises(ValueError, match="Unsupported language"):
        resolve_language("anything", environ={})


def test_message_metadata_survives_errors_and_copies_without_affecting_identity():
    original = msg("error.STALE_PATCH.2", file="中文 paper.tex")
    error = PaperDeltaError("STALE_PATCH", original)
    assert isinstance(str(error), Message)
    value = {"code": error.code, "message": deepcopy(str(error)), "source": "Author's text"}
    encoded, identity = json_text(value), fingerprint(value)
    with language_context("zh-CN"):
        assert "已发生变化" in translated(value)["message"]
        assert translated(value)["source"] == "Author's text"
        assert json_text(value) == encoded
        assert fingerprint(value) == identity
    assert current_language() == "en"


def test_validation_errors_have_localized_field_paths_and_nested_model_explanations(project):
    path = project / "paperdelta.yaml"
    path.write_text(
        "schema_version: 1\npaper: {entry: paper/main.tex}\n"
        "sources: {data: {path: results.csv, format: csv}}\n",
        encoding="utf-8",
    )
    with pytest.raises(PaperDeltaError) as caught:
        load_config(Project(project))
    rendered = caught.value.render("zh-CN")
    assert "sources.data" in rendered and "类型声明" in rendered
    assert "CSV sources require" in str(caught.value)
    with pytest.raises(ValueError) as raw:
        Config.model_validate({"schema_version": 1, "paper": {"entry": 3}})
    assert "需要字符串" in error_message(raw.value).render("zh-CN")


def test_both_locales_preserve_core_result_and_localize_live_diagnostics(project, change_results):
    change_results(project)
    with language_context("en"):
        english = check_project(project)
    with language_context("zh-CN"):
        chinese = check_project(project)
    english.pop("created_at")
    chinese.pop("created_at")
    assert json_text(english) == json_text(chinese)
    translated_report = translated(chinese, "zh-CN")
    assert translated_report["coverage"] == english["coverage"]
    assert any("应根据指标" in item["message"] for item in translated_report["diagnostics"])


def test_concurrent_language_contexts_do_not_leak():
    async def operation(language):
        with language_context(language):
            await asyncio.sleep(0)
            return msg("diagnostic.NO_BINDINGS").render()

    async def run():
        return await asyncio.gather(operation("en"), operation("zh-CN"))

    english, chinese = asyncio.run(run())
    assert english.startswith("No confirmed")
    assert chinese.startswith("尚无")
    assert current_language() == "en"
