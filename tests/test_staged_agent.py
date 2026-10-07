from copy import deepcopy

import pytest

from paperdelta.agent import AgentSession
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import language_context
from paperdelta.onboarding import init_project
from paperdelta.storage import Project, parse_json


@pytest.fixture
def mapping(tmp_path):
    project = Project(tmp_path)
    project.write("paper.tex", b"Model 001 accuracy is 80.0\\%.\nModel 1 accuracy is 80.0\\%.\n")
    project.write("results.csv", b"model,seed,accuracy\n001,1,0.79\n001,2,0.81\n1,1,0.80\n")
    init_project(project, "paper.tex", ["results.csv"])
    return AgentSession(project)


def files(project):
    return {
        p.relative_to(project.root): p.read_bytes() for p in project.root.rglob("*") if p.is_file()
    }


def source(mapping, state):
    return mapping.mapping_call(
        "advance",
        state["session_id"],
        state["revision"],
        "source",
        {
            "name": "results",
            "path": "results.csv",
            "format": "csv",
            "columns": {"model": "string", "seed": "integer", "accuracy": "decimal"},
            "primary_key": ["model", "seed"],
        },
    )


def test_error_correction_and_final_proposal_preserve_equal_value_identities(mapping):
    before = files(mapping.project)
    start = mapping.mapping_call("start")
    state = source(mapping, start)
    valid = deepcopy(state)
    arguments = {
        "name": "accuracy",
        "source": "results",
        "field": "accuracy",
        "where": {"model": "001"},
        "unit": "fraction",
        "reduce": "mean",
        "expected_count": 2,
        "expected_seeds": [1, 2],
    }
    state = mapping.mapping_call(
        "advance", state["session_id"], state["revision"], "metric", arguments
    )
    assert state["status"] == "needs_correction" and not state["applied"]
    assert state["draft_id"] == valid["draft_id"]
    assert state["error"]["fields"] == [["expected_seeds", 0], ["expected_seeds", 1]]
    arguments["expected_seeds"] = ["1", "2"]
    state = mapping.mapping_call(
        "advance", state["session_id"], state["revision"], "metric", arguments
    )
    assert state["preview"]["metrics"]["accuracy"]["value"] == "0.80"
    candidate = next(c for c in start["discovery"]["candidates"] if c["text"] == "80.0")
    state = mapping.mapping_call(
        "advance",
        state["session_id"],
        state["revision"],
        "locations",
        {
            "metric": "accuracy",
            "candidate_ids": [candidate["candidate_id"]],
            "names": ["accuracy_text"],
            "display_kind": "percent",
            "places": 1,
            "percent_symbol": True,
            "rationale": "Explicit model 001, mean accuracy of seeds 1 and 2; first sentence.",
        },
    )
    state = mapping.mapping_call("advance", state["session_id"], state["revision"], "finish", {})
    assert state["status"] == "proposed" and state["requires_confirmation"]
    proposal = parse_json(state["proposal_json"])
    assert proposal["additions"]["metrics"]["accuracy"]["where"] == {"model": "001"}
    assert state["deterministic_check"]["coverage"]["confirmed"] == 1
    assert files(mapping.project) == before


def test_invalid_action_budget_stops_without_discarding_valid_draft(mapping):
    state = source(mapping, mapping.mapping_call("start"))
    draft_id = state["draft_id"]
    for _ in range(3):
        state = mapping.mapping_call(
            "advance", state["session_id"], state["revision"], "finish", {}
        )
    assert state["status"] == "budget_exhausted" and state["allowed_actions"] == []
    assert state["draft_id"] == draft_id and state["corrections_remaining"] == 0
    assert mapping.mapping_call("inspect", state["session_id"])["draft_json"]
    with pytest.raises(PaperDeltaError, match="ended"):
        mapping.mapping_call("advance", state["session_id"], state["revision"], "source", {})


def test_input_change_stops_session_and_old_revision_cannot_mutate(mapping):
    state = source(mapping, mapping.mapping_call("start"))
    with pytest.raises(PaperDeltaError) as error:
        mapping.mapping_call("advance", state["session_id"], 0, "finish", {})
    assert error.value.code == "MAPPING_REVISION"
    mapping.project.write("results.csv", mapping.project.read("results.csv") + b"1,2,0.80\n")
    state = mapping.mapping_call("advance", state["session_id"], state["revision"], "finish", {})
    assert state["status"] == "stale" and state["error"]["code"] == "STALE_DRAFT"
    assert state["previous_draft_preserved"] and not state["allowed_actions"]


def test_explicit_abstention_and_bilingual_correction(mapping):
    with language_context("zh-CN"):
        state = mapping.mapping_call("start")
        state = mapping.mapping_call(
            "advance", state["session_id"], state["revision"], "metric", {}
        )
        assert "请选择" in state["error"]["message"]
        state = mapping.mapping_call(
            "advance", state["session_id"], state["revision"], "abstain", {}, "无法确定实验身份"
        )
    assert state["status"] == "abstained" and "proposal_json" not in state


def test_session_handles_are_process_local_and_expire(mapping):
    state = mapping.mapping_call("start")
    with pytest.raises(PaperDeltaError) as error:
        AgentSession(mapping.project).mapping_call("inspect", state["session_id"])
    assert error.value.code == "MAPPING_SESSION"
    mapping.mapping.sessions[state["session_id"]]["created"] -= 3601
    with pytest.raises(PaperDeltaError) as error:
        mapping.mapping_call("inspect", state["session_id"])
    assert error.value.code == "MAPPING_SESSION"


def test_statistical_method_and_display_are_typed_without_accepting_computed_values(mapping):
    start = mapping.mapping_call("start")
    state = source(mapping, start)
    state = mapping.mapping_call(
        "advance",
        state["session_id"],
        state["revision"],
        "metric",
        {
            "name": "accuracy",
            "source": "results",
            "field": "accuracy",
            "where": {"model": "001"},
            "unit": "fraction",
            "reduce": "statistics",
            "expected_count": 2,
            "expected_seeds": ["1", "2"],
            "statistics": {"ddof": 1, "unit_of_analysis": "seed"},
        },
    )
    assert state["applied"]
    previous = state["draft_id"]
    candidate = next(c for c in start["discovery"]["candidates"] if c["text"] == "80.0")
    arguments = {
        "metric": "accuracy",
        "candidate_ids": [candidate["candidate_id"]],
        "names": ["accuracy_text"],
        "display_kind": "percent",
        "places": 1,
        "percent_symbol": True,
        "rationale": "Mean across both declared model 001 seeds.",
        "statistics": {"mean": "0.80"},
    }
    state = mapping.mapping_call(
        "advance", state["session_id"], state["revision"], "locations", arguments
    )
    assert not state["applied"] and state["draft_id"] == previous
    assert ["statistics", "mean"] in state["error"]["fields"]
    arguments["statistics"] = {"component": "mean"}
    state = mapping.mapping_call(
        "advance", state["session_id"], state["revision"], "locations", arguments
    )
    assert state["applied"]
    state = mapping.mapping_call("advance", state["session_id"], state["revision"], "finish", {})
    assert state["status"] == "proposed" and state["requires_confirmation"]
    assert state["review"]["bindings"][0]["deterministic_result"]["status"] == "pass"
