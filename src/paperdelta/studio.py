"""Local visual binding sessions using the same drafts and acceptance as the CLI.

Browser state is presentation, never the authority for a proposal or calculation.
Every edit names a session revision; only an inspected, server-held proposal can
be accepted. Nothing writes manuscript or evidence files.
"""

from __future__ import annotations

import csv
import io
import os
import secrets
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

from paperdelta import __version__, builder
from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.html_report import html_report
from paperdelta.i18n import language_context, msg, translated
from paperdelta.locations import location_label
from paperdelta.models import (
    Aggregation,
    ColumnType,
    DerivedOperation,
    DisplayKind,
    Identifier,
    SourceFormat,
    StrictModel,
    Unit,
)
from paperdelta.onboarding import (
    _source_summary,
    accept_bindings,
    init_project,
    inspect_proposal,
    scan_project,
)
from paperdelta.patches import _write_lock
from paperdelta.pdf_previews import pdf_previews
from paperdelta.records import validate_record
from paperdelta.sources import EvidenceStore
from paperdelta.storage import Project, json_text, sha256

MAX_CANDIDATES = 5000


class Empty(StrictModel):
    pass


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


class SourcePreview(StrictModel):
    path: str = Field(min_length=1, max_length=1000)
    offset: int = Field(default=0, ge=0, le=1000000)


class PagePreview(StrictModel):
    file: str
    page: int = Field(ge=1, le=200)


class Accept(StrictModel):
    proposal_id: str
    selected: list[str] = Field(min_length=1, max_length=200)


class ImportDraft(StrictModel):
    draft: dict


