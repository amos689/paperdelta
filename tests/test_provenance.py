import pytest
from test_notebooks import notebook

from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.provenance import (
    accept_producer,
    producer_record,
    propose_producer,
)
from paperdelta.storage import Project, fingerprint, json_text


def setup_notebook(project):
    store = Project(project)
    store.write("analysis.ipynb", json_text(notebook()).encode())
    store.write("observations.csv", b"sample,value\na,1\n")
    spec = {
        "kind": "notebook",
        "source": "analysis.ipynb",
        "inputs": ["observations.csv"],
        "outputs": ["results/metrics.csv"],
        "cells": ["train-result"],
    }
    record = producer_record(store, spec, "The selected cell exports the named result table.")
    proposal = propose_producer(store, "training", record)
    return store, spec, proposal


def test_reviewed_notebook_source_tracks_changed_inputs_code_and_saved_outputs(project):
    store, _, proposal = setup_notebook(project)
    original = store.read("paperdelta.yaml")
    accepted = accept_producer(store, proposal)
    assert store.read(accepted["backup"]) == original
    report = check_project(project)
    assert report["exit_code"] == 0
    state = report["provenance"]["training"]
    assert state["status"] == "pass" and state["method"] == "declared"
    assert state["observed_command"] is None
    assert report["report_schema_version"] == 9
    store.write("observations.csv", b"sample,value\na,2\n")
    changed = check_project(project)
    assert changed["exit_code"] == 1
    assert changed["provenance"]["training"]["changed_paths"] == ["observations.csv"]
    current = notebook()
    current["cells"][0]["source"] = "print('new source but old outputs')"
    store.write("analysis.ipynb", json_text(current).encode())
    state = check_project(project)["provenance"]["training"]
    assert state["cells"][0]["code_changed"] and not state["cells"][0]["outputs_changed"]


def test_unexecuted_notebook_and_missing_producer_evidence_remain_unknown(project):
    store, _, proposal = setup_notebook(project)
    accept_producer(store, proposal)
    value = notebook()
    value["cells"][0]["execution_count"] = None
    store.write("analysis.ipynb", json_text(value).encode())
    report = check_project(project)
    assert report["exit_code"] == 2
    assert report["provenance"]["training"]["unverified_cells"] == ["train-result"]
    (project / "analysis.ipynb").unlink()
    report = check_project(project)
    assert report["exit_code"] == 2 and report["provenance"]["training"]["status"] == "unknown"


def test_producer_acceptance_refuses_changed_previews_and_requires_explicit_replacement(project):
    store, spec, proposal = setup_notebook(project)
    before = store.read("paperdelta.yaml")
    store.write("observations.csv", b"changed\n")
    with pytest.raises(PaperDeltaError) as error:
        accept_producer(store, proposal)
    assert error.value.code == "PROVENANCE_STALE"
    assert store.read("paperdelta.yaml") == before
    record = producer_record(store, spec, "Review updated listed inputs and saved outputs.")
    accept_producer(store, propose_producer(store, "training", record))
    with pytest.raises(PaperDeltaError) as error:
        propose_producer(store, "training", record)
    assert error.value.code == "PROVENANCE_EXISTS"
    assert propose_producer(store, "training", record, replace=True)["replace"]


def test_quarto_render_record_detects_old_output_after_source_changes(project):
    store = Project(project)
    store.write("manuscript.qmd", b"# Results\n\nScore: 84.1%.\n")
    store.write("rendered.html", b"<h1>Results</h1><p>Score: 84.1%.</p>")
    spec = {
        "kind": "quarto",
        "source": "manuscript.qmd",
        "inputs": ["results/metrics.csv"],
        "outputs": ["rendered.html"],
    }
    record = producer_record(store, spec, "Declared render from the source and result table.")
    accept_producer(store, propose_producer(store, "render", record))
    assert check_project(project)["provenance"]["render"]["status"] == "pass"
    store.write("manuscript.qmd", b"# Results\n\nScore: 80.9%.\n")
    state = check_project(project)["provenance"]["render"]
    assert state["status"] == "mismatch"
    assert state["changed_paths"] == ["manuscript.qmd"]
    assert state["outputs"] == ["rendered.html"]


def test_empty_producer_extension_preserves_existing_configuration_identity(project):
    config, _ = load_config(Project(project))
    legacy = config.model_dump()
    assert "provenance" not in legacy
    config.provenance = {}
    assert fingerprint(config) == fingerprint(legacy)


def test_explicit_command_run_records_actual_process_without_accepting_or_reexecuting(project):
    import sys

    from paperdelta.producer_run import observe_producer_command

    store, spec, _ = setup_notebook(project)
    original = store.read("paperdelta.yaml")
    command = [sys.executable, "-I", "-c", "print('An explicitly requested controlled command')"]
    observed = observe_producer_command(store, spec, command, "Observe a controlled process.")
    assert not observed["accepted"] and store.read("paperdelta.yaml") == original
    assert observed["record"]["method"] == "observed_command"
    assert observed["record"]["observation"]["exit_code"] == 0
    assert b"explicitly requested" in store.read(observed["logs"] + "/stdout.log")
    accept_producer(store, propose_producer(store, "observed", observed["record"]))
    report = check_project(project)
    assert report["provenance"]["observed"]["observed_command"] == command


