"""Check strict scorer behavior using declared reference controls, never inference."""

import argparse
from copy import deepcopy
from pathlib import Path

from paperdelta.errors import PaperDeltaError
from paperdelta.onboarding import propose_bindings
from paperdelta.storage import Project, json_text, parse_json
from tools.evaluate_mapping_v5 import assess, cases_for
from tools.evaluate_staged_mappings import write_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    assert not args.out.exists()
    cases, _ = cases_for("development")
    records = []
    for name, case in cases.items():
        oracle = parse_json((case["path"] / "oracle.json").read_text("utf-8"))
        project = Project(case["path"] / "project")
        for index, reference in enumerate(oracle["reference_inputs"]):
            proposal = propose_bindings(project, **reference)
            outcome = assess(case, {"status": "proposed", "proposal": proposal}, "development")
            assert outcome["complete_mapping"] and outcome["count_guard_verified"], (name, outcome)
            records.append({"case": name, "control": index, "result": outcome})
        for status in (
            "abstained",
            "budget_exhausted",
            "transport_or_runtime_error",
            "action_limit",
        ):
            result = assess(case, {"status": status}, "development")
            assert result["expected_abstention"] == (
                status == "abstained" and oracle["expected_decision"] == "abstain"
            )
    case = cases["D01"]
    original = parse_json((case["path"] / "oracle.json").read_text("utf-8"))["reference_inputs"][0]
    for mutation in ("same_number_wrong_checkpoint", "wrong_unit", "wrong_precision"):
        reference = deepcopy(original)
        metric = reference["additions"]["metrics"]["target"]
        if mutation == "same_number_wrong_checkpoint":
            metric["where"]["checkpoint"] = "alternate"
        elif mutation == "wrong_unit":
            metric["unit"] = "percent"
        else:
            reference["additions"]["occurrences"]["requested"]["display"]["places"] = 2
        proposal = propose_bindings(Project(case["path"] / "project"), **reference)
        result = assess(case, {"status": "proposed", "proposal": proposal}, "development")
        assert result["core_valid_proposal"] and not result["complete_mapping"]
        records.append({"case": "D01", "control": mutation, "result": result})
    invalid = deepcopy(original)
    invalid["additions"]["metrics"]["target"]["expected_count"] = 2
    try:
        propose_bindings(Project(case["path"] / "project"), **invalid)
    except PaperDeltaError as error:
        records.append({"case": "D01", "control": "wrong_count_rejected", "error": error.code})
    else:
        raise AssertionError("Wrong count accepted")
    write_new(
        args.out / "evidence.json",
        {
            "status": "passed",
            "model_calls": 0,
            "scope": "Reference and adversarial scorer controls on development tasks only.",
            "cases": records,
        },
    )
    print(
        json_text(
            {
                "status": "passed",
                "reference_and_adversarial_controls": len(records),
                "model_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
