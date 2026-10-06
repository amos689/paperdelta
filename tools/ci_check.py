"""Trusted CI wrapper: read a target-commit snapshot, then check current inputs.

Run this wrapper from a trusted PaperDelta checkout/installation environment,
not a version supplied by an untrusted paper PR. It executes Git reads only.
"""

import os
import re
import subprocess
import sys
from html import escape
from pathlib import Path

import yaml

from paperdelta.analysis import check_stored_project
from paperdelta.arguments import ArgumentParser, json_errors
from paperdelta.config import ConfigLoader
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import (
    UnsupportedLanguage,
    language_context,
    msg,
    resolve_language,
    tr,
    translated,
)
from paperdelta.locations import location_label
from paperdelta.models import Config
from paperdelta.pr_review import review_delta
from paperdelta.preferences import read_preferences
from paperdelta.reports import write_reports
from paperdelta.snapshots import snapshot_path
from paperdelta.storage import Project, fingerprint, json_text, parse_json, sha256

METADATA_DIRECTORIES = (".paperdelta/baselines", ".paperdelta/reviews")
NAMED_SECTIONS = ("sources", "metrics", "occurrences", "claims", "figures", "coverage_exclusions")
LIMIT = 32 * 1024 * 1024


class CIProject(Project):
    """Paper inputs and outputs cannot access checkout administration files."""

    def path(self, relative):
        resolved = super().path(relative)
        declared = Path(relative.replace("\\", "/")).parts
        actual = resolved.relative_to(self.root).parts
        if any(part.casefold() == ".git" for part in (*declared, *actual)):
            raise PaperDeltaError("CI_PRIVATE_PATH", msg("ci.error.private_path"))
        return resolved


