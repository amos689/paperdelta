import pytest

from paperdelta.demo import create_demo
from paperdelta.errors import PaperDeltaError
from paperdelta.storage import Project
from paperdelta.studio import StudioSession


def call(session, action, payload=None, language="en"):
    return session.execute(
        {
            "action": action,
            "payload": payload or {},
            "revision": session.revision,
            "language": language,
        }
    )


@pytest.mark.parametrize("document", ["latex", "markdown", "quarto"])
@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_joined_revision_preview_explicit_apply_and_recovery(tmp_path, document, language):
    create_demo(Project(tmp_path), "paper", scenario="safe-update", document=document)
    project = Project(tmp_path / "paper")
    session = StudioSession(project)
    detail = call(session, "review", language=language)
    tasks = {item["subject"]: item for item in detail["revision_tasks"]}
    task = tasks["occurrence:table_accuracy"]
    assert task["patchable"] and task["context"] and task["metrics"]
    path = detail["report"]["occurrences"]["table_accuracy"]["location"]["file"]
    original = project.read(path)
    plan = call(session, "patch-preview", {"occurrences": ["table_accuracy"]}, language)
    assert "84.5" in plan["diff"] and project.read(path) == original
    with pytest.raises(PaperDeltaError):
        call(session, "patch-apply", {"preview_id": plan["preview_id"], "attest": False}, language)
    assert project.read(path) == original
    result = call(
        session, "patch-apply", {"preview_id": plan["preview_id"], "attest": True}, language
    )
    assert project.read(path) != original
    assert call(session, "review")["report"]["occurrences"]["table_accuracy"]["status"] == "pass"
    history = call(session, "patch-transactions")["transactions"]
    assert history[0]["id"] == result["transaction_id"] and history[0]["status"] == "applied"
    restored = StudioSession(project)
    preview = call(
        restored, "patch-recover-preview", {"transaction_id": result["transaction_id"]}, language
    )
    written = project.read(path)
    assert "+" in preview["diff"] and written != original
    with pytest.raises(PaperDeltaError):
        call(
            restored,
            "patch-recover",
            {"preview_id": preview["preview_id"], "attest": False},
            language,
        )
    assert project.read(path) == written
    call(restored, "patch-recover", {"preview_id": preview["preview_id"], "attest": True}, language)
    assert project.read(path) == original


def test_joined_task_marks_claim_blocked_changes_unpatchable(tmp_path):
    create_demo(Project(tmp_path), "paper", document="markdown")
    project = Project(tmp_path / "paper")
    session = StudioSession(project)
    tasks = call(session, "review")["revision_tasks"]
    item = next(item for item in tasks if item["subject"] == "occurrence:abstract_accuracy")
    assert not item["patchable"] and item["patch_blocked_by"] == ["claim:main_comparison"]
    with pytest.raises(PaperDeltaError) as error:
        call(session, "patch-preview", {"occurrences": ["abstract_accuracy"]})
    assert error.value.code == "CLAIM_REVIEW_REQUIRED"


@pytest.mark.parametrize("document", ["docx", "pdf"])
def test_joined_native_tasks_remain_read_only(tmp_path, document):
    create_demo(Project(tmp_path), "paper", scenario="safe-update", document=document)
    project = Project(tmp_path / "paper")
    session = StudioSession(project)
    detail = call(session, "review")
    item = next(t for t in detail["revision_tasks"] if t["subject"] == "occurrence:table_accuracy")
    assert not item["patchable"] and item["context"] and item["patch_reason"]
    path = detail["report"]["occurrences"]["table_accuracy"]["location"]["file"]
    original = project.read(path)
    with pytest.raises(PaperDeltaError) as error:
        call(session, "patch-preview", {"occurrences": ["table_accuracy"]})
    assert error.value.code == "DOCUMENT_READ_ONLY"
    assert project.read(path) == original


