"""Small read-only views for existing agents, using the same deterministic core."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.onboarding import propose_bindings, scan_project
from paperdelta.patches import create_patch
from paperdelta.snapshots import read_snapshot
from paperdelta.storage import Project, json_text, parse_json


def _wire(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _wire(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_wire(item) for item in value]
    return value


def compact_report(report: dict) -> dict:
    value = deepcopy(report)
    for metric in value["metrics"].values():
        for evidence in metric.get("evidence", []):
            for key in ("records", "locations"):
                evidence[key + "_total"] = len(evidence[key])
                evidence[key] = evidence[key][:10]
    value["agent_view"] = {
        "evidence_row_limit": 10,
        "decimal_encoding": "strings preserve exact decimal representation",
    }
    return _wire(value)


class AgentSession:
    def __init__(self, project: Project, config_path="paperdelta.yaml"):
        self.project = project
        self.config_path = config_path

    def scan_project(self) -> dict:
        return _wire(scan_project(self.project, self.config_path))

    def check_project(self, baseline: str | None = None) -> dict:
        previous = read_snapshot(self.project, baseline) if baseline else None
        return compact_report(check_project(self.project.root, self.config_path, previous))

    def propose_bindings(self, additions_json: str, rationale: dict[str, str]) -> dict:
        value = propose_bindings(
            self.project, parse_json(additions_json), rationale, config_path=self.config_path
        )
        return {
            "status": "proposed",
            "proposal_id": value["proposal_id"],
            "proposal_json": json_text(value),
            "next": "Ask the author to inspect and explicitly accept selected binding IDs.",
        }

    def explain_finding(self, finding_id: str) -> dict:
        report = self.check_project()
        finding = next((item for item in report["diagnostics"] if item["id"] == finding_id), None)
        if finding is None:
            raise PaperDeltaError("FINDING_MISSING", "Finding is absent from the current check")
        group, _, name = finding["subject"].partition(":")
        states = {"occurrence": "occurrences", "claim": "claims", "figure": "figures"}
        state = report[states[group]].get(name, {}) if group in states else {}
        refs = state.get("metrics", [state["metric"]] if "metric" in state else [])
        return {
            "finding": finding,
            "state": state,
            "metrics": {ref: report["metrics"][ref] for ref in refs},
            "input_hashes": report["input_hashes"],
            "agent_view": report["agent_view"],
        }

    def propose_patch(self, occurrences: list[str] | None = None) -> dict:
        report = check_project(self.project.root, self.config_path)
        patch = create_patch(self.project, report, occurrences)
        return {
            "status": "proposed",
            "patch_json": json_text(patch),
            "patch_id": patch["patch_id"],
            "next": "Preview the patch, then obtain explicit authorization before applying it.",
        }
