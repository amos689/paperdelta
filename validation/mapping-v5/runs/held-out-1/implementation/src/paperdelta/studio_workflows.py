"""Studio's reviewed generation declarations. No command execution endpoint."""

from typing import Literal

from pydantic import Field

from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.fragments import FragmentSpec, accept_fragment, preview_fragment
from paperdelta.i18n import msg
from paperdelta.models import Identifier, StrictModel
from paperdelta.notebooks import inspect_notebook
from paperdelta.provenance import (
    ProducerRequest,
    accept_producer,
    producer_record,
    propose_producer,
)
from paperdelta.revisions import revision_list


class NotebookPath(StrictModel):
    path: str = Field(min_length=1, max_length=1000)


class ProducerPreview(ProducerRequest):
    pass


class FragmentPreview(StrictModel):
    name: Identifier
    spec: FragmentSpec
    replace: bool = False


class WorkflowAccept(StrictModel):
    proposal_id: str
    attest: Literal[True]


def execute(session, action, parameters):
    if action == "workflow-options":
        config, _ = load_config(session.project, session.config_path)
        report = session.reviewer.detail()["report"]
        return {
            "bindings": [
                {
                    "name": name,
                    "metric": item.metric,
                    "file": item.file,
                    "display": item.display.model_dump(),
                }
                for name, item in config.occurrences.items()
            ],
            "provenance": report.get("provenance", {}) if report else {},
            "fragments": report.get("fragments", {}) if report else {},
            "revisions": revision_list(report) if report else [],
        }
    if action == "producer-notebook":
        return inspect_notebook(session.project, parameters["path"])
    session._require_clean()
    if action == "producer-preview":
        record = producer_record(session.project, parameters["spec"], parameters["rationale"])
        proposal = propose_producer(
            session.project,
            parameters["name"],
            record,
            replace=parameters["replace"],
            config_path=session.config_path,
        )
    elif action == "fragment-preview":
        proposal = preview_fragment(
            session.project,
            parameters["name"],
            parameters["spec"],
            replace=parameters["replace"],
            config_path=session.config_path,
        )
    else:
        saved = getattr(session, "workflow_proposal", None)
        if (
            saved is None
            or saved["action"] != action.replace("-accept", "-preview")
            or saved["proposal"]["proposal_id"] != parameters["proposal_id"]
        ):
            raise PaperDeltaError("PROVENANCE_STALE", msg("provenance.stale"))
        accept = accept_producer if action == "producer-accept" else accept_fragment
        session.receipt = accept(session.project, saved["proposal"])
        session.receipt["workflow"] = action.removesuffix("-accept")
        session.workflow_proposal = None
        session._after_accept()
        return {"state": session.state()}
    session.workflow_proposal = {"action": action, "proposal": proposal}
    return {"proposal": proposal}
