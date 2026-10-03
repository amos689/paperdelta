"""Validated local records. Their hashes provide identity, not authentication."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Annotated, Any, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from paperdelta.errors import PaperDeltaError, error_message, validation_error
from paperdelta.i18n import msg
from paperdelta.models import (
    DerivedMetric,
    Hash,
    Identifier,
    Scalar,
    SourceMetric,
    StrictModel,
    Unit,
    VersionOne,
)

Nonnegative = Annotated[int, Field(ge=0)]
Positive = Annotated[int, Field(ge=1)]
CheckStatus = Literal["pass", "mismatch", "unknown"]
ChangeKind = Literal["added", "changed", "unchanged", "unavailable", "definition_changed"]


class SourceLocation(StrictModel):
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


class Evidence(StrictModel):
    source: Identifier
    path: str
    field: str
    where: dict[str, Scalar]
    reduce: Literal["unique", "mean", "sum", "count"]
    count: Positive
    records: list[CsvRecord | JsonRecord]
    locations: list[CsvLocation | JsonLocation]

    @model_validator(mode="after")
    def complete_rows(self):
        if len(self.records) != self.count:
            raise validation_error(msg("validation.records.5"))
        if all(isinstance(record, CsvRecord) for record in self.records):
            if len(self.locations) != self.count or any(
                not isinstance(location, CsvLocation) for location in self.locations
            ):
                raise validation_error(msg("validation.records.17"))
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


class Coverage(StrictModel):
    confirmed: Nonnegative
    pass_: Nonnegative = Field(alias="pass")
    mismatch: Nonnegative
    unknown: Nonnegative
    candidate_numbers: Nonnegative
    unbound_numbers: list[SourceLocation]
    unregistered_figures: list[UnregisteredFigure]
    unsupported: list[UnsupportedRegion]

    @model_validator(mode="after")
    def counted_checks(self):
        if self.confirmed != self.pass_ + self.mismatch + self.unknown:
            raise validation_error(msg("validation.records.14"))
        if len(self.unbound_numbers) > self.candidate_numbers:
            raise validation_error(msg("validation.records.15"))
        return self


class StoredReport(TimestampedRecord):
    report_schema_version: VersionOne
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

    @model_validator(mode="after")
    def counted_verdicts(self):
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
