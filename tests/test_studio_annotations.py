"""The browser's accepted preview is local, current and explicitly confirmed."""

import base64
import io
from zipfile import ZipFile

import pytest

from paperdelta.demo import create_demo
from paperdelta.errors import PaperDeltaError
from paperdelta.storage import Project, parse_json, sha256
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


@pytest.mark.parametrize("kind", ["docx", "pdf"])
@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_reviewed_annotations_are_downloads_without_project_mutation(tmp_path, kind, language):
    create_demo(Project(tmp_path), "paper", document=kind)
    project = Project(tmp_path / "paper")
    session = StudioSession(project)
    review = call(session, "review", language=language)
    task = next(t for t in review["revision_tasks"] if t.get("occurrence") == "abstract_accuracy")
    assert task["annotatable"] and not task["patchable"]
    before = {
        p: project.read(p) for p, digest in review["report"]["input_hashes"].items() if digest
    }
    plan = call(session, "annotation-preview", {"occurrences": ["abstract_accuracy"]}, language)[
        "plan"
    ]
    acceptance = {"preview_id": plan["preview_id"], "attest": True}
    with pytest.raises(PaperDeltaError):
        call(session, "annotation-export", {**acceptance, "attest": False}, language)
    exported = call(session, "annotation-export", acceptance, language)
    with ZipFile(io.BytesIO(base64.b64decode(exported["base64"]))) as archive:
        manifest = parse_json(archive.read("review.json").decode())
        assert manifest["language"] == language
        assert "claim:main_comparison" in manifest["entries"][0]["note"]
        for path, digest in manifest["copies_sha256"].items():
            assert sha256(archive.read(path)) == digest
    assert all(project.read(p) == raw for p, raw in before.items())
    with pytest.raises(PaperDeltaError):
        call(session, "annotation-export", acceptance, language)


@pytest.mark.parametrize("change", ["refresh", "evidence", "language", "restart", "forged"])
def test_studio_rejects_obsolete_or_unseen_annotation_acceptance(tmp_path, change):
    create_demo(Project(tmp_path), "paper", document="docx")
    project = Project(tmp_path / "paper")
    session = StudioSession(project)
    original = project.read("paper.docx")
    plan = call(session, "annotation-preview", {"occurrences": ["table_accuracy"]})["plan"]
    language = "en"
    if change == "refresh":
        call(session, "refresh")
    elif change == "evidence":
        project.write("results/metrics.csv", project.read("results/metrics.csv") + b"\n")
    elif change == "language":
        language = "zh-CN"
    elif change == "restart":
        session = StudioSession(project)
    else:
        plan["preview_id"] = "sha256:" + "0" * 64
    with pytest.raises(PaperDeltaError):
        call(
            session,
            "annotation-export",
            {"preview_id": plan["preview_id"], "attest": True},
            language,
        )
    assert project.read("paper.docx") == original
