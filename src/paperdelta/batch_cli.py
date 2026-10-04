"""Batch onboarding with reusable declarations and explicit, editable choices."""

from __future__ import annotations

from paperdelta import builder
from paperdelta.batch import build_proposal, create_catalog, inspect_catalog
from paperdelta.errors import PaperDeltaError
from paperdelta.guided import Questions, _source
from paperdelta.i18n import msg, tr
from paperdelta.i18n import translated as translate_location
from paperdelta.interactive import _safe, _show, confirm_bindings
from paperdelta.locations import location_label
from paperdelta.storage import json_text, parse_json


def _display(questions, statistical=False):
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
    result = {"kind": kind, "places": places, "percent_symbol": symbol}
    if statistical:
        from paperdelta.statistical_guide import display_questions

        result["statistics"] = display_questions(questions)
    return result


def _selection(preview, choice, questions, default_display):
    _show(questions.output, tr("batch.metric"), choice)
    if choice["status"] != "ready":
        questions.output.write(tr("batch.unresolved") + "\n")
        return None
    if questions.choose(
        "batch.select_or_skip", [(False, tr("batch.select")), (True, tr("batch.skip"))]
    ):
        return None
    query = questions.read("guide.filter").casefold()
    suggested = {
        item["candidate_id"]: index for index, item in enumerate(choice["suggested_locations"])
    }
    locations = list(preview["locations"])
    if query:
        locations = [
            item
            for item in locations
            if query
            in (
                item["file"] + item["context_before"] + item["text"] + item["context_after"]
            ).casefold()
        ]
    locations.sort(
        key=lambda item: (
            suggested.get(item["candidate_id"], len(suggested)),
            item["file"],
            item["start"],
        )
    )
    if not locations:
        raise PaperDeltaError("BUILDER_SELECTION", msg("guide.no_candidates"))
    selected = questions.many(
        "batch.locations",
        [
            (
                item["candidate_id"],
                f"{translate_location(location_label(item))} · {item['context_before']} "
                f"⟦{item['text']}⟧{item['context_after']}",
            )
            for item in locations
        ],
    )
    display = default_display
    if questions.choose(
        "batch.display_override",
        [(False, tr("batch.keep_display")), (True, tr("batch.change_display"))],
    ):
        display = _display(questions, bool(default_display.get("statistics")))
    rationale = questions.read("guide.rationale", required=True)
    return {
        "choice_id": choice["choice_id"],
        "candidate_ids": selected,
        "rationale": rationale,
        "display": display,
    }


