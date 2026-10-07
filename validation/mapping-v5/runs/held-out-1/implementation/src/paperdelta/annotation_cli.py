"""Preview reviewed locations, then create an explicitly accepted annotation ZIP."""

from paperdelta.annotations import annotation_bytes, preview_annotations
from paperdelta.i18n import tr
from paperdelta.storage import json_text, parse_json


def register_commands(commands):
    root = commands.add_parser("annotate", help=tr("annotation.help"))
    sub = root.add_subparsers(dest="annotation_command", required=True)
    preview = sub.add_parser("preview", help=tr("annotation.preview_help"))
    preview.add_argument("--only", action="append", required=True, help=tr("annotation.only_help"))
    preview.add_argument("--out", help=tr("annotation.plan_out"))
    create = sub.add_parser("create", help=tr("annotation.create_help"))
    create.add_argument("--plan", required=True, help=tr("annotation.plan_help"))
    create.add_argument("--out", required=True, help=tr("annotation.out_help"))
    create.add_argument(
        "--attest-reviewed", action="store_true", required=True, help=tr("annotation.attest_help")
    )


def run_command(project, arguments):
    if arguments.annotation_command == "preview":
        value = preview_annotations(project, {"occurrences": arguments.only}, arguments.config)
        if arguments.out:
            project.write(arguments.out, json_text(value).encode(), exclusive=True)
        print(json_text(value))
        return 0
    plan = parse_json(project.read(arguments.plan, 16 * 1024 * 1024).decode("utf-8"))
    raw = annotation_bytes(project, plan)
    project.write(arguments.out, raw, exclusive=True)
    print(json_text({"status": "created", "path": arguments.out, "bytes": len(raw)}))
    return 0
