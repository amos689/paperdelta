"""Portable reports rendered entirely from the checker's evidence model."""

from __future__ import annotations

from paperdelta.errors import PaperDeltaError
from paperdelta.html_report import html_report as html_report
from paperdelta.i18n import msg, tr, translated
from paperdelta.storage import Project, json_text


def text_report(report: dict) -> str:
    counts = report["coverage"]
    lines = [
        tr("report.title"),
        tr(
            "report.counts",
            confirmed=counts["confirmed"],
            passed=counts["pass"],
            mismatch=counts["mismatch"],
            unknown=counts["unknown"],
        ),
        tr(
            "report.coverage",
            unbound=len(counts["unbound_numbers"]),
            unsupported=len(counts["unsupported"]),
        ),
        tr("report.figures", count=len(counts["unregistered_figures"])),
    ]
    for item in report["diagnostics"]:
        location = item.get("location", {})
        where = f"{location['file']}:{location['line']}" if location else item["subject"]
        severity = tr("status." + item["severity"]).upper()
        lines.append(f"{severity} {where} [{item['rule']}] {translated(item['message'])}")
    if report["baseline"]:
        lines.append(
            tr("report.baseline", count=len(report["changes"]), name=report["baseline"]["name"])
        )
    else:
        lines.append(tr("report.no_baseline"))
    for name, state in report["claims"].items():
        lines.append(
            tr(
                "report.review",
                name=name,
                review=tr("status." + state.get("review", "unreviewed")),
                status=tr("status." + state["status"]),
            )
        )
    return "\n".join(lines) + "\n"


def markdown_report(report: dict) -> str:
    # Indented output avoids letting source text close a Markdown fence.
    output = (
        "# "
        + tr("report.markdown_title")
        + "\n\n"
        + "\n".join("    " + line for line in text_report(report).splitlines())
    )
    output += "\n\n## " + tr("report.changes") + "\n\n"
    for change in report["changes"]:
        output += "    " + json_text(change).replace("\n", "\n    ").rstrip() + "\n\n"
    output += "\n## " + tr("report.impacts") + "\n\n"
    for group in report["impact_groups"]:
        output += "    " + json_text(group).replace("\n", "\n    ").rstrip() + "\n\n"
    return output + "\n" + tr("report.scope") + "\n"


def write_reports(project: Project, directory: str, report: dict) -> None:
    outputs = {
        "report.json": json_text(report),
        "report.md": markdown_report(report),
        "report.html": html_report(report),
    }
    protected = {project.path(name) for name in report["input_hashes"]}
    for name in outputs:
        if project.path(f"{directory}/{name}") in protected:
            raise PaperDeltaError("REPORT_OVERWRITE", msg("error.REPORT_OVERWRITE"))
    for name, content in outputs.items():
        project.write(f"{directory}/{name}", content.encode("utf-8"))
