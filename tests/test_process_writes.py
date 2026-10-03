"""Exercise write contention and abrupt process death against actual OS locks."""

import json
import queue
import subprocess
import sys
import threading

import pytest

from paperdelta.analysis import check_project
from paperdelta.patches import create_patch
from paperdelta.storage import Project, json_text

PAUSED_WRITER = r"""
import json
import sys

from paperdelta.patches import apply_patch
from paperdelta.storage import Project, parse_json

project = Project(sys.argv[1])
patch = parse_json(project.text("process-patch.json")[0])
original_write = Project.write
paused = False

def write_then_pause(self, relative, raw, **kwargs):
    global paused
    result = original_write(self, relative, raw, **kwargs)
    if relative.endswith(".tex") and not paused:
        paused = True
        print(json.dumps({"first_file_written": relative}), flush=True)
        if sys.stdin.readline().strip() != "continue":
            raise RuntimeError("Parent did not authorize continuation")
    return result

Project.write = write_then_pause
result = apply_patch(project, patch)
print(json.dumps({"status": result["status"]}), flush=True)
"""


def _paper_bytes(project):
    return {path.relative_to(project): path.read_bytes() for path in project.rglob("*.tex")}


def _cli(project, *arguments):
    return subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "paperdelta", "-C", str(project), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


@pytest.mark.parametrize("owner_exit", ["continue", "kill"])
def test_process_contention_and_owner_exit(project, change_results, owner_exit):
    change_results(project, new=("0.843", "0.845", "0.847"))
    patch = create_patch(Project(project), check_project(project))
    (project / "process-patch.json").write_text(json_text(patch), encoding="utf-8")
    before = _paper_bytes(project)
    config_before = (project / "paperdelta.yaml").read_bytes()
    writer = subprocess.Popen(
        [sys.executable, "-X", "utf8", "-c", PAUSED_WRITER, str(project)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    )
    try:
        ready = queue.Queue()
        reader = threading.Thread(target=lambda: ready.put(writer.stdout.readline()), daemon=True)
        reader.start()
        message = ready.get(timeout=60)
        assert message, "The writer exited before committing its first file"
        assert "first_file_written" in json.loads(message)
        reader.join(timeout=5)
        partial = _paper_bytes(project)
        assert sum(partial[name] != raw for name, raw in before.items()) == 1
        manifests = list((project / ".paperdelta/transactions").glob("*/manifest.json"))
        assert len(manifests) == 1
        manifest = manifests[0]
        journal_before = manifest.read_bytes()
        record = json.loads(journal_before)
        assert record["status"] == "applying"

        # Independent CLI processes must not start a second write or recovery.
        for arguments in (
            ("apply", "process-patch.json", "--write"),
            ("recover", record["id"], "--write"),
        ):
            competing = _cli(project, *arguments)
            assert competing.returncode == 2 and "WRITE_LOCKED" in competing.stderr
            assert _paper_bytes(project) == partial
            assert manifest.read_bytes() == journal_before
            assert (project / "paperdelta.yaml").read_bytes() == config_before
            assert list((project / ".paperdelta/transactions").glob("*/manifest.json")) == [
                manifest
            ]

        if owner_exit == "continue":
            writer.stdin.write("continue\n")
            writer.stdin.flush()
            output, error = writer.communicate(timeout=60)
            assert writer.returncode == 0, error
            assert json.loads(output)["status"] == "applied"
            assert check_project(project)["exit_code"] == 0
        else:
            # This skips Python exception handlers and lock-release finally blocks.
            writer.kill()
            writer.communicate(timeout=30)
            assert writer.returncode != 0
            assert manifest.read_bytes() == journal_before
            retry = _cli(project, "apply", "process-patch.json", "--write")
            assert retry.returncode == 2 and "RECOVERY_REQUIRED" in retry.stderr
            assert _paper_bytes(project) == partial

        recovered = _cli(project, "recover", record["id"], "--write")
        assert recovered.returncode == 0, recovered.stderr
        assert json.loads(recovered.stdout)["status"] == "reverted"
        assert _paper_bytes(project) == before
        assert (project / "paperdelta.yaml").read_bytes() == config_before
        assert json.loads(manifest.read_bytes())["status"] == "reverted"

        # Recovery restores the exact pre-patch state, so the same patch can run again.
        reapplied = _cli(project, "apply", "process-patch.json", "--write")
        assert reapplied.returncode == 0, reapplied.stderr
        assert check_project(project)["exit_code"] == 0
    finally:
        if writer.poll() is None:
            writer.kill()
        writer.communicate(timeout=30)
