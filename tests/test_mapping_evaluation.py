import copy
from pathlib import Path

import pytest

from paperdelta.storage import json_text, sha256
from tools.evaluate_mappings import Answer, evaluate_answer, export_tasks, load_suite, score

LOCK = "sha256:" + "a" * 64


@pytest.fixture
def suite():
    return load_suite(verify=False)


def reference_answer(case, alternative=0):
    return Answer(
        decision="propose",
        reason="Synthetic scorer control; not model output.",
        proposal_input=copy.deepcopy(case["oracle"]["reference_inputs"][alternative]),
    )


def control_submission(manifest, cases):
    return {
        "schema_version": 1,
        "suite_id": manifest["suite_id"],
        "suite_lock_sha256": LOCK,
        "run": {
            "kind": "control",
            "label": "Synthetic scorer unit test",
            "context_protocol": "Reads the reference answers; not a model trial.",
        },
        "answers": {
            name: reference_answer(case).model_dump()
            if case["oracle"]["expected_decision"] == "map"
            else {"decision": "abstain", "reason": "Synthetic reference abstention."}
            for name, case in cases.items()
        },
    }


def encoded(value):
    return json_text(value).encode("utf-8")


def test_reference_alternatives_and_stale_mapping_have_independent_expected_states(suite):
    _, cases = suite
    checked = 0
    for name, case in cases.items():
        for alternative in range(len(case["oracle"]["reference_inputs"])):
            result = evaluate_answer(case, reference_answer(case, alternative))
            candidate = result["candidates"][0]
            assert candidate["result"] == "reference_contract_match"
            assert candidate["core_status"] == ("mismatch" if name == "C08" else "pass")
            checked += 1
    assert checked == 10


@pytest.mark.parametrize(
    ("case_id", "field", "wrong_value"),
    [
        ("C01", "split", "train"),
        ("C02", "dataset", "Data-B"),
        ("C03", "variant", "ablated"),
        ("C06", "model", "1"),
    ],
)
def test_equal_numeric_value_does_not_pass_reference_identity(suite, case_id, field, wrong_value):
    case = suite[1][case_id]
    answer = reference_answer(case)
    answer.proposal_input["additions"]["metrics"]["target"]["where"][field] = wrong_value
    candidate = evaluate_answer(case, answer)["candidates"][0]
    assert candidate["core_status"] == "pass"
    assert candidate["result"] == "reference_contract_mismatch"


def test_json_pointer_and_relative_gain_are_part_of_mapping_identity(suite):
    cases = suite[1]
    json_answer = reference_answer(cases["C07"])
    json_answer.proposal_input["additions"]["metrics"]["target"]["field"] = (
        "/runs/evaluation~1train/accuracy.mean"
    )
    candidate = evaluate_answer(cases["C07"], json_answer)["candidates"][0]
    assert candidate["core_status"] == "pass"
    assert candidate["result"] == "reference_contract_mismatch"
    gain = reference_answer(cases["C05"])
    gain.proposal_input["additions"]["metrics"]["gain"]["op"] = "relative_change_percent"
    assert evaluate_answer(cases["C05"], gain)["candidates"][0]["result"] == (
        "reference_contract_mismatch"
    )


def test_missing_seed_and_ambiguous_anchor_are_counted_invalid(suite):
    cases = suite[1]
    result = evaluate_answer(cases["C11"], reference_answer(cases["C01"]))
    assert result["state"] == "invalid_proposal"
    assert len(result["candidates"]) == 1
    incomplete_mean = reference_answer(cases["C01"])
    del incomplete_mean.proposal_input["additions"]["metrics"]["target"]["expected_seeds"]
    assert evaluate_answer(cases["C11"], incomplete_mean)["candidates"][0]["result"] == (
        "proposal_despite_insufficient_evidence"
    )
    table = reference_answer(cases["C09"])
    table.proposal_input["additions"]["occurrences"]["result"]["anchor"]["prefix"] = " & "
    assert evaluate_answer(cases["C09"], table)["state"] == "invalid_proposal"


def test_renamed_ids_preserve_contract_and_exact_anchor_preserves_position(suite):
    case = suite[1]["C01"]
    answer = reference_answer(case)
    additions = answer.proposal_input["additions"]
    additions["metrics"]["renamed"] = additions["metrics"].pop("target")
    occurrence = additions["occurrences"].pop("result")
    occurrence.update(metric="renamed", anchor={"exact": r"84.1\%"})
    additions["occurrences"]["another"] = occurrence
    answer.proposal_input["rationale"] = {"occurrences:another": "Explicit declared identity"}
    candidate = evaluate_answer(case, answer)["candidates"][0]
    assert candidate["result"] == "reference_contract_match"


