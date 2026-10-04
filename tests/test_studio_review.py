"""Second-experiment workflows, accepted declarations and restart recovery."""

import io
from copy import deepcopy

import pytest
from test_studio import call, stage_locations, stage_metric
from test_studio import studio_project as studio_project

from paperdelta import builder
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.onboarding import init_project
from paperdelta.storage import Project, fingerprint, json_text, parse_json
from paperdelta.studio import StudioSession
from paperdelta.studio_recovery import MAX_RECOVERY_BYTES, migrate_draft, rebuild_draft


def accept_all(session):
    preview = call(session, "preview")["state"]["preview"]
    return call(
        session,
        "accept",
        {
            "proposal_id": preview["proposal_id"],
            "selected": [item["binding"] for item in preview["items"]],
        },
    )["state"]


def test_durable_draft_restores_after_server_restart_without_acceptance(studio_project):
    project, path = studio_project
    first = StudioSession(project)
    stage_metric(first, path)
    stage_locations(first)
    original = project.read("paperdelta.yaml")
    saved = first.draft
    second = StudioSession(project)
    state = call(second, "state")["state"]
    assert state["recovery"]["available"] and not state["additions"]["occurrences"]
    state = call(second, "recovery-restore")["state"]
    assert state["additions"] == first.state()["additions"]
    assert second.draft == saved and state["preview"] is None
    assert project.read("paperdelta.yaml") == original
    accepted = accept_all(second)
    assert accepted["coverage"]["pass"] == 2 and not accepted["recovery"]["available"]


def test_saved_draft_conflicts_preserve_downloadable_work(studio_project):
    project, path = studio_project
    first = StudioSession(project)
    stage_metric(first, path)
    stage_locations(first)
    old = first.draft
    project.write("results.csv", project.read("results.csv").replace(b"0.840", b"0.800"))
    second = StudioSession(project)
    state = call(second, "state")["state"]
    assert state["recovery"]["changed_paths"] == ["results.csv"]
    with pytest.raises(PaperDeltaError) as error:
        call(second, "recovery-restore")
    assert error.value.code == "STALE_DRAFT"
    assert parse_json(call(second, "recovery-export")["json"]) == old
    assert parse_json(call(first, "draft-export")["json"]) == old
    assert not load_config(project)[0].occurrences


def test_multiple_servers_cannot_silently_replace_saved_drafts(studio_project):
    project, path = studio_project
    first = StudioSession(project)
    call(first, "initialize", {"paper": path, "data": ["results.csv"]})
    second = StudioSession(project)
    fresh = builder.add_source(
        project,
        first.draft,
        name="a",
        path="results.csv",
        format="csv",
        columns={"model": "string", "seed": "integer", "score": "decimal"},
        primary_key=["model", "seed"],
    )
    first._stage(fresh)
    saved = project.read(first.recovery.path)
    with pytest.raises(PaperDeltaError) as error:
        second._stage(fresh)
    assert error.value.code == "STUDIO_RECOVERY_CONFLICT"
    assert project.read(first.recovery.path) == saved
    assert not second.draft["additions"]["sources"]


@pytest.mark.parametrize("previous", ["0.6.0", "0.7.0", "0.7.1"])
def test_patch_release_migration_verifies_original_hashes(project, monkeypatch, previous):
    store = Project(project)
    monkeypatch.setattr(builder, "__version__", previous)
    draft = builder.start_draft(store)
    old = deepcopy(draft)
    monkeypatch.setattr(builder, "__version__", "0.7.2")
    monkeypatch.setattr("paperdelta.studio_recovery.__version__", "0.7.2")
    migrated = migrate_draft(store, old)
    assert migrated["tool_version"] == "0.7.2"
    assert migrated["input_hashes"] == old["input_hashes"]
    assert migrated["additions"] == old["additions"]
    assert old == draft
    tampered = deepcopy(old)
    tampered["tool_version"] = "0.5.0"
    tampered["draft_id"] = fingerprint({k: v for k, v in tampered.items() if k != "draft_id"})
    with pytest.raises(PaperDeltaError):
        migrate_draft(store, tampered)


