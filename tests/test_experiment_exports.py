"""Actual local REST traffic and real SDK pagination, then fully offline checking."""

import base64
import json
import subprocess
import sys
import threading
from copy import deepcopy
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from test_xlsx_evidence import book

from paperdelta import builder
from paperdelta.analysis import check_project
from paperdelta.batch import create_catalog, inspect_catalog
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.experiment_exports import validate_export
from paperdelta.experiment_imports import import_evidence
from paperdelta.models import Config, Source, SourceMetric
from paperdelta.onboarding import accept_bindings, init_project, inspect_proposal, scan_project
from paperdelta.records import StoredReport
from paperdelta.sources import EvidenceStore
from paperdelta.storage import Project, fingerprint, json_text, parse_json


def read_export(project, path="results.pdevidence.json"):
    return parse_json(project.text(path)[0])


def resolve(project, result, where, field="value"):
    config = Config(
        schema_version=5,
        paper={"entry": "paper.tex"},
        sources={"results": Source.model_validate(result["source"])},
        metrics={"test": SourceMetric(source="results", field=field, where=where, unit="fraction")},
    )
    return EvidenceStore(project, config).resolve("test")


@pytest.mark.parametrize("kind", ["csv", "tsv", "xlsx"])
def test_portable_local_export_keeps_original_cells_and_no_longer_needs_source(tmp_path, kind):
    project = Project(tmp_path)
    raw = (
        book()
        if kind == "xlsx"
        else ("model,accuracy\n001,0.80000000000000000000000000001\n1,0.801\n")
        .replace(",", "\t" if kind == "tsv" else ",")
        .encode()
    )
    project.write("results." + kind, raw)
    source = {
        "path": "results." + kind,
        "format": kind,
        "columns": {"model": "string", "accuracy": "decimal"},
        "primary_key": ["model"],
    }
    if kind == "xlsx":
        source.update(sheet="Results", cell_range="A1:B3")
    result = import_evidence(
        project,
        {"provider": "file", "origin": source["path"], "source": source},
        "results.pdevidence.json",
    )
    project.path(source["path"]).unlink()
    exact = resolve(project, result, {"model": "001"}, "accuracy")
    assert exact.quantity.value == Decimal("0.80000000000000000000000000001")
    location = exact.evidence[0]["locations"][0]
    assert location["pointer"] == ("Results!B2" if kind == "xlsx" else "line:2:accuracy")
    assert exact.evidence[0]["provenance"]["precision"] == "stored-lexemes"

    # Imported rows go through the ordinary accepted binding contract.
    project.write("paper.tex", b"Model 001 accuracy 80.0\\%.\n")
    init_project(project, "paper.tex", [result["path"]])
    draft = builder.add_source(
        project, builder.start_draft(project), name="results", **result["source"]
    )
    catalog = create_catalog(
        project,
        draft,
        {
            "source": "results",
            "fields": ["accuracy"],
            "group_by": ["model"],
            "unit": "fraction",
            "reduce": "unique",
            "expected_count": 1,
        },
    )
    assert [item["status"] for item in inspect_catalog(project, catalog)["choices"]] == [
        "ready",
        "ready",
    ]
    draft = builder.add_metric(
        project,
        draft,
        name="accuracy",
        source="results",
        field="accuracy",
        where={"model": "001"},
        unit="fraction",
        reduce="unique",
    )
    candidate = next(item for item in scan_project(project)["candidates"] if item["text"] == "80.0")
    draft = builder.add_occurrences(
        project,
        draft,
        metric="accuracy",
        candidate_ids=[candidate["candidate_id"]],
        names=["accuracy"],
        display_kind="percent",
        places=1,
        percent_symbol=True,
        rationale="Model 001, explicit source column accuracy.",
    )
    proposal = builder.finalize_draft(project, draft)
    _, _, report = inspect_proposal(project, proposal)
    StoredReport.model_validate(report)
    assert report["report_schema_version"] == 9
    accept_bindings(project, proposal, ["occurrences:accuracy"])
    assert load_config(project)[0].schema_version == 5
    assert check_project(project.root)["coverage"]["pass"] == 1


