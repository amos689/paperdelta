"""Read-only discovery and explicit acceptance of evidence-backed mapping proposals."""

from __future__ import annotations

import csv
import io
import re
import uuid
from collections import Counter
from pathlib import Path

from pydantic import Field

from paperdelta import __version__
from paperdelta.analysis import check_configuration
from paperdelta.config import config_text, load_config
from paperdelta.errors import PaperDeltaError, error_message
from paperdelta.i18n import msg
from paperdelta.latex import PaperIndex
from paperdelta.models import (
    Claim,
    Config,
    DerivedMetric,
    Figure,
    Hash,
    Identifier,
    Occurrence,
    Paper,
    Source,
    SourceMetric,
    StrictModel,
    VersionOne,
)
from paperdelta.patches import _write_lock
from paperdelta.records import validate_record
from paperdelta.storage import Project, fingerprint, json_text, parse_json, sha256


class Additions(StrictModel):
    sources: dict[Identifier, Source] = Field(default_factory=dict)
    metrics: dict[Identifier, SourceMetric | DerivedMetric] = Field(default_factory=dict)
    occurrences: dict[Identifier, Occurrence] = Field(default_factory=dict)
    claims: dict[Identifier, Claim] = Field(default_factory=dict)
    figures: dict[Identifier, Figure] = Field(default_factory=dict)


class Proposal(StrictModel):
    proposal_schema_version: VersionOne
    tool_version: str
    config_path: str
    input_hashes: dict[str, Hash]
    additions: Additions
    rationale: dict[str, str]
    proposal_id: Hash


class ProposalInput(StrictModel):
    additions: Additions
    rationale: dict[str, str]


class OnboardingInputs(StrictModel):
    schema_version: VersionOne
    data: list[str]


def _source_summary(project: Project, path: str) -> tuple[dict, str]:
    text, raw = project.text(path)
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        try:
            reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
            headers = reader.fieldnames
            if not headers or len(set(headers)) != len(headers):
                raise PaperDeltaError("CSV_HEADER", msg("error.CSV_HEADER", path=path))
            sample = []
            count = 0
            for row in reader:
                if None in row or any(value is None for value in row.values()):
                    raise PaperDeltaError(
                        "CSV_ROW", msg("error.CSV_ROW", path=path, value2=reader.line_num)
                    )
                count += 1
                if len(sample) < 5:
                    sample.append(row)
            # Raw text deliberately preserves identities such as model '001'.
            result = {
                "path": path,
                "format": "csv",
                "columns": headers,
                "record_count": count,
                "sample": sample,
                "needs_confirmation": ["column types", "primary key", "units", "scope"],
            }
        except csv.Error as exc:
            raise PaperDeltaError("INVALID_CSV", error_message(exc)) from exc
    elif suffix == ".json":
        value = parse_json(text)
        leaves = []

        def walk(item, pointer, depth=0):
            if len(leaves) >= 50 or depth >= 30:
                return
            if isinstance(item, dict):
                for key, child in item.items():
                    walk(
                        child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"), depth + 1
                    )
                    if len(leaves) >= 50:
                        break
            elif isinstance(item, list):
                for index, child in enumerate(item):
                    walk(child, pointer + f"/{index}", depth + 1)
                    if len(leaves) >= 50:
                        break
            else:
                leaves.append({"pointer": pointer, "value": item})

        walk(value, "")
        result = {
            "path": path,
            "format": "json",
            "sample": leaves,
            "sample_limit": 50,
            "needs_confirmation": ["units", "experiment identity"],
        }
    else:
        raise PaperDeltaError("SOURCE_FORMAT", msg("error.SOURCE_FORMAT"))
    return result, sha256(raw)


def init_project(
    project: Project,
    paper: str,
    data: list[str],
    *,
    config_path="paperdelta.yaml",
    macros: dict[str, int] | None = None,
) -> dict:
    config = Config(schema_version=1, paper=Paper(entry=paper, macros=macros or {}))
    PaperIndex(project, config.paper)
    for path in data:
        _source_summary(project, path)
    hints = ".paperdelta/onboarding.json"
    if project.path(config_path).exists() or project.path(hints).exists():
        raise PaperDeltaError("ALREADY_EXISTS", msg("error.ALREADY_EXISTS"))
    # These paths are discovery hints, not accepted evidence declarations.
    project.write(
        hints, json_text({"schema_version": 1, "data": data}).encode("utf-8"), exclusive=True
    )
    project.write(config_path, config_text(config).encode("utf-8"), exclusive=True)
    return {
        "config_path": config_path,
        "confirmed": 0,
        "next": "scan, propose, then explicitly bind",
    }


