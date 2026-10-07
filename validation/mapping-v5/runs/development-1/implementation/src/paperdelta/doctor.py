"""Read-only diagnosis of the local installation and paper configuration."""

import importlib.metadata
import importlib.util
import platform
import shutil

from paperdelta import __version__
from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg, tr, translated
from paperdelta.preferences import read_preferences
from paperdelta.storage import Project


def diagnose(project: Project, config_path="paperdelta.yaml", *, require_mcp=False) -> dict:
    checks = []

    def add(name, status, message, action=None, **details):
        checks.append(
            {"id": name, "status": status, "message": message, "action": action, **details}
        )

    add(
        "python",
        "ok",
        msg("doctor.python", version=platform.python_version()),
        system=platform.system(),
        architecture=platform.machine(),
    )
    try:
        installed = importlib.metadata.version("paperdelta")
    except importlib.metadata.PackageNotFoundError:
        installed = None
    add(
        "installation",
        "ok" if installed == __version__ else "warning",
        msg("doctor.installation", runtime=__version__, installed=installed or "unknown"),
        msg("doctor.install_action") if installed != __version__ else None,
    )
    for package in ("pydantic", "PyYAML", "pylatexenc"):
        try:
            version = importlib.metadata.version(package)
            add(
                "dependency:" + package,
                "ok",
                msg("doctor.dependency", name=package, version=version),
            )
        except importlib.metadata.PackageNotFoundError:
            add(
                "dependency:" + package,
                "error",
                msg("doctor.missing", name=package),
                msg("doctor.install_action"),
            )
    if importlib.util.find_spec("mcp") is None:
        add(
            "mcp",
            "error" if require_mcp else "optional",
            msg("doctor.mcp_absent"),
            msg("doctor.mcp_action"),
        )
    else:
        try:
            from paperdelta.mcp_server import create_server

            create_server(project, config_path)
            add("mcp", "ok", msg("doctor.mcp_ready"))
        except PaperDeltaError as error:
            add(
                "mcp",
                "error" if require_mcp else "warning",
                error.message,
                msg("doctor.mcp_action"),
                code=error.code,
            )
    add(
        "git",
        "ok" if shutil.which("git") else "optional",
        msg("doctor.git_ready" if shutil.which("git") else "doctor.git_absent"),
    )
    try:
        preferences = read_preferences(project)
        add(
            "preferences",
            "ok",
            msg("doctor.preferences", language=preferences.get("language", "auto")),
        )
    except PaperDeltaError as error:
        add(
            "preferences", "error", error.message, msg("doctor.preferences_action"), code=error.code
        )
    report = None
    try:
        config, _ = load_config(project, config_path)
        add(
            "configuration",
            "ok",
            msg("doctor.config_ready", path=config_path),
            sources=len(config.sources),
            metrics=len(config.metrics),
        )
        report = check_project(project.root, config_path)
        for finding in report["diagnostics"]:
            code = finding["rule"]
            status = (
                "error" if finding["severity"] == "unknown" and code != "NO_BINDINGS" else "warning"
            )
            if code == "NO_BINDINGS":
                action = msg("doctor.bind_action")
            elif code.startswith("ANCHOR_"):
                action = msg("doctor.anchor_action")
            elif code in {"FILE_UNAVAILABLE", "MISSING_COLUMN", "EMPTY_SELECTION", "SEED_SET"}:
                action = msg("doctor.source_action")
            elif code in {"DYNAMIC_TEX", "UNSUPPORTED_SPAN", "UNSUPPORTED_MACRO", "LATEX_PARSE"}:
                action = msg("doctor.tex_action")
            else:
                action = msg("doctor.check_action")
            add("project:" + finding["id"], status, finding["message"], action, code=code)
    except PaperDeltaError as error:
        add(
            "configuration",
            "error",
            error.message,
            msg("doctor.config_action", path=config_path),
            code=error.code,
        )
    errors = sum(check["status"] == "error" for check in checks)
    return {
        "doctor_schema_version": 1,
        "tool_version": __version__,
        "status": "needs_attention" if errors else "ready",
        "exit_code": 2 if errors else 0,
        "checks": checks,
        "required_errors": errors,
        "warnings": sum(check["status"] == "warning" for check in checks),
        "project_check_exit_code": report["exit_code"] if report else None,
        "notice": msg("doctor.notice"),
    }


def doctor_text(result: dict) -> str:
    lines = [
        tr("doctor.title"),
        tr("doctor.summary", errors=result["required_errors"], warnings=result["warnings"]),
    ]
    for check in result["checks"]:
        lines.append(
            f"[{tr('status.' + check['status'])}] {check['id']}: {translated(check['message'])}"
        )
        if check["action"]:
            lines.append("  " + translated(check["action"]))
    lines.append(translated(result["notice"]))
    return "\n".join(lines) + "\n"
