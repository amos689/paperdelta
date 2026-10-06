"""Selected, previewed review artifacts and exact-input offline replay; no execution."""

from __future__ import annotations

import io
import stat
import uuid
import zlib
from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile, ZipInfo

from pydantic import Field

from paperdelta import __version__
from paperdelta.analysis import check_stored_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import current_language, language_context, msg, tr
from paperdelta.models import Hash, StrictModel, VersionOne
from paperdelta.pdf_previews import pdf_previews
from paperdelta.records import Snapshot, validate_record
from paperdelta.reports import html_report, markdown_report, write_reports
from paperdelta.sarif import sarif_report
from paperdelta.snapshots import read_snapshot, snapshot_path
from paperdelta.storage import Project, fingerprint, json_text, parse_json, sha256

MAX_FILE = 32 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_ARCHIVE = 160 * 1024 * 1024
FORMATS = {"json", "html", "md", "sarif"}


class BundleSelection(StrictModel):
    reports: list[Literal["json", "html", "md", "sarif"]] = Field(max_length=4)
    inputs: list[str] = Field(max_length=512)


class BundleFile(StrictModel):
    bytes: int = Field(ge=0, le=MAX_FILE)
    sha256: Hash
    kind: Literal["report", "input"]
    preview: str | None = Field(default=None, max_length=4096)
    truncated: bool = False


class BundlePlan(StrictModel):
    review_bundle_schema_version: VersionOne
    tool_version: str
    language: Literal["en", "zh-CN"]
    config_path: str
    baseline: str | None
    selection: BundleSelection
    checked_at: str
    report_fingerprint: Hash
    required_inputs: dict[str, Hash]
    scope: dict
    files: dict[str, BundleFile]
    replayable: bool
    missing_inputs: list[str]
    notice: str
    preview_id: Hash


def _error(key):
    return PaperDeltaError("REVIEW_BUNDLE_" + key.upper(), msg("bundle." + key))


def _name(value):
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or str(path) != value
        or value == "."
        or any(part in {".", ".."} or part.casefold() == ".git" for part in path.parts)
        or any(ord(character) < 32 or character in '\\:<>"|?*' for character in value)
        or any(
            part.rstrip(". ") != part
            or part.split(".")[0].casefold()
            in {
                "con",
                "prn",
                "aux",
                "nul",
                *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10)),
            }
            for part in path.parts
        )
    ):
        raise _error("path")
    return value


def _report_identity(report):
    return fingerprint({key: value for key, value in report.items() if key != "created_at"})


def _scope(config, report):
    return {
        "bindings": {
            group: sorted(getattr(config, group))
            for group in ("occurrences", "claims", "figures", "provenance", "fragments")
            if group in {"occurrences", "claims", "figures"} or getattr(config, group)
        },
        "review_scope": config.review_scope.model_dump() if config.review_scope else None,
        "coverage_exclusions": sorted(config.coverage_exclusions),
        "require_complete_coverage": config.require_complete_coverage,
        "check_exit_code": report["exit_code"],
        "coverage": {
            key: report["coverage"][key] for key in ("confirmed", "pass", "mismatch", "unknown")
        },
    }


def _entry(raw, kind, name):
    if len(raw) > MAX_FILE:
        raise _error("limit")
    preview = None
    if PurePosixPath(name).suffix.lower() in {
        ".json",
        ".yaml",
        ".yml",
        ".csv",
        ".tsv",
        ".tex",
        ".md",
        ".qmd",
        ".txt",
        ".py",
        ".bib",
        ".sarif",
        ".html",
    }:
        try:
            preview = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            pass
    return BundleFile(
        bytes=len(raw),
        sha256=sha256(raw),
        kind=kind,
        preview=preview[:4096] if preview is not None else None,
        truncated=preview is not None and len(preview) > 4096,
    )


