import io
import subprocess
import sys
from copy import deepcopy

import pytest

from paperdelta.agent import AgentSession
from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import language_context
from paperdelta.repairs import (
    accept_repairs,
    confirm_repairs,
    guide_repairs,
    inspect_repair,
    propose_repairs,
    scan_repairs,
)
from paperdelta.snapshots import create_snapshot
from paperdelta.storage import Project, fingerprint, json_text, parse_json


class Terminal(io.StringIO):
    def isatty(self):
        return True


def files(project):
    return {
        p.relative_to(project.root): p.read_bytes() for p in project.root.rglob("*") if p.is_file()
    }


NEW_CLAIM = "We report a higher accuracy than Baseline on Data-A."


@pytest.fixture
def moved(project):
    store = Project(project)
    create_snapshot(store, "before", check_project(project))
    store.write(
        "paper/overview.tex",
        store.read("paper/abstract.tex").replace(
            b"Our method achieves", b"Our updated result reaches"
        ),
    )
    (project / "paper/abstract.tex").unlink()
    store.write(
        "paper/main.tex",
        store.read("paper/main.tex").replace(b"input{abstract}", b"input{overview}"),
    )
    old = b"Our method outperforms Baseline on Data-A."
    assert old in store.read("paper/results.tex")
    store.write(
        "paper/results.tex", store.read("paper/results.tex").replace(old, NEW_CLAIM.encode())
    )
    return store


def selections(project):
    scan = scan_repairs(project, baseline="before")
    candidate = next(item for item in scan["candidates"] if item["file"] == "paper/overview.tex")
    return [
        {
            "binding": "occurrences:abstract_accuracy",
            "candidate_id": candidate["candidate_id"],
            "rationale": "Abstract moved and reworded; the Data-A test accuracy is the same.",
        },
        {
            "binding": "claims:main_comparison",
            "file": "paper/results.tex",
            "anchor": {"exact": NEW_CLAIM},
            "rationale": "The comparison sentence was reworded with the same operands and scope.",
        },
    ]


def test_move_and_claim_rewording_show_old_new_context_and_preserve_science(moved):
    original, _ = load_config(moved)
    before = files(moved)
    scan = scan_repairs(moved, baseline="before")
    assert {item["binding"] for item in scan["broken"]} == {
        "occurrences:abstract_accuracy",
        "claims:main_comparison",
    }
    english = propose_repairs(moved, selections(moved), baseline="before")
    with language_context("zh-CN"):
        chinese = propose_repairs(moved, selections(moved), baseline="before")
    assert english == chinese
    _, _, review = inspect_repair(moved, parse_json(json_text(english)))
    assert "Our updated result reaches" in review["changes"][0]["current_context"]
    assert review["changes"][0]["previous_location"]["text"] == r"84.1\%"
    assert review["changes"][0]["before"]["file"] == "paper/abstract.tex"
    assert review["changes"][0]["after"]["file"] == "paper/overview.tex"
    assert review["preview"]["coverage"]["pass"] == 6
    assert files(moved) == before
    result = accept_repairs(moved, english, [item["binding"] for item in selections(moved)])
    assert result["report"]["exit_code"] == 0
    updated, _ = load_config(moved)
    assert updated.metrics == original.metrics and updated.sources == original.sources
    assert (
        updated.claims["main_comparison"].predicate == original.claims["main_comparison"].predicate
    )
    assert (
        updated.occurrences["abstract_accuracy"].display
        == original.occurrences["abstract_accuracy"].display
    )
    assert (
        moved.read(result["backup"])
        == before[next(p for p in before if p.as_posix() == "paperdelta.yaml")]
    )
    assert all(
        moved.read(path.as_posix()) == value
        for path, value in before.items()
        if path.as_posix() != "paperdelta.yaml"
    )


def test_partial_acceptance_changes_only_selected_binding(moved):
    proposal = propose_repairs(moved, selections(moved), baseline="before")
    original, _ = load_config(moved)
    result = accept_repairs(moved, proposal, ["occurrences:abstract_accuracy"])
    updated, _ = load_config(moved)
    assert updated.claims == original.claims
    assert result["report"]["occurrences"]["abstract_accuracy"]["status"] == "pass"
    assert result["report"]["claims"]["main_comparison"]["status"] == "unknown"
    with pytest.raises(PaperDeltaError) as error:
        accept_repairs(moved, proposal, ["claims:main_comparison"])
    assert error.value.code == "STALE_REPAIR"


@pytest.mark.parametrize(
    "path",
    [
        "paper/overview.tex",
        "results/metrics.csv",
        "paperdelta.yaml",
        ".paperdelta/baselines/before.json",
    ],
)
def test_changed_inputs_invalidate_repairs_before_any_write(moved, path):
    proposal = propose_repairs(moved, selections(moved), baseline="before")
    moved.write(path, moved.read(path) + b"\n")
    before = files(moved)
    with pytest.raises(PaperDeltaError) as error:
        accept_repairs(moved, proposal, ["occurrences:abstract_accuracy"])
    assert error.value.code == "STALE_REPAIR"
    assert files(moved) == before


