"""Local command-line entry point. JSON output is suitable for agent clients."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from paperdelta import __version__
from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.onboarding import (
    accept_bindings,
    init_project,
    inspect_proposal,
    parse_macros,
    propose_bindings,
    scan_project,
)
from paperdelta.patches import apply_patch, create_patch, preview_patch, recover_transaction
from paperdelta.reports import text_report, write_reports
from paperdelta.reviews import record_review
from paperdelta.snapshots import create_snapshot, read_snapshot
from paperdelta.storage import Project, json_text, parse_json


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="paperdelta", description="Review experiment changes in an existing paper."
    )
    root.add_argument("--version", action="version", version=f"PaperDelta {__version__}")
    root.add_argument(
        "-C", "--project", default=".", help="Project root (default: working directory)"
    )
    root.add_argument("--config", default="paperdelta.yaml", help="Project-relative configuration")
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("mcp", help="Run the optional read-only stdio MCP server")
    schema = commands.add_parser("schema", help="Print a versioned JSON Schema")
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
        ],
    )
    check = commands.add_parser("check", help="Check confirmed bindings against current results")
    check.add_argument("--format", choices=["text", "json"], default="text")
    check.add_argument("--baseline", help="A named snapshot for historical comparison")
    check.add_argument(
        "--report", help="Write JSON, Markdown and HTML to a project-relative directory"
    )
    scan = commands.add_parser("scan", help="List candidate numbers and current evidence")
    scan.add_argument("--format", choices=["text", "json"], default="json")
    scan.add_argument("--data", action="append", help="Additional CSV/JSON input to inspect")
    init = commands.add_parser(
        "init", help="Create discovery configuration without accepting bindings"
    )
    init.add_argument("--paper", required=True)
    init.add_argument("--data", action="append", default=[])
    init.add_argument(
        "--macro", action="append", default=[], help="Explicit literal macro name=arity"
    )
    propose = commands.add_parser(
        "propose", help="Validate and save an unaccepted mapping proposal"
    )
    propose.add_argument(
        "--input", required=True, help="JSON with additions and per-binding rationale"
    )
    propose.add_argument("--out", required=True)
    bind = commands.add_parser(
        "bind", help="Preview proposal evidence or explicitly accept selected mappings"
    )
    bind.add_argument("--proposal", required=True)
    bind.add_argument(
        "--accept", action="append", help="Qualified binding ID, e.g. occurrences:accuracy"
    )
    snapshots = commands.add_parser(
        "snapshot", help="Record a state without accepting it as reviewed"
    )
    snapshot_commands = snapshots.add_subparsers(dest="snapshot_command", required=True)
    create = snapshot_commands.add_parser("create", help="Save a new named snapshot")
    create.add_argument("name")
    fix = commands.add_parser("fix", help="Propose currently verified numeric fixes")
    fix.add_argument("--report", required=True, help="Project-relative report JSON")
    fix.add_argument("--out", required=True, help="New project-relative patch file")
    fix.add_argument("--only", action="append", help="Select an occurrence ID; repeatable")
    apply = commands.add_parser("apply", help="Preview or explicitly write a verified patch")
    apply.add_argument("patch")
    writing = apply.add_mutually_exclusive_group()
    writing.add_argument("--dry-run", action="store_true")
    writing.add_argument("--write", action="store_true")
    recover = commands.add_parser("recover", help="Preview or restore original transaction bytes")
    recover.add_argument("transaction")
    recover.add_argument("--write", action="store_true")
    review = commands.add_parser("review", help="Record an author's review of a specific state")
    review_commands = review.add_subparsers(dest="review_command", required=True)
    record = review_commands.add_parser("record")
    record.add_argument("--claim", required=True)
    record.add_argument("--state", required=True, help="Exact state_fingerprint from a fresh check")
    record.add_argument("--reviewer", required=True)
    record.add_argument("--note", default="")
    record.add_argument("--attest-reviewed", action="store_true", required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    arguments = parser().parse_args(argv)
    project = Project(Path(arguments.project))
    try:
        if arguments.command == "schema":
            from paperdelta.models import Config
            from paperdelta.onboarding import Proposal, ProposalInput
            from paperdelta.patches import Patch
            from paperdelta.records import FigureRecord, ReviewRecord, Snapshot, StoredReport

            schemas = {
                "config": Config,
                "proposal": Proposal,
                "proposal-input": ProposalInput,
                "patch": Patch,
                "figure-record": FigureRecord,
                "review-record": ReviewRecord,
                "snapshot": Snapshot,
                "report": StoredReport,
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
            print(json_text(result), end="")
            return 0
        if arguments.command == "scan":
            result = scan_project(project, arguments.config, arguments.data)
            if arguments.format == "json":
                print(json_text(result), end="")
            else:
                print(
                    f"{len(result['candidates'])} numeric candidates; "
                    f"{len(result['sources'])} data sources"
                )
                for item in result["candidates"]:
                    print(
                        f"{item['file']}:{item['line']}: {item['text']} ({item['priority_hint']})"
                    )
                for item in result["unsupported"]:
                    print(f"{item['file']}: {item['code']}: {item['message']}")
            return 0 if not result["unsupported"] else 2
        if arguments.command == "propose":
            saved, _ = project.text(arguments.input)
            value = parse_json(saved)
            if not isinstance(value, dict) or set(value) != {"additions", "rationale"}:
                raise PaperDeltaError("PROPOSAL_INPUT", "Expected additions and rationale fields")
            proposal = propose_bindings(
                project, value["additions"], value["rationale"], config_path=arguments.config
            )
            project.write(arguments.out, json_text(proposal).encode("utf-8"), exclusive=True)
            print(f"Saved unaccepted proposal {arguments.out}. Use bind to inspect its evidence.")
            return 0
        if arguments.command == "bind":
            saved, _ = project.text(arguments.proposal)
            value = parse_json(saved)
            if arguments.accept:
                print(json_text(accept_bindings(project, value, arguments.accept)), end="")
            else:
                proposal, _, report = inspect_proposal(project, value)
                print(
                    json_text(
                        {"status": "proposed", "rationale": proposal.rationale, "preview": report}
                    ),
                    end="",
                )
            return 0
        if arguments.command == "fix":
            saved, _ = project.text(arguments.report)
            patch = create_patch(project, parse_json(saved), arguments.only)
            if project.path(arguments.out) in {
                project.path(path) for path in patch["input_hashes"]
            }:
                raise PaperDeltaError("PATCH_OVERWRITE", "Patch output would overwrite an input")
            project.write(arguments.out, json_text(patch).encode("utf-8"), exclusive=True)
            print(f"Saved {arguments.out}: {len(patch['changes'])} proposed numeric changes.")
            return 0
        if arguments.command == "apply":
            saved, _ = project.text(arguments.patch)
            patch = parse_json(saved)
            if not arguments.write:
                print(preview_patch(project, patch), end="")
                return 0
            result = apply_patch(project, patch)
            print(f"Applied transaction {result['transaction_id']}.")
            print(text_report(result["report"]), end="")
            return result["report"]["exit_code"]
        if arguments.command == "recover":
            result = recover_transaction(project, arguments.transaction, write=arguments.write)
            print(json_text(result), end="")
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
            print(f"Recorded {path}. This declaration does not change any check result.")
            return 0
        baseline = (
            read_snapshot(project, arguments.baseline)
            if getattr(arguments, "baseline", None)
            else None
        )
        report = check_project(project.root, arguments.config, baseline)
        if arguments.command == "snapshot":
            if report["exit_code"] == 2:
                print(text_report(report), end="")
                return 2
            path = create_snapshot(project, arguments.name, report)
            print(f"Recorded {path}. A snapshot is not an approval of the paper.")
            return 0
        if getattr(arguments, "report", None):
            write_reports(project, arguments.report, report)
        print(json_text(report) if arguments.format == "json" else text_report(report), end="")
        return report["exit_code"]
    except (PaperDeltaError, OSError) as exc:
        if getattr(arguments, "format", "text") == "json":
            print(
                json_text({"error": getattr(exc, "code", "IO_ERROR"), "message": str(exc)}), end=""
            )
        else:
            print(f"PaperDelta: {getattr(exc, 'code', 'IO_ERROR')}: {exc}", file=sys.stderr)
        return 2
