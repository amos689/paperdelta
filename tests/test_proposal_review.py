from copy import deepcopy

import pytest

from paperdelta import builder
from paperdelta.agent import AgentSession
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import language_context, translated
from paperdelta.onboarding import init_project, propose_bindings
from paperdelta.proposal_review import inspect_review
from paperdelta.storage import Project, json_text, parse_json, sha256
from paperdelta.studio_batch import proposal_preview


def prepared(tmp_path):
    project = Project(tmp_path)
    project.write("paper.tex", b"Model 001 accuracy is 88.0\\%.\n")
    records = "model,checkpoint,seed,score\n" + "".join(
        f"001,{checkpoint},{seed:03d},0.80\n"
        for checkpoint in ("selected", "other")
        for seed in range(1, 13)
    )
    project.write("results.csv", records.encode())
    init_project(project, "paper.tex", ["results.csv"])
    additions = {
        "sources": {
            "runs": {
                "path": "results.csv",
                "format": "csv",
                "columns": {
                    "model": "string",
                    "checkpoint": "string",
                    "seed": "string",
                    "score": "decimal",
                },
                "primary_key": ["model", "checkpoint", "seed"],
            }
        },
        "metrics": {
            "accuracy": {
                "source": "runs",
                "field": "score",
                "unit": "fraction",
                "reduce": "mean",
                "where": {"model": "001", "checkpoint": "selected"},
                "expected_count": 12,
                "seed_column": "seed",
                "expected_seeds": [f"{seed:03d}" for seed in range(1, 13)],
            }
        },
        "occurrences": {
            "result": {
                "file": "paper.tex",
                "anchor": {"exact": r"88.0\%"},
                "metric": "accuracy",
                "display": {"kind": "percent", "places": 1, "percent_symbol": True},
            }
        },
    }
    rationale = {"occurrences:result": "The author identified model 001 and checkpoint selected."}
    return project, additions, rationale


def snapshots(project):
    return {
        p.relative_to(project.root): p.read_bytes() for p in project.root.rglob("*") if p.is_file()
    }


def test_shared_review_preserves_typed_identity_and_exposes_truncation(tmp_path):
    project, additions, rationale = prepared(tmp_path)
    before = snapshots(project)
    agent = AgentSession(project)
    result = agent.propose_bindings(json_text(additions), rationale)
    proposal = parse_json(result["proposal_json"])
    review = result["review"]
    assert review["requires_confirmation"] and review["rationale_status"] == "unverified_assertion"
    item = review["bindings"][0]
    assert item["identity_status"] == "requires_author_review"
    assert item["deterministic_result"]["status"] == "mismatch"
    assert "stale paper value" in item["notices"][1]
    metric = item["metrics"]["accuracy"]
    identity = metric["declared_identity"]
    assert identity["selectors"] == {"model": "001", "checkpoint": "selected"}
    assert identity["expected_seeds"][0] == "001"
    assert identity["columns"]["model"] == "string"
    assert identity["sha256"] == sha256(project.read("results.csv"))
    evidence = metric["evidence"][0]
    assert evidence["records_total"] == evidence["locations_total"] == 12
    assert len(evidence["records"]) == len(evidence["locations"]) == 10
    assert evidence["truncated"] and evidence["inspect"]["path"] == "results.csv"
    assert evidence["records"][0]["key"]["seed"] == "001"
    assert "definition" not in metric["computed"]
    studio = proposal_preview(project, proposal, agent.scan_project()["candidates"])
    # Studio and Agent use the same view; decimal transport encoding is the only difference.
    assert parse_json(json_text(studio["review"])) == parse_json(
        json_text(inspect_review(project, proposal))
    )
    assert studio["items"][0]["review"]["binding"] == item["binding"]
    assert snapshots(project) == before


def test_review_is_fresh_bilingual_and_not_an_author_attestation(tmp_path):
    project, additions, rationale = prepared(tmp_path)
    proposal = propose_bindings(project, additions, rationale)
    with language_context("zh-CN"):
        review = translated(inspect_review(project, proposal))
    assert "真实性" in review["verification_scope"]
    assert "不能证明" in review["bindings"][0]["notices"][0]
    assert review["bindings"][0]["asserted_rationale"] == rationale["occurrences:result"]
    assert "accept" not in review["full_evidence"]["cli_arguments"]
    project.write("results.csv", project.read("results.csv").replace(b"0.80", b"0.79"))
    with pytest.raises(PaperDeltaError) as error:
        inspect_review(project, proposal)
    assert error.value.code == "STALE_PROPOSAL"


def test_evidence_limits_are_explicit_and_do_not_change_the_proposal(tmp_path):
    project, additions, rationale = prepared(tmp_path)
    proposal = propose_bindings(project, additions, rationale)
    saved = deepcopy(proposal)
    for limit in (1, 12, 100):
        evidence = inspect_review(project, proposal, row_limit=limit)["bindings"][0]["metrics"][
            "accuracy"
        ]["evidence"][0]
        assert len(evidence["records"]) == min(limit, 12)
        assert evidence["truncated"] == (limit < 12)
    for limit in (0, -1, 101, True):
        with pytest.raises(ValueError):
            inspect_review(project, proposal, row_limit=limit)
    assert proposal == saved


