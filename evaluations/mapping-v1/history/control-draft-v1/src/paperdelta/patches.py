"""Re-derived numeric patches and recoverable, guarded multi-file writes."""

from __future__ import annotations

import difflib
import os
import re
import uuid
from contextlib import contextmanager, nullcontext
from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import Field, ValidationError, model_validator

from paperdelta import __version__
from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.models import Hash, StrictModel, VersionOne
from paperdelta.records import TimestampedRecord, validate_record
from paperdelta.storage import Project, fingerprint, json_text, parse_json, sha256


class Change(StrictModel):
    occurrence: str
    file: str
    byte_start: Annotated[int, Field(ge=0)]
    byte_end: Annotated[int, Field(ge=1)]
    original: str
    replacement: str

    @model_validator(mode="after")
    def valid_range(self):
        if self.byte_end <= self.byte_start or not self.file.endswith(".tex"):
            raise ValueError("Changes must cover a nonempty range in a .tex file")
        return self


class Patch(StrictModel):
    patch_schema_version: VersionOne
    tool_version: str
    config_path: str
    input_hashes: dict[str, Hash]
    changes: Annotated[list[Change], Field(min_length=1)]
    patch_id: Hash


class TransactionFile(StrictModel):
    path: str
    before_hash: Hash
    after_hash: Hash
    backup: str


class Transaction(TimestampedRecord):
    transaction_schema_version: VersionOne
    id: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
    patch_id: Hash
    status: Literal["prepared", "applying", "applied", "interrupted", "recovering", "reverted"]
    files: Annotated[list[TransactionFile], Field(min_length=1)]
    verification_exit_code: Literal[0, 1, 2] | None = None
    error: str | None = None

    @model_validator(mode="after")
    def valid_files(self):
        if len({item.path for item in self.files}) != len(self.files):
            raise ValueError("Transaction must not repeat files")
        for index, item in enumerate(self.files):
            if item.backup != f".paperdelta/transactions/{self.id}/backups/{index}.bin":
                raise ValueError("Unexpected backup path")
            if not item.path.endswith(".tex"):
                raise ValueError("Transactions only write .tex files")
        return self


def _safe_changes(report: dict, selected: list[str] | None = None) -> list[dict]:
    names = selected if selected is not None else sorted(report["occurrences"])
    if len(names) != len(set(names)):
        raise PaperDeltaError("PATCH_SELECTION", "Do not repeat occurrence IDs")
    changes = []
    for name in names:
        if name not in report["occurrences"]:
            raise PaperDeltaError("PATCH_SELECTION", f"Unknown occurrence {name}")
        state = report["occurrences"][name]
        suggestion = state.get("suggestion")
        if state["status"] != "mismatch" or suggestion is None:
            if selected is not None:
                raise PaperDeltaError("NOT_FIXABLE", f"{name} has no numeric fix")
            continue
        if suggestion["blocked_by"]:
            if selected is not None:
                raise PaperDeltaError(
                    "CLAIM_REVIEW_REQUIRED", f"{name}: review {suggestion['blocked_by']} first"
                )
            continue
        span = state["location"]
        changes.append(
            {
                "occurrence": name,
                "file": span["file"],
                "byte_start": span["byte_start"],
                "byte_end": span["byte_end"],
                "original": span["text"],
                "replacement": suggestion["replacement"],
            }
        )
    return sorted(changes, key=lambda item: (item["file"], item["byte_start"], item["occurrence"]))


def create_patch(project: Project, report: dict, selected: list[str] | None = None) -> dict:
    if (
        not isinstance(report, dict)
        or type(report.get("report_schema_version")) is not int
        or report.get("report_schema_version") != 1
    ):
        raise PaperDeltaError("REPORT_SCHEMA", "Expected a version 1 report")
    config_path = report.get("config_path")
    if not isinstance(config_path, str):
        raise PaperDeltaError("REPORT_SCHEMA", "Report must identify its project configuration")
    current = check_project(project.root, config_path)
    if report.get("input_hashes") != current["input_hashes"]:
        raise PaperDeltaError("STALE_REPORT", "Inputs changed since the report; check again")
    # Derive every replacement again. Edited report suggestions have no authority.
    changes = _safe_changes(current, selected)
    if not changes:
        raise PaperDeltaError(
            "NO_SAFE_FIXES", "No independent numeric fixes; review related claims or unknowns first"
        )
    body = {
        "patch_schema_version": 1,
        "tool_version": __version__,
        "config_path": config_path,
        "input_hashes": current["input_hashes"],
        "changes": changes,
    }
    patch = Patch.model_validate({**body, "patch_id": fingerprint(body)})
    _replacement_files(project, patch)
    return patch.model_dump()


