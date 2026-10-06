"""Local visual binding sessions using the same drafts and acceptance as the CLI.

Browser state is presentation, never the authority for a proposal or calculation.
Every edit names a session revision; only an inspected, server-held proposal can
be accepted. Nothing writes manuscript or evidence files.
"""

from __future__ import annotations

import os
import secrets
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from paperdelta import __version__, builder
from paperdelta.analysis import check_project
from paperdelta.batch import BatchRequest, BatchSelection
from paperdelta.config import load_config
from paperdelta.declarations import (
    DeclarationEdit,
    Group,
    accept_maintenance,
    declaration_fields,
    dependents,
    field_replacement,
    propose_maintenance,
)
from paperdelta.errors import PaperDeltaError
from paperdelta.experiment_definitions import (
    accept_definition,
    list_definitions,
    load_definition,
    preview_definition,
)
from paperdelta.html_report import html_report
from paperdelta.i18n import language_context, msg, translated
from paperdelta.locations import location_label
from paperdelta.models import (
    Aggregation,
    ColumnType,
    DerivedOperation,
    DisplayKind,
    Hash,
    Identifier,
    ReviewedTableIdentity,
    SourceFormat,
    StatisticalContract,
    StatisticalDisplay,
    StrictModel,
    Unit,
)
from paperdelta.onboarding import (
    _source_summary,
    accept_bindings,
    init_project,
    scan_project,
)
from paperdelta.patches import _write_lock
from paperdelta.pdf_previews import pdf_previews
from paperdelta.records import validate_record
from paperdelta.repairs import (
    RepairSelection,
    accept_repairs,
    inspect_repair,
    propose_repairs,
    scan_repairs,
)
from paperdelta.sources import EvidenceStore
from paperdelta.storage import Project, fingerprint, json_text, parse_json, sha256
from paperdelta.studio_batch import (
    MAX_TEMPLATE_BYTES,
    StudioBatch,
    make_template,
    proposal_draft,
    proposal_preview,
    read_template,
    save_template,
    template_list,
    template_request,
)
from paperdelta.studio_recovery import DraftRecovery, migrate_draft, rebuild_draft
from paperdelta.studio_review import StudioReview

MAX_CANDIDATES = 30


class Empty(StrictModel):
    pass


class DiagnosticExport(StrictModel):
    preview_id: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")


class Initialize(StrictModel):
    paper: str = Field(min_length=1, max_length=1000)
    data: list[str] = Field(default_factory=list, max_length=30)


class SourceInput(StrictModel):
    name: Identifier
    path: str = Field(min_length=1, max_length=1000)
    format: SourceFormat
    columns: dict[str, ColumnType] = Field(default_factory=dict, max_length=100)
    primary_key: list[str] = Field(default_factory=list, max_length=100)
    source_hash: str
    sheet: str | None = None
    cell_range: str | None = None


class MetricInput(StrictModel):
    name: Identifier
    source: Identifier
    field: str = Field(max_length=1000)
    unit: Unit
    reduce: Aggregation
    where: dict[str, str] = Field(default_factory=dict, max_length=100)
    expected_count: int = Field(default=1, ge=1, le=10000)
    seed_column: str = Field(default="seed", max_length=1000)
    expected_seeds: list[str] | None = Field(default=None, max_length=10000)
    statistics: StatisticalContract | None = None


class DerivedInput(StrictModel):
    name: Identifier
    operation: DerivedOperation
    left: Identifier
    right: Identifier


class LocationsInput(StrictModel):
    metric: Identifier
    candidate_ids: list[str] = Field(min_length=1, max_length=200)
    names: list[Identifier] = Field(min_length=1, max_length=200)
    display_kind: DisplayKind
    places: int = Field(ge=0, le=15)
    percent_symbol: bool
    rationale: str = Field(min_length=1, max_length=4000)
    statistics: StatisticalDisplay | None = None
    table_identity: ReviewedTableIdentity | None = None


class SourcePreview(StrictModel):
    path: str = Field(min_length=1, max_length=1000)
    offset: int = Field(default=0, ge=0, le=1000000)
    sheet: str | None = None
    cell_range: str | None = None


class PagePreview(StrictModel):
    file: str
    page: int = Field(ge=1, le=200)


class Accept(StrictModel):
    proposal_id: str
    selected: list[str] = Field(min_length=1, max_length=200)


class ImportDraft(StrictModel):
    draft: dict