def scan_project(
    project: Project, config_path="paperdelta.yaml", data: list[str] | None = None
) -> dict:
    config, config_hash = load_config(project, config_path)
    paper = PaperIndex(project, config.paper)
    hashes = {config_path: config_hash, **{file: doc.hash for file, doc in paper.documents.items()}}
    paths = set(data or []) | {source.path for source in config.sources.values()}
    hints_path = ".paperdelta/onboarding.json"
    if project.path(hints_path).exists():
        text, raw = project.text(hints_path, 64 * 1024)
        hints = validate_record(OnboardingInputs, parse_json(text), "ONBOARDING_SCHEMA")
        paths.update(hints.data)
        hashes[hints_path] = sha256(raw)
    sources, issues = [], list(paper.issues)
    for path in sorted(paths):
        try:
            summary, identity = _source_summary(project, path)
            sources.append(summary)
            hashes[path] = identity
        except PaperDeltaError as exc:
            issues.append({"code": exc.code, "file": path, "message": str(exc)})
    spans = [span for doc in paper.documents.values() for span in doc.numbers()]
    counts = Counter(span.text for span in spans)
    candidates = []
    for span in spans:
        doc = paper.documents[span.file]
        regions = {
            kind
            for start, end, kind in doc.priority_regions
            if start <= span.start and span.end <= end
        }
        candidates.append(
            {
                **span.to_dict(),
                "candidate_id": fingerprint(span.to_dict()),
                "context_before": doc.text[max(0, span.start - 90) : span.start],
                "context_after": doc.text[span.end : span.end + 90],
                "same_text_count": counts[span.text],
                "priority_hint": "abstract"
                if "abstract" in regions or "abstract" in span.file.lower()
                else "table"
                if "table" in regions
                else "repeated"
                if counts[span.text] > 1
                else "body",
            }
        )
    candidates.sort(
        key=lambda item: (
            {"abstract": 0, "table": 1, "repeated": 2, "body": 3}[item["priority_hint"]],
            item["file"],
            item["byte_start"],
        )
    )
    return {
        "scan_schema_version": 1,
        "config_path": config_path,
        "input_hashes": hashes,
        "sources": sources,
        "candidates": candidates,
        "unsupported": issues,
        "confirmed": {
            group: list(getattr(config, group)) for group in ("occurrences", "claims", "figures")
        },
        "notice": msg("notice.onboarding"),
    }


def _merge(config: Config, additions: Additions) -> Config:
    value = config.model_dump()
    for group, entries in additions.model_dump().items():
        duplicates = set(value[group]) & set(entries)
        if duplicates:
            raise PaperDeltaError(
                "BINDING_CONFLICT",
                msg("error.BINDING_CONFLICT", group=group, value2=sorted(duplicates)),
            )
        value[group].update(entries)
    if any(
        item["anchor"].get("table")
        for group in ("occurrences", "claims")
        for item in value[group].values()
    ):
        value["schema_version"] = 2
    return validate_record(Config, value, "PROPOSAL_CONFIG")


def _binding_ids(additions: Additions) -> list[str]:
    return [
        f"{group}:{name}"
        for group in ("occurrences", "claims", "figures")
        for name in getattr(additions, group)
    ]


def _check_additions(project, config, config_path, config_hash, additions):
    merged = _merge(config, additions)
    report = check_configuration(project, merged, config_path, config_hash)
    for binding in _binding_ids(additions):
        group, name = binding.split(":", 1)
        if report[group].get(name, {}).get("status") not in {"pass", "mismatch"}:
            raise PaperDeltaError(
                "PROPOSAL_UNRESOLVED",
                msg("error.PROPOSAL_UNRESOLVED", binding=binding),
            )
    return merged, report


