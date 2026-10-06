"""Deterministic result fragments from explicitly accepted display contracts."""

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
from paperdelta.patches import _write_lock
from paperdelta.provenance import _safe_path
from paperdelta.records import TimestampedRecord, validate_record
from paperdelta.sources import EvidenceStore
from paperdelta.statistical_display import render_result
from paperdelta.storage import fingerprint, json_text, parse_json, sha256


class FragmentSpec(StrictModel):
    format: Literal["latex", "markdown"]
    path: str = Field(min_length=1, max_length=1000)
    occurrences: list[Identifier] = Field(min_length=1, max_length=128)
    layout: Literal["value", "table"] = "table"
    language: Literal["en", "zh-CN"] = "en"

    @model_validator(mode="after")
    def distinct(self):
        if len(set(self.occurrences)) != len(self.occurrences):
            raise ValueError(msg("fragments.selection"))
        if self.layout == "value" and len(self.occurrences) != 1:
            raise ValueError(msg("fragments.selection"))
        if not self.path.endswith(".tex" if self.format == "latex" else ".md"):
            raise ValueError(msg("fragments.extension"))
        return self


class FragmentValue(StrictModel):
    occurrence: Identifier
    metric: Identifier
    rendered: str
    evidence_fingerprint: Hash


class FragmentRecord(StrictModel):
    fragment_schema_version: VersionOne
    tool_version: str
    recorded_at: str
    spec: FragmentSpec
    contract: Hash
    inputs: dict[str, Hash]
    values: list[FragmentValue]
    output_hash: Hash
    record_id: Hash

    @field_validator("recorded_at")
    @classmethod
    def timestamp(cls, value):
        return TimestampedRecord.timestamp(value)

    @model_validator(mode="after")
    def complete(self):
        if [item.occurrence for item in self.values] != self.spec.occurrences:
            raise ValueError(msg("fragments.record"))
        return self


class FragmentProposal(StrictModel):
    fragment_proposal_schema_version: VersionOne
    tool_version: str
    name: Identifier
    config_path: str
    config_hash: Hash
    replace: bool
    previous_output_hash: Hash | None
    record: FragmentRecord
    content: str
    proposal_id: Hash


def _error(key):
    return PaperDeltaError("FRAGMENT_" + key.upper(), msg("fragments." + key))


def _render(project, config, spec):
    store = EvidenceStore(project, config)
    values, definitions, sources, displays = [], {}, {}, {}

    def dependencies(name):
        if name in definitions:
            return
        metric = config.metrics[name]
        definitions[name] = metric.model_dump()
        if hasattr(metric, "source"):
            sources[metric.source] = config.sources[metric.source].model_dump()
        else:
            for argument in metric.args:
                dependencies(argument)

    for name in spec.occurrences:
        if name not in config.occurrences:
            raise _error("selection")
        occurrence = config.occurrences[name]
        dependencies(occurrence.metric)
        displays[name] = {"metric": occurrence.metric, "display": occurrence.display.model_dump()}
        result = store.resolve(occurrence.metric)
        value = render_result(result, occurrence.display, config.rounding)
        if spec.format == "markdown":
            value = value.replace(r"\%", "%").replace(r"\pm", "±")
        elif r"\pm" in value:
            value = r"\ensuremath{" + value + "}"
        values.append(
            {
                "occurrence": name,
                "metric": occurrence.metric,
                "rendered": value,
                "evidence_fingerprint": result.fingerprint,
            }
        )
    contract = fingerprint(
        {
            "metrics": definitions,
            "sources": sources,
            "displays": displays,
            "rounding": config.rounding,
        }
    )
    if spec.layout == "value":
        content = values[0]["rendered"] + "\n"
    else:

        def escape(value):
            return value.replace("_", r"\_")

        heading = ("Binding", "Value") if spec.language == "en" else ("绑定", "数值")
        if spec.format == "markdown":
            content = f"| {heading[0]} | {heading[1]} |\n| --- | ---: |\n" + "".join(
                f"| {escape(item['occurrence'])} | {item['rendered']} |\n" for item in values
            )
        else:
            content = (
                "\\begin{tabular}{lr}\n"
                + " & ".join(heading)
                + " \\\\\n"
                + "".join(
                    f"{escape(item['occurrence'])} & {item['rendered']} \\\\\n" for item in values
                )
                + "\\end{tabular}\n"
            )
    for path, digest in store.hashes.items():
        if _safe_path(project, path) != path or sha256(project.read(path)) != digest:
            raise _error("stale")
    return content, contract, dict(store.hashes), values


def validate_fragment(value):
    record = validate_record(FragmentRecord, value, "FRAGMENT_RECORD")
    if record.record_id != fingerprint(record.model_dump(exclude={"record_id"})):
        raise _error("record")
    return record