@pytest.mark.parametrize("version", ["0.7.999", "0.7.invalid", "0.6.-1", "0.5.0", "1.0.0"])
def test_restore_and_rebuild_reject_unknown_or_future_versions(project, monkeypatch, version):
    store = Project(project)
    draft = builder.start_draft(store)
    draft["tool_version"] = version
    draft["draft_id"] = fingerprint({key: item for key, item in draft.items() if key != "draft_id"})
    monkeypatch.setattr("paperdelta.studio_recovery.__version__", "0.7.2")
    for operation in (migrate_draft, lambda p, d: rebuild_draft(p, d, ["metrics:ours"])):
        with pytest.raises(PaperDeltaError) as error:
            operation(store, draft)
        assert error.value.code == "DRAFT_IDENTITY"


def test_unreadable_recovery_does_not_prevent_inspection_or_allow_overwrite(project):
    store = Project(project)
    session = StudioSession(store)
    corrupt = b"x" * (MAX_RECOVERY_BYTES + 1)
    store.write(session.recovery.path, corrupt)
    restarted = StudioSession(store)
    state = call(restarted, "state")["state"]
    assert state["recovery"]["error"] == "FILE_LIMIT"
    assert state["initialized"] and not state["stale"]
    with pytest.raises(PaperDeltaError):
        restarted.recovery.save(None)
    assert store.read(session.recovery.path) == corrupt


def test_poll_keeps_draft_conflict_visible_even_after_event_is_consumed(studio_project):
    project, path = studio_project
    session = StudioSession(project)
    stage_metric(session, path)
    original_draft = deepcopy(session.draft)
    original_config = project.read("paperdelta.yaml")
    project.write("results.csv", project.read("results.csv").replace(b"0.840", b"0.800"))
    for _ in range(3):
        assert call(session, "poll")["stale"] is True
    assert session.draft == original_draft
    assert project.read("paperdelta.yaml") == original_config


def test_native_second_experiment_maintenance_and_snapshot(studio_project, monkeypatch):
    project, path = studio_project
    session = StudioSession(project)
    stage_metric(session, path)
    stage_locations(session)
    accept_all(session)
    original_paper = project.read(path)
    snapshot = call(session, "snapshot-create", {"name": "submitted-v1"})["snapshot"]
    baseline_bytes = project.read(snapshot["path"])
    call(session, "baseline", {"name": "submitted-v1"})
    clock = [10.0]
    monkeypatch.setattr("paperdelta.watch.time.monotonic", lambda: clock[0])
    project.write("results.csv", project.read("results.csv").replace(b"0.840", b"0.800"))
    assert call(session, "poll")["review"]["state"] == "pending"
    assert call(session, "review")["report"]["exit_code"] == 2
    clock[0] += 1
    assert call(session, "poll")["review"]["state"] == "current"
    detail = call(session, "review")
    assert detail["report"]["coverage"]["mismatch"] == 2
    assert not call(session, "state")["state"]["stale"]
    definition = load_config(project)[0].occurrences["abstract"].model_dump()
    definition["display"]["places"] = 2
    preview = call(
        session,
        "maintenance-preview",
        {
            "edits": [
                {
                    "group": "occurrences",
                    "name": "abstract",
                    "operation": "replace",
                    "definition_json": json_text(definition),
                    "rationale": "Show two decimal places.",
                }
            ]
        },
    )["state"]["maintenance"]
    original_config = project.read("paperdelta.yaml")
    result = call(session, "maintenance-accept", {"proposal_id": preview["proposal_id"]})["state"]
    assert project.read(result["receipt"]["backup"]) == original_config
    assert load_config(project)[0].occurrences["abstract"].display.places == 2
    assert project.read(snapshot["path"]) == baseline_bytes
    assert project.read(path) == original_paper
    with pytest.raises(PaperDeltaError):
        call(session, "snapshot-create", {"name": "submitted-v1"})