class ImportProposal(StrictModel):
    value_json: str = Field(min_length=1, max_length=900000)


class BatchIdentity(StrictModel):
    catalog_id: str


class BatchPage(BatchIdentity):
    query: str = Field(default="", max_length=1000)
    offset: int = Field(default=0, ge=0, le=10000000)
    limit: int = Field(default=20, ge=1, le=100)


class BatchLocations(BatchPage):
    choice_id: str


class BatchStage(BatchIdentity):
    selections: list[BatchSelection] = Field(min_length=1, max_length=200)


class TemplateSave(BatchIdentity):
    name: Identifier


class TemplateName(StrictModel):
    name: Identifier


class TemplateLoad(TemplateName):
    source: Identifier


class TemplateImport(StrictModel):
    value_json: str = Field(min_length=1, max_length=MAX_TEMPLATE_BYTES)
    source: Identifier


class ExperimentPreview(StrictModel):
    name: Identifier
    request: BatchRequest
    rationale: str = Field(min_length=1, max_length=4000)


class ExperimentAccept(StrictModel):
    preview_id: Hash


class ExperimentLoad(StrictModel):
    definition_id: Hash
    source: Identifier


class CandidateQuery(StrictModel):
    query: str = Field(default="", max_length=1000)
    file: str | None = Field(default=None, max_length=1000)
    include_bound: bool = False
    offset: int = Field(default=0, ge=0, le=10000000)
    limit: int = Field(default=30, ge=1, le=100)
    page: int | None = Field(default=None, ge=1, le=200)


class MaintenanceInput(StrictModel):
    edits: list[DeclarationEdit] = Field(min_length=1, max_length=200)


class DefinitionField(StrictModel):
    path: list[str] = Field(min_length=1, max_length=5)
    value_json: str = Field(max_length=150000)


class MaintenanceFields(StrictModel):
    group: Group
    name: Identifier
    fields: list[DefinitionField] = Field(min_length=1, max_length=300)
    rationale: str = Field(min_length=1, max_length=4000)


class ProposalIdentity(StrictModel):
    proposal_id: str


class RepairInput(StrictModel):
    selections: list[RepairSelection] = Field(min_length=1, max_length=200)


class RepairAccept(StrictModel):
    repair_id: str
    selected: list[str] = Field(min_length=1, max_length=200)


class SnapshotName(StrictModel):
    name: str = Field(min_length=1, max_length=80)


class BaselineName(StrictModel):
    name: str | None = Field(default=None, max_length=80)


class ClaimReview(StrictModel):
    claim: Identifier
    state: str
    reviewer: str = Field(min_length=1, max_length=200)
    note: str = Field(min_length=1, max_length=4000)
    attest: Literal[True]


class RecoveryIdentity(StrictModel):
    record_id: str


class RecoverySelection(RecoveryIdentity):
    selected: list[str] = Field(min_length=1, max_length=500)


PARAMETERS = {
    "state": Empty,
    "refresh": Empty,
    "initialize": Initialize,
    "source-preview": SourcePreview,
    "source-advice": SourcePreview,
    "source": SourceInput,
    "metric": MetricInput,
    "derived": DerivedInput,
    "locations": LocationsInput,
    "undo": Empty,
    "preview": Empty,
    "accept": Accept,
    "page": PagePreview,
    "report": Empty,
    "diagnostic-preview": Empty,
    "diagnostic-export": DiagnosticExport,
    "draft-export": Empty,
    "draft-import": ImportDraft,
    "proposal-import": ImportProposal,
    "batch-catalog": BatchRequest,
    "batch-choices": BatchPage,
    "batch-review": BatchPage,
    "experiment-preview": ExperimentPreview,
    "experiment-accept": ExperimentAccept,
    "experiment-list": Empty,
    "experiment-load": ExperimentLoad,
    "batch-locations": BatchLocations,
    "batch-stage": BatchStage,
    "template-list": Empty,
    "template-save": TemplateSave,
    "template-export": TemplateName,
    "template-load": TemplateLoad,
    "template-import": TemplateImport,
    "candidates": CandidateQuery,
    "poll": Empty,
    "review": Empty,
    "snapshot-create": SnapshotName,
    "baseline": BaselineName,
    "claim-review": ClaimReview,
    "declarations": Empty,
    "maintenance-preview": MaintenanceInput,
    "maintenance-fields": MaintenanceFields,
    "maintenance-accept": ProposalIdentity,
    "repair-scan": Empty,
    "repair-preview": RepairInput,
    "repair-accept": RepairAccept,
    "recovery-restore": Empty,
    "recovery-discard": RecoveryIdentity,
    "recovery-export": Empty,
    "recovery-items": Empty,
    "recovery-preview": RecoverySelection,
    "recovery-rebuild": ProposalIdentity,
}


