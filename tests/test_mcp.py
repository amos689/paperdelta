import asyncio
import sys

import pytest

from paperdelta.i18n import language_context
from paperdelta.mcp_server import create_server
from paperdelta.storage import Project, parse_json

mcp = pytest.importorskip("mcp")
StdioServerParameters = pytest.importorskip("mcp.client.stdio").StdioServerParameters


def test_mcp_exposes_only_read_only_tools(project):
    async def run():
        async with mcp.Client(create_server(Project(project))) as client:
            listing = await client.list_tools()
            assert {tool.name for tool in listing.tools} == {
                "scan_project",
                "check_project",
                "propose_bindings",
                "explain_finding",
                "propose_patch",
                "start_binding_draft",
                "add_draft_source",
                "add_draft_metric",
                "add_draft_derived",
                "add_draft_locations",
                "finish_binding_draft",
                "scan_binding_repairs",
                "propose_binding_repair",
            }
            assert all(tool.annotations.read_only_hint for tool in listing.tools)
            schemas = {tool.name: tool.input_schema for tool in listing.tools}
            assert "fraction" in schemas["add_draft_metric"]["properties"]["unit"]["enum"]
            assert schemas["add_draft_source"]["properties"]["format"]["enum"] == ["csv", "json"]
            result = await client.call_tool("check_project")
            assert not result.is_error
            assert result.structured_content["coverage"]["confirmed"] == 6
            assert result.structured_content["exit_code"] == 0
            bad = await client.call_tool("explain_finding", {"finding_id": "does-not-exist"})
            assert bad.is_error

    asyncio.run(run())


def test_mcp_keeps_server_language_for_tools_called_outside_creation_context(
    project, change_results
):
    change_results(project)
    with language_context("zh-CN"):
        server = create_server(Project(project))

    async def run():
        async with mcp.Client(server) as client:
            listing = await client.list_tools()
            assert all(
                any("\u4e00" <= char <= "\u9fff" for char in tool.description)
                for tool in listing.tools
            )
            result = await client.call_tool("check_project")
            assert result.structured_content["agent_view"]["language"] == "zh-CN"
            assert result.structured_content["exit_code"] == 1
            assert any(
                "应根据指标" in item["message"] for item in result.structured_content["diagnostics"]
            )

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


def test_staged_mcp_proposal_roundtrip_never_accepts_or_writes(project):
    from paperdelta.config import config_text, load_config
    from paperdelta.models import Config

    store = Project(project)
    original, _ = load_config(store)
    store.write(
        "paperdelta.yaml", config_text(Config(schema_version=1, paper=original.paper)).encode()
    )
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}

    async def run():
        async with mcp.Client(create_server(store)) as client:

            async def call(name, /, **arguments):
                result = await client.call_tool(name, arguments)
                assert not result.is_error, result.content
                return result.structured_content

            state = await call("start_binding_draft")
            candidate = next(
                item
                for item in state["discovery"]["candidates"]
                if item["file"] == "paper/abstract.tex"
            )
            state = await call(
                "add_draft_source",
                draft_json=state["draft_json"],
                name="benchmark",
                **original.sources["benchmark"].model_dump(),
            )
            state = await call(
                "add_draft_metric",
                draft_json=state["draft_json"],
                name="ours",
                source="benchmark",
                field="accuracy",
                unit="fraction",
                reduce="mean",
                where={"dataset": "Data-A", "model": "Ours", "split": "test"},
                expected_count=3,
                expected_seeds=["1", "2", "3"],
            )
            assert state["preview"]["metrics"]["ours"]["value"] == "0.841"
            state = await call(
                "add_draft_locations",
                draft_json=state["draft_json"],
                metric="ours",
                candidate_ids=[candidate["candidate_id"]],
                names=["abstract_accuracy"],
                display_kind="percent",
                places=1,
                percent_symbol=True,
                rationale="Data-A test, Ours, seeds 1–3.",
            )
            proposal = await call("finish_binding_draft", draft_json=state["draft_json"])
            assert proposal["status"] == "proposed"
            assert (
                parse_json(proposal["proposal_json"])["additions"]["occurrences"][
                    "abstract_accuracy"
                ]["metric"]
                == "ours"
            )
            report = await call("check_project")
            assert report["coverage"]["confirmed"] == 0

    asyncio.run(run())
    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == before
