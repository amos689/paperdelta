import copy
import json
import subprocess
import sys

import pytest

from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.patches import apply_patch, create_patch, preview_patch, recover_transaction
from paperdelta.storage import Project, fingerprint, json_text


@pytest.fixture
def patch(project, change_results):
    change_results(project, new=("0.843", "0.845", "0.847"))
    return create_patch(Project(project), check_project(project))


def tex_bytes(project):
    return {p.relative_to(project).as_posix(): p.read_bytes() for p in project.rglob("*.tex")}


def test_preview_is_read_only_and_multifile_application_can_be_recovered(project, patch):
    store = Project(project)
    before = tex_bytes(project)
    diff = preview_patch(store, patch)
    assert "84.5" in diff and "3.5" in diff
    assert tex_bytes(project) == before
    assert not (project / ".paperdelta").exists()
    result = apply_patch(store, patch)
    assert result["report"]["exit_code"] == 0
    assert len([name for name, raw in tex_bytes(project).items() if raw != before[name]]) == 3
    written = tex_bytes(project)
    assert recover_transaction(store, result["transaction_id"])["status"] == "preview"
    assert tex_bytes(project) == written
    assert recover_transaction(store, result["transaction_id"], write=True)["status"] == "reverted"
    assert tex_bytes(project) == before


@pytest.mark.parametrize("path", ["paper/abstract.tex", "results/metrics.csv", "paperdelta.yaml"])
def test_old_patch_refuses_any_changed_precondition(project, patch, path):
    target = project / path
    target.write_bytes(target.read_bytes() + b"\n")
    before = tex_bytes(project)
    with pytest.raises(PaperDeltaError, match="changed") as error:
        apply_patch(Project(project), patch)
    assert error.value.code == "STALE_PATCH"
    assert tex_bytes(project) == before


def test_tampered_patch_is_rederived_even_with_recomputed_hash(project, patch):
    patch["changes"][0]["replacement"] = "99.9"
    patch["patch_id"] = fingerprint({k: v for k, v in patch.items() if k != "patch_id"})
    with pytest.raises(PaperDeltaError) as error:
        apply_patch(Project(project), patch)
    assert error.value.code == "PATCH_NOT_DERIVED"


def test_report_suggestions_are_not_authority(project, change_results):
    change_results(project, new=("0.843", "0.845", "0.847"))
    report = check_project(project)
    report["occurrences"]["abstract_accuracy"]["suggestion"]["replacement"] = "99.9"
    patch = create_patch(Project(project), report, ["abstract_accuracy"])
    assert patch["changes"][0]["replacement"] == r"84.5\%"


def test_false_claim_prevents_partial_numeric_fix(project, change_results):
    change_results(project)
    with pytest.raises(PaperDeltaError) as error:
        create_patch(Project(project), check_project(project), ["abstract_accuracy"])
    assert error.value.code == "CLAIM_REVIEW_REQUIRED"


def test_overlapping_bindings_are_rejected_before_writing(project, change_results):
    import yaml

    path = project / "paperdelta.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["occurrences"]["duplicate"] = config["occurrences"]["abstract_accuracy"]
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    change_results(project, new=("0.843", "0.845", "0.847"))
    before = tex_bytes(project)
    with pytest.raises(PaperDeltaError) as error:
        create_patch(Project(project), check_project(project))
    assert error.value.code == "PATCH_OVERLAP"
    assert tex_bytes(project) == before


def test_partial_write_is_journaled_and_recoverable(project, patch, monkeypatch):
    before = tex_bytes(project)
    original = Project.write
    count = 0

    def fail_second_tex_write(self, path, raw, **kwargs):
        nonlocal count
        if path.endswith(".tex"):
            count += 1
            if count == 2:
                raise OSError("injected disk failure")
        return original(self, path, raw, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(Project, "write", fail_second_tex_write)
        with pytest.raises(PaperDeltaError) as error:
            apply_patch(Project(project), patch)
    assert error.value.code == "TRANSACTION_INTERRUPTED"
    manifests = list((project / ".paperdelta/transactions").glob("*/manifest.json"))
    assert len(manifests) == 1
    record = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert record["status"] == "interrupted" and tex_bytes(project) != before
    with pytest.raises(PaperDeltaError) as blocked:
        apply_patch(Project(project), patch)
    assert blocked.value.code == "RECOVERY_REQUIRED"
    recover_transaction(Project(project), record["id"], write=True)
    assert tex_bytes(project) == before


def test_recovery_refuses_to_overwrite_later_author_edits(project, patch):
    transaction = apply_patch(Project(project), patch)["transaction_id"]
    path = project / "paper/abstract.tex"
    path.write_bytes(path.read_bytes() + b"Author's later note.\n")
    before = tex_bytes(project)
    with pytest.raises(PaperDeltaError) as error:
        recover_transaction(Project(project), transaction, write=True)
    assert error.value.code == "RECOVERY_CONFLICT"
    assert tex_bytes(project) == before


def test_utf8_bom_crlf_and_unrelated_bytes_survive_numeric_fix(project, change_results):
    path = project / "paper/abstract.tex"
    raw = b"\xef\xbb\xbf" + "中文注释\r\n".encode() + path.read_bytes().replace(b"\n", b"\r\n")
    path.write_bytes(raw)
    change_results(project, new=("0.843", "0.845", "0.847"))
    patch = create_patch(Project(project), check_project(project), ["abstract_accuracy"])
    apply_patch(Project(project), patch)
    assert path.read_bytes() == raw.replace(b"84.1", b"84.5")


def test_cli_apply_defaults_to_preview(project, patch):
    (project / "patch.json").write_text(json_text(patch), encoding="utf-8")
    before = tex_bytes(project)
    proc = subprocess.run(
        [sys.executable, "-m", "paperdelta", "-C", str(project), "apply", "patch.json"],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert proc.returncode == 0 and "+++ b/" in proc.stdout
    assert tex_bytes(project) == before


@pytest.mark.parametrize("value", [{}, [], {"transaction_schema_version": True}])
def test_invalid_transaction_is_a_diagnostic(project, value):
    store = Project(project)
    name = "1" * 32
    store.write(f".paperdelta/transactions/{name}/manifest.json", json_text(value).encode())
    with pytest.raises(PaperDeltaError) as error:
        recover_transaction(store, name, write=True)
    assert error.value.code == "TRANSACTION_SCHEMA"


def test_same_display_data_change_during_write_is_not_silent_success(project, patch, monkeypatch):
    original = Project.write
    changed = False

    def change_evidence(self, path, raw, **kwargs):
        nonlocal changed
        result = original(self, path, raw, **kwargs)
        if path.endswith(".tex") and not changed:
            changed = True
            data = project / "results/metrics.csv"
            data.write_bytes(data.read_bytes().replace(b"0.843", b"0.84301"))
        return result

    monkeypatch.setattr(Project, "write", change_evidence)
    with pytest.raises(PaperDeltaError) as error:
        apply_patch(Project(project), patch)
    assert error.value.code == "TRANSACTION_INTERRUPTED"
    assert "Inputs changed" in str(error.value)


def test_old_report_is_rejected(project, patch):
    report = check_project(project)
    (project / "paper/main.tex").write_bytes((project / "paper/main.tex").read_bytes() + b"\n")
    with pytest.raises(PaperDeltaError) as error:
        create_patch(Project(project), copy.deepcopy(report))
    assert error.value.code == "STALE_REPORT"
