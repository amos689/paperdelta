"""Explicit review scope and source-bound exclusions; never waive accepted checks."""

from __future__ import annotations

import uuid

from paperdelta.config import config_text, load_config
from paperdelta.documents import PaperIndex
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg, tr
from paperdelta.models import Anchor, Config, CoverageExclusion, ReviewScope
from paperdelta.patches import _write_lock
from paperdelta.records import validate_record
from paperdelta.storage import Project, sha256


def context_hash(document, span):
    # Include the number and its immediate context, not only its old value.
    return sha256(document.text[max(0, span.start - 80) : span.end + 80].encode("utf-8"))


def _overlaps(first, second):
    return first.file == second.file and first.start < second.end and second.start < first.end


def _selected(scope, paper, span):
    if scope is None:
        return True
    if scope.files and span.file not in scope.files:
        return False
    return not scope.regions or any(
        kind in scope.regions and start <= span.start and span.end <= end
        for start, end, kind in paper.documents[span.file].priority_regions
    )


def apply_coverage(config, paper, report, covered):
    coverage = report["coverage"]
    scope = config.review_scope
    if scope:
        scope = ReviewScope(
            files=[paper.project.relative(paper.project.path(file)) for file in scope.files],
            regions=scope.regions,
        )
    coverage["review_scope"] = scope.model_dump() if scope else None
    coverage["outside_scope_numbers"] = []
    coverage["exclusions"] = []
    if scope:
        for file in scope.files:
            paper.document(file)
        # A typo or an unsupported environment cannot yield a vacuous success.
        if scope.regions and not any(
            kind in scope.regions
            for file, doc in paper.documents.items()
            if not scope.files or file in scope.files
            for _, _, kind in doc.priority_regions
        ):
            raise PaperDeltaError("SCOPE_EMPTY", msg("scope.no_regions"))
    bound = [
        paper.documents[file].span(start, end)
        for file, locations in covered.items()
        for start, end in locations
    ]
    numeric_bound = list(bound)
    for item in report["claims"].values():
        if location := item.get("location"):
            bound.append(paper.documents[location["file"]].span(location["start"], location["end"]))
    excluded = []
    for name, declaration in config.coverage_exclusions.items():
        state = {"id": name, "reason": declaration.reason, "status": "stale"}
        coverage["exclusions"].append(state)
        try:
            document = paper.document(declaration.file)
            span = document.locate(declaration.anchor)
            document.validate_numeric_span(span)
            state["location"] = span.to_dict()
            if any(_overlaps(span, other) for other in bound):
                raise PaperDeltaError("EXCLUSION_BOUND", msg("scope.bound"))
            if any(_overlaps(span, other) for other in excluded):
                raise PaperDeltaError("EXCLUSION_OVERLAP", msg("scope.overlap"))
            if context_hash(document, span) != declaration.context_hash:
                raise PaperDeltaError("EXCLUSION_STALE", msg("scope.stale"))
            excluded.append(span)
            state["status"] = "active"
        except PaperDeltaError as exc:
            state["error"] = exc.code
            report["diagnostics"].append(
                {
                    "id": f"exclusion:{name}/{exc.code}",
                    "rule": exc.code,
                    "subject": f"exclusion:{name}",
                    "severity": "unknown",
                    "message": str(exc),
                    **({"location": state["location"]} if "location" in state else {}),
                }
            )
    numbers = [span for doc in paper.documents.values() for span in doc.numbers()]
    coverage["candidate_numbers"] = len(numbers)
    coverage["unbound_numbers"] = []
    for span in numbers:
        if any(_overlaps(span, other) for other in numeric_bound):
            continue
        if any(_overlaps(span, other) for other in excluded):
            continue
        key = "unbound_numbers" if _selected(scope, paper, span) else "outside_scope_numbers"
        coverage[key].append(span.to_dict())


