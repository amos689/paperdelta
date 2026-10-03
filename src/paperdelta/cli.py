"""Local command-line entry point. JSON output is suitable for agent clients."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from paperdelta import __version__
from paperdelta.analysis import check_project
from paperdelta.arguments import ArgumentParser, json_errors
from paperdelta.errors import PaperDeltaError, error_message
from paperdelta.i18n import (
    UnsupportedLanguage,
    language_context,
    msg,
    resolve_language,
    tr,
    translated,
)
from paperdelta.i18n import translated as translate_location
from paperdelta.locations import location_label
from paperdelta.onboarding import (
    accept_bindings,
    init_project,
    inspect_proposal,
    parse_macros,
    propose_bindings,
    scan_project,
)
from paperdelta.patches import apply_patch, create_patch, preview_patch, recover_transaction
from paperdelta.preferences import read_preferences, save_language
from paperdelta.reports import text_report, write_reports
from paperdelta.reviews import record_review
from paperdelta.snapshots import create_snapshot, read_snapshot
from paperdelta.storage import Project, json_text, parse_json


def parser() -> argparse.ArgumentParser:
    root = ArgumentParser(prog="paperdelta", description=tr("cli.help.1"))
    root.add_argument(
        "--version",
        action="version",
        version=f"PaperDelta {__version__}",
        help=tr("argparse.version"),
    )
    root.add_argument("--lang", default=None, metavar="{en,zh-CN,auto}", help=tr("cli.language"))
    root.add_argument("-C", "--project", default=".", help=tr("cli.help.2"))
    root.add_argument("--config", default="paperdelta.yaml", help=tr("cli.help.3"))
    commands = root.add_subparsers(dest="command", required=True)
    from paperdelta.batch_cli import register_commands as register_batch
    from paperdelta.coverage import register_commands as register_scope
    from paperdelta.demo import register_commands as register_demo
    from paperdelta.watch import register_commands as register_watch

    register_scope(commands)
    register_batch(commands)
    register_watch(commands)
    register_demo(commands)
    doctor = commands.add_parser("doctor", help=tr("cli.doctor"))
    doctor.add_argument("--require-mcp", action="store_true", help=tr("cli.require_mcp"))
    guide = commands.add_parser("guide", help=tr("cli.guide"))
    repair = commands.add_parser("repair", help=tr("cli.repair"))
    repair_commands = repair.add_subparsers(dest="repair_command", required=True)
    repair_scan = repair_commands.add_parser("scan", help=tr("cli.repair_scan"))
    repair_scan.add_argument("--baseline", help=tr("cli.repair_baseline"))
    repair_guide = repair_commands.add_parser("guide", help=tr("cli.repair_guide"))
    repair_guide.add_argument("--baseline", help=tr("cli.repair_baseline"))
    repair_propose = repair_commands.add_parser("propose", help=tr("cli.repair_propose"))
    repair_propose.add_argument("--binding", required=True, help=tr("cli.repair_binding"))
    target = repair_propose.add_mutually_exclusive_group(required=True)
    target.add_argument("--candidate", help=tr("cli.repair_candidate"))
    target.add_argument("--exact", help=tr("cli.repair_exact"))
    repair_propose.add_argument("--file", help=tr("cli.repair_file"))
    repair_propose.add_argument("--rationale", required=True, help=tr("cli.repair_rationale"))
    repair_propose.add_argument("--baseline", help=tr("cli.repair_baseline"))
    repair_propose.add_argument("--out", required=True)
    repair_apply = repair_commands.add_parser("apply", help=tr("cli.repair_apply"))
    repair_apply.add_argument("proposal")
    repair_accept = repair_apply.add_mutually_exclusive_group()
    repair_accept.add_argument("--accept", action="append", help=tr("cli.repair_accept"))
    repair_accept.add_argument("--interactive", action="store_true", help=tr("cli.help.17"))
    settings = commands.add_parser("settings", help=tr("cli.settings"))
    settings.add_argument(
        "--language", choices=["en", "zh-CN", "auto"], help=tr("cli.save_language")
    )
    commands.add_parser("mcp", help=tr("cli.help.4"))
    schema = commands.add_parser("schema", help=tr("cli.help.5"))
    schema.add_argument(
        "kind",
        choices=[
            "config",
            "proposal",
            "proposal-input",
            "patch",
            "figure-record",
            "review-record",
            "snapshot",
            "report",
            "binding-draft",
            "repair-proposal",
            "batch-request",
            "batch-catalog",
            "batch-selection",
        ],
    )
    check = commands.add_parser("check", help=tr("cli.help.6"))
    check.add_argument("--format", choices=["text", "json"], default="text")
    check.add_argument("--baseline", help=tr("cli.help.7"))
    check.add_argument("--report", help=tr("cli.help.8"))
    scan = commands.add_parser("scan", help=tr("cli.help.9"))
    scan.add_argument("--format", choices=["text", "json"], default="json")
    scan.add_argument("--data", action="append", help=tr("cli.help.10"))
    init = commands.add_parser("init", help=tr("cli.help.11"))
    init.add_argument("--paper", required=True)
    init.add_argument("--data", action="append", default=[])
    init.add_argument("--macro", action="append", default=[], help=tr("cli.help.12"))
    propose = commands.add_parser("propose", help=tr("cli.help.13"))
    propose.add_argument("--input", required=True, help=tr("cli.help.14"))
    propose.add_argument("--out", required=True)
    bind = commands.add_parser("bind", help=tr("cli.help.15"))
    bind.add_argument("--proposal", required=True)
    binding_mode = bind.add_mutually_exclusive_group()
    binding_mode.add_argument("--accept", action="append", help=tr("cli.help.16"))
    binding_mode.add_argument("--interactive", action="store_true", help=tr("cli.help.17"))
    snapshots = commands.add_parser("snapshot", help=tr("cli.help.18"))
    snapshot_commands = snapshots.add_subparsers(dest="snapshot_command", required=True)
    create = snapshot_commands.add_parser("create", help=tr("cli.help.19"))
    create.add_argument("name")
    fix = commands.add_parser("fix", help=tr("cli.help.20"))
    fix.add_argument("--report", required=True, help=tr("cli.help.21"))
    fix.add_argument("--out", required=True, help=tr("cli.help.22"))
    fix.add_argument("--only", action="append", help=tr("cli.help.23"))
    apply = commands.add_parser("apply", help=tr("cli.help.24"))
    apply.add_argument("patch")
    writing = apply.add_mutually_exclusive_group()
    writing.add_argument("--dry-run", action="store_true")
    writing.add_argument("--write", action="store_true")
    recover = commands.add_parser("recover", help=tr("cli.help.25"))
    recover.add_argument("transaction")
    recover.add_argument("--write", action="store_true")
    review = commands.add_parser("review", help=tr("cli.help.26"))
    review_commands = review.add_subparsers(dest="review_command", required=True)
    record = review_commands.add_parser("record")
    record.add_argument("--claim", required=True)
    record.add_argument("--state", required=True, help=tr("cli.help.27"))
    record.add_argument("--reviewer", required=True)
    record.add_argument("--note", default="")
    record.add_argument("--attest-reviewed", action="store_true", required=True)
    for command, default in (
        (doctor, "text"),
        (guide, "text"),
        (repair_scan, "json"),
        (repair_guide, "text"),
        (repair_propose, "text"),
        (repair_apply, "text"),
        (settings, "text"),
        (init, "json"),
        (propose, "text"),
        (bind, "json"),
        (create, "text"),
        (fix, "text"),
        (apply, "text"),
        (recover, "json"),
        (record, "text"),
    ):
        command.add_argument(
            "--format", choices=["text", "json"], default=default, help=tr("cli.format")
        )
    return root


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    argv = list(sys.argv[1:] if argv is None else argv)
    use_json = any(
        value == "--format=json"
        or (value == "--format" and argv[index + 1 : index + 2] == ["json"])
        for index, value in enumerate(argv)
    )
    selected = None
    directory = "."
    for index, argument in enumerate(argv):
        if argument == "--":
            break
        if argument.startswith("--lang="):
            selected = argument.split("=", 1)[1]
        elif argument == "--lang" and index + 1 < len(argv):
            selected = argv[index + 1]
        elif argument.startswith("--project="):
            directory = argument.split("=", 1)[1]
        elif argument in {"-C", "--project"} and index + 1 < len(argv):
            directory = argv[index + 1]
        elif argument.startswith("-C") and len(argument) > 2:
            directory = argument[2:]
    try:
        preferences = {}
        if selected in {None, "auto"} and os.environ.get("PAPERDELTA_LANG") in {None, "", "auto"}:
            preferences = read_preferences(Project(directory))
        language = resolve_language(selected, preferences=preferences)
    except (ValueError, PaperDeltaError, OSError) as error:
        if isinstance(error, UnsupportedLanguage):
            code, message = "LANGUAGE", error.args[0]
        else:
            code, message = getattr(error, "code", "IO_ERROR"), error_message(error)
        if use_json:
            print(
                json_text(
                    {"error": code, "message": message, "display_message": translated(message)}
                ),
                end="",
            )
        else:
            print(f"PaperDelta: {code}: {translated(message)}", file=sys.stderr)
        return 2
    token = json_errors.set(use_json)
    try:
        with language_context(language):
            return _main(argv)
    finally:
        json_errors.reset(token)


def _main(argv: list[str]) -> int:
    arguments = parser().parse_args(argv)
    project = Project(Path(arguments.project))
    try:
        if arguments.command == "demo":
            from paperdelta.demo import run_command

            return run_command(project, arguments)
        if arguments.command == "watch":
            from paperdelta.watch import run_command

            return run_command(project, arguments)
        if arguments.command == "batch":
            from paperdelta.batch_cli import run_command

            return run_command(project, arguments)
        if arguments.command == "scope":
            from paperdelta.coverage import run_command

            return run_command(project, arguments)
        if arguments.command == "repair":
            return _repair(project, arguments)
        if arguments.command == "guide":
            from paperdelta.guided import guide_bindings

            result = guide_bindings(
                project, arguments.config, input_stream=sys.stdin, output=sys.stderr
            )
            _output(
                arguments,
                result,
                tr(
                    "cli.binding_result",
                    status=tr("status." + result["status"]),
                    count=len(result.get("bindings", [])),
                ),
            )
            return 0
        if arguments.command == "doctor":
            from paperdelta.doctor import diagnose, doctor_text

            result = diagnose(project, arguments.config, require_mcp=arguments.require_mcp)
            _output(arguments, result, doctor_text(result))
            return result["exit_code"]
        if arguments.command == "settings":
            result = (
                save_language(project, arguments.language)
                if arguments.language
                else read_preferences(project)
            )
            _output(
                arguments,
                result,
                tr("cli.settings_result", language=result.get("language", "auto")),
            )
            return 0
        if arguments.command == "schema":
            from paperdelta.batch import BatchCatalog, BatchRequest, BatchSelection
            from paperdelta.builder import BindingDraft
            from paperdelta.models import Config
            from paperdelta.onboarding import Proposal, ProposalInput
            from paperdelta.patches import Patch
            from paperdelta.records import FigureRecord, ReviewRecord, Snapshot, StoredReport
            from paperdelta.repairs import RepairProposal

            schemas = {
                "config": Config,
                "proposal": Proposal,
                "proposal-input": ProposalInput,
                "patch": Patch,
                "figure-record": FigureRecord,
                "review-record": ReviewRecord,
                "snapshot": Snapshot,
                "report": StoredReport,
                "binding-draft": BindingDraft,
                "repair-proposal": RepairProposal,
                "batch-request": BatchRequest,
                "batch-catalog": BatchCatalog,
                "batch-selection": BatchSelection,
            }
            print(json_text(schemas[arguments.kind].model_json_schema()), end="")
            return 0
        if arguments.command == "mcp":
            from paperdelta.mcp_server import serve

            serve(project, arguments.config)
            return 0
        if arguments.command == "init":
            result = init_project(
                project,
                arguments.paper,
                arguments.data,
                config_path=arguments.config,
                macros=parse_macros(arguments.macro),
            )
            _output(arguments, result, tr("cli.initialized", path=result["config_path"]))
            return 0
        if arguments.command == "scan":
            result = scan_project(project, arguments.config, arguments.data)
            if arguments.format == "json":
                print(json_text(result), end="")
            else:
                print(
                    tr(
                        "cli.output.6",
                        value1=len(result["candidates"]),
                        value2=len(result["sources"]),
                    )
                )
                for item in result["candidates"]:
                    hint = tr("hint." + item["priority_hint"])
                    print(f"{translate_location(location_label(item))}: {item['text']} ({hint})")
                for item in result["unsupported"]:
                    print(f"{item['file']}: {item['code']}: {translated(item['message'])}")
            return 0 if not result["unsupported"] else 2
        if arguments.command == "propose":
            saved, _ = project.text(arguments.input)
            value = parse_json(saved)
            if not isinstance(value, dict) or set(value) != {"additions", "rationale"}:
                raise PaperDeltaError("PROPOSAL_INPUT", msg("error.PROPOSAL_INPUT"))
            proposal = propose_bindings(
                project, value["additions"], value["rationale"], config_path=arguments.config
            )
            project.write(arguments.out, json_text(proposal).encode("utf-8"), exclusive=True)
            _output(
                arguments,
                {
                    "status": "proposed",
                    "path": arguments.out,
                    "proposal_id": proposal["proposal_id"],
                },
                tr("cli.output.1", value1=arguments.out),
            )
            return 0
        if arguments.command == "bind":
            saved, _ = project.text(arguments.proposal)
            value = parse_json(saved)
            if arguments.interactive:
                from paperdelta.interactive import confirm_bindings

                result = confirm_bindings(project, value, input_stream=sys.stdin, output=sys.stderr)
            elif arguments.accept:
                result = accept_bindings(project, value, arguments.accept)
            else:
                proposal, _, report = inspect_proposal(project, value)
                result = {"status": "proposed", "rationale": proposal.rationale, "preview": report}
            _output(
                arguments,
                result,
                tr(
                    "cli.binding_result",
                    status=tr("status." + result["status"]),
                    count=len(result.get("bindings", [])),
                ),
            )
            if arguments.format == "text" and "preview" in result:
                print(text_report(result["preview"]), end="")
            return 0
        if arguments.command == "fix":
            saved, _ = project.text(arguments.report)
            patch = create_patch(project, parse_json(saved), arguments.only)
            if project.path(arguments.out) in {
                project.path(path) for path in patch["input_hashes"]
            }:
                raise PaperDeltaError("PATCH_OVERWRITE", msg("error.PATCH_OVERWRITE"))
            project.write(arguments.out, json_text(patch).encode("utf-8"), exclusive=True)
            _output(
                arguments,
                {
                    "status": "proposed",
                    "path": arguments.out,
                    "patch_id": patch["patch_id"],
                    "changes": len(patch["changes"]),
                },
                tr("cli.output.2", value1=arguments.out, value2=len(patch["changes"])),
            )
            return 0
        if arguments.command == "apply":
            saved, _ = project.text(arguments.patch)
            patch = parse_json(saved)
            if not arguments.write:
                diff = preview_patch(project, patch)
                _output(
                    arguments,
                    {"status": "preview", "patch_id": patch["patch_id"], "diff": diff},
                    diff,
                )
                return 0
            result = apply_patch(project, patch)
            _output(arguments, result, tr("cli.output.3", value1=result["transaction_id"]))
            if arguments.format == "text":
                print(text_report(result["report"]), end="")
            return result["report"]["exit_code"]
        if arguments.command == "recover":
            result = recover_transaction(project, arguments.transaction, write=arguments.write)
            _output(
                arguments,
                result,
                tr(
                    "cli.recovery_result",
                    status=tr("status." + result["status"]),
                    transaction=result["transaction_id"],
                ),
            )
            return 0
        if arguments.command == "review":
            path = record_review(
                project,
                arguments.claim,
                arguments.state,
                arguments.reviewer,
                arguments.note,
                config_path=arguments.config,
                attest_reviewed=arguments.attest_reviewed,
            )
            _output(arguments, {"status": "recorded", "path": path}, tr("cli.output.4", path=path))
            return 0
        baseline = (
            read_snapshot(project, arguments.baseline)
            if getattr(arguments, "baseline", None)
            else None
        )
        report = check_project(project.root, arguments.config, baseline)
        if arguments.command == "snapshot":
            if report["exit_code"] == 2:
                _output(arguments, {"status": "unavailable", "report": report}, text_report(report))
                return 2
            path = create_snapshot(project, arguments.name, report)
            _output(
                arguments,
                {"status": "recorded", "path": path, "name": arguments.name},
                tr("cli.output.5", path=path),
            )
            return 0
        if getattr(arguments, "report", None):
            write_reports(project, arguments.report, report)
        print(json_text(report) if arguments.format == "json" else text_report(report), end="")
        return report["exit_code"]
    except (PaperDeltaError, OSError) as exc:
        if getattr(arguments, "format", "text") == "json" and (
            json_errors.get() or arguments.command in {"check", "scan"}
        ):
            print(
                json_text(
                    {
                        "error": getattr(exc, "code", "IO_ERROR"),
                        "message": str(exc),
                        "display_message": exc.render()
                        if isinstance(exc, PaperDeltaError)
                        else str(exc),
                    }
                ),
                end="",
            )
        else:
            print(
                tr("cli.output.7", value1=getattr(exc, "code", "IO_ERROR"), exc=exc),
                file=sys.stderr,
            )
        return 2


def _output(arguments, result: dict, text: str) -> None:
    if arguments.format == "json":
        print(
            json_text({"command_result_version": 1, "command": arguments.command, **result}), end=""
        )
    else:
        print(text, end="" if text.endswith("\n") else "\n")


def _repair(project, arguments):
    from paperdelta.repairs import (
        accept_repairs,
        confirm_repairs,
        guide_repairs,
        inspect_repair,
        propose_repairs,
        repair_text,
        scan_repairs,
    )

    if arguments.repair_command == "scan":
        result = scan_repairs(project, arguments.config, arguments.baseline)
        _output(arguments, result, repair_text(result))
    elif arguments.repair_command == "guide":
        result = guide_repairs(
            project, arguments.config, arguments.baseline, input_stream=sys.stdin, output=sys.stderr
        )
        _output(
            arguments,
            result,
            tr(
                "cli.binding_result",
                status=tr("status." + result["status"]),
                count=len(result["bindings"]),
            ),
        )
    elif arguments.repair_command == "propose":
        choice = {
            "binding": arguments.binding,
            "candidate_id": arguments.candidate,
            "file": arguments.file,
            "anchor": {"exact": arguments.exact} if arguments.exact else None,
            "rationale": arguments.rationale,
        }
        proposal = propose_repairs(
            project, [choice], config_path=arguments.config, baseline=arguments.baseline
        )
        project.write(arguments.out, json_text(proposal).encode("utf-8"), exclusive=True)
        _output(
            arguments,
            {"status": "proposed", "path": arguments.out, "repair_id": proposal["repair_id"]},
            tr("cli.output.1", value1=arguments.out),
        )
    else:
        text, _ = project.text(arguments.proposal)
        value = parse_json(text)
        if arguments.accept:
            result = accept_repairs(project, value, arguments.accept)
        elif arguments.interactive:
            result = confirm_repairs(project, value, input_stream=sys.stdin, output=sys.stderr)
        else:
            _, _, result = inspect_repair(project, value)
        description = (
            repair_text(result)
            if "changes" in result
            else tr(
                "cli.binding_result",
                status=tr("status." + result["status"]),
                count=len(result.get("bindings", [])),
            )
        )
        _output(arguments, result, description)
    return 0
