"""Observe only a command explicitly supplied to the run command; never used by checking."""

import subprocess
import uuid
from datetime import UTC, datetime

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.notebooks import inspect_notebook
from paperdelta.provenance import ProducerSpec, _safe_path, producer_record
from paperdelta.records import validate_record
from paperdelta.storage import fingerprint, sha256


def _code_identity(project, spec):
    if spec.kind == "quarto":
        return sha256(project.read(spec.source))
    notebook = inspect_notebook(project, spec.source)
    return fingerprint(
        [
            {key: cell[key] for key in ("id", "cell_type", "source_hash")}
            for cell in notebook["cells"]
        ]
    )


def observe_producer_command(project, spec, command, rationale, *, timeout=600):
    spec = validate_record(ProducerSpec, spec, "PROVENANCE_SPEC")
    if (
        not command
        or not command[0]
        or len(command) > 128
        or not 1 <= timeout <= 3600
        or any(not isinstance(arg, str) or "\x00" in arg or len(arg) > 8192 for arg in command)
    ):
        raise PaperDeltaError("PROVENANCE_COMMAND", msg("provenance.command"))
    paths = [spec.source, *spec.inputs, *spec.outputs]
    if [_safe_path(project, name) for name in paths] != paths:
        raise PaperDeltaError("PROVENANCE_SPEC", msg("provenance.distinct"))
    source_hash = sha256(project.read(spec.source))
    source_code = _code_identity(project, spec)
    inputs = {name: sha256(project.read(name)) for name in spec.inputs}
    logs = ".paperdelta/run-logs/" + uuid.uuid4().hex
    project.path(logs).mkdir(parents=True)
    started = datetime.now(UTC).isoformat()
    try:
        with (
            project.path(logs + "/stdout.log").open("wb") as stdout,
            project.path(logs + "/stderr.log").open("wb") as stderr,
        ):
            result = subprocess.run(
                command,
                cwd=project.root,
                shell=False,
                check=False,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
            )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PaperDeltaError("PROVENANCE_RUN", msg("provenance.run_error", logs=logs)) from error
    finished = datetime.now(UTC).isoformat()
    if result.returncode:
        raise PaperDeltaError(
            "PROVENANCE_RUN", msg("provenance.run_failed", code=result.returncode, logs=logs)
        )
    if _code_identity(project, spec) != source_code or any(
        sha256(project.read(name)) != digest for name, digest in inputs.items()
    ):
        raise PaperDeltaError("PROVENANCE_RUN_CHANGED", msg("provenance.run_changed", logs=logs))
    observation = {
        "command": command,
        "started_at": started,
        "finished_at": finished,
        "exit_code": 0,
        "input_hashes_before": inputs,
        "source_hash_before": source_hash,
        "stdout_hash": sha256(project.read(logs + "/stdout.log")),
        "stderr_hash": sha256(project.read(logs + "/stderr.log")),
    }
    record = producer_record(project, spec.model_dump(), rationale, observation=observation)
    return {"record": record, "logs": logs, "accepted": False}
