"""Joined revision tasks and explicit text-patch transactions for local Studio."""

from __future__ import annotations

import difflib
from typing import Literal

from pydantic import Field

from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.models import Hash, Identifier, StrictModel
from paperdelta.patches import (
    Transaction,
    _safe_changes,
    _transaction_path,
    apply_patch,
    create_patch,
    preview_patch,
    recover_transaction,
)
from paperdelta.records import validate_record
from paperdelta.revisions import revision_list
from paperdelta.storage import fingerprint, parse_json, sha256


class PatchSelection(StrictModel):
    occurrences: list[Identifier] = Field(min_length=1, max_length=500)


class PatchAcceptance(StrictModel):
    preview_id: Hash
    attest: Literal[True]


class TransactionSelection(StrictModel):
    transaction_id: str = Field(pattern=r"^[a-f0-9]{32}$")


def revision_tasks(report, positions):
    tasks = []
    for item in revision_list(report):
        item = dict(item)
        item["patchable"] = False
        item["annotatable"] = False
        item["patch_blocked_by"] = []
        kind, _, name = item["subject"].partition(":")
        if kind == "occurrence":
            state = report["occurrences"][name]
            item["annotatable"] = bool(
                (state.get("location") or {}).get("format") in {"docx", "pdf"}
                and isinstance(state.get("actual"), str)
            )
            suggestion = state.get("suggestion") or {}
            item["patch_blocked_by"] = suggestion.get("blocked_by", [])
            if state["status"] == "mismatch":
                try:
                    item["patchable"] = bool(_safe_changes(report, [name]))
                except PaperDeltaError as error:
                    item["patch_reason"] = error.message
            item["occurrence"] = name
        position = positions.get(("occurrences" if kind == "occurrence" else "claims") + ":" + name)
        if kind in {"occurrence", "claim"} and position:
            item["context"] = position["context"]
            item["position"] = position["label"]
        tasks.append(item)
    return tasks


def transaction_summaries(project):
    output = []
    for path in sorted(project.path(".paperdelta/transactions").glob("*/manifest.json")):
        try:
            record = validate_record(
                Transaction,
                parse_json(project.read(project.relative(path), 1024 * 1024).decode()),
                "TRANSACTION_SCHEMA",
            )
            if record.id != path.parent.name:
                raise PaperDeltaError("TRANSACTION_SCHEMA", msg("error.TRANSACTION_SCHEMA"))
            output.append(
                {
                    "id": record.id,
                    "status": record.status,
                    "created_at": record.created_at,
                    "files": [item.path for item in record.files],
                }
            )
        except PaperDeltaError as error:
            output.append({"id": path.parent.name, "error": error.code})
    return sorted(output, key=lambda item: item.get("created_at", ""), reverse=True)


def recovery_preview(project, transaction_id):
    result = recover_transaction(project, transaction_id)
    directory = _transaction_path(transaction_id)
    raw = project.read(directory + "/manifest.json", 1024 * 1024)
    record = validate_record(Transaction, parse_json(raw.decode()), "TRANSACTION_SCHEMA")
    hashes, diff = {}, []
    for item in record.files:
        current, original = project.read(item.path), project.read(item.backup)
        hashes[item.path] = sha256(current)
        diff.extend(
            difflib.unified_diff(
                current.decode("utf-8").splitlines(keepends=True),
                original.decode("utf-8").splitlines(keepends=True),
                fromfile="a/" + item.path,
                tofile="b/" + item.path,
            )
        )
    body = {**result, "manifest_hash": sha256(raw), "input_hashes": hashes, "diff": "".join(diff)}
    return {**body, "preview_id": fingerprint(body)}


def execute(session, action, parameters):
    if action == "patch-transactions":
        return {"transactions": transaction_summaries(session.project)}
    if action == "patch-preview":
        session._require_clean()
        report = check_project(session.project.root, session.config_path)
        value = create_patch(session.project, report, parameters["occurrences"])
        difference = preview_patch(session.project, value)
        session.numeric_patch = value
        return {"preview_id": value["patch_id"], "patch": value, "diff": difference}
    if action == "patch-apply":
        session._require_clean()
        value = getattr(session, "numeric_patch", None)
        if value is None or value["patch_id"] != parameters["preview_id"]:
            raise PaperDeltaError("STALE_PATCH", msg("error.STALE_PATCH"))
        result = apply_patch(session.project, value)
        session.numeric_patch = None
        session.receipt = {
            "workflow": "patch",
            "name": ", ".join(sorted({c["file"] for c in value["changes"]})),
            "backup": _transaction_path(result["transaction_id"]),
        }
        session._after_accept()
        return {
            "state": session.state(),
            "transaction_id": result["transaction_id"],
            "verification_exit_code": result["report"]["exit_code"],
        }
    # Recovery remains available when an interrupted source write made the clean
    # draft's original hashes stale. It must not discard unaccepted binding work.
    if session.draft and any(session.draft["additions"].values()):
        raise PaperDeltaError("STUDIO_STAGED", msg("studio.finish_draft"))
    if action == "patch-recover-preview":
        value = recovery_preview(session.project, parameters["transaction_id"])
        session.numeric_recovery = value
        return value
    value = getattr(session, "numeric_recovery", None)
    if value is None or value["preview_id"] != parameters["preview_id"]:
        raise PaperDeltaError("STALE_PATCH", msg("error.STALE_PATCH"))
    if recovery_preview(session.project, value["transaction_id"]) != value:
        raise PaperDeltaError("STALE_PATCH", msg("error.STALE_PATCH"))
    result = recover_transaction(session.project, value["transaction_id"], write=True)
    session.numeric_recovery = session.numeric_patch = None
    session.receipt = {
        "workflow": "patch-recovery",
        "name": ", ".join(result["files"]),
        "backup": _transaction_path(result["transaction_id"]),
    }
    session._after_accept()
    return {
        "state": session.state(),
        "transaction_id": result["transaction_id"],
        "status": result["status"],
    }
