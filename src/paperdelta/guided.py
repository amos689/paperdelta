"""Terminal construction of typed mappings, followed by the normal final review."""

from __future__ import annotations

from pathlib import Path

from paperdelta import builder
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg, tr
from paperdelta.i18n import translated as translate_location
from paperdelta.interactive import _safe, _show, confirm_bindings
from paperdelta.locations import location_label
from paperdelta.onboarding import _source_summary, scan_project


class Questions:
    def __init__(self, input_stream, output):
        self.input = input_stream
        self.output = output

    def read(self, key, *, required=False, exact=False, **parameters):
        while True:
            self.output.write(tr(key, **parameters) + " ")
            self.output.flush()
            value = self.input.readline()
            if not value or value.strip() in {":q", "取消"}:
                raise EOFError
            value = value.rstrip("\r\n") if exact else value.strip()
            if value or not required:
                return value
            self.output.write(tr("guide.required") + "\n")

    def choose(self, key, options):
        self.output.write(tr(key) + "\n")
        for index, (_, label) in enumerate(options, 1):
            self.output.write(f"  {index}. {_safe(str(label))}\n")
        while True:
            answer = self.read("guide.choice")
            if answer.isascii() and answer.isdigit() and 1 <= int(answer) <= len(options):
                return options[int(answer) - 1][0]
            self.output.write(tr("guide.invalid_choice") + "\n")

    def many(self, key, options):
        self.output.write(tr(key) + "\n")
        for index, (_, label) in enumerate(options, 1):
            self.output.write(f"  {index}. {_safe(str(label))}\n")
        while True:
            answer = self.read("guide.many")
            parts = answer.split(",")
            if all(part.strip().isascii() and part.strip().isdigit() for part in parts):
                indices = [int(part.strip()) for part in parts]
                if len(set(indices)) == len(indices) and all(
                    1 <= i <= len(options) for i in indices
                ):
                    return [options[i - 1][0] for i in indices]
            self.output.write(tr("guide.invalid_choice") + "\n")

    def integer(self, key, lower, upper):
        while True:
            answer = self.read(key)
            if answer.isascii() and answer.isdigit() and lower <= int(answer) <= upper:
                return int(answer)
            self.output.write(tr("guide.integer", lower=lower, upper=upper) + "\n")


def _source(project, draft, questions):
    _, config = builder.resume_draft(project, draft)
    scan = scan_project(project, draft["config_path"])
    options = [
        ("existing:" + name, f"{name} · {source.path}") for name, source in config.sources.items()
    ]
    known = {source.path for source in config.sources.values()}
    options.extend(
        ("path:" + source["path"], source["path"])
        for source in scan["sources"]
        if source["path"] not in known
    )
    options.append(("custom", tr("guide.custom_source")))
    choice = questions.choose("guide.source", options)
    if choice.startswith("existing:"):
        name = choice.split(":", 1)[1]
        _show(questions.output, tr("guide.source"), config.sources[name].model_dump())
        return draft, name
    path = (
        choice.split(":", 1)[1]
        if choice.startswith("path:")
        else questions.read("guide.path", required=True)
    )
    summary, _ = _source_summary(project, path)
    _show(questions.output, tr("guide.sample"), summary["sample"])
    name = questions.read("guide.source_name", required=True)
    columns, keys = {}, []
    if Path(path).suffix.lower() == ".csv":
        keys = questions.many("guide.primary_key", [(name, name) for name in summary["columns"]])
        for column in summary["columns"]:
            questions.output.write(tr("guide.column", name=_safe(column)) + "\n")
            columns[column] = questions.choose(
                "guide.type",
                [(kind, tr("type." + kind)) for kind in ("string", "integer", "decimal")],
            )
    return builder.add_source(
        project,
        draft,
        name=name,
        path=path,
        format=summary["format"],
        columns=columns,
        primary_key=keys,
    ), name


def _new_metric(project, draft, questions):
    draft, source = _source(project, draft, questions)
    _, config = builder.resume_draft(project, draft)
    declaration = config.sources[source]
    name = questions.read("guide.metric_name", required=True)
    where, seeds = {}, None
    seed_column = "seed"
    if declaration.format == "csv":
        field = questions.choose("guide.field", [(key, key) for key in declaration.columns])
        for column in declaration.columns:
            if column == field:
                continue
            selected = questions.read("guide.where", exact=True, column=_safe(column))
            if selected:
                where[column] = selected
    else:
        field = questions.read("guide.pointer", exact=True)
    unit = questions.choose(
        "guide.unit",
        [
            (unit, f"{unit} · {tr('unit.' + unit)}")
            for unit in ("scalar", "fraction", "percent", "percentage_point", "count", "ratio")
        ],
    )
    reduce = questions.choose(
        "guide.reduce",
        [
            (reduce, f"{reduce} · {tr('reduce.' + reduce)}")
            for reduce in ("unique", "mean", "sum", "count")
        ],
    )
    count = 1 if reduce == "unique" else questions.integer("guide.expected_count", 1, 10000)
    seed_options = [
        (key, key) for key, kind in declaration.columns.items() if kind in {"string", "integer"}
    ]
    if declaration.format == "csv":
        seed_column = questions.choose(
            "guide.seed_column", [(None, tr("guide.no_seeds")), *seed_options]
        )
        if seed_column is not None:
            seeds = questions.read("guide.seeds", required=True, exact=True).split(",")
        else:
            seed_column = "seed"
    draft = builder.add_metric(
        project,
        draft,
        name=name,
        source=source,
        field=field,
        unit=unit,
        reduce=reduce,
        where=where,
        expected_count=count,
        seed_column=seed_column,
        expected_seeds=seeds,
    )
    return draft, name


