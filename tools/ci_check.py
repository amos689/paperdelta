"""Trusted CI wrapper: read a target-commit snapshot, then check current inputs.

Run this wrapper from a trusted PaperDelta checkout/installation environment,
not a version supplied by an untrusted paper PR. It executes Git reads only.
"""

import argparse
import os
import re
import subprocess
from html import escape
from pathlib import Path

import yaml

from paperdelta.analysis import check_project
from paperdelta.config import ConfigLoader
from paperdelta.errors import PaperDeltaError
from paperdelta.models import Config
from paperdelta.reports import write_reports
from paperdelta.snapshots import snapshot_path
from paperdelta.storage import Project, fingerprint, json_text, parse_json, sha256

METADATA_DIRECTORIES = (".paperdelta/baselines", ".paperdelta/reviews")
NAMED_SECTIONS = ("sources", "metrics", "occurrences", "claims", "figures")
LIMIT = 32 * 1024 * 1024


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
            raise PaperDeltaError(
                "CI_METADATA_TYPE", f"Target metadata is not a regular file: {name}"
            )
        size = int(git_read(project.root, "cat-file", "-s", identity))
        total += size
        if size > LIMIT or total > 2 * LIMIT or len(files) >= 2000:
            raise PaperDeltaError("CI_METADATA_LIMIT", "Target metadata exceeds the CI read limit")
        files[name] = git_read(project.root, "cat-file", "blob", identity)
    return files


def _current_metadata(project, config_path):
    names = {config_path}
    for directory in METADATA_DIRECTORIES:
        for path in project.path(directory).rglob("*.json"):
            names.add(path.relative_to(project.root).as_posix())
    if len(names) > 2000:
        raise PaperDeltaError("CI_METADATA_LIMIT", "More than 2000 current metadata files")
    files = {}
    total = 0
    for name in sorted(names):
        path = project.path(name)
        if path.exists():
            if not path.is_file():
                raise PaperDeltaError("CI_METADATA_TYPE", f"Metadata is not a file: {name}")
            raw = project.read(name, LIMIT)
            total += len(raw)
            if total > 2 * LIMIT:
                raise PaperDeltaError("CI_METADATA_LIMIT", "Current metadata exceeds 64 MiB")
            files[name] = raw
    return files


def _configuration_changes(before, after):
    if before is None or after is None:
        return {"status": "unavailable", "reason": "Configuration missing on one side"}
    configurations = []
    for side, raw in (("target", before), ("current", after)):
        try:
            if len(raw) > 1024 * 1024:
                raise ValueError("Configuration exceeds 1 MiB")
            data = yaml.load(raw.decode("utf-8-sig"), Loader=ConfigLoader)
            configurations.append(Config.model_validate(data).model_dump())
        except (PaperDeltaError, yaml.YAMLError, ValueError, RecursionError) as exc:
            return {"status": "unavailable", "reason": f"{side}: {exc}"}
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
    value = str(value)
    if len(value) > 512:
        value = value[:512] + "… [truncated; full value in artifacts]"
    text = re.sub(
        r"[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]",
        lambda match: f"\\u{ord(match[0]):04x}",
        value,
    )
    return "<code>" + escape(text).replace("|", "&#124;") + "</code>"


