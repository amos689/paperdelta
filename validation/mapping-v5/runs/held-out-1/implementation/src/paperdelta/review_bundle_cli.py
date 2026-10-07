"""Explicit local preview, creation, inspection and replay of selected review files."""

from paperdelta.i18n import tr
from paperdelta.review_bundle import (
    MAX_ARCHIVE,
    bundle_bytes,
    inspect_bundle,
    preview_bundle,
    replay_bundle,
)
from paperdelta.storage import json_text, parse_json


def register_commands(commands):
    root = commands.add_parser("bundle", help=tr("bundle.help"))
    sub = root.add_subparsers(dest="bundle_command", required=True)
    preview = sub.add_parser("preview", help=tr("bundle.preview_help"))
    preview.add_argument(
        "--reports",
        nargs="*",
        choices=["html", "json", "md", "sarif"],
        default=["html", "json"],
        help=tr("bundle.reports_help"),
    )
    preview.add_argument("--input", action="append", default=[], help=tr("bundle.input_help"))
    preview.add_argument("--all-inputs", action="store_true", help=tr("bundle.all_help"))
    preview.add_argument("--baseline", help=tr("bundle.baseline_help"))
    preview.add_argument("--out", help=tr("bundle.plan_out"))
    create = sub.add_parser("create", help=tr("bundle.create_help"))
    create.add_argument("--plan", required=True, help=tr("bundle.plan_help"))
    create.add_argument("--out", required=True, help=tr("bundle.zip_out"))
    inspect = sub.add_parser("inspect", help=tr("bundle.inspect_help"))
    inspect.add_argument("archive", help=tr("bundle.archive_help"))
    replay = sub.add_parser("replay", help=tr("bundle.replay_help"))
    replay.add_argument("archive", help=tr("bundle.archive_help"))
    replay.add_argument("--out", required=True, help=tr("bundle.replay_out"))


def run_command(project, args):
    if args.bundle_command == "preview":
        inputs = args.input
        if args.all_inputs:
            initial = preview_bundle(
                project, {"reports": ["json"], "inputs": []}, args.config, args.baseline
            )
            inputs = sorted(initial["required_inputs"])
        result = preview_bundle(
            project, {"reports": args.reports, "inputs": inputs}, args.config, args.baseline
        )
        if args.out:
            project.write(args.out, json_text(result).encode("utf-8"), exclusive=True)
    elif args.bundle_command == "create":
        plan = parse_json(project.read(args.plan, 4 * 1024 * 1024).decode("utf-8"))
        raw = bundle_bytes(project, plan)
        project.write(args.out, raw, exclusive=True)
        result = {
            "status": "saved",
            "path": args.out,
            "bytes": len(raw),
            "preview_id": plan["preview_id"],
        }
    elif args.bundle_command == "inspect":
        result = inspect_bundle(project.read(args.archive, MAX_ARCHIVE))
    else:
        result = replay_bundle(project, project.read(args.archive, MAX_ARCHIVE), args.out)
    print(json_text(result), end="")
    return result.get("exit_code", 0)
