"""Optional stdio adapter. No tool accepts mappings, writes papers or attests review."""

from __future__ import annotations

from typing import Any

from paperdelta import __version__
from paperdelta.agent import AgentSession
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import current_language, language_context, msg, tr
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
