"""Batch and proposal workflows preserve identity through the Studio boundary."""

from copy import deepcopy
from decimal import Decimal

import pytest

from paperdelta import __version__, builder
from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.onboarding import init_project, propose_bindings
from paperdelta.storage import Project, fingerprint, json_text, parse_json, sha256
from paperdelta.studio import StudioSession
from paperdelta.studio_batch import make_template, proposal_preview, template_request
from paperdelta.studio_recovery import rebuild_draft

COLUMNS = {"model": "string", "split": "string", "seed": "integer", "accuracy": "decimal"}
REQUEST = {
    "source": "results",
    "fields": ["accuracy"],
    "group_by": ["model"],
    "where": {"split": "test"},
    "unit": "fraction",
    "reduce": "mean",
    "expected_count": 2,
    "expected_seeds": ["1", "2"],
    "display": {"kind": "percent", "places": 1, "percent_symbol": True},
}


def call(session, action, payload=None, language="en"):
    return session.execute(
        {
            "action": action,
            "payload": payload or {},
            "revision": session.revision,
            "language": language,
        }
    )


@pytest.fixture
def batch_session(tmp_path):
    project = Project(tmp_path)
    project.write(
        "paper.tex",
        b"\\begin{tabular}{lr}\nModel & accuracy \\\\\n"
        b"001 & 80.0\\% \\\\\n1 & 80.0\\% \\\\\n\\end{tabular}\n",
    )
    project.write(
        "results.csv",
        (
            "model,split,seed,accuracy\n"
            + "".join(
                f"{model},{split},{seed},0.80000000000000000000000000001\n"
                for model in ["001", "1"]
                for split in ["test", "train"]
                for seed in [1, 2]
            )
        ).encode(),
    )
    init_project(project, "paper.tex", ["results.csv"])
    session = StudioSession(project)
    preview = call(session, "source-preview", {"path": "results.csv"})["source"]
    call(
        session,
        "source",
        {
            "name": "results",
            "path": "results.csv",
            "format": "csv",
            "columns": COLUMNS,
            "primary_key": ["model", "split", "seed"],
            "source_hash": preview["hash"],
        },
    )
    return session


def catalog(session):
    return call(session, "batch-catalog", REQUEST)["batch"]


def selections(session, batch):
    chosen = []
    for choice in batch["items"]:
        model = choice["definition"]["where"]["model"]
        result = call(
            session,
            "batch-locations",
            {
                "catalog_id": batch["catalog_id"],
                "choice_id": choice["choice_id"],
            },
        )
        matching = next(
            item
            for item in result["items"]
            if item["row"].split("&")[0].strip() == model and item["text"] == "80.0"
        )
        chosen.append(
            {
                "choice_id": choice["choice_id"],
                "candidate_ids": [matching["candidate_id"]],
                "rationale": f"Model {model}, accuracy, test split and both seeds.",
            }
        )
    return chosen


def test_batch_preserves_string_identity_exact_decimal_and_subset_acceptance(batch_session):
    session = batch_session
    before = session.project.read("paperdelta.yaml")
    batch = catalog(session)
    assert batch["total"] == 2
    assert {item["definition"]["where"]["model"] for item in batch["items"]} == {"001", "1"}
    assert all(
        item["result"]["value"] == "0.80000000000000000000000000001" for item in batch["items"]
    )
    call(
        session,
        "batch-stage",
        {"catalog_id": batch["catalog_id"], "selections": selections(session, batch)},
    )
    assert session.project.read("paperdelta.yaml") == before
    restored = StudioSession(session.project)
    call(restored, "recovery-restore")
    preview = call(restored, "preview")["state"]["preview"]
    assert len(preview["items"]) == 2
    call(
        restored,
        "accept",
        {"proposal_id": preview["proposal_id"], "selected": [preview["items"][0]["binding"]]},
    )
    config, _ = load_config(session.project)
    assert len(config.occurrences) == len(config.metrics) == len(config.sources) == 1
    assert check_project(session.project.root)["coverage"]["pass"] == 1


