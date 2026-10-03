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
        "--scenario",
        choices=["changed", "baseline", "safe-update"],
        default="changed",
        help=tr("demo.scenario"),
    )
    demo.add_argument("--open", action="store_true", help=tr("demo.open"))
    demo.add_argument("--format", choices=["text", "json"], default="text")


def create_demo(parent: Project, output: str, scenario: str = "changed") -> dict:
    if scenario not in {"changed", "baseline", "safe-update"}:
        raise PaperDeltaError("DEMO_SCENARIO", msg("demo.invalid_scenario"))
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

    copy_resources(files("paperdelta").joinpath("demo_project"))
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
    report = check_project(target, baseline=read_snapshot(project, "before"))
    expected_exit = 0 if scenario == "baseline" else 1
    if report["exit_code"] != expected_exit:
        raise PaperDeltaError("DEMO_INVALID", msg("demo.invalid"))
    write_reports(project, "review", report)
    patch_path = None
    if scenario == "safe-update":
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
    result = create_demo(project, arguments.out, arguments.scenario)
    if arguments.format == "json":
        print(json_text({"command_result_version": 1, "command": "demo", **result}), end="")
    else:
        print(tr("demo.created", project=result["project"], report=result["report"]))
        print(tr("demo.result", code=result["check_exit_code"]))
        print(tr("demo." + arguments.scenario))
    if arguments.open:
        import webbrowser

        webbrowser.open(project.path(result["report"]).as_uri())
    return 0
