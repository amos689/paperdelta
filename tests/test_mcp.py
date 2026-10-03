import asyncio
import sys

import pytest

from paperdelta.mcp_server import create_server
from paperdelta.storage import Project

mcp = pytest.importorskip("mcp")
StdioServerParameters = pytest.importorskip("mcp.client.stdio").StdioServerParameters


def test_mcp_exposes_only_five_read_only_tools(project):
    async def run():
        async with mcp.Client(create_server(Project(project))) as client:
            listing = await client.list_tools()
            assert {tool.name for tool in listing.tools} == {
                "scan_project",
                "check_project",
                "propose_bindings",
                "explain_finding",
                "propose_patch",
            }
            assert all(tool.annotations.read_only_hint for tool in listing.tools)
            result = await client.call_tool("check_project")
            assert not result.is_error
            assert result.structured_content["coverage"]["confirmed"] == 6
            assert result.structured_content["exit_code"] == 0
            bad = await client.call_tool("explain_finding", {"finding_id": "does-not-exist"})
            assert bad.is_error

    asyncio.run(run())


def test_stdio_cli_handshake_and_data_only_change(project, change_results):
    change_results(project)

    async def run():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "paperdelta", "-C", str(project), "mcp"],
            env={"PYTHONUTF8": "1"},
        )
        async with mcp.Client(parameters, read_timeout_seconds=20) as client:
            result = await client.call_tool("check_project")
            assert not result.is_error
            assert result.structured_content["exit_code"] == 1
            assert result.structured_content["claims"]["main_comparison"]["status"] == "mismatch"

    asyncio.run(run())
