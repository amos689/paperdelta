"""Explicit import and offline inspection without accepting manuscript bindings."""

from paperdelta.experiment_exports import provenance, validate_export
from paperdelta.experiment_imports import import_evidence
from paperdelta.i18n import tr
from paperdelta.storage import json_text, parse_json


def register_commands(commands):
    command = commands.add_parser("evidence", help=tr("export.cli"))
    actions = command.add_subparsers(dest="evidence_command", required=True)
    load = actions.add_parser("import", help=tr("export.cli_import"))
    load.add_argument("request", help=tr("export.cli_request"))
    load.add_argument("--out", required=True, help=tr("export.cli_out"))
    inspect = actions.add_parser("inspect", help=tr("export.cli_inspect"))
    inspect.add_argument("path")
    inspect.add_argument("--offset", type=int, default=0)
    inspect.add_argument("--limit", type=int, default=20)
    for parser in (load, inspect):
        parser.add_argument("--format", choices=["json", "text"], default="json")


def run_command(project, args):
    from paperdelta.experiment_exports import export_error

    if args.evidence_command == "import":
        raw, _ = project.text(args.request)
        result = import_evidence(project, parse_json(raw), args.out)
    else:
        if args.offset < 0 or not 1 <= args.limit <= 100:
            raise export_error("page")
        raw, _ = project.text(args.path)
        document = validate_export(parse_json(raw))
        result = {
            "status": "inspected",
            "path": args.path,
            "records": len(document.records),
            "columns": document.columns,
            "primary_key": document.primary_key,
            "sample": [
                row.model_dump() for row in document.records[args.offset : args.offset + args.limit]
            ],
            "provenance": provenance(document),
        }
    if args.format == "text":
        print(tr("export.result", path=result["path"], count=result["records"]))
    print(json_text(result), end="")
    return 0