def change_scope(
    project: Project,
    *,
    config_path="paperdelta.yaml",
    action,
    files=None,
    regions=None,
    require_complete=None,
    candidate_id=None,
    name=None,
    reason=None,
    accept=False,
):
    # Import here: the check pipeline calls apply_coverage in this module.
    from paperdelta.analysis import check_configuration
    from paperdelta.builder import anchor_for_span
    from paperdelta.onboarding import scan_project

    config, identity = load_config(project, config_path)
    value = config.model_dump()
    value["schema_version"] = max(2, value["schema_version"])
    if action == "set":
        value["review_scope"] = validate_record(
            ReviewScope,
            {
                "files": [project.relative(project.path(file)) for file in files or []],
                "regions": regions or [],
            },
            "SCOPE_SELECTION",
        ).model_dump()
    elif action == "clear":
        value["review_scope"] = None
    elif action == "exclude":
        if name in config.coverage_exclusions:
            raise PaperDeltaError("EXCLUSION_EXISTS", msg("scope.exists", name=name))
        scan = scan_project(project, config_path)
        choice = next(
            (item for item in scan["candidates"] if item["candidate_id"] == candidate_id), None
        )
        if choice is None:
            raise PaperDeltaError("BUILDER_SELECTION", msg("builder.selection", value=candidate_id))
        paper = PaperIndex(project, config.paper)
        document = paper.document(choice["file"])
        span = document.span(choice["start"], choice["end"])
        try:
            anchor = anchor_for_span(document, span)
        except PaperDeltaError:
            # An exclusion must expire when its number changes; an exact, unique
            # token is appropriate here, unlike an editable numeric binding.
            anchor = Anchor(
                exact=span.text,
                parser=document.parser if getattr(document, "format", "latex") == "pdf" else None,
            )
            located = document.locate(anchor)
            if (located.start, located.end) != (span.start, span.end):
                raise PaperDeltaError("EXCLUSION_INVALID", msg("scope.invalid")) from None
        declaration = validate_record(
            CoverageExclusion,
            {
                "file": span.file,
                "anchor": anchor.model_dump(),
                "reason": reason,
                "context_hash": context_hash(document, span),
            },
            "EXCLUSION_SCHEMA",
        )
        value["coverage_exclusions"][name] = declaration.model_dump()
    elif action == "remove-exclusion":
        if name not in config.coverage_exclusions:
            raise PaperDeltaError("EXCLUSION_MISSING", msg("scope.missing", name=name))
        del value["coverage_exclusions"][name]
    else:
        raise PaperDeltaError("SCOPE_ACTION", msg("scope.action"))
    if require_complete is not None:
        value["require_complete_coverage"] = require_complete
    from paperdelta.config_versions import upgrade_layout_schema

    upgrade_layout_schema(value)
    proposed = validate_record(Config, value, "SCOPE_SCHEMA")
    report = check_configuration(project, proposed, config_path, identity)
    if action == "exclude":
        state = next(
            (item for item in report["coverage"]["exclusions"] if item["id"] == name), None
        )
        if state is None or state["status"] != "active":
            raise PaperDeltaError("EXCLUSION_INVALID", msg("scope.invalid"))
    if action == "set":
        paper = PaperIndex(project, proposed.paper)
        for file in proposed.review_scope.files:
            paper.document(file)
        if any(item["rule"] == "SCOPE_EMPTY" for item in report["diagnostics"]):
            raise PaperDeltaError("SCOPE_SELECTION", msg("scope.no_regions"))
    result = {
        "status": "preview",
        "before": config.model_dump(),
        "after": proposed.model_dump(),
        "preview": report,
    }
    if accept:
        with _write_lock(project):
            for path, expected in report["input_hashes"].items():
                if sha256(project.read(path)) != expected:
                    raise PaperDeltaError(
                        "STALE_PROPOSAL", msg("error.STALE_PROPOSAL.3", path=path)
                    )
            backup = f".paperdelta/config-backups/{uuid.uuid4().hex}.yaml"
            project.write(backup, project.read(config_path), exclusive=True)
            project.write(config_path, config_text(proposed).encode("utf-8"))
        result.update(status="accepted", backup=backup)
    return result


def register_commands(commands):
    scope = commands.add_parser("scope", help=tr("scope.help"))
    actions = scope.add_subparsers(dest="scope_action", required=True)
    for action in ("show", "set", "clear", "exclude", "remove-exclusion"):
        child = actions.add_parser(action, help=tr("scope.help_" + action))
        child.add_argument(
            "--format", choices=["text", "json"], default="text", help=tr("cli.format")
        )
        if action != "show":
            child.add_argument("--accept", action="store_true", help=tr("scope.accept"))
        if action in {"set", "clear"}:
            policy = child.add_mutually_exclusive_group()
            policy.add_argument(
                "--require-complete",
                dest="complete",
                action="store_const",
                const=True,
                default=None,
                help=tr("scope.complete"),
            )
            policy.add_argument(
                "--allow-incomplete",
                dest="complete",
                action="store_const",
                const=False,
                help=tr("scope.incomplete"),
            )
        if action == "set":
            child.add_argument("--file", action="append", default=[], help=tr("scope.file"))
            child.add_argument(
                "--region",
                choices=["abstract", "table"],
                action="append",
                default=[],
                help=tr("scope.region"),
            )
        if action in {"exclude", "remove-exclusion"}:
            child.add_argument("--name", required=True, help=tr("scope.name"))
        if action == "exclude":
            child.add_argument("--candidate", required=True, help=tr("cli.repair_candidate"))
            child.add_argument("--reason", required=True, help=tr("scope.reason"))


def run_command(project, arguments):
    from paperdelta.analysis import check_project
    from paperdelta.reports import text_report
    from paperdelta.storage import json_text

    if arguments.scope_action == "show":
        report = check_project(project.root, arguments.config)
        result = {"status": "current", "coverage": report["coverage"], "preview": report}
    else:
        result = change_scope(
            project,
            config_path=arguments.config,
            action=arguments.scope_action,
            files=getattr(arguments, "file", None),
            regions=getattr(arguments, "region", None),
            require_complete=getattr(arguments, "complete", None),
            candidate_id=getattr(arguments, "candidate", None),
            name=getattr(arguments, "name", None),
            reason=getattr(arguments, "reason", None),
            accept=arguments.accept,
        )
    if arguments.format == "json":
        print(json_text(result), end="")
    else:
        print(tr("scope.result", status=tr("scope.status_" + result["status"])))
        if "after" in result:
            print(
                json_text(
                    {
                        key: result["after"][key]
                        for key in (
                            "review_scope",
                            "coverage_exclusions",
                            "require_complete_coverage",
                        )
                    }
                ),
                end="",
            )
        print(text_report(result["preview"]), end="")
        if "backup" in result:
            print(tr("scope.backup", path=result["backup"]))
    return 0