@pytest.fixture
def tracking_server():
    state = {"calls": [], "repeat": False, "status": "FINISHED", "error": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            url = urlsplit(self.path)
            params = {key: values[0] for key, values in parse_qs(url.query).items()}
            state["calls"].append((url.path, params, self.headers.get("Authorization")))
            if state["error"]:
                self.send_response(403)
                self.end_headers()
                self.wfile.write(b"SECRET_FROM_SERVER")
                return
            run = params["run_id"]
            if url.path.endswith("/runs/get"):
                payload = {
                    "run": {
                        "info": {"run_id": run, "status": state["status"]},
                        "data": {
                            "params": [
                                {"key": "seed", "value": "001"},
                                {"key": "split", "value": "test"},
                            ],
                            "tags": [{"key": "checkpoint", "value": "epoch-5"}],
                        },
                    }
                }
            elif params["metric_key"] == "loss":
                payload = {"metrics": []}
            else:
                page = int(params.get("page_token", "0"))
                payload = {
                    "metrics": [
                        {
                            "key": "accuracy",
                            "value": Decimal("0.8000000000000001") + page,
                            "timestamp": 1234567890000 + page,
                            "step": 5 + page,
                            "model_id": "model-01",
                            "dataset_name": "test",
                            "dataset_digest": "abc",
                        }
                    ]
                }
                if page == 0 or state["repeat"]:
                    payload["next_page_token"] = "1"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json_text(payload).encode())

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    state["url"] = f"http://127.0.0.1:{server.server_port}"
    try:
        yield state
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def mlflow_request(server):
    return {
        "provider": "mlflow",
        "origin": server["url"],
        "runs": ["run-001", "run-1"],
        "metrics": ["accuracy", "loss"],
        "identity": {
            "seed": {"scope": "param", "field": "seed", "type": "string"},
            "split": {"scope": "param", "field": "split"},
            "checkpoint": {"scope": "tag", "field": "checkpoint"},
        },
    }


def test_actual_paginated_mlflow_gets_become_portable_offline_records(
    tmp_path, tracking_server, monkeypatch
):
    project = Project(tmp_path)
    monkeypatch.setenv("MLFLOW_TRACKING_TOKEN", "credential-never-stored")
    result = import_evidence(project, mlflow_request(tracking_server), "results.pdevidence.json")
    calls = len(tracking_server["calls"])
    assert calls == 8 and result["records"] == 6
    assert all(call[2] == "Bearer credential-never-stored" for call in tracking_server["calls"])
    assert "credential-never-stored" not in project.text(result["path"])[0]
    actual = resolve(project, result, {"run_id": "run-001", "metric": "accuracy", "step": 5})
    assert actual.quantity.value == Decimal("0.8000000000000001")
    document = validate_export(read_export(project))
    assert document.records[0].values["seed"] == "001"
    assert document.records[0].values["checkpoint"] == "epoch-5"
    assert document.records[0].values["dataset_digest"] == "abc"
    assert actual.evidence[0]["provenance"]["precision"] == "api-double"
    assert actual.evidence[0]["locations"][0]["pointer"] == "/metrics/0"
    with pytest.raises(PaperDeltaError):
        resolve(project, result, {"run_id": "run-001", "metric": "loss"})
    with pytest.raises(PaperDeltaError):
        resolve(project, result, {"run_id": "run-001", "metric": "accuracy"})
    with pytest.raises(PaperDeltaError, match="already exists"):
        import_evidence(project, mlflow_request(tracking_server), "results.pdevidence.json")
    assert len(tracking_server["calls"]) == calls  # No read/inspection/overwrite triggers a fetch.

    edited = read_export(project)
    edited["records"][0]["values"]["value"] = "99"
    edited["export_id"] = fingerprint({k: v for k, v in edited.items() if k != "export_id"})
    with pytest.raises(PaperDeltaError) as failure:
        validate_export(edited)
    assert failure.value.code == "EXPORT_PROJECTION"
    edited = read_export(project)
    edited["snapshots"][0]["content_base64"] = base64.b64encode(b"changed").decode()
    edited["export_id"] = fingerprint({k: v for k, v in edited.items() if k != "export_id"})
    with pytest.raises(PaperDeltaError) as failure:
        validate_export(edited)
    assert failure.value.code == "EXPORT_IDENTITY"