def guide_batch(project, config_path, *, input_stream, output):
    if not input_stream.isatty() or not output.isatty():
        raise PaperDeltaError("INTERACTIVE_TERMINAL", msg("error.INTERACTIVE_TERMINAL"))
    questions = Questions(input_stream, output)
    output.write(tr("batch.welcome") + "\n")
    try:
        draft, source = _source(project, builder.start_draft(project, config_path), questions)
        _, config = builder.resume_draft(project, draft)
        declaration = config.sources[source]
        if declaration.format == "json":
            raise PaperDeltaError("BATCH_FORMAT", msg("batch.csv"))
        fields = questions.many(
            "batch.fields",
            [
                (name, name)
                for name, kind in declaration.columns.items()
                if kind in {"integer", "decimal"}
            ],
        )
        groups = questions.many(
            "batch.group_by", [(name, name) for name in declaration.columns if name not in fields]
        )
        where = {}
        for column in declaration.columns:
            if column in fields or column in groups:
                continue
            value = questions.read("guide.where", exact=True, column=_safe(column))
            if value:
                where[column] = value
        unit = questions.choose(
            "guide.unit",
            [
                (kind, tr("unit." + kind))
                for kind in ("scalar", "fraction", "percent", "percentage_point", "count", "ratio")
            ],
        )
        reduce = questions.choose(
            "guide.reduce",
            [
                (kind, tr("reduce." + kind))
                for kind in ("unique", "mean", "sum", "count", "statistics")
            ],
        )
        count = 1 if reduce == "unique" else questions.integer("guide.expected_count", 1, 10000)
        seed_column = questions.choose(
            "guide.seed_column",
            [
                (None, tr("guide.no_seeds")),
                *[
                    (name, name)
                    for name, kind in declaration.columns.items()
                    if kind in {"string", "integer"} and name not in fields
                ],
            ],
        )
        seeds = (
            questions.read("guide.seeds", required=True, exact=True).split(",")
            if seed_column
            else None
        )
        from paperdelta.statistical_guide import contract_questions

        statistics = contract_questions(questions) if reduce == "statistics" else None
        display = _display(questions, statistics is not None)
        catalog = create_catalog(
            project,
            draft,
            {
                "source": source,
                "fields": fields,
                "group_by": groups,
                "where": where,
                "unit": unit,
                "reduce": reduce,
                "expected_count": count,
                "seed_column": seed_column or "seed",
                "expected_seeds": seeds,
                "display": display,
                "statistics": statistics,
            },
        )
        preview = inspect_catalog(project, catalog)
        _show(
            output,
            tr("batch.candidates"),
            [
                {key: item.get(key) for key in ("choice_id", "definition", "status", "error")}
                for item in preview["choices"]
            ],
        )
        choices = questions.many(
            "batch.metrics",
            [
                (
                    index,
                    f"{item['definition']['field']} · {item['definition']['where']} "
                    f"· {item['status']}",
                )
                for index, item in enumerate(preview["choices"])
            ],
        )
        selections = {}

        def select(index):
            choice = preview["choices"][index]
            while True:
                try:
                    item = _selection(preview, choice, questions, display)
                    proposed = dict(selections)
                    if item is None:
                        proposed.pop(index, None)
                    else:
                        proposed[index] = item
                    if proposed:
                        build_proposal(project, catalog, list(proposed.values()))
                    selections.clear()
                    selections.update(proposed)
                    return
                except PaperDeltaError as exc:
                    output.write(_safe(exc.render()) + "\n")
                    if exc.code in {"STALE_DRAFT", "DRAFT_IDENTITY", "BATCH_IDENTITY"}:
                        raise
                    if not questions.choose(
                        "guide.retry", [(True, tr("guide.yes")), (False, tr("guide.no"))]
                    ):
                        return

        for index in choices:
            select(index)
        while True:
            action = questions.choose(
                "batch.review_menu",
                [
                    ("review", tr("guide.review")),
                    ("edit", tr("batch.edit")),
                    ("cancel", tr("batch.cancel")),
                ],
            )
            if action == "cancel":
                raise EOFError
            if action == "review":
                proposal = build_proposal(project, catalog, list(selections.values()))
                break
            index = questions.choose(
                "batch.metrics",
                [
                    (index, f"{item['definition']['field']} · {item['definition']['where']}")
                    for index, item in enumerate(preview["choices"])
                ],
            )
            select(index)
    except (EOFError, KeyboardInterrupt):
        output.write(tr("guide.cancelled") + "\n")
        return {"status": "cancelled", "bindings": [], "reason": "input interrupted"}
    return confirm_bindings(project, proposal, input_stream=input_stream, output=output, batch=True)


def register_commands(commands):
    batch = commands.add_parser("batch", help=tr("batch.help"))
    actions = batch.add_subparsers(dest="batch_action", required=True)
    for action in ("guide", "scan", "propose"):
        child = actions.add_parser(action, help=tr("batch.help_" + action))
        child.add_argument(
            "--format",
            choices=["text", "json"],
            default="json" if action == "scan" else "text",
            help=tr("cli.format"),
        )
        if action == "scan":
            child.add_argument("--request", required=True, help=tr("batch.request_file"))
            child.add_argument("--draft", help=tr("batch.draft_file"))
        if action == "propose":
            child.add_argument("--catalog", required=True, help=tr("batch.catalog_file"))
            child.add_argument("--selections", required=True, help=tr("batch.selections_file"))
        if action != "guide":
            child.add_argument("--out", required=True, help=tr("batch.output_file"))


def run_command(project, arguments):
    import sys

    def read(path):
        return parse_json(project.text(path)[0])

    if arguments.batch_action == "guide":
        result = guide_batch(project, arguments.config, input_stream=sys.stdin, output=sys.stderr)
    elif arguments.batch_action == "scan":
        draft = (
            read(arguments.draft)
            if arguments.draft
            else builder.start_draft(project, arguments.config)
        )
        catalog = create_catalog(project, draft, read(arguments.request))
        project.write(arguments.out, json_text(catalog).encode("utf-8"), exclusive=True)
        result = {"status": "proposed", "path": arguments.out, **inspect_catalog(project, catalog)}
    else:
        selections = read(arguments.selections)
        if not isinstance(selections, list):
            raise PaperDeltaError("BATCH_SELECTION", msg("batch.selection"))
        proposal = build_proposal(project, read(arguments.catalog), selections)
        project.write(arguments.out, json_text(proposal).encode("utf-8"), exclusive=True)
        result = {
            "status": "proposed",
            "path": arguments.out,
            "proposal_id": proposal["proposal_id"],
            "next": msg("agent.next_binding"),
        }
    if arguments.format == "json":
        print(json_text(result), end="")
    else:
        print(tr("batch.result", status=tr("status." + result["status"])))
        if "path" in result:
            print(tr("cli.output.1", value1=result["path"]))
        if "choices" in result:
            for item in result["choices"]:
                _show(sys.stdout, tr("batch.metric"), item)
    return 0
