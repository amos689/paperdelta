"""Optional stdio adapter. No tool accepts mappings, writes papers or attests review."""

from __future__ import annotations

from typing import Any, Literal

from paperdelta import __version__
from paperdelta.agent import AgentSession
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import current_language, language_context, msg, tr
from paperdelta.models import (
    Aggregation,
    ColumnType,
    DerivedOperation,
    DisplayKind,
    SourceFormat,
    Unit,
)
from paperdelta.storage import Project


def create_server(project: Project, config_path="paperdelta.yaml"):
    try:
        from mcp.server import MCPServer
        from mcp.server.mcpserver.exceptions import ToolError
        from mcp_types import ToolAnnotations
    except ImportError as exc:
        raise PaperDeltaError("MCP_NOT_INSTALLED", msg("error.MCP_NOT_INSTALLED")) from exc

    session = AgentSession(project, config_path)
    language = current_language()
    server = MCPServer(
        "PaperDelta",
        version=__version__,
        instructions=tr("agent.instructions"),
    )
    annotations = ToolAnnotations(
        read_only_hint=True, destructive_hint=False, open_world_hint=False
    )

    def call(function, *args):
        with language_context(language):
            try:
                return function(*args)
            except PaperDeltaError as exc:
                raise ToolError(f"{exc.code}: {exc.render()}") from exc

    @server.tool(annotations=annotations, description=tr("batch.mcp_start"))
    def start_batch_binding(
        source: str,
        fields: list[str],
        group_by: list[str],
        unit: Unit,
        reduce: Aggregation,
        expected_count: int,
        where: dict[str, str] | None = None,
        expected_seeds: list[str] | None = None,
        seed_column: str = "seed",
        display_kind: DisplayKind = "decimal",
        places: int = 1,
        percent_symbol: bool = True,
        source_path: str | None = None,
        columns: dict[str, ColumnType] | None = None,
        primary_key: list[str] | None = None,
    ) -> dict[str, Any]:
        request = {
            "source": source,
            "fields": fields,
            "group_by": group_by,
            "unit": unit,
            "reduce": reduce,
            "expected_count": expected_count,
            "where": where or {},
            "expected_seeds": expected_seeds,
            "seed_column": seed_column,
            "display": {"kind": display_kind, "places": places, "percent_symbol": percent_symbol},
        }
        return call(session.batch_call, "start", request, source_path, columns, primary_key)

    @server.tool(annotations=annotations, description=tr("batch.mcp_list"))
    def list_batch_candidates(
        session_id: str,
        kind: Literal["metrics", "locations"] = "metrics",
        offset: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        return call(session.batch_call, "list", session_id, kind, offset, limit)

    @server.tool(annotations=annotations, description=tr("batch.mcp_select"))
    def select_batch_bindings(
        session_id: str,
        choice_id: str,
        candidate_ids: list[str],
        rationale: str,
        display_kind: DisplayKind | None = None,
        places: int = 1,
        percent_symbol: bool = True,
    ) -> dict[str, Any]:
        display = (
            {"kind": display_kind, "places": places, "percent_symbol": percent_symbol}
            if display_kind
            else None
        )
        return call(
            session.batch_call, "select", session_id, choice_id, candidate_ids, rationale, display
        )

    @server.tool(annotations=annotations, description=tr("batch.mcp_finish"))
    def finish_batch_binding(session_id: str) -> dict[str, Any]:
        return call(session.batch_call, "finish", session_id)

    @server.tool(annotations=annotations, description=tr("agent.scan"))
    def scan_project() -> dict[str, Any]:
        """Find candidate numbers and source samples without confirming any mapping."""
        return call(session.scan_project)

    @server.tool(annotations=annotations, description=tr("agent.check"))
    def check_project(baseline: str | None = None) -> dict[str, Any]:
        """Check bindings; return coverage, findings and ten evidence rows per metric."""
        return call(session.check_project, baseline)

    @server.tool(annotations=annotations, description=tr("agent.propose"))
    def propose_bindings(additions_json: str, rationale: dict[str, str]) -> dict[str, Any]:
        """Validate an unaccepted proposal. Exact JSON text preserves decimal selectors."""
        return call(session.propose_bindings, additions_json, rationale)

    @server.tool(annotations=annotations, description=tr("agent.draft_start"))
    def start_binding_draft() -> dict[str, Any]:
        return call(session.start_binding_draft)

    @server.tool(annotations=annotations, description=tr("agent.draft_source"))
    def add_draft_source(
        draft_json: str,
        name: str,
        path: str,
        format: SourceFormat,
        columns: dict[str, ColumnType] | None = None,
        primary_key: list[str] | None = None,
    ) -> dict[str, Any]:
        return call(session.add_draft_source, draft_json, name, path, format, columns, primary_key)

    @server.tool(annotations=annotations, description=tr("agent.draft_metric"))
    def add_draft_metric(
        draft_json: str,
        name: str,
        source: str,
        field: str,
        unit: Unit,
        reduce: Aggregation,
        where: dict[str, str] | None = None,
        expected_count: int | None = None,
        seed_column: str = "seed",
        expected_seeds: list[str] | None = None,
    ) -> dict[str, Any]:
        return call(
            session.add_draft_metric,
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
        )

    @server.tool(annotations=annotations, description=tr("agent.draft_derived"))
    def add_draft_derived(
        draft_json: str, name: str, operation: DerivedOperation, left: str, right: str
    ) -> dict[str, Any]:
        return call(session.add_draft_derived, draft_json, name, operation, left, right)

    @server.tool(annotations=annotations, description=tr("agent.draft_locations"))
    def add_draft_locations(
        draft_json: str,
        metric: str,
        candidate_ids: list[str],
        names: list[str],
        display_kind: DisplayKind,
        places: int,
        percent_symbol: bool,
        rationale: str,
    ) -> dict[str, Any]:
        return call(
            session.add_draft_locations,
            draft_json,
            metric,
            candidate_ids,
            names,
            display_kind,
            places,
            percent_symbol,
            rationale,
        )

    @server.tool(annotations=annotations, description=tr("agent.draft_finish"))
    def finish_binding_draft(draft_json: str) -> dict[str, Any]:
        return call(session.finish_binding_draft, draft_json)

    @server.tool(annotations=annotations, description=tr("agent.repair_scan"))
    def scan_binding_repairs(baseline: str | None = None) -> dict[str, Any]:
        return call(session.scan_binding_repairs, baseline)

    @server.tool(annotations=annotations, description=tr("agent.repair_propose"))
    def propose_binding_repair(
        binding: str,
        rationale: str,
        candidate_id: str | None = None,
        file: str | None = None,
        exact: str | None = None,
        baseline: str | None = None,
    ) -> dict[str, Any]:
        return call(
            session.propose_binding_repair, binding, rationale, candidate_id, file, exact, baseline
        )

    @server.tool(annotations=annotations, description=tr("agent.explain"))
    def explain_finding(finding_id: str) -> dict[str, Any]:
        """Recheck and return a finding's text, comparison and selected evidence."""
        return call(session.explain_finding, finding_id)

    @server.tool(annotations=annotations, description=tr("agent.patch"))
    def propose_patch(occurrences: list[str] | None = None) -> dict[str, Any]:
        """Recompute permitted numeric changes and return a patch for explicit author review."""
        return call(session.propose_patch, occurrences)

    return server


def serve(project: Project, config_path="paperdelta.yaml") -> None:
    create_server(project, config_path).run(transport="stdio")
