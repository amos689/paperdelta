from copy import deepcopy

import pytest

from paperdelta.analysis import check_project
from paperdelta.config import config_text, load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.fragments import accept_fragment, preview_fragment
from paperdelta.records import StoredReport, validate_record
from paperdelta.revisions import revision_list
from paperdelta.snapshots import create_snapshot, read_snapshot
from paperdelta.storage import Project


def spec(format="latex", **extra):
    return {
        "format": format,
        "path": "generated/results." + ("tex" if format == "latex" else "md"),
        "occurrences": ["abstract_accuracy", "gain_text"],
        **extra,
    }


@pytest.mark.parametrize("format", ["latex", "markdown"])
@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_fragment_preview_is_deterministic_reviewed_and_tracks_exact_inputs(
    project, change_results, format, language
):
    store = Project(project)
    before = store.read("paperdelta.yaml")
    specification = spec(format, language=language)
    plan = preview_fragment(store, "results", specification)
    repeated = preview_fragment(store, "results", specification)
    assert plan["content"] == repeated["content"]
    assert "84.1" in plan["content"] and "3.1" in plan["content"]
    assert ("绑定" in plan["content"]) == (language == "zh-CN")
    assert store.read("paperdelta.yaml") == before
    assert not store.path(specification["path"]).exists()
    accepted = accept_fragment(store, plan)
    assert store.read(accepted["backup"] + "/config.yaml") == before
    assert store.read(specification["path"]).decode() == plan["content"]
    report = check_project(project)
    assert report["fragments"]["results"]["status"] == "pass"
    validate_record(StoredReport, report, "REPORT_SCHEMA")
    change_results(project)
    report = check_project(project)
    assert report["fragments"]["results"]["status"] == "mismatch"
    assert "fragment:results" in {item["subject"] for item in revision_list(report)}
    updated = preview_fragment(store, "results", specification, replace=True)
    assert "80.9" in updated["content"] and "-0.1" in updated["content"]
    refreshed = accept_fragment(store, updated)
    assert store.read(refreshed["backup"] + "/output").decode() == plan["content"]
    assert check_project(project)["fragments"]["results"]["status"] == "pass"


def test_generated_fragment_does_not_overwrite_edited_files_or_stale_previews(
    project, change_results
):
    store = Project(project)
    plan = preview_fragment(store, "results", spec())
    change_results(project)
    with pytest.raises(PaperDeltaError):
        accept_fragment(store, plan)
    assert not store.path(spec()["path"]).exists()
    accepted = preview_fragment(store, "results", spec())
    accept_fragment(store, accepted)
    store.write(spec()["path"], b"Author's manual changes\n")
    with pytest.raises(PaperDeltaError) as error:
        preview_fragment(store, "results", spec(), replace=True)
    assert error.value.code == "FRAGMENT_EDITED"
    assert store.read(spec()["path"]) == b"Author's manual changes\n"


def test_fragment_rejects_unaccepted_bindings_paths_and_forged_content(project):
    store = Project(project)
    for specification in [
        spec(occurrences=["guessed_metric"]),
        spec(path="paper/main.tex"),
        spec(path=".git/hooks/generated.tex"),
        spec(path="../outside.tex"),
    ]:
        with pytest.raises(PaperDeltaError):
            preview_fragment(store, "results", specification)
    plan = preview_fragment(store, "results", spec())
    bad = deepcopy(plan)
    bad["content"] = "Invented result: 99.9%"
    with pytest.raises(PaperDeltaError):
        accept_fragment(store, bad)
    assert not store.path(spec()["path"]).exists()


def test_contract_changes_are_visible_even_when_current_rendered_value_is_equal(project):
    store = Project(project)
    accept_fragment(store, preview_fragment(store, "results", spec()))
    config, _ = load_config(store)
    config.rounding = "half_even"
    store.write("paperdelta.yaml", config_text(config).encode())
    state = check_project(project)["fragments"]["results"]
    assert state["status"] == "mismatch" and state["contract_changed"]


def test_revision_list_distinguishes_refreshed_table_from_old_prose_and_false_claim(
    project, change_results
):
    store = Project(project)
    create_snapshot(store, "before", check_project(project))
    change_results(project)
    path = "paper/results.tex"
    store.write(path, store.read(path).replace(b"Ours & 84.1", b"Ours & 80.9"))
    report = check_project(project, baseline=read_snapshot(store, "before"))
    items = {item["subject"]: item for item in revision_list(report)}
    assert items["occurrence:table_accuracy"]["kind"] == "table"
    assert items["occurrence:table_accuracy"]["action"] == "review_refreshed"
    assert items["occurrence:abstract_accuracy"]["status"] == "mismatch"
    assert items["claim:main_comparison"]["action"] == "review_claims"
    assert items["occurrence:abstract_accuracy"]["expected"] == r"80.9\%"


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_cli_fragment_preview_accept_and_revision_list(project, language, capsys):
    from paperdelta.cli import main

    prefix = ["--lang", language, "-C", str(project)]
    assert (
        main(
            prefix
            + [
                "fragment",
                "preview",
                "accuracy",
                "--occurrence",
                "abstract_accuracy",
                "--format",
                "markdown",
                "--layout",
                "value",
                "--path",
                "generated/accuracy.md",
                "--out",
                "fragment-plan.json",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert main(prefix + ["fragment", "accept", "fragment-plan.json"]) == 0
    capsys.readouterr()
    assert (project / "generated/accuracy.md").read_text() == "84.1%\n"
    assert main(prefix + ["revisions"]) == 0
    capsys.readouterr()


@pytest.mark.parametrize("format", ["latex", "markdown"])
def test_fragment_preserves_statistical_convention_and_refuses_missing_seed(tmp_path, format):
    from test_statistics import bind, make_project, metric

    from paperdelta import builder
    from paperdelta.onboarding import accept_bindings

    store, draft = make_project(tmp_path)
    proposal = builder.finalize_draft(store, bind(store, metric(store, draft)))
    accept_bindings(store, proposal, ["occurrences:abstract"])
    specification = spec(format, occurrences=["abstract"], layout="value")
    plan = preview_fragment(store, "statistics", specification)
    expected = (
        r"\ensuremath{82.00 \pm 1.58 (n = 5)}" if format == "latex" else "82.00 ± 1.58 (n = 5)"
    )
    assert plan["content"].strip() == expected
    store.write("results.tsv", store.read("results.tsv").replace(b"method\t5\t84\n", b""))
    with pytest.raises(PaperDeltaError):
        preview_fragment(store, "statistics", specification)
