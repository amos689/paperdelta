from copy import deepcopy

import pytest

from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.onboarding import init_project
from paperdelta.storage import Project
from paperdelta.studio import StudioSession


def call(session, action, payload=None):
    return session.execute(
        {"action": action, "payload": payload or {}, "revision": session.revision}
    )


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
    "aliases": [
        {
            "column": "model",
            "value": "001",
            "label": "Ours",
            "rationale": "Experiment log identifies Ours as model 001.",
        },
        {
            "column": "model",
            "value": "1",
            "label": "Baseline",
            "rationale": "Experiment log identifies Baseline as model 1.",
        },
    ],
}


@pytest.fixture
def session(tmp_path):
    project = Project(tmp_path)
    project.write(
        "paper.tex",
        b"\\begin{tabular}{lr}\nModel & accuracy \\\\\n"
        b"Ours & 80.0\\% \\\\\nBaseline & 80.0\\% \\\\\n\\end{tabular}\n",
    )
    project.write(
        "results.csv",
        b"model,split,seed,accuracy\n001,test,1,0.79\n001,test,2,0.81\n1,test,1,0.80\n1,test,2,0.80\n",
    )
    init_project(project, "paper.tex", ["results.csv"])
    value = StudioSession(project)
    source = call(value, "source-preview", {"path": "results.csv"})["source"]
    call(
        value,
        "source",
        {
            "name": "results",
            "path": "results.csv",
            "format": "csv",
            "columns": {
                "model": "string",
                "split": "string",
                "seed": "integer",
                "accuracy": "decimal",
            },
            "primary_key": ["model", "split", "seed"],
            "source_hash": source["hash"],
        },
    )
    return value


def definition(session, name="test_accuracy", request=None):
    return call(
        session,
        "experiment-preview",
        {
            "name": name,
            "request": request or REQUEST,
            "rationale": "Reviewed test split, seeds, fraction unit and explicit model labels.",
        },
    )


def test_definition_and_aliases_require_preview_and_keep_accepted_contract_snapshots(session):
    original = session.project.read("paperdelta.yaml")
    preview = definition(session)
    assert not session.project.path(".paperdelta/experiments").exists()
    with pytest.raises(PaperDeltaError) as error:
        call(session, "experiment-accept", {"preview_id": "sha256:" + "0" * 64})
    assert error.value.code == "EXPERIMENT_PREVIEW"
    saved = call(session, "experiment-accept", {"preview_id": preview["preview_id"]})
    assert session.project.read("paperdelta.yaml") == original
    loaded = call(
        session, "experiment-load", {"definition_id": saved["definition_id"], "source": "results"}
    )
    batch = call(session, "batch-catalog", loaded["request"])["batch"]
    joint = call(session, "batch-review", {"catalog_id": batch["catalog_id"]})
    selections = []
    for item in joint["items"]:
        assert len(item["locations"]) == 1
        candidate = item["locations"][0]
        model = item["definition"]["where"]["model"]
        label = "Ours" if model == "001" else "Baseline"
        assert candidate["row"].split("&")[0].strip() == label
        assert candidate["suggestion"]["aliases"][0]["label"] == label
        selections.append(
            {
                "choice_id": item["choice_id"],
                "candidate_ids": [candidate["candidate_id"]],
                "rationale": "Reviewed the literal model label and exact evidence identity.",
            }
        )
    call(session, "batch-stage", {"catalog_id": batch["catalog_id"], "selections": selections})
    preview = call(session, "preview")["state"]["preview"]
    assert all(saved["definition_id"] in item["rationale"] for item in preview["items"])
    call(
        session,
        "accept",
        {
            "proposal_id": preview["proposal_id"],
            "selected": [item["binding"] for item in preview["items"]],
        },
    )
    config, _ = load_config(session.project)
    assert {m.where["model"] for m in config.metrics.values()} == {"001", "1"}
    assert check_project(session.project.root)["coverage"]["pass"] == 2
    accepted = session.project.read("paperdelta.yaml")
    revised = deepcopy(REQUEST)
    revised["display"]["places"] = 2
    change = definition(session, request=revised)
    newer = call(session, "experiment-accept", {"preview_id": change["preview_id"]})
    assert newer["definition_id"] != saved["definition_id"]
    assert len(call(session, "experiment-list")["items"]) == 2
    assert session.project.read("paperdelta.yaml") == accepted


@pytest.mark.parametrize(
    "change,code",
    [
        ("collision", "EXPERIMENT_ALIAS_CONFLICT"),
        ("result", "EXPERIMENT_ALIAS_COLUMN"),
        ("missing", "EXPERIMENT_ALIAS_VALUE"),
    ],
)
def test_alias_conflict_and_measurement_identity_are_rejected(session, change, code):
    request = deepcopy(REQUEST)
    if change == "collision":
        request["aliases"][1]["label"] = "ours"
    elif change == "result":
        request["aliases"][0].update(column="accuracy", value="0.79")
    else:
        request["aliases"][0]["value"] = "0001"
    with pytest.raises(PaperDeltaError) as error:
        definition(session, request=request)
    assert error.value.code == code


def test_saved_reference_cannot_be_silently_modified_or_confirmed_after_input_change(session):
    preview = definition(session)
    saved = call(session, "experiment-accept", {"preview_id": preview["preview_id"]})
    request = call(
        session, "experiment-load", {"definition_id": saved["definition_id"], "source": "results"}
    )["request"]
    request["unit"] = "scalar"
    with pytest.raises(PaperDeltaError) as error:
        call(session, "batch-catalog", request)
    assert error.value.code == "EXPERIMENT_CHANGED"
    preview = definition(session, name="new_definition")
    session.project.write("results.csv", session.project.read("results.csv") + b"2,test,1,0.8\n")
    with pytest.raises(PaperDeltaError) as error:
        call(session, "experiment-accept", {"preview_id": preview["preview_id"]})
    assert error.value.code == "STALE_DRAFT"
    assert len(list(session.project.path(".paperdelta/experiments").glob("*.json"))) == 1