def test_ambiguous_claim_and_overlapping_numeric_selection_never_relocate(moved):
    choices = selections(moved)
    moved.write("paper/results.tex", moved.read("paper/results.tex") + ("\n" + NEW_CLAIM).encode())
    with pytest.raises(PaperDeltaError) as error:
        propose_repairs(moved, choices)
    assert error.value.code == "ANCHOR_AMBIGUOUS"
    candidate = next(
        item for item in scan_repairs(moved)["candidates"] if item["file"] == "paper/results.tex"
    )
    choices[0]["candidate_id"] = candidate["candidate_id"]
    with pytest.raises(PaperDeltaError) as error:
        propose_repairs(moved, choices[:1])
    assert error.value.code == "BUILDER_OVERLAP"


@pytest.mark.parametrize(
    "selection", [[], ["occurrences:abstract_accuracy"] * 2, ["claims:unknown"]]
)
def test_acceptance_requires_valid_explicit_distinct_ids(moved, selection):
    proposal = propose_repairs(moved, selections(moved))
    before = files(moved)
    with pytest.raises(PaperDeltaError) as error:
        accept_repairs(moved, proposal, selection)
    assert error.value.code == "REPAIR_SELECTION"
    assert files(moved) == before


def test_cannot_smuggle_scientific_changes_into_location_repairs(moved):
    proposal = propose_repairs(moved, selections(moved))
    forged = deepcopy(proposal)
    forged["selections"][0]["metric"] = "baseline"
    forged["repair_id"] = fingerprint(
        {key: value for key, value in forged.items() if key != "repair_id"}
    )
    with pytest.raises(PaperDeltaError) as error:
        inspect_repair(moved, forged)
    assert error.value.code == "REPAIR_SCHEMA"
    forged = deepcopy(proposal)
    forged["selections"][0]["candidate_id"] = "sha256:" + "0" * 64
    with pytest.raises(PaperDeltaError) as error:
        inspect_repair(moved, forged)
    assert error.value.code == "REPAIR_IDENTITY"


@pytest.mark.parametrize("answer", ["", "n\nn\n", "y\ny\n\n"])
def test_interactive_repair_cancellation_never_writes(moved, answer):
    proposal = propose_repairs(moved, selections(moved), baseline="before")
    before = files(moved)
    result = confirm_repairs(moved, proposal, input_stream=Terminal(answer), output=Terminal())
    assert result["status"] == "cancelled"
    assert files(moved) == before


def test_chinese_repair_guide_selects_locations_and_waits_for_final_confirmation(moved):
    scan = scan_repairs(moved)
    numeric = next(
        index
        for index, item in enumerate(scan["candidates"], 1)
        if item["file"] == "paper/overview.tex"
    )
    output = Terminal()
    with language_context("zh-CN"):
        result = guide_repairs(
            moved,
            "paperdelta.yaml",
            "before",
            input_stream=Terminal(f"1\n{numeric}\nSame abstract after move.\n是\n确认\n"),
            output=output,
        )
    assert result["status"] == "accepted"
    assert result["bindings"] == ["occurrences:abstract_accuracy"]
    assert "新的论文上下文" in output.getvalue()


def test_cli_repair_preview_and_explicit_acceptance(moved):
    proposal = propose_repairs(moved, selections(moved), baseline="before")
    moved.write("repair.json", json_text(proposal).encode())
    command = [
        sys.executable,
        "-m",
        "paperdelta",
        "--lang",
        "zh-CN",
        "-C",
        str(moved.root),
        "repair",
        "apply",
        "repair.json",
        "--format",
        "json",
    ]
    before = files(moved)
    preview = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", check=False)
    assert preview.returncode == 0, preview.stderr
    assert parse_json(preview.stdout)["status"] == "proposed"
    assert files(moved) == before
    accepted = subprocess.run(
        command + ["--accept", "occurrences:abstract_accuracy"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert accepted.returncode == 0, accepted.stderr
    assert parse_json(accepted.stdout)["status"] == "accepted"


def test_agent_repair_is_only_a_proposal(moved):
    before = files(moved)
    session = AgentSession(moved)
    with language_context("zh-CN"):
        scan = session.scan_binding_repairs("before")
        assert "明确选择" in scan["notice"]
        choice = selections(moved)[0]
        result = session.propose_binding_repair(
            choice["binding"], choice["rationale"], choice["candidate_id"], None, None, "before"
        )
    assert result["status"] == "proposed"
    assert parse_json(result["repair_json"])["repair_id"] == result["repair_id"]
    assert files(moved) == before