def test_batch_rejects_overlapping_positions_without_partial_stage(batch_session):
    batch = catalog(batch_session)
    chosen = selections(batch_session, batch)
    chosen[1]["candidate_ids"] = chosen[0]["candidate_ids"]
    identity = batch_session.draft["draft_id"]
    with pytest.raises(PaperDeltaError):
        call(
            batch_session, "batch-stage", {"catalog_id": batch["catalog_id"], "selections": chosen}
        )
    assert batch_session.draft["draft_id"] == identity


@pytest.mark.parametrize("change", ["source", "draft", "catalog"])
def test_batch_rejects_stale_input_or_catalog(batch_session, change):
    session = batch_session
    batch = catalog(session)
    if change == "source":
        session.project.write(
            "results.csv", session.project.read("results.csv") + b"new,test,1,0.5\n"
        )
    elif change == "draft":
        call(session, "undo")
    else:
        batch["catalog_id"] = "sha256:" + "0" * 64
    with pytest.raises(PaperDeltaError):
        call(session, "batch-choices", {"catalog_id": batch["catalog_id"]})


def test_choices_and_locations_are_paginated_without_implicit_selections(batch_session):
    session = batch_session
    batch = catalog(session)
    first = call(session, "batch-choices", {"catalog_id": batch["catalog_id"], "limit": 1})
    second = call(
        session, "batch-choices", {"catalog_id": batch["catalog_id"], "offset": 1, "limit": 1}
    )
    assert first["total"] == 2 and first["items"][0]["choice_id"] != second["items"][0]["choice_id"]
    assert not session.draft["additions"]["occurrences"]
    first["items"][0]["definition"]["where"]["model"] = "tampered"
    assert "tampered" not in str(
        call(session, "batch-choices", {"catalog_id": batch["catalog_id"]})
    )


def test_joint_review_preserves_context_identity_without_choosing_or_writing(batch_session):
    session = batch_session
    before = session.project.read("paperdelta.yaml")
    batch = catalog(session)
    reviewed = call(session, "batch-review", {"catalog_id": batch["catalog_id"]})
    assert reviewed["total"] == 2
    for choice in reviewed["items"]:
        assert len(choice["locations"]) == choice["context_match_count"] == 1
        candidate = choice["locations"][0]
        assert candidate["row"].split("&")[0].strip() == choice["definition"]["where"]["model"]
        assert candidate["suggestion"]["missing_identity"] == ["split"]
        assert candidate["suggestion"]["field_matches"]
        assert choice["result"]["value"] == "0.80000000000000000000000000001"
    assert session.project.read("paperdelta.yaml") == before
    assert not session.draft["additions"]["occurrences"]
    reviewed["items"][0]["locations"][0]["suggestion"]["matched_identity"].clear()
    fresh = call(session, "batch-review", {"catalog_id": batch["catalog_id"]})
    assert fresh["items"][0]["locations"][0]["suggestion"]["matched_identity"] == ["model"]


def test_joint_review_exposes_ties_and_keeps_complete_positions_accessible(batch_session):
    session = batch_session
    paper = session.project.read("paper.tex")
    session.project.write("paper.tex", paper * 5)
    call(session, "refresh")
    preview = call(session, "source-preview", {"path": "results.csv"})["source"]
    call(
        session,
        "source",
        {
            "name": "results",
            "path": "results.csv",
            "format": "csv",
            "columns": COLUMNS,
            "primary_key": ["model", "split", "seed"],
            "source_hash": preview["hash"],
        },
    )
    batch = catalog(session)
    result = call(session, "batch-review", {"catalog_id": batch["catalog_id"], "limit": 1})
    choice = result["items"][0]
    assert result["total"] == 2 and len(result["items"]) == 1
    assert len(choice["locations"]) == 3 and choice["context_match_count"] == 5
    locations = call(
        session,
        "batch-locations",
        {"catalog_id": batch["catalog_id"], "choice_id": choice["choice_id"], "limit": 100},
    )
    assert locations["total"] == choice["location_count"]
    assert choice["location_count"] > choice["context_match_count"]