PARAMETERS = {
    "state": Empty,
    "refresh": Empty,
    "initialize": Initialize,
    "source-preview": SourcePreview,
    "source": SourceInput,
    "metric": MetricInput,
    "derived": DerivedInput,
    "locations": LocationsInput,
    "undo": Empty,
    "preview": Empty,
    "accept": Accept,
    "page": PagePreview,
    "report": Empty,
    "draft-export": Empty,
    "draft-import": ImportDraft,
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
                and path.suffix.lower() in {".tex", ".docx", ".pdf", ".csv", ".json"}
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

    def _advance(self):
        self.revision = secrets.token_hex(16)
        self.proposal = self.preview = None

    def _require_draft(self):
        if self.draft is None:
            raise PaperDeltaError("STUDIO_SETUP", msg("studio.setup_required"))
        return builder.resume_draft(self.project, self.draft)

    def _stage(self, draft):
        if sum(len(items) for items in draft["additions"].values()) > 500:
            raise PaperDeltaError("STUDIO_LIMIT", msg("studio.stage_limit"))
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
        }
        if self.draft is None:
            result["files"] = project_files(self.project)
            return result
        try:
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
        for candidate in self.scan["candidates"][:MAX_CANDIDATES]:
            bound = [
                name
                for name, location in occupied
                if location["file"] == candidate["file"]
                and location["start"] < candidate["end"]
                and candidate["start"] < location["end"]
            ]
            candidates.append({**candidate, "label": location_label(candidate), "bound": bound})
        builder.resume_draft(self.project, self.draft)
        result.update(
            sources={name: source.model_dump() for name, source in config.sources.items()},
            discovered_sources=self.scan["sources"],
            metrics=metrics,
            candidates=candidates,
            candidate_total=len(self.scan["candidates"]),
            candidate_limit=MAX_CANDIDATES,
            unsupported=self.scan["unsupported"],
            additions=draft.additions.model_dump(),
            coverage=self.report["coverage"],
            check_exit_code=self.report["exit_code"],
        )
        return result

    def execute(self, value):
        request = validate_record(Request, value, "STUDIO_REQUEST")
        model = PARAMETERS.get(request.action)
        if model is None:
            raise PaperDeltaError("STUDIO_REQUEST", msg("studio.unknown_action"))
        parameters = validate_record(model, request.payload, "STUDIO_REQUEST").model_dump()
        if request.action != "state" and request.revision != self.revision:
            raise PaperDeltaError("STUDIO_REVISION", msg("studio.revision"))
        with language_context(request.language):
            result = self._execute(request.action, parameters)
        return browser_value(translated(result, request.language))

    def _execute(self, action, parameters):
        if action == "state":
            return {"state": self.state()}
        if action == "refresh":
            self.refresh()
        elif action == "initialize":
            if self.draft is not None:
                raise PaperDeltaError("ALREADY_EXISTS", msg("error.ALREADY_EXISTS"))
            with _write_lock(self.project):
                init_project(self.project, config_path=self.config_path, **parameters)
            self.refresh()
        elif action == "source-preview":
            summary, identity = _source_summary(self.project, parameters["path"])
            if summary["format"] == "csv":
                text, raw = self.project.text(parameters["path"])
                if sha256(raw) != identity:
                    raise PaperDeltaError("STALE_DRAFT", msg("studio.changed"))
                reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
                start = parameters["offset"]
                rows = []
                for index, row in enumerate(reader):
                    if start <= index < start + 100:
                        rows.append(row)
                    if index >= start + 100:
                        break
                summary["sample"] = rows
                summary["offset"] = start
            return {"source": {**summary, "hash": identity}}
        else:
            self._require_draft()
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
                self.draft = self.history.pop()
                self._advance()
            elif action == "preview":
                proposal = builder.finalize_draft(self.project, self.draft)
                _, _, report = inspect_proposal(self.project, proposal)
                items = []
                for binding, rationale in proposal["rationale"].items():
                    group, name = binding.split(":", 1)
                    item = report[group][name]
                    candidate = next(
                        (
                            entry
                            for entry in self.scan["candidates"]
                            if entry["file"] == item["location"]["file"]
                            and entry["start"] == item["location"]["start"]
                        ),
                        {},
                    )
                    items.append(
                        {
                            "binding": binding,
                            "rationale": rationale,
                            **item,
                            "label": location_label(item["location"]),
                            "context_before": candidate.get("context_before", ""),
                            "context_after": candidate.get("context_after", ""),
                            "candidate_text": candidate.get("text", item["location"]["text"]),
                        }
                    )
                self.proposal = proposal
                self.preview = {
                    "proposal_id": proposal["proposal_id"],
                    "items": items,
                    "metrics": report["metrics"],
                    "coverage": report["coverage"],
                    "diagnostics": report["diagnostics"],
                    "exit_code": report["exit_code"],
                }
            elif action == "accept":
                if (
                    self.proposal is None
                    or parameters["proposal_id"] != self.proposal["proposal_id"]
                ):
                    raise PaperDeltaError("STUDIO_PREVIEW", msg("studio.preview_required"))
                self.receipt = accept_bindings(self.project, self.proposal, parameters["selected"])
                # The write succeeded even if the next scan encounters a concurrent
                # edit. Return that receipt so clients never mistake it for failure.
                try:
                    self.refresh()
                except PaperDeltaError:
                    self._advance()
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
                return {"preview": pdf_previews(self.project, report, max_pages=1)}
            elif action == "report":
                from paperdelta.i18n import current_language

                report = check_project(self.project.root, self.config_path)
                return {
                    "html": html_report(report, previews=pdf_previews(self.project, report)),
                    "language": current_language(),
                }
            elif action == "draft-export":
                return {"json": json_text(self.draft)}
            elif action == "draft-import":
                draft, _ = builder.resume_draft(self.project, parameters["draft"])
                if (
                    draft.config_path != self.config_path
                    or draft.additions.claims
                    or draft.additions.figures
                ):
                    raise PaperDeltaError("STUDIO_DRAFT", msg("studio.draft_project"))
                self._stage(draft.model_dump())
        return {"state": self.state()}
