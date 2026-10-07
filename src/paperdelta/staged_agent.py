"""Bounded, read-only mapping sessions with recoverable, typed stage errors."""

from __future__ import annotations

import inspect
import time
import uuid
from collections import OrderedDict
from functools import lru_cache
from typing import get_type_hints

from pydantic import ConfigDict, Field, ValidationError, create_model

from paperdelta import builder
from paperdelta.errors import PaperDeltaError, error_message
from paperdelta.i18n import current_language, language_context, msg, tr
from paperdelta.models import Hash, Identifier, ReviewedTableIdentity
from paperdelta.onboarding import inspect_proposal, scan_project
from paperdelta.proposal_review import draft_review, from_checked
from paperdelta.storage import json_text

STAGES = {
    "source": builder.add_source,
    "metric": builder.add_metric,
    "derived": builder.add_derived,
    "locations": builder.add_occurrences,
}
MAX_ACTIONS = 16
MAX_ERRORS = 3
MAX_UNDOS = 4


def stage_models():
    return _stage_models(current_language())


@lru_cache(maxsize=2)
def _stage_models(language):
    result = {}
    for name, function in STAGES.items():
        hints = get_type_hints(function)
        fields = {
            key: (
                hints[key],
                ... if parameter.default is inspect.Parameter.empty else parameter.default,
            )
            for key, parameter in inspect.signature(function).parameters.items()
            if key not in {"project", "value"}
        }
        for key, (kind, default) in list(fields.items()):
            if key in {"name", "source", "metric", "left", "right"}:
                kind = Identifier
            elif key == "names":
                kind = list[Identifier]
            elif key == "candidate_ids":
                kind = list[Hash]
            elif key == "table_identity":
                kind = ReviewedTableIdentity | None
            description = {
                "name": "identifier",
                "source": "reference",
                "metric": "reference",
                "left": "reference",
                "right": "reference",
                "names": "names",
                "columns": "columns",
                "primary_key": "primary_key",
                "unit": "unit",
                "display_kind": "display",
                "percent_symbol": "percent_symbol",
                "expected_count": "expected_count",
                "where": "where",
                "field": "field",
                "places": "places",
                "candidate_ids": "candidate_ids",
                "table_identity": "table_identity",
            }.get(key)
            with language_context(language):
                fields[key] = (
                    (kind, Field(default=default, description=tr("mapping.schema_" + description)))
                    if description
                    else (kind, default)
                )
        result[name] = create_model(
            name.title() + "MappingStage",
            __config__=ConfigDict(strict=True, extra="forbid"),
            **fields,
        )
    return result


def _hint(code, action):
    if code in {"STALE_DRAFT", "INPUT_CHANGED", "STALE_PROPOSAL"}:
        return msg("mapping.hint_stale")
    if code in {"BUILDER_EXPECTATION", "EXPECTED_COUNT", "MISSING_SEED", "SEED_MISMATCH"}:
        return msg("mapping.hint_count")
    if code.startswith(("SOURCE_", "CSV_", "DUPLICATE_", "DRAFT_SOURCE")):
        return msg("mapping.hint_source")
    if code.startswith(("BUILDER_ANCHOR", "ANCHOR_", "BUILDER_OVERLAP", "PDF_", "DOCX_")):
        return msg("mapping.hint_location")
    if code == "UNIT_MISMATCH":
        return msg("mapping.hint_unit")
    if code == "BUILDER_SELECTION" and action == "locations":
        return msg("mapping.hint_selection")
    return msg("mapping.hint_arguments")


