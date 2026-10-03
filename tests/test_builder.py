import io
from copy import deepcopy
from decimal import Decimal

import pytest

from paperdelta import builder
from paperdelta.analysis import check_project
from paperdelta.errors import PaperDeltaError
from paperdelta.guided import guide_bindings
from paperdelta.i18n import language_context
from paperdelta.onboarding import accept_bindings, init_project, scan_project
from paperdelta.patches import apply_patch, create_patch, recover_transaction
from paperdelta.storage import Project, json_text, parse_json


class Terminal(io.StringIO):
    def isatty(self):
        return True


@pytest.fixture
def unmapped(tmp_path):
    project = Project(tmp_path / "论文 experiment")
    project.write(
        "paper.tex",
        (
            "\ufeff" + "".join(f"Location {letter} score: 84.1\\%.\r\n" for letter in "ABCDEFGHIJ")
        ).encode("utf-8"),
    )
    project.write("results.csv", b"model,seed,score\n001,1,0.840\n001,2,0.842\n002,1,0.123\n")
    init_project(project, "paper.tex", ["results.csv"])
    return project


def files(project):
    return {
        p.relative_to(project.root): p.read_bytes() for p in project.root.rglob("*") if p.is_file()
    }


def metric_draft(project):
    draft = builder.start_draft(project)
    draft = builder.add_source(
        project,
        draft,
        name="experiment",
        path="results.csv",
        format="csv",
        columns={"model": "string", "seed": "integer", "score": "decimal"},
        primary_key=["model", "seed"],
    )
    draft = builder.add_metric(
        project,
        parse_json(json_text(draft)),
        name="score",
        source="experiment",
        field="score",
        unit="fraction",
        reduce="mean",
        where={"model": "001"},
        expected_count=2,
        expected_seeds=["1", "2"],
    )
    return draft


def positions(project, draft):
    return builder.add_occurrences(
        project,
        draft,
        metric="score",
        candidate_ids=[item["candidate_id"] for item in scan_project(project)["candidates"]],
        names=[f"result_{i}" for i in range(10)],
        display_kind="percent",
        places=1,
        percent_symbol=True,
        rationale="Model 001, seeds 1 and 2; mean accuracy; repeated paper uses.",
    )


def test_ten_repeated_locations_have_explicit_contexts_and_survive_patch_recovery(unmapped):
    before = files(unmapped)
    english = positions(unmapped, metric_draft(unmapped))
    with language_context("zh-CN"):
        chinese = positions(unmapped, metric_draft(unmapped))
    assert english == chinese
    proposal = builder.finalize_draft(unmapped, parse_json(json_text(english)))
    assert files(unmapped) == before
    assert all(item["anchor"]["prefix"] for item in proposal["additions"]["occurrences"].values())
    assert proposal["additions"]["metrics"]["score"]["where"] == {"model": "001"}
    accept_bindings(unmapped, proposal, list(proposal["rationale"]))
    assert check_project(unmapped.root)["coverage"]["pass"] == 10
    original_tex = unmapped.read("paper.tex")
    unmapped.write("results.csv", unmapped.read("results.csv").replace(b"0.840", b"0.940"))
    report = check_project(unmapped.root)
    assert report["coverage"]["mismatch"] == 10
    result = apply_patch(unmapped, create_patch(unmapped, report))
    assert result["report"]["coverage"]["pass"] == 10
    recover_transaction(unmapped, result["transaction_id"], write=True)
    assert unmapped.read("paper.tex") == original_tex


@pytest.mark.parametrize("tamper", ["hash", "evidence", "paper", "config"])
def test_each_stage_rejects_changed_identity(unmapped, tamper):
    draft = metric_draft(unmapped)
    if tamper == "hash":
        draft["additions"]["metrics"]["score"]["unit"] = "percent"
    else:
        path = {"evidence": "results.csv", "paper": "paper.tex", "config": "paperdelta.yaml"}[
            tamper
        ]
        unmapped.write(path, unmapped.read(path) + b"\n")
    before = files(unmapped)
    with pytest.raises(PaperDeltaError) as error:
        positions(unmapped, draft)
    assert error.value.code in {"DRAFT_IDENTITY", "STALE_DRAFT"}
    assert files(unmapped) == before


