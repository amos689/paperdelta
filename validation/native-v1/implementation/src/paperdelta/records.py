"""Validated local records. Their hashes provide identity, not authentication."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import Field, ValidationError, field_validator, model_serializer, model_validator

from paperdelta.errors import PaperDeltaError, error_message, validation_error
from paperdelta.evidence_models import ImportRequest
from paperdelta.i18n import msg
from paperdelta.models import (
    Aggregation,
    ConfidenceInterval,
    Coordinate,
    DerivedMetric,
    Hash,
    Identifier,
    ReviewScope,
    Scalar,
    SourceMetric,
    StrictModel,
    Unit,
    VersionOne,
)

Nonnegative = Annotated[int, Field(ge=0)]
Positive = Annotated[int, Field(ge=1)]
REPORT_SCHEMA_MAX = 7
CheckStatus = Literal["pass", "mismatch", "unknown"]
ChangeKind = Literal["added", "changed", "unchanged", "unavailable", "definition_changed"]


class LatexLocation(StrictModel):
    file: str
    start: Nonnegative
    end: Nonnegative
    byte_start: Nonnegative
    byte_end: Nonnegative
    line: Positive
    column: Positive
    text: str

    @model_validator(mode="after")
    def ordered_span(self):
        if self.end <= self.start or self.byte_end <= self.byte_start:
            raise validation_error(msg("validation.records"))
        if self.end - self.start != len(self.text):
            raise validation_error(msg("validation.records.2"))
        if self.byte_end - self.byte_start != len(self.text.encode("utf-8")):
            raise validation_error(msg("validation.records.3"))
        return self


class DocxLocator(StrictModel):
    part: Literal["word/document.xml", "word/footnotes.xml", "word/endnotes.xml"]
    paragraph: Positive
    style: str
    section: list[str]
    table: Positive | None = None
    row: Positive | None = None
    cell: Positive | None = None
    block: Hash
    offset: Nonnegative
    note_id: Nonnegative | None = None
    column_span: Annotated[int, Field(ge=2, le=100)] | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        value = handler(self)
        for key in ("note_id", "column_span"):
            if value.get(key) is None:
                value.pop(key, None)
        return value

    @model_validator(mode="after")
    def complete_cell(self):
        if (self.part != "word/document.xml") != (self.note_id is not None):
            raise validation_error(msg("document.location"))
        if self.column_span is not None and self.cell is None:
            raise validation_error(msg("document.location"))
        if any(v is not None for v in (self.table, self.row, self.cell)) and any(
            v is None for v in (self.table, self.row, self.cell)
        ):
            raise validation_error(msg("document.location"))
        return self


class DocxLocation(StrictModel):
    file: str
    start: Nonnegative
    end: Nonnegative
    text: str
    format: Literal["docx"]
    parser: str = Field(min_length=1)
    locator: DocxLocator
    context: str

    @model_validator(mode="after")
    def ordered_span(self):
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise validation_error(msg("document.location"))
        return self


class PdfLocator(StrictModel):
    page: Annotated[int, Field(ge=1, le=200)]
    bbox: Annotated[list[Coordinate], Field(min_length=4, max_length=4)]
    page_box: Annotated[list[Coordinate], Field(min_length=4, max_length=4)]
    block: Hash
    offset: Nonnegative
    region: Identifier | None = None
    table: Positive | None = None
    row: Positive | None = None
    cell: Positive | None = None

    @model_validator(mode="after")
    def ordered_box(self):
        outer, box = self.page_box, self.bbox
        if not (
            outer[0] <= box[0] < box[2] <= outer[2] and outer[1] <= box[1] < box[3] <= outer[3]
        ):
            raise validation_error(msg("pdf.region_box"))
        if any(v is not None for v in (self.table, self.row, self.cell)) and any(
            v is None for v in (self.table, self.row, self.cell)
        ):
            raise validation_error(msg("document.location"))
        return self


class PdfLocation(StrictModel):
    file: str
    start: Nonnegative
    end: Nonnegative
    text: str
    format: Literal["pdf"]
    parser: str = Field(min_length=1)
    locator: PdfLocator
    context: str

    @model_validator(mode="after")
    def ordered_span(self):
        if self.end <= self.start or self.end - self.start != len(self.text):
            raise validation_error(msg("document.location"))
        return self


SourceLocation = LatexLocation | DocxLocation | PdfLocation


class EvidenceDatum(StrictModel):
    # A count can select arbitrary JSON values; their container is versioned
    # even when the source payload has no domain-specific schema.
    value: Any

    @field_validator("value")
    @classmethod
    def json_value(cls, value):
        def check(item):
            if item is None or type(item) in {str, bool, int}:
                return
            if isinstance(item, Decimal) and item.is_finite():
                return
            if isinstance(item, list):
                for child in item:
                    check(child)
                return
            if isinstance(item, dict) and all(isinstance(key, str) for key in item):
                for child in item.values():
                    check(child)
                return
            raise validation_error(msg("validation.records.4"))

        check(value)
        return value


class CsvRecord(EvidenceDatum):
    key: dict[str, Scalar]


class JsonRecord(EvidenceDatum):
    index: Nonnegative


class CsvLocation(StrictModel):
    key: dict[str, Scalar]
    line: Positive


class JsonLocation(StrictModel):
    pointer: str


class XlsxLocation(StrictModel):
    key: dict[str, Scalar]
    sheet: str
    row: Positive
    cell: Annotated[str, Field(pattern=r"^[A-Z]{1,3}[1-9][0-9]{0,6}$")]


class ExportLocation(StrictModel):
    key: dict[str, Scalar]
    snapshot: Hash
    pointer: str


class ExportProvenance(StrictModel):
    export_id: Hash
    tool_version: str
    provider: Literal["file", "mlflow", "wandb"]
    origin: str
    created_at: str
    precision: Literal["stored-lexemes", "api-double", "sdk-binary64"]
    selection: ImportRequest
    snapshot_hashes: list[Hash] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def consistent_provenance(self):
        expected = {"file": "stored-lexemes", "mlflow": "api-double", "wandb": "sdk-binary64"}
        if (
            self.provider != self.selection.provider
            or self.origin != self.selection.origin
            or self.precision != expected[self.provider]
            or datetime.fromisoformat(self.created_at).tzinfo is None
        ):
            raise validation_error(msg("export.provenance"))
        return self


class Evidence(StrictModel):
    source: Identifier
    path: str
    field: str
    where: dict[str, Scalar]
    reduce: Aggregation
    count: Positive
    records: list[CsvRecord | JsonRecord]
    locations: list[CsvLocation | JsonLocation | XlsxLocation | ExportLocation]
    format: Literal["tsv", "xlsx", "records"] | None = None
    provenance: ExportProvenance | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        value = handler(self)
        if value.get("format") is None:
            value.pop("format", None)
        if value.get("provenance") is None:
            value.pop("provenance", None)
        return value

    @model_validator(mode="after")
    def complete_rows(self):
        if len(self.records) != self.count:
            raise validation_error(msg("validation.records.5"))
        if (self.format == "records") != (self.provenance is not None):
            raise validation_error(msg("export.provenance"))
        if all(isinstance(record, CsvRecord) for record in self.records):
            location_type = {"xlsx": XlsxLocation, "records": ExportLocation}.get(
                self.format, CsvLocation
            )
            if len(self.locations) != self.count or any(
                not isinstance(location, location_type) for location in self.locations
            ):
                raise validation_error(msg("validation.records.17"))
            if self.provenance and any(
                location.snapshot not in self.provenance.snapshot_hashes
                for location in self.locations
            ):
                raise validation_error(msg("export.provenance"))
        elif any(isinstance(record, CsvRecord) for record in self.records) or (
            len(self.locations) != 1 or not isinstance(self.locations[0], JsonLocation)
        ):
            raise validation_error(msg("validation.records.18"))
        return self


class TimestampedRecord(StrictModel):
    created_at: str

    @field_validator("created_at")
    @classmethod
    def timestamp(cls, value):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise validation_error(msg("validation.records.6"))
        return value


class FileIdentity(StrictModel):
    path: str
    hash: Hash


class FigureRecord(StrictModel):
    schema_version: VersionOne
    path: str
    output_hash: Hash
    inputs: dict[str, Hash] = Field(min_length=1)
    script: FileIdentity
    recorded_at: str
    method: Literal["manual", "imported"]

    @field_validator("recorded_at")
    @classmethod
    def timestamp(cls, value):
        return TimestampedRecord.timestamp(value)

    @model_validator(mode="after")
    def consistent_identities(self):
        identities = {**self.inputs, self.path: self.output_hash}
        if self.script.path in identities and identities[self.script.path] != self.script.hash:
            raise validation_error(msg("validation.records.7"))
        if self.path in self.inputs and self.inputs[self.path] != self.output_hash:
            raise validation_error(msg("validation.records.8"))
        return self


class ConfidenceIntervalResult(ConfidenceInterval):
    df: Annotated[int, Field(ge=1, le=9999)]
    critical_value: str
    lower: str
    upper: str
    quantile_engine: str = Field(pattern=r"^mpmath-[0-9]+\.[0-9]+\.[0-9]+$")


class StatisticalSummary(StrictModel):
    mean: str
    sd: str
    se: str
    n: Annotated[int, Field(ge=1, le=10000)]
    ddof: Annotated[int, Field(ge=0, le=1)]
    unit_of_analysis: str
    arithmetic: Literal["rational-moments-decimal-sqrt-v1"]
    precision_digits: Annotated[int, Field(ge=80, le=260)]
    confidence_interval: ConfidenceIntervalResult | None = None

    @model_validator(mode="after")
    def finite_consistent(self):
        values = [self.mean, self.sd, self.se]
        interval = self.confidence_interval
        if interval:
            values.extend([interval.critical_value, interval.lower, interval.upper])
        try:
            if any(len(value) > 2000 or not Decimal(value).is_finite() for value in values):
                raise ValueError
            if Decimal(self.sd) < 0 or Decimal(self.se) < 0 or self.n <= self.ddof:
                raise ValueError
            if interval and (
                self.ddof != 1
                or interval.df != self.n - 1
                or not Decimal(interval.lower) <= Decimal(self.mean) <= Decimal(interval.upper)
                or Decimal(interval.critical_value) <= 0
            ):
                raise ValueError
        except (InvalidOperation, ValueError) as exc:
            raise validation_error(msg("statistics.result")) from exc
        return self


class MetricState(StrictModel):
    status: Literal["ok", "unknown"]
    value: str | None = None
    unit: Unit | None = None
    fingerprint: Hash | None = None
    definition_fingerprint: Hash | None = None
    definition: SourceMetric | DerivedMetric | None = None
    evidence: list[Evidence] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    error: str | None = None
    message: str | None = None
    change: ChangeKind | None = None
    statistics: StatisticalSummary | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        value = handler(self)
        if value.get("statistics") is None:
            value.pop("statistics", None)
        return value

    @field_validator("value")
    @classmethod
    def finite_decimal_text(cls, value):
        if value is not None:
            try:
                finite = Decimal(value).is_finite()
            except InvalidOperation:
                finite = False
            if not finite:
                raise validation_error(msg("validation.records.19"))
        return value

    @model_validator(mode="after")
    def complete_success(self):
        if self.status == "ok" and (
            (getattr(self.definition, "statistics", None) is not None)
            != (self.statistics is not None)
            or (self.statistics is not None and self.value != self.statistics.mean)
        ):
            raise validation_error(msg("statistics.result"))
        if self.statistics is not None:
            if (
                self.status != "ok"
                or not isinstance(self.definition, SourceMetric)
                or self.definition.statistics is None
            ):
                raise validation_error(msg("statistics.result"))
            summary, contract = self.statistics, self.definition.statistics
            if (
                self.status != "ok"
                or summary.n != self.definition.expected_count
                or summary.ddof != contract.ddof
                or summary.unit_of_analysis != contract.unit_of_analysis
                or len(self.evidence) != 1
                or self.evidence[0].reduce != "statistics"
                or self.evidence[0].count != summary.n
                or (summary.confidence_interval is None) != (contract.confidence_interval is None)
            ):
                raise validation_error(msg("statistics.result"))
            if summary.confidence_interval and any(
                getattr(summary.confidence_interval, key)
                != getattr(contract.confidence_interval, key)
                for key in ("method", "level", "assumption")
            ):
                raise validation_error(msg("statistics.result"))
        if self.status == "ok" and any(
            value is None
            for value in (self.value, self.unit, self.fingerprint, self.definition_fingerprint)
        ):
            raise validation_error(msg("validation.records.9"))
        return self


class Suggestion(StrictModel):
    replacement: str
    blocked_by: list[str]


class OccurrenceState(StrictModel):
    metric: Identifier
    status: CheckStatus
    location: SourceLocation | None = None
    expected: str | None = None
    actual: str | None = None
    evidence_fingerprint: Hash | None = None
    suggestion: Suggestion | None = None
    error: str | None = None

    @model_validator(mode="after")
    def completed_check(self):
        if self.status != "unknown" and any(
            value is None
            for value in (self.location, self.expected, self.actual, self.evidence_fingerprint)
        ):
            raise validation_error(msg("validation.records.10"))
        if self.suggestion is not None and self.status != "mismatch":
            raise validation_error(msg("validation.records.11"))
        return self


class ClaimState(StrictModel):
    status: CheckStatus
    metrics: list[Identifier]
    location: SourceLocation | None = None
    state_fingerprint: Hash | None = None
    review: Literal["unreviewed", "reviewed", "superseded"] = "unreviewed"
    review_records: list[ReviewRecord] = Field(default_factory=list)
    matching_reviews: list[Hash] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def completed_check(self):
        if self.status != "unknown" and (self.location is None or self.state_fingerprint is None):
            raise validation_error(msg("validation.records.12"))
        return self


class FigureState(StrictModel):
    path: str
    status: CheckStatus
    provenance: Literal["unknown", "dependency_changed", "unchanged_since_record"]
    record_method: Literal["manual", "imported"] | None = None
    dependencies: list[str] = Field(default_factory=list)
    changed_paths: list[str] = Field(default_factory=list)
    error: str | None = None

    @model_validator(mode="after")
    def completed_check(self):
        if self.status != "unknown" and (self.record_method is None or not self.dependencies):
            raise validation_error(msg("validation.records.13"))
        return self


class Diagnostic(StrictModel):
    id: str
    rule: str
    subject: str
    severity: Literal["error", "unknown", "warning"]
    message: str
    location: SourceLocation | None = None


class Change(StrictModel):
    metric: Identifier
    kind: ChangeKind
    before: str | None
    after: str | None
    unit: Unit | None
    occurrences: list[Identifier]
    claims: list[Identifier]


class ImpactGroup(StrictModel):
    metric: Identifier
    sources: list[str]
    metrics: list[Identifier]
    occurrences: list[Identifier]
    claims: list[Identifier]
    figures: list[Identifier]
    change: ChangeKind


class BaselineReference(StrictModel):
    name: str
    created_at: str


class UnsupportedRegion(StrictModel):
    code: str
    file: str
    message: str


class UnregisteredFigure(StrictModel):
    file: str
    reference: str
    resolved: list[str]
    reason: Literal["not registered", "missing or ambiguous"]


class ExclusionState(StrictModel):
    id: Identifier
    reason: str
    status: Literal["active", "stale"]
    location: SourceLocation | None = None
    error: str | None = None


class Coverage(StrictModel):
    confirmed: Nonnegative
    pass_: Nonnegative = Field(alias="pass")
    mismatch: Nonnegative
    unknown: Nonnegative
    candidate_numbers: Nonnegative
    unbound_numbers: list[SourceLocation]
    unregistered_figures: list[UnregisteredFigure]
    unsupported: list[UnsupportedRegion]
    review_scope: ReviewScope | None = None
    outside_scope_numbers: list[SourceLocation] = Field(default_factory=list)
    exclusions: list[ExclusionState] = Field(default_factory=list)

    @model_validator(mode="after")
    def counted_checks(self):
        if self.confirmed != self.pass_ + self.mismatch + self.unknown:
            raise validation_error(msg("validation.records.14"))
        if len(self.unbound_numbers) > self.candidate_numbers:
            raise validation_error(msg("validation.records.15"))
        return self


class ReviewAction(StrictModel):
    kind: Literal[
        "wait_for_check",
        "resolve_evidence",
        "repair_bindings",
        "review_exclusions",
        "review_claims",
        "update_numbers",
        "update_document",
        "reexport_pdf",
        "update_figures",
        "complete_coverage",
    ]
    subjects: list[str]
    findings: list[str]


class WatchState(StrictModel):
    state: Literal["running", "pending", "stopped"]
    generation: Nonnegative
    changed_paths: list[str]


class ExportState(StrictModel):
    file: str
    source: str
    metric: Identifier | None
    status: Literal["aligned", "stale", "unknown", "source_outdated"]
    source_bindings: list[Identifier]
    export_bindings: list[Identifier]


class StoredReport(TimestampedRecord):
    report_schema_version: Annotated[int, Field(ge=1, le=REPORT_SCHEMA_MAX)]
    tool_version: str
    ruleset_version: str
    config_path: str
    input_hashes: dict[str, Hash]
    metrics: dict[str, MetricState]
    occurrences: dict[Identifier, OccurrenceState]
    claims: dict[Identifier, ClaimState]
    figures: dict[Identifier, FigureState]
    diagnostics: list[Diagnostic]
    changes: list[Change]
    impact_groups: list[ImpactGroup] = Field(default_factory=list)
    baseline: BaselineReference | None
    coverage: Coverage
    exit_code: Literal[0, 1, 2]
    config_fingerprint: Hash | None = None
    configuration_changed: bool | None = None
    removed_bindings: dict[str, list[str]] | None = None
    watch: WatchState | None = None
    actions: list[ReviewAction] = Field(default_factory=list)
    exports: list[ExportState] = Field(default_factory=list)

    @model_validator(mode="after")
    def counted_verdicts(self):
        if self.report_schema_version < 6 and any(
            metric.statistics is not None
            or getattr(metric.definition, "statistics", None)
            or any(evidence.reduce == "statistics" for evidence in metric.evidence)
            for metric in self.metrics.values()
        ):
            raise validation_error(msg("statistics.report_schema"))
        if self.report_schema_version < 5 and any(
            evidence.format is not None
            for metric in self.metrics.values()
            for evidence in metric.evidence
        ):
            raise validation_error(msg("evidence.report_schema"))
        locations = [
            *(
                item.location
                for item in [*self.occurrences.values(), *self.claims.values(), *self.diagnostics]
            ),
            *self.coverage.unbound_numbers,
            *self.coverage.outside_scope_numbers,
            *(item.location for item in self.coverage.exclusions),
        ]
        if self.report_schema_version < 7 and any(
            isinstance(item, DocxLocation)
            and (item.locator.note_id is not None or item.locator.column_span is not None)
            for item in locations
        ):
            raise validation_error(msg("document.layout_report_schema"))
        if self.report_schema_version < 3 and any(
            isinstance(item, DocxLocation) for item in locations
        ):
            raise validation_error(msg("document.report_schema"))
        if self.report_schema_version < 4 and (
            self.exports or any(isinstance(item, PdfLocation) for item in locations)
        ):
            raise validation_error(msg("pdf.report_schema"))
        states = [*self.occurrences.values(), *self.claims.values(), *self.figures.values()]
        if len(states) != self.coverage.confirmed or any(
            sum(item.status == status for item in states) != count
            for status, count in [
                ("pass", self.coverage.pass_),
                ("mismatch", self.coverage.mismatch),
                ("unknown", self.coverage.unknown),
            ]
        ):
            raise validation_error(msg("validation.records.16"))
        return self


class Snapshot(TimestampedRecord):
    snapshot_schema_version: VersionOne
    name: str
    report: StoredReport


class ReviewRecord(TimestampedRecord):
    review_schema_version: VersionOne
    record_id: Hash
    claim: Identifier
    state_fingerprint: Hash
    reviewer: str = Field(min_length=1, max_length=200)
    note: str = Field(max_length=4000)
    assertion: Literal["I reviewed this claim and its selected evidence"]


# Resolve ClaimState's review-record reference after all record types exist.
ClaimState.model_rebuild()
StoredReport.model_rebuild()
Snapshot.model_rebuild()


def validate_record(model, value, code: str):
    try:
        return model.model_validate(value)
    except (ValidationError, RecursionError) as exc:
        raise PaperDeltaError(code, error_message(exc)) from exc
