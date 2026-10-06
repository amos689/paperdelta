"""Previewable support metadata. No manuscript, evidence, paths or error messages."""

from __future__ import annotations

import importlib.metadata
import io
import platform
import re
from collections import Counter
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from paperdelta import __version__
from paperdelta.doctor import diagnose
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg, tr
from paperdelta.storage import fingerprint, json_text

PACKAGES = (
    "pydantic",
    "PyYAML",
    "pylatexenc",
    "mpmath",
    "markdown-it-py",
    "python-docx",
    "lxml",
    "pdfplumber",
    "pdfminer.six",
    "mcp",
)
EXCLUDED = [
    "manuscript_text",
    "evidence_values",
    "file_names",
    "personal_paths",
    "environment_variables",
    "error_messages",
    "project_identifiers",
    "input_hashes",
]


def _version(name):
    try:
        version = importlib.metadata.version(name)
        return version if re.fullmatch(r"[A-Za-z0-9.+_-]{1,80}", version) else "unrecognized"
    except importlib.metadata.PackageNotFoundError:
        return None


def preview_bundle(project, config_path="paperdelta.yaml"):
    doctor = diagnose(project, config_path)
    # Only explicitly enumerated fields leave the doctor result. In particular,
    # translated messages and project finding IDs can contain private content.
    statuses = Counter(
        item["status"] if item["status"] in {"ok", "error", "warning", "optional"} else "other"
        for item in doctor["checks"]
    )
    codes = Counter(
        item["code"] if re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", item["code"]) else "OTHER"
        for item in doctor["checks"]
        if item.get("code")
    )
    payload = {
        "diagnostic_bundle_schema_version": 1,
        "tool_version": __version__,
        "python": platform.python_version(),
        "system": platform.system()
        if platform.system() in {"Windows", "Darwin", "Linux"}
        else "Other",
        "architecture": platform.machine()
        if platform.machine()
        in {
            "AMD64",
            "x86_64",
            "arm64",
            "aarch64",
            "x86",
            "i686",
            "ARM64",
        }
        else "Other",
        "dependencies": {name: _version(name) for name in PACKAGES},
        "doctor": {
            "status_counts": dict(sorted(statuses.items())),
            "diagnostic_codes": dict(sorted(codes.items())),
            "project_check_exit_code": doctor["project_check_exit_code"]
            if doctor["project_check_exit_code"] in {0, 1, 2, None}
            else None,
        },
        "privacy": {"excluded": EXCLUDED, "uploads": False},
    }
    return {
        "preview_id": fingerprint(payload),
        "files": {"diagnostics.json": payload},
        "notice": tr("diagnostics.notice"),
    }


def bundle_bytes(project, preview_id, config_path="paperdelta.yaml"):
    preview = preview_bundle(project, config_path)
    if preview_id != preview["preview_id"]:
        raise PaperDeltaError("DIAGNOSTIC_PREVIEW_CHANGED", msg("diagnostics.changed"))
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        entry = ZipInfo("diagnostics.json", (1980, 1, 1, 0, 0, 0))
        entry.compress_type = ZIP_DEFLATED
        archive.writestr(entry, json_text(preview["files"]["diagnostics.json"]).encode("utf-8"))
    return output.getvalue()
