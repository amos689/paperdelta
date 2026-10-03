import pytest
from pydantic import ValidationError

from paperdelta.builder import start_draft
from paperdelta.errors import PaperDeltaError
from paperdelta.storage import Project, parse_json
from tools import evaluate_staged_mappings as evaluation


def test_prepared_prompts_exclude_oracles_and_protocol_detects_implementation_drift(
    tmp_path, monkeypatch
):
    provenance = tmp_path / "provenance.json"
    provenance.write_text('{"kind":"test-only, no model executed"}', encoding="utf-8")
    directory = tmp_path / "prepared"
    evaluation.prepare(directory, "test-only", provenance)
    protocol = evaluation.verify_protocol(directory)
    assert len(protocol["initial_prompt_sha256"]) == 12
    for path in (directory / "initial-prompts").glob("*.json"):
        messages = parse_json(path.read_text("utf-8"))
        context = parse_json(messages[1]["content"])
        assert "oracle.json" not in context["project_files"]
        assert "reference_inputs" not in context
        assert "expected_decision" not in context
    monkeypatch.setattr(evaluation, "identities", lambda: {"modified": "implementation"})
    with pytest.raises(ValueError, match="changed"):
        evaluation.verify_protocol(directory)


def test_action_errors_and_abstention_do_not_modify_project(project):
    store = Project(project)
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    draft = start_draft(store)
    for raw, error in [
        ({"action": "shell", "arguments": {}, "reason": "invalid"}, ValidationError),
        ({"action": "abstain", "arguments": {"source": "x"}, "reason": "invalid"}, ValueError),
        ({"action": "finish", "arguments": {}, "reason": "No added bindings"}, PaperDeltaError),
        (
            {
                "action": "metric",
                "arguments": {
                    "name": "x",
                    "source": "benchmark",
                    "field": "accuracy",
                    "unit": "fraction",
                    "reduce": "mean",
                    "expected_count": "3",
                },
                "reason": "bad type",
            },
            ValidationError,
        ),
    ]:
        with pytest.raises(error):
            evaluation.execute_action(store, draft, raw)
    returned, result = evaluation.execute_action(
        store, draft, {"action": "abstain", "arguments": {}, "reason": "Unknown identity"}
    )
    assert returned == draft and result["terminal"] == "abstain" and result["proposal"] is None
    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == before


def test_identity_comparison_ignores_only_count_guards_and_keeps_scope_unit_seeds():
    reference = {
        "metric": {
            "where": {"split": "test", "model": "001"},
            "unit": "fraction",
            "expected_seeds": [1, 2, 3],
            "expected_count": None,
        },
        "display": {"kind": "percent", "places": 1},
    }
    guarded = {**reference, "metric": {**reference["metric"], "expected_count": 3}}
    assert reference != guarded
    assert evaluation.without_count(reference) == evaluation.without_count(guarded)
    for key, wrong in [
        ("where", {"split": "train", "model": "001"}),
        ("unit", "percent"),
        ("expected_seeds", [1, 2]),
    ]:
        candidate = {**guarded, "metric": {**guarded["metric"], key: wrong}}
        assert evaluation.without_count(candidate) != evaluation.without_count(reference)