def test_missing_seed_stays_unknown_and_cannot_be_staged(batch_session):
    session = batch_session
    request = {**REQUEST, "expected_count": 3, "expected_seeds": ["1", "2", "3"]}
    batch = call(session, "batch-catalog", request)["batch"]
    assert all(item["status"] == "unknown" for item in batch["items"])
    old = deepcopy(session.draft)
    with pytest.raises(PaperDeltaError) as error:
        call(
            session,
            "batch-stage",
            {"catalog_id": batch["catalog_id"], "selections": selections(session, batch)},
        )
    assert error.value.code == "BATCH_SELECTION" and session.draft == old


def test_batch_stage_counts_all_selected_positions_before_building(batch_session):
    session = batch_session
    batch = catalog(session)
    selection = selections(session, batch)[0]
    excessive = [
        {**selection, "candidate_ids": selection["candidate_ids"] * count}
        for count in [100, 100, 1]
    ]
    before = deepcopy(session.draft)
    with pytest.raises(PaperDeltaError) as error:
        call(session, "batch-stage", {"catalog_id": batch["catalog_id"], "selections": excessive})
    assert error.value.code == "STUDIO_LIMIT" and session.draft == before


def test_template_import_enforces_utf8_byte_limit_and_accepts_boundary(batch_session):
    session = batch_session
    catalog(session)
    _, config = builder.resume_draft(session.project, session.draft)
    template = make_template("limit", config.sources["results"], session.batch.catalog["request"])
    raw = json_text(template)
    padded = raw + " " * (65536 - len(raw.encode("utf-8")))
    assert call(session, "template-import", {"value_json": padded, "source": "results"})
    template["request"]["where"]["split"] = "测" * 22000
    template["template_id"] = fingerprint(
        {key: value for key, value in template.items() if key != "template_id"}
    )
    with pytest.raises(PaperDeltaError) as error:
        call(session, "template-import", {"value_json": json_text(template), "source": "results"})
    assert error.value.code == "STUDIO_TEMPLATE_LIMIT"


def test_template_moves_to_another_project_and_explicit_source_name(batch_session, tmp_path):
    session = batch_session
    batch = catalog(session)
    call(session, "template-save", {"catalog_id": batch["catalog_id"], "name": "portable"})
    exported = call(session, "template-export", {"name": "portable"})["json"]
    other = Project(tmp_path / "new-project")
    other.write("new.tex", session.project.read("paper.tex"))
    other.write("other.csv", session.project.read("results.csv"))
    init_project(other, "new.tex", ["other.csv"])
    target = StudioSession(other)
    preview = call(target, "source-preview", {"path": "other.csv"})["source"]
    call(
        target,
        "source",
        {
            "name": "new_results",
            "path": "other.csv",
            "format": "csv",
            "columns": COLUMNS,
            "primary_key": ["model", "split", "seed"],
            "source_hash": preview["hash"],
        },
    )
    imported = call(target, "template-import", {"value_json": exported, "source": "new_results"})[
        "request"
    ]
    assert imported["source"] == "new_results" and imported["expected_seeds"] == ["1", "2"]
    fresh = call(target, "batch-catalog", imported)["batch"]
    assert {item["definition"]["where"]["model"] for item in fresh["items"]} == {"001", "1"}
    assert all(item["definition"]["source"] == "new_results" for item in fresh["items"])
    assert not load_config(other)[0].occurrences


