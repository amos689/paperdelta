"""Content-addressed, explicitly reviewed experiment definitions for later batches."""

from pydantic import Field, TypeAdapter

from paperdelta import builder
from paperdelta.batch import BatchRequest, create_catalog
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.models import Hash, Identifier, StrictModel, VersionOne
from paperdelta.patches import _write_lock
from paperdelta.records import validate_record
from paperdelta.storage import fingerprint, json_text, parse_json
from paperdelta.studio_batch import TemplateSource

DIRECTORY = ".paperdelta/experiments"
MAX_BYTES = 131072


class ExperimentDefinition(StrictModel):
    experiment_schema_version: VersionOne
    name: Identifier
    source_contract: TemplateSource
    request: BatchRequest
    rationale: str = Field(min_length=1, max_length=4000)
    definition_id: Hash


def _validated(value):
    definition = validate_record(ExperimentDefinition, value, "EXPERIMENT_SCHEMA")
    if definition.definition_id != fingerprint(definition.model_dump(exclude={"definition_id"})):
        raise PaperDeltaError("EXPERIMENT_IDENTITY", msg("experiment.identity"))
    if definition.request.experiment_definition is not None:
        raise PaperDeltaError("EXPERIMENT_REFERENCE", msg("experiment.reference"))
    return definition


def definition_path(definition_id):
    identity = TypeAdapter(Hash).validate_python(definition_id, strict=True)
    return f"{DIRECTORY}/{identity[7:]}.json"


def read_definition(project, definition_id):
    raw = project.read(definition_path(definition_id), MAX_BYTES)
    definition = _validated(parse_json(raw.decode("utf-8")))
    if definition.definition_id != definition_id:
        raise PaperDeltaError("EXPERIMENT_IDENTITY", msg("experiment.identity"))
    return definition


def _contract_matches(source, contract):
    return source is not None and (
        source.format == contract.format
        and source.primary_key == contract.primary_key
        and all(source.columns.get(key) == kind for key, kind in contract.columns.items())
    )


def validate_reference(project, source, request):
    definition = read_definition(project, request.experiment_definition)
    expected = definition.request.model_copy(update={"source": request.source}).model_dump()
    actual = request.model_copy(update={"experiment_definition": None}).model_dump()
    if actual != expected or not _contract_matches(source, definition.source_contract):
        raise PaperDeltaError("EXPERIMENT_CHANGED", msg("experiment.changed"))


def preview_definition(project, draft, name, request, rationale):
    request = validate_record(BatchRequest, request, "BATCH_REQUEST")
    request = request.model_copy(update={"experiment_definition": None})
    catalog = create_catalog(project, draft, request.model_dump())
    _, config = builder.resume_draft(project, draft)
    source = config.sources[request.source]
    body = {
        "experiment_schema_version": 1,
        "name": name,
        "source_contract": {
            "format": source.format,
            "columns": source.columns,
            "primary_key": source.primary_key,
        },
        "request": request.model_dump(),
        "rationale": rationale,
    }
    definition = _validated({**body, "definition_id": fingerprint(body)}).model_dump()
    preview = {
        "definition": definition,
        "draft_id": draft["draft_id"],
        "catalog_id": catalog["catalog_id"],
    }
    raw = json_text(preview).encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise PaperDeltaError("EXPERIMENT_LIMIT", msg("experiment.limit"))
    return {
        **preview,
        "preview_id": fingerprint(preview),
        "requires_confirmation": True,
        "notice": msg("experiment.notice"),
    }


def accept_definition(project, draft, preview, preview_id):
    if preview is None or preview.get("preview_id") != preview_id:
        raise PaperDeltaError("EXPERIMENT_PREVIEW", msg("experiment.preview"))
    value = preview["definition"]
    with _write_lock(project):
        fresh = preview_definition(
            project, draft, value["name"], value["request"], value["rationale"]
        )
        if fresh["preview_id"] != preview_id:
            raise PaperDeltaError("EXPERIMENT_PREVIEW", msg("experiment.preview"))
        path = definition_path(value["definition_id"])
        if project.path(path).exists():
            read_definition(project, value["definition_id"])
        else:
            directory = project.path(DIRECTORY)
            if directory.exists() and len(list(directory.glob("*.json"))) >= 100:
                raise PaperDeltaError("EXPERIMENT_LIMIT", msg("experiment.limit"))
            project.write(path, json_text(value).encode("utf-8"), exclusive=True)
    return {
        "definition_id": value["definition_id"],
        "path": path,
        "status": "saved",
        "notice": msg("experiment.saved"),
    }


def list_definitions(project):
    directory = project.path(DIRECTORY)
    paths = sorted(directory.glob("*.json")) if directory.exists() else []
    items, errors = [], []
    for path in paths[:100]:
        try:
            items.append(read_definition(project, "sha256:" + path.stem).model_dump())
        except (PaperDeltaError, UnicodeError, ValueError) as exc:
            errors.append({"file": path.name, "message": str(exc)})
    return {"items": items, "errors": errors, "limited": len(paths) > 100}


def load_definition(project, draft, definition_id, source):
    definition = read_definition(project, definition_id)
    _, config = builder.resume_draft(project, draft)
    request = definition.request.model_copy(
        update={"source": source, "experiment_definition": definition_id}
    )
    validate_reference(project, config.sources.get(source), request)
    create_catalog(project, draft, request.model_dump())
    return {
        "definition": definition.model_dump(),
        "request": request.model_dump(),
        "requires_confirmation": True,
        "notice": msg("experiment.loaded"),
    }
