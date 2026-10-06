import io
from contextlib import nullcontext
from copy import deepcopy
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import language_context
from paperdelta.review_bundle import bundle_bytes, inspect_bundle, preview_bundle, replay_bundle
from paperdelta.snapshots import create_snapshot
from paperdelta.storage import Project, fingerprint, json_text, parse_json


def full_preview(store):
    initial = preview_bundle(store, {"reports": ["html", "json", "sarif"], "inputs": []})
    return preview_bundle(
        store, {"reports": ["html", "json", "sarif"], "inputs": sorted(initial["required_inputs"])}
    )


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_selected_full_review_replays_exact_scope_without_executing_project_code(project, language):
    store = Project(project)
    store.write("sitecustomize.py", b"raise RuntimeError('Must never execute paper code')\n")
    with language_context(language):
        preview = full_preview(store)
        before = {name: store.read(name) for name in preview["required_inputs"]}
        raw = bundle_bytes(store, preview)
        assert bundle_bytes(store, preview) == raw
    inspected = inspect_bundle(raw)
    assert inspected["plan"] == preview
    assert not any("sitecustomize" in name for name in preview["files"])
    replay = replay_bundle(store, raw, "build/isolated-replay")
    assert replay["same_result"] and replay["status"] == "reproduced"
    assert not replay["executed_project_code"] and replay["exit_code"] == 0
    assert replay["scope"] == preview["scope"]
    assert all(store.read(name) == value for name, value in before.items())
    with pytest.raises(PaperDeltaError) as error:
        replay_bundle(store, raw, "build/isolated-replay")
    assert error.value.code == "REVIEW_BUNDLE_EXISTS"


def test_partial_review_is_viewable_but_cannot_claim_replay_and_stale_preview_rejected(
    project, change_results
):
    store = Project(project)
    preview = preview_bundle(store, {"reports": ["html"], "inputs": []})
    assert not preview["replayable"] and preview["missing_inputs"]
    raw = bundle_bytes(store, preview)
    assert inspect_bundle(raw)["status"] == "verified_bytes"
    with pytest.raises(PaperDeltaError) as error:
        replay_bundle(store, raw, "build/missing-inputs")
    assert error.value.code == "REVIEW_BUNDLE_INCOMPLETE"
    assert not (project / "build/missing-inputs").exists()
    change_results(project)
    with pytest.raises(PaperDeltaError) as error:
        bundle_bytes(store, preview)
    assert error.value.code == "REVIEW_BUNDLE_CHANGED"


@pytest.mark.parametrize(
    "attack", ["extra", "traversal", "symlink", "duplicate", "data", "false_preview"]
)
def test_archive_inspection_refuses_unlisted_paths_and_corrupt_or_misleading_contents(
    project, attack
):
    raw = bundle_bytes(Project(project), full_preview(Project(project)))
    with ZipFile(io.BytesIO(raw)) as original:
        entries = {name: original.read(name) for name in original.namelist()}
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as changed:
        if attack == "false_preview":
            plan = parse_json(entries["review-bundle.json"].decode())
            plan["files"]["review/report.json"]["preview"] = "Everything is fine"
            plan["preview_id"] = fingerprint({k: v for k, v in plan.items() if k != "preview_id"})
            entries["review-bundle.json"] = json_text(plan).encode()
        for name, data in entries.items():
            if attack == "data" and name == "review/report.json":
                data += b"changed"
            changed.writestr(name, data)
        if attack in {"extra", "traversal", "duplicate"}:
            name = {
                "extra": "hidden.py",
                "traversal": "../escape.txt",
                "duplicate": "review/report.json",
            }[attack]
            with pytest.warns(UserWarning) if attack == "duplicate" else nullcontext():
                changed.writestr(name, b"extra")
        if attack == "symlink":
            entry = ZipInfo("project/link")
            entry.external_attr = 0o120777 << 16
            changed.writestr(entry, b"../../outside")
    with pytest.raises(PaperDeltaError):
        inspect_bundle(output.getvalue())
    assert not (project.parent / "escape.txt").exists()


def test_a_reviewed_plan_cannot_silently_add_a_file_outside_checked_inputs(project):
    store = Project(project)
    store.write("private.txt", b"not part of the accepted checks")
    with pytest.raises(PaperDeltaError) as error:
        preview_bundle(store, {"reports": ["json"], "inputs": ["private.txt"]})
    assert error.value.code == "REVIEW_BUNDLE_SELECTION"
    plan = full_preview(store)
    changed = deepcopy(plan)
    changed["selection"]["inputs"].append("private.txt")
    with pytest.raises(PaperDeltaError):
        bundle_bytes(store, changed)


def test_replay_reports_changed_declared_scope_even_when_archive_hashes_are_valid(project):
    store = Project(project)
    raw = bundle_bytes(store, full_preview(store))
    with ZipFile(io.BytesIO(raw)) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    plan = parse_json(files["review-bundle.json"].decode())
    plan["scope"]["bindings"]["occurrences"] = []
    plan["preview_id"] = fingerprint({k: v for k, v in plan.items() if k != "preview_id"})
    files["review-bundle.json"] = json_text(plan).encode()
    output = io.BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    assert inspect_bundle(output.getvalue())["status"] == "verified_bytes"
    result = replay_bundle(store, output.getvalue(), "build/forged-scope")
    assert result["status"] == "different_result" and result["exit_code"] == 2
    assert result["scope"]["bindings"]["occurrences"]
    assert not result["declared_scope"]["bindings"]["occurrences"]


def test_baseline_changing_during_preview_cannot_describe_different_input_bytes(project):
    snapshot = create_snapshot(Project(project), "before", check_project(project))

    class ChangingBaseline(Project):
        def read(self, path, limit=32 * 1024 * 1024):
            raw = super().read(path, limit)
            if path == snapshot:
                self.write(path, raw + b"\n")
            return raw

    with pytest.raises(PaperDeltaError) as error:
        preview_bundle(
            ChangingBaseline(project), {"reports": ["json"], "inputs": []}, baseline="before"
        )
    assert error.value.code == "REVIEW_BUNDLE_CHANGED"


@pytest.mark.parametrize("name", [".", ".git/config", "AUX.txt", "trailing. ", "a?b", "x\x01y"])
def test_portable_review_refuses_nonportable_names_and_git_metadata(name):
    from paperdelta.review_bundle import _name

    with pytest.raises(PaperDeltaError) as error:
        _name(name)
    assert error.value.code == "REVIEW_BUNDLE_PATH"