class MappingSessions:
    def __init__(self, project, config_path):
        self.project, self.config_path = project, config_path
        self.sessions = OrderedDict()

    def _session(self, session_id):
        state = self.sessions.get(session_id)
        if state is None or time.monotonic() - state["created"] > 3600:
            self.sessions.pop(session_id, None)
            raise PaperDeltaError("MAPPING_SESSION", msg("mapping.session"))
        return state

    def _view(self, session_id, state):
        preview = builder.inspect_draft(self.project, state["draft"])
        for metric in preview["metrics"].values():
            for evidence in metric["evidence"]:
                for key in ("records", "locations"):
                    evidence[key + "_total"] = len(evidence[key])
                    evidence[key] = evidence[key][:5]
        active = state["status"] in {"draft", "needs_correction"}
        undo = bool(state["history"]) and state["undos"] < MAX_UNDOS
        next_stage = (
            "finish"
            if "finish" in preview["available_stages"]
            else "locations"
            if preview["available_metrics"]
            else "metric"
            if preview["available_sources"]
            else "source"
        )
        view = {
            "session_id": session_id,
            "revision": state["revision"],
            "status": state["status"],
            "actions_remaining": MAX_ACTIONS - state["actions"],
            "corrections_remaining": MAX_ERRORS - state["errors"],
            "allowed_actions": [
                *preview["available_stages"],
                *(["undo"] if undo else []),
                "abstain",
            ]
            if active
            else [],
            "draft_id": state["draft"]["draft_id"],
            "preview": preview,
            "review": draft_review(self.project, state["draft"]),
            "stage_guidance": msg("mapping.stage_" + next_stage),
            "undo": {
                "remaining": MAX_UNDOS - state["undos"],
                "last_action": state["history"][-1]["action"] if undo else None,
                "notice": msg("mapping.undo_notice"),
            },
            "requires_confirmation": True,
            "next": msg("mapping.next"),
        }
        if "reason" in state:
            view["reason"] = state["reason"]
        return view

    def start(self):
        draft = builder.start_draft(self.project, self.config_path)
        session_id = uuid.uuid4().hex
        while len(self.sessions) >= 32:
            self.sessions.popitem(last=False)
        state = {
            "created": time.monotonic(),
            "draft": draft,
            "revision": 0,
            "status": "draft",
            "actions": 0,
            "errors": 0,
            "history": [],
            "undos": 0,
        }
        self.sessions[session_id] = state
        return {
            **self._view(session_id, state),
            "discovery": scan_project(self.project, self.config_path),
            "stage_schemas": {
                name: model.model_json_schema() for name, model in stage_models().items()
            },
            "limits": {
                "max_actions": MAX_ACTIONS,
                "max_errors": MAX_ERRORS,
                "max_undos": MAX_UNDOS,
                "expires_seconds": 3600,
            },
            "instructions": msg("mapping.instructions"),
        }

    def inspect(self, session_id):
        state = self._session(session_id)
        return {**self._view(session_id, state), "draft_json": json_text(state["draft"])}

    def advance(self, session_id, revision, action, arguments=None, reason=""):
        state = self._session(session_id)
        if type(revision) is not int or revision != state["revision"]:
            raise PaperDeltaError("MAPPING_REVISION", msg("mapping.revision"))
        if state["status"] not in {"draft", "needs_correction"}:
            raise PaperDeltaError("MAPPING_TERMINAL", msg("mapping.terminal"))
        before = state["draft"]["draft_id"]
        before_draft = state["draft"]
        before_history = list(state["history"])
        before_undos = state["undos"]
        state["actions"] += 1
        state["revision"] += 1
        try:
            preview = builder.inspect_draft(self.project, state["draft"])
            undo = bool(state["history"]) and state["undos"] < MAX_UNDOS
            if action not in [*preview["available_stages"], *(["undo"] if undo else []), "abstain"]:
                raise PaperDeltaError("MAPPING_ORDER", msg("mapping.order"))
            if (
                not isinstance(arguments, dict)
                or len(json_text(arguments).encode("utf-8")) > 131072
            ):
                raise PaperDeltaError("MAPPING_ARGUMENTS", msg("mapping.arguments"))
            if action in {"finish", "abstain", "undo"} and arguments:
                raise PaperDeltaError("MAPPING_ARGUMENTS", msg("mapping.arguments"))
            if action == "undo":
                if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
                    raise PaperDeltaError("MAPPING_REASON", msg("mapping.undo_reason"))
                previous = state["history"][-1]
                restored = builder._seal(
                    self.project, previous["draft"], state["draft"]["input_hashes"]
                )
                builder.inspect_draft(self.project, restored)
                state["history"].pop()
                state["draft"] = restored
                state["undos"] += 1
                state["status"] = "draft" if state["actions"] < MAX_ACTIONS else "budget_exhausted"
                return {
                    **self._view(session_id, state),
                    "applied": True,
                    "undone_action": previous["action"],
                    "previous_draft_id": before,
                    "reason": reason,
                }
            if action == "abstain":
                if not isinstance(reason, str) or not reason.strip() or len(reason) > 4000:
                    raise PaperDeltaError("MAPPING_REASON", msg("mapping.reason"))
                state["status"] = "abstained"
                state["reason"] = reason
                return {**self._view(session_id, state), "reason": reason, "applied": False}
            if action == "finish":
                proposal = builder.finalize_draft(self.project, state["draft"])
                parsed, config, checked = inspect_proposal(self.project, proposal)
                state["status"] = "proposed"
                return {
                    **self._view(session_id, state),
                    "proposal_id": proposal["proposal_id"],
                    "proposal_json": json_text(proposal),
                    "review": from_checked(self.project, parsed, config, checked),
                    "deterministic_check": {
                        "exit_code": checked["exit_code"],
                        "coverage": checked["coverage"],
                        "diagnostics": checked["diagnostics"],
                    },
                    "applied": False,
                }
            parameters = stage_models()[action].model_validate(arguments).model_dump()
            draft = STAGES[action](self.project, state["draft"], **parameters)
            builder.inspect_draft(self.project, draft)
            state["history"].append({"action": action, "draft": state["draft"]})
            state["history"] = state["history"][-MAX_UNDOS:]
            state["draft"] = draft
            state["status"] = "draft" if state["actions"] < MAX_ACTIONS else "budget_exhausted"
            return {**self._view(session_id, state), "applied": True}
        except (PaperDeltaError, ValidationError) as exc:
            state["draft"] = before_draft
            state["history"] = before_history
            state["undos"] = before_undos
            state.pop("reason", None)
            validation = exc if isinstance(exc, ValidationError) else exc.__cause__
            if not isinstance(validation, ValidationError):
                validation = None
            state["errors"] += 1
            code = exc.code if isinstance(exc, PaperDeltaError) else "MAPPING_ARGUMENTS"
            stale = code in {"STALE_DRAFT", "INPUT_CHANGED", "STALE_PROPOSAL"}
            state["status"] = (
                "stale"
                if stale
                else (
                    "needs_correction"
                    if state["errors"] < MAX_ERRORS and state["actions"] < MAX_ACTIONS
                    else "budget_exhausted"
                )
            )
            view = (
                {
                    "session_id": session_id,
                    "revision": state["revision"],
                    "status": state["status"],
                    "allowed_actions": [],
                    "draft_id": before,
                    "requires_confirmation": True,
                }
                if stale
                else self._view(session_id, state)
            )
            return {
                **view,
                "applied": False,
                "previous_draft_preserved": True,
                "error": {
                    "code": code,
                    "message": error_message(validation or exc),
                    "hint": _hint(code, action),
                    "fields": [
                        list(error["loc"])
                        for error in validation.errors(include_url=False, include_input=False)
                    ]
                    if validation is not None
                    else [],
                },
            }
