"""Local, content-aware watching with debounced, snapshot-consistent reports."""

from __future__ import annotations

import json
import math
import os
import time
import webbrowser
from copy import deepcopy
from pathlib import Path

from paperdelta.analysis import _diagnostic, _finish, check_project, empty_report
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg, tr
from paperdelta.patches import _write_lock
from paperdelta.reports import write_reports
from paperdelta.snapshots import read_snapshot, snapshot_path
from paperdelta.storage import fingerprint, parse_json, sha256


class Watcher:
    def __init__(
        self,
        project,
        *,
        config_path="paperdelta.yaml",
        directory="build/paperdelta",
        baseline=None,
        debounce=0.5,
        publish=None,
        write_output=True,
    ):
        self.project, self.config_path = project, config_path
        self.directory = project.relative(project.path(directory))
        self.baseline, self.debounce = baseline, debounce
        self.publish = publish or (lambda report: None)
        self.write_output = write_output
        self.previous = None
        self.seen = None
        self.due = None
        self.generation = 0
        self.changed = []

    def inputs(self, extra=()):
        paths = {self.config_path, *extra}
        if self.baseline is not None:
            paths.add(snapshot_path(self.baseline))
        if self.previous:
            paths.update(self.previous["input_hashes"])
        if self.baseline:
            paths.add(snapshot_path(self.baseline))
        try:
            config, _ = load_config(self.project, self.config_path)
            paths.add(config.paper.entry)
            paths.update(item.entry for item in config.paper.companions)
            paths.update(source.path for source in config.sources.values())
            from paperdelta.fragments import validate_fragment
            from paperdelta.provenance import validate_producer

            for group, validator in (
                (config.provenance, validate_producer),
                (config.fragments, validate_fragment),
            ):
                for reference in group.values():
                    paths.add(reference.record)
                    try:
                        record = validator(
                            parse_json(self.project.text(reference.record, 4 * 1024 * 1024)[0])
                        )
                        if hasattr(record, "identities"):
                            paths.update(record.identities)
                        else:
                            paths.update(record.inputs)
                            paths.add(record.spec.path)
                    except PaperDeltaError:
                        pass
            for figure in config.figures.values():
                paths.add(figure.path)
                if figure.record:
                    paths.add(figure.record)
                    try:
                        record = parse_json(self.project.text(figure.record, 1024 * 1024)[0])
                        if isinstance(record, dict):
                            inputs = record.get("inputs", {})
                            if isinstance(inputs, dict):
                                paths.update(path for path in inputs if isinstance(path, str))
                            script = record.get("script", {})
                            if isinstance(script, dict) and isinstance(script.get("path"), str):
                                paths.add(script["path"])
                    except PaperDeltaError:
                        pass
        except PaperDeltaError:
            pass
        # Discover new/missing includes even while the main file is being edited.
        # Do not follow directory links or traverse environments/generated reports.
        output = self.project.path(self.directory)
        for directory, children, files in os.walk(self.project.root, followlinks=False):
            children[:] = [
                name
                for name in children
                if not name.startswith(".")
                and name not in {"node_modules", "__pycache__", "build", "dist"}
                and not Path(directory, name).is_symlink()
                and Path(directory, name).resolve() != output
            ]
            for name in files:
                if name.lower().endswith(".tex"):
                    # relative() checks link targets before any bytes are read.
                    path = Path(directory, name)
                    try:
                        paths.add(self.project.relative(path))
                    except PaperDeltaError:
                        continue
            if len(paths) > 2000:
                raise PaperDeltaError("WATCH_LIMIT", msg("watch.limit"))
        reviews = self.project.path(".paperdelta/reviews")
        if reviews.exists():
            for path in reviews.glob("*.json"):
                paths.add(self.project.relative(path))
        if len(paths) > 2000:
            raise PaperDeltaError("WATCH_LIMIT", msg("watch.limit"))
        identities = {}
        for path in sorted(paths):
            try:
                identities[path] = sha256(self.project.read(path))
            except PaperDeltaError as exc:
                identities[path] = "unavailable:" + exc.code
        return identities

    def _check(self):
        try:
            baseline = read_snapshot(self.project, self.baseline) if self.baseline else None
            return check_project(self.project.root, self.config_path, baseline)
        except PaperDeltaError as exc:
            report = empty_report(self.config_path)
            report["diagnostics"].append(_diagnostic(exc.code, "project", "unknown", str(exc)))
            _finish(report)
            return report

    def _publish(self, report, state, *, unverified=False):
        from paperdelta.actions import review_actions

        observed = self.inputs(report["input_hashes"])
        if state == "running" and observed != self.seen:
            self.changed = sorted(
                path
                for path in observed.keys() | self.seen.keys()
                if observed.get(path) != self.seen.get(path)
            )
            self.seen, self.due = observed, time.monotonic() + self.debounce
            state = "pending"
        value = deepcopy(report)
        value["watch"] = {
            "state": state,
            "generation": self.generation,
            "changed_paths": self.changed,
        }
        if state == "pending" or unverified:
            value["diagnostics"] = [
                item for item in value["diagnostics"] if item["rule"] != "WATCH_PENDING"
            ]
            value["diagnostics"].append(
                _diagnostic("WATCH_PENDING", "project", "unknown", msg("watch.pending"))
            )
            value["exit_code"] = 2
        value["actions"] = review_actions(value)
        protected = set()
        for path in observed:
            try:
                protected.add(self.project.path(path))
            except PaperDeltaError:
                continue
        if any(
            self.project.path(f"{self.directory}/{name}") in protected
            for name in ("report.json", "report.html", "report.md")
        ):
            raise PaperDeltaError("REPORT_OVERWRITE", msg("error.REPORT_OVERWRITE"))
        if self.write_output:
            write_reports(self.project, self.directory, value)
        self.publish(value)
        self.previous = value
        return value

    def step(self, now=None):
        now = time.monotonic() if now is None else now
        observed = self.inputs()
        if observed != self.seen:
            initial = self.seen is None
            self.changed = sorted(
                path
                for path in observed.keys() | (self.seen or {}).keys()
                if observed.get(path) != (self.seen or {}).get(path)
            )
            self.seen = observed
            self.due = now if initial else now + self.debounce
            if self.previous:
                self._publish(self.previous, "pending")
        if self.due is None or now < self.due:
            return None
        report = self._check()
        after = self.inputs(report["input_hashes"])
        if after != observed:
            self.changed = sorted(
                path
                for path in after.keys() | observed.keys()
                if after.get(path) != observed.get(path)
            )
            self.seen, self.due = after, now + self.debounce
            return self._publish(self.previous or report, "pending")
        self.due = None
        self.generation += 1
        return self._publish(report, "running")

    def stop(self):
        if self.previous is None:
            return None
        return self._publish(
            self.previous, "stopped", unverified=self.due is not None or self.inputs() != self.seen
        )