@pytest.mark.parametrize(
    "mode,code",
    [("repeat", "EXPORT_PAGINATION"), ("active", "EXPORT_ACTIVE_RUN"), ("error", "EXPORT_REQUEST")],
)
def test_failed_remote_import_has_no_partial_output(tmp_path, tracking_server, mode, code):
    if mode == "active":
        tracking_server["status"] = "RUNNING"
    else:
        tracking_server[mode] = True
    with pytest.raises(PaperDeltaError) as failure:
        import_evidence(
            Project(tmp_path), mlflow_request(tracking_server), "results.pdevidence.json"
        )
    assert failure.value.code == code and "SECRET_FROM_SERVER" not in str(failure.value)
    assert not (tmp_path / "results.pdevidence.json").exists()


def test_real_wandb_sdk_scan_crosses_empty_page_and_preserves_sparse_and_nonfinite_rows(tmp_path):
    pytest.importorskip("wandb")
    from wandb.apis.public import Run
    from wandb.proto import wandb_api_pb2 as pb

    requests = []

    class Service:
        def send_api_request(self, request):
            read = request.read_run_history_request
            response = pb.ApiResponse()
            if read.HasField("scan_run_history_init"):
                assert not read.scan_run_history_init.use_cache
                assert not read.scan_run_history_init.keys
                response.read_run_history_response.scan_run_history_init.request_id = 1
                return response
            page = read.scan_run_history
            requests.append((page.min_step, page.max_step))
            rows = {
                0: [
                    {
                        "_step": 0,
                        "_timestamp": 12.5,
                        "accuracy": 0.8000000000000002,
                        "checkpoint": "epoch-0",
                    }
                ],
                2000: [
                    {
                        "_step": 2500,
                        "_timestamp": 25.5,
                        "loss": float("nan"),
                        "checkpoint": "epoch-25",
                    }
                ],
            }.get(page.min_step, [])
            for item in rows:
                row = response.read_run_history_response.run_history.history_rows.add()
                for key, value in item.items():
                    row.history_items.add(key=key, value_json=json.dumps(value))
            return response

        def finalize(self, owner, request):
            assert request.read_run_history_request.HasField("scan_run_history_cleanup")

    class RemoteRun:
        # Exercise the installed SDK's actual Run.scan_history and HistoryScan,
        # replacing only its transport with controlled protobuf responses.
        scan_history = Run.scan_history
        _service_api = Service()
        lastHistoryStep = 2500
        entity, project, id = "org", "experiment", "run001"
        path = [entity, project, id]
        state = "finished"
        config = {"seed": 1, "split": "test"}

    api = SimpleNamespace(run=lambda path: RemoteRun())
    request = {
        "provider": "wandb",
        "origin": "https://api.wandb.ai",
        "runs": ["org/experiment/run001"],
        "metrics": ["accuracy", "loss"],
        "identity": {
            "seed": {"scope": "config", "field": "seed", "type": "integer"},
            "split": {"scope": "config", "field": "split"},
            "checkpoint": {"scope": "history", "field": "checkpoint"},
        },
    }
    project = Project(tmp_path)
    result = import_evidence(project, request, "results.pdevidence.json", wandb_api=api)
    assert requests == [(0, 1000), (1000, 2000), (2000, 2501)]
    document = validate_export(read_export(project))
    assert len(document.records) == 4
    assert [row.values["status"] for row in document.records] == [
        "observed",
        "missing",
        "missing",
        "nonfinite",
    ]
    actual = resolve(project, result, {"metric": "accuracy", "step": 0, "seed": 1})
    assert actual.quantity.value == Decimal("0.8000000000000002")
    assert actual.evidence[0]["provenance"]["precision"] == "sdk-binary64"
    assert document.records[1].values["checkpoint"] == "epoch-25"
    assert len(requests) == 3
    mismatch = deepcopy(request)
    mismatch["identity"]["seed"]["type"] = "string"
    with pytest.raises(PaperDeltaError) as failure:
        import_evidence(project, mismatch, "wrong.pdevidence.json", wandb_api=api)
    assert failure.value.code == "EXPORT_IDENTITY_TYPE"