@pytest.mark.parametrize(
    "program,code",
    [
        ("raise SystemExit(7)", "PROVENANCE_RUN"),
        (
            "from pathlib import Path; Path('observations.csv').write_text('changed')",
            "PROVENANCE_RUN_CHANGED",
        ),
    ],
)
def test_failed_or_input_changing_runs_do_not_create_successful_provenance(project, program, code):
    import sys

    from paperdelta.producer_run import observe_producer_command

    store, spec, _ = setup_notebook(project)
    original = store.read("paperdelta.yaml")
    with pytest.raises(PaperDeltaError) as error:
        observe_producer_command(
            store, spec, [sys.executable, "-I", "-c", program], "Controlled failure."
        )
    assert error.value.code == code
    assert store.read("paperdelta.yaml") == original


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_provenance_cli_produces_unaccepted_preview_and_requires_explicit_accept(
    project, capsys, language
):
    from paperdelta.cli import main

    store, _, _ = setup_notebook(project)
    prefix = ["--lang", language, "-C", str(project), "provenance"]
    before = store.read("paperdelta.yaml")
    assert (
        main(
            prefix
            + [
                "preview",
                "training",
                "--kind",
                "notebook",
                "--source",
                "analysis.ipynb",
                "--cell",
                "train-result",
                "--input",
                "observations.csv",
                "--output",
                "results/metrics.csv",
                "--rationale",
                "Reviewed input and output relationship",
                "--out",
                "producer-plan.json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    assert store.read("paperdelta.yaml") == before
    assert main(prefix + ["accept", "producer-plan.json"]) == 0
    capsys.readouterr()
    assert load_config(store)[0].provenance["training"]


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_cli_run_preserves_external_arguments_and_requires_acceptance(project, capsys, language):
    import sys

    from paperdelta.cli import main
    from paperdelta.storage import parse_json

    store, _, _ = setup_notebook(project)
    original = store.read("paperdelta.yaml")
    arguments = [
        "--lang",
        language,
        "-C",
        str(project),
        "provenance",
        "run",
        "observed",
        "--kind",
        "notebook",
        "--source",
        "analysis.ipynb",
        "--cell",
        "train-result",
        "--input",
        "observations.csv",
        "--output",
        "results/metrics.csv",
        "--rationale",
        "Explicitly observe an argument-preserving process.",
        "--out",
        "run-plan.json",
        "--command",
        sys.executable,
        "-I",
        "-c",
        "import sys; assert sys.argv[1:] == ['--lang', 'unchanged', '']; print('observed')",
        "--lang",
        "unchanged",
        "",
    ]
    assert main(arguments) == 0
    capsys.readouterr()
    plan = parse_json(store.read("run-plan.json").decode())
    assert plan["record"]["observation"]["command"][-3:] == ["--lang", "unchanged", ""]
    assert store.read("paperdelta.yaml") == original
    assert not load_config(store)[0].provenance


@pytest.mark.parametrize("invalid", ["name", "reason", "config_output", "timeout"])
def test_invalid_cli_run_is_rejected_before_execution(project, capsys, invalid):
    import sys

    from paperdelta.cli import main

    store, _, _ = setup_notebook(project)
    original = store.read("paperdelta.yaml")
    arguments = [
        "-C",
        str(project),
        "provenance",
        "run",
        "bad name" if invalid == "name" else "run",
        "--kind",
        "notebook",
        "--source",
        "analysis.ipynb",
        "--cell",
        "train-result",
        "--input",
        "observations.csv",
        "--output",
        "paperdelta.yaml" if invalid == "config_output" else "results/metrics.csv",
        "--rationale",
        "   " if invalid == "reason" else "Review the run.",
        "--timeout",
        "0" if invalid == "timeout" else "60",
        "--out",
        "run-plan.json",
        "--command",
        sys.executable,
        "-I",
        "-c",
        "from pathlib import Path; Path('executed.txt').write_text('unexpected')",
    ]
    assert main(arguments) == 2
    capsys.readouterr()
    assert not (project / "executed.txt").exists()
    assert not (project / "run-plan.json").exists()
    assert store.read("paperdelta.yaml") == original


def test_timed_out_command_keeps_logs_without_successful_record(project):
    import sys

    from paperdelta.producer_run import observe_producer_command

    store, spec, _ = setup_notebook(project)
    original = store.read("paperdelta.yaml")
    with pytest.raises(PaperDeltaError) as error:
        observe_producer_command(
            store,
            spec,
            [sys.executable, "-I", "-c", "import time; time.sleep(30)"],
            "Controlled timeout.",
            timeout=1,
        )
    assert error.value.code == "PROVENANCE_RUN"
    assert list((project / ".paperdelta/run-logs").glob("*/stderr.log"))
    assert store.read("paperdelta.yaml") == original
