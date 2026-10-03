import io
import json
import subprocess
import sys

import pytest

from paperdelta import builder
from paperdelta.analysis import check_project
from paperdelta.batch import build_proposal, create_catalog, inspect_catalog
from paperdelta.batch_agent import BatchSessions
from paperdelta.batch_cli import guide_batch
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import language_context
from paperdelta.interactive import confirm_bindings
from paperdelta.onboarding import accept_bindings, init_project, inspect_proposal
from paperdelta.patches import apply_patch, create_patch, recover_transaction
from paperdelta.storage import Project, json_text, parse_json

FIELDS = ["accuracy", "precision", "recall", "fscore"]
COLUMNS = {
    "model": "string",
    "split": "string",
    "seed": "integer",
    **{field: "decimal" for field in FIELDS},
}
REQUEST = {
    "source": "results",
    "fields": FIELDS,
    "group_by": ["model"],
    "where": {"split": "test"},
    "unit": "fraction",
    "reduce": "mean",
    "expected_count": 3,
    "expected_seeds": ["1", "2", "3"],
    "display": {"kind": "percent", "places": 1, "percent_symbol": False},
}


@pytest.fixture
def batch_project(tmp_path):
    store = Project(tmp_path)
    models = ["001", "1", "Model-C", "Model-D", "Model-E"]
    table = "\\begin{tabular}{lrrrr}\nModel & " + " & ".join(FIELDS) + r" \\" + "\n"
    table += "\n".join(model + " & 80.0 & 80.0 & 80.0 & 80.0 " + r"\\" for model in models)
    table += "\n\\end{tabular}\n"
    store.write("paper.tex", table.encode())
    data = "model,split,seed," + ",".join(FIELDS) + "\n"
    data += "".join(
        f"{model},{split},{seed},0.800,0.800,0.800,0.800\n"
        for model in models
        for split in ["test", "train"]
        for seed in [1, 2, 3]
    )
    store.write("results.csv", data.encode())
    init_project(store, "paper.tex", ["results.csv"])
    return store


def catalogue(store, request=None):
    draft = builder.add_source(
        store,
        builder.start_draft(store),
        name="results",
        path="results.csv",
        format="csv",
        columns=COLUMNS,
        primary_key=["model", "split", "seed"],
    )
    return create_catalog(store, draft, request or REQUEST)


def choose_every_cell(store, catalog):
    preview = inspect_catalog(store, catalog)
    selections = []
    for choice in preview["choices"]:
        identity = choice["definition"]["where"]["model"]
        field = choice["definition"]["field"]
        target = next(
            item
            for item in preview["locations"]
            if item["row"].split("&")[0].strip() == identity
            and item["column_header"].strip() == field
        )
        selections.append(
            {
                "choice_id": choice["choice_id"],
                "candidate_ids": [target["candidate_id"]],
                "rationale": f"{identity}, {field}, test split, seeds 1–3.",
            }
        )
    return selections


def test_twenty_cells_remain_bound_after_neighbouring_values_change_and_recover(batch_project):
    store = batch_project
    catalog = catalogue(store)
    selections = choose_every_cell(store, catalog)
    assert len(selections) == 20
    proposal = build_proposal(store, catalog, selections)
    _, merged, preview = inspect_proposal(store, proposal)
    assert merged.schema_version == 2
    assert preview["coverage"]["pass"] == 20
    before = store.read("paper.tex")
    accept_bindings(
        store, proposal, ["occurrences:" + name for name in proposal["additions"]["occurrences"]]
    )
    config, _ = load_config(store)
    assert any(item.anchor.table is not None for item in config.occurrences.values())
    store.write("results.csv", store.read("results.csv").replace(b"0.800", b"0.845"))
    report = check_project(store.root)
    assert report["exit_code"] == 1 and report["coverage"]["mismatch"] == 20
    patch = create_patch(store, report)
    applied = apply_patch(store, patch)
    assert applied["report"]["exit_code"] == 0 and applied["report"]["coverage"]["pass"] == 20
    recover_transaction(store, applied["transaction_id"], write=True)
    assert store.read("paper.tex") == before


def test_missing_runs_stay_unresolved_and_equal_numbers_do_not_choose_identity(batch_project):
    store = batch_project
    data = store.read("results.csv").replace(b"001,test,3,0.800,0.800,0.800,0.800\n", b"")
    store.write("results.csv", data)
    catalog = catalogue(store)
    preview = inspect_catalog(store, catalog)
    ours = [item for item in preview["choices"] if item["definition"]["where"]["model"] == "001"]
    another = [item for item in preview["choices"] if item["definition"]["where"]["model"] == "1"]
    assert len(ours) == len(another) == 4
    assert all(item["status"] == "unknown" and item["error"] == "SEED_SET" for item in ours)
    assert all(item["status"] == "ready" for item in another)
    assert preview["requires_confirmation"] is True
    assert check_project(store.root)["coverage"]["confirmed"] == 0
    with pytest.raises(PaperDeltaError):
        build_proposal(
            store,
            catalog,
            [
                {
                    "choice_id": ours[0]["choice_id"],
                    "candidate_ids": [preview["locations"][0]["candidate_id"]],
                    "rationale": "No seed 3; must fail.",
                }
            ],
        )