def _load_patch(value: dict) -> Patch:
    try:
        patch = Patch.model_validate(value)
    except ValidationError as exc:
        raise PaperDeltaError("PATCH_SCHEMA", str(exc)) from exc
    body = patch.model_dump(exclude={"patch_id"})
    if patch.patch_id != fingerprint(body) or patch.tool_version != __version__:
        raise PaperDeltaError(
            "PATCH_IDENTITY", "Patch is damaged or belongs to another tool version"
        )
    return patch


def _validate_current(project: Project, patch: Patch) -> dict:
    current = check_project(project.root, patch.config_path)
    if current["input_hashes"] != patch.input_hashes:
        raise PaperDeltaError(
            "STALE_PATCH", "Paper, configuration or evidence changed; generate a new patch"
        )
    selected = [item.occurrence for item in patch.changes]
    expected = _safe_changes(current, selected)
    if expected != [item.model_dump() for item in patch.changes]:
        raise PaperDeltaError(
            "PATCH_NOT_DERIVED", "Patch does not match currently verified numeric fixes"
        )
    return current


def _replacement_files(project: Project, patch: Patch) -> dict[str, tuple[bytes, bytes]]:
    result = {}
    for file in sorted({item.file for item in patch.changes}):
        before = project.read(file)
        if sha256(before) != patch.input_hashes.get(file):
            raise PaperDeltaError("STALE_PATCH", f"{file} changed")
        after = before
        previous_start = len(before)
        changes = sorted(
            (item for item in patch.changes if item.file == file),
            key=lambda item: item.byte_start,
            reverse=True,
        )
        for item in changes:
            if item.byte_end > previous_start:
                raise PaperDeltaError("PATCH_OVERLAP", f"Overlapping edits in {file}")
            if before[item.byte_start : item.byte_end] != item.original.encode("utf-8"):
                raise PaperDeltaError("STALE_PATCH", f"Original bytes no longer match in {file}")
            after = (
                after[: item.byte_start] + item.replacement.encode("utf-8") + after[item.byte_end :]
            )
            previous_start = item.byte_start
        result[file] = before, after
    return result


def preview_patch(project: Project, value: dict) -> str:
    patch = _load_patch(value)
    _validate_current(project, patch)
    output = []
    for file, (before, after) in _replacement_files(project, patch).items():
        output.extend(
            difflib.unified_diff(
                before.decode("utf-8").splitlines(keepends=True),
                after.decode("utf-8").splitlines(keepends=True),
                fromfile=f"a/{file}",
                tofile=f"b/{file}",
            )
        )
    return "".join(output)


