"""Explicit, re-derived repairs of paper locations, preserving scientific definitions."""

from __future__ import annotations

import uuid
from typing import Annotated

from pydantic import Field

from paperdelta import __version__
from paperdelta.analysis import check_configuration, check_project
from paperdelta.builder import anchor_for_span, candidate_span
from paperdelta.config import config_text, load_config
from paperdelta.documents import PaperIndex
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg, tr, translated
from paperdelta.i18n import translated as translate_location
from paperdelta.locations import location_label
from paperdelta.models import Anchor, Config, Hash, StrictModel, VersionOne
from paperdelta.onboarding import scan_project
from paperdelta.patches import _write_lock
from paperdelta.records import Snapshot, validate_record
from paperdelta.snapshots import snapshot_path
from paperdelta.storage import Project, fingerprint, parse_json, sha256


class RepairSelection(StrictModel):
    binding: str
    candidate_id: Hash | None = None
    file: str | None = None
    anchor: Anchor | None = None
    rationale: str = Field(min_length=1, max_length=4000)


class RepairProposal(StrictModel):
    repair_schema_version: VersionOne
    tool_version: str
    config_path: str
    baseline: str | None = None
    input_hashes: dict[str, Hash]
    selections: Annotated[list[RepairSelection], Field(min_length=1)]
    repair_id: Hash


def _history(project, baseline):
    if baseline is None:
        return None, {}
    path = snapshot_path(baseline)
    text, raw = project.text(path)
    snapshot = validate_record(Snapshot, parse_json(text), "BASELINE_SCHEMA")
    return snapshot.report.model_dump(), {path: sha256(raw)}


def _binding(config, identity):
    group, _, name = identity.partition(":")
    if group not in {"occurrences", "claims"} or name not in getattr(config, group):
        raise PaperDeltaError("REPAIR_SELECTION", msg("repair.binding", binding=identity))
    return group, name, getattr(config, group)[name]


def _current_inputs(project, config, config_path, config_hash, baseline):
    history, hashes = _history(project, baseline)
    scan = scan_project(project, config_path)
    report = check_configuration(project, config, config_path, config_hash)
    for inputs in (scan["input_hashes"], report["input_hashes"]):
        for path, identity in inputs.items():
            if path in hashes and hashes[path] != identity:
                raise PaperDeltaError("STALE_REPAIR", msg("repair.stale", path=path))
            hashes[path] = identity
    _unchanged(project, hashes)
    return history, scan, report, hashes


def _unchanged(project, hashes):
    for path, identity in hashes.items():
        if sha256(project.read(path)) != identity:
            raise PaperDeltaError("STALE_REPAIR", msg("repair.stale", path=path))


def scan_repairs(project: Project, config_path="paperdelta.yaml", baseline=None):
    config, identity = load_config(project, config_path)
    history, scan, report, hashes = _current_inputs(
        project, config, config_path, identity, baseline
    )
    paper = PaperIndex(project, config.paper)
    broken = []
    for group in ("occurrences", "claims"):
        for name, binding in getattr(config, group).items():
            try:
                document = paper.document(binding.file)
                span = document.locate(binding.anchor)
                if group == "occurrences":
                    document.validate_numeric_span(span)
            except PaperDeltaError as error:
                broken.append(
                    {
                        "binding": f"{group}:{name}",
                        "reason": error.code,
                        "message": error.message,
                        "old_definition": binding.model_dump(),
                        "previous_location": (history or {})
                        .get(group, {})
                        .get(name, {})
                        .get("location"),
                    }
                )
    _unchanged(project, hashes)
    return {
        "repair_scan_version": 1,
        "input_hashes": hashes,
        "broken": broken,
        "candidates": scan["candidates"],
        "files": list(paper.documents),
        "diagnostics": report["diagnostics"],
        "notice": msg("repair.notice"),
    }