def test_template_restart_export_import_and_no_implicit_acceptance(batch_session):
    session = batch_session
    batch = catalog(session)
    before = session.project.read("paperdelta.yaml")
    call(session, "template-save", {"catalog_id": batch["catalog_id"], "name": "test_v1"})
    restored = StudioSession(session.project)
    call(restored, "recovery-restore")
    exported = call(restored, "template-export", {"name": "test_v1"})["json"]
    template = parse_json(exported)
    assert "input_hashes" not in template and "occurrences" not in template
    loaded = call(restored, "template-import", {"value_json": exported, "source": "results"})
    assert loaded["requires_confirmation"] and loaded["request"]["where"] == {"split": "test"}
    assert not restored.draft["additions"]["metrics"]
    assert restored.project.read("paperdelta.yaml") == before
    assert call(restored, "template-list")["templates"][0]["name"] == "test_v1"
    with pytest.raises(PaperDeltaError) as error:
        call(session, "template-save", {"catalog_id": batch["catalog_id"], "name": "test_v1"})
    assert error.value.code == "ALREADY_EXISTS"


def test_template_refuses_identity_and_column_type_changes(batch_session):
    session = batch_session
    batch = catalog(session)
    _, config = builder.resume_draft(session.project, session.draft)
    template = make_template(
        "identity", config.sources["results"], session.batch.catalog["request"]
    )
    damaged = deepcopy(template)
    damaged["request"]["where"]["split"] = "train"
    with pytest.raises(PaperDeltaError, match="identity"):
        template_request(session.project, session.draft, damaged, "results")
    changed = deepcopy(template)
    changed["source_contract"]["columns"]["model"] = "integer"
    changed["template_id"] = fingerprint(
        {key: value for key, value in changed.items() if key != "template_id"}
    )
    with pytest.raises(PaperDeltaError):
        template_request(session.project, session.draft, changed, "results")
    assert batch["total"] == 2


def test_template_list_retains_valid_files_and_reports_invalid_utf8(batch_session):
    session = batch_session
    batch = catalog(session)
    call(session, "template-save", {"catalog_id": batch["catalog_id"], "name": "valid"})
    session.project.write(".paperdelta/studio/templates/broken.json", b"\xff")
    result = call(session, "template-list")
    assert len(result["templates"]) == len(result["errors"]) == 1