def test_missing_experiment_identity_is_an_unknown_batch_choice(tmp_path):
    request = {
        "provider": "wandb",
        "origin": "https://api.wandb.ai",
        "runs": ["e/p/r"],
        "metrics": ["accuracy"],
        "identity": {"checkpoint": {"scope": "history", "field": "checkpoint", "type": "string"}},
    }
    run = SimpleNamespace(
        path=["e", "p", "r"],
        state="finished",
        config={},
        lastHistoryStep=1,
        scan_history=lambda **kwargs: iter(
            [
                {"_step": 0, "accuracy": 0.8, "checkpoint": "epoch-0"},
                {"_step": 1, "accuracy": 0.9},
            ]
        ),
    )
    project = Project(tmp_path)
    result = import_evidence(
        project, request, "results.pdevidence.json", wandb_api=SimpleNamespace(run=lambda path: run)
    )
    project.write("paper.tex", b"Accuracy: 80.0\\%.\n")
    init_project(project, "paper.tex", [result["path"]])
    draft = builder.add_source(
        project, builder.start_draft(project), name="results", **result["source"]
    )
    catalog = create_catalog(
        project,
        draft,
        {
            "source": "results",
            "fields": ["value"],
            "group_by": ["checkpoint"],
            "unit": "fraction",
            "reduce": "unique",
            "expected_count": 1,
        },
    )
    assert [item["status"] for item in inspect_catalog(project, catalog)["choices"]] == [
        "ready",
        "unknown",
    ]


@pytest.mark.parametrize("lang", ["en", "zh-CN"])
def test_real_cli_import_and_inspect_work_without_a_manuscript(tmp_path, lang):
    project = Project(tmp_path)
    project.write("local.tsv", b"model\tvalue\n001\t0.80000000000000000000000000001\n")
    project.write(
        "request.json",
        json_text(
            {
                "provider": "file",
                "origin": "local.tsv",
                "source": {
                    "path": "local.tsv",
                    "format": "tsv",
                    "primary_key": ["model"],
                    "columns": {"model": "string", "value": "decimal"},
                },
            }
        ).encode(),
    )
    command = [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "paperdelta",
        "--lang",
        lang,
        "-C",
        str(tmp_path),
        "evidence",
    ]
    result = subprocess.run(
        command + ["import", "request.json", "--out", "offline.pdevidence.json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["records"] == 1
    project.path("local.tsv").unlink()
    read = subprocess.run(
        command + ["inspect", "offline.pdevidence.json"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert read.returncode == 0, read.stderr
    assert (
        json.loads(read.stdout)["sample"][0]["values"]["value"] == "0.80000000000000000000000000001"
    )


@pytest.mark.parametrize(
    "origin", ["http://remote.test", "https://u:p@host.test", "https://host.test?token=x"]
)
def test_endpoints_do_not_allow_embedded_credentials_or_cleartext_remote_hosts(tmp_path, origin):
    with pytest.raises(PaperDeltaError):
        import_evidence(
            Project(tmp_path),
            {"provider": "mlflow", "origin": origin, "runs": ["run"], "metrics": ["accuracy"]},
            "rejected.pdevidence.json",
        )
    assert not (tmp_path / "rejected.pdevidence.json").exists()