def propose_bindings(
    project: Project,
    additions: dict,
    rationale: dict[str, str],
    *,
    config_path="paperdelta.yaml",
) -> dict:
    draft = validate_record(
        ProposalInput, {"additions": additions, "rationale": rationale}, "PROPOSAL_SCHEMA"
    )
    changes, rationale = draft.additions, draft.rationale
    bindings = _binding_ids(changes)
    if (
        not bindings
        or set(rationale) != set(bindings)
        or any(not text.strip() for text in rationale.values())
    ):
        raise PaperDeltaError("PROPOSAL_RATIONALE", msg("error.PROPOSAL_RATIONALE"))
    config, config_hash = load_config(project, config_path)
    _, report = _check_additions(project, config, config_path, config_hash, changes)
    body = {
        "proposal_schema_version": 1,
        "tool_version": __version__,
        "config_path": config_path,
        "input_hashes": report["input_hashes"],
        "additions": changes.model_dump(),
        "rationale": rationale,
    }
    proposal = validate_record(
        Proposal, {**body, "proposal_id": fingerprint(body)}, "PROPOSAL_SCHEMA"
    )
    return proposal.model_dump()


def inspect_proposal(project: Project, value: dict) -> tuple[Proposal, Config, dict]:
    proposal = validate_record(Proposal, value, "PROPOSAL_SCHEMA")
    if (
        proposal.proposal_id != fingerprint(proposal.model_dump(exclude={"proposal_id"}))
        or proposal.tool_version != __version__
    ):
        raise PaperDeltaError("PROPOSAL_IDENTITY", msg("error.PROPOSAL_IDENTITY"))
    config, config_hash = load_config(project, proposal.config_path)
    if config_hash != proposal.input_hashes.get(proposal.config_path):
        raise PaperDeltaError("STALE_PROPOSAL", msg("error.STALE_PROPOSAL"))
    merged, report = _check_additions(
        project, config, proposal.config_path, config_hash, proposal.additions
    )
    if report["input_hashes"] != proposal.input_hashes:
        raise PaperDeltaError("STALE_PROPOSAL", msg("error.STALE_PROPOSAL.2"))
    return proposal, merged, report


def accept_bindings(project: Project, value: dict, selected: list[str]) -> dict:
    if not selected or len(set(selected)) != len(selected):
        raise PaperDeltaError("BINDING_SELECTION", msg("error.BINDING_SELECTION"))
    with _write_lock(project):
        proposal, _, _ = inspect_proposal(project, value)
        if not set(selected).issubset(_binding_ids(proposal.additions)):
            raise PaperDeltaError("BINDING_SELECTION", msg("error.BINDING_SELECTION.2"))
        additions = proposal.additions.model_dump()
        chosen = {group: {} for group in additions}
        required = set()
        for binding in selected:
            group, name = binding.split(":", 1)
            chosen[group][name] = additions[group][name]
            if group == "occurrences":
                required.add(additions[group][name]["metric"])
            elif group == "claims":
                predicate = additions[group][name]["predicate"]
                required.update([predicate["left"], *predicate["candidates"]])
                if isinstance(predicate["right"], str):
                    required.add(predicate["right"])
        while required:
            name = required.pop()
            if name in chosen["metrics"] or name not in additions["metrics"]:
                continue
            metric = additions["metrics"][name]
            chosen["metrics"][name] = metric
            if "args" in metric:
                required.update(metric["args"])
            elif metric["source"] in additions["sources"]:
                source = metric["source"]
                chosen["sources"][source] = additions["sources"][source]
        config, config_hash = load_config(project, proposal.config_path)
        merged, report = _check_additions(
            project, config, proposal.config_path, config_hash, Additions.model_validate(chosen)
        )
        for path, identity in proposal.input_hashes.items():
            if sha256(project.read(path)) != identity:
                raise PaperDeltaError("STALE_PROPOSAL", msg("error.STALE_PROPOSAL.3", path=path))
        backup = f".paperdelta/config-backups/{uuid.uuid4().hex}.yaml"
        project.write(backup, project.read(proposal.config_path), exclusive=True)
        project.write(proposal.config_path, config_text(merged).encode("utf-8"))
        return {
            "status": "accepted",
            "bindings": selected,
            "backup": backup,
            "consistency_exit_code_before_acceptance": report["exit_code"],
        }


def parse_macros(values: list[str]) -> dict[str, int]:
    macros = {}
    for value in values:
        if not re.fullmatch(r"[A-Za-z]+=[0-9]", value):
            raise PaperDeltaError("MACRO_DECLARATION", msg("error.MACRO_DECLARATION"))
        name, arity = value.split("=")
        if name in macros:
            raise PaperDeltaError("MACRO_DECLARATION", msg("error.MACRO_DECLARATION.2", name=name))
        macros[name] = int(arity)
    return macros