def _prepare(project, selection, config_path, baseline, checked_at=None):
    selected = BundleSelection.model_validate(selection)
    if len(set(selected.reports)) != len(selected.reports) or len(set(selected.inputs)) != len(
        selected.inputs
    ):
        raise _error("selection")
    config_path = project.relative(project.path(config_path))
    config, config_hash = load_config(project, config_path)
    baseline_raw = project.read(snapshot_path(baseline)) if baseline else None
    saved = parse_json(baseline_raw.decode("utf-8-sig")) if baseline_raw else None
    if saved is not None:
        validate_record(Snapshot, saved, "BASELINE_SCHEMA")
    report = check_stored_project(project, config_path, saved)
    required = dict(report["input_hashes"])
    if required.get(config_path) != config_hash or any(
        d["rule"] == "INPUT_CHANGED" for d in report["diagnostics"]
    ):
        raise _error("changed")
    if baseline:
        required[snapshot_path(baseline)] = sha256(baseline_raw)
    for name in required:
        _name(name)
    if not set(selected.inputs) <= required.keys():
        raise _error("selection")
    if not selected.inputs and not selected.reports:
        raise _error("selection")
    if checked_at:
        try:
            timestamp = datetime.fromisoformat(checked_at)
            if timestamp.tzinfo is None:
                raise ValueError("Missing timezone")
        except ValueError as error:
            raise _error("plan") from error
        report["created_at"] = checked_at
    outputs = {}
    for name in sorted(selected.inputs):
        raw = project.read(_name(name), MAX_FILE)
        if sha256(raw) != required[name]:
            raise _error("changed")
        outputs["project/" + name] = raw
    for kind in sorted(selected.reports):
        value = {
            "json": lambda: json_text(report),
            "html": lambda: html_report(report, previews=pdf_previews(project, report)),
            "md": lambda: markdown_report(report),
            "sarif": lambda: json_text(sarif_report(report)),
        }[kind]()
        outputs[f"review/report.{kind}"] = value.encode("utf-8")
    if len(outputs) > 512 or sum(len(raw) for raw in outputs.values()) > MAX_TOTAL:
        raise _error("limit")
    files = {
        name: _entry(raw, "input" if name.startswith("project/") else "report", name)
        for name, raw in sorted(outputs.items())
    }
    if len({name.casefold() for name in files}) != len(files):
        raise _error("path")
    missing = sorted(required.keys() - set(selected.inputs))
    value = BundlePlan(
        review_bundle_schema_version=1,
        tool_version=__version__,
        language=current_language(),
        config_path=config_path,
        baseline=baseline,
        selection=selected,
        checked_at=report["created_at"],
        report_fingerprint=_report_identity(report),
        required_inputs=required,
        scope=_scope(config, report),
        files=files,
        replayable=not missing,
        missing_inputs=missing,
        notice=tr("bundle.notice"),
        preview_id="sha256:" + "0" * 64,
    )
    value.preview_id = fingerprint(value.model_dump(exclude={"preview_id"}))
    for name, expected in required.items():
        if sha256(project.read(name)) != expected:
            raise _error("changed")
    return value, outputs


def preview_bundle(project, selection, config_path="paperdelta.yaml", baseline=None):
    return _prepare(project, selection, config_path, baseline)[0].model_dump()


def _validate_plan(value):
    try:
        plan = BundlePlan.model_validate(value)
    except ValueError as error:
        raise _error("plan") from error
    if plan.preview_id != fingerprint(plan.model_dump(exclude={"preview_id"})):
        raise _error("plan")
    for name in [plan.config_path, *plan.required_inputs, *plan.files]:
        _name(name)
    expected_names = {"project/" + name for name in plan.selection.inputs} | {
        "review/report." + kind for kind in plan.selection.reports
    }
    missing = sorted(plan.required_inputs.keys() - set(plan.selection.inputs))
    if (
        expected_names != set(plan.files)
        or plan.config_path not in plan.required_inputs
        or (plan.baseline and snapshot_path(plan.baseline) not in plan.required_inputs)
        or not set(plan.selection.inputs) <= plan.required_inputs.keys()
        or plan.missing_inputs != missing
        or plan.replayable != (not missing)
        or len(plan.files) > 512
        or len({name.casefold() for name in plan.files}) != len(plan.files)
        or sum(entry.bytes for entry in plan.files.values()) > MAX_TOTAL
    ):
        raise _error("plan")
    for name in plan.selection.inputs:
        if plan.files["project/" + name].sha256 != plan.required_inputs[name]:
            raise _error("plan")
    return plan


