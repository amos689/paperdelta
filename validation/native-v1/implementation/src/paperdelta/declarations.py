"""Previewed maintenance of accepted declarations, with dependency-aware writes."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Literal

from pydantic import Field, model_validator

from paperdelta import __version__
from paperdelta.analysis import check_configuration, check_project
from paperdelta.config import config_text, load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.models import Config, Identifier, StrictModel, VersionOne
from paperdelta.patches import _write_lock
from paperdelta.records import validate_record
from paperdelta.storage import fingerprint, json_text, parse_json, sha256

Group = Literal["sources", "metrics", "occurrences", "claims", "figures"]


def declaration_fields(definition, path=()):
    fields = []
    for name, value in definition.items():
        pointer = [*path, name]
        if isinstance(value, dict) and name != "anchor" and len(path) < 2 and value:
            fields.extend(declaration_fields(value, pointer))
            continue
        kind = (
            "boolean"
            if isinstance(value, bool)
            else "string"
            if isinstance(value, str)
            else "number"
            if isinstance(value, (int, Decimal))
            else "json"
        )
        fields.append({"path": pointer, "kind": kind, "json": json_text(value)})
    return fields


def field_replacement(project, group, name, fields, *, config_path="paperdelta.yaml"):
    config, _ = load_config(project, config_path)
    entries = getattr(config, group)
    if name not in entries:
        raise PaperDeltaError("MAINTENANCE_SELECTION", msg("maintenance.missing", name=name))
    definition = entries[name].model_dump()
    selected = set()
    for field in fields:
        pointer = tuple(field["path"])
        if not pointer or pointer in selected:
            raise PaperDeltaError("MAINTENANCE_SELECTION", msg("maintenance.distinct"))
        selected.add(pointer)
        current = definition
        for key in pointer[:-1]:
            if not isinstance(current, dict) or key not in current:
                raise PaperDeltaError("MAINTENANCE_SCHEMA", msg("maintenance.object"))
            current = current[key]
        if not isinstance(current, dict) or pointer[-1] not in current:
            raise PaperDeltaError("MAINTENANCE_SCHEMA", msg("maintenance.object"))
        current[pointer[-1]] = parse_json(field["value_json"])
    return json_text(definition)


class DeclarationEdit(StrictModel):
    group: Group
    name: Identifier
    operation: Literal["replace", "remove"]
    # A JSON string travels through the browser without rounding long decimals.
    definition_json: str | None = Field(default=None, max_length=150000)
    rationale: str = Field(min_length=1, max_length=4000)

    @model_validator(mode="after")
    def meaningful(self):
        if not self.rationale.strip() or (self.operation == "replace") != (
            self.definition_json is not None
        ):
            raise ValueError(msg("maintenance.edit_required"))
        return self


class DeclarationProposal(StrictModel):
    maintenance_schema_version: VersionOne
    tool_version: str
    config_path: str
    input_identities: dict[str, str]
    edits: list[DeclarationEdit] = Field(min_length=1, max_length=200)
    proposal_id: str


def observe(project, paths):
    """Track absent inputs too: a file appearing after preview changes its identity."""
    result = {}
    for path in sorted(set(paths)):
        path = project.relative(project.path(path))
        try:
            result[path] = sha256(project.read(path))
        except PaperDeltaError as exc:
            if exc.code != "FILE_UNAVAILABLE":
                raise
            result[path] = "unavailable:" + exc.code
    return result


def dependents(config, identities):
    edges = {}
    for name, metric in config.metrics.items():
        edges[f"metrics:{name}"] = (
            {f"metrics:{item}" for item in metric.args}
            if hasattr(metric, "args")
            else {f"sources:{metric.source}"}
        )
    for name, item in config.occurrences.items():
        edges[f"occurrences:{name}"] = {f"metrics:{item.metric}"}
    for name, item in config.claims.items():
        refs = [item.predicate.left, *item.predicate.candidates]
        if isinstance(item.predicate.right, str):
            refs.append(item.predicate.right)
        edges[f"claims:{name}"] = {f"metrics:{item}" for item in refs}
    related = set(identities)
    while True:
        added = {name for name, inputs in edges.items() if inputs & related} - related
        if not added:
            return sorted(related)
        related.update(added)


def _paths(config, report, config_path):
    paths = {config_path, *report["input_hashes"]}
    paths.update(source.path for source in config.sources.values())
    for figure in config.figures.values():
        paths.add(figure.path)
        if figure.record:
            paths.add(figure.record)
    paths.update(item.entry for item in [config.paper, *config.paper.companions])
    return paths


def affected_declarations(config, report, identities):
    related = set(dependents(config, identities))
    paths = {
        config.sources[name].path
        for group, name in (identity.split(":", 1) for identity in related)
        if group == "sources" and name in config.sources
    }
    for group in report["impact_groups"]:
        if related.intersection("metrics:" + name for name in group["metrics"]):
            paths.update(group["sources"])
    related.update(
        "figures:" + name
        for name, state in report["figures"].items()
        if paths.intersection(state.get("dependencies", []))
    )
    return related


def _derive(project, edits, config_path):
    original, identity = load_config(project, config_path)
    before = check_configuration(project, original, config_path, identity)
    observed = observe(project, _paths(original, before, config_path))
    identities = [f"{edit.group}:{edit.name}" for edit in edits]
    if not edits or len(set(identities)) != len(identities):
        raise PaperDeltaError("MAINTENANCE_SELECTION", msg("maintenance.distinct"))
    value = original.model_dump()
    changes = []
    for edit in edits:
        entries = value[edit.group]
        if edit.name not in entries:
            raise PaperDeltaError(
                "MAINTENANCE_SELECTION", msg("maintenance.missing", name=edit.name)
            )
        previous = entries[edit.name]
        replacement = parse_json(edit.definition_json) if edit.operation == "replace" else None
        if replacement is not None and not isinstance(replacement, dict):
            raise PaperDeltaError("MAINTENANCE_SCHEMA", msg("maintenance.object"))
        if edit.operation == "replace":
            if replacement == previous:
                raise PaperDeltaError("MAINTENANCE_UNCHANGED", msg("maintenance.unchanged"))
            entries[edit.name] = replacement
        else:
            del entries[edit.name]
        changes.append(
            {
                "id": f"{edit.group}:{edit.name}",
                "operation": edit.operation,
                "before": previous,
                "after": replacement,
                "rationale": edit.rationale,
            }
        )
    # This validates references and cycles, including references to removed definitions.
    if any(metric.get("statistics") for metric in value["metrics"].values()):
        value["schema_version"] = max(6, value["schema_version"])
    from paperdelta.config_versions import upgrade_layout_schema

    upgrade_layout_schema(value)
    proposed = validate_record(Config, value, "MAINTENANCE_DEPENDENCY")
    config_target = project.path(config_path)
    if any(project.path(item.path) == config_target for item in proposed.sources.values()):
        raise PaperDeltaError("MAINTENANCE_INPUT", msg("maintenance.config_input"))
    preview = check_configuration(project, proposed, config_path, identity)
    for edit in edits:
        if edit.operation == "remove" or edit.group == "sources":
            continue
        status = preview.get(edit.group, {}).get(edit.name, {}).get("status")
        if status not in {"ok", "pass", "mismatch"}:
            raise PaperDeltaError(
                "MAINTENANCE_UNRESOLVED", msg("maintenance.unresolved", name=edit.name)
            )
        if edit.group == "occurrences":
            location = preview[edit.group][edit.name]["location"]
            for name, item in preview["occurrences"].items():
                other = item.get("location")
                if (
                    name != edit.name
                    and other
                    and location["file"] == other["file"]
                    and (location["start"] < other["end"] and other["start"] < location["end"])
                ):
                    raise PaperDeltaError("MAINTENANCE_OVERLAP", msg("maintenance.overlap"))
    after_observed = observe(project, _paths(proposed, preview, config_path))
    if any(after_observed.get(path, observed[path]) != observed[path] for path in observed):
        raise PaperDeltaError("STALE_MAINTENANCE", msg("maintenance.stale"))
    observed.update(after_observed)
    if observe(project, observed) != observed:
        raise PaperDeltaError("STALE_MAINTENANCE", msg("maintenance.stale"))
    affected = sorted(
        affected_declarations(original, before, identities)
        | affected_declarations(proposed, preview, identities)
    )
    states = []
    for subject in affected:
        group, name = subject.split(":", 1)
        if group == "sources":
            continue
        states.append(
            {
                "id": subject,
                "before": before.get(group, {}).get(name),
                "after": preview.get(group, {}).get(name),
            }
        )
    return (
        proposed,
        observed,
        {
            "changes": changes,
            "affected": affected,
            "states": states,
            "coverage_before": before["coverage"],
            "coverage_after": preview["coverage"],
            "preview": preview,
        },
    )


def propose_maintenance(project, edits, *, config_path="paperdelta.yaml"):
    choices = [validate_record(DeclarationEdit, edit, "MAINTENANCE_SCHEMA") for edit in edits]
    _, identities, preview = _derive(project, choices, config_path)
    body = {
        "maintenance_schema_version": 1,
        "tool_version": __version__,
        "config_path": project.relative(project.path(config_path)),
        "input_identities": identities,
        "edits": [edit.model_dump() for edit in choices],
    }
    proposal = validate_record(
        DeclarationProposal, {**body, "proposal_id": fingerprint(body)}, "MAINTENANCE_SCHEMA"
    ).model_dump()
    return proposal, preview


def inspect_maintenance(project, value):
    proposal = validate_record(DeclarationProposal, value, "MAINTENANCE_SCHEMA")
    if proposal.tool_version != __version__ or proposal.proposal_id != fingerprint(
        proposal.model_dump(exclude={"proposal_id"})
    ):
        raise PaperDeltaError("MAINTENANCE_IDENTITY", msg("maintenance.identity"))
    if observe(project, proposal.input_identities) != proposal.input_identities:
        raise PaperDeltaError("STALE_MAINTENANCE", msg("maintenance.stale"))
    config, identities, preview = _derive(project, proposal.edits, proposal.config_path)
    if identities != proposal.input_identities:
        raise PaperDeltaError("STALE_MAINTENANCE", msg("maintenance.stale"))
    return proposal, config, preview


def accept_maintenance(project, value):
    inspect_maintenance(project, value)
    with _write_lock(project):
        proposal, config, preview = inspect_maintenance(project, value)
        backup = f".paperdelta/config-backups/{uuid.uuid4().hex}.yaml"
        project.write(backup, project.read(proposal.config_path), exclusive=True)
        if observe(project, proposal.input_identities) != proposal.input_identities:
            raise PaperDeltaError("STALE_MAINTENANCE", msg("maintenance.stale"))
        project.write(proposal.config_path, config_text(config).encode("utf-8"))
    return {
        "status": "accepted",
        "proposal_id": proposal.proposal_id,
        "backup": backup,
        "changes": preview["changes"],
        "affected": preview["affected"],
        "coverage_before": preview["coverage_before"],
        "report": check_project(project.root, proposal.config_path),
    }