def test_derived_review_contains_both_complete_source_contracts(tmp_path):
    project, additions, rationale = prepared(tmp_path)
    additions["metrics"]["other"] = {
        **additions["metrics"]["accuracy"],
        "where": {"model": "001", "checkpoint": "other"},
    }
    additions["metrics"]["gain"] = {"op": "relative_change_percent", "args": ["accuracy", "other"]}
    additions["occurrences"]["result"]["metric"] = "gain"
    proposal = propose_bindings(project, additions, rationale)
    metrics = inspect_review(project, proposal)["bindings"][0]["metrics"]
    assert set(metrics) == {"gain", "accuracy", "other"}
    assert metrics["gain"]["derivation"]["arguments"] == ["accuracy", "other"]
    assert metrics["accuracy"]["declared_identity"]["selectors"]["checkpoint"] == "selected"
    assert metrics["other"]["declared_identity"]["selectors"]["checkpoint"] == "other"


def test_json_pointer_review_keeps_exact_path_and_no_invented_row_identity(tmp_path):
    project, additions, rationale = prepared(tmp_path)
    project.write("result.json", b'{"evaluation/test":{"score.mean":0.8}}')
    additions["sources"] = {"runs": {"path": "result.json", "format": "json"}}
    additions["metrics"]["accuracy"] = {
        "source": "runs",
        "field": "/evaluation~1test/score.mean",
        "unit": "fraction",
        "reduce": "unique",
        "expected_count": 1,
    }
    proposal = propose_bindings(project, additions, rationale)
    metric = inspect_review(project, proposal)["bindings"][0]["metrics"]["accuracy"]
    assert metric["declared_identity"]["primary_key"] == []
    assert metric["declared_identity"]["expected_seeds"] is None
    assert metric["evidence"][0]["locations"] == [{"pointer": "/evaluation~1test/score.mean"}]


def test_direct_draft_inspection_reports_the_same_truncation_totals(tmp_path):
    project, additions, _ = prepared(tmp_path)
    agent = AgentSession(project)
    draft = builder.start_draft(project)
    draft = builder.add_source(project, draft, name="runs", **additions["sources"]["runs"])
    draft = builder.add_metric(project, draft, name="accuracy", **additions["metrics"]["accuracy"])
    view = agent._draft_view(draft)
    sample = view["preview"]["metrics"]["accuracy"]["evidence"][0]
    assert sample["records_total"] == 12 and len(sample["records"]) == 10
    reviewed = view["review"]["metrics"]["accuracy"]["evidence"][0]
    assert reviewed["records_total"] == 12 and len(reviewed["records"]) == 5


def test_undo_retains_newly_observed_file_identity_and_has_a_separate_budget(tmp_path):
    project, additions, _ = prepared(tmp_path)
    agent = AgentSession(project)
    state = agent.mapping_call("start")
    project.write("later.csv", project.read("results.csv"))
    source = {**additions["sources"]["runs"], "path": "later.csv", "name": "runs"}

    def advance(action, arguments, reason=""):
        nonlocal state
        state = agent.mapping_call(
            "advance", state["session_id"], state["revision"], action, arguments, reason
        )
        return state

    for remaining in (3, 2, 1, 0):
        advance("source", source)
        draft_id = state["draft_id"]
        advance("undo", {}, "The source declaration needs review.")
        assert state["previous_draft_id"] == draft_id
        assert state["preview"]["available_sources"] == []
        assert state["undo"]["remaining"] == remaining
        assert state["corrections_remaining"] == 3
        exported = parse_json(agent.mapping_call("inspect", state["session_id"])["draft_json"])
        assert exported["input_hashes"]["later.csv"] == sha256(project.read("later.csv"))
    advance("source", source)
    assert "undo" not in state["allowed_actions"]
    project.write("later.csv", project.read("later.csv") + b"001,new,001,0.7\n")
    advance("abstain", {}, "Missing identity evidence.")
    assert state["status"] == "stale" and state["previous_draft_preserved"]


def test_unit_correction_preserves_last_valid_draft_and_explicit_abstention(tmp_path):
    project, additions, _ = prepared(tmp_path)
    agent = AgentSession(project)
    state = agent.mapping_call("start")

    def advance(action, arguments, reason=""):
        nonlocal state
        state = agent.mapping_call(
            "advance", state["session_id"], state["revision"], action, arguments, reason
        )

    advance("source", {"name": "runs", **additions["sources"]["runs"]})
    advance("metric", {"name": "accuracy", **additions["metrics"]["accuracy"], "unit": "percent"})
    advance("undo", {}, "Source documentation declares a fraction, not a percent.")
    advance("metric", {"name": "accuracy", **additions["metrics"]["accuracy"]})
    valid = state["draft_id"]
    advance(
        "locations",
        {
            "metric": "accuracy",
            "candidate_ids": [],
            "names": [],
            "display_kind": "percent",
            "places": 1,
            "percent_symbol": True,
            "rationale": "No location selected.",
        },
    )
    assert state["draft_id"] == valid and state["previous_draft_preserved"]
    assert "one original candidate ID" in state["error"]["hint"]
    reason = "The experiment identity cannot be established from the available context."
    advance("abstain", {}, reason)
    assert state["status"] == "abstained" and "proposal_json" not in state
    assert agent.mapping_call("inspect", state["session_id"])["reason"] == reason
