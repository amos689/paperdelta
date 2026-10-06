"""Read-only, typed proposal stages shared by terminal users and agents."""

from __future__ import annotations

from pydantic import Field

from paperdelta import __version__
from paperdelta.config import load_config
from paperdelta.documents import Document, LocatedText, PaperIndex
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.locations import location_label
from paperdelta.models import (
    Aggregation,
    Anchor,
    ColumnType,
    Config,
    DerivedMetric,
    DerivedOperation,
    Display,
    DisplayKind,
    Hash,
    Source,
    SourceFormat,
    SourceMetric,
    StatisticalContract,
    StatisticalDisplay,
    StrictModel,
    Unit,
    VersionOne,
)
from paperdelta.onboarding import Additions, _merge, propose_bindings, scan_project
from paperdelta.records import validate_record
from paperdelta.sources import EvidenceStore, typed_cell
from paperdelta.storage import Project, fingerprint, sha256


class BindingDraft(StrictModel):
    draft_schema_version: VersionOne
    tool_version: str
    config_path: str
    input_hashes: dict[str, Hash]
    additions: Additions = Field(default_factory=Additions)
    rationale: dict[str, str] = Field(default_factory=dict)
    draft_id: Hash


def _unchanged(project: Project, hashes: dict[str, str]) -> None:
    for path, identity in hashes.items():
        if sha256(project.read(path)) != identity:
            raise PaperDeltaError("STALE_DRAFT", msg("builder.stale", path=path))


def _seal(project: Project, body: dict, hashes: dict | None = None) -> dict:
    value = dict(body)
    value.pop("draft_id", None)
    value["input_hashes"] = {**body["input_hashes"]}
    for path, identity in (hashes or {}).items():
        if path in value["input_hashes"] and value["input_hashes"][path] != identity:
            raise PaperDeltaError("STALE_DRAFT", msg("builder.stale", path=path))
        value["input_hashes"][path] = identity
    _unchanged(project, value["input_hashes"])
    return validate_record(
        BindingDraft, {**value, "draft_id": fingerprint(value)}, "DRAFT_SCHEMA"
    ).model_dump()


def resume_draft(project: Project, value: dict) -> tuple[BindingDraft, Config]:
    draft = validate_record(BindingDraft, value, "DRAFT_SCHEMA")
    if draft.tool_version != __version__ or draft.draft_id != fingerprint(
        draft.model_dump(exclude={"draft_id"})
    ):
        raise PaperDeltaError("DRAFT_IDENTITY", msg("builder.identity"))
    _unchanged(project, draft.input_hashes)
    config, identity = load_config(project, draft.config_path)
    if draft.input_hashes.get(draft.config_path) != identity:
        raise PaperDeltaError("STALE_DRAFT", msg("builder.stale", path=draft.config_path))
    return draft, _merge(config, draft.additions)


def start_draft(project: Project, config_path="paperdelta.yaml") -> dict:
    scan = scan_project(project, config_path)
    return _seal(
        project,
        {
            "draft_schema_version": 1,
            "tool_version": __version__,
            "config_path": config_path,
            "input_hashes": scan["input_hashes"],
            "additions": Additions().model_dump(),
            "rationale": {},
        },
    )


def _new_name(config: Config, group: str, name: str) -> None:
    if name in getattr(config, group):
        raise PaperDeltaError("BINDING_CONFLICT", msg("builder.exists", group=group, name=name))


def add_source(
    project: Project,
    value: dict,
    *,
    name: str,
    path: str,
    format: SourceFormat,
    columns: dict[str, ColumnType] | None = None,
    primary_key: list[str] | None = None,
    sheet: str | None = None,
    cell_range: str | None = None,
) -> dict:
    draft, config = resume_draft(project, value)
    _new_name(config, "sources", name)
    source = validate_record(
        Source,
        {
            "path": project.relative(project.path(path)),
            "format": format,
            "columns": columns or {},
            "primary_key": primary_key or [],
            "sheet": sheet,
            "cell_range": cell_range,
        },
        "DRAFT_SOURCE",
    )
    addition = validate_record(Additions, {"sources": {name: source}}, "DRAFT_SOURCE")
    config = _merge(config, addition)
    store = EvidenceStore(project, config)
    store.load_source(name)  # Verify all declared types and all row identities now.
    body = draft.model_dump()
    body["additions"]["sources"][name] = source.model_dump()
    return _seal(project, body, store.hashes)


