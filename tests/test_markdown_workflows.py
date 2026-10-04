"""Static sources use the existing reviewed workflows and keep evidence identity."""

import asyncio

import pytest
from test_markdown import bind_accuracy, static_project

from paperdelta import builder
from paperdelta.analysis import check_project
from paperdelta.batch import build_proposal, create_catalog, inspect_catalog
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import language_context
from paperdelta.onboarding import accept_bindings, init_project
from paperdelta.repairs import accept_repairs, inspect_repair, propose_repairs, scan_repairs
from paperdelta.snapshots import create_snapshot
from paperdelta.storage import Project, parse_json
from paperdelta.watch import Watcher


@pytest.mark.parametrize("extension", ["md", "qmd"])
def test_context_change_needs_reviewed_repair_and_stale_proposal_cannot_write(tmp_path, extension):
    project, file = static_project(tmp_path, extension)
    bind_accuracy(project, file)
    create_snapshot(project, "before", check_project(tmp_path))
    before = load_config(project)[0]
    project.write(file, project.read(file).replace(b"Our accuracy is", b"Updated accuracy reaches"))
    assert check_project(tmp_path)["occurrences"]["accuracy_text"]["status"] == "unknown"
    scan = scan_repairs(project, baseline="before")
    selection = [
        {
            "binding": "occurrences:accuracy_text",
            "candidate_id": scan["candidates"][0]["candidate_id"],
            "rationale": "Same declared experiment; reviewed the rewritten source context.",
        }
    ]
    proposal = propose_repairs(project, selection, baseline="before")
    _, _, review = inspect_repair(project, proposal)
    assert review["changes"][0]["previous_location"]["text"] == "84.1%"
    original_config = project.read("paperdelta.yaml")
    project.write("results.csv", b"model,score\nOurs,0.809\n")
    with pytest.raises(PaperDeltaError) as failed:
        accept_repairs(project, proposal, ["occurrences:accuracy_text"])
    assert (
        failed.value.code == "STALE_REPAIR" and project.read("paperdelta.yaml") == original_config
    )
    proposal = propose_repairs(project, selection, baseline="before")
    result = accept_repairs(project, proposal, ["occurrences:accuracy_text"])
    # Repair only relocates; it cannot turn an outdated number into a pass.
    assert result["report"]["occurrences"]["accuracy_text"]["status"] == "mismatch"
    assert load_config(project)[0].metrics == before.metrics
    assert load_config(project)[0].sources == before.sources


@pytest.mark.parametrize("extension", ["md", "qmd"])
def test_watcher_observes_source_hash_and_preserves_read_only_files(tmp_path, extension):
    project, file = static_project(tmp_path, extension)
    bind_accuracy(project, file)
    watcher = Watcher(project, debounce=0)
    assert watcher.step(0)["exit_code"] == 0
    project.write(file, project.read(file).replace(b"84.1", b"80.9"))
    changed_bytes = project.read(file)
    changed = watcher.step(1)
    assert changed["exit_code"] == 1
    assert changed["occurrences"]["accuracy_text"]["actual"] == "80.9%"
    assert project.read(file) == changed_bytes
    project.write("results.csv", b"model,score\nOurs,0.809\n")
    assert watcher.step(2)["exit_code"] == 0
    watcher.stop()


@pytest.mark.parametrize("extension", ["md", "qmd"])
def test_batch_equal_values_keep_independent_row_and_field_identities(tmp_path, extension):
    project = Project(tmp_path)
    file = "paper." + extension
    project.write(
        file,
        b"| Model | accuracy | precision |\n| --- | --- | --- |\n"
        b"| A | 80.0 | 80.0 |\n| B | 80.0 | 80.0 |\n",
    )
    project.write("data.csv", b"model,accuracy,precision\nA,0.800,0.800\nB,0.800,0.800\n")
    init_project(project, file, ["data.csv"])
    draft = builder.add_source(
        project,
        builder.start_draft(project),
        name="runs",
        path="data.csv",
        format="csv",
        primary_key=["model"],
        columns={"model": "string", "accuracy": "decimal", "precision": "decimal"},
    )
    catalog = create_catalog(
        project,
        draft,
        {
            "source": "runs",
            "fields": ["accuracy", "precision"],
            "group_by": ["model"],
            "where": {},
            "unit": "fraction",
            "reduce": "unique",
            "expected_count": 1,
            "display": {"kind": "percent", "places": 1, "percent_symbol": False},
        },
    )
    preview = inspect_catalog(project, catalog)
    selections = []
    for choice in preview["choices"]:
        definition = choice["definition"]
        candidate = next(
            c
            for c in preview["locations"]
            if c["row"].split("|")[0].strip() == definition["where"]["model"]
            and c["column_header"] == definition["field"]
        )
        selections.append(
            {
                "choice_id": choice["choice_id"],
                "candidate_ids": [candidate["candidate_id"]],
                "rationale": "Reviewed literal model label and named column.",
            }
        )
    proposal = build_proposal(project, catalog, selections)
    assert not load_config(project)[0].occurrences
    accept_bindings(
        project, proposal, ["occurrences:" + n for n in proposal["additions"]["occurrences"]]
    )
    assert check_project(tmp_path)["coverage"]["pass"] == 4
    project.write("data.csv", project.read("data.csv").replace(b"A,0.800,0.800", b"A,0.809,0.800"))
    report = check_project(tmp_path)
    assert report["coverage"]["mismatch"] == 1 and report["coverage"]["pass"] == 3
    changed = next(o for o in report["occurrences"].values() if o["status"] == "mismatch")
    assert (
        changed["location"]["locator"]["row"] == 2 and changed["location"]["locator"]["cell"] == 2
    )


@pytest.mark.parametrize("extension", ["md", "qmd"])
@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_mcp_static_source_proposal_is_read_only_and_uses_original_positions(
    tmp_path, extension, language
):
    mcp = pytest.importorskip("mcp")
    from paperdelta.mcp_server import create_server

    project, file = static_project(tmp_path, extension)
    original = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with language_context(language):
        server = create_server(project)

    async def run():
        async with mcp.Client(server) as client:

            async def call(name, **args):
                result = await client.call_tool(name, args)
                assert not result.is_error, result.content
                return result.structured_content

            state = await call("start_binding_draft")
            candidate = next(c for c in state["discovery"]["candidates"] if c["text"] == "84.1")
            assert candidate["file"] == file and candidate["line"] == 3
            state = await call(
                "add_draft_locations",
                draft_json=state["draft_json"],
                metric="accuracy",
                candidate_ids=[candidate["candidate_id"]],
                names=["result"],
                display_kind="percent",
                places=1,
                percent_symbol=True,
                rationale="Reviewed exact source position and explicit experiment identity.",
            )
            proposal = await call("finish_binding_draft", draft_json=state["draft_json"])
            assert (
                parse_json(proposal["proposal_json"])["additions"]["occurrences"]["result"]["file"]
                == file
            )
            report = await call("check_project")
            assert report["coverage"]["confirmed"] == 0
            assert report["agent_view"]["language"] == language

    asyncio.run(run())
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == original