def _derive(project, selections, config_path, baseline):
    config, identity = load_config(project, config_path)
    history, scan, _, hashes = _current_inputs(project, config, config_path, identity, baseline)
    if not selections or len({item.binding for item in selections}) != len(selections):
        raise PaperDeltaError("REPAIR_SELECTION", msg("repair.distinct"))
    paper = PaperIndex(project, config.paper)
    candidates = {item["candidate_id"]: item for item in scan["candidates"]}
    merged = config.model_dump()
    changes = []
    occupied = []
    selected = {item.binding for item in selections}
    for name, original in config.occurrences.items():
        if f"occurrences:{name}" not in selected:
            try:
                occupied.append(paper.document(original.file).locate(original.anchor))
            except PaperDeltaError:
                continue
    for selection in selections:
        group, name, before = _binding(config, selection.binding)
        if not selection.rationale.strip():
            raise PaperDeltaError("REPAIR_SELECTION", msg("repair.rationale"))
        if group == "occurrences":
            if (
                selection.file is not None
                or selection.anchor is not None
                or selection.candidate_id not in candidates
            ):
                raise PaperDeltaError("REPAIR_SELECTION", msg("repair.numeric"))
            candidate = candidates[selection.candidate_id]
            document = paper.document(candidate["file"])
            span = candidate_span(document, candidate, before.display)
            if any(
                item.file == span.file and item.start < span.end and span.start < item.end
                for item in occupied
            ):
                raise PaperDeltaError(
                    "BUILDER_OVERLAP",
                    msg("document.overlap", location=location_label(span.to_dict())),
                )
            occupied.append(span)
            anchor = anchor_for_span(document, span)
        else:
            if (
                selection.candidate_id is not None
                or selection.file is None
                or selection.anchor is None
            ):
                raise PaperDeltaError("REPAIR_SELECTION", msg("repair.claim"))
            document = paper.document(selection.file)
            span = document.locate(selection.anchor)
            anchor = selection.anchor
        after = {**before.model_dump(), "file": span.file, "anchor": anchor.model_dump()}
        if before.model_dump() == after:
            raise PaperDeltaError(
                "REPAIR_SELECTION", msg("repair.no_change", binding=selection.binding)
            )
        merged[group][name] = after
        changes.append(
            {
                "binding": selection.binding,
                "before": before.model_dump(),
                "after": after,
                "previous_location": (history or {}).get(group, {}).get(name, {}).get("location"),
                "current_location": span.to_dict(),
                "current_context": document.text[max(0, span.start - 90) : span.end + 90],
                "rationale": selection.rationale,
            }
        )
    new_config = validate_record(Config, merged, "REPAIR_CONFIG")
    preview = check_configuration(project, new_config, config_path, identity)
    for selection in selections:
        group, name, _ = _binding(config, selection.binding)
        if preview[group][name]["status"] == "unknown":
            raise PaperDeltaError(
                "REPAIR_UNRESOLVED", msg("repair.unresolved", binding=selection.binding)
            )
    if any(hashes.get(path, value) != value for path, value in preview["input_hashes"].items()):
        raise PaperDeltaError("STALE_REPAIR", msg("repair.stale", path=config_path))
    hashes.update(preview["input_hashes"])
    _unchanged(project, hashes)
    return new_config, changes, preview, hashes


def propose_repairs(
    project: Project, selections: list[dict], *, config_path="paperdelta.yaml", baseline=None
):
    choices = [validate_record(RepairSelection, item, "REPAIR_SCHEMA") for item in selections]
    _, _, _, hashes = _derive(project, choices, config_path, baseline)
    body = {
        "repair_schema_version": 1,
        "tool_version": __version__,
        "config_path": config_path,
        "baseline": baseline,
        "input_hashes": hashes,
        "selections": [item.model_dump() for item in choices],
    }
    return validate_record(
        RepairProposal, {**body, "repair_id": fingerprint(body)}, "REPAIR_SCHEMA"
    ).model_dump()


def inspect_repair(project, value):
    proposal = validate_record(RepairProposal, value, "REPAIR_SCHEMA")
    if proposal.tool_version != __version__ or proposal.repair_id != fingerprint(
        proposal.model_dump(exclude={"repair_id"})
    ):
        raise PaperDeltaError("REPAIR_IDENTITY", msg("repair.identity"))
    _unchanged(project, proposal.input_hashes)
    merged, changes, preview, hashes = _derive(
        project, proposal.selections, proposal.config_path, proposal.baseline
    )
    if hashes != proposal.input_hashes:
        raise PaperDeltaError("STALE_REPAIR", msg("repair.stale", path=proposal.config_path))
    return (
        proposal,
        merged,
        {
            "status": "proposed",
            "repair_id": proposal.repair_id,
            "changes": changes,
            "preview": preview,
        },
    )


