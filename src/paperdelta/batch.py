"""Evidence-first batch candidates shared by terminal and agent workflows."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import Field, model_validator

from paperdelta import builder
from paperdelta.errors import PaperDeltaError, validation_error
from paperdelta.i18n import msg
from paperdelta.latex import PaperIndex
from paperdelta.models import (
    Aggregation,
    Display,
    Hash,
    SourceMetric,
    StrictModel,
    Unit,
    VersionOne,
)
from paperdelta.onboarding import scan_project
from paperdelta.records import validate_record
from paperdelta.sources import EvidenceStore, typed_cell
from paperdelta.storage import fingerprint


class BatchRequest(StrictModel):
    source: str
    fields: Annotated[list[str], Field(min_length=1, max_length=30)]
    group_by: Annotated[list[str], Field(min_length=1, max_length=12)]
    where: dict[str, str] = Field(default_factory=dict)
    unit: Unit
    reduce: Aggregation
    expected_count: Annotated[int, Field(ge=1, le=10000)]
    seed_column: str = "seed"
    expected_seeds: list[str] | None = None
    display: Display = Field(default_factory=Display)

    @model_validator(mode="after")
    def explicit_selection(self):
        if len(set(self.fields)) != len(self.fields) or len(set(self.group_by)) != len(
            self.group_by
        ):
            raise validation_error(msg("batch.duplicates"))
        if set(self.group_by) & set(self.where):
            raise validation_error(msg("batch.group_filter"))
        if self.reduce == "unique" and self.expected_count != 1:
            raise validation_error(msg("batch.unique"))
        return self


class BatchCatalog(StrictModel):
    batch_schema_version: VersionOne
    draft: builder.BindingDraft
    request: BatchRequest
    catalog_id: Hash


class BatchSelection(StrictModel):
    choice_id: Hash
    candidate_ids: Annotated[list[Hash], Field(min_length=1, max_length=100)]
    rationale: str = Field(min_length=1, max_length=4000)
    display: Display | None = None


def create_catalog(project, draft, request):
    request = validate_record(BatchRequest, request, "BATCH_REQUEST")
    builder.resume_draft(project, draft)
    body = {"batch_schema_version": 1, "draft": draft, "request": request.model_dump()}
    catalog = validate_record(
        BatchCatalog, {**body, "catalog_id": fingerprint(body)}, "BATCH_CATALOG"
    ).model_dump()
    inspect_catalog(project, catalog)
    return catalog


def _plain(text):
    text = re.sub(r"\\[A-Za-z]+\*?", " ", text)
    return re.sub(r"[{}$\\]", " ", text).casefold()


def _contains(text, value):
    return bool(re.search(r"(?<![\w.])" + re.escape(str(value).casefold()) + r"(?![\w.])", text))


def _cells(text, offset):
    cells = []
    depth, start = 0, 0
    for index, char in enumerate(text):
        if index and text[index - 1] == "\\":
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif char == "&" and depth == 0:
            cells.append((offset + start, offset + index, text[start:index]))
            start = index + 1
    cells.append((offset + start, offset + len(text), text[start:]))
    return cells


def _location_context(document, candidate):
    start, end = candidate["start"], candidate["end"]
    regions = [
        (low, high)
        for low, high, kind in document.priority_regions
        if kind == "table" and low <= start and end <= high
    ]
    separator = document.text.rfind("\n\n", 0, start)
    paragraph_start = separator + 2 if separator >= 0 else 0
    paragraph_end = document.text.find("\n\n", end)
    context = (
        document.text[paragraph_start:start]
        + "[value]"
        + document.text[end : paragraph_end if paragraph_end >= 0 else len(document.text)]
    )
    if not regions:
        return {"row": context[:2000], "column_header": "", "kind": "text"}
    low, high = min(regions, key=lambda span: span[1] - span[0])
    rows, cursor = [], low
    for separator in re.finditer(r"(?<!\\)\\\\(?:\[[^\]]*\])?", document.text[low:high]):
        stop = low + separator.start()
        rows.append(_cells(document.text[cursor:stop], cursor))
        cursor = low + separator.end()
    rows.append(_cells(document.text[cursor:high], cursor))
    column = next(
        (
            (row_index, col)
            for row_index, row in enumerate(rows)
            for col, (a, b, _) in enumerate(row)
            if a <= start and end <= b
        ),
        None,
    )
    if column is None:
        return {"row": context[:2000], "column_header": "", "kind": "text"}
    row_index, col = column
    # Only rows preceding all numeric result rows can supply column labels.
    numbers = document.numbers()
    headers = []
    for row in rows[:row_index]:
        if any(row[0][0] <= number.start < row[-1][1] for number in numbers):
            break
        if col < len(row):
            headers.append(row[col][2])
    row = " & ".join(
        text[: start - a] + "[value]" + text[end - a :] if a <= start and end <= b else text
        for a, b, text in rows[row_index]
    )
    return {"row": row[:2000], "column_header": " ".join(headers)[-500:], "kind": "table"}


def inspect_catalog(project, value):
    catalog = validate_record(BatchCatalog, value, "BATCH_CATALOG")
    if catalog.catalog_id != fingerprint(catalog.model_dump(exclude={"catalog_id"})):
        raise PaperDeltaError("BATCH_IDENTITY", msg("batch.identity"))
    draft, config = builder.resume_draft(project, catalog.draft.model_dump())
    request = catalog.request
    if request.source not in config.sources:
        raise PaperDeltaError("BATCH_SOURCE", msg("batch.source", source=request.source))
    source = config.sources[request.source]
    if source.format != "csv":
        raise PaperDeltaError("BATCH_FORMAT", msg("batch.csv"))
    if not set([*request.fields, *request.group_by, *request.where]).issubset(source.columns):
        raise PaperDeltaError(
            "BATCH_COLUMNS", msg("batch.columns", columns=", ".join(source.columns))
        )
    store = EvidenceStore(project, config)
    data = store.load_source(request.source)
    where = {key: typed_cell(raw, source.columns[key], key) for key, raw in request.where.items()}
    selected = store._select_csv(request.source, data, where)
    if not selected:
        raise PaperDeltaError("EMPTY_SELECTION", msg("error.EMPTY_SELECTION"))
    groups = {}
    for row in selected:
        identity = {key: row["values"][key] for key in request.group_by}
        groups[fingerprint(identity)] = identity
        if len(groups) * len(request.fields) > 1000:
            raise PaperDeltaError("BATCH_LIMIT", msg("batch.limit"))
    scan = scan_project(project, draft.config_path)
    paper = PaperIndex(project, config.paper)
    occupied = []
    for occurrence in config.occurrences.values():
        try:
            occupied.append(paper.document(occurrence.file).locate(occurrence.anchor))
        except PaperDeltaError:
            continue
    locations = []
    for item in scan["candidates"]:
        if any(
            other.file == item["file"] and other.start < item["end"] and item["start"] < other.end
            for other in occupied
        ):
            continue
        locations.append({**item, **_location_context(paper.documents[item["file"]], item)})
    seeds = None
    if request.expected_seeds is not None:
        if source.columns.get(request.seed_column) not in {"string", "integer"}:
            raise PaperDeltaError("BUILDER_SELECTOR", msg("builder.seeds"))
        seeds = [
            typed_cell(raw, source.columns[request.seed_column], request.seed_column)
            for raw in request.expected_seeds
        ]
    choices = []
    for identity in groups.values():
        selection = {**where, **identity}
        for field in request.fields:
            metric = validate_record(
                SourceMetric,
                {
                    "source": request.source,
                    "field": field,
                    "where": selection,
                    "unit": request.unit,
                    "reduce": request.reduce,
                    "expected_count": request.expected_count,
                    "seed_column": request.seed_column,
                    "expected_seeds": seeds,
                },
                "BATCH_METRIC",
            )
            choice_id = fingerprint(metric)
            metric_name = next(
                (name for name, definition in config.metrics.items() if definition == metric),
                "batch_" + choice_id[7:23],
            )
            choice = {
                "choice_id": choice_id,
                "metric_name": metric_name,
                "definition": metric.model_dump(),
                "status": "ready",
                "suggested_locations": [],
            }
            candidate_config = config.model_copy(deep=True)
            if (
                metric_name in candidate_config.metrics
                and candidate_config.metrics[metric_name] != metric
            ):
                raise PaperDeltaError(
                    "BINDING_CONFLICT", msg("builder.exists", group="metrics", name=metric_name)
                )
            candidate_config.metrics[metric_name] = metric
            candidate_store = EvidenceStore(project, candidate_config)
            # The source and immutable indexes are shared during this inspection only.
            candidate_store.sources = store.sources
            candidate_store.csv_indexes = store.csv_indexes
            try:
                result = candidate_store.resolve(metric_name).to_dict()
                for evidence in result["evidence"]:
                    evidence["records"] = evidence["records"][:10]
                    evidence["locations"] = evidence["locations"][:10]
                choice["result"] = result
            except PaperDeltaError as exc:
                choice.update(status="unknown", error=exc.code, message=str(exc))
            for location in locations:
                text = _plain(location["row"])
                matched = [key for key, value in selection.items() if _contains(text, value)]
                field_matches = _contains(
                    _plain(
                        location["column_header"]
                        if location["kind"] == "table"
                        else location["row"]
                    ),
                    field,
                )
                # Never rank by numeric equality. A stale value is still a candidate.
                if matched or field_matches:
                    choice["suggested_locations"].append(
                        {
                            "candidate_id": location["candidate_id"],
                            "matched_identity": matched,
                            "missing_identity": sorted(set(selection) - set(matched)),
                            "field_matches": field_matches,
                            "kind": location["kind"],
                        }
                    )
            choice["suggested_locations"].sort(
                key=lambda item: (
                    -len(item["matched_identity"]),
                    not item["field_matches"],
                    item["kind"] != "table",
                    item["candidate_id"],
                )
            )
            choices.append(choice)
    builder._unchanged(project, draft.input_hashes)
    builder._unchanged(project, {**store.hashes, **scan["input_hashes"]})
    return {
        "catalog_id": catalog.catalog_id,
        "choices": choices,
        "locations": locations,
        "requires_confirmation": True,
    }


def build_proposal(project, value, selections):
    catalog = validate_record(BatchCatalog, value, "BATCH_CATALOG")
    preview = inspect_catalog(project, value)
    choices = {item["choice_id"]: item for item in preview["choices"]}
    if not selections or len(selections) > 1000:
        raise PaperDeltaError("BATCH_SELECTION", msg("batch.selection"))
    draft = catalog.draft.model_dump()
    for raw in selections:
        selection = validate_record(BatchSelection, raw, "BATCH_SELECTION")
        choice = choices.get(selection.choice_id)
        if choice is None or choice["status"] != "ready":
            raise PaperDeltaError("BATCH_SELECTION", msg("batch.selection"))
        _, config = builder.resume_draft(project, draft)
        metric = choice["definition"]
        if choice["metric_name"] not in config.metrics:
            draft = builder.add_metric(
                project,
                draft,
                name=choice["metric_name"],
                source=metric["source"],
                field=metric["field"],
                unit=metric["unit"],
                reduce=metric["reduce"],
                where={key: str(item) for key, item in metric["where"].items()},
                expected_count=metric["expected_count"],
                seed_column=metric["seed_column"],
                expected_seeds=[str(seed) for seed in metric["expected_seeds"]]
                if metric["expected_seeds"] is not None
                else None,
            )
        display = selection.display or catalog.request.display
        draft = builder.add_occurrences(
            project,
            draft,
            metric=choice["metric_name"],
            candidate_ids=selection.candidate_ids,
            names=[
                "batch_" + selection.choice_id[7:19] + "_" + candidate[7:19]
                for candidate in selection.candidate_ids
            ],
            display_kind=display.kind,
            places=display.places,
            percent_symbol=display.percent_symbol,
            rationale=selection.rationale,
        )
    return builder.finalize_draft(project, draft)
