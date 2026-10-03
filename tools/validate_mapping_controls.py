"""Exercise the frozen mapping scorer with known controls, never model responses."""

import argparse
import copy
import json
from datetime import UTC, datetime

from evaluate_mappings import ROOT, SUITE, load_suite, score

from paperdelta.storage import Project, json_text, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = Project(ROOT).path(args.out)
    output.mkdir(parents=True, exist_ok=False)
    manifest, cases = load_suite()
    before = {
        path.relative_to(SUITE).as_posix(): sha256(path.read_bytes())
        for path in SUITE.rglob("*")
        if path.is_file()
    }
    lock_hash = sha256((SUITE / "protocol-lock.json").read_bytes())
    reference = {
        "schema_version": 1,
        "suite_id": manifest["suite_id"],
        "suite_lock_sha256": lock_hash,
        "run": {
            "kind": "control",
            "label": "Reference control",
            "context_protocol": "Constructed directly from known answers. No model or user trial.",
        },
        "answers": {
            name: {
                "decision": "propose",
                "reason": "Known reference control",
                "proposal_input": copy.deepcopy(case["oracle"]["reference_inputs"][0]),
            }
            if case["oracle"]["expected_decision"] == "map"
            else {"decision": "abstain", "reason": case["oracle"]["reason"]}
            for name, case in cases.items()
        },
    }
    adversarial = copy.deepcopy(reference)
    adversarial["run"]["label"] = "Deliberately wrong control"
    answers = adversarial["answers"]
    for name, field, value in [
        ("C01", "split", "train"),
        ("C02", "dataset", "Data-B"),
        ("C03", "variant", "ablated"),
        ("C06", "model", "1"),
    ]:
        answers[name]["proposal_input"]["additions"]["metrics"]["target"]["where"][field] = value
    answers["C04"]["proposal_input"]["additions"]["metrics"]["target"]["unit"] = "percent"
    answers["C05"]["proposal_input"]["additions"]["metrics"]["gain"]["op"] = (
        "relative_change_percent"
    )
    answers["C07"]["proposal_input"]["additions"]["metrics"]["target"]["field"] = (
        "/runs/evaluation~1train/accuracy.mean"
    )
    answers["C09"]["proposal_input"]["additions"]["occurrences"]["result"]["anchor"]["prefix"] = (
        " & "
    )
    for name in ["C10", "C11", "C12"]:
        draft = copy.deepcopy(reference["answers"]["C01"])
        target = cases[name]["oracle"]["target"]
        occurrence = draft["proposal_input"]["additions"]["occurrences"]["result"]
        occurrence["anchor"] = {"prefix": target["prefix"], "suffix": target["suffix"]}
        if name == "C10":
            # A period-only suffix cuts inside the decimal; use its unique full literal.
            occurrence["anchor"] = {"exact": target["literal"]}
        if name == "C11":
            del draft["proposal_input"]["additions"]["metrics"]["target"]["expected_seeds"]
        if name == "C12":
            occurrence["display"] = {"kind": "decimal", "places": 2}
        answers[name] = draft
    reports = {}
    for name, submission in [("reference", reference), ("adversarial", adversarial)]:
        raw = json_text(submission).encode("utf-8")
        (output / f"{name}.submission.json").write_bytes(raw)
        report, review = score(raw, manifest, cases, lock_hash)
        (output / f"{name}.report.json").write_bytes(json_text(report).encode("utf-8"))
        (output / f"{name}.review.template.json").write_bytes(json_text(review).encode("utf-8"))
        assert report["human_measurements"]["candidate_precision"] is None
        assert report["human_measurements"]["ambiguity_rate"] is None
        assert not report["human_measurements"]["confirmation_seconds"]
        reports[name] = report
    assert reports["reference"]["reference_targets_matched"] == 9
    assert reports["reference"]["case_states"] == {"proposed": 9, "expected_abstention": 3}
    assert reports["adversarial"]["candidate_results"] == {
        "reference_contract_mismatch": 7,
        "reference_contract_match": 1,
        "invalid_proposal": 1,
        "proposal_despite_insufficient_evidence": 3,
    }
    for name in ["C01", "C02", "C03", "C06", "C07"]:
        candidate = reports["adversarial"]["outcomes"][name]["candidates"][0]
        assert candidate["core_status"] == "pass"
        assert candidate["result"] == "reference_contract_mismatch"
    assert before == {
        path.relative_to(SUITE).as_posix(): sha256(path.read_bytes())
        for path in SUITE.rglob("*")
        if path.is_file()
    }
    summary = {
        "checked_at": datetime.now(UTC).isoformat(),
        "suite_lock_sha256": lock_hash,
        "kind": "scorer_controls",
        "model_runs": 0,
        "independent_participants": 0,
        "suite_cases": len(cases),
        "reference_mappable_cases": 9,
        "reference_abstention_cases": 3,
        "all_suite_input_bytes_unchanged": True,
        "controls": {
            name: {
                key: report[key]
                for key in (
                    "case_states",
                    "candidate_results",
                    "reference_targets_matched",
                    "human_measurements",
                )
            }
            for name, report in reports.items()
        },
        "files": {
            path.name: sha256(path.read_bytes()) for path in output.iterdir() if path.is_file()
        },
        "scope": "Checks the measurement tool, not the performance of an AI model or a user.",
    }
    (output / "evidence.json").write_bytes(json_text(summary).encode("utf-8"))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