def test_partial_save_keeps_review_unknown_until_complete_inputs_return(
    studio_project, monkeypatch
):
    project, path = studio_project
    session = StudioSession(project)
    stage_metric(session, path)
    stage_locations(session)
    accept_all(session)
    original = project.read(path)
    clock = [10.0]
    monkeypatch.setattr("paperdelta.watch.time.monotonic", lambda: clock[0])
    project.write(path, original[:12])
    assert call(session, "poll")["review"]["state"] == "pending"
    clock[0] += 1
    assert call(session, "poll")["review"]["exit_code"] == 2
    project.write(path, original)
    assert call(session, "poll")["review"]["state"] == "pending"
    clock[0] += 1
    result = call(session, "poll")
    assert result["review"]["state"] == "current" and result["review"]["exit_code"] == 0
    assert call(session, "state")["state"]["coverage"]["pass"] == 2


def test_review_context_never_uses_unchecked_new_manuscript_bytes(project):
    store = Project(project)
    session = StudioSession(store)
    first = call(session, "review")["positions"]["occurrences:abstract_accuracy"]
    assert "84.1" in first["context"] and ":" in first["label"]
    store.write("paper/abstract.tex", b"UNREVIEWED_TEXT: 12.3\\%.\n")
    previous = call(session, "review")["positions"]["occurrences:abstract_accuracy"]
    assert "UNREVIEWED_TEXT" not in previous["context"]


def test_reviewed_false_claim_still_fails_and_has_explicit_state(project, change_results):
    change_results(project)
    store = Project(project)
    session = StudioSession(store)
    report = call(session, "review")["report"]
    state = report["claims"]["main_comparison"]["state_fingerprint"]
    result = call(
        session,
        "claim-review",
        {
            "claim": "main_comparison",
            "state": state,
            "reviewer": "author",
            "note": "Checked the records.",
            "attest": True,
        },
    )
    assert result["report"]["claims"]["main_comparison"]["review"] == "reviewed"
    assert result["report"]["claims"]["main_comparison"]["status"] == "mismatch"
    assert store.path(result["receipt"]["path"]).exists()
    with pytest.raises(PaperDeltaError):
        call(
            session,
            "claim-review",
            {
                "claim": "main_comparison",
                "state": "old",
                "reviewer": "author",
                "note": "Must not write.",
                "attest": True,
            },
        )


def test_search_reaches_beyond_former_5000_limit(tmp_path):
    project = Project(tmp_path)
    project.write("paper.tex", b"Repeated measurement 1.0.\n" * 5100 + b"Lastmarker 2.5.\n")
    project.write("data.csv", b"model,value\na,2.5\n")
    init_project(project, paper="paper.tex", data=["data.csv"])
    session = StudioSession(project)
    state = call(session, "state")["state"]
    assert len(state["candidates"]) == 30 and state["candidate_total"] == 5101
    found = call(session, "candidates", {"query": "lastMARKER"})
    target = next(item for item in found["items"] if item["text"] == "2.5")
    next_page = call(session, "candidates", {"offset": 5100})
    assert next_page["items"][0]["candidate_id"] == target["candidate_id"]


def test_cached_state_is_not_mutable_authority_and_stale_inputs_fail(studio_project):
    project, path = studio_project
    session = StudioSession(project)
    stage_metric(session, path)
    first = call(session, "state")["state"]
    first["metrics"]["ours"]["result"]["value"] = "123"
    assert call(session, "state")["state"]["metrics"]["ours"]["result"]["value"] == "0.841"
    project.write("results.csv", b"unavailable,partial\n")
    assert call(session, "state")["state"]["stale"]
    with pytest.raises(PaperDeltaError):
        call(session, "candidates", {})


