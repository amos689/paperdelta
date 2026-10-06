"""Only reviewed support metadata may leave the local project."""

import base64
import io
import json
from zipfile import ZipFile

import pytest

from paperdelta.cli import main
from paperdelta.diagnostic_bundle import bundle_bytes, preview_bundle
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import language_context, translated
from paperdelta.storage import Project
from paperdelta.studio import StudioSession


def test_private_content_is_excluded_even_from_doctor_failures(project, monkeypatch):
    secret = "PRIVATE manuscript 用户/secret.csv score=0.98765"
    monkeypatch.setenv("PAPERDELTA_PRIVATE_TEST", secret)
    monkeypatch.setattr(
        "paperdelta.diagnostic_bundle.diagnose",
        lambda *a: {
            "checks": [
                {"id": secret, "status": "error", "code": "FILE_UNAVAILABLE", "message": secret},
                {"id": secret, "status": secret, "code": secret, "action": secret},
            ],
            "project_check_exit_code": secret,
            "private": secret,
        },
    )
    preview = preview_bundle(Project(project))
    raw = bundle_bytes(Project(project), preview["preview_id"])
    with ZipFile(io.BytesIO(raw)) as archive:
        assert archive.namelist() == ["diagnostics.json"]
        content = archive.read("diagnostics.json").decode()
    assert "PRIVATE" not in content and "secret.csv" not in content
    assert str(project) not in content
    assert json.loads(content) == preview["files"]["diagnostics.json"]
    assert json.loads(content)["doctor"] == {
        "status_counts": {"error": 1, "other": 1},
        "diagnostic_codes": {"FILE_UNAVAILABLE": 1, "OTHER": 1},
        "project_check_exit_code": None,
    }


def test_changed_preview_is_rejected_and_does_not_write(project):
    root = Project(project)
    before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    preview = preview_bundle(root)
    assert bundle_bytes(root, preview["preview_id"]) == bundle_bytes(root, preview["preview_id"])
    assert before == {
        p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()
    }
    (project / "results/metrics.csv").unlink()
    with pytest.raises(PaperDeltaError) as failure:
        bundle_bytes(root, preview["preview_id"])
    assert failure.value.code == "DIAGNOSTIC_PREVIEW_CHANGED"


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_cli_preview_export_exact_payload_and_no_overwrite(project, capsys, language):
    args = ["--lang", language, "-C", str(project), "diagnostics"]
    assert main(args) == 0
    preview = json.loads(capsys.readouterr().out)
    with language_context(language):
        assert translated(preview_bundle(Project(project))["notice"]) == preview["notice"]
    assert main([*args, "--out", "diagnostic.zip"]) == 2
    capsys.readouterr()
    assert not (project / "diagnostic.zip").exists()
    export = [*args, "--out", "diagnostic.zip", "--preview-id", preview["preview_id"]]
    assert main(export) == 0
    capsys.readouterr()
    with ZipFile(project / "diagnostic.zip") as archive:
        assert json.loads(archive.read("diagnostics.json")) == preview["files"]["diagnostics.json"]
    assert main(export) == 2


def test_studio_preview_is_language_independent_and_export_matches(project):
    session = StudioSession(Project(project))

    def call(action, language, payload=None):
        return session.execute(
            {
                "action": action,
                "language": language,
                "revision": session.revision,
                "payload": payload or {},
            }
        )

    en = call("diagnostic-preview", "en")
    zh = call("diagnostic-preview", "zh-CN")
    assert en["files"] == zh["files"] and en["preview_id"] == zh["preview_id"]
    assert en["notice"] != zh["notice"]
    exported = call("diagnostic-export", "zh-CN", {"preview_id": en["preview_id"]})
    with ZipFile(io.BytesIO(base64.b64decode(exported["base64"]))) as archive:
        assert json.loads(archive.read("diagnostics.json")) == en["files"]["diagnostics.json"]
