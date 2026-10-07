from __future__ import annotations

import re
from datetime import UTC, datetime

from paperdelta.errors import PaperDeltaError
from paperdelta.records import Snapshot, validate_record
from paperdelta.storage import Project, json_text, parse_json


def snapshot_path(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", name):
        raise PaperDeltaError(
            "SNAPSHOT_NAME", "Use a short snapshot name containing letters, digits, _.-"
        )
    return f".paperdelta/baselines/{name}.json"


def create_snapshot(project: Project, name: str, report: dict) -> str:
    path = snapshot_path(name)
    value = {
        "snapshot_schema_version": 1,
        "name": name,
        "created_at": datetime.now(UTC).isoformat(),
        "report": report,
    }
    validate_record(Snapshot, value, "BASELINE_SCHEMA")
    project.write(path, json_text(value).encode("utf-8"), exclusive=True)
    return path


def read_snapshot(project: Project, name: str) -> dict:
    text, _ = project.text(snapshot_path(name))
    value = parse_json(text)
    validate_record(Snapshot, value, "BASELINE_SCHEMA")
    return value
