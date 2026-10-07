from copy import deepcopy

import pytest
from test_markdown import bind_accuracy, static_project

from paperdelta.analysis import check_project
from paperdelta.config import config_text, load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.manuscripts import change_manuscripts
from paperdelta.patches import apply_patch, create_patch, preview_patch, recover_transaction
from paperdelta.storage import Project, fingerprint, parse_json


@pytest.mark.parametrize("extension", ["md", "qmd"])
def test_text_patch_preserves_unicode_bom_crlf_code_and_metadata(tmp_path, extension):
    project, file = static_project(tmp_path, extension)
    raw = (
        '\ufeff---\r\ntitle: "Study 84.1"\r\n---\r\n\r\n'
        "# 结果\r\n\r\n模型的准确率为 **84.1%**。\r\n\r\n"
        '```python\r\nraise RuntimeError("84.1 must not execute")\r\n```\r\n'
    ).encode()
    project.write(file, raw)
    bind_accuracy(project, file)
    project.write("results.csv", b"model,score\nOurs,0.081\n")
    patch = create_patch(project, check_project(tmp_path), ["accuracy_text"])
    assert "8.1%" in preview_patch(project, patch)
    assert project.read(file) == raw
    result = apply_patch(project, patch)
    assert project.read(file) == raw.replace(b"**84.1%**", b"**8.1%**")
    assert result["report"]["occurrences"]["accuracy_text"]["status"] == "pass"
    # Unsupported code and metadata are still disclosed after a valid local edit.
    assert result["report"]["exit_code"] == 2
    recover_transaction(project, result["transaction_id"], write=True)
    assert project.read(file) == raw


@pytest.mark.parametrize("extension", ["md", "qmd"])
@pytest.mark.parametrize("mutation", ["data", "paper", "forged", "overlap"])
def test_text_patch_refuses_changed_forged_or_overlapping_edits(tmp_path, extension, mutation):
    project, file = static_project(tmp_path, extension, table=True)
    bind_accuracy(project, file)
    project.write("results.csv", b"model,score\nOurs,0.809\n")
    if mutation == "overlap":
        config, _ = load_config(project)
        config.occurrences["duplicate"] = config.occurrences["accuracy_text"].model_copy(deep=True)
        project.write("paperdelta.yaml", config_text(config).encode())
        before = project.read(file)
        with pytest.raises(PaperDeltaError) as error:
            create_patch(project, check_project(tmp_path))
        assert error.value.code == "PATCH_OVERLAP" and project.read(file) == before
        return
    patch = create_patch(project, check_project(tmp_path))
    if mutation in {"data", "paper"}:
        target = "results.csv" if mutation == "data" else file
        project.write(target, project.read(target) + b"\n")
    else:
        patch = deepcopy(patch)
        patch["changes"][0]["replacement"] = "99.9%"
        patch["patch_id"] = fingerprint({k: v for k, v in patch.items() if k != "patch_id"})
    before = project.read(file)
    with pytest.raises(PaperDeltaError) as error:
        apply_patch(project, patch)
    assert error.value.code == ("PATCH_NOT_DERIVED" if mutation == "forged" else "STALE_PATCH")
    assert project.read(file) == before


def test_interrupted_mixed_markdown_quarto_write_can_be_recovered(tmp_path, monkeypatch):
    project, file = static_project(tmp_path, "md")
    project.write("other.qmd", project.read(file))
    change_manuscripts(project, action="add", file="other.qmd", accept=True)
    bind_accuracy(project, file)
    bind_accuracy(project, "other.qmd", "other")
    project.write("results.csv", b"model,score\nOurs,0.809\n")
    patch = create_patch(project, check_project(tmp_path))
    before = {path: project.read(path) for path in (file, "other.qmd")}
    original = Project.write
    written = []

    def interrupted(self, path, raw, **options):
        if path in before:
            written.append(path)
            if len(written) == 2:
                raise OSError("Controlled second source write failure")
        return original(self, path, raw, **options)

    with monkeypatch.context() as context:
        context.setattr(Project, "write", interrupted)
        with pytest.raises(PaperDeltaError) as error:
            apply_patch(project, patch)
        assert error.value.code == "TRANSACTION_INTERRUPTED"
    manifest = next((tmp_path / ".paperdelta/transactions").glob("*/manifest.json"))
    record = parse_json(manifest.read_text("utf-8"))
    assert record["status"] == "interrupted"
    assert any(project.read(path) != raw for path, raw in before.items())
    recover_transaction(project, record["id"], write=True)
    assert all(project.read(path) == raw for path, raw in before.items())


@pytest.mark.parametrize("extension", ["md", "qmd"])
@pytest.mark.parametrize("state", ["false", "unknown"])
def test_text_patch_cannot_bypass_related_false_or_unknown_comparison(tmp_path, extension, state):
    from paperdelta.demo import create_demo

    create_demo(Project(tmp_path), "paper", document="markdown" if extension == "md" else "quarto")
    project = Project(tmp_path / "paper")
    if state == "unknown":
        file = "paper." + extension
        project.write(file, project.read(file).replace(b"outperforms", b"was compared with"))
    report = check_project(project.root)
    assert report["claims"]["main_comparison"]["status"] == (
        "mismatch" if state == "false" else "unknown"
    )
    before = project.read("paper." + extension)
    with pytest.raises(PaperDeltaError) as error:
        create_patch(project, report, ["abstract_accuracy"])
    assert error.value.code == "CLAIM_REVIEW_REQUIRED"
    assert project.read("paper." + extension) == before