def add_metric(
    project: Project,
    value: dict,
    *,
    name: str,
    source: str,
    field: str,
    unit: Unit,
    reduce: Aggregation,
    where: dict[str, str] | None = None,
    expected_count: int | None = None,
    seed_column: str = "seed",
    expected_seeds: list[str] | None = None,
    statistics: dict | None = None,
) -> dict:
    draft, config = resume_draft(project, value)
    _new_name(config, "metrics", name)
    if source not in config.sources:
        raise PaperDeltaError("BUILDER_SELECTION", msg("builder.selection", value=source))
    declaration = config.sources[source]
    where = where or {}
    # Client values are exact strings; declared types determine their meaning.
    if any(not isinstance(item, str) for item in where.values()):
        raise PaperDeltaError("BUILDER_SELECTOR", msg("builder.selector"))
    if any(column not in declaration.columns for column in where):
        raise PaperDeltaError("BUILDER_SELECTION", msg("builder.selection", value=list(where)))
    selection = {
        column: typed_cell(raw, declaration.columns[column], column)
        for column, raw in where.items()
    }
    seeds = None
    if expected_seeds is not None:
        if declaration.columns.get(seed_column) not in {"string", "integer"} or any(
            not isinstance(seed, str) for seed in expected_seeds
        ):
            raise PaperDeltaError("BUILDER_SELECTOR", msg("builder.seeds"))
        seeds = [
            typed_cell(seed, declaration.columns[seed_column], seed_column)
            for seed in expected_seeds
        ]
    if reduce != "unique" and expected_count is None:
        raise PaperDeltaError("BUILDER_EXPECTATION", msg("builder.expectation"))
    metric = validate_record(
        SourceMetric,
        {
            "source": source,
            "field": field,
            "unit": unit,
            "reduce": reduce,
            "where": selection,
            "expected_count": expected_count if expected_count is not None else 1,
            "seed_column": seed_column,
            "expected_seeds": seeds,
            "statistics": validate_record(StatisticalContract, statistics, "DRAFT_STATISTICS")
            if statistics is not None
            else None,
        },
        "DRAFT_METRIC",
    )
    return _add_metric(project, draft, config, name, metric)


def add_derived(
    project: Project,
    value: dict,
    *,
    name: str,
    operation: DerivedOperation,
    left: str,
    right: str,
) -> dict:
    draft, config = resume_draft(project, value)
    _new_name(config, "metrics", name)
    metric = validate_record(
        DerivedMetric, {"op": operation, "args": [left, right]}, "DRAFT_METRIC"
    )
    return _add_metric(project, draft, config, name, metric)


def _add_metric(project, draft, config, name, metric):
    config = _merge(config, validate_record(Additions, {"metrics": {name: metric}}, "DRAFT_METRIC"))
    store = EvidenceStore(project, config)
    store.resolve(name)  # Includes unit arithmetic, expected counts and seed checks.
    body = draft.model_dump()
    body["additions"]["metrics"][name] = metric.model_dump()
    return _seal(project, body, store.hashes)


def anchor_for_span(
    document: Document, span: LocatedText, identity_values=(), display=None
) -> Anchor:
    """Use only the explicitly selected span, never a same-number heuristic.

    Context anchors survive numeric corrections. A contextless boundary or truly
    indistinguishable repetition requires an author edit, not a positional guess.
    """
    from paperdelta.statistical_display import validate_span

    validate_span(document, span, display or Display())
    if hasattr(document, "anchor_for_span"):
        return document.anchor_for_span(span, identity_values, display)
    from paperdelta.tables import anchor_for_cell

    statistical = (
        display.statistics
        if display and display.statistics and display.statistics.compound
        else None
    )
    table_anchor = anchor_for_cell(document, span, identity_values, statistical)
    if table_anchor is not None:
        return table_anchor
    numbers = document.numbers()
    low = max((item.end for item in numbers if item.end <= span.start), default=0)
    high = min(
        (item.start for item in numbers if item.start >= span.end), default=len(document.text)
    )
    # Anchors may not depend on another numeric candidate: a multi-location patch
    # could change that candidate and otherwise invalidate the neighbouring binding.
    for before in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512):
        for after in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512):
            prefix = document.text[max(low, span.start - before) : span.start]
            suffix = document.text[span.end : min(high, span.end + after)]
            if not prefix or not suffix:
                continue
            anchor = Anchor(prefix=prefix, suffix=suffix)
            try:
                found = document.locate(anchor)
            except PaperDeltaError:
                continue
            if (found.start, found.end) == (span.start, span.end):
                return anchor
    raise PaperDeltaError("BUILDER_ANCHOR", msg("builder.anchor", file=span.file, line=span.line))


def candidate_span(document: Document, choice: dict, display: Display) -> LocatedText:
    span = document.span(choice["start"], choice["end"])
    if (
        display.kind == "percent"
        and display.percent_symbol
        and document.text[span.end :].startswith(document.percent_token)
    ):
        span = document.span(span.start, span.end + len(document.percent_token))
    return span