def _stage(project, draft, questions):
    _, config = builder.resume_draft(project, draft)
    options = [("new", tr("guide.new_metric"))]
    if config.metrics:
        options.append(("derived", tr("guide.derived")))
        options.extend(("use:" + name, name) for name in config.metrics)
    choice = questions.choose("guide.metric", options)
    if choice == "new":
        draft, metric = _new_metric(project, draft, questions)
    elif choice == "derived":
        metric = questions.read("guide.metric_name", required=True)
        operation = questions.choose(
            "guide.operation",
            [
                (op, tr("operation." + op))
                for op in (
                    "difference",
                    "ratio",
                    "percentage_point_difference",
                    "relative_change_percent",
                )
            ],
        )
        operands = [(name, name) for name in config.metrics]
        left = questions.choose("guide.left", operands)
        right = questions.choose("guide.right", operands)
        draft = builder.add_derived(
            project, draft, name=metric, operation=operation, left=left, right=right
        )
    else:
        metric = choice.split(":", 1)[1]
    _, config = builder.resume_draft(project, draft)
    from paperdelta.sources import EvidenceStore

    result = EvidenceStore(project, config).resolve(metric).to_dict()
    for evidence in result["evidence"]:
        evidence["records"] = evidence["records"][:10]
        evidence["locations"] = evidence["locations"][:10]
    _show(questions.output, tr("guide.selected_evidence"), result)
    scan = scan_project(project, draft["config_path"])
    query = questions.read("guide.filter").casefold()
    candidates = [
        item
        for item in scan["candidates"]
        if query
        in (item["file"] + item["context_before"] + item["text"] + item["context_after"]).casefold()
    ]
    if not candidates:
        raise PaperDeltaError("BUILDER_SELECTION", msg("guide.no_candidates"))
    selected = questions.many(
        "guide.locations",
        [
            (
                item["candidate_id"],
                f"{translate_location(location_label(item))} · {item['context_before']} "
                f"⟦{item['text']}⟧{item['context_after']}",
            )
            for item in candidates
        ],
    )
    base_name = questions.read("guide.binding_name", required=True)
    names = (
        [base_name]
        if len(selected) == 1
        else [f"{base_name}_{index}" for index in range(1, len(selected) + 1)]
    )
    kind = questions.choose(
        "guide.display",
        [(kind, tr("display." + kind)) for kind in ("decimal", "percent", "integer", "scientific")],
    )
    places = 0 if kind == "integer" else questions.integer("guide.places", 0, 15)
    symbol = (
        questions.choose("guide.percent_symbol", [(True, tr("guide.yes")), (False, tr("guide.no"))])
        if kind == "percent"
        else True
    )
    rationale = questions.read("guide.rationale", required=True)
    return builder.add_occurrences(
        project,
        draft,
        metric=metric,
        candidate_ids=selected,
        names=names,
        display_kind=kind,
        places=places,
        percent_symbol=symbol,
        rationale=rationale,
    )


def guide_bindings(project, config_path, *, input_stream, output):
    if not input_stream.isatty() or not output.isatty():
        raise PaperDeltaError("INTERACTIVE_TERMINAL", msg("error.INTERACTIVE_TERMINAL"))
    questions = Questions(input_stream, output)
    draft = builder.start_draft(project, config_path)
    output.write(tr("guide.welcome") + "\n")
    try:
        while True:
            try:
                staged = _stage(project, draft, questions)
            except PaperDeltaError as error:
                output.write(_safe(error.render()) + "\n")
                if error.code in {"STALE_DRAFT", "DRAFT_IDENTITY"}:
                    raise
                if questions.choose(
                    "guide.retry", [(True, tr("guide.yes")), (False, tr("guide.no"))]
                ):
                    continue
                raise EOFError from error
            draft = staged
            if not questions.choose(
                "guide.more", [(False, tr("guide.review")), (True, tr("guide.add_more"))]
            ):
                break
        proposal = builder.finalize_draft(project, draft)
    except (EOFError, KeyboardInterrupt):
        output.write(tr("guide.cancelled") + "\n")
        return {"status": "cancelled", "bindings": [], "reason": "input interrupted"}
    # No write has occurred. Final review and acceptance recheck every identity.
    return confirm_bindings(project, proposal, input_stream=input_stream, output=output)