def test_session_refresh_invalidates_reviewed_patch_and_recovery(tmp_path):
    create_demo(Project(tmp_path), "paper", scenario="safe-update", document="markdown")
    project = Project(tmp_path / "paper")
    session = StudioSession(project)
    preview = call(session, "patch-preview", {"occurrences": ["table_accuracy"]})
    call(session, "refresh")
    with pytest.raises(PaperDeltaError) as error:
        call(session, "patch-apply", {"preview_id": preview["preview_id"], "attest": True})
    assert error.value.code == "STALE_PATCH"
    preview = call(session, "patch-preview", {"occurrences": ["table_accuracy"]})
    result = call(session, "patch-apply", {"preview_id": preview["preview_id"], "attest": True})
    recovery = call(session, "patch-recover-preview", {"transaction_id": result["transaction_id"]})
    written = project.read("paper.md")
    call(session, "refresh")
    with pytest.raises(PaperDeltaError) as error:
        call(session, "patch-recover", {"preview_id": recovery["preview_id"], "attest": True})
    assert error.value.code == "STALE_PATCH"
    assert project.read("paper.md") == written


def test_studio_refuses_unseen_and_stale_patch_previews(tmp_path):
    create_demo(Project(tmp_path), "paper", scenario="safe-update", document="quarto")
    project = Project(tmp_path / "paper")
    session = StudioSession(project)
    with pytest.raises(PaperDeltaError) as error:
        call(session, "patch-apply", {"preview_id": "sha256:" + "0" * 64, "attest": True})
    assert error.value.code == "STALE_PATCH"
    preview = call(session, "patch-preview", {"occurrences": ["table_accuracy"]})
    original = project.read("paper.qmd")
    project.write("results/metrics.csv", project.read("results/metrics.csv") + b"\n")
    with pytest.raises(PaperDeltaError):
        call(session, "patch-apply", {"preview_id": preview["preview_id"], "attest": True})
    assert project.read("paper.qmd") == original


def test_interrupted_source_write_can_be_recovered_in_stale_studio_session(tmp_path, monkeypatch):
    create_demo(Project(tmp_path), "paper", scenario="safe-update", document="markdown")
    project = Project(tmp_path / "paper")
    session = StudioSession(project)
    preview = call(session, "patch-preview", {"occurrences": ["table_accuracy"]})
    original = project.read("paper.md")
    original_write = Project.write

    def fail_after_write(self, path, raw, **kwargs):
        result = original_write(self, path, raw, **kwargs)
        if path == "paper.md":
            raise OSError("Controlled failure after source write")
        return result

    with monkeypatch.context() as context:
        context.setattr(Project, "write", fail_after_write)
        with pytest.raises(PaperDeltaError) as error:
            call(session, "patch-apply", {"preview_id": preview["preview_id"], "attest": True})
        assert error.value.code == "TRANSACTION_INTERRUPTED"
    assert project.read("paper.md") != original
    transaction = call(session, "patch-transactions")["transactions"][0]
    assert transaction["status"] == "interrupted"
    recovery = call(session, "patch-recover-preview", {"transaction_id": transaction["id"]})
    call(session, "patch-recover", {"preview_id": recovery["preview_id"], "attest": True})
    assert project.read("paper.md") == original


@pytest.mark.parametrize("document", ["markdown", "quarto"])
@pytest.mark.parametrize("changed", ["manuscript", "manifest"])
def test_recovery_revalidates_the_reviewed_diff_without_losing_author_edits(
    tmp_path, document, changed
):
    create_demo(Project(tmp_path), "paper", scenario="safe-update", document=document)
    project = Project(tmp_path / "paper")
    session = StudioSession(project)
    preview = call(session, "patch-preview", {"occurrences": ["table_accuracy"]})
    applied = call(session, "patch-apply", {"preview_id": preview["preview_id"], "attest": True})
    recovery = call(session, "patch-recover-preview", {"transaction_id": applied["transaction_id"]})
    source = "paper." + ("md" if document == "markdown" else "qmd")
    path = (
        source
        if changed == "manuscript"
        else f".paperdelta/transactions/{applied['transaction_id']}/manifest.json"
    )
    project.write(path, project.read(path) + b"\n")
    before = project.read(source)
    with pytest.raises(PaperDeltaError) as error:
        call(session, "patch-recover", {"preview_id": recovery["preview_id"], "attest": True})
    assert error.value.code == ("RECOVERY_CONFLICT" if changed == "manuscript" else "STALE_PATCH")
    assert project.read(source) == before
