"""Ongoing local review uses the same watcher, snapshots and claim attestations."""

from __future__ import annotations

import time

from paperdelta.analysis import check_project
from paperdelta.declarations import observe
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.locations import location_label
from paperdelta.patches import _write_lock
from paperdelta.reviews import record_review
from paperdelta.snapshots import create_snapshot, read_snapshot, snapshot_path
from paperdelta.storage import sha256
from paperdelta.watch import Watcher


class StudioReview:
    def __init__(self, project, config_path):
        self.project, self.config_path = project, config_path
        self.watcher = Watcher(
            project,
            config_path=config_path,
            directory=".paperdelta/studio/review",
            write_output=False,
        )

    def seed(self, report):
        if self.watcher.baseline is not None:
            report = check_project(
                self.project.root,
                self.config_path,
                read_snapshot(self.project, self.watcher.baseline),
            )
        self.watcher.previous = report
        self.watcher.seen = self.watcher.inputs(report["input_hashes"])
        self.watcher.due = (
            time.monotonic() + self.watcher.debounce
            if any(
                self.watcher.seen.get(path) != identity
                for path, identity in report["input_hashes"].items()
            )
            else None
        )
        self.watcher.generation += 1

    def poll(self, now=None):
        changed = self.watcher.step(now) is not None
        return changed, self.summary()

    def summary(self):
        report = self.watcher.previous
        if report is None:
            return {"available": False, "generation": self.watcher.generation}
        pending = self.watcher.due is not None
        return {
            "available": True,
            "generation": self.watcher.generation,
            "state": "pending" if pending else "current",
            "baseline": self.watcher.baseline,
            "changed_paths": self.watcher.changed,
            "exit_code": 2 if pending else report["exit_code"],
            "counts": {
                key: report["coverage"][key] for key in ("confirmed", "pass", "mismatch", "unknown")
            },
        }

    def snapshots(self):
        output = []
        for path in sorted(self.project.path(".paperdelta/baselines").glob("*.json"))[:1000]:
            try:
                record = read_snapshot(self.project, path.stem)
                output.append(
                    {
                        "name": path.stem,
                        "created_at": record["created_at"],
                        "exit_code": record["report"]["exit_code"],
                    }
                )
            except PaperDeltaError as exc:
                output.append({"name": path.stem, "error": exc.code})
        return output

    def select_baseline(self, name):
        if name is not None:
            read_snapshot(self.project, name)
        self.watcher.baseline = name
        self.watcher.seen = None
        self.watcher.step()

    def create_snapshot(self, name):
        snapshot_path(name)
        with _write_lock(self.project):
            report = check_project(self.project.root, self.config_path)
            if observe(self.project, report["input_hashes"]) != report["input_hashes"]:
                raise PaperDeltaError("STALE_REVIEW", msg("maintenance.stale"))
            path = create_snapshot(self.project, name, report)
        return {"name": name, "path": path, "exit_code": report["exit_code"]}

    def attest(self, claim, state, reviewer, note):
        with _write_lock(self.project):
            path = record_review(
                self.project,
                claim,
                state,
                reviewer,
                note,
                config_path=self.config_path,
                attest_reviewed=True,
            )
        self.watcher.seen = None
        self.watcher.step()
        return {"path": path, "claim": claim, "reviewed_state": state}

    def detail(self):
        report = self.watcher.previous
        positions, texts = {}, {}
        if report is not None:
            for group in ("occurrences", "claims"):
                for name, item in report[group].items():
                    location = item.get("location")
                    if not location:
                        continue
                    context = location.get("context", location["text"])
                    if "format" not in location:
                        path = location["file"]
                        if path not in texts:
                            try:
                                text, raw = self.project.text(path)
                                texts[path] = (
                                    text
                                    if sha256(raw) == report["input_hashes"].get(path)
                                    else None
                                )
                            except PaperDeltaError:
                                texts[path] = None
                        if texts[path] is not None:
                            context = texts[path][
                                max(0, location["start"] - 80) : location["end"] + 80
                            ]
                    positions[f"{group}:{name}"] = {
                        "label": location_label(location),
                        "context": context,
                    }
        return {
            "summary": self.summary(),
            "report": report,
            "snapshots": self.snapshots(),
            "positions": positions,
        }