@contextmanager
def _write_lock(project: Project):
    path = project.path(".paperdelta/transactions.lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        if path.stat().st_size == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise PaperDeltaError("WRITE_LOCKED", "Another PaperDelta write is active") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _transaction_path(transaction_id: str) -> str:
    if not re.fullmatch(r"[a-f0-9]{32}", transaction_id):
        raise PaperDeltaError("TRANSACTION_ID", "Invalid transaction ID")
    return f".paperdelta/transactions/{transaction_id}"


def _require_no_pending(project: Project) -> None:
    for path in project.path(".paperdelta/transactions").glob("*/manifest.json"):
        text, _ = project.text(project.relative(path))
        record = parse_json(text)
        validate_record(Transaction, record, "TRANSACTION_SCHEMA")
        if record["id"] != path.parent.name:
            raise PaperDeltaError("TRANSACTION_SCHEMA", "Transaction directory and ID disagree")
        if record.get("status") not in {"applied", "reverted"}:
            raise PaperDeltaError(
                "RECOVERY_REQUIRED", f"Recover transaction {path.parent.name} first"
            )


def apply_patch(project: Project, value: dict) -> dict:
    patch = _load_patch(value)
    with _write_lock(project):
        _require_no_pending(project)
        _validate_current(project, patch)
        files = _replacement_files(project, patch)
        transaction_id = uuid.uuid4().hex
        directory = _transaction_path(transaction_id)
        record = {
            "transaction_schema_version": 1,
            "id": transaction_id,
            "patch_id": patch.patch_id,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "prepared",
            "files": [],
        }
        for index, (file, (before, after)) in enumerate(files.items()):
            backup = f"{directory}/backups/{index}.bin"
            project.write(backup, before, exclusive=True)
            record["files"].append(
                {
                    "path": file,
                    "before_hash": sha256(before),
                    "after_hash": sha256(after),
                    "backup": backup,
                }
            )

        def save() -> None:
            validate_record(Transaction, record, "TRANSACTION_SCHEMA")
            project.write(f"{directory}/manifest.json", json_text(record).encode("utf-8"))

        save()
        try:
            record["status"] = "applying"
            save()
            for file, (before, after) in files.items():
                if project.read(file) != before:
                    raise PaperDeltaError("CONCURRENT_EDIT", f"{file} changed before its write")
                project.write(file, after)
            verification = check_project(project.root, patch.config_path)
            expected_hashes = dict(patch.input_hashes)
            expected_hashes.update({file: sha256(after) for file, (_, after) in files.items()})
            if verification["input_hashes"] != expected_hashes:
                raise PaperDeltaError("PATCH_VERIFICATION", "Inputs changed during the transaction")
            for item in patch.changes:
                if verification["occurrences"].get(item.occurrence, {}).get("status") != "pass":
                    raise PaperDeltaError(
                        "PATCH_VERIFICATION", f"{item.occurrence} did not pass after writing"
                    )
            record["status"] = "applied"
            record["verification_exit_code"] = verification["exit_code"]
            save()
        except Exception as exc:
            record["status"] = "interrupted"
            record["error"] = str(exc)
            try:
                save()
            except OSError:
                pass  # The previous durable prepared/applying journal still requires recovery.
            raise PaperDeltaError(
                "TRANSACTION_INTERRUPTED",
                f"Recover {transaction_id}: {exc}",
            ) from exc
        return {"transaction_id": transaction_id, "status": "applied", "report": verification}


def recover_transaction(project: Project, transaction_id: str, *, write: bool = False) -> dict:
    directory = _transaction_path(transaction_id)
    with _write_lock(project) if write else nullcontext():
        text, _ = project.text(f"{directory}/manifest.json")
        record = parse_json(text)
        validate_record(Transaction, record, "TRANSACTION_SCHEMA")
        if record["id"] != transaction_id:
            raise PaperDeltaError("TRANSACTION_SCHEMA", "Invalid transaction manifest")
        restore: list[tuple[str, bytes, str]] = []
        resolved_paths = [project.path(item["path"]) for item in record["files"]]
        if len(set(resolved_paths)) != len(resolved_paths):
            raise PaperDeltaError("TRANSACTION_SCHEMA", "File aliases overlap in transaction")
        for index, item in enumerate(record["files"]):
            expected_backup = f"{directory}/backups/{index}.bin"
            if item["backup"] != expected_backup or not item["path"].endswith(".tex"):
                raise PaperDeltaError("TRANSACTION_SCHEMA", "Invalid backup path or file type")
            backup = project.read(expected_backup)
            if sha256(backup) != item["before_hash"]:
                raise PaperDeltaError("BACKUP_CHANGED", f"Backup for {item['path']} was modified")
            current = sha256(project.read(item["path"]))
            if current not in (item["before_hash"], item["after_hash"]):
                raise PaperDeltaError(
                    "RECOVERY_CONFLICT", f"{item['path']} has later edits; no files restored"
                )
            restore.append((item["path"], backup, current))
        if not write:
            return {
                "transaction_id": transaction_id,
                "status": "preview",
                "files": [item[0] for item in restore],
            }
        record["status"] = "recovering"
        project.write(f"{directory}/manifest.json", json_text(record).encode("utf-8"))
        for path, backup, expected in restore:
            if sha256(project.read(path)) != expected:
                raise PaperDeltaError("RECOVERY_CONFLICT", f"{path} changed during recovery")
            project.write(path, backup)
        record["status"] = "reverted"
        project.write(f"{directory}/manifest.json", json_text(record).encode("utf-8"))
        return {
            "transaction_id": transaction_id,
            "status": "reverted",
            "files": [item[0] for item in restore],
        }
