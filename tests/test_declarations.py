from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from paperdelta.config import config_text, load_config
from paperdelta.declarations import (
    accept_maintenance,
    dependents,
    inspect_maintenance,
    propose_maintenance,
)
from paperdelta.errors import PaperDeltaError
from paperdelta.storage import Project, json_text


def edit(group, name, definition=None):
    return {
        "group": group,
        "name": name,
        "operation": "replace" if definition is not None else "remove",
        "definition_json": json_text(definition) if definition is not None else None,
        "rationale": "Reviewed the intended result identity and affected paper positions.",
    }


def test_preview_edit_backup_and_report_preserve_inputs(project):
    store = Project(project)
    config, _ = load_config(store)
    original = store.read("paperdelta.yaml")
    inputs = {p: store.read(p) for p in ("results/metrics.csv", "paper/abstract.tex")}
    definition = config.occurrences["abstract_accuracy"].model_dump()
    definition["display"]["places"] = 2
    proposal, preview = propose_maintenance(
        store, [edit("occurrences", "abstract_accuracy", definition)]
    )
    assert preview["preview"]["occurrences"]["abstract_accuracy"]["expected"] == r"84.10\%"
    assert store.read("paperdelta.yaml") == original
    receipt = accept_maintenance(store, proposal)
    assert store.read(receipt["backup"]) == original
    assert load_config(store)[0].occurrences["abstract_accuracy"].display.places == 2
    assert {p: store.read(p) for p in inputs} == inputs
    with pytest.raises(PaperDeltaError, match="Inputs changed"):
        accept_maintenance(store, proposal)


def test_shared_metric_dependency_preview_and_no_dangling_deletion(project):
    store = Project(project)
    config, _ = load_config(store)
    related = dependents(config, ["metrics:ours"])
    assert "occurrences:abstract_accuracy" in related
    assert "metrics:gain" in related
    assert "claims:main_comparison" in related
    original = store.read("paperdelta.yaml")
    with pytest.raises(PaperDeltaError) as error:
        propose_maintenance(store, [edit("metrics", "ours")])
    assert error.value.code == "MAINTENANCE_DEPENDENCY"
    assert store.read("paperdelta.yaml") == original
    proposal, preview = propose_maintenance(
        store, [edit(*identity.split(":")) for identity in related]
    )
    assert preview["coverage_after"]["confirmed"] < preview["coverage_before"]["confirmed"]
    assert any(item["before"] and item["after"] is None for item in preview["states"])
    accept_maintenance(store, proposal)
    assert "ours" not in load_config(store)[0].metrics


def test_maintenance_preview_includes_figures_sharing_changed_metric_evidence(project):
    from tools.demo import add_figure

    store = Project(project)
    add_figure(store, Path(__file__).resolve().parents[1])
    config, _ = load_config(store)
    definition = config.metrics["ours"].model_dump()
    definition["expected_count"] = 3
    _, preview = propose_maintenance(store, [edit("metrics", "ours", definition)])
    assert "figures:accuracy" in preview["affected"]
    assert (
        next(item for item in preview["states"] if item["id"] == "figures:accuracy")["after"][
            "status"
        ]
        == "pass"
    )


@pytest.mark.parametrize("target", ["paper/abstract.tex", "results/metrics.csv", "paperdelta.yaml"])
def test_stale_edit_never_writes_configuration(project, target):
    store = Project(project)
    proposal, _ = propose_maintenance(store, [edit("occurrences", "abstract_accuracy")])
    store.write(target, store.read(target) + b"\n")
    original = store.read("paperdelta.yaml")
    with pytest.raises(PaperDeltaError) as error:
        accept_maintenance(store, proposal)
    assert error.value.code == "STALE_MAINTENANCE"
    assert store.read("paperdelta.yaml") == original
    assert not store.path(".paperdelta/config-backups").exists()


def test_decimal_definition_survives_browser_text_and_preview(project):
    store = Project(project)
    config, _ = load_config(store)
    definition = config.claims["main_comparison"].model_dump()
    exact = Decimal("0.8409999999999999999999999999999")
    definition["predicate"] = {
        "op": "greater_than",
        "left": "ours",
        "right": {"value": exact, "unit": "fraction"},
    }
    proposal, preview = propose_maintenance(store, [edit("claims", "main_comparison", definition)])
    assert preview["preview"]["claims"]["main_comparison"]["status"] == "pass"
    accept_maintenance(store, proposal)
    assert load_config(store)[0].claims["main_comparison"].predicate.right.value == exact


def test_changed_input_appearing_and_tampered_preview_are_refused(project):
    store = Project(project)
    config, _ = load_config(store)
    config.sources["unused"] = config.sources[next(iter(config.sources))].model_copy(
        update={"path": "later.csv"}
    )
    store.write("paperdelta.yaml", config_text(config).encode())
    proposal, _ = propose_maintenance(store, [edit("sources", "unused")])
    tampered = deepcopy(proposal)
    tampered["edits"][0]["name"] = "not_the_same"
    with pytest.raises(PaperDeltaError) as error:
        inspect_maintenance(store, tampered)
    assert error.value.code == "MAINTENANCE_IDENTITY"
    store.write("later.csv", b"value\n1\n")
    with pytest.raises(PaperDeltaError) as error:
        accept_maintenance(store, proposal)
    assert error.value.code == "STALE_MAINTENANCE"


def test_overlapping_replacement_is_not_accepted(project):
    store = Project(project)
    config, _ = load_config(store)
    definition = config.occurrences["abstract_accuracy"].model_dump()
    other = next(v for k, v in config.occurrences.items() if k != "abstract_accuracy")
    definition.update(file=other.file, anchor=other.anchor.model_dump())
    with pytest.raises(PaperDeltaError) as error:
        propose_maintenance(store, [edit("occurrences", "abstract_accuracy", definition)])
    assert error.value.code == "MAINTENANCE_OVERLAP"


def test_removing_a_failed_binding_exposes_previous_failure_and_coverage(project, change_results):
    change_results(project)
    proposal, preview = propose_maintenance(
        Project(project), [edit("occurrences", "abstract_accuracy")]
    )
    assert preview["states"][0]["before"]["status"] == "mismatch"
    assert preview["states"][0]["after"] is None
    assert preview["coverage_after"]["unbound_numbers"]
    assert proposal["edits"][0]["rationale"]
