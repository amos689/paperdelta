"""Previewed, backed-up declarations for companion manuscripts and PDF regions."""

from __future__ import annotations

import uuid

from paperdelta.analysis import check_configuration
from paperdelta.config import config_text, load_config
from paperdelta.documents import PaperIndex
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg, tr, translated
from paperdelta.models import Config
from paperdelta.patches import _write_lock
from paperdelta.records import validate_record
from paperdelta.storage import decimal_value, json_text, sha256


def change_manuscripts(
    project,
    *,
    action,
    file,
    export_of=None,
    region=None,
    name=None,
    accept=False,
    config_path="paperdelta.yaml",
):
    config, identity = load_config(project, config_path)
    value = config.model_dump()
    value["schema_version"] = max(4, value["schema_version"])
    paper = value["paper"]
    companions = paper.setdefault("companions", [])
    file = project.relative(project.path(file))
    entries = [paper, *companions]
    selected = next(
        (item for item in entries if project.relative(project.path(item["entry"])) == file), None
    )
    if action == "add":
        if selected is not None:
            raise PaperDeltaError("DOCUMENT_DUPLICATE", msg("document.duplicate"))
        companions.append(
            {
                "entry": file,
                **({"export_of": project.relative(project.path(export_of))} if export_of else {}),
            }
        )
    elif action == "remove":
        if selected is None or selected is paper:
            raise PaperDeltaError("MANUSCRIPT_SELECTION", msg("manuscript.remove_primary"))
        index = PaperIndex(project, config.paper)
        related = index.members[file]
        if any(
            project.relative(project.path(item.file)) in related
            for item in [
                *config.occurrences.values(),
                *config.claims.values(),
                *config.coverage_exclusions.values(),
            ]
        ) or any(item.get("export_of") == selected["entry"] for item in entries):
            raise PaperDeltaError("MANUSCRIPT_REFERENCED", msg("manuscript.referenced", file=file))
        companions.remove(selected)
    elif action in {"region-add", "region-remove"}:
        if selected is None:
            raise PaperDeltaError("MANUSCRIPT_SELECTION", msg("document.unreachable", file=file))
        regions = selected.setdefault("pdf_regions", [])
        if action == "region-add":
            regions.append(region)
        else:
            if not any(item["name"] == name for item in regions):
                raise PaperDeltaError("PDF_REGION", msg("pdf.region_missing", name=name))
            regions[:] = [item for item in regions if item["name"] != name]
    else:
        raise PaperDeltaError("MANUSCRIPT_SELECTION", msg("manuscript.action"))
    proposed = validate_record(Config, value, "MANUSCRIPT_SCHEMA")
    index = PaperIndex(project, proposed.paper)
    hashes = {config_path: identity, **{path: doc.hash for path, doc in index.documents.items()}}
    report = check_configuration(project, proposed, config_path, identity)
    for path, expected in report["input_hashes"].items():
        if path in hashes and hashes[path] != expected:
            raise PaperDeltaError("STALE_PROPOSAL", msg("error.STALE_PROPOSAL.3", path=path))
        hashes[path] = expected
    result = {
        "status": "preview",
        "before": config.model_dump(),
        "after": proposed.model_dump(),
        "preview": report,
    }
    if accept:
        with _write_lock(project):
            for path, expected in hashes.items():
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
    manuscripts = commands.add_parser("manuscript", help=tr("manuscript.help"))
    pdf = commands.add_parser("pdf", help=tr("pdf.help"))
    for parent, actions in (
        (manuscripts, ("list", "add", "remove")),
        (pdf, ("inspect", "region-add", "region-remove")),
    ):
        children = parent.add_subparsers(dest="document_action", required=True)
        for action in actions:
            child = children.add_parser(action, help=tr("manuscript." + action))
            child.add_argument(
                "--format", choices=["text", "json"], default="text", help=tr("cli.format")
            )
            if action != "list":
                child.add_argument("--file", required=True, help=tr("manuscript.file"))
            if action not in {"list", "inspect"}:
                child.add_argument("--accept", action="store_true", help=tr("scope.accept"))
            if action == "add":
                child.add_argument("--export-of", help=tr("manuscript.export_of"))
            if action in {"region-add", "region-remove"}:
                child.add_argument("--name", required=True, help=tr("pdf.region_name"))
            if action == "region-add":
                child.add_argument("--page", type=int, required=True, help=tr("pdf.page"))
                child.add_argument(
                    "--bbox",
                    nargs=4,
                    required=True,
                    metavar=("X0", "TOP", "X1", "BOTTOM"),
                    help=tr("pdf.bbox"),
                )
                child.add_argument(
                    "--kind",
                    choices=["text", "table", "abstract"],
                    default="text",
                    help=tr("pdf.kind"),
                )


def run_command(project, arguments):
    from paperdelta.reports import text_report

    action = arguments.document_action
    if action in {"list", "inspect"}:
        config, _ = load_config(project, arguments.config)
        if action == "list":
            result = {
                "status": "current",
                "manuscripts": [
                    item.model_dump(exclude={"companions"})
                    for item in [config.paper, *config.paper.companions]
                ],
            }
        else:
            document = PaperIndex(project, config.paper).document(arguments.file)
            if getattr(document, "format", None) != "pdf":
                raise PaperDeltaError("DOCUMENT_FORMAT", msg("pdf.options_format"))
            result = {
                "file": document.file,
                "parser": document.parser,
                "pages": [{"page": page, "bbox": box} for page, box in document.page_boxes.items()],
                "regions": [item.model_dump() for item in document.regions],
                "issues": document.issues,
                "numbers": [item.to_dict() for item in document.numbers()],
            }
    else:
        region = (
            {
                "name": arguments.name,
                "page": arguments.page,
                "bbox": [decimal_value(item) for item in arguments.bbox],
                "kind": arguments.kind,
            }
            if action == "region-add"
            else None
        )
        result = change_manuscripts(
            project,
            action=action,
            file=arguments.file,
            export_of=getattr(arguments, "export_of", None),
            region=region,
            name=getattr(arguments, "name", None),
            accept=arguments.accept,
            config_path=arguments.config,
        )
    if arguments.format == "json":
        print(json_text(result), end="")
    else:
        print(tr("manuscript.result"))
        print(json_text(translated(result.get("after", {}).get("paper", result))), end="")
        if "preview" in result:
            print(tr("scope.result", status=tr("scope.status_" + result["status"])))
            print(text_report(result["preview"]), end="")
        if "backup" in result:
            print(tr("scope.backup", path=result["backup"]))
    return 0