class Request(StrictModel):
    action: Annotated[str, Field(min_length=1, max_length=30)]
    language: Literal["en", "zh-CN"] = "en"
    revision: str | None = None
    payload: dict = Field(default_factory=dict)


def browser_value(value):
    """Decimals and large record keys must never pass through JavaScript Number."""
    if isinstance(value, Decimal) or (type(value) is int and abs(value) > 2**53 - 1):
        return str(value)
    if isinstance(value, dict):
        return {key: browser_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [browser_value(item) for item in value]
    return value


def project_files(project):
    output, visited = [], 0
    ignored = {"build", "dist", "node_modules", "__pycache__", "venv"}
    for root, directories, names in os.walk(project.root, followlinks=False):
        depth = len(Path(root).relative_to(project.root).parts)
        directories[:] = sorted(
            name
            for name in directories
            if depth < 8
            and not name.startswith(".")
            and name not in ignored
            and not (Path(root) / name).is_symlink()
        )
        for name in sorted(names):
            visited += 1
            path = Path(root) / name
            if (
                not name.startswith(".")
                and path.suffix.lower()
                in {".tex", ".docx", ".pdf", ".md", ".qmd", ".csv", ".json", ".tsv", ".xlsx"}
                and not path.is_symlink()
            ):
                output.append(project.relative(path))
            if len(output) >= 500 or visited >= 20000:
                return {"paths": output, "limited": True}
    return {"paths": output, "limited": False}


class StudioSession:
    def __init__(self, project: Project, config_path="paperdelta.yaml"):
        self.project = project
        self.config_path = project.relative(project.path(config_path))
        self.revision = secrets.token_hex(16)
        self.draft = None
        self.scan = None
        self.report = None
        self.proposal = None
        self.preview = None
        self.history = []
        self.receipt = None
        self._cached_state = None
        self._all_candidates = None
        self.maintenance = None
        self.repair = None
        self.rebuild = None
        self.batch = None
        self.experiment = None
        self.recovery_archive = None
        self.recovery = DraftRecovery(project, self.config_path)
        self.reviewer = StudioReview(project, self.config_path)
        self.refresh()

    def refresh(self):
        draft = scan = report = None
        if self.project.path(self.config_path).exists():
            draft = builder.start_draft(self.project, self.config_path)
            scan = scan_project(self.project, self.config_path)
            report = check_project(self.project.root, self.config_path)
            builder.resume_draft(self.project, draft)
            if any(draft["input_hashes"].get(k) != v for k, v in scan["input_hashes"].items()):
                raise PaperDeltaError("STALE_DRAFT", msg("studio.changed"))
        self.draft, self.scan, self.report = draft, scan, report
        self.history = []
        self._advance()
        if report is not None:
            self.reviewer.seed(report)

    def _advance(self):
        self.revision = secrets.token_hex(16)
        self.proposal = self.preview = None
        self.maintenance = self.repair = None
        self.rebuild = None
        self.batch = None
        self.experiment = None
        self._cached_state = self._all_candidates = None

    def _require_draft(self):
        if self.draft is None:
            raise PaperDeltaError("STUDIO_SETUP", msg("studio.setup_required"))
        return builder.resume_draft(self.project, self.draft)

    def _stage(self, draft):
        if sum(len(items) for items in draft["additions"].values()) > 500:
            raise PaperDeltaError("STUDIO_LIMIT", msg("studio.stage_limit"))
        self.recovery.save(draft)
        self.history = [*self.history[-19:], self.draft]
        self.draft = draft
        self._advance()

    def state(self):
        result = {
            "version": __version__,
            "project": self.project.root.name,
            "config_path": self.config_path,
            "revision": self.revision,
            "initialized": self.draft is not None,
            "can_undo": bool(self.history),
            "receipt": self.receipt,
            "preview": self.preview,
            "stale": False,
            "input_identity": fingerprint(self.draft["input_hashes"]) if self.draft else None,
            "review": self.reviewer.summary(),
            "recovery": self.recovery.status(),
            "maintenance": self.maintenance[1] if self.maintenance else None,
            "repair": self.repair[1] if self.repair else None,
            "rebuild": self.rebuild[2] if self.rebuild else None,
            "batch_id": self.batch.catalog_id if self.batch else None,
            "recovery_archive": self.recovery_archive,
        }
        if self.draft is None:
            result["files"] = project_files(self.project)
            return result
        try:
            if self._cached_state is not None:
                builder._unchanged(self.project, self.draft["input_hashes"])
                return {**deepcopy(self._cached_state), **result}
            draft, config = self._require_draft()
        except PaperDeltaError as exc:
            result.update(stale=True, error=exc.code, message=exc.message)
            return result
        store = EvidenceStore(self.project, config)
        metrics = {}
        for name, definition in config.metrics.items():
            try:
                entry = {"result": store.resolve(name).to_dict()}
            except PaperDeltaError as exc:
                entry = {"error": exc.code, "message": exc.message}
            metrics[name] = {"definition": definition.model_dump(), **entry}
        candidates = []
        occupied = [
            (name, item["location"])
            for name, item in self.report["occurrences"].items()
            if item.get("location")
        ]
        # Staged anchors are validated by add_occurrences. Reuse its exact candidate
        # identity, rather than confusing an equal number with a selected position.
        from paperdelta.documents import PaperIndex

        paper = PaperIndex(self.project, config.paper)
        for name, occurrence in draft.additions.occurrences.items():
            location = paper.document(occurrence.file).locate(occurrence.anchor).to_dict()
            occupied.append((name, location))
        for candidate in self.scan["candidates"]:
            bound = [
                name
                for name, location in occupied
                if location["file"] == candidate["file"]
                and location["start"] < candidate["end"]
                and candidate["start"] < location["end"]
            ]
            candidates.append({**candidate, "label": location_label(candidate), "bound": bound})
        builder.resume_draft(self.project, self.draft)
        self._all_candidates = candidates
        result.update(
            sources={name: source.model_dump() for name, source in config.sources.items()},
            discovered_sources=self.scan["sources"],
            metrics=metrics,
            candidates=candidates[:MAX_CANDIDATES],
            candidate_files=sorted({item["file"] for item in candidates}),
            candidate_total=len(self.scan["candidates"]),
            candidate_limit=MAX_CANDIDATES,
            unsupported=self.scan["unsupported"],
            additions=draft.additions.model_dump(),
            coverage=self.report["coverage"],
            check_exit_code=self.report["exit_code"],
        )
        self._cached_state = deepcopy(result)
        return result

    def candidates(self, query):
        state = self.state()
        if state["stale"]:
            self._require_draft()
        items = self._all_candidates or []
        text = query["query"].casefold().strip()
        chosen = [
            item
            for item in items
            if (not query["file"] or item["file"] == query["file"])
            and (query["include_bound"] or not item["bound"])
            and (query["page"] is None or item.get("locator", {}).get("page") == query["page"])
            and (
                not text
                or text
                in " ".join(
                    str(item.get(key, ""))
                    for key in ("file", "text", "context_before", "context_after")
                ).casefold()
            )
        ]
        start = query["offset"]
        return {
            "items": chosen[start : start + query["limit"]],
            "total": len(chosen),
            "offset": start,
            "limit": query["limit"],
            "revision": self.revision,
        }

    def _require_clean(self):
        self._require_draft()
        if any(self.draft["additions"].values()):
            raise PaperDeltaError("STUDIO_STAGED", msg("studio.finish_draft"))

    def _after_accept(self):
        try:
            self.recovery.save(None)
        except PaperDeltaError as exc:
            self.receipt["recovery_error"] = exc.message
        try:
            self.refresh()
        except PaperDeltaError:
            self._advance()

    def execute(self, value):
        request = validate_record(Request, value, "STUDIO_REQUEST")
        model = PARAMETERS.get(request.action)
        if model is None:
            raise PaperDeltaError("STUDIO_REQUEST", msg("studio.unknown_action"))
        parameters = validate_record(model, request.payload, "STUDIO_REQUEST").model_dump()
        if request.action not in {"state", "poll", "review"} and request.revision != self.revision:
            raise PaperDeltaError("STUDIO_REVISION", msg("studio.revision"))
        with language_context(request.language):
            result = self._execute(request.action, parameters)
        return browser_value(translated(result, request.language))

    def _execute(self, action, parameters):
        if action == "diagnostic-preview":
            from paperdelta.diagnostic_bundle import preview_bundle

            return preview_bundle(self.project, self.config_path)
        if action == "diagnostic-export":
            import base64

            from paperdelta.diagnostic_bundle import bundle_bytes

            raw = bundle_bytes(self.project, parameters["preview_id"], self.config_path)
            return {"base64": base64.b64encode(raw).decode("ascii")}
        if action == "state":
            return {"state": self.state()}
        if action == "poll":
            updated, summary = self.reviewer.poll()
            if (
                updated
                and summary["state"] == "current"
                and self.draft is not None
                and not any(self.draft["additions"].values())
            ):
                try:
                    builder._unchanged(self.project, self.draft["input_hashes"])
                except PaperDeltaError:
                    try:
                        self.refresh()
                    except PaperDeltaError:
                        pass  # The independent review still exposes incomplete/partial saves.
            stale = False
            if self.draft is not None:
                try:
                    builder._unchanged(self.project, self.draft["input_hashes"])
                except PaperDeltaError:
                    stale = True
            return {
                "review": self.reviewer.summary(),
                "revision": self.revision,
                # A busy tab may miss the first event. Keep reporting the current
                # draft status, including changed sources not yet accepted.
                "stale": stale,
            }
        if action == "review":
            return self.reviewer.detail()
        if action == "draft-export":
            if self.draft is None:
                self._require_draft()
            return {"json": json_text(self.draft)}
        if action == "recovery-export":
            return {"json": self.recovery.export()}
        if action == "recovery-items":
            record = self.recovery.read()
            if record is None or record.draft is None:
                raise PaperDeltaError("STUDIO_RECOVERY_EMPTY", msg("recovery.empty"))
            return {
                "record_id": record.record_id,
                "status": self.recovery.status(),
                "items": [
                    {"id": f"{group}:{name}", "definition_json": json_text(definition)}
                    for group, items in record.draft["additions"].items()
                    for name, definition in items.items()
                ],
            }
        if action == "recovery-preview":
            record = self.recovery.select_record(parameters["record_id"])
            rebuilt, preview = rebuild_draft(self.project, record.draft, parameters["selected"])
            proposal_id = fingerprint({"record": record.record_id, "draft": rebuilt})
            self._advance()
            self.rebuild = (record.record_id, rebuilt, {**preview, "proposal_id": proposal_id})
            return {"state": self.state()}
        if action == "recovery-rebuild":
            if self.rebuild is None or self.rebuild[2]["proposal_id"] != parameters["proposal_id"]:
                raise PaperDeltaError("STUDIO_PREVIEW", msg("studio.preview_required"))
            record_id, draft, _ = self.rebuild
            builder.resume_draft(self.project, draft)
            self.recovery.claim_record(record_id)
            self.recovery_archive = self.recovery.archive()
            self.refresh()
            self._stage(draft)
            return {"state": self.state()}
        if action == "recovery-restore":
            self._stage(self.recovery.restore())
            return {"state": self.state()}
        if action == "recovery-discard":
            self.recovery.discard(parameters["record_id"])
            return {"state": self.state()}
        if action == "baseline":
            self.reviewer.select_baseline(parameters["name"])
            return self.reviewer.detail()
        if action == "snapshot-create":
            result = self.reviewer.create_snapshot(parameters["name"])
            return {"snapshot": result, **self.reviewer.detail()}
        if action == "claim-review":
            parameters.pop("attest")
            receipt = self.reviewer.attest(**parameters)
            return {"receipt": receipt, **self.reviewer.detail()}
        if action == "refresh":
            if self.draft and any(self.draft["additions"].values()):
                self.recovery_archive = self.recovery.archive()
            self.refresh()
        elif action == "initialize":
            if self.draft is not None:
                raise PaperDeltaError("ALREADY_EXISTS", msg("error.ALREADY_EXISTS"))
            with _write_lock(self.project):
                init_project(self.project, config_path=self.config_path, **parameters)
            self.refresh()
        elif action == "source-preview":
            summary, identity = _source_summary(self.project, **parameters, limit=100)
            summary["offset"] = parameters["offset"]
            return {"source": {**summary, "hash": identity}}
        elif action == "source-advice":
            from paperdelta.source_advice import source_advice

            parameters.pop("offset", None)
            return source_advice(self.project, **parameters)
        else:
            self._require_draft()
            if action == "experiment-preview":
                self.experiment = preview_definition(self.project, self.draft, **parameters)
                return self.experiment
            if action == "experiment-accept":
                receipt = accept_definition(self.project, self.draft, self.experiment, **parameters)
                self.experiment = None
                return receipt
            if action == "experiment-list":
                return list_definitions(self.project)
            if action == "experiment-load":
                return load_definition(self.project, self.draft, **parameters)
            if action == "batch-catalog":
                batch = StudioBatch(self.project, self.draft, parameters)
                self._advance()
                self.batch = batch
                return {"state": self.state(), "batch": batch.choices()}
            if action in {
                "batch-choices",
                "batch-review",
                "batch-locations",
                "batch-stage",
                "template-save",
            }:
                if self.batch is None:
                    raise PaperDeltaError("STUDIO_BATCH_STALE", msg("studio.batch_stale"))
                self.batch.validate(self.project, self.draft, parameters.pop("catalog_id"))
                if action == "batch-choices":
                    return self.batch.choices(**parameters)
                if action == "batch-review":
                    return self.batch.review(**parameters)
                if action == "batch-locations":
                    return self.batch.locations(**parameters)
                if action == "template-save":
                    request = self.batch.catalog["request"]
                    _, config = self._require_draft()
                    template = make_template(
                        parameters["name"], config.sources[request["source"]], request
                    )
                    save_template(self.project, template)
                    return template_list(self.project)
                if sum(len(item["candidate_ids"]) for item in parameters["selections"]) > 200:
                    raise PaperDeltaError("STUDIO_LIMIT", msg("studio.selection_limit"))
                draft = self.batch.draft(self.project, parameters["selections"])
                self._stage(draft)
                return {"state": self.state()}
            if action == "template-list":
                return template_list(self.project)
            if action == "template-export":
                template = read_template(self.project, parameters["name"])
                return {"json": json_text(template.model_dump())}
            if action in {"template-load", "template-import"}:
                if (
                    action == "template-import"
                    and len(parameters["value_json"].encode("utf-8")) > MAX_TEMPLATE_BYTES
                ):
                    raise PaperDeltaError("STUDIO_TEMPLATE_LIMIT", msg("studio.template_limit"))
                value = (
                    read_template(self.project, parameters["name"]).model_dump()
                    if action == "template-load"
                    else parse_json(parameters["value_json"])
                )
                return {
                    "request": template_request(
                        self.project, self.draft, value, parameters["source"]
                    ),
                    "requires_confirmation": True,
                }
            if action == "proposal-import":
                draft = proposal_draft(
                    self.project, self.draft, parse_json(parameters["value_json"])
                )
                self._stage(draft)
                return self._execute("preview", {})
            if action == "candidates":
                return self.candidates(parameters)
            if action == "declarations":
                config, _ = load_config(self.project, self.config_path)
                return {
                    "items": [
                        {
                            "id": f"{group}:{name}",
                            "group": group,
                            "name": name,
                            "definition": definition.model_dump(),
                            "definition_json": json_text(definition.model_dump()),
                            "fields": declaration_fields(definition.model_dump()),
                            "dependents": [
                                identity
                                for identity in dependents(config, [f"{group}:{name}"])
                                if identity != f"{group}:{name}"
                            ],
                            "state": self.report.get(group, {}).get(name),
                        }
                        for group in ("sources", "metrics", "occurrences", "claims", "figures")
                        for name, definition in getattr(config, group).items()
                    ]
                }
            if action == "maintenance-fields":
                self._require_clean()
                replacement = field_replacement(
                    self.project,
                    parameters["group"],
                    parameters["name"],
                    parameters["fields"],
                    config_path=self.config_path,
                )
                return self._execute(
                    "maintenance-preview",
                    {
                        "edits": [
                            {
                                "group": parameters["group"],
                                "name": parameters["name"],
                                "operation": "replace",
                                "definition_json": replacement,
                                "rationale": parameters["rationale"],
                            }
                        ]
                    },
                )
            if action in {
                "maintenance-preview",
                "maintenance-accept",
                "repair-preview",
                "repair-accept",
            }:
                self._require_clean()
                if action == "maintenance-preview":
                    proposal, preview = propose_maintenance(
                        self.project, parameters["edits"], config_path=self.config_path
                    )
                    self._advance()
                    self.maintenance = (
                        proposal,
                        {**preview, "proposal_id": proposal["proposal_id"]},
                    )
                elif action == "maintenance-accept":
                    if (
                        self.maintenance is None
                        or self.maintenance[0]["proposal_id"] != parameters["proposal_id"]
                    ):
                        raise PaperDeltaError("STUDIO_PREVIEW", msg("studio.preview_required"))
                    self.receipt = accept_maintenance(self.project, self.maintenance[0])
                    self.receipt["bindings"] = [item["id"] for item in self.receipt["changes"]]
                    self._after_accept()
                elif action == "repair-preview":
                    proposal = propose_repairs(
                        self.project,
                        parameters["selections"],
                        config_path=self.config_path,
                        baseline=self.reviewer.watcher.baseline,
                    )
                    _, _, preview = inspect_repair(self.project, proposal)
                    self._advance()
                    self.repair = (proposal, preview)
                else:
                    if (
                        self.repair is None
                        or self.repair[0]["repair_id"] != parameters["repair_id"]
                    ):
                        raise PaperDeltaError("STUDIO_PREVIEW", msg("studio.preview_required"))
                    self.receipt = accept_repairs(
                        self.project, self.repair[0], parameters["selected"]
                    )
                    self._after_accept()
                return {"state": self.state()}
            if action == "repair-scan":
                result = scan_repairs(
                    self.project, self.config_path, self.reviewer.watcher.baseline
                )
                # Positions are searched through the same paginated candidate endpoint.
                return {key: value for key, value in result.items() if key != "candidates"}
            if action in {"source", "metric", "derived", "locations"}:
                if action == "source":
                    if sha256(self.project.read(parameters["path"])) != parameters.pop(
                        "source_hash"
                    ):
                        raise PaperDeltaError("STALE_DRAFT", msg("studio.changed"))
                operation = {
                    "source": builder.add_source,
                    "metric": builder.add_metric,
                    "derived": builder.add_derived,
                    "locations": builder.add_occurrences,
                }[action]
                self._stage(operation(self.project, self.draft, **parameters))
            elif action == "undo":
                if not self.history:
                    raise PaperDeltaError("STUDIO_UNDO", msg("studio.no_undo"))
                self.recovery.save(self.history[-1])
                self.draft = self.history.pop()
                self._advance()
            elif action == "preview":
                proposal = builder.finalize_draft(self.project, self.draft)
                preview = proposal_preview(self.project, proposal, self.scan["candidates"])
                self.proposal = proposal
                self.preview = preview
            elif action == "accept":
                if (
                    self.proposal is None
                    or parameters["proposal_id"] != self.proposal["proposal_id"]
                ):
                    raise PaperDeltaError("STUDIO_PREVIEW", msg("studio.preview_required"))
                self.receipt = accept_bindings(self.project, self.proposal, parameters["selected"])
                # The write succeeded even if the next scan encounters a concurrent
                # edit. Return that receipt so clients never mistake it for failure.
                self._after_accept()
            elif action == "page":
                locations = [
                    item
                    for item in self.scan["candidates"]
                    if item.get("format") == "pdf"
                    and item["file"] == parameters["file"]
                    and item["locator"]["page"] == parameters["page"]
                ]
                if not locations:
                    raise PaperDeltaError("STUDIO_PAGE", msg("studio.page_missing"))
                report = {
                    "diagnostics": [],
                    "occurrences": {},
                    "claims": {},
                    "coverage": {"unbound_numbers": locations},
                    "input_hashes": self.draft["input_hashes"],
                }
                self.state()
                return {
                    "preview": pdf_previews(self.project, report, max_pages=1),
                    "candidates": [
                        item
                        for item in self._all_candidates or []
                        if item.get("format") == "pdf"
                        and item["file"] == parameters["file"]
                        and item["locator"]["page"] == parameters["page"]
                    ][:500],
                }
            elif action == "report":
                from paperdelta.i18n import current_language

                report = check_project(self.project.root, self.config_path)
                return {
                    "html": html_report(report, previews=pdf_previews(self.project, report)),
                    "language": current_language(),
                }
            elif action == "draft-import":
                draft, _ = builder.resume_draft(
                    self.project, migrate_draft(self.project, parameters["draft"])
                )
                if draft.config_path != self.config_path:
                    raise PaperDeltaError("STUDIO_DRAFT", msg("studio.draft_project"))
                if draft.additions.claims or draft.additions.figures:
                    builder.finalize_draft(self.project, draft.model_dump())
                self._stage(draft.model_dump())
        return {"state": self.state()}