def ci_summary(result):
    """A bounded Markdown summary; full evidence remains in the report artifacts."""
    context, report = result["context"], result["report"]
    coverage = report["coverage"]
    lines = [
        "# PaperDelta CI review",
        "",
        f"Current check exit code: **{report['exit_code']}**.",
        f"{coverage['confirmed']} confirmed: {coverage['pass']} pass, "
        f"{coverage['mismatch']} mismatch, {coverage['unknown']} unknown.",
        f"{len(coverage['unbound_numbers'])} unbound numeric candidates; "
        f"{len(coverage['unsupported'])} unsupported regions; "
        f"{len(coverage['unregistered_figures'])} unregistered figure references.",
        "",
        f"Target commit: {_cell(context['base_commit'])}.",
        f"Historical baseline: {_cell(context['baseline_status'])}.",
        "",
        "## Repository declaration changes",
        "",
        "Compared with the target commit. These changes are separate from numerical "
        "consistency; snapshot and review files are declarations, not authenticated approval.",
        "",
        "| Kind | Path | Change | Target SHA256 | Current SHA256 |",
        "| --- | --- | --- | --- | --- |",
    ]
    changes = context["policy_changes"]
    for item in changes[:50]:
        lines.append(
            "| "
            + " | ".join(
                _cell(item[key])
                for key in ("kind", "path", "change", "target_hash", "current_hash")
            )
            + " |"
        )
    if not changes:
        lines.append("| — | No declaration file changes | — | — | — |")
    if len(changes) > 50:
        lines.extend(["", f"Showing 50 of {len(changes)} changes; see ci-context.json for all."])
    configuration = context["configuration"]
    lines.extend(["", f"Configuration semantics: **{configuration['status']}**.", ""])
    if configuration["status"] == "unavailable":
        lines.append(_cell(configuration["reason"]))
    else:
        for section in configuration["sections"]:
            lines.append(
                f"- {_cell(section['section'])}: added {_cell(section['added'][:50])}; "
                f"removed {_cell(section['removed'][:50])}; "
                f"changed {_cell(section['changed'][:50])}."
            )
        if configuration["settings"]:
            lines.append("- Changed settings: " + _cell(configuration["settings"]) + ".")
        lines.append("Named-ID lists show at most 50 entries per category; full lists are in JSON.")
    lines.extend(["", "## Current findings", ""])
    for item in report["diagnostics"][:50]:
        location = item.get("location", {})
        where = f"{location['file']}:{location['line']}" if location else item["subject"]
        lines.append(f"- {_cell(item['rule'])} at {_cell(where)}: {_cell(item['message'])}")
    if not report["diagnostics"]:
        lines.append("No diagnostics from the declared checks.")
    if len(report["diagnostics"]) > 50:
        lines.append(f"Showing 50 of {len(report['diagnostics'])} diagnostics.")
    lines.extend(
        [
            "",
            "Full artifacts: report.html, report.json, report.md and ci-context.json.",
            "A successful check covers confirmed bindings; it does not certify the whole paper.",
            "",
        ]
    )
    summary = "\n".join(lines)
    encoded = summary.encode("utf-8")
    if len(encoded) > 900 * 1024:
        summary = encoded[: 900 * 1024].decode("utf-8", errors="ignore").rsplit("\n", 1)[0]
        summary += "\n\nSummary truncated; download the full report artifacts.\n"
    return summary


def run_ci(root, base_commit, name, output, config_path="paperdelta.yaml"):
    project = Project(root)
    project.path(config_path)
    config_path = Path(config_path.replace("\\", "/")).as_posix()
    if ".." in Path(config_path).parts:
        raise PaperDeltaError("CI_CONFIG", "Use a canonical project-relative configuration path")
    if not re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", base_commit):
        raise PaperDeltaError("CI_BASE", "Supply the full target commit SHA, not an expression")
    top = git_read(project.root, "rev-parse", "--show-toplevel").decode("utf-8").strip()
    if Path(top).resolve() != project.root:
        raise PaperDeltaError("CI_ROOT", "Run at the paper repository root")
    if git_read(project.root, "cat-file", "-t", base_commit).strip() != b"commit":
        raise PaperDeltaError("CI_BASE", "The target identity must name a commit")
    path = snapshot_path(name)
    target = _target_metadata(project, base_commit, config_path)
    current = _current_metadata(project, config_path)
    baseline = None
    context = {
        "ci_context_schema_version": 1,
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
    report = check_project(project.root, config_path, baseline)
    if _current_metadata(project, config_path) != current:
        raise PaperDeltaError("CI_INPUT_CHANGED", "Declaration files changed while checking")
    protected = {project.path(p) for p in report["input_hashes"]} | {
        project.path(p) for p in target.keys() | current.keys()
    }
    for filename in ("report.json", "report.md", "report.html", "ci-context.json", "ci-summary.md"):
        if project.path((Path(output) / filename).as_posix()) in protected:
            raise PaperDeltaError("CI_OUTPUT", "CI output would overwrite a checked declaration")
    result = {"context": context, "report": report}
    write_reports(project, output, report)
    project.write((Path(output) / "ci-context.json").as_posix(), json_text(context).encode("utf-8"))
    project.write((Path(output) / "ci-summary.md").as_posix(), ci_summary(result).encode("utf-8"))
    return result


def _append_job_summary(content, path):
    if path:
        with Path(path).open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("\n" + content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--base-commit", required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--report", default="build/paperdelta")
    parser.add_argument("--config", default="paperdelta.yaml")
    parser.add_argument("--summary-file", default=os.environ.get("GITHUB_STEP_SUMMARY"))
    args = parser.parse_args()
    summary_file = None
    try:
        if args.summary_file:
            candidate = Path(args.summary_file).resolve()
            if candidate.is_relative_to(Path(args.project).resolve()):
                raise PaperDeltaError("CI_OUTPUT", "The job summary must be outside the paper root")
            summary_file = candidate
        result = run_ci(args.project, args.base_commit, args.snapshot, args.report, args.config)
        _append_job_summary(ci_summary(result), summary_file)
    except (PaperDeltaError, UnicodeDecodeError, OSError) as exc:
        code = getattr(exc, "code", "IO_ERROR")
        message = "# PaperDelta CI incomplete\n\n" + _cell(code + ": " + str(exc)) + "\n"
        try:
            _append_job_summary(message, summary_file)
        except OSError:
            pass
        print(json_text({"code": code, "error": str(exc)}))
        return 2
    print(json_text(result))
    return result["report"]["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
