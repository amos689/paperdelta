import copy
import subprocess
import sys
from decimal import Decimal

import pytest

from paperdelta.analysis import check_project
from paperdelta.config import load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.onboarding import (
    accept_bindings,
    init_project,
    inspect_proposal,
    propose_bindings,
    scan_project,
)
from paperdelta.storage import Project, json_text, parse_json


@pytest.fixture
def unmapped(project):
    config, _ = load_config(Project(project))
    additions = {
        group: getattr(config, group)
        for group in ("sources", "metrics", "occurrences", "claims", "figures")
    }
    (project / "paperdelta.yaml").unlink()
    init_project(Project(project), "paper/main.tex", ["results/metrics.csv"], macros={"score": 1})
    return project, additions


def proposal_for(project, additions):
    reasons = {
        f"{group}:{name}": "Author confirms Data-A test split, seeds 1–3, accuracy."
        for group in ("occurrences", "claims", "figures")
        for name in additions[group]
    }
    return propose_bindings(Project(project), additions, reasons)


def test_init_and_scan_discover_without_accepting_anything(unmapped):
    project, _ = unmapped
    report = check_project(project)
    assert report["exit_code"] == 2 and report["coverage"]["confirmed"] == 0
    before = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    scan = scan_project(Project(project))
    assert len(scan["candidates"]) == 5
    assert scan["candidates"][0]["priority_hint"] == "abstract"
    assert scan["sources"][0]["sample"][0]["seed"] == "1"
    assert scan["confirmed"] == {"occurrences": [], "claims": [], "figures": []}
    after = {p.relative_to(project): p.read_bytes() for p in project.rglob("*") if p.is_file()}
    assert before == after


def test_scan_prioritizes_inline_abstract_and_table_without_trusting_comments(tmp_path):
    project = Project(tmp_path)
    project.write(
        "main.tex",
        (
            "Ordinary result: 1.1. Repeated: 2.2 and 2.2.\n"
            r"\begin{abstract}Summary: 3.3.\end{abstract}"
            "\n"
            r"\begin{table}\begin{tabular}{ll}Ours & 4.4\\\end{tabular}\end{table}"
            "\n% " + r"\begin{table}" + "\nOther result: 5.5.\n"
        ).encode(),
    )
    init_project(project, "main.tex", [])
    candidates = scan_project(project)["candidates"]
    assert [(v["text"], v["priority_hint"]) for v in candidates] == [
        ("3.3", "abstract"),
        ("4.4", "table"),
        ("2.2", "repeated"),
        ("2.2", "repeated"),
        ("1.1", "body"),
        ("5.5", "body"),
    ]


def test_proposal_preview_has_evidence_without_modifying_config(unmapped):
    project, additions = unmapped
    before = (project / "paperdelta.yaml").read_bytes()
    proposal = proposal_for(project, additions)
    _, _, preview = inspect_proposal(Project(project), parse_json(json_text(proposal)))
    assert preview["exit_code"] == 0
    assert preview["metrics"]["ours"]["evidence"][0]["count"] == 3
    assert (project / "paperdelta.yaml").read_bytes() == before
    assert check_project(project)["coverage"]["confirmed"] == 0


def test_accept_only_selected_binding_and_its_required_dependencies(unmapped):
    project, additions = unmapped
    proposal = proposal_for(project, additions)
    result = accept_bindings(Project(project), proposal, ["occurrences:abstract_accuracy"])
    config, _ = load_config(Project(project))
    assert set(config.occurrences) == {"abstract_accuracy"}
    assert set(config.metrics) == {"ours"}
    assert set(config.sources) == {"benchmark"}
    assert not config.claims
    assert (project / result["backup"]).exists()
    assert check_project(project)["coverage"]["confirmed"] == 1


def test_claim_acceptance_adds_both_metric_dependencies(unmapped):
    project, additions = unmapped
    proposal = proposal_for(project, additions)
    accept_bindings(Project(project), proposal, ["claims:main_comparison"])
    config, _ = load_config(Project(project))
    assert set(config.metrics) == {"ours", "baseline"} and not config.occurrences
    assert check_project(project)["claims"]["main_comparison"]["status"] == "pass"


def test_changed_evidence_invalidates_unaccepted_proposal(unmapped, change_results):
    project, additions = unmapped
    proposal = proposal_for(project, additions)
    change_results(project)
    before = (project / "paperdelta.yaml").read_bytes()
    with pytest.raises(PaperDeltaError) as error:
        accept_bindings(Project(project), proposal, ["occurrences:abstract_accuracy"])
    assert error.value.code == "STALE_PROPOSAL"
    assert (project / "paperdelta.yaml").read_bytes() == before