def test_invalid_agent_choice_is_recoverable_without_repeating_draft_json(batch_project):
    store = batch_project
    before = {path: path.read_bytes() for path in store.root.rglob("*") if path.is_file()}
    sessions = BatchSessions(store, "paperdelta.yaml")
    state = sessions.start(REQUEST, "results.csv", COLUMNS, ["model", "split", "seed"])
    session_id = state["session_id"]
    catalog = sessions.sessions[session_id]["catalog"]
    choice = choose_every_cell(store, catalog)[0]
    with pytest.raises(PaperDeltaError):
        sessions.select(session_id, choice["choice_id"], ["sha256:" + "f" * 64], "Invalid location")
    selected = sessions.select(
        session_id, choice["choice_id"], choice["candidate_ids"], choice["rationale"]
    )
    assert selected["selected_locations"] == 1
    proposal = sessions.finish(session_id)
    assert len(parse_json(proposal["proposal_json"])["additions"]["occurrences"]) == 1
    assert {path: path.read_bytes() for path in store.root.rglob("*") if path.is_file()} == before
    store.write("results.csv", store.read("results.csv").replace(b"0.800", b"0.900"))
    with pytest.raises(PaperDeltaError, match="changed"):
        sessions.finish(session_id)


class Terminal(io.StringIO):
    def isatty(self):
        return True


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_batch_guide_from_empty_configuration_to_confirmed_mapping(batch_project, language):
    answers = [
        "1",
        "results",
        "1,2,3",
        "1",
        "1",
        "2",
        "3",
        "3",
        "3",
        "3",
        "2,3,4,5",
        "1",
        "test",
        "",
        "2",
        "2",
        "3",
        "4",
        "1,2,3",
        "2",
        "1",
        "2",
        "1",
        "1",
        "",
        "1",
        "1",
        "Model 001 accuracy, test split, seeds 1–3.",
        "1",
        "all",
        "accept",
        "",
    ]
    output = Terminal()
    with language_context(language):
        result = guide_batch(
            batch_project,
            "paperdelta.yaml",
            input_stream=Terminal("\n".join(answers)),
            output=output,
        )
    assert result["status"] == "accepted", output.getvalue()
    report = check_project(batch_project.root)
    assert report["coverage"]["pass"] == 1
    metric = next(iter(report["metrics"].values()))
    assert metric["definition"]["where"] == {"model": "001", "split": "test"}


@pytest.mark.parametrize(
    "answer,expected", [("all\naccept\n", 20), ("1,3\naccept\n", 2), ("all\n\n", 0)]
)
def test_batch_review_can_accept_all_select_subset_or_cancel(batch_project, answer, expected):
    store = batch_project
    catalog = catalogue(store)
    proposal = build_proposal(store, catalog, choose_every_cell(store, catalog))
    result = confirm_bindings(
        store, proposal, input_stream=Terminal(answer), output=Terminal(), batch=True
    )
    assert len(result["bindings"]) == expected
    assert check_project(store.root)["coverage"]["confirmed"] == expected


def test_table_headers_and_duplicate_rows_never_silently_retarget(batch_project):
    store = batch_project
    catalog = catalogue(store)
    proposal = build_proposal(store, catalog, choose_every_cell(store, catalog))
    accept_bindings(
        store, proposal, ["occurrences:" + name for name in proposal["additions"]["occurrences"]]
    )
    original = store.read("paper.tex")
    store.write("paper.tex", original.replace(b"accuracy & precision", b"precision & accuracy"))
    assert check_project(store.root)["exit_code"] == 2
    duplicate = b"Model-C & 80.0 & 80.0 & 80.0 & 80.0 \\\\\n"
    store.write("paper.tex", original.replace(b"\\end{tabular}", duplicate + b"\\end{tabular}"))
    report = check_project(store.root)
    assert report["exit_code"] == 2
    assert any(item["rule"] == "ANCHOR_AMBIGUOUS" for item in report["diagnostics"])


def test_cli_catalogue_to_proposal_preserves_exact_selection_ids(batch_project):
    store = batch_project
    catalog = catalogue(store)
    store.write("request.json", json_text(REQUEST).encode())
    store.write("draft.json", json_text(catalog["draft"]).encode())
    command = [
        sys.executable,
        "-m",
        "paperdelta",
        "--lang",
        "zh-CN",
        "-C",
        str(store.root),
        "batch",
    ]
    scanned = subprocess.run(
        [
            *command,
            "scan",
            "--request",
            "request.json",
            "--draft",
            "draft.json",
            "--out",
            "catalog.json",
        ],
        capture_output=True,
        encoding="utf-8",
    )
    assert scanned.returncode == 0, scanned.stderr
    assert len(json.loads(scanned.stdout)["choices"]) == 20
    store.write("selections.json", json_text(choose_every_cell(store, catalog)).encode())
    proposed = subprocess.run(
        [
            *command,
            "propose",
            "--catalog",
            "catalog.json",
            "--selections",
            "selections.json",
            "--out",
            "proposal.json",
            "--format",
            "json",
        ],
        capture_output=True,
        encoding="utf-8",
    )
    assert proposed.returncode == 0, proposed.stderr
    assert json.loads(proposed.stdout)["status"] == "proposed"
    assert check_project(store.root)["coverage"]["confirmed"] == 0
