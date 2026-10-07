"""Portable, self-contained evidence exports; validation never accesses a network.

Stored rows are a projection of bounded source snapshots, not a second editable
source of truth. Recompute that projection when reading an export. Hashes detect
changes and do not authenticate the origin of an experiment.
"""

from __future__ import annotations

import base64
import binascii
import csv
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from paperdelta import __version__
from paperdelta.errors import PaperDeltaError
from paperdelta.evidence_models import ImportRequest
from paperdelta.i18n import msg
from paperdelta.models import ColumnType, Hash, StrictModel, VersionOne
from paperdelta.records import validate_record
from paperdelta.storage import decimal_value, fingerprint, json_text, parse_json, sha256

MAX_EXPORT_BYTES = 32 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 16 * 1024 * 1024
MAX_RECORDS = 100_000


def export_error(key="schema", **values):
    return PaperDeltaError("EXPORT_" + key.upper(), msg("export." + key, **values))


class SourceSnapshot(StrictModel):
    kind: Literal["file", "run", "history"]
    run: str | None = None
    metric: str | None = None
    page: int = Field(default=0, ge=0)
    sha256: Hash
    content_base64: str

    def raw(self):
        if len(self.content_base64) > MAX_SNAPSHOT_BYTES * 4 // 3 + 4:
            raise export_error("limit")
        try:
            raw = base64.b64decode(self.content_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise export_error() from exc
        if len(raw) > MAX_SNAPSHOT_BYTES or sha256(raw) != self.sha256:
            raise export_error("identity")
        return raw


class ExportRow(StrictModel):
    values: dict[str, str | None]
    snapshot: Hash
    pointers: dict[str, str]


class ExperimentExport(StrictModel):
    export_schema_version: VersionOne
    tool_version: str
    created_at: str
    request: ImportRequest
    precision: Literal["stored-lexemes", "api-double", "sdk-binary64"]
    snapshots: list[SourceSnapshot] = Field(min_length=1, max_length=10000)
    columns: dict[str, ColumnType] = Field(min_length=1, max_length=1000)
    primary_key: list[str] = Field(min_length=1, max_length=100)
    records: list[ExportRow] = Field(min_length=1, max_length=MAX_RECORDS)
    export_id: Hash


def snapshot(raw, *, kind, run=None, metric=None, page=0):
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise export_error("limit")
    return SourceSnapshot(
        kind=kind,
        run=run,
        metric=metric,
        page=page,
        sha256=sha256(raw),
        content_base64=base64.b64encode(raw).decode("ascii"),
    )


def _identity(request, metadata, history=None):
    from paperdelta.sources import typed_cell

    result = {}
    for name, declaration in request.identity.items():
        container = history if declaration.scope == "history" else metadata.get(declaration.scope)
        value = (container or {}).get(declaration.field)
        if value is None:
            result[name] = None
        else:
            if type(value) is bool or not isinstance(value, (str, int, Decimal)):
                raise export_error("identity_type", field=name)
            if declaration.type == "string" and not isinstance(value, str):
                raise export_error("identity_type", field=name)
            result[name] = str(typed_cell(str(value), declaration.type, name))
    return result


def _number(value, *, integer=False):
    if value is None:
        return None
    number = decimal_value(value)
    if integer and (number != number.to_integral_value() or type(value) is bool):
        raise export_error()
    return str(int(number)) if integer else str(number)


def _measurement(value):
    if value is None:
        return None, "missing"
    if value in ("NaN", "Infinity", "-Infinity", "nan", "inf", "-inf") or (
        isinstance(value, dict) and set(value) == {"$nonfinite"}
    ):
        return None, "nonfinite"
    return _number(value), "observed"


def _row(request, metadata, entry, metric, run, index, source, pointer):
    wandb = request.provider == "wandb"
    value, status = _measurement(entry.get(metric) if wandb else entry.get("value"))
    values = {
        "run_id": run,
        "metric": metric,
        "record_index": str(index),
        "value": value,
        "status": status,
        "step": _number(entry.get("_step" if wandb else "step"), integer=True),
        "timestamp": _number(entry.get("_timestamp" if wandb else "timestamp")),
        "timestamp_unit": "s" if wandb else "ms",
        **_identity(request, metadata, entry),
    }
    if not wandb:
        for key in ("model_id", "dataset_name", "dataset_digest"):
            item = entry.get(key)
            if item is not None and not isinstance(item, str):
                raise export_error()
            values[key] = item
    return ExportRow(values=values, snapshot=source.sha256, pointers=dict.fromkeys(values, pointer))


def project_snapshots(request, snapshots):
    """Return normalized columns, primary key and rows from original input only."""
    if sum(len(item.content_base64) for item in snapshots) > MAX_EXPORT_BYTES:
        raise export_error("limit")
    for item in snapshots:
        item.raw()
    if request.provider == "file":
        from paperdelta.sources import EvidenceStore

        if len(snapshots) != 1 or snapshots[0].kind != "file":
            raise export_error()
        source, original = request.source, snapshots[0]
        # These readers need no project: use exactly the same type/key contract.
        reader = EvidenceStore(None, None)
        raw = original.raw()
        rows = (
            reader._xlsx(source, raw)
            if source.format == "xlsx"
            else reader._csv(source, raw.decode("utf-8-sig"))
        )
        if len(rows) > MAX_RECORDS:
            raise export_error("limit")
        result = []
        for row in rows:
            pointers = {
                column: f"{source.sheet}!{row['cells'][column]}"
                if source.format == "xlsx"
                else f"line:{row['line']}:{column}"
                for column in source.columns
            }
            result.append(
                ExportRow(
                    values={k: str(v) if v is not None else None for k, v in row["values"].items()},
                    snapshot=original.sha256,
                    pointers=pointers,
                )
            )
        return source.columns, source.primary_key, result
    columns = {
        "run_id": "string",
        "metric": "string",
        "record_index": "integer",
        "value": "decimal",
        "status": "string",
        "step": "integer",
        "timestamp": "decimal",
        "timestamp_unit": "string",
        **{key: field.type for key, field in request.identity.items()},
    }
    if request.provider == "mlflow":
        columns.update(dict.fromkeys(("model_id", "dataset_name", "dataset_digest"), "string"))
    result, consumed = [], set()
    for run in request.runs:
        run_sources = [
            (i, item) for i, item in enumerate(snapshots) if item.kind == "run" and item.run == run
        ]
        if len(run_sources) != 1:
            raise export_error()
        source_index, run_source = run_sources[0]
        consumed.add(source_index)
        run_data = parse_json(run_source.raw().decode("utf-8"))
        if request.provider == "mlflow":
            data = run_data["run"]
            if data["info"]["run_id"] != run:
                raise export_error("identity")
            if data["info"].get("status") not in {"FINISHED", "FAILED", "KILLED"}:
                raise export_error("active_run")
            metadata = {}
            for scope, key in (("param", "params"), ("tag", "tags")):
                fields = data.get("data", {}).get(key, [])
                if len({field["key"] for field in fields}) != len(fields):
                    raise export_error()
                metadata[scope] = {field["key"]: field["value"] for field in fields}
        else:
            if run_data["id"] != run:
                raise export_error("identity")
            if run_data.get("state") not in {"finished", "crashed", "failed", "killed"}:
                raise export_error("active_run")
            metadata = {"config": run_data["config"]}
        for metric in request.metrics:
            if request.provider == "wandb":
                history = run_data["history"]
                if not isinstance(history, list):
                    raise export_error()
                entries = [(run_source, f"/history/{i}", entry) for i, entry in enumerate(history)]
            else:
                pages = [
                    (i, item)
                    for i, item in enumerate(snapshots)
                    if item.kind == "history" and item.run == run and item.metric == metric
                ]
                if not pages or [item.page for _, item in pages] != list(range(len(pages))):
                    raise export_error()
                entries = []
                tokens = set()
                for page_index, (i, item) in enumerate(pages):
                    consumed.add(i)
                    page = parse_json(item.raw().decode("utf-8"))
                    token = page.get("next_page_token")
                    if bool(token) != (page_index < len(pages) - 1) or (token and token in tokens):
                        raise export_error("pagination")
                    if token:
                        tokens.add(token)
                    for j, entry in enumerate(page.get("metrics", [])):
                        if entry.get("key") != metric:
                            raise export_error("identity")
                        entries.append((item, f"/metrics/{j}", entry))
            empty_history = not entries
            if empty_history:
                entries = [
                    (run_source, "/history", {})
                    if request.provider == "wandb"
                    else (pages[-1][1], "/metrics", {})
                ]
            for index, (item, pointer, entry) in enumerate(entries):
                result.append(_row(request, metadata, entry, metric, run, index, item, pointer))
                if empty_history:
                    result[-1].values["status"] = "not_logged"
                if len(result) > MAX_RECORDS:
                    raise export_error("limit")
    if consumed != set(range(len(snapshots))):
        raise export_error()
    return columns, ["run_id", "metric", "record_index"], result


def create_export(request, snapshots):
    columns, keys, rows = project_snapshots(request, snapshots)
    body = {
        "export_schema_version": 1,
        "tool_version": __version__,
        "created_at": datetime.now(UTC).isoformat(),
        "request": request.model_dump(),
        "precision": {"file": "stored-lexemes", "mlflow": "api-double", "wandb": "sdk-binary64"}[
            request.provider
        ],
        "snapshots": [item.model_dump() for item in snapshots],
        "columns": columns,
        "primary_key": keys,
        "records": [row.model_dump() for row in rows],
    }
    value = {**body, "export_id": fingerprint(body)}
    encoded = json_text(value).encode("utf-8")
    if len(encoded) > MAX_EXPORT_BYTES:
        raise export_error("limit")
    validate_export(value)
    return value


def validate_export(value):
    document = validate_record(ExperimentExport, value, "EXPORT_SCHEMA")
    if document.export_id != fingerprint(document.model_dump(exclude={"export_id"})):
        raise export_error("identity")
    try:
        date = datetime.fromisoformat(document.created_at)
        if date.tzinfo is None:
            raise ValueError()
        columns, keys, rows = project_snapshots(document.request, document.snapshots)
    except (KeyError, TypeError, ValueError, AttributeError, csv.Error, RecursionError) as exc:
        raise export_error() from exc
    precision = {"file": "stored-lexemes", "mlflow": "api-double", "wandb": "sdk-binary64"}[
        document.request.provider
    ]
    if (
        document.columns != columns
        or document.primary_key != keys
        or document.precision != precision
        or fingerprint(rows) != fingerprint(document.records)
    ):
        raise export_error("projection")
    return document


def provenance(document):
    return {
        "export_id": document.export_id,
        "tool_version": document.tool_version,
        "provider": document.request.provider,
        "origin": document.request.origin,
        "created_at": document.created_at,
        "precision": document.precision,
        "selection": document.request.model_dump(),
        "snapshot_hashes": [item.sha256 for item in document.snapshots],
    }