def test_builder_never_selects_by_value_or_silently_reduces_ambiguity(unmapped):
    draft = metric_draft(unmapped)
    for parameters, code in [
        ({"reduce": "unique", "expected_count": 2}, "AMBIGUOUS_SELECTION"),
        ({"reduce": "mean", "expected_count": None}, "BUILDER_EXPECTATION"),
        ({"where": {"model": "1"}}, "EMPTY_SELECTION"),
        ({"where": {"model": 1}}, "BUILDER_SELECTOR"),
        ({"expected_seeds": ["1"]}, "SEED_SET"),
    ]:
        arguments = dict(
            name="other",
            source="experiment",
            field="score",
            unit="fraction",
            reduce="mean",
            where={"model": "001"},
            expected_count=2,
        )
        arguments.update(parameters)
        with pytest.raises(PaperDeltaError) as error:
            builder.add_metric(unmapped, draft, **arguments)
        assert error.value.code == code
    bad = deepcopy(draft)
    bad["draft_id"] = "sha256:" + "0" * 64
    with pytest.raises(PaperDeltaError):
        builder.finalize_draft(unmapped, bad)


def test_overlapping_confirmed_location_cannot_be_added_again(unmapped):
    draft = positions(unmapped, metric_draft(unmapped))
    proposal = builder.finalize_draft(unmapped, draft)
    accept_bindings(unmapped, proposal, ["occurrences:result_0"])
    with pytest.raises(PaperDeltaError) as error:
        builder.add_occurrences(
            unmapped,
            builder.start_draft(unmapped),
            metric="score",
            candidate_ids=[scan_project(unmapped)["candidates"][0]["candidate_id"]],
            names=["another"],
            display_kind="percent",
            places=1,
            percent_symbol=True,
            rationale="explicit",
        )
    assert error.value.code == "BUILDER_OVERLAP"


def test_exact_decimal_selector_survives_stages(unmapped):
    unmapped.write("decimal.csv", b"setting,score\n0.12345678901234567890123456789,0.841\n")
    draft = builder.add_source(
        unmapped,
        builder.start_draft(unmapped),
        name="exact",
        path="decimal.csv",
        format="csv",
        columns={"setting": "decimal", "score": "decimal"},
        primary_key=["setting"],
    )
    draft = builder.add_metric(
        unmapped,
        parse_json(json_text(draft)),
        name="score",
        source="exact",
        field="score",
        unit="fraction",
        reduce="unique",
        where={"setting": "0.12345678901234567890123456789"},
    )
    metric = parse_json(json_text(draft))["additions"]["metrics"]["score"]
    assert metric["where"]["setting"] == Decimal("0.12345678901234567890123456789")


def guide_answers():
    return "\n".join(
        [
            "1",
            "1",
            "experiment",
            "1,2",
            "1",
            "2",
            "3",  # source + explicit types/identity
            "score",
            "3",
            "001",
            "",
            "2",
            "2",
            "2",
            "3",
            "1,2",  # metric, unit/count/seeds
            "",
            ",".join(str(i) for i in range(1, 11)),
            "result",
            "2",
            "1",
            "1",
            "Model 001, seeds 1 and 2; repeated accuracy results",
            "1",
            *("y" for _ in range(10)),
            "accept",
            "",
        ]
    )


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_real_guide_workflow_builds_ten_bindings_without_nested_json(unmapped, language):
    terminal = Terminal()
    with language_context(language):
        result = guide_bindings(
            unmapped, "paperdelta.yaml", input_stream=Terminal(guide_answers()), output=terminal
        )
    assert result["status"] == "accepted", terminal.getvalue()
    assert len(result["bindings"]) == 10
    assert check_project(unmapped.root)["coverage"]["pass"] == 10
    assert ("选中的证据" if language == "zh-CN" else "Selected evidence") in terminal.getvalue()


@pytest.mark.parametrize("answers", ["", ":q\n", guide_answers().replace("accept\n", "\n")])
def test_guide_cancellation_never_writes(unmapped, answers):
    before = files(unmapped)
    result = guide_bindings(
        unmapped, "paperdelta.yaml", input_stream=Terminal(answers), output=Terminal()
    )
    assert result["status"] == "cancelled"
    assert files(unmapped) == before


def test_indistinguishable_repetitions_are_rejected_instead_of_positional_guess(unmapped):
    unmapped.write("paper.tex", b"Values: 84.1 and 84.1 and 84.1 and 84.1.\n")
    draft = metric_draft(unmapped)
    candidate = scan_project(unmapped)["candidates"][1]
    before = files(unmapped)
    with pytest.raises(PaperDeltaError) as error:
        builder.add_occurrences(
            unmapped,
            draft,
            metric="score",
            candidate_ids=[candidate["candidate_id"]],
            names=["middle"],
            display_kind="percent",
            places=1,
            percent_symbol=False,
            rationale="Explicit middle selection",
        )
    assert error.value.code == "BUILDER_ANCHOR"
    assert files(unmapped) == before