def accept_repairs(project: Project, value: dict, selected: list[str]):
    if not selected or len(set(selected)) != len(selected):
        raise PaperDeltaError("REPAIR_SELECTION", msg("repair.distinct"))
    # Reject invalid/stale requests before even creating the coordination file.
    # Repeat the check under the write lock to close concurrent writer races.
    proposal, _, _ = inspect_repair(project, value)
    if not set(selected).issubset(item.binding for item in proposal.selections):
        raise PaperDeltaError("REPAIR_SELECTION", msg("repair.distinct"))
    with _write_lock(project):
        proposal, _, _ = inspect_repair(project, value)
        if not set(selected).issubset(item.binding for item in proposal.selections):
            raise PaperDeltaError("REPAIR_SELECTION", msg("repair.distinct"))
        choices = [item for item in proposal.selections if item.binding in selected]
        merged, _, preview, _ = _derive(project, choices, proposal.config_path, proposal.baseline)
        _unchanged(project, proposal.input_hashes)
        backup = f".paperdelta/config-backups/{uuid.uuid4().hex}.yaml"
        project.write(backup, project.read(proposal.config_path), exclusive=True)
        project.write(proposal.config_path, config_text(merged).encode("utf-8"))
        return {
            "status": "accepted",
            "bindings": selected,
            "backup": backup,
            "repair_id": proposal.repair_id,
            "consistency_exit_code_before_acceptance": preview["exit_code"],
            "report": check_project(project.root, proposal.config_path),
        }


def repair_text(result):
    from paperdelta.interactive import _safe

    lines = [tr("repair.title")]
    for item in result.get("broken", []):
        lines.append(f"{item['binding']}: {_safe(translated(item['message']))}")
    for change in result.get("changes", []):
        lines.append(f"{change['binding']}: {change['before']['file']} → {change['after']['file']}")
        lines.append(tr("repair.old", context=change["before"]["anchor"]))
        if change["previous_location"]:
            lines.append(tr("repair.previous", text=change["previous_location"]["text"]))
        lines.append(tr("repair.new", context=change["current_context"]))
        lines.append(tr("repair.reason", rationale=change["rationale"]))
    return "\n".join(_safe(line) for line in lines) + "\n"


def confirm_repairs(project, value, *, input_stream, output):
    from paperdelta.interactive import _answer, _show

    if not input_stream.isatty() or not output.isatty():
        raise PaperDeltaError("INTERACTIVE_TERMINAL", msg("error.INTERACTIVE_TERMINAL"))
    _, _, result = inspect_repair(project, value)
    output.write(repair_text(result))
    selected = []
    try:
        for change in result["changes"]:
            _show(output, tr("repair.selection"), change["binding"])
            if _answer(input_stream, output, tr("repair.select_prompt")) in {"y", "yes", "是"}:
                selected.append(change["binding"])
        if not selected or _answer(input_stream, output, tr("interactive.prompt.1")) not in {
            "accept",
            "确认",
        }:
            return {"status": "cancelled", "bindings": []}
    except (EOFError, KeyboardInterrupt):
        return {"status": "cancelled", "bindings": []}
    return accept_repairs(project, value, selected)


def guide_repairs(project, config_path, baseline, *, input_stream, output):
    from paperdelta.guided import Questions
    from paperdelta.interactive import _show

    if not input_stream.isatty() or not output.isatty():
        raise PaperDeltaError("INTERACTIVE_TERMINAL", msg("error.INTERACTIVE_TERMINAL"))
    scan = scan_repairs(project, config_path, baseline)
    output.write(tr("repair.notice") + "\n")
    if not scan["broken"]:
        output.write(tr("repair.none") + "\n")
        return {"status": "unchanged", "bindings": []}
    questions = Questions(input_stream, output)
    choices = []
    try:
        selected = questions.many(
            "repair.choose",
            [(item, item["binding"] + " · " + item["reason"]) for item in scan["broken"]],
        )
        for item in selected:
            _show(output, tr("repair.selection"), item["binding"])
            _show(output, tr("repair.old_definition"), item["old_definition"])
            _show(output, tr("repair.previous_location"), item["previous_location"])
            choice = {"binding": item["binding"]}
            if item["binding"].startswith("occurrences:"):
                if not scan["candidates"]:
                    raise PaperDeltaError("REPAIR_SELECTION", msg("guide.no_candidates"))
                choice["candidate_id"] = questions.choose(
                    "guide.locations",
                    [
                        (
                            candidate["candidate_id"],
                            f"{translate_location(location_label(candidate))} · "
                            f"{candidate['context_before']} ⟦{candidate['text']}⟧"
                            f"{candidate['context_after']}",
                        )
                        for candidate in scan["candidates"]
                    ],
                )
            else:
                choice["file"] = questions.choose(
                    "repair.file", [(file, file) for file in scan["files"]]
                )
                choice["anchor"] = {"exact": questions.read("repair.exact", required=True)}
            choice["rationale"] = questions.read("guide.rationale", required=True)
            choices.append(choice)
        _unchanged(project, scan["input_hashes"])
        proposal = propose_repairs(project, choices, config_path=config_path, baseline=baseline)
    except (EOFError, KeyboardInterrupt):
        output.write(tr("guide.cancelled") + "\n")
        return {"status": "cancelled", "bindings": []}
    return confirm_repairs(project, proposal, input_stream=input_stream, output=output)