@pytest.fixture
def general_proposal(tmp_path):
    project = Project(tmp_path)
    project.write("paper.tex", b"Accuracy: 80.0\\%.\nThe result exceeds the threshold.\n")
    project.write("data.json", b'{"accuracy":0.80000000000000000000000000001}')
    project.write("figure.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>')
    init_project(project, "paper.tex", ["data.json"])
    proposal = propose_bindings(
        project,
        {
            "sources": {"data": {"path": "data.json", "format": "json"}},
            "metrics": {"accuracy": {"source": "data", "field": "/accuracy", "unit": "fraction"}},
            "occurrences": {
                "abstract": {
                    "file": "paper.tex",
                    "metric": "accuracy",
                    "anchor": {"prefix": "Accuracy: ", "suffix": "\\%."},
                    "display": {"kind": "percent", "places": 1},
                }
            },
            "claims": {
                "comparison": {
                    "file": "paper.tex",
                    "anchor": {"exact": "The result exceeds the threshold."},
                    "predicate": {
                        "op": "greater_than",
                        "left": "accuracy",
                        "right": {"value": Decimal("0.7"), "unit": "fraction"},
                    },
                }
            },
        },
        {
            "occurrences:abstract": "The explicitly selected accuracy.",
            "claims:comparison": "The same accuracy against the stated threshold.",
        },
    )
    return project, proposal


def test_imported_proposal_keeps_claims_precision_recovery_and_subset(general_proposal):
    project, proposal = general_proposal
    session = StudioSession(project)
    state = call(session, "proposal-import", {"value_json": json_text(proposal)}, "zh-CN")["state"]
    assert len(state["preview"]["items"]) == 2
    assert state["metrics"]["accuracy"]["result"]["value"] == "0.80000000000000000000000000001"
    restarted = StudioSession(project)
    call(restarted, "recovery-restore")
    preview = call(restarted, "preview")["state"]["preview"]
    call(
        restarted,
        "accept",
        {"proposal_id": preview["proposal_id"], "selected": ["claims:comparison"]},
    )
    config, _ = load_config(project)
    assert set(config.claims) == {"comparison"} and not config.occurrences
    assert len(config.metrics) == len(config.sources) == 1


def test_claim_preview_keeps_complete_wording_when_it_starts_with_a_number(general_proposal):
    project, old = general_proposal
    wording = "80.0\\% exceeds the threshold."
    project.write("paper.tex", (wording + "\n").encode())
    additions = deepcopy(old["additions"])
    additions["occurrences"] = {}
    additions["claims"]["comparison"]["anchor"] = {"exact": wording}
    proposal = propose_bindings(project, additions, {"claims:comparison": "The whole comparison."})
    session = StudioSession(project)
    state = call(session, "proposal-import", {"value_json": json_text(proposal)})["state"]
    assert state["preview"]["items"][0]["candidate_text"] == wording


def test_import_refuses_stale_tool_version_and_changed_inputs(general_proposal):
    project, proposal = general_proposal
    session = StudioSession(project)
    changed = deepcopy(proposal)
    changed["tool_version"] = "0.0.0"
    changed["proposal_id"] = fingerprint(
        {key: value for key, value in changed.items() if key != "proposal_id"}
    )
    with pytest.raises(PaperDeltaError):
        call(session, "proposal-import", {"value_json": json_text(changed)})
    assert not any(session.draft["additions"].values())
    project.write("data.json", b'{"accuracy":0.9}')
    with pytest.raises(PaperDeltaError):
        call(StudioSession(project), "proposal-import", {"value_json": json_text(proposal)})


def test_rebuild_imported_claim_selects_dependencies_after_data_change(general_proposal):
    project, proposal = general_proposal
    session = StudioSession(project)
    call(session, "proposal-import", {"value_json": json_text(proposal)})
    old = deepcopy(session.draft)
    project.write("data.json", b'{"accuracy":0.6}')
    rebuilt, preview = rebuild_draft(project, old, ["claims:comparison"])
    assert set(preview["dependencies"]) == {"sources:data", "metrics:accuracy"}
    assert preview["preview"]["claims"]["comparison"]["status"] == "mismatch"
    assert not rebuilt["additions"]["occurrences"]
    assert rebuilt["tool_version"] == __version__


def test_figure_proposal_preview_without_fake_text_position(tmp_path):
    project = Project(tmp_path)
    project.write("paper.tex", b"A manuscript without a numeric assertion.\n")
    project.write("figure.svg", b'<svg xmlns="http://www.w3.org/2000/svg"/>')
    init_project(project, "paper.tex", [])
    project.write("data.json", b'{"value":0.8}')
    project.write("plot.py", b"# This script is never executed by the checker.\n")
    project.write(
        "figure.record.json",
        json_text(
            {
                "schema_version": 1,
                "path": "figure.svg",
                "output_hash": sha256(project.read("figure.svg")),
                "inputs": {"data.json": sha256(project.read("data.json"))},
                "script": {"path": "plot.py", "hash": sha256(project.read("plot.py"))},
                "recorded_at": "2026-10-04T00:00:00+00:00",
                "method": "manual",
            }
        ).encode(),
    )
    proposal = propose_bindings(
        project,
        {"figures": {"plot": {"path": "figure.svg", "record": "figure.record.json"}}},
        {"figures:plot": "Explicitly selected figure provenance."},
    )
    preview = proposal_preview(project, proposal, [])
    assert preview["items"][0]["label"] == "figure.svg"
    assert preview["items"][0].get("location") is None
    session = StudioSession(project)
    call(session, "proposal-import", {"value_json": json_text(proposal)})
    old = deepcopy(session.draft)
    project.write("data.json", b'{"value":0.9}')
    rebuilt, preview = rebuild_draft(project, old, ["figures:plot"])
    assert preview["preview"]["figures"]["plot"]["status"] == "mismatch"
    assert rebuilt["input_hashes"]["data.json"] == sha256(project.read("data.json"))
