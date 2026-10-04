"""Batch inspection, portable selection templates and ordinary proposal previews."""

from __future__ import annotations

from copy import deepcopy
from typing import Literal

from pydantic import Field

from paperdelta import builder
from paperdelta.batch import BatchRequest, build_proposal, create_catalog, inspect_catalog
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.locations import location_label
from paperdelta.models import ColumnType, Hash, Identifier, StrictModel, VersionOne
from paperdelta.onboarding import inspect_proposal
from paperdelta.patches import _write_lock
from paperdelta.records import validate_record
from paperdelta.storage import fingerprint, json_text, parse_json

TEMPLATE_DIRECTORY = ".paperdelta/studio/templates"
MAX_TEMPLATE_BYTES = 64 * 1024


class TemplateSource(StrictModel):
    format: Literal["csv"]
    columns: dict[str, ColumnType] = Field(min_length=1, max_length=100)
    primary_key: list[str] = Field(min_length=1, max_length=100)


class ExperimentTemplate(StrictModel):
    template_schema_version: VersionOne
    name: Identifier
    source_contract: TemplateSource
    request: BatchRequest
    template_id: Hash


def validate_template(value):
    template = validate_record(ExperimentTemplate, value, "STUDIO_TEMPLATE")
    if template.template_id != fingerprint(template.model_dump(exclude={"template_id"})):
        raise PaperDeltaError("STUDIO_TEMPLATE_IDENTITY", msg("studio.template_identity"))
    keys = template.source_contract.primary_key
    if len(set(keys)) != len(keys) or not set(keys) <= set(template.source_contract.columns):
        raise PaperDeltaError("STUDIO_TEMPLATE_SCHEMA", msg("studio.template_contract"))
    return template


def make_template(name, source, request):
    body = {
        "template_schema_version": 1,
        "name": name,
        "source_contract": {
            "format": source.format,
            "columns": source.columns,
            "primary_key": source.primary_key,
        },
        "request": request,
    }
    return validate_template({**body, "template_id": fingerprint(body)}).model_dump()


def save_template(project, value):
    template = validate_template(value)
    raw = json_text(template.model_dump()).encode("utf-8")
    if len(raw) > MAX_TEMPLATE_BYTES:
        raise PaperDeltaError("STUDIO_TEMPLATE_LIMIT", msg("studio.template_limit"))
    with _write_lock(project):
        directory = project.path(TEMPLATE_DIRECTORY)
        if directory.exists() and sum(1 for _ in directory.glob("*.json")) >= 100:
            raise PaperDeltaError("STUDIO_TEMPLATE_LIMIT", msg("studio.template_limit"))
        project.write(f"{TEMPLATE_DIRECTORY}/{template.name}.json", raw, exclusive=True)
    return template.model_dump()


def template_list(project):
    directory = project.path(TEMPLATE_DIRECTORY)
    names = sorted(directory.glob("*.json")) if directory.exists() else []
    items, errors = [], []
    for path in names[:100]:
        try:
            template = read_template(project, path.stem)
            items.append(template.model_dump())
        except PaperDeltaError as exc:
            errors.append({"name": path.stem, "code": exc.code, "message": exc.message})
    return {"templates": items, "errors": errors, "limited": len(names) > 100}


def read_template(project, name):
    # Validate the name independently; never turn a browser string into a path.
    from pydantic import TypeAdapter, ValidationError

    try:
        TypeAdapter(Identifier).validate_python(name, strict=True)
    except ValidationError as exc:
        raise PaperDeltaError("STUDIO_TEMPLATE_NAME", msg("studio.template_name")) from exc
    raw = project.read(f"{TEMPLATE_DIRECTORY}/{name}.json", MAX_TEMPLATE_BYTES)
    try:
        value = validate_template(parse_json(raw.decode("utf-8-sig")))
    except UnicodeError as exc:
        raise PaperDeltaError("STUDIO_TEMPLATE_SCHEMA", msg("studio.template_contract")) from exc
    if value.name != name:
        raise PaperDeltaError("STUDIO_TEMPLATE_IDENTITY", msg("studio.template_identity"))
    return value


def template_request(project, draft, value, source_name):
    template = validate_template(value)
    _, config = builder.resume_draft(project, draft)
    source = config.sources.get(source_name)
    contract = template.source_contract
    if (
        source is None
        or source.format != contract.format
        or source.primary_key != contract.primary_key
        or any(source.columns.get(key) != kind for key, kind in contract.columns.items())
    ):
        raise PaperDeltaError("STUDIO_TEMPLATE_SCHEMA", msg("studio.template_contract"))
    request = template.request.model_dump()
    request["source"] = source_name
    return request