def git_read(root, *arguments):
    result = subprocess.run(
        ["git", "--literal-pathspecs", "-C", str(root), *arguments],
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise PaperDeltaError("CI_GIT", result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def _target_metadata(project, commit, config_path):
    listed = git_read(
        project.root,
        "ls-tree",
        "-r",
        "-z",
        "--full-tree",
        commit,
        "--",
        config_path,
        *METADATA_DIRECTORIES,
    )
    files = {}
    total = 0
    for entry in listed.split(b"\0"):
        if not entry:
            continue
        header, raw_name = entry.split(b"\t", 1)
        name = raw_name.decode("utf-8")
        if name != config_path and not name.endswith(".json"):
            continue
        mode, kind, identity = header.decode("ascii").split()
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise PaperDeltaError("CI_METADATA_TYPE", msg("ci.error.type_target", name=name))
        size = int(git_read(project.root, "cat-file", "-s", identity))
        total += size
        if size > LIMIT or total > 2 * LIMIT or len(files) >= 2000:
            raise PaperDeltaError("CI_METADATA_LIMIT", msg("ci.error.limit_target"))
        files[name] = git_read(project.root, "cat-file", "blob", identity)
    return files


def _current_metadata(project, config_path):
    names = {config_path}
    for directory in METADATA_DIRECTORIES:
        for path in project.path(directory).rglob("*.json"):
            names.add(path.relative_to(project.root).as_posix())
    if len(names) > 2000:
        raise PaperDeltaError("CI_METADATA_LIMIT", msg("ci.error.count"))
    files = {}
    total = 0
    for name in sorted(names):
        path = project.path(name)
        if path.exists():
            if not path.is_file():
                raise PaperDeltaError("CI_METADATA_TYPE", msg("ci.error.type_current", name=name))
            raw = project.read(name, LIMIT)
            total += len(raw)
            if total > 2 * LIMIT:
                raise PaperDeltaError("CI_METADATA_LIMIT", msg("ci.error.limit_current"))
            files[name] = raw
    return files


def _configuration_changes(before, after):
    if before is None or after is None:
        return {"status": "unavailable", "reason": msg("ci.config_missing")}
    configurations = []
    for side, raw in (("target", before), ("current", after)):
        try:
            if len(raw) > 1024 * 1024:
                raise PaperDeltaError("CI_CONFIG", msg("ci.config_limit"))
            data = yaml.load(raw.decode("utf-8-sig"), Loader=ConfigLoader)
            configurations.append(Config.model_validate(data).model_dump())
        except (PaperDeltaError, yaml.YAMLError, ValueError, RecursionError) as exc:
            return {"status": "unavailable", "reason": msg("ci.parse", side=side, detail=exc)}
    old, new = configurations
    sections = []
    for section in NAMED_SECTIONS:
        left, right = old[section], new[section]
        added, removed = sorted(right.keys() - left.keys()), sorted(left.keys() - right.keys())
        changed = sorted(
            name
            for name in left.keys() & right.keys()
            if fingerprint(left[name]) != fingerprint(right[name])
        )
        if added or removed or changed:
            sections.append(
                {"section": section, "added": added, "removed": removed, "changed": changed}
            )
    settings = sorted(
        key
        for key in old
        if key not in NAMED_SECTIONS and fingerprint(old[key]) != fingerprint(new[key])
    )
    return {
        "status": "changed" if sections or settings else "unchanged",
        "sections": sections,
        "settings": settings,
    }


def _policy_changes(before, after, config_path):
    changes = []
    for name in sorted(before.keys() | after.keys()):
        old, new = before.get(name), after.get(name)
        if old == new:
            continue
        kind = (
            "configuration"
            if name == config_path
            else ("baseline" if name.startswith(".paperdelta/baselines/") else "review_record")
        )
        changes.append(
            {
                "path": name,
                "kind": kind,
                "change": "added" if old is None else "removed" if new is None else "modified",
                "target_hash": sha256(old) if old is not None else None,
                "current_hash": sha256(new) if new is not None else None,
            }
        )
    return changes


def _cell(value):
    value = str(translated(value))
    if len(value) > 512:
        value = value[:512] + tr("ci.truncated_value")
    text = re.sub(
        r"[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]",
        lambda match: f"\\u{ord(match[0]):04x}",
        value,
    )
    return "<code>" + escape(text).replace("|", "&#124;") + "</code>"


def ci_summary(result):
    """Localized presentation; stored report/context fields remain canonical."""
    context, report = result["context"], result["report"]
    coverage = report["coverage"]
    lines = [
        tr("ci.title"),
        "",
        tr("ci.exit", code=report["exit_code"]),
        tr(
            "ci.counts",
            confirmed=coverage["confirmed"],
            passed=coverage["pass"],
            mismatch=coverage["mismatch"],
            unknown=coverage["unknown"],
        ),
        tr(
            "ci.coverage",
            unbound=len(coverage["unbound_numbers"]),
            unsupported=len(coverage["unsupported"]),
            figures=len(coverage["unregistered_figures"]),
        ),
        "",
        tr("ci.target", value=_cell(context["base_commit"])),
        tr("ci.baseline", value=_cell(tr("ci.status." + context["baseline_status"]))),
        "",
        tr("ci.changes_title"),
        "",
        tr("ci.changes_note"),
        "",
        tr("ci.table"),
        "| --- | --- | --- | --- | --- |",
    ]
    changes = context["policy_changes"]
    delta = context.get("finding_changes")
    if delta:
        transition_lines = [
            "",
            tr("ci.delta.title"),
            "",
            tr("ci.delta.scope"),
            "",
            tr("ci.delta.table"),
            "| --- | --- | --- | --- |",
        ]
        for category in delta["counts"]:
            items = delta[category]
            for item in items[:50]:
                transition_lines.append(
                    "| "
                    + " | ".join(
                        _cell(value)
                        for value in (
                            tr("ci.delta." + category),
                            item["subject"],
                            tr("status." + item["before"]) if item["before"] else "—",
                            tr("status." + item["after"]) if item["after"] else "—",
                        )
                    )
                    + " |"
                )
        if not any(delta["counts"].values()):
            transition_lines.append(tr("ci.delta.none"))
        if delta["comparison"] == "unavailable":
            transition_lines.extend(["", tr("ci.delta.unavailable")])
        elif not delta["same_baseline_contract"]:
            transition_lines.extend(["", tr("ci.delta.contract")])
        transition_lines.extend(["", tr("ci.delta.full"), ""])
        # Put the transition review before the existing declaration-change table.
        lines[8:8] = transition_lines
    for item in changes[:50]:
        cells = [
            tr("ci.status." + item["kind"]),
            item["path"],
            tr("ci.status." + item["change"]),
            item["target_hash"],
            item["current_hash"],
        ]
        lines.append("| " + " | ".join(_cell(value) for value in cells) + " |")
    if not changes:
        lines.append(tr("ci.no_changes"))
    if len(changes) > 50:
        lines.extend(["", tr("ci.more_changes", count=len(changes))])
    configuration = context["configuration"]
    lines.extend(["", tr("ci.semantics", status=tr("ci.status." + configuration["status"])), ""])
    if configuration["status"] == "unavailable":
        lines.append(_cell(configuration["reason"]))
    else:
        for section in configuration["sections"]:
            lines.append(
                tr(
                    "ci.section",
                    section=_cell(section["section"]),
                    added=_cell(section["added"][:50]),
                    removed=_cell(section["removed"][:50]),
                    changed=_cell(section["changed"][:50]),
                )
            )
        if configuration["settings"]:
            lines.append(tr("ci.settings", value=_cell(configuration["settings"])))
        lines.append(tr("ci.lists_note"))
    lines.extend(["", tr("ci.findings_title"), ""])
    for item in report["diagnostics"][:50]:
        location = item.get("location", {})
        where = location_label(location) if location else item["subject"]
        lines.append(
            tr(
                "ci.finding",
                rule=_cell(item["rule"]),
                where=_cell(where),
                message=_cell(item["message"]),
            )
        )
    if not report["diagnostics"]:
        lines.append(tr("ci.no_findings"))
    if len(report["diagnostics"]) > 50:
        lines.append(tr("ci.more_findings", count=len(report["diagnostics"])))
    lines.extend(["", tr("ci.artifacts"), tr("ci.scope"), ""])
    summary = "\n".join(lines)
    encoded = summary.encode("utf-8")
    if len(encoded) > 900 * 1024:
        summary = encoded[: 900 * 1024].decode("utf-8", errors="ignore").rsplit("\n", 1)[0]
        summary += "\n\n" + tr("ci.truncated") + "\n"
    return summary


def run_ci(root, base_commit, name, output, config_path="paperdelta.yaml"):
    project = CIProject(root)
    project.path(config_path)
    config_path = Path(config_path.replace("\\", "/")).as_posix()
    if ".." in Path(config_path).parts:
        raise PaperDeltaError("CI_CONFIG", msg("ci.error.config"))
    if not re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", base_commit):
        raise PaperDeltaError("CI_BASE", msg("ci.error.sha"))
    top = git_read(project.root, "rev-parse", "--show-toplevel").decode("utf-8").strip()
    if Path(top).resolve() != project.root:
        raise PaperDeltaError("CI_ROOT", msg("ci.error.root"))
    if git_read(project.root, "cat-file", "-t", base_commit).strip() != b"commit":
        raise PaperDeltaError("CI_BASE", msg("ci.error.commit"))
    path = snapshot_path(name)
    target = _target_metadata(project, base_commit, config_path)
    current = _current_metadata(project, config_path)
    baseline = None
    context = {
        "ci_context_schema_version": 2,
        "base_commit": base_commit,
        "snapshot_path": path,
        "baseline_status": "unavailable",
        "policy_changes": _policy_changes(target, current, config_path),
        "configuration": _configuration_changes(target.get(config_path), current.get(config_path)),
    }
    if path in target:
        raw = target[path]
        baseline = parse_json(raw.decode("utf-8"))
        context.update({"baseline_status": "read_from_target_commit", "snapshot_hash": sha256(raw)})
    report = check_stored_project(project, config_path, baseline)
    context["finding_changes"] = review_delta(
        report,
        baseline,
        context["configuration"],
        same_baseline_contract=bool(
            baseline
            and config_path in target
            and baseline["report"]["input_hashes"].get(config_path) == sha256(target[config_path])
        ),
    )
    if _current_metadata(project, config_path) != current:
        raise PaperDeltaError("CI_INPUT_CHANGED", msg("ci.error.changed"))
    protected = {project.path(p) for p in report["input_hashes"]} | {
        project.path(p) for p in target.keys() | current.keys()
    }
    for filename in (
        "report.json",
        "report.md",
        "report.html",
        "report.sarif",
        "ci-context.json",
        "ci-summary.md",
    ):
        if project.path((Path(output) / filename).as_posix()) in protected:
            raise PaperDeltaError("CI_OUTPUT", msg("ci.error.output"))
    result = {"context": context, "report": report}
    write_reports(project, output, report)
    project.write((Path(output) / "ci-context.json").as_posix(), json_text(context).encode("utf-8"))
    project.write((Path(output) / "ci-summary.md").as_posix(), ci_summary(result).encode("utf-8"))
    return result


def _append_job_summary(content, path):
    if path:
        with Path(path).open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("\n" + content)


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

    def early(name):
        values = [
            value.split("=", 1)[1]
            if "=" in value
            else (arguments[i + 1] if i + 1 < len(arguments) else None)
            for i, value in enumerate(arguments)
            if value == name or value.startswith(name + "=")
        ]
        return values[-1] if values else None

    try:
        requested = early("--lang")
        root = early("--project")
        preferences = {}
        if (
            root
            and requested in (None, "auto")
            and os.environ.get("PAPERDELTA_LANG") in (None, "", "auto")
        ):
            preferences = read_preferences(Project(root))
        selected = resolve_language(requested, preferences=preferences)
    except (UnsupportedLanguage, PaperDeltaError, OSError) as exc:
        print(
            json_text(
                {
                    "code": getattr(
                        exc,
                        "code",
                        "LANGUAGE" if isinstance(exc, UnsupportedLanguage) else "IO_ERROR",
                    ),
                    "error": str(exc),
                }
            )
        )
        return 2
    token = json_errors.set(True)
    try:
        with language_context(selected):
            return _main(arguments)
    finally:
        json_errors.reset(token)


def _main(argv):
    parser = ArgumentParser(description=tr("ci.description"))
    parser.add_argument("--project", required=True, help=tr("ci.help.project"))
    parser.add_argument("--base-commit", required=True, help=tr("ci.help.base"))
    parser.add_argument("--snapshot", required=True, help=tr("ci.help.snapshot"))
    parser.add_argument("--report", default="build/paperdelta", help=tr("ci.help.report"))
    parser.add_argument("--config", default="paperdelta.yaml", help=tr("ci.help.config"))
    parser.add_argument(
        "--summary-file", default=os.environ.get("GITHUB_STEP_SUMMARY"), help=tr("ci.help.summary")
    )
    parser.add_argument("--lang", help=tr("ci.help.language"))
    args = parser.parse_args(argv)
    summary_file = None
    try:
        if args.summary_file:
            candidate = Path(args.summary_file).resolve()
            if candidate.is_relative_to(Path(args.project).resolve()):
                raise PaperDeltaError("CI_OUTPUT", msg("ci.error.summary"))
            summary_file = candidate
        result = run_ci(args.project, args.base_commit, args.snapshot, args.report, args.config)
        _append_job_summary(ci_summary(result), summary_file)
    except (PaperDeltaError, UnicodeDecodeError, OSError) as exc:
        code = getattr(exc, "code", "IO_ERROR")
        detail = translated(getattr(exc, "message", str(exc)))
        message = tr("ci.incomplete") + "\n\n" + _cell(code + ": " + detail) + "\n"
        try:
            _append_job_summary(message, summary_file)
        except OSError:
            pass
        print(json_text({"code": code, "error": str(exc), "display_message": detail}))
        return 2
    print(json_text(result))
    return result["report"]["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
