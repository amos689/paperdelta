"""Bounded, process-local draft handles; no project writes or confirmations."""

from __future__ import annotations

import time
import uuid
from collections import OrderedDict

from paperdelta import builder
from paperdelta.batch import build_proposal, create_catalog, inspect_catalog
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.storage import fingerprint, json_text


class BatchSessions:
    def __init__(self, project, config_path):
        self.project, self.config_path = project, config_path
        self.sessions = OrderedDict()

    def _session(self, session_id):
        state = self.sessions.get(session_id)
        if state is None or time.monotonic() - state["created"] > 3600:
            self.sessions.pop(session_id, None)
            raise PaperDeltaError("BATCH_SESSION", msg("batch.session"))
        return state

    def start(self, request, source_path=None, columns=None, primary_key=None):
        draft = builder.start_draft(self.project, self.config_path)
        _, config = builder.resume_draft(self.project, draft)
        source = request["source"]
        if source_path is not None:
            if source in config.sources:
                raise PaperDeltaError(
                    "BATCH_SOURCE_EXISTS", msg("batch.source_exists", source=source)
                )
            draft = builder.add_source(
                self.project,
                draft,
                name=source,
                path=source_path,
                format="csv",
                columns=columns,
                primary_key=primary_key,
            )
        catalog = create_catalog(self.project, draft, request)
        session_id = uuid.uuid4().hex
        while len(self.sessions) >= 32:
            self.sessions.popitem(last=False)
        self.sessions[session_id] = {
            "created": time.monotonic(),
            "catalog": catalog,
            "selections": [],
        }
        return {
            "session_id": session_id,
            "status": "draft",
            "next": msg("batch.agent_next"),
            **self.list(session_id),
        }

    def list(self, session_id, kind="metrics", offset=0, limit=20):
        if (
            kind not in {"metrics", "locations"}
            or type(offset) is not int
            or type(limit) is not int
            or offset < 0
            or not 1 <= limit <= 50
        ):
            raise PaperDeltaError("BATCH_PAGE", msg("batch.page"))
        state = self._session(session_id)
        preview = inspect_catalog(self.project, state["catalog"])
        values = preview["choices" if kind == "metrics" else "locations"]
        return {
            "session_id": session_id,
            "kind": kind,
            "items": values[offset : offset + limit],
            "total": len(values),
            "next_offset": offset + limit if offset + limit < len(values) else None,
            "selected_locations": sum(len(item["candidate_ids"]) for item in state["selections"]),
            "requires_confirmation": True,
        }

    def select(self, session_id, choice_id, candidate_ids, rationale, display=None):
        state = self._session(session_id)
        if not candidate_ids:
            preview = inspect_catalog(self.project, state["catalog"])
            if choice_id not in {item["choice_id"] for item in preview["choices"]}:
                raise PaperDeltaError("BATCH_SELECTION", msg("batch.selection"))
            selected = [item for item in state["selections"] if item["choice_id"] != choice_id]
        else:
            selected = [
                item
                for item in state["selections"]
                if not (
                    item["choice_id"] == choice_id
                    and fingerprint(item.get("display")) == fingerprint(display)
                )
            ]
            selected.append(
                {
                    "choice_id": choice_id,
                    "candidate_ids": candidate_ids,
                    "rationale": rationale,
                    "display": display,
                }
            )
            # Invalid choices never replace an earlier valid selection.
            build_proposal(self.project, state["catalog"], selected)
        state["selections"] = selected
        return {
            "status": "draft",
            "session_id": session_id,
            "selected_locations": sum(len(item["candidate_ids"]) for item in selected),
            "next": msg("batch.agent_finish"),
        }

    def finish(self, session_id):
        state = self._session(session_id)
        proposal = build_proposal(self.project, state["catalog"], state["selections"])
        return {
            "status": "proposed",
            "proposal_id": proposal["proposal_id"],
            "proposal_json": json_text(proposal),
            "next": msg("agent.next_binding"),
        }