def bundle_bytes(project, preview):
    plan = _validate_plan(preview)
    with language_context(plan.language):
        fresh, files = _prepare(
            project, plan.selection.model_dump(), plan.config_path, plan.baseline, plan.checked_at
        )
    if fresh.preview_id != plan.preview_id:
        raise _error("changed")
    output = io.BytesIO()
    files["review-bundle.json"] = json_text(plan.model_dump()).encode("utf-8")
    with ZipFile(output, "w") as archive:
        for name, raw in sorted(files.items()):
            entry = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            entry.external_attr = (stat.S_IFREG | 0o600) << 16
            archive.writestr(entry, raw)
    return output.getvalue()


def _read_bundle(raw):
    if len(raw) > MAX_ARCHIVE:
        raise _error("limit")
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            names = [_name(entry.filename) for entry in entries]
            if (
                len(entries) > 513
                or len(set(names)) != len(names)
                or len({name.casefold() for name in names}) != len(names)
                or "review-bundle.json" not in names
                or sum(entry.file_size for entry in entries) > MAX_TOTAL + 4 * 1024 * 1024
                or any(
                    entry.file_size > MAX_FILE
                    or entry.flag_bits & 1
                    or entry.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
                    or stat.S_ISLNK(entry.external_attr >> 16)
                    for entry in entries
                )
            ):
                raise _error("archive")
            manifest = archive.read("review-bundle.json")
            if len(manifest) > 4 * 1024 * 1024:
                raise _error("limit")
            plan = _validate_plan(parse_json(manifest.decode("utf-8")))
            if set(names) != {"review-bundle.json", *plan.files}:
                raise _error("archive")
            files = {}
            for name, entry in plan.files.items():
                data = archive.read(name)
                if len(data) != entry.bytes or sha256(data) != entry.sha256:
                    raise _error("archive")
                expected_kind = "input" if name.startswith("project/") else "report"
                if _entry(data, expected_kind, name) != entry:
                    raise _error("archive")
                files[name] = data
            return plan, files
    except (
        BadZipFile,
        UnicodeDecodeError,
        ValueError,
        RuntimeError,
        EOFError,
        zlib.error,
    ) as error:
        raise _error("archive") from error


def inspect_bundle(raw):
    plan, _ = _read_bundle(raw)
    return {"status": "verified_bytes", "archive_sha256": sha256(raw), "plan": plan.model_dump()}


def replay_bundle(project, raw, output):
    plan, files = _read_bundle(raw)
    if not plan.replayable:
        raise _error("incomplete")
    if plan.tool_version != __version__:
        raise _error("version")
    target = project.path(output)
    if target.exists():
        raise _error("exists")
    target.mkdir(parents=True)
    restored = Project(target)
    for name in plan.selection.inputs:
        restored.write(name, files["project/" + name], exclusive=True)
    with language_context(plan.language):
        baseline = read_snapshot(restored, plan.baseline) if plan.baseline else None
        report = check_stored_project(restored, plan.config_path, baseline)
        config, _ = load_config(restored, plan.config_path)
        actual_scope = _scope(config, report)
        same = _report_identity(report) == plan.report_fingerprint and actual_scope == plan.scope
        report_path = ".paperdelta/replay-report-" + uuid.uuid4().hex
        write_reports(restored, report_path, report)
    return {
        "status": "reproduced" if same else "different_result",
        "same_result": same,
        "check_exit_code": report["exit_code"],
        "exit_code": report["exit_code"] if same else 2,
        "report": f"{output}/{report_path}/report.html",
        "scope": actual_scope,
        "declared_scope": plan.scope,
        "archive_sha256": sha256(raw),
        "executed_project_code": False,
    }
