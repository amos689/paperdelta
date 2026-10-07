"""Explicit, reviewed input/output declarations; checking never executes producers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_validator, model_validator

from paperdelta import __version__
from paperdelta.config import config_text, load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.models import Hash, Identifier, ProvenanceReference, StrictModel, VersionOne
from paperdelta.notebooks import inspect_notebook
from paperdelta.patches import _write_lock
from paperdelta.records import TimestampedRecord, validate_record
from paperdelta.storage import fingerprint, json_text, sha256


class ProducerSpec(StrictModel):
    kind: Literal["notebook", "quarto"]
    source: str
    inputs: list[str] = Field(max_length=128)
    outputs: list[str] = Field(min_length=1, max_length=128)
    cells: list[str] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def declared_paths(self):
        paths = [self.source, *self.inputs, *self.outputs]
        if len(set(paths)) != len(paths) or len(set(self.cells)) != len(self.cells):
            raise ValueError(msg("provenance.distinct"))
        if (self.kind == "notebook") != bool(self.cells):
            raise ValueError(msg("provenance.cells"))
        if not self.source.lower().endswith(".ipynb" if self.kind == "notebook" else ".qmd"):
            raise ValueError(msg("provenance.source"))
        return self


class SavedCell(StrictModel):
    id: str
    index: int = Field(ge=1)
    source_hash: Hash
    outputs_hash: Hash
    execution_count: int | None = Field(ge=0)
    status: Literal["saved_outputs", "unexecuted", "saved_error", "unsupported_output"]


class ProducerRequest(StrictModel):
    name: Identifier
    spec: ProducerSpec
    rationale: str = Field(min_length=1, max_length=4000)
    replace: bool = False

    @model_validator(mode="after")
    def meaningful_reason(self):
        if not self.rationale.strip():
            raise ValueError(msg("provenance.rationale"))
        return self


class CommandObservation(StrictModel):
    command: list[str] = Field(min_length=1, max_length=128)
    started_at: str
    finished_at: str
    exit_code: Literal[0]
    input_hashes_before: dict[str, Hash]
    source_hash_before: Hash
    stdout_hash: Hash
    stderr_hash: Hash

    @field_validator("started_at", "finished_at")
    @classmethod
    def timestamp(cls, value):
        return TimestampedRecord.timestamp(value)

    @model_validator(mode="after")
    def ordered(self):
        if datetime.fromisoformat(self.finished_at) < datetime.fromisoformat(self.started_at):
            raise ValueError(msg("provenance.record"))
        if not self.command[0] or any(
            "\x00" in argument or len(argument) > 8192 for argument in self.command
        ):
            raise ValueError(msg("provenance.command"))
        return self


class ProducerRecord(StrictModel):
    producer_schema_version: VersionOne
    tool_version: str
    recorded_at: str
    spec: ProducerSpec
    identities: dict[str, Hash]
    cells: list[SavedCell]
    method: Literal["declared", "observed_command"]
    observation: CommandObservation | None = None
    rationale: str = Field(min_length=1, max_length=4000)
    record_id: Hash

    @field_validator("recorded_at")
    @classmethod
    def timestamp(cls, value):
        return TimestampedRecord.timestamp(value)

    @model_validator(mode="after")
    def complete_identity(self):
        if set(self.identities) != {self.spec.source, *self.spec.inputs, *self.spec.outputs}:
            raise ValueError(msg("provenance.record"))
        if [cell.id for cell in self.cells] != self.spec.cells:
            raise ValueError(msg("provenance.record"))
        if (self.method == "observed_command") != (self.observation is not None):
            raise ValueError(msg("provenance.record"))
        if self.observation and self.observation.input_hashes_before != {
            name: self.identities[name] for name in self.spec.inputs
        }:
            raise ValueError(msg("provenance.record"))
        if self.observation and (
            datetime.fromisoformat(self.recorded_at)
            < datetime.fromisoformat(self.observation.finished_at)
            or (
                self.spec.kind == "quarto"
                and self.observation.source_hash_before != self.identities[self.spec.source]
            )
        ):
            raise ValueError(msg("provenance.record"))
        if not self.rationale.strip():
            raise ValueError(msg("provenance.rationale"))
        return self


class ProducerProposal(StrictModel):
    producer_proposal_schema_version: VersionOne
    tool_version: str
    config_path: str
    config_hash: Hash
    name: Identifier
    replace: bool
    record: ProducerRecord
    proposal_id: Hash


def _error(key):
    return PaperDeltaError("PROVENANCE_" + key.upper(), msg("provenance." + key))


def _safe_path(project, path):
    value = project.relative(project.path(path))
    if ".git" in {part.casefold() for part in value.split("/")}:
        raise _error("private")
    return value


def _identities(project, spec):
    paths = [spec.source, *spec.inputs, *spec.outputs]
    canonical = [_safe_path(project, path) for path in paths]
    if paths != canonical or len(set(canonical)) != len(paths):
        raise _error("distinct")
    return {path: sha256(project.read(path)) for path in paths}


def _cells(project, spec):
    if spec.kind != "notebook":
        return []
    notebook = inspect_notebook(project, spec.source)
    by_id = {cell["id"]: cell for cell in notebook["cells"] if cell["cell_type"] == "code"}
    if not set(spec.cells) <= by_id.keys():
        raise _error("cells")
    return [
        SavedCell(**{key: by_id[name][key] for key in SavedCell.model_fields})
        for name in spec.cells
    ]


def producer_record(project, spec, rationale, *, observation=None):
    spec = validate_record(ProducerSpec, spec, "PROVENANCE_SPEC")
    identities = _identities(project, spec)
    cells = _cells(project, spec)
    if _identities(project, spec) != identities:
        raise _error("stale")
    record = validate_record(
        ProducerRecord,
        dict(
            producer_schema_version=1,
            tool_version=__version__,
            recorded_at=datetime.now(UTC).isoformat(),
            spec=spec,
            identities=identities,
            cells=cells,
            method="observed_command" if observation else "declared",
            observation=observation,
            rationale=rationale,
            record_id="sha256:" + "0" * 64,
        ),
        "PROVENANCE_RECORD",
    )
    record.record_id = fingerprint(record.model_dump(exclude={"record_id"}))
    return record.model_dump()


def validate_producer(value):
    record = validate_record(ProducerRecord, value, "PROVENANCE_RECORD")
    if record.record_id != fingerprint(record.model_dump(exclude={"record_id"})):
        raise _error("record")
    return record


def propose_producer(project, name, record, *, replace=False, config_path="paperdelta.yaml"):
    record = validate_producer(record)
    config_path = _safe_path(project, config_path)
    config, identity = load_config(project, config_path)
    if (name in config.provenance) and not replace:
        raise _error("exists")
    if config_path in record.identities:
        raise _error("config_dependency")
    if (
        _identities(project, record.spec) != record.identities
        or _cells(project, record.spec) != record.cells
    ):
        raise _error("stale")
    proposal = validate_record(
        ProducerProposal,
        dict(
            producer_proposal_schema_version=1,
            tool_version=__version__,
            config_path=config_path,
            config_hash=identity,
            name=name,
            replace=replace,
            record=record,
            proposal_id="sha256:" + "0" * 64,
        ),
        "PROVENANCE_PROPOSAL",
    )
    proposal.proposal_id = fingerprint(proposal.model_dump(exclude={"proposal_id"}))
    return proposal.model_dump()


def inspect_producer_proposal(project, value):
    proposal = validate_record(ProducerProposal, value, "PROVENANCE_PROPOSAL")
    if proposal.tool_version != __version__ or proposal.proposal_id != fingerprint(
        proposal.model_dump(exclude={"proposal_id"})
    ):
        raise _error("record")
    expected = propose_producer(
        project,
        proposal.name,
        proposal.record.model_dump(),
        replace=proposal.replace,
        config_path=proposal.config_path,
    )
    if expected != proposal.model_dump():
        raise _error("stale")
    return proposal


def accept_producer(project, value):
    with _write_lock(project):
        proposal = inspect_producer_proposal(project, value)
        config, _ = load_config(project, proposal.config_path)
        path = ".paperdelta/provenance/" + proposal.record.record_id.split(":")[1] + ".json"
        if path in proposal.record.identities or path == proposal.config_path:
            raise _error("config_dependency")
        raw = json_text(proposal.record.model_dump()).encode("utf-8")
        if project.path(path).exists():
            if project.read(path) != raw:
                raise _error("record")
        else:
            project.write(path, raw, exclusive=True)
        backup = f".paperdelta/config-backups/{uuid.uuid4().hex}.yaml"
        project.write(backup, project.read(proposal.config_path), exclusive=True)
        inspect_producer_proposal(project, value)
        config.schema_version = 10
        config.provenance[proposal.name] = ProvenanceReference(record=path)
        project.write(proposal.config_path, config_text(config).encode("utf-8"))
    return {"status": "accepted", "name": proposal.name, "record": path, "backup": backup}


def producer_state(project, value):
    record = validate_producer(value)
    current = _identities(project, record.spec)
    changed = [path for path, digest in current.items() if digest != record.identities[path]]
    cells = _cells(project, record.spec)
    changed_cells = [
        {
            "id": before.id,
            "code_changed": before.source_hash != after.source_hash,
            "outputs_changed": before.outputs_hash != after.outputs_hash,
            "execution_count_changed": before.execution_count != after.execution_count,
        }
        for before, after in zip(record.cells, cells, strict=True)
        if before != after
    ]
    unresolved = [cell.id for cell in cells if cell.status != "saved_outputs"]
    return {
        "status": "unknown" if unresolved else "mismatch" if changed or changed_cells else "pass",
        "kind": record.spec.kind,
        "source": record.spec.source,
        "inputs": record.spec.inputs,
        "outputs": record.spec.outputs,
        "method": record.method,
        "changed_paths": changed,
        "cells": changed_cells,
        "unverified_cells": unresolved,
        "identities": current,
        "observed_command": record.observation.command if record.observation else None,
        "notice": msg(
            "provenance.declared" if record.method == "declared" else "provenance.observed"
        ),
    }