def preview_fragment(
    project, name, spec, *, replace=False, config_path="paperdelta.yaml", recorded_at=None
):
    spec = validate_record(FragmentSpec, spec, "FRAGMENT_SPEC")
    config, config_hash = load_config(project, config_path)
    if (
        _safe_path(project, spec.path) != spec.path
        or _safe_path(project, config_path) != config_path
    ):
        raise _error("path")
    # Generated artifacts have their own destinations. Never overwrite accepted paper/data inputs.
    protected = {
        config_path,
        config.paper.entry,
        *(item.entry for item in config.paper.companions),
        *(item.path for item in config.sources.values()),
        *(item.path for item in config.figures.values()),
        *(item.record for item in config.figures.values() if item.record),
        *(item.record for item in config.provenance.values()),
        *(item.record for item in config.fragments.values()),
    }
    if spec.path.casefold().startswith(".paperdelta/") or spec.path in protected:
        raise _error("path")
    previous = config.fragments.get(name)
    if previous and not replace:
        raise _error("exists")
    content, contract, inputs, values = _render(project, config, spec)
    if spec.path in inputs:
        raise _error("path")
    current = None
    if project.path(spec.path).exists():
        if not previous or not replace:
            raise _error("exists")
        prior = validate_fragment(
            parse_json(project.read(previous.record, 4 * 1024 * 1024).decode())
        )
        if prior.spec.path != spec.path:
            raise _error("exists")
        current = sha256(project.read(spec.path))
        # Manual changes are never silently replaced by regeneration.
        if current != prior.output_hash:
            raise _error("edited")
    for other_name, reference in config.fragments.items():
        if other_name != name:
            prior = validate_fragment(
                parse_json(project.read(reference.record, 4 * 1024 * 1024).decode())
            )
            if prior.spec.path == spec.path:
                raise _error("exists")
    record = validate_record(
        FragmentRecord,
        {
            "fragment_schema_version": 1,
            "tool_version": __version__,
            "recorded_at": recorded_at or datetime.now(UTC).isoformat(),
            "spec": spec.model_dump(),
            "contract": contract,
            "inputs": inputs,
            "values": values,
            "output_hash": sha256(content.encode("utf-8")),
            "record_id": "sha256:" + "0" * 64,
        },
        "FRAGMENT_RECORD",
    )
    record.record_id = fingerprint(record.model_dump(exclude={"record_id"}))
    proposal = validate_record(
        FragmentProposal,
        {
            "fragment_proposal_schema_version": 1,
            "tool_version": __version__,
            "name": name,
            "config_path": config_path,
            "config_hash": config_hash,
            "replace": replace,
            "previous_output_hash": current,
            "record": record.model_dump(),
            "content": content,
            "proposal_id": "sha256:" + "0" * 64,
        },
        "FRAGMENT_PROPOSAL",
    )
    proposal.proposal_id = fingerprint(proposal.model_dump(exclude={"proposal_id"}))
    return proposal.model_dump()


def inspect_fragment(project, value):
    proposal = validate_record(FragmentProposal, value, "FRAGMENT_PROPOSAL")
    expected = preview_fragment(
        project,
        proposal.name,
        proposal.record.spec.model_dump(),
        replace=proposal.replace,
        config_path=proposal.config_path,
        recorded_at=proposal.record.recorded_at,
    )
    if expected != proposal.model_dump():
        raise _error("stale")
    return proposal


def accept_fragment(project, value):
    with _write_lock(project):
        proposal = inspect_fragment(project, value)
        config, _ = load_config(project, proposal.config_path)
        record = proposal.record
        record_path = ".paperdelta/fragments/" + record.record_id.split(":")[1] + ".json"
        raw = json_text(record.model_dump()).encode("utf-8")
        if project.path(record_path).exists():
            if project.read(record_path) != raw:
                raise _error("record")
        else:
            project.write(record_path, raw, exclusive=True)
        backup = ".paperdelta/fragment-backups/" + uuid.uuid4().hex
        project.write(backup + "/config.yaml", project.read(proposal.config_path), exclusive=True)
        if proposal.previous_output_hash is not None:
            project.write(backup + "/output", project.read(record.spec.path), exclusive=True)
        inspect_fragment(project, value)
        project.write(
            record.spec.path,
            proposal.content.encode("utf-8"),
            exclusive=proposal.previous_output_hash is None,
        )
        config.schema_version = 10
        config.fragments[proposal.name] = ProvenanceReference(record=record_path)
        project.write(proposal.config_path, config_text(config).encode("utf-8"))
    return {
        "status": "accepted",
        "name": proposal.name,
        "path": record.spec.path,
        "record": record_path,
        "backup": backup,
    }


def fragment_state(project, config, value):
    record = validate_fragment(value)
    content, contract, inputs, values = _render(project, config, record.spec)
    actual = sha256(project.read(record.spec.path))
    if _safe_path(project, record.spec.path) != record.spec.path:
        raise _error("path")
    changed = sorted(
        path
        for path in inputs.keys() | record.inputs.keys()
        if inputs.get(path) != record.inputs.get(path)
    )
    if actual != record.output_hash:
        changed.append(record.spec.path)
    stale = bool(
        changed
        or contract != record.contract
        or values != [v.model_dump() for v in record.values]
        or sha256(content.encode("utf-8")) != actual
    )
    return {
        "status": "mismatch" if stale else "pass",
        "path": record.spec.path,
        "format": record.spec.format,
        "occurrences": record.spec.occurrences,
        "metrics": sorted({item["metric"] for item in values}),
        "changed_paths": changed,
        "contract_changed": contract != record.contract,
        "identities": {**inputs, record.spec.path: actual},
    }
