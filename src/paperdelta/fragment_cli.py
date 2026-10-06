"""Preview and explicitly accept generated result fragments; never patch prose."""

from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.fragments import accept_fragment, preview_fragment
from paperdelta.i18n import current_language, msg, tr, translated
from paperdelta.provenance import _safe_path
from paperdelta.revisions import revision_list
from paperdelta.snapshots import read_snapshot
from paperdelta.storage import json_text, parse_json


def register_commands(commands):
    revisions = commands.add_parser("revisions", help=tr("revisions.help"))
    revisions.add_argument("--baseline", help=tr("revisions.baseline"))
    root = commands.add_parser("fragment", help=tr("fragments.help"))
    sub = root.add_subparsers(dest="fragment_command", required=True)
    preview = sub.add_parser("preview", help=tr("fragments.preview_help"))
    preview.add_argument("name", help=tr("provenance.name_help"))
    preview.add_argument(
        "--occurrence", action="append", required=True, help=tr("fragments.occurrence_help")
    )
    preview.add_argument(
        "--format", choices=["latex", "markdown"], required=True, help=tr("fragments.format_help")
    )
    preview.add_argument(
        "--layout", choices=["value", "table"], default="table", help=tr("fragments.layout_help")
    )
    preview.add_argument("--path", required=True, help=tr("fragments.path_help"))
    preview.add_argument("--replace", action="store_true", help=tr("fragments.replace_help"))
    preview.add_argument("--out", required=True, help=tr("provenance.preview_out"))
    accept = sub.add_parser("accept", help=tr("fragments.accept_help"))
    accept.add_argument("proposal", help=tr("provenance.proposal_help"))


def run_command(project, args):
    if args.command == "revisions":
        baseline = read_snapshot(project, args.baseline) if args.baseline else None
        report = check_project(project.root, args.config, baseline)
        result = {
            "items": revision_list(report),
            "notice": msg("revisions.notice"),
            "exit_code": report["exit_code"],
            "input_hashes": report["input_hashes"],
        }
        print(json_text(translated(result)), end="")
        return report["exit_code"]
    if args.fragment_command == "accept":
        result = accept_fragment(
            project, parse_json(project.text(args.proposal, 4 * 1024 * 1024)[0])
        )
    else:
        proposal = preview_fragment(
            project,
            args.name,
            {
                "format": args.format,
                "path": args.path,
                "occurrences": args.occurrence,
                "layout": args.layout,
                "language": current_language(),
            },
            replace=args.replace,
            config_path=args.config,
        )
        output = _safe_path(project, args.out)
        if output in {args.config, args.path, *proposal["record"]["inputs"]}:
            raise PaperDeltaError("FRAGMENT_PATH", msg("fragments.path"))
        project.write(output, json_text(proposal).encode("utf-8"), exclusive=True)
        result = {"status": "preview", "path": output, "proposal": proposal, "accepted": False}
    print(json_text(result), end="")
    return 0