def add_occurrences(
    project: Project,
    value: dict,
    *,
    metric: str,
    candidate_ids: list[str],
    names: list[str],
    display_kind: DisplayKind,
    places: int,
    percent_symbol: bool,
    rationale: str,
    statistics: dict | None = None,
    table_identity: dict | None = None,
) -> dict:
    draft, config = resume_draft(project, value)
    statistical = (
        validate_record(StatisticalDisplay, statistics, "DRAFT_STATISTICS")
        if statistics is not None
        else None
    )
    compound = statistical is not None and statistical.compound
    if (
        not candidate_ids
        or (len(names) != 1 if compound else len(candidate_ids) != len(names))
        or len(set(candidate_ids)) != len(candidate_ids)
        or len(set(names)) != len(names)
        or metric not in config.metrics
    ):
        raise PaperDeltaError("BUILDER_SELECTION", msg("builder.locations"))
    if not rationale.strip():
        raise PaperDeltaError("PROPOSAL_RATIONALE", msg("error.PROPOSAL_RATIONALE"))
    display = validate_record(
        Display,
        {
            "kind": display_kind,
            "places": places,
            "percent_symbol": percent_symbol,
            "statistics": statistical,
        },
        "DRAFT_DISPLAY",
    )
    scan = scan_project(project, draft.config_path)
    paper = PaperIndex(project, config.paper)
    candidates = {item["candidate_id"]: item for item in scan["candidates"]}
    occupied = []
    for existing in config.occurrences.values():
        try:
            occupied.append(paper.document(existing.file).locate(existing.anchor))
        except PaperDeltaError:
            continue
    body = draft.model_dump()
    if not set(candidate_ids).issubset(candidates):
        raise PaperDeltaError("BUILDER_SELECTION", msg("builder.locations"))
    for name, candidate in zip(
        names, candidate_ids[:1] if compound else candidate_ids, strict=True
    ):
        _new_name(config, "occurrences", name)
        if candidate not in candidates:
            raise PaperDeltaError("BUILDER_SELECTION", msg("builder.selection", value=candidate))
        choice = candidates[candidate]
        document = paper.document(choice["file"])
        if compound:
            from paperdelta.statistical_display import compound_span

            span = compound_span(document, [candidates[item] for item in candidate_ids], display)
        else:
            span = candidate_span(document, choice, display)
        if any(
            other.file == span.file and other.start < span.end and span.start < other.end
            for other in occupied
        ):
            raise PaperDeltaError(
                "BUILDER_OVERLAP", msg("document.overlap", location=location_label(span.to_dict()))
            )
        occupied.append(span)
        definition = config.metrics[metric]
        identity_values = (
            {str(value) for value in definition.where.values()}
            if isinstance(definition, SourceMetric)
            else ()
        )
        if table_identity is None:
            anchor = anchor_for_span(document, span, identity_values, display)
        else:
            from paperdelta.models import ReviewedTableIdentity
            from paperdelta.tables import reviewed_table_anchor

            identity = validate_record(ReviewedTableIdentity, table_identity, "TABLE_IDENTITY")
            anchor = reviewed_table_anchor(
                document, span, identity, statistical if compound else None
            )
        body["additions"]["occurrences"][name] = {
            "file": span.file,
            "anchor": anchor.model_dump(),
            "metric": metric,
            "display": display.model_dump(),
        }
        body["rationale"]["occurrences:" + name] = rationale
    sealed = _seal(project, body, scan["input_hashes"])
    # A stage with positions is already a real, inspectable proposal. This rejects
    # unsupported locations/display combinations without accepting anything.
    finalize_draft(project, sealed)
    return sealed


def inspect_draft(project: Project, value: dict) -> dict:
    draft, config = resume_draft(project, value)
    store = EvidenceStore(project, config)
    metrics = {}
    for name in draft.additions.metrics:
        metrics[name] = store.resolve(name).to_dict()
    _unchanged(project, draft.input_hashes)
    stages = ["source"]
    if config.sources:
        stages.append("metric")
    if config.metrics:
        stages.extend(["derived", "locations"])
    if draft.additions.occurrences or draft.additions.claims or draft.additions.figures:
        stages.append("finish")
    return {
        "available_stages": stages,
        "available_sources": list(config.sources),
        "available_metrics": list(config.metrics),
        "draft_id": draft.draft_id,
        "metrics": metrics,
        "rationale": draft.rationale,
        "additions": draft.additions.model_dump(),
    }


def finalize_draft(project: Project, value: dict) -> dict:
    draft, _ = resume_draft(project, value)
    result = propose_bindings(
        project,
        draft.additions.model_dump(),
        draft.rationale,
        config_path=draft.config_path,
    )
    _unchanged(project, draft.input_hashes)
    # Retain discovery identities as well as the narrower final proposal identities
    # until construction finishes. Acceptance then uses the usual proposal contract.
    return result
