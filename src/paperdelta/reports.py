"""Portable reports rendered entirely from the checker's evidence model."""

from __future__ import annotations

from paperdelta.errors import PaperDeltaError
from paperdelta.html_report import html_report as html_report
from paperdelta.i18n import msg, tr, translated
from paperdelta.i18n import translated as translate_location
from paperdelta.locations import location_label
from paperdelta.sarif import sarif_report
from paperdelta.storage import Project, json_text


def text_report(report: dict) -> str:
    counts = report["coverage"]
    watch = report.get("watch")
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
    if watch:
        lines.insert(
            1,
            tr(
                "watch.banner",
                state=tr("watch.state_" + watch["state"]),
                generation=watch["generation"],
            ),
        )
    lines.append(
        tr(
            "report.scope_counts",
            outside=len(counts.get("outside_scope_numbers", [])),
            excluded=sum(item["status"] == "active" for item in counts.get("exclusions", [])),
        )
    )
    if counts.get("review_scope"):
        lines.append(tr("report.selected_scope", value=json_text(counts["review_scope"]).strip()))
    for exclusion in counts.get("exclusions", []):
        lines.append(
            tr(
                "report.exclusion",
                name=exclusion["id"],
                status=tr("scope.exclusion_" + exclusion["status"]),
                reason=exclusion["reason"],
            )
        )
    for action in report.get("actions", []):
        lines.append(
            tr(
                "actions.item",
                action=tr("actions." + action["kind"]),
                count=len(action["subjects"]),
            )
        )
    for name, state in report.get("provenance", {}).items():
        lines.append(
            name
            + ": "
            + tr("workflow.unchanged" if state["status"] == "pass" else "status." + state["status"])
        )
        lines.append(
            tr(
                "provenance.observed"
                if state.get("method") == "observed_command"
                else "provenance.declared"
            )
        )
        lines.append(
            tr(
                "workflow.io",
                inputs=", ".join(state.get("inputs", [])),
                outputs=", ".join(state.get("outputs", [])),
            )
        )
    from paperdelta.revisions import revision_list

    lines.append(tr("revisions.title"))
    lines.append(tr("revisions.notice"))
    for item in revision_list(report):
        lines.append(
            item["subject"]
            + " · "
            + tr("revisions." + item["kind"])
            + " · "
            + tr("status." + item["status"])
        )
        lines.append(tr("revisions." + item["action"]))
        if item["expected"] is not None:
            lines.append(str(item["actual"]) + " → " + str(item["expected"]))
    for export in report.get("exports", []):
        lines.append(
            tr(
                "pdf.export_line",
                file=export["file"],
                source=export["source"],
                metric=export["metric"] or "—",
                status=tr("pdf.export_" + export["status"]),
            )
        )
    for item in report["diagnostics"]:
        location = item.get("location", {})
        where = translate_location(location_label(location)) if location else item["subject"]
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
    from paperdelta.pdf_previews import pdf_previews

    outputs = {
        "report.json": json_text(report),
        "report.md": markdown_report(report),
        "report.html": html_report(report, previews=pdf_previews(project, report)),
        "report.sarif": json_text(sarif_report(report, f"{directory}/report.html")),
    }
    protected = {project.path(name) for name in report["input_hashes"]}
    protected.add(project.path(report["config_path"]))
    for name in outputs:
        if project.path(f"{directory}/{name}") in protected:
            raise PaperDeltaError("REPORT_OVERWRITE", msg("error.REPORT_OVERWRITE"))
    for name, content in outputs.items():
        project.write(f"{directory}/{name}", content.encode("utf-8"))
