"""Versioned, strict contracts shared by the CLI and agent adapters."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StrictStr,
    model_serializer,
    model_validator,
)

from paperdelta.errors import validation_error
from paperdelta.i18n import msg

Scalar = StrictStr | StrictInt | Decimal
Unit = Literal["scalar", "fraction", "percent", "percentage_point", "count", "ratio"]
SourceFormat = Literal["csv", "json"]
ColumnType = Literal["string", "integer", "decimal"]
Aggregation = Literal["unique", "mean", "sum", "count"]
DisplayKind = Literal["decimal", "percent", "integer", "scientific"]
DerivedOperation = Literal[
    "difference", "ratio", "percentage_point_difference", "relative_change_percent"
]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,99}$")]
Hash = Annotated[str, Field(pattern=r"^sha256:[a-f0-9]{64}$")]
VersionOne = Annotated[int, Field(ge=1, le=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Paper(StrictModel):
    entry: str
    macros: dict[str, Annotated[int, Field(ge=0, le=9)]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def macro_names(self) -> Self:
        if any(not re.fullmatch(r"[A-Za-z]+", key) for key in self.macros):
            raise validation_error(msg("validation.models"))
        return self


class Source(StrictModel):
    path: str
    format: SourceFormat
    primary_key: list[str] = Field(default_factory=list)
    columns: dict[str, ColumnType] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_format(self) -> Self:
        if self.format == "csv":
            if not self.primary_key or not self.columns:
                raise validation_error(msg("validation.models.3"))
            if len(set(self.primary_key)) != len(self.primary_key):
                raise validation_error(msg("validation.models.4"))
            if not set(self.primary_key).issubset(self.columns):
                raise validation_error(msg("validation.models.5"))
        elif self.primary_key or self.columns:
            raise validation_error(msg("validation.models.6"))
        return self


class SourceMetric(StrictModel):
    source: Identifier
    field: str
    where: dict[str, Scalar] = Field(default_factory=dict)
    reduce: Aggregation = "unique"
    expected_seeds: list[StrictStr | StrictInt] | None = None
    seed_column: str = "seed"
    expected_count: Annotated[int, Field(ge=1)] | None = None
    unit: Unit

    @model_validator(mode="after")
    def validate_seeds(self) -> Self:
        if self.expected_seeds is not None:
            if not self.expected_seeds or len(set(self.expected_seeds)) != len(self.expected_seeds):
                raise validation_error(msg("validation.models.7"))
        if self.reduce == "count" and self.unit != "count":
            raise validation_error(msg("validation.models.2"))
        return self


class DerivedMetric(StrictModel):
    op: DerivedOperation
    args: Annotated[list[Identifier], Field(min_length=2, max_length=2)]


class TableCellAnchor(StrictModel):
    headers: Annotated[list[str], Field(min_length=1, max_length=20)]
    row_prefix: Annotated[list[str], Field(min_length=1, max_length=20)]
    column: Annotated[int, Field(ge=1, le=100)]
    percent_symbol: bool = False


class Anchor(StrictModel):
    exact: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    table: TableCellAnchor | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        value = handler(self)
        if self.table is None:
            value.pop("table", None)
        return value

    @model_validator(mode="after")
    def exactly_one_mode(self) -> Self:
        if self.table is not None:
            if any(item is not None for item in (self.exact, self.prefix, self.suffix)):
                raise validation_error(msg("validation.models.8"))
        elif self.exact is not None:
            if not self.exact or self.prefix is not None or self.suffix is not None:
                raise validation_error(msg("validation.models.8"))
        elif not self.prefix or not self.suffix:
            raise validation_error(msg("validation.models.9"))
        return self


class Display(StrictModel):
    kind: DisplayKind = "decimal"
    places: Annotated[int, Field(ge=0, le=15)] = 1
    percent_symbol: bool = True


class Occurrence(StrictModel):
    file: str
    anchor: Anchor
    metric: Identifier
    display: Display = Field(default_factory=Display)


class Threshold(StrictModel):
    value: Scalar
    unit: Unit


class Predicate(StrictModel):
    op: Literal["greater_than", "greater_equal", "less_than", "less_equal", "equal", "best_in_set"]
    left: Identifier
    right: Identifier | Threshold | None = None
    candidates: list[Identifier] = Field(default_factory=list)
    direction: Literal["maximize", "minimize"] | None = None
    allow_ties: bool = False

    @model_validator(mode="after")
    def validate_operands(self) -> Self:
        if self.op == "best_in_set":
            if self.right is not None or not self.candidates or self.direction is None:
                raise validation_error(msg("validation.models.10"))
            if len(set(self.candidates)) != len(self.candidates) or self.left in self.candidates:
                raise validation_error(msg("validation.models.11"))
        elif self.right is None or self.candidates or self.direction is not None or self.allow_ties:
            raise validation_error(msg("validation.models.12"))
        return self


class Claim(StrictModel):
    file: str
    anchor: Anchor
    predicate: Predicate
    scope: dict[str, Scalar] = Field(default_factory=dict)


class Figure(StrictModel):
    path: str
    record: str | None = None


class ReviewScope(StrictModel):
    files: list[str] = Field(default_factory=list)
    regions: list[Literal["abstract", "table"]] = Field(default_factory=list)

    @model_validator(mode="after")
    def nonempty_selection(self) -> Self:
        if not self.files and not self.regions:
            raise validation_error(msg("scope.empty"))
        if len(set(self.files)) != len(self.files) or len(set(self.regions)) != len(self.regions):
            raise validation_error(msg("scope.duplicate"))
        return self


class CoverageExclusion(StrictModel):
    file: str
    anchor: Anchor
    reason: str = Field(min_length=1, max_length=2000)
    context_hash: Hash

    @model_validator(mode="after")
    def meaningful_reason(self) -> Self:
        if not self.reason.strip():
            raise validation_error(msg("scope.reason_required"))
        return self


class Config(StrictModel):
    schema_version: Annotated[int, Field(ge=1, le=2)]
    paper: Paper
    rounding: Literal["half_up", "half_even"] = "half_up"
    sources: dict[Identifier, Source] = Field(default_factory=dict)
    metrics: dict[Identifier, SourceMetric | DerivedMetric] = Field(default_factory=dict)
    occurrences: dict[Identifier, Occurrence] = Field(default_factory=dict)
    claims: dict[Identifier, Claim] = Field(default_factory=dict)
    figures: dict[Identifier, Figure] = Field(default_factory=dict)
    require_complete_coverage: bool = False
    review_scope: ReviewScope | None = None
    coverage_exclusions: dict[Identifier, CoverageExclusion] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        if self.schema_version == 1 and (
            self.review_scope
            or self.coverage_exclusions
            or any(
                item.anchor.table is not None
                for item in [*self.occurrences.values(), *self.claims.values()]
            )
        ):
            raise validation_error(msg("scope.version"))
        dependencies: dict[str, list[str]] = {}
        for name, metric in self.metrics.items():
            if isinstance(metric, SourceMetric):
                if metric.source not in self.sources:
                    raise validation_error(
                        msg("validation.models.17", name=name, value2=metric.source)
                    )
                dependencies[name] = []
            else:
                dependencies[name] = metric.args
        for name, edges in dependencies.items():
            if any(edge not in self.metrics for edge in edges):
                raise validation_error(msg("validation.models.13", name=name))
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                raise validation_error(msg("validation.models.14", name=name))
            if name in visited:
                return
            visiting.add(name)
            for edge in dependencies[name]:
                visit(edge)
            visiting.remove(name)
            visited.add(name)

        for name in dependencies:
            visit(name)
        for name, occurrence in self.occurrences.items():
            if occurrence.metric not in self.metrics:
                raise validation_error(
                    msg("validation.models.15", name=name, value2=occurrence.metric)
                )
        for name, claim in self.claims.items():
            refs = [claim.predicate.left, *claim.predicate.candidates]
            if isinstance(claim.predicate.right, str):
                refs.append(claim.predicate.right)
            if any(ref not in self.metrics for ref in refs):
                raise validation_error(msg("validation.models.16", name=name))
        return self