def test_native_visual_repair_preserves_declared_metric(studio_project):
    project, path = studio_project
    session = StudioSession(project)
    stage_metric(session, path)
    stage_locations(session)
    accept_all(session)
    call(session, "snapshot-create", {"name": "before"})
    call(session, "baseline", {"name": "before"})
    if path.endswith("tex"):
        raw = project.read(path).replace(
            b"Abstract score: 84.1\\%.", b"Revised measurement =84.1\\%; updated context."
        )
    elif path.endswith("docx"):
        from docx import Document

        document = Document(io.BytesIO(project.read(path)))
        document.paragraphs[0].text = "Revised measurement =84.1%; updated context."
        stream = io.BytesIO()
        document.save(stream)
        raw = stream.getvalue()
    else:
        from reportlab.pdfgen.canvas import Canvas

        stream = io.BytesIO()
        canvas = Canvas(stream, invariant=True)
        canvas.drawString(60, 740, "Revised measurement =84.1%; updated context.")
        canvas.drawString(60, 700, "Second result: 84.1%.")
        canvas.save()
        raw = stream.getvalue()
    project.write(path, raw)
    call(session, "refresh")
    scan = call(session, "repair-scan")
    assert "occurrences:abstract" in {item["binding"] for item in scan["broken"]}
    candidates = call(session, "candidates", {"query": "Revised"})["items"]
    assert candidates
    preview = call(
        session,
        "repair-preview",
        {
            "selections": [
                {
                    "binding": "occurrences:abstract",
                    "candidate_id": candidates[0]["candidate_id"],
                    "rationale": "Reworded the same declared result.",
                }
            ]
        },
    )["state"]["repair"]
    state = call(
        session,
        "repair-accept",
        {"repair_id": preview["repair_id"], "selected": ["occurrences:abstract"]},
    )["state"]
    assert state["coverage"]["pass"] == 2
    assert load_config(project)[0].occurrences["abstract"].metric == "ours"
    assert project.read(path) == raw


def test_rebuild_changed_evidence_rechecks_selected_draft_and_archives_original(studio_project):
    project, path = studio_project
    session = StudioSession(project)
    stage_metric(session, path)
    stage_locations(session)
    old = session.draft
    original_config = project.read("paperdelta.yaml")
    project.write("results.csv", project.read("results.csv").replace(b"0.840", b"0.800"))
    items = call(session, "recovery-items")
    state = call(
        session,
        "recovery-preview",
        {
            "record_id": items["record_id"],
            "selected": ["occurrences:abstract"],
        },
    )["state"]
    assert state["rebuild"]["preview"]["metrics"]["ours"]["value"] == "0.821"
    assert state["rebuild"]["preview"]["occurrences"]["abstract"]["status"] == "mismatch"
    assert project.read("paperdelta.yaml") == original_config
    state = call(
        session,
        "recovery-rebuild",
        {
            "proposal_id": state["rebuild"]["proposal_id"],
        },
    )["state"]
    assert not state["stale"] and state["preview"] is None
    assert set(state["additions"]["occurrences"]) == {"abstract"}
    assert project.read("paperdelta.yaml") == original_config
    archived = parse_json(project.text(state["recovery_archive"])[0])
    assert archived["draft"] == old
    assert session.draft["input_hashes"] != old["input_hashes"]


def test_field_editor_preserves_unedited_exact_values_and_checks_preview(project):
    session = StudioSession(Project(project))
    declaration = next(
        item
        for item in call(session, "declarations")["items"]
        if item["id"] == "occurrences:abstract_accuracy"
    )
    assert any(field["path"] == ["display", "places"] for field in declaration["fields"])
    preview = call(
        session,
        "maintenance-fields",
        {
            "group": "occurrences",
            "name": "abstract_accuracy",
            "fields": [{"path": ["display", "places"], "value_json": "3"}],
            "rationale": "Display three decimal places.",
        },
    )["state"]["maintenance"]
    assert preview["changes"][0]["after"]["display"]["places"] == 3
    assert preview["changes"][0]["after"]["anchor"] == declaration["definition"]["anchor"]