def proposal_draft(project, current, value):
    """Validate exact original proposal identity before creating a recoverable draft."""
    old, _ = builder.resume_draft(project, current)
    if any(old.additions.model_dump().values()):
        raise PaperDeltaError("STUDIO_STAGED", msg("studio.finish_draft"))
    proposal, _, _ = inspect_proposal(project, value)
    if proposal.config_path != old.config_path:
        raise PaperDeltaError("STUDIO_DRAFT", msg("studio.draft_project"))
    body = old.model_dump(exclude={"draft_id"})
    body.update(additions=proposal.additions.model_dump(), rationale=proposal.rationale)
    return builder._seal(project, body, proposal.input_hashes)


def proposal_preview(project, proposal, candidates):
    parsed, _, report = inspect_proposal(project, proposal)
    positions = {(item["file"], item["start"], item["end"]): item for item in candidates}
    items = []
    for binding, rationale in parsed.rationale.items():
        group, name = binding.split(":", 1)
        entry = report[group][name]
        location = entry.get("location")
        candidate = (
            positions.get((location["file"], location["start"], location["end"]), {})
            if location
            else {}
        )
        definition = getattr(parsed.additions, group)[name].model_dump()
        items.append(
            {
                **entry,
                "binding": binding,
                "group": group,
                "rationale": rationale,
                "definition_json": json_text(definition),
                "label": location_label(location) if location else definition.get("path", name),
                "context_before": candidate.get("context_before", ""),
                "context_after": candidate.get("context_after", ""),
                "candidate_text": candidate.get("text", location["text"] if location else ""),
            }
        )
    return {
        "proposal_id": parsed.proposal_id,
        "items": items,
        "metrics": report["metrics"],
        "coverage": report["coverage"],
        "diagnostics": report["diagnostics"],
        "exit_code": report["exit_code"],
        "additions": parsed.additions.model_dump(),
    }


class StudioBatch:
    def __init__(self, project, draft, request):
        self.catalog = create_catalog(project, draft, request)
        self.inspection = inspect_catalog(project, self.catalog)
        self.catalog_id = self.catalog["catalog_id"]

    def validate(self, project, draft, catalog_id):
        if self.catalog_id != catalog_id or self.catalog["draft"]["draft_id"] != draft["draft_id"]:
            raise PaperDeltaError("STUDIO_BATCH_STALE", msg("studio.batch_stale"))
        builder.resume_draft(project, draft)

    def choices(self, query="", offset=0, limit=20):
        query = query.strip().casefold()
        selected = [
            choice
            for choice in self.inspection["choices"]
            if not query or query in json_text(choice["definition"]).casefold()
        ]
        return {
            "catalog_id": self.catalog_id,
            "request": deepcopy(self.catalog["request"]),
            "items": [
                {
                    key: deepcopy(value)
                    for key, value in choice.items()
                    if key != "suggested_locations"
                }
                for choice in selected[offset : offset + limit]
            ],
            "total": len(selected),
            "offset": offset,
            "limit": limit,
        }

    def locations(self, choice_id, query="", offset=0, limit=20):
        choice = next(
            (item for item in self.inspection["choices"] if item["choice_id"] == choice_id), None
        )
        if choice is None:
            raise PaperDeltaError("BATCH_SELECTION", msg("batch.selection"))
        suggested = {item["candidate_id"]: item for item in choice["suggested_locations"]}
        order = {key: index for index, key in enumerate(suggested)}
        query = query.strip().casefold()
        locations = [
            item
            for item in self.inspection["locations"]
            if not query
            or query
            in " ".join(
                str(item.get(key, ""))
                for key in (
                    "file",
                    "row",
                    "column_header",
                    "context_before",
                    "context_after",
                    "text",
                )
            ).casefold()
        ]
        locations.sort(key=lambda item: order.get(item["candidate_id"], len(order)))
        return {
            "catalog_id": self.catalog_id,
            "choice_id": choice_id,
            "items": [
                {
                    **deepcopy(item),
                    "label": location_label(item),
                    "suggestion": deepcopy(suggested.get(item["candidate_id"])),
                }
                for item in locations[offset : offset + limit]
            ],
            "total": len(locations),
            "offset": offset,
            "limit": limit,
        }

    def draft(self, project, selections):
        proposal = build_proposal(project, self.catalog, selections)
        body = deepcopy(self.catalog["draft"])
        body.update(additions=proposal["additions"], rationale=proposal["rationale"])
        return builder._seal(project, body, proposal["input_hashes"])
