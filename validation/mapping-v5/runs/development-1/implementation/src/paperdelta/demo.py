"""An offline first report, available from the installed core wheel."""

from __future__ import annotations

from importlib.resources import files

from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg, tr
from paperdelta.patches import create_patch, preview_patch
from paperdelta.reports import write_reports
from paperdelta.snapshots import create_snapshot, read_snapshot
from paperdelta.storage import Project, json_text


def register_commands(commands):
    demo = commands.add_parser("demo", help=tr("demo.help"))
    demo.add_argument("--out", default="paperdelta-demo", help=tr("demo.out"))
    demo.add_argument(
        "--document",
        choices=["latex", "docx", "pdf", "markdown", "quarto"],
        default="latex",
        help=tr("demo.document"),
    )
    demo.add_argument(
        "--scenario",
        choices=["changed", "baseline", "safe-update"],
        default="changed",
        help=tr("demo.scenario"),
    )
    demo.add_argument("--open", action="store_true", help=tr("demo.open"))
    demo.add_argument("--format", choices=["text", "json"], default="text")


def create_demo(
    parent: Project, output: str, scenario: str = "changed", document: str = "latex"
) -> dict:
    if scenario not in {"changed", "baseline", "safe-update"}:
        raise PaperDeltaError("DEMO_SCENARIO", msg("demo.invalid_scenario"))
    if document not in {"latex", "docx", "pdf", "markdown", "quarto"}:
        raise PaperDeltaError("DOCUMENT_FORMAT", msg("document.format", file=document))
    if document == "docx":
        from paperdelta.docx_document import DocxDocument

        # Diagnose absent optional dependencies before creating the output directory.
        DocxDocument(
            "paper.docx", files("paperdelta").joinpath("demo_word/paper.docx").read_bytes()
        )
    if document == "pdf":
        from paperdelta.pdf_document import PdfDocument

        pdf = PdfDocument(
            "paper.pdf", files("paperdelta").joinpath("demo_pdf/paper.pdf").read_bytes()
        )
    target = parent.path(output)
    try:
        target.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise PaperDeltaError("ALREADY_EXISTS", msg("demo.exists", path=output)) from exc
    project = Project(target)

    def copy_resources(source, prefix=""):
        for child in source.iterdir():
            name = prefix + child.name
            if child.is_dir():
                if child.name != "__pycache__":
                    copy_resources(child, name + "/")
            elif not child.name.endswith((".pyc", ".pyo")):
                project.write(name, child.read_bytes(), exclusive=True)

    copy_resources(
        files("paperdelta").joinpath(
            {
                "latex": "demo_project",
                "docx": "demo_word",
                "pdf": "demo_pdf",
                "markdown": "demo_markdown",
                "quarto": "demo_quarto",
            }[document]
        )
    )
    if document == "pdf":
        from paperdelta.config import config_text, load_config

        config, _ = load_config(project)
        # This is a new, authored demo with known mappings, not a repair of user bindings.
        for binding in [*config.occurrences.values(), *config.claims.values()]:
            if binding.file == "paper.pdf":
                anchor = binding.anchor.table if binding.anchor.table else binding.anchor
                anchor.parser = pdf.parser
        project.write("paperdelta.yaml", config_text(config).encode("utf-8"))
    before = check_project(target)
    if before["exit_code"] != 0:
        raise PaperDeltaError("DEMO_INVALID", msg("demo.invalid"))
    create_snapshot(project, "before", before)
    write_reports(project, "before", before)
    if scenario != "baseline":
        replacements = (
            (b"0.807", b"0.809", b"0.811")
            if scenario == "changed"
            else (b"0.843", b"0.845", b"0.847")
        )
        rows = project.read("results/metrics.csv").splitlines(keepends=True)
        for index, (old, new) in enumerate(
            zip((b"0.839", b"0.841", b"0.843"), replacements, strict=True), start=1
        ):
            rows[index] = rows[index].replace(old, new)
        project.write("results/metrics.csv", b"".join(rows))
        if document == "pdf":
            project.write(
                "source.tex",
                project.read("source.tex").replace(
                    b"84.1", b"80.9" if scenario == "changed" else b"84.5"
                ),
            )
    report = check_project(target, baseline=read_snapshot(project, "before"))
    expected_exit = 0 if scenario == "baseline" else 1
    if report["exit_code"] != expected_exit:
        raise PaperDeltaError("DEMO_INVALID", msg("demo.invalid"))
    write_reports(project, "review", report)
    patch_path = None
    if scenario == "safe-update" and document in {"latex", "markdown", "quarto"}:
        patch = create_patch(project, report)
        patch_path = "changes.pdpatch.json"
        project.write(patch_path, json_text(patch).encode("utf-8"), exclusive=True)
        project.write("changes.diff", preview_patch(project, patch).encode("utf-8"), exclusive=True)
    return {
        "status": "created",
        "scenario": scenario,
        "project": parent.relative(target),
        "report": parent.relative(target / "review/report.html"),
        "check_exit_code": report["exit_code"],
        "expected_check_exit_code": expected_exit,
        "patch": parent.relative(target / patch_path) if patch_path else None,
    }


def run_command(project, arguments):
    result = create_demo(project, arguments.out, arguments.scenario, arguments.document)
    if arguments.format == "json":
        print(json_text({"command_result_version": 1, "command": "demo", **result}), end="")
    else:
        print(tr("demo.created", project=result["project"], report=result["report"]))
        print(tr("demo.result", code=result["check_exit_code"]))
        print(
            tr(
                "document.manual_update"
                if arguments.document in {"docx", "pdf", "markdown", "quarto"}
                else "demo." + arguments.scenario
            )
        )
    if arguments.open:
        import webbrowser

        webbrowser.open(project.path(result["report"]).as_uri())
    return 0
