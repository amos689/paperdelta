"""Explicit read-only provider requests followed by one portable local export."""

from __future__ import annotations

import base64
import csv
import math
import os
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from paperdelta.errors import PaperDeltaError
from paperdelta.experiment_exports import (
    MAX_RECORDS,
    MAX_SNAPSHOT_BYTES,
    ImportRequest,
    create_export,
    export_error,
    provenance,
    snapshot,
    validate_export,
)
from paperdelta.records import validate_record
from paperdelta.storage import json_text, parse_json


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Keep authorization at the explicitly selected origin.
        return None


def _get(origin, endpoint, parameters):
    headers = {"Accept": "application/json"}
    token = os.environ.get("MLFLOW_TRACKING_TOKEN")
    user, password = (
        os.environ.get("MLFLOW_TRACKING_USERNAME"),
        os.environ.get("MLFLOW_TRACKING_PASSWORD"),
    )
    if token:
        headers["Authorization"] = "Bearer " + token
    elif user and password:
        headers["Authorization"] = "Basic " + base64.b64encode(
            f"{user}:{password}".encode()
        ).decode("ascii")
    request = Request(origin.rstrip("/") + endpoint + "?" + urlencode(parameters), headers=headers)
    try:
        with build_opener(NoRedirects).open(request, timeout=30) as response:
            raw = response.read(MAX_SNAPSHOT_BYTES + 1)
    except (HTTPError, URLError, OSError, ValueError) as exc:
        # Server bodies, URLs from exceptions and request headers can contain
        # credentials. Report only the provider and bounded HTTP status.
        raise export_error(
            "request", provider="MLflow", status=getattr(exc, "code", "IO")
        ) from None
    if len(raw) > MAX_SNAPSHOT_BYTES:
        raise export_error("limit")
    parse_json(raw.decode("utf-8"))
    return raw


def import_mlflow(request):
    snapshots = []
    for run in request.runs:
        raw = _get(request.origin, "/api/2.0/mlflow/runs/get", {"run_id": run})
        info = parse_json(raw.decode("utf-8"))["run"]["info"]
        if info.get("status") not in {"FINISHED", "FAILED", "KILLED"}:
            raise export_error("active_run")
        snapshots.append(snapshot(raw, kind="run", run=run))
        for metric in request.metrics:
            token, seen, page = None, set(), 0
            while True:
                parameters = {"run_id": run, "metric_key": metric, "max_results": 1000}
                if token:
                    parameters["page_token"] = token
                raw = _get(request.origin, "/api/2.0/mlflow/metrics/get-history", parameters)
                snapshots.append(snapshot(raw, kind="history", run=run, metric=metric, page=page))
                token = parse_json(raw.decode("utf-8")).get("next_page_token")
                if not token:
                    break
                if not isinstance(token, str) or token in seen:
                    raise export_error("pagination")
                seen.add(token)
                page += 1
                if page >= 1000 or len(snapshots) >= 10000:
                    raise export_error("limit")
                if sum(len(item.content_base64) for item in snapshots) > MAX_SNAPSHOT_BYTES * 2:
                    raise export_error("limit")
    return snapshots


def _sdk_value(value):
    if type(value) is float:
        return Decimal(repr(value)) if math.isfinite(value) else {"$nonfinite": str(value)}
    if value is None or type(value) in {str, int, bool}:
        return value
    # Only selected scalar fields are supported. Never stringify an arbitrary
    # object or coerce arrays into scalar evidence.
    raise export_error("scalar")


def import_wandb(request, *, api=None):
    if api is None:
        if not os.environ.get("WANDB_API_KEY"):
            raise export_error("wandb_key")
        try:
            import wandb
        except ImportError as exc:
            raise export_error("wandb_dependency") from exc
        try:
            api = wandb.Api(overrides={"base_url": request.origin}, timeout=30)
        except Exception:
            raise export_error("request", provider="W&B", status="SDK") from None
    snapshots = []
    total = 0
    for run_path in request.runs:
        try:
            run = api.run(run_path)
            path = run.path
            actual_path = "/".join(path) if isinstance(path, list) else path
            if actual_path != run_path:
                raise export_error("identity")
            # Terminal runs avoid an apparently complete snapshot of a history
            # still being written. A new explicit import captures later edits.
            if run.state not in {"finished", "crashed", "failed", "killed"}:
                raise export_error("active_run")
            config = {
                field.field: _sdk_value(run.config.get(field.field))
                for field in request.identity.values()
                if field.scope == "config"
            }
            fields = (
                set(request.metrics)
                | {"_step", "_timestamp"}
                | {field.field for field in request.identity.values() if field.scope == "history"}
            )
            history = []
            # No keys filter: it omits rows when requested metrics are logged
            # sparsely. scan_history is unsampled; history() defaults to sampling.
            for row in run.scan_history(page_size=1000, use_cache=False):
                total += len(request.metrics)
                if total > MAX_RECORDS:
                    raise export_error("limit")
                history.append({key: _sdk_value(row[key]) for key in fields if key in row})
            if not history and run.lastHistoryStep >= 0:
                raise export_error("incomplete")
            payload = {
                "id": run_path,
                "state": run.state,
                "config": config,
                "history": history,
                "last_history_step": run.lastHistoryStep,
            }
            snapshots.append(snapshot(json_text(payload).encode("utf-8"), kind="run", run=run_path))
        except PaperDeltaError:
            raise
        except Exception:
            raise export_error("request", provider="W&B", status="SDK") from None
    return snapshots


def import_evidence(project, request_value, output, *, wandb_api=None):
    request = validate_record(ImportRequest, request_value, "EXPORT_REQUEST")
    if not output.lower().endswith(".pdevidence.json"):
        raise export_error("suffix")
    if project.path(output).exists():
        raise export_error("exists", path=output)
    try:
        if request.provider == "file":
            snapshots = [snapshot(project.read(request.source.path), kind="file")]
        elif request.provider == "mlflow":
            snapshots = import_mlflow(request)
        else:
            snapshots = import_wandb(request, api=wandb_api)
        value = create_export(request, snapshots)
    except (KeyError, TypeError, ValueError, AttributeError, csv.Error, RecursionError) as exc:
        raise export_error() from exc
    project.write(output, json_text(value).encode("utf-8"), exclusive=True)
    document = validate_export(value)
    return {
        "status": "imported",
        "path": output,
        "records": len(document.records),
        "source": {
            "path": output,
            "format": "records",
            "columns": document.columns,
            "primary_key": document.primary_key,
        },
        "provenance": provenance(document),
    }