def test_ambiguous_numeric_anchor_cannot_be_proposed(unmapped):
    project, additions = unmapped
    abstract = project / "paper/abstract.tex"
    abstract.write_bytes(abstract.read_bytes() * 2)
    with pytest.raises(PaperDeltaError) as error:
        proposal_for(project, additions)
    assert error.value.code == "PROPOSAL_UNRESOLVED"


def test_proposal_cannot_overwrite_confirmed_configuration(project):
    config, _ = load_config(Project(project))
    with pytest.raises(PaperDeltaError) as error:
        propose_bindings(
            Project(project),
            {"occurrences": {"abstract_accuracy": config.occurrences["abstract_accuracy"]}},
            {"occurrences:abstract_accuracy": "Same number"},
        )
    assert error.value.code == "BINDING_CONFLICT"


@pytest.mark.parametrize("selected", [[], ["all"], ["occurrences:abstract_accuracy"] * 2])
def test_binding_acceptance_requires_explicit_unique_valid_ids(unmapped, selected):
    project, additions = unmapped
    with pytest.raises(PaperDeltaError) as error:
        accept_bindings(Project(project), proposal_for(project, additions), selected)
    assert error.value.code == "BINDING_SELECTION"


def test_existing_project_initialization_never_overwrites_config(project):
    before = (project / "paperdelta.yaml").read_bytes()
    with pytest.raises(PaperDeltaError) as error:
        init_project(Project(project), "paper/main.tex", [])
    assert error.value.code == "ALREADY_EXISTS"
    assert (project / "paperdelta.yaml").read_bytes() == before


def test_cli_bind_preview_then_explicit_selection(unmapped):
    project, additions = unmapped
    proposal = proposal_for(project, additions)
    (project / "proposal.json").write_text(json_text(proposal), encoding="utf-8")
    command = [
        sys.executable,
        "-m",
        "paperdelta",
        "-C",
        str(project),
        "bind",
        "--proposal",
        "proposal.json",
    ]
    preview = subprocess.run(command, capture_output=True, encoding="utf-8", check=False)
    assert preview.returncode == 0 and parse_json(preview.stdout)["status"] == "proposed"
    assert check_project(project)["coverage"]["confirmed"] == 0
    accepted = subprocess.run(
        command + ["--accept", "occurrences:abstract_accuracy"],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert accepted.returncode == 0 and parse_json(accepted.stdout)["status"] == "accepted"
    assert check_project(project)["coverage"]["confirmed"] == 1


def test_decimal_selector_survives_proposal_json_and_config_yaml_roundtrip(tmp_path):
    store = Project(tmp_path)
    store.write("paper.tex", b"Result: 12.3 points.")
    store.write("results.csv", b"setting,score\n0.1,12.3\n")
    init_project(store, "paper.tex", ["results.csv"])
    additions = {
        "sources": {
            "experiment": {
                "path": "results.csv",
                "format": "csv",
                "primary_key": ["setting"],
                "columns": {"setting": "decimal", "score": "decimal"},
            }
        },
        "metrics": {
            "score": {
                "source": "experiment",
                "field": "score",
                "where": {"setting": Decimal("0.1")},
                "unit": "scalar",
            }
        },
        "occurrences": {
            "result": {
                "file": "paper.tex",
                "anchor": {"prefix": "Result: ", "suffix": " points."},
                "metric": "score",
            }
        },
    }
    proposal = propose_bindings(store, additions, {"occurrences:result": "Explicit setting 0.1"})
    reloaded = parse_json(json_text(proposal))
    accept_bindings(store, reloaded, ["occurrences:result"])
    assert load_config(store)[0].metrics["score"].where["setting"] == Decimal("0.1")
    assert check_project(tmp_path)["exit_code"] == 0


@pytest.mark.parametrize("rationale", [None, [], {"occurrences:x": 12}])
def test_malformed_proposal_rationale_is_rejected(project, rationale):
    with pytest.raises(PaperDeltaError) as error:
        propose_bindings(Project(project), {}, rationale)
    assert error.value.code == "PROPOSAL_SCHEMA"


def test_edited_proposal_identity_is_rejected(unmapped):
    project, additions = unmapped
    proposal = copy.deepcopy(proposal_for(project, additions))
    proposal["rationale"]["occurrences:abstract_accuracy"] = "Replaced rationale"
    with pytest.raises(PaperDeltaError) as error:
        inspect_proposal(Project(project), proposal)
    assert error.value.code == "PROPOSAL_IDENTITY"
