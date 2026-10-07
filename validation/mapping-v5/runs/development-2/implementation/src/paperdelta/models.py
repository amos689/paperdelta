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
SourceFormat = Literal["csv", "json", "tsv", "xlsx", "records"]
ColumnType = Literal["string", "integer", "decimal"]
Aggregation = Literal["unique", "mean", "sum", "count", "statistics"]
DisplayKind = Literal["decimal", "percent", "integer", "scientific"]
DerivedOperation = Literal[
    "difference", "ratio", "percentage_point_difference", "relative_change_percent"
]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,99}$")]
Hash = Annotated[str, Field(pattern=r"^sha256:[a-f0-9]{64}$")]
VersionOne = Annotated[int, Field(ge=1, le=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


Coordinate = Annotated[StrictInt | Decimal, Field(ge=0, le=20000)]


class PdfRegion(StrictModel):
    name: Identifier
    page: Annotated[int, Field(ge=1, le=200)]
    bbox: Annotated[list[Coordinate], Field(min_length=4, max_length=4)]
    kind: Literal["text", "table", "abstract"] = "text"

    @model_validator(mode="after")
    def ordered_box(self) -> Self:
        if self.bbox[0] >= self.bbox[2] or self.bbox[1] >= self.bbox[3]:
            raise validation_error(msg("pdf.region_box"))
        return self


class Manuscript(StrictModel):
    entry: str
    macros: dict[str, Annotated[int, Field(ge=0, le=9)]] = Field(default_factory=dict)
    pdf_regions: Annotated[list[PdfRegion], Field(max_length=200)] = Field(default_factory=list)
    export_of: str | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        value = handler(self)
        for key in ("pdf_regions", "export_of", "companions"):
            if not value.get(key):
                value.pop(key, None)
        return value

    @model_validator(mode="after")
    def macro_names(self) -> Self:
        if any(not re.fullmatch(r"[A-Za-z]+", key) for key in self.macros):
            raise validation_error(msg("validation.models"))
        if self.pdf_regions or self.export_of is not None:
            if not self.entry.lower().endswith(".pdf"):
                raise validation_error(msg("pdf.options_format"))
        if len({region.name for region in self.pdf_regions}) != len(self.pdf_regions):
            raise validation_error(msg("pdf.region_duplicate"))
        return self


class Paper(Manuscript):
    companions: Annotated[list[Manuscript], Field(max_length=20)] = Field(default_factory=list)


class Source(StrictModel):
    path: str
    format: SourceFormat
    primary_key: list[str] = Field(default_factory=list)
    columns: dict[str, ColumnType] = Field(default_factory=dict)
    sheet: str | None = None
    cell_range: str | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        value = handler(self)
        for key in ("sheet", "cell_range"):
            if value.get(key) is None:
                value.pop(key, None)
        return value

    @model_validator(mode="after")
    def validate_format(self) -> Self:
        if self.format != "json":
            if not self.primary_key or not self.columns:
                raise validation_error(msg("validation.models.3"))
            if len(set(self.primary_key)) != len(self.primary_key):
                raise validation_error(msg("validation.models.4"))
            if not set(self.primary_key).issubset(self.columns):
                raise validation_error(msg("validation.models.5"))
        elif self.primary_key or self.columns:
            raise validation_error(msg("validation.models.6"))
        if self.format == "xlsx":
            if not self.sheet or not self.cell_range:
                raise validation_error(msg("xlsx.selection"))
        elif self.sheet is not None or self.cell_range is not None:
            raise validation_error(msg("xlsx.only"))
        return self


class ConfidenceInterval(StrictModel):
    method: Literal["student_t"]
    level: str = Field(pattern=r"^0\.\d{1,6}$")
    assumption: Literal["independent_normal_observations"]

    @model_validator(mode="after")
    def supported_level(self) -> Self:
        if not Decimal("0.5") <= Decimal(self.level) <= Decimal("0.999"):
            raise validation_error(msg("statistics.level"))
        return self


class StatisticalContract(StrictModel):
    ddof: Annotated[StrictInt, Field(ge=0, le=1)]
    unit_of_analysis: str = Field(min_length=1, max_length=200)
    confidence_interval: ConfidenceInterval | None = None

    @model_validator(mode="after")
    def explicit_conventions(self) -> Self:
        if not self.unit_of_analysis.strip() or isinstance(self.ddof, bool):
            raise validation_error(msg("statistics.contract"))
        if self.confidence_interval is not None and self.ddof != 1:
            raise validation_error(msg("statistics.ci_ddof"))
        return self


StatisticalComponent = Literal[
    "mean",
    "sd",
    "se",
    "n",
    "ci_lower",
    "ci_upper",
    "confidence_level",
    "mean_sd",
    "mean_se",
    "ci",
    "mean_ci",
]


class StatisticalDisplay(StrictModel):
    component: StatisticalComponent
    show_n: bool = False
    spread_places: Annotated[int, Field(ge=0, le=15)] | None = None

    @property
    def compound(self) -> bool:
        return self.component in {"mean_sd", "mean_se", "ci", "mean_ci"}

    @model_validator(mode="after")
    def compound_options(self) -> Self:
        if not self.compound and (self.show_n or self.spread_places is not None):
            raise validation_error(msg("statistics.display"))
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
    statistics: StatisticalContract | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        value = handler(self)
        if value.get("statistics") is None:
            value.pop("statistics", None)
        return value

    @model_validator(mode="after")
    def validate_seeds(self) -> Self:
        if self.expected_seeds is not None:
            if not self.expected_seeds or len(set(self.expected_seeds)) != len(self.expected_seeds):
                raise validation_error(msg("validation.models.7"))
        if self.reduce == "count" and self.unit != "count":
            raise validation_error(msg("validation.models.2"))
        if (self.reduce == "statistics") != (self.statistics is not None):
            raise validation_error(msg("statistics.contract"))
        if self.statistics is not None and (
            self.expected_count is None
            or self.expected_seeds is None
            or len(self.expected_seeds) != self.expected_count
            or self.expected_count <= self.statistics.ddof
        ):
            raise validation_error(msg("statistics.expected"))
        return self


class DerivedMetric(StrictModel):
    op: DerivedOperation
    args: Annotated[list[Identifier], Field(min_length=2, max_length=2)]


class CellValueContext(StrictModel):
    """Reviewed literal structure around one value within a labelled table cell."""

    shape: str = Field(min_length=1, max_length=8000)
    prefix: str = Field(max_length=4000)
    suffix: str = Field(max_length=4000)


class ReviewedTableIdentity(StrictModel):
    header_rows: Annotated[int, Field(ge=1, le=20)]
    row_prefix: Annotated[list[str], Field(min_length=1, max_length=20)]


class TableCellAnchor(StrictModel):
    headers: Annotated[list[str], Field(min_length=1, max_length=20)]
    row_prefix: Annotated[list[str], Field(min_length=1, max_length=20)]
    column: Annotated[int, Field(ge=1, le=100)]
    percent_symbol: bool = False
    page: Annotated[int, Field(ge=1, le=200)] | None = None
    region: Identifier | None = None
    parser: str | None = Field(default=None, min_length=1, max_length=256)
    statistical_display: StatisticalDisplay | None = None
    header_rows: Annotated[int, Field(ge=1, le=20)] | None = None
    caption: str | None = Field(default=None, min_length=1, max_length=2000)
    value_context: CellValueContext | None = None

    @model_validator(mode="after")
    def explicit_header_boundary(self) -> Self:
        if (self.header_rows is not None and self.header_rows != len(self.headers)) or (
            self.caption is not None and self.header_rows is None
        ):
            raise validation_error(msg("document.header_boundary"))
        if self.value_context is not None and self.statistical_display is not None:
            raise validation_error(msg("document.cell_compound"))
        return self

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        value = handler(self)
        for key in (
            "page",
            "region",
            "parser",
            "statistical_display",
            "header_rows",
            "caption",
            "value_context",
        ):
            if value.get(key) is None:
                value.pop(key, None)
        return value


class Anchor(StrictModel):
    exact: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    table: TableCellAnchor | None = None
    block: Hash | None = None
    parser: str | None = Field(default=None, min_length=1, max_length=256)
    numeric_only: bool = False

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        value = handler(self)
        if self.table is None:
            value.pop("table", None)
        if self.block is None:
            value.pop("block", None)
        if self.parser is None:
            value.pop("parser", None)
        if not self.numeric_only:
            value.pop("numeric_only", None)
        return value

    @model_validator(mode="after")
    def exactly_one_mode(self) -> Self:
        if self.numeric_only and (self.block is None or self.table is not None or self.exact):
            raise validation_error(msg("document.numeric_context"))
        if self.table is not None:
            if any(
                item is not None
                for item in (self.exact, self.prefix, self.suffix, self.block, self.parser)
            ):
                raise validation_error(msg("validation.models.8"))
        elif self.exact is not None:
            if not self.exact or self.prefix is not None or self.suffix is not None:
                raise validation_error(msg("validation.models.8"))
        elif (self.prefix is None or self.suffix is None) or (
            self.block is None and (not self.prefix or not self.suffix)
        ):
            raise validation_error(msg("validation.models.9"))
        return self


class Display(StrictModel):
    kind: DisplayKind = "decimal"
    places: Annotated[int, Field(ge=0, le=15)] = 1
    percent_symbol: bool = True
    statistics: StatisticalDisplay | None = None

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        value = handler(self)
        if value.get("statistics") is None:
            value.pop("statistics", None)
        return value

    @model_validator(mode="after")
    def count_format(self) -> Self:
        if (
            self.statistics is not None
            and self.statistics.component == "n"
            and self.kind != "integer"
        ):
            raise validation_error(msg("statistics.n_display"))
        return self


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


class ProvenanceReference(StrictModel):
    record: str


class Config(StrictModel):
    schema_version: Annotated[int, Field(ge=1, le=10)]
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
    provenance: dict[Identifier, ProvenanceReference] = Field(default_factory=dict)
    fragments: dict[Identifier, ProvenanceReference] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def preserve_legacy_identity(self, handler):
        value = handler(self)
        if not value.get("provenance"):
            value.pop("provenance", None)
        if not value.get("fragments"):
            value.pop("fragments", None)
        return value

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        if (self.provenance or self.fragments) and self.schema_version < 10:
            raise validation_error(msg("provenance.schema"))
        if self.schema_version < 9 and any(
            item.anchor.numeric_only
            or (item.anchor.table and item.anchor.table.value_context is not None)
            for item in [
                *self.occurrences.values(),
                *self.claims.values(),
                *self.coverage_exclusions.values(),
            ]
        ):
            raise validation_error(msg("document.cell_schema"))
        if self.schema_version < 8 and any(
            item.entry.lower().endswith((".md", ".qmd"))
            for item in [self.paper, *self.paper.companions]
        ):
            raise validation_error(msg("markdown.schema"))
        if self.schema_version < 7 and any(
            item.anchor.table
            and (item.anchor.table.header_rows is not None or item.anchor.table.caption is not None)
            for item in [
                *self.occurrences.values(),
                *self.claims.values(),
                *self.coverage_exclusions.values(),
            ]
        ):
            raise validation_error(msg("document.layout_schema"))
        if self.schema_version < 6 and (
            any(getattr(metric, "statistics", None) for metric in self.metrics.values())
            or any(item.display.statistics for item in self.occurrences.values())
            or any(
                item.anchor.table and item.anchor.table.statistical_display
                for item in [
                    *self.occurrences.values(),
                    *self.claims.values(),
                    *self.coverage_exclusions.values(),
                ]
            )
        ):
            raise validation_error(msg("statistics.schema"))
        if self.schema_version < 5 and any(
            source.format not in {"csv", "json"} for source in self.sources.values()
        ):
            raise validation_error(msg("evidence.schema"))
        manuscripts = [self.paper, *self.paper.companions]
        if self.schema_version < 4 and (
            self.paper.companions
            or self.paper.pdf_regions
            or self.paper.export_of is not None
            or self.paper.entry.lower().endswith(".pdf")
            or any(
                item.anchor.parser is not None
                for item in [
                    *self.occurrences.values(),
                    *self.claims.values(),
                    *self.coverage_exclusions.values(),
                ]
            )
            or any(
                item.anchor.table is not None
                and (
                    item.anchor.table.page is not None
                    or item.anchor.table.region is not None
                    or item.anchor.table.parser is not None
                )
                for item in [
                    *self.occurrences.values(),
                    *self.claims.values(),
                    *self.coverage_exclusions.values(),
                ]
            )
        ):
            raise validation_error(msg("pdf.schema"))
        if len({item.entry for item in manuscripts}) != len(manuscripts):
            raise validation_error(msg("document.duplicate"))
        for item in manuscripts:
            if item.export_of is not None and not any(
                other.entry == item.export_of
                and other.entry.lower().endswith((".tex", ".docx", ".md", ".qmd"))
                for other in manuscripts
            ):
                raise validation_error(msg("pdf.export_source"))
        if self.schema_version < 3 and (
            not self.paper.entry.lower().endswith(".tex")
            or any(
                item.anchor.block is not None
                for item in [
                    *self.occurrences.values(),
                    *self.claims.values(),
                    *self.coverage_exclusions.values(),
                ]
            )
        ):
            raise validation_error(msg("document.schema"))
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
            metric = self.metrics[occurrence.metric]
            contract = getattr(metric, "statistics", None)
            display = occurrence.display.statistics
            if (contract is not None) != (display is not None):
                raise validation_error(msg("statistics.explicit_display"))
            if (
                display
                and display.component
                in {"ci", "mean_ci", "ci_lower", "ci_upper", "confidence_level"}
                and contract.confidence_interval is None
            ):
                raise validation_error(msg("statistics.ci_required"))
            if occurrence.anchor.table and occurrence.anchor.table.statistical_display != (
                display if display and display.compound else None
            ):
                raise validation_error(msg("statistics.table_display"))
        for name, claim in self.claims.items():
            refs = [claim.predicate.left, *claim.predicate.candidates]
            if isinstance(claim.predicate.right, str):
                refs.append(claim.predicate.right)
            if any(ref not in self.metrics for ref in refs):
                raise validation_error(msg("validation.models.16", name=name))
        return self
