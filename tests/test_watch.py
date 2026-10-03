import json
import os
import queue
import subprocess
import sys
import threading
from copy import deepcopy

import pytest

from paperdelta.analysis import check_project
from paperdelta.config import config_text, load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.records import StoredReport
from paperdelta.storage import Project, parse_json
from paperdelta.watch import Watcher


def normalized(report):
    report = deepcopy(report)
    report.pop("created_at", None)
    report.pop("watch", None)
    return report


def test_watch_coalesces_changes_marks_old_results_pending_and_matches_full_check(
    project, change_results
):
    store = Project(project)
    events = []
    watcher = Watcher(store, debounce=0.5, publish=events.append)
    first = watcher.step(0)
    assert first["exit_code"] == 0
    assert normalized(first) == normalized(check_project(project))
    change_results(project)
    assert watcher.step(1) is None
    assert events[-1]["exit_code"] == 2
    assert events[-1]["watch"]["state"] == "pending"
    assert events[-1]["actions"][0]["kind"] == "wait_for_check"
    store.write(
        "results/metrics.csv", store.read("results/metrics.csv").replace(b"0.809", b"0.805")
    )
    assert watcher.step(1.3) is None
    assert watcher.step(1.6) is None
    checked = watcher.step(1.9)
    assert checked["watch"]["generation"] == 2
    assert normalized(checked) == normalized(check_project(project))
    assert checked["exit_code"] == 1
    assert any(action["kind"] == "review_claims" for action in checked["actions"])
    assert all(action["kind"] != "update_numbers" for action in checked["actions"])
    assert watcher.step(3) is None
    assert watcher.generation == 2  # Generated reports never trigger themselves.
    stopped = watcher.stop()
    StoredReport.model_validate(stopped)
    assert stopped["watch"]["state"] == "stopped"
    assert 'http-equiv="refresh"' not in store.text("build/paperdelta/report.html")[0]


def test_watch_uses_content_not_size_or_mtime(project):
    watcher = Watcher(Project(project), debounce=0)
    watcher.step(0)
    source = project / "results/metrics.csv"
    old = source.stat()
    source.write_bytes(source.read_bytes().replace(b"0.841", b"0.809"))
    assert source.stat().st_size == old.st_size
    os.utime(source, ns=(old.st_atime_ns, old.st_mtime_ns))
    assert watcher.step(1)["exit_code"] == 1


def test_watch_recovers_missing_data_new_include_and_malformed_config(project):
    store = Project(project)
    watcher = Watcher(store, debounce=0)
    watcher.step(0)
    source = store.read("results/metrics.csv")
    (project / "results/metrics.csv").unlink()
    assert watcher.step(1)["exit_code"] == 2
    store.write("results/metrics.csv", source)
    assert watcher.step(2)["exit_code"] == 0
    main = store.read("paper/main.tex")
    store.write(
        "paper/main.tex", main.replace(b"\\end{document}", b"\\input{added}\n\\end{document}")
    )
    assert watcher.step(3)["exit_code"] == 2
    store.write("paper/added.tex", b"Additional discussion.\n")
    assert watcher.step(4)["exit_code"] == 0
    original = store.read("paperdelta.yaml")
    store.write("paperdelta.yaml", b"sources: [")
    assert watcher.step(5)["exit_code"] == 2
    store.write("paperdelta.yaml", original)
    assert watcher.step(6)["exit_code"] == 0
    watcher.stop()


def test_changes_during_check_cannot_publish_a_current_pass(project, monkeypatch, change_results):
    store = Project(project)
    events = []
    watcher = Watcher(store, debounce=0.2, publish=events.append)
    original = watcher._check

    def changing():
        report = original()
        change_results(project)
        return report

    monkeypatch.setattr(watcher, "_check", changing)
    report = watcher.step(0)
    assert report["watch"]["state"] == "pending" and report["exit_code"] == 2
    assert not any(event["exit_code"] == 0 for event in events)
    monkeypatch.setattr(watcher, "_check", original)
    assert watcher.step(1)["exit_code"] == 1


def test_stopping_with_unchecked_edits_never_leaves_a_success_verdict(project, change_results):
    watcher = Watcher(Project(project), debounce=1)
    watcher.step(0)
    change_results(project)
    stopped = watcher.stop()
    assert stopped["exit_code"] == 2
    assert stopped["watch"]["state"] == "stopped"


def test_first_check_tracks_an_explicit_include_inside_a_discovery_exclusion(project, monkeypatch):
    store = Project(project)
    store.write("build/included.tex", b"A generated sentence.\n")
    store.write(
        "paper/main.tex",
        store.read("paper/main.tex").replace(
            b"\\end{document}", b"\\input{../build/included}\n\\end{document}"
        ),
    )
    watcher = Watcher(store, debounce=0)
    original = watcher._check

    def changing():
        report = original()
        store.write("build/included.tex", b"Changed after the checker read this include.\n")
        return report

    monkeypatch.setattr(watcher, "_check", changing)
    first = watcher.step(0)
    assert first["exit_code"] == 2 and first["watch"]["state"] == "pending"
    monkeypatch.setattr(watcher, "_check", original)
    assert watcher.step(1)["exit_code"] == 0


def test_watch_refuses_report_output_that_overwrites_declared_evidence(project):
    store = Project(project)
    config, _ = load_config(store)
    source = store.read("results/metrics.csv")
    config.sources["benchmark"].path = "build/live/report.json"
    store.write("build/live/report.json", source)
    store.write("paperdelta.yaml", config_text(config).encode())
    with pytest.raises(PaperDeltaError) as error:
        Watcher(store, directory="build/live").step(0)
    assert error.value.code == "REPORT_OVERWRITE"
    assert store.read("build/live/report.json") == source


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_real_watch_process_detects_data_only_edits_and_stops_cleanly(
    project, change_results, language
):
    command = [
        sys.executable,
        "-m",
        "paperdelta",
        "--lang",
        language,
        "-C",
        str(project),
        "watch",
        "--interval",
        "0.1",
        "--debounce",
        "0.1",
        "--max-checks",
        "2",
        "--format",
        "json",
    ]
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8"
    )
    messages = queue.Queue()
    reader = threading.Thread(
        target=lambda: [messages.put(line) for line in process.stdout], daemon=True
    )
    reader.start()
    try:
        first = json.loads(messages.get(timeout=20))
        assert first["event"] == "running" and first["exit_code"] == 0
        change_results(project)
        assert process.wait(timeout=20) == 1, process.stderr.read()
        reader.join(timeout=2)
        events = []
        while not messages.empty():
            events.append(json.loads(messages.get_nowait()))
        assert any(event["event"] == "pending" and event["exit_code"] == 2 for event in events)
        assert events[-1]["event"] == "stopped"
        saved = parse_json((project / "build/paperdelta/report.json").read_text(encoding="utf-8"))
        assert saved["watch"]["generation"] == 2 and saved["exit_code"] == 1
        assert saved["claims"]["main_comparison"]["status"] == "mismatch"
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)
        process.stdout.close()
        process.stderr.close()


def test_once_and_invalid_timing_options_use_real_cli(project):
    command = [sys.executable, "-m", "paperdelta", "-C", str(project), "watch"]
    completed = subprocess.run(
        [*command, "--once", "--format", "json"], capture_output=True, encoding="utf-8"
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.splitlines()[-1])["event"] == "stopped"
    failed = subprocess.run(
        [*command, "--interval", "nan", "--once", "--format", "json"],
        capture_output=True,
        encoding="utf-8",
    )
    assert failed.returncode == 2
    assert json.loads(failed.stdout)["error"] == "WATCH_OPTIONS"
