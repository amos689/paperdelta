import pytest
from test_notebooks import notebook
from test_studio import call

from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.fragments import accept_fragment, preview_fragment
from paperdelta.provenance import accept_producer, producer_record, propose_producer
from paperdelta.review_bundle import bundle_bytes, inspect_bundle, preview_bundle, replay_bundle
from paperdelta.storage import Project, json_text
from paperdelta.studio import StudioSession


def workflow(store):
    store.write("analysis.ipynb", json_text(notebook()).encode())
    store.write("observations.csv", b"sample,value\na,1\n")
    return {
        "kind": "notebook",
        "source": "analysis.ipynb",
        "inputs": ["observations.csv"],
        "outputs": ["results/metrics.csv"],
        "cells": ["train-result"],
    }


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_studio_workflow_requires_server_held_explicit_acceptance(project, language):
    store = Project(project)
    spec = workflow(store)
    session = StudioSession(store)
    before = store.read("paperdelta.yaml")

    def request(action, payload=None):
        return session.execute(
            {
                "action": action,
                "payload": payload or {},
                "revision": session.revision,
                "language": language,
            }
        )

    assert request("producer-notebook", {"path": "analysis.ipynb"})["executed"] is False
    plan = request(
        "producer-preview",
        {"name": "training", "spec": spec, "rationale": "Reviewed generation relationship"},
    )["proposal"]
    assert store.read("paperdelta.yaml") == before
    with pytest.raises(PaperDeltaError):
        request("producer-accept", {"proposal_id": plan["proposal_id"], "attest": False})
    with pytest.raises(PaperDeltaError):
        request("producer-run", {"command": ["do-not-execute"]})
    request("producer-accept", {"proposal_id": plan["proposal_id"], "attest": True})
    assert load_config(store)[0].provenance["training"]
    assert request("workflow-options")["provenance"]["training"]["method"] == "declared"
    fragment = request(
        "fragment-preview",
        {
            "name": "accuracy",
            "spec": {
                "format": "markdown",
                "path": "generated/result.md",
                "layout": "value",
                "occurrences": ["abstract_accuracy"],
                "language": language,
            },
        },
    )["proposal"]
    assert not store.path("generated/result.md").exists()
    request("fragment-accept", {"proposal_id": fragment["proposal_id"], "attest": True})
    assert store.read("generated/result.md") == b"84.1%\n"


def test_fragment_and_notebook_bundle_replay_preserves_scope_without_executing(project):
    store = Project(project)
    spec = workflow(store)
    accept_producer(
        store,
        propose_producer(store, "training", producer_record(store, spec, "Declared test workflow")),
    )
    accept_fragment(
        store,
        preview_fragment(
            store,
            "accuracy",
            {
                "format": "markdown",
                "path": "generated/result.md",
                "layout": "value",
                "occurrences": ["abstract_accuracy"],
            },
        ),
    )
    initial = preview_bundle(store, {"reports": ["json", "html"], "inputs": []})
    plan = preview_bundle(
        store, {"reports": ["json", "html"], "inputs": sorted(initial["required_inputs"])}
    )
    raw = bundle_bytes(store, plan)
    scope = inspect_bundle(raw)["plan"]["scope"]
    assert scope["bindings"]["provenance"] == ["training"]
    assert scope["bindings"]["fragments"] == ["accuracy"]
    replay = replay_bundle(store, raw, "replayed")
    assert replay["same_result"] and not replay["executed_project_code"]
    assert replay["scope"] == scope
    assert check_project(project)["exit_code"] == 0


def test_studio_refuses_stale_producer_record_after_independent_file_change(project):
    store = Project(project)
    spec = workflow(store)
    session = StudioSession(store)
    before = store.read("paperdelta.yaml")
    plan = call(
        session, "producer-preview", {"name": "training", "spec": spec, "rationale": "Reviewed"}
    )["proposal"]
    store.write("observations.csv", b"changed\n")
    with pytest.raises(PaperDeltaError):
        call(session, "producer-accept", {"proposal_id": plan["proposal_id"], "attest": True})
    assert store.read("paperdelta.yaml") == before
