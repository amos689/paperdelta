"""Small read-only views for existing agents, using the same deterministic core."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal

from paperdelta import builder
from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import current_language, msg, tr, translated
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
        "decimal_encoding": msg("agent.decimal_encoding"),
        "language": current_language(),
    }
    return _wire(translated(value))


class AgentSession:
    def __init__(self, project: Project, config_path="paperdelta.yaml"):
        from paperdelta.batch_agent import BatchSessions

        self.project = project
        self.config_path = config_path
        self.batch = BatchSessions(project, config_path)

    def batch_call(self, method, *args):
        return _wire(translated(getattr(self.batch, method)(*args)))

    def scan_project(self) -> dict:
        return _wire(translated(scan_project(self.project, self.config_path)))

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
            "next": tr("agent.next_binding"),
        }

    def _draft_view(self, value):
        preview = builder.inspect_draft(self.project, value)
        for state in preview["metrics"].values():
            for source in state["evidence"]:
                source["records"] = source["records"][:10]
                source["locations"] = source["locations"][:10]
        return {
            "status": "draft",
            "draft_json": json_text(value),
            "preview": _wire(preview),
            "next": tr("agent.next_draft"),
        }

    def start_binding_draft(self):
        value = builder.start_draft(self.project, self.config_path)
        return {**self._draft_view(value), "discovery": self.scan_project()}

    def add_draft_source(
        self, draft_json, name, path, format, columns, primary_key, sheet=None, cell_range=None
    ):
        return self._draft_view(
            builder.add_source(
                self.project,
                parse_json(draft_json),
                name=name,
                path=path,
                format=format,
                columns=columns,
                primary_key=primary_key,
                sheet=sheet,
                cell_range=cell_range,
            )
        )

    def add_draft_metric(
        self,
        draft_json,
        name,
        source,
        field,
        unit,
        reduce,
        where,
        expected_count,
        seed_column,
        expected_seeds,
    ):
        return self._draft_view(
            builder.add_metric(
                self.project,
                parse_json(draft_json),
                name=name,
                source=source,
                field=field,
                unit=unit,
                reduce=reduce,
                where=where,
                expected_count=expected_count,
                seed_column=seed_column,
                expected_seeds=expected_seeds,
            )
        )

    def add_draft_derived(self, draft_json, name, operation, left, right):
        return self._draft_view(
            builder.add_derived(
                self.project,
                parse_json(draft_json),
                name=name,
                operation=operation,
                left=left,
                right=right,
            )
        )

    def add_draft_locations(
        self,
        draft_json,
        metric,
        candidate_ids,
        names,
        display_kind,
        places,
        percent_symbol,
        rationale,
    ):
        return self._draft_view(
            builder.add_occurrences(
                self.project,
                parse_json(draft_json),
                metric=metric,
                candidate_ids=candidate_ids,
                names=names,
                display_kind=display_kind,
                places=places,
                percent_symbol=percent_symbol,
                rationale=rationale,
            )
        )

    def finish_binding_draft(self, draft_json):
        value = builder.finalize_draft(self.project, parse_json(draft_json))
        return {
            "status": "proposed",
            "proposal_id": value["proposal_id"],
            "proposal_json": json_text(value),
            "next": tr("agent.next_binding"),
        }

    def scan_binding_repairs(self, baseline=None):
        from paperdelta.repairs import scan_repairs

        return _wire(translated(scan_repairs(self.project, self.config_path, baseline)))

    def propose_binding_repair(self, binding, rationale, candidate_id, file, exact, baseline):
        from paperdelta.repairs import inspect_repair, propose_repairs

        choice = {
            "binding": binding,
            "rationale": rationale,
            "candidate_id": candidate_id,
            "file": file,
            "anchor": {"exact": exact} if exact is not None else None,
        }
        proposal = propose_repairs(
            self.project, [choice], config_path=self.config_path, baseline=baseline
        )
        _, _, preview = inspect_repair(self.project, proposal)
        return {
            "status": "proposed",
            "repair_json": json_text(proposal),
            "repair_id": proposal["repair_id"],
            "changes": _wire(preview["changes"]),
            "preview": compact_report(preview["preview"]),
            "next": tr("agent.next_repair"),
        }

    def explain_finding(self, finding_id: str) -> dict:
        report = self.check_project()
        finding = next((item for item in report["diagnostics"] if item["id"] == finding_id), None)
        if finding is None:
            raise PaperDeltaError("FINDING_MISSING", msg("error.FINDING_MISSING"))
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
            "next": tr("agent.next_patch"),
        }