def test_export_excludes_oracles_and_evaluation_never_changes_inputs(suite, tmp_path):
    manifest, cases = suite
    before = {
        path: sha256(path.read_bytes())
        for case in cases.values()
        for path in Path(case["project"]).rglob("*")
        if path.is_file()
    }
    output = tmp_path / "agent inputs"
    export_tasks(output, manifest, cases, LOCK)
    assert not list(output.rglob("oracle.json"))
    assert not (output / "protocol-lock.json").exists()
    assert len(list((output / "cases").glob("*/REQUEST.md"))) == 12
    for name, case in cases.items():
        for path in case["project"].rglob("*"):
            if path.is_file():
                assert (
                    output / "cases" / name / path.relative_to(case["project"])
                ).read_bytes() == (path.read_bytes())
    report, template = score(encoded(control_submission(manifest, cases)), manifest, cases, LOCK)
    assert report["reference_targets_matched"] == 9
    assert report["case_states"] == {"proposed": 9, "expected_abstention": 3}
    assert report["human_measurements"]["candidate_precision"] is None
    assert all(v["verdict"] is None for v in template["judgments"].values())
    assert before == {path: sha256(path.read_bytes()) for path in before}
    with pytest.raises(FileExistsError):
        export_tasks(output, manifest, cases, LOCK)


def test_invalid_candidates_cannot_disappear_from_review_denominator(suite):
    manifest, cases = suite
    submission = control_submission(manifest, cases)
    submission["answers"]["C01"]["proposal_input"]["additions"]["metrics"]["target"]["field"] = (
        "imaginary_column"
    )
    raw = encoded(submission)
    report, template = score(raw, manifest, cases, LOCK)
    assert report["candidate_records"] == 9 and report["candidate_count_exact"]
    assert report["candidate_results"]["invalid_proposal"] == 1
    assert "C01/occurrences:result" in template["judgments"]
    template.update(reviewer="Synthetic fixture", reviewer_kind="synthetic_test", observed=True)
    for value in template["judgments"].values():
        value["verdict"] = "correct"
    with pytest.raises(ValueError, match="invalid proposal"):
        score(raw, manifest, cases, LOCK, encoded(template))
    template["judgments"]["C01/occurrences:result"]["verdict"] = "incorrect"
    result, _ = score(raw, manifest, cases, LOCK, encoded(template))
    assert result["human_measurements"]["candidate_precision"] is None


def test_unparsed_candidate_counts_disable_precision_and_missing_cases_remain(suite):
    manifest, cases = suite
    submission = control_submission(manifest, cases)
    submission["answers"]["C01"]["proposal_input"] = {"unexpected": True}
    del submission["answers"]["C02"]
    report, _ = score(encoded(submission), manifest, cases, LOCK)
    assert report["candidate_count_exact"] is False
    assert report["case_states"]["invalid_proposal"] == 1
    assert report["case_states"]["missing"] == 1
    assert report["reference_targets_matched"] == 7
    assert report["human_measurements"]["candidate_precision"] is None


def test_review_requires_matching_submission_all_candidates_and_declared_observation(suite):
    manifest, cases = suite
    raw = encoded(control_submission(manifest, cases))
    _, template = score(raw, manifest, cases, LOCK)
    stale = copy.deepcopy(template)
    stale["submission_sha256"] = "sha256:" + "b" * 64
    with pytest.raises(ValueError, match="stale"):
        score(raw, manifest, cases, LOCK, encoded(stale))
    missing = copy.deepcopy(template)
    missing["judgments"].pop("C01/occurrences:result")
    with pytest.raises(ValueError, match="every candidate"):
        score(raw, manifest, cases, LOCK, encoded(missing))
    template["judgments"]["C01/occurrences:result"]["confirmation_seconds"] = 1.0
    with pytest.raises(ValueError, match="observer"):
        score(raw, manifest, cases, LOCK, encoded(template))


def test_adjudicated_precision_is_conditional_on_a_complete_declared_model_review(suite):
    manifest, cases = suite
    submission = control_submission(manifest, cases)
    submission["run"].update(
        kind="model",
        model="UNIT-TEST-ONLY",
        label="Synthetic review-schema test; not an actual run",
    )
    raw = encoded(submission)
    _, template = score(raw, manifest, cases, LOCK)
    template.update(reviewer="Synthetic test data", reviewer_kind="developer", observed=True)
    for value in template["judgments"].values():
        value["verdict"] = "correct"
    template["judgments"]["C01/occurrences:result"]["verdict"] = "incorrect"
    template["judgments"]["C02/occurrences:result"]["verdict"] = "ambiguous"
    result, _ = score(raw, manifest, cases, LOCK, encoded(template))
    assert result["human_measurements"]["candidate_precision"] == pytest.approx(7 / 9)
    assert result["human_measurements"]["ambiguity_rate"] == pytest.approx(1 / 9)
    template["judgments"]["C03/occurrences:result"]["verdict"] = None
    result, _ = score(raw, manifest, cases, LOCK, encoded(template))
    assert result["human_measurements"]["candidate_precision"] is None
