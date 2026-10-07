"""Current-evidence previews and explicitly accepted Word/PDF annotation copies."""

from __future__ import annotations

import io
import re
from pathlib import PurePosixPath
from typing import Literal
from zipfile import ZIP_DEFLATED, ZipFile

from pydantic import Field

from paperdelta import __version__
from paperdelta.analysis import check_stored_project
from paperdelta.config import load_config
from paperdelta.declarations import observe
from paperdelta.documents import PaperIndex
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import current_language, language_context, tr
from paperdelta.locations import location_label
from paperdelta.models import Hash, Identifier, StrictModel, VersionOne
from paperdelta.native_comments import error, pdf_copy, word_copy
from paperdelta.records import validate_record
from paperdelta.storage import fingerprint, json_text, sha256

MAX_TOTAL = 128 * 1024 * 1024


class AnnotationSelection(StrictModel):
    occurrences: list[Identifier] = Field(min_length=1, max_length=500)


class AnnotationAcceptance(StrictModel):
    preview_id: Hash
    attest: Literal[True]


class AnnotationPlan(StrictModel):
    annotation_schema_version: VersionOne
    tool_version: str
    language: Literal["en", "zh-CN"]
    config_path: str
    selection: AnnotationSelection
    input_hashes: dict[str, Hash | None]
    report_fingerprint: Hash
    entries: list[dict] = Field(max_length=500)
    refused: list[dict] = Field(max_length=500)
    copies: list[dict] = Field(max_length=500)
    notice: str
    preview_id: Hash


def _note(name, state, metric, readable_actual):
    evidence = metric.get("evidence", [])
    # Show declared identity, complete participating row keys and source hashes in
    # the manifest. Comments include a bounded, human-readable summary.
    sources = sorted({item["path"] for item in evidence if "path" in item})
    return "\n".join(
        [
            tr("annotation.note_title", name=name),
            tr("annotation.note_status", status=tr("annotation.status_" + state["status"])),
            tr(
                "annotation.note_actual_scientific"
                if readable_actual != state["actual"]
                else "annotation.note_actual",
                value=readable_actual,
            ),
            tr("annotation.note_expected", value=state.get("expected", "?")),
            tr("annotation.note_metric", metric=state["metric"]),
            tr("annotation.note_evidence", paths=", ".join(sources)),
            tr(
                "annotation.note_claims",
                claims=", ".join((state.get("suggestion") or {}).get("blocked_by", [])) or "—",
            ),
            tr("annotation.note_notice"),
        ]
    )


def _copies(index, entries):
    files = {}
    for entry in entries:
        files.setdefault(entry["location"]["file"], []).append(entry)
    result, refused, copies, metadata = [], [], {}, []
    total = 0
    for number, (name, items) in enumerate(sorted(files.items()), 1):
        document = index.document(name)
        try:
            raw = (word_copy if document.format == "docx" else pdf_copy)(document, items)
        except PaperDeltaError as exc:
            refused.extend(
                {
                    "occurrence": item["occurrence"],
                    "code": exc.code,
                    "reason": exc.message.render()
                    if hasattr(exc.message, "render")
                    else str(exc.message),
                }
                for item in items
            )
            continue
        except (ValueError, KeyError, OSError, TypeError) as exc:
            raise error("structure") from exc
        total += len(raw)
        if len(raw) > 48 * 1024 * 1024 or total > MAX_TOTAL:
            raise error("limit")
        stem = re.sub(r"[^\w.-]", "_", PurePosixPath(name).stem)[:80]
        destination = f"copies/{number:03d}-{stem}.review.{document.format}"
        copies[destination] = raw
        metadata.append({"path": destination, "original": name, "annotations": len(items)})
        result.extend(items)
    return result, refused, copies, metadata


def _prepare(project, selection, config_path):
    selection = validate_record(AnnotationSelection, selection, "ANNOTATION_SELECTION")
    if len(set(selection.occurrences)) != len(selection.occurrences):
        raise error("selection")
    report = check_stored_project(project, config_path)
    config, _ = load_config(project, config_path)
    index = PaperIndex(project, config.paper)
    entries, refused = [], []
    for name in sorted(selection.occurrences):
        state = report["occurrences"].get(name)
        if state is None:
            raise error("selection")
        location = state.get("location")
        if (
            not location
            or location.get("format") not in {"docx", "pdf"}
            or not isinstance(state.get("actual"), str)
        ):
            refused.append(
                {
                    "occurrence": name,
                    "code": "ANNOTATION_POSITION",
                    "reason": tr("annotation.position"),
                }
            )
            continue
        document = index.document(location["file"])
        span = document.locate(config.occurrences[name].anchor)
        if span.to_dict() != location or state.get("actual") != span.text:
            raise error("changed")
        if location["format"] == "docx" and (
            location["locator"].get("part") != "word/document.xml"
            or location["locator"].get("note_id") is not None
        ):
            refused.append(
                {"occurrence": name, "code": "ANNOTATION_PART", "reason": tr("annotation.part")}
            )
            continue
        metric = report["metrics"].get(state["metric"], {})
        note = _note(name, state, metric, document.comparison_text(span))
        if len(note) > 16384:
            raise error("limit")
        entries.append(
            {
                "occurrence": name,
                "status": state["status"],
                "location": location,
                "position": str(location_label(location).render()),
                "actual": state["actual"],
                "expected": state.get("expected"),
                "metric": state["metric"],
                "definition": metric.get("definition"),
                "evidence": metric.get("evidence", []),
                "related_claims": (state.get("suggestion") or {}).get("blocked_by", []),
                "note": note,
            }
        )
    entries, copy_refused, copies, metadata = _copies(index, entries)
    refused.extend(copy_refused)
    if observe(project, report["input_hashes"]) != report["input_hashes"]:
        raise error("changed")
    body = {
        "annotation_schema_version": 1,
        "tool_version": __version__,
        "language": current_language(),
        "config_path": config_path,
        "selection": {"occurrences": sorted(selection.occurrences)},
        "input_hashes": report["input_hashes"],
        "report_fingerprint": fingerprint({k: v for k, v in report.items() if k != "created_at"}),
        "entries": entries,
        "refused": refused,
        "copies": metadata,
        "notice": tr("annotation.notice"),
    }
    return {**body, "preview_id": fingerprint(body)}, copies


def preview_annotations(project, selection, config_path="paperdelta.yaml"):
    return _prepare(project, selection, config_path)[0]


def annotation_bytes(project, value):
    plan = validate_record(AnnotationPlan, value, "ANNOTATION_PLAN")
    if plan.tool_version != __version__:
        raise error("changed")
    with language_context(plan.language):
        fresh, copies = _prepare(project, plan.selection.model_dump(), plan.config_path)
    if fresh != plan.model_dump():
        raise error("changed")
    if not copies:
        raise error("empty")
    manifest = {**fresh, "copies_sha256": {name: sha256(raw) for name, raw in copies.items()}}
    output = io.BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("review.json", json_text(manifest).encode())
        for name, raw in copies.items():
            archive.writestr(name, raw)
    if observe(project, plan.input_hashes) != plan.input_hashes:
        raise error("changed")
    if len(output.getvalue()) > MAX_TOTAL:
        raise error("limit")
    return output.getvalue()