def register_commands(commands):
    child = commands.add_parser("watch", help=tr("watch.help"))
    child.add_argument("--report", default="build/paperdelta", help=tr("cli.help.8"))
    child.add_argument("--baseline", help=tr("cli.help.7"))
    child.add_argument("--interval", type=float, default=1.0, help=tr("watch.interval"))
    child.add_argument("--debounce", type=float, default=0.5, help=tr("watch.debounce"))
    child.add_argument("--max-checks", type=int, default=0, help=tr("watch.max_checks"))
    child.add_argument("--once", action="store_true", help=tr("watch.once"))
    child.add_argument("--open", action="store_true", help=tr("watch.open"))
    child.add_argument("--format", choices=["text", "json"], default="text", help=tr("cli.format"))


def run_command(project, arguments):
    if (
        not math.isfinite(arguments.interval)
        or not 0.1 <= arguments.interval <= 3600
        or not math.isfinite(arguments.debounce)
        or not 0 <= arguments.debounce <= 60
        or not 0 <= arguments.max_checks <= 10000
    ):
        raise PaperDeltaError("WATCH_OPTIONS", msg("watch.options"))
    opened = False

    def publish(report):
        nonlocal opened
        event = {
            "event": report["watch"]["state"],
            "generation": report["watch"]["generation"],
            "exit_code": report["exit_code"],
            "report": f"{arguments.report}/report.html",
            "changed_paths": report["watch"]["changed_paths"],
        }
        if arguments.format == "json":
            print(json.dumps(event, ensure_ascii=False), flush=True)
        else:
            print(
                tr(
                    "watch.event",
                    state=tr("watch.state_" + event["event"]),
                    generation=event["generation"],
                    code=event["exit_code"],
                    path=event["report"],
                ),
                flush=True,
            )
        if arguments.open and not opened:
            webbrowser.open(project.path(f"{arguments.report}/report.html").as_uri())
            opened = True

    watcher = Watcher(
        project,
        config_path=arguments.config,
        directory=arguments.report,
        baseline=arguments.baseline,
        debounce=arguments.debounce,
        publish=publish,
    )
    limit = 1 if arguments.once else arguments.max_checks
    lock_path = ".paperdelta/watch-locks/" + fingerprint(watcher.directory)[7:] + ".lock"
    with _write_lock(project, lock_path=lock_path):
        try:
            while True:
                watcher.step()
                if limit and watcher.generation >= limit:
                    break
                time.sleep(arguments.interval)
        except KeyboardInterrupt:
            pass
        finally:
            final = watcher.stop()
    return final["exit_code"] if final else 2
