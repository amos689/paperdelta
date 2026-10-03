"""Versioned, strict contracts shared by the CLI and agent adapters."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

Scalar = StrictStr | StrictInt | Decimal
Unit = Literal["scalar", "fraction", "percent", "percentage_point", "count", "ratio"]
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
            raise ValueError("Macro names must contain letters only, without a backslash")
        return self


class Source(StrictModel):
    path: str
    format: Literal["csv", "json"]
    primary_key: list[str] = Field(default_factory=list)
    columns: dict[str, Literal["string", "integer", "decimal"]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_format(self) -> Self:
        if self.format == "csv":
            if not self.primary_key or not self.columns:
                raise ValueError("CSV sources require primary_key and explicit columns")
            if len(set(self.primary_key)) != len(self.primary_key):
                raise ValueError("primary_key must not repeat columns")
            if not set(self.primary_key).issubset(self.columns):
                raise ValueError("Every primary key column must have a declared type")
        elif self.primary_key or self.columns:
            raise ValueError("JSON sources use JSON Pointer, not CSV column declarations")
        return self


class SourceMetric(StrictModel):
    source: Identifier
    field: str
    where: dict[str, Scalar] = Field(default_factory=dict)
    reduce: Literal["unique", "mean", "sum", "count"] = "unique"
    expected_seeds: list[StrictStr | StrictInt] | None = None
    seed_column: str = "seed"
    expected_count: Annotated[int, Field(ge=1)] | None = None
    unit: Unit

    @model_validator(mode="after")
    def validate_seeds(self) -> Self:
        if self.expected_seeds is not None:
            if not self.expected_seeds or len(set(self.expected_seeds)) != len(self.expected_seeds):
                raise ValueError("expected_seeds must be a nonempty, unique list")
        if self.reduce == "count" and self.unit != "count":
            raise ValueError("A count metric must use unit: count")
        return self


class DerivedMetric(StrictModel):
    op: Literal["difference", "ratio", "percentage_point_difference", "relative_change_percent"]
    args: Annotated[list[Identifier], Field(min_length=2, max_length=2)]


class Anchor(StrictModel):
    exact: str | None = None
    prefix: str | None = None
    suffix: str | None = None

    @model_validator(mode="after")
    def exactly_one_mode(self) -> Self:
        if self.exact is not None:
            if not self.exact or self.prefix is not None or self.suffix is not None:
                raise ValueError("Use a nonempty exact anchor OR a prefix and suffix")
        elif not self.prefix or not self.suffix:
            raise ValueError("Both prefix and suffix must be nonempty")
        return self


class Display(StrictModel):
    kind: Literal["decimal", "percent", "integer", "scientific"] = "decimal"
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
                raise ValueError("best_in_set requires candidates and direction, without right")
            if len(set(self.candidates)) != len(self.candidates) or self.left in self.candidates:
                raise ValueError("Candidates must be unique and exclude the left metric")
        elif self.right is None or self.candidates or self.direction is not None or self.allow_ties:
            raise ValueError("Binary comparisons require right, without ranking options")
        return self


class Claim(StrictModel):
    file: str
    anchor: Anchor
    predicate: Predicate
    scope: dict[str, Scalar] = Field(default_factory=dict)


class Figure(StrictModel):
    path: str
    record: str | None = None


class Config(StrictModel):
    schema_version: VersionOne
    paper: Paper
    rounding: Literal["half_up", "half_even"] = "half_up"
    sources: dict[Identifier, Source] = Field(default_factory=dict)
    metrics: dict[Identifier, SourceMetric | DerivedMetric] = Field(default_factory=dict)
    occurrences: dict[Identifier, Occurrence] = Field(default_factory=dict)
    claims: dict[Identifier, Claim] = Field(default_factory=dict)
    figures: dict[Identifier, Figure] = Field(default_factory=dict)
    require_complete_coverage: bool = False

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        dependencies: dict[str, list[str]] = {}
        for name, metric in self.metrics.items():
            if isinstance(metric, SourceMetric):
                if metric.source not in self.sources:
                    raise ValueError(f"Metric {name}: source {metric.source!r} does not exist")
                dependencies[name] = []
            else:
                dependencies[name] = metric.args
        for name, edges in dependencies.items():
            if any(edge not in self.metrics for edge in edges):
                raise ValueError(f"Metric {name}: unknown input metric")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(name: str) -> None:
            if name in visiting:
                raise ValueError(f"Cyclic metric dependency at {name}")
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
                raise ValueError(f"Occurrence {name}: unknown metric {occurrence.metric}")
        for name, claim in self.claims.items():
            refs = [claim.predicate.left, *claim.predicate.candidates]
            if isinstance(claim.predicate.right, str):
                refs.append(claim.predicate.right)
            if any(ref not in self.metrics for ref in refs):
                raise ValueError(f"Claim {name}: unknown metric")
        return self
