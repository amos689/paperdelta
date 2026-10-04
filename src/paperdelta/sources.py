"""Read exact evidence and resolve a restricted, typed metric graph."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Any

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.metrics import Quantity, derive
from paperdelta.models import Config, DerivedMetric, Source, SourceMetric
from paperdelta.storage import Project, canonical, decimal_value, fingerprint, parse_json, sha256


@dataclass
class Result:
    quantity: Quantity
    fingerprint: str
    evidence: list[dict]
    dependencies: list[str]

    def to_dict(self) -> dict:
        return {
            "value": str(self.quantity.value),
            "unit": self.quantity.unit,
            "fingerprint": self.fingerprint,
            "evidence": self.evidence,
            "dependencies": self.dependencies,
        }


def json_pointer(data: Any, pointer: str) -> Any:
    if pointer == "":
        return data
    if not pointer.startswith("/") or re.search(r"~(?![01])", pointer):
        raise PaperDeltaError("INVALID_POINTER", msg("error.INVALID_POINTER", pointer=pointer))
    current = data
    for raw in pointer[1:].split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and re.fullmatch(r"0|[1-9][0-9]*", part):
            index = int(part)
            if index >= len(current):
                raise PaperDeltaError(
                    "MISSING_VALUE", msg("error.MISSING_VALUE.2", pointer=pointer)
                )
            current = current[index]
        else:
            raise PaperDeltaError("MISSING_VALUE", msg("error.MISSING_VALUE", pointer=pointer))
    return current


def typed_cell(value: str, kind: str, label: str) -> str | int | Decimal:
    if kind == "string":
        return value
    if kind == "integer":
        if len(value) > 2048:
            raise PaperDeltaError("NUMBER_LIMIT", msg("error.NUMBER_LIMIT", label=label))
        if not re.fullmatch(r"[+\-]?(0|[1-9][0-9]*)", value):
            raise PaperDeltaError("COLUMN_TYPE", msg("error.COLUMN_TYPE", label=label))
        return int(value)
    return decimal_value(value)


class EvidenceStore:
    def __init__(self, project: Project, config: Config):
        self.project = project
        self.config = config
        self.sources: dict[str, Any] = {}
        self.hashes: dict[str, str] = {}
        self.results: dict[str, Result] = {}
        self.errors: dict[str, PaperDeltaError] = {}
        self.csv_indexes: dict[str, dict[str, dict[Any, list[dict]]]] = {}
        self.export_info: dict[str, dict] = {}

    def load_source(self, name: str) -> Any:
        if name in self.sources:
            return self.sources[name]
        source = self.config.sources[name]
        if source.format == "xlsx":
            raw = self.project.read(source.path)
            text = None
        else:
            text, raw = self.project.text(source.path)
        self.hashes[source.path] = sha256(raw)
        if source.format == "json":
            data = parse_json(text)
        elif source.format == "records":
            data = self._records(name, source, parse_json(text))
        elif source.format == "xlsx":
            data = self._xlsx(source, raw)
        else:
            try:
                data = self._csv(source, text)
            except csv.Error as exc:
                raise PaperDeltaError(
                    "INVALID_CSV", msg("error.INVALID_CSV.2", value1=source.path, exc=exc)
                ) from exc
        self.sources[name] = data
        return data

    def _csv(self, source: Source, text: str) -> list[dict]:
        reader = csv.DictReader(
            io.StringIO(text, newline=""),
            delimiter="\t" if source.format == "tsv" else ",",
            strict=True,
        )
        names = reader.fieldnames
        if not names or len(set(names)) != len(names):
            raise PaperDeltaError("CSV_HEADER", msg("error.CSV_HEADER.2", value1=source.path))
        if not set(source.columns).issubset(names):
            raise PaperDeltaError("MISSING_COLUMN", msg("error.MISSING_COLUMN", value1=source.path))
        keys: set[tuple] = set()
        rows: list[dict] = []
        previous_line = reader.line_num
        try:
            for raw in reader:
                first_line = previous_line + 1
                previous_line = reader.line_num
                if None in raw or any(value is None for value in raw.values()):
                    raise PaperDeltaError(
                        "CSV_ROW", msg("error.CSV_ROW.2", value1=source.path, first_line=first_line)
                    )
                values = {
                    key: None
                    if source.format == "tsv" and raw[key] == "" and kind != "string"
                    else typed_cell(raw[key], kind, f"{source.path}:{first_line}:{key}")
                    for key, kind in source.columns.items()
                }
                identity = {key: values[key] for key in source.primary_key}
                if any(value is None for value in identity.values()):
                    raise PaperDeltaError(
                        "MISSING_VALUE", msg("evidence.key_missing", path=source.path)
                    )
                # Each column has one declared type; tuple equality preserves the
                # same exact Decimal identity without serializing every CSV row.
                key = tuple(identity.values())
                if key in keys:
                    raise PaperDeltaError(
                        "DUPLICATE_RECORD", msg("error.DUPLICATE_RECORD", identity=identity)
                    )
                keys.add(key)
                rows.append({"values": values, "key": identity, "line": first_line})
        except csv.Error as exc:
            raise PaperDeltaError(
                "INVALID_CSV", msg("error.INVALID_CSV", value1=source.path, exc=exc)
            ) from exc
        return rows

    def _xlsx(self, source, raw):
        from paperdelta.xlsx_evidence import coordinate, read_xlsx

        table = read_xlsx(raw, source.sheet, source.cell_range)
        if not set(source.columns) <= set(table.columns):
            raise PaperDeltaError("MISSING_COLUMN", msg("error.MISSING_COLUMN", value1=source.path))
        rows, identities = [], set()
        for row in table.rows:
            values = {}
            for column, kind in source.columns.items():
                cell = row[column]
                if cell.value is None:
                    values[column] = None
                else:
                    if kind == "string" and cell.kind != "string":
                        raise PaperDeltaError(
                            "XLSX_IDENTITY",
                            msg("xlsx.text_identity", sheet=source.sheet, cell=cell.address),
                        )
                    values[column] = typed_cell(
                        cell.value, kind, f"{source.path}:{source.sheet}!{cell.address}"
                    )
            identity = {column: values[column] for column in source.primary_key}
            if any(value is None for value in identity.values()):
                raise PaperDeltaError(
                    "MISSING_VALUE", msg("evidence.key_missing", path=source.path)
                )
            key = tuple(identity.values())
            if key in identities:
                raise PaperDeltaError(
                    "DUPLICATE_RECORD", msg("error.DUPLICATE_RECORD", identity=identity)
                )
            identities.add(key)
            rows.append(
                {
                    "values": values,
                    "key": identity,
                    "line": coordinate(next(iter(row.values())).address)[1],
                    "cells": {column: cell.address for column, cell in row.items()},
                }
            )
        return rows

    def _records(self, name, source, value):
        from paperdelta.experiment_exports import export_error, provenance, validate_export

        document = validate_export(value)
        if source.columns != document.columns or source.primary_key != document.primary_key:
            raise export_error("contract")
        self.export_info[name] = provenance(document)
        rows, seen = [], set()
        for row in document.records:
            values = {
                key: typed_cell(row.values[key], kind, key) if row.values[key] is not None else None
                for key, kind in source.columns.items()
            }
            identity = {key: values[key] for key in source.primary_key}
            if any(value is None for value in identity.values()):
                raise export_error("key_missing")
            key = tuple(identity.values())
            if key in seen:
                raise export_error("duplicate")
            seen.add(key)
            rows.append(
                {
                    "values": values,
                    "key": identity,
                    "snapshot": row.snapshot,
                    "pointers": row.pointers,
                }
            )
        return rows

    def _select_csv(self, name: str, data: list[dict], where: dict) -> list[dict]:
        if not where:
            return data
        indexes = self.csv_indexes.setdefault(name, {})
        candidates = []
        for column, value in where.items():
            if column not in indexes:
                index: dict[Any, list[dict]] = {}
                for row in data:
                    index.setdefault(row["values"][column], []).append(row)
                indexes[column] = index
            candidates.append(indexes[column].get(value, []))
        # Indexes only narrow candidates. Verify every predicate with the same
        # typed equality and retain CSV order, evidence rows and line identities.
        return [
            row
            for row in min(candidates, key=len)
            if all(row["values"][key] == value for key, value in where.items())
        ]

    def resolve(self, name: str) -> Result:
        if name in self.results:
            return self.results[name]
        if name in self.errors:
            raise self.errors[name]
        try:
            metric = self.config.metrics[name]
            if isinstance(metric, DerivedMetric):
                left, right = [self.resolve(ref) for ref in metric.args]
                quantity = derive(metric.op, left.quantity, right.quantity)
                evidence = {fingerprint(item): item for item in [*left.evidence, *right.evidence]}
                result = Result(
                    quantity,
                    fingerprint({"rule": metric, "inputs": [left.fingerprint, right.fingerprint]}),
                    list(evidence.values()),
                    metric.args,
                )
            else:
                result = self._source_metric(metric)
            self.results[name] = result
            return result
        except PaperDeltaError as exc:
            self.errors[name] = exc
            raise

    def _source_metric(self, metric: SourceMetric) -> Result:
        source = self.config.sources[metric.source]
        data = self.load_source(metric.source)
        selected: list[dict]
        if source.format != "json":
            if metric.field not in source.columns or not set(metric.where).issubset(source.columns):
                raise PaperDeltaError("MISSING_COLUMN", msg("error.MISSING_COLUMN.2"))
            if metric.reduce != "count" and source.columns[metric.field] == "string":
                raise PaperDeltaError("COLUMN_TYPE", msg("error.COLUMN_TYPE.2"))
            for column, value in metric.where.items():
                expected = typed_cell(str(value), source.columns[column], column)
                if type(value) is not type(expected):
                    raise PaperDeltaError(
                        "SELECTOR_TYPE", msg("error.SELECTOR_TYPE", column=column)
                    )
            selected = self._select_csv(metric.source, data, metric.where)
            if metric.expected_seeds is not None:
                if metric.seed_column not in source.columns:
                    raise PaperDeltaError("MISSING_COLUMN", msg("error.MISSING_COLUMN.3"))
                seeds = [row["values"][metric.seed_column] for row in selected]
                if len(seeds) != len(set(seeds)) or set(seeds) != set(metric.expected_seeds):
                    raise PaperDeltaError(
                        "SEED_SET", msg("error.SEED_SET", value1=metric.expected_seeds, seeds=seeds)
                    )
            values = [row["values"][metric.field] for row in selected]
            records = [
                {"key": row["key"], "value": value}
                for row, value in zip(selected, values, strict=True)
            ]
            if source.format == "records":
                locations = [
                    {
                        "key": row["key"],
                        "snapshot": row["snapshot"],
                        "pointer": row["pointers"][metric.field],
                    }
                    for row in selected
                ]
            elif source.format == "xlsx":
                locations = [
                    {
                        "key": row["key"],
                        "sheet": source.sheet,
                        "row": row["line"],
                        "cell": row["cells"][metric.field],
                    }
                    for row in selected
                ]
            else:
                locations = [{"key": row["key"], "line": row["line"]} for row in selected]
        else:
            if metric.where or metric.expected_seeds is not None:
                raise PaperDeltaError("JSON_SELECTOR", msg("error.JSON_SELECTOR"))
            value = json_pointer(data, metric.field)
            values = value if isinstance(value, list) else [value]
            records = [{"index": i, "value": item} for i, item in enumerate(values)]
            locations = [{"pointer": metric.field}]
        if not values:
            raise PaperDeltaError("EMPTY_SELECTION", msg("error.EMPTY_SELECTION"))
        if len(values) > 10000:
            raise PaperDeltaError("SELECTION_LIMIT", msg("error.SELECTION_LIMIT"))
        if metric.expected_count is not None and len(values) != metric.expected_count:
            raise PaperDeltaError(
                "RECORD_COUNT",
                msg("error.RECORD_COUNT", value1=metric.expected_count, value2=len(values)),
            )
        if metric.reduce == "unique" and len(values) != 1:
            raise PaperDeltaError(
                "AMBIGUOUS_SELECTION", msg("error.AMBIGUOUS_SELECTION", value1=len(values))
            )
        numbers = [decimal_value(value) for value in values] if metric.reduce != "count" else []
        with localcontext() as context:
            context.prec = 4096
            if metric.reduce == "count":
                number = Decimal(len(values))
            elif metric.reduce == "unique":
                number = numbers[0]
            else:
                number = sum(numbers, Decimal(0))
                if metric.reduce == "mean":
                    # Retain at least 50 significant digits for nonterminating division.
                    context.prec = max(50, len(number.as_tuple().digits) + 10)
                    number /= len(numbers)
        semantic = sorted(records, key=lambda record: json.dumps(canonical(record), sort_keys=True))
        identity = {"source": source.path, "selector": metric, "records": semantic}
        if source.format not in {"csv", "json"}:
            identity["source_definition"] = source
        if source.format == "records":
            identity["provenance"] = self.export_info[metric.source]
        digest = fingerprint(identity)
        evidence = [
            {
                "source": metric.source,
                "path": source.path,
                "field": metric.field,
                "where": metric.where,
                "reduce": metric.reduce,
                "count": len(values),
                "records": records,
                "locations": locations,
            }
        ]
        if source.format not in {"csv", "json"}:
            evidence[0]["format"] = source.format
        if source.format == "records":
            evidence[0]["provenance"] = self.export_info[metric.source]
        return Result(Quantity(number, metric.unit), digest, evidence, [])

    def check_scope(self, name: str, scope: dict) -> None:
        metric = self.config.metrics[name]
        if isinstance(metric, DerivedMetric):
            for ref in metric.args:
                self.check_scope(ref, scope)
        elif any(metric.where.get(key) != value for key, value in scope.items()):
            raise PaperDeltaError(
                "SCOPE_MISMATCH", msg("error.SCOPE_MISMATCH", name=name, scope=scope)
            )
