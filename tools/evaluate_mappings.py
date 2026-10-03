"""Export answer-free mapping tasks and score saved proposals without calling a model.

Reference-contract matches and human judgments are separate measurements. Neither
structural validity nor agreement with a number establishes scientific identity.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal, Self

from pydantic import Field, ValidationError, model_validator

import paperdelta
from paperdelta.errors import PaperDeltaError
from paperdelta.models import Config, DerivedMetric, Hash, Identifier, StrictModel, VersionOne
from paperdelta.onboarding import ProposalInput, inspect_proposal, propose_bindings
from paperdelta.storage import Project, fingerprint, json_text, parse_json, sha256

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "evaluations/mapping-v1"
Nonempty = Annotated[str, Field(min_length=1)]


class Run(StrictModel):
    kind: Literal["control", "model"]
    label: Nonempty
    model: str | None = None
    context_protocol: Nonempty

    @model_validator(mode="after")
    def named_model(self) -> Self:
        if self.kind == "model" and not (self.model or "").strip():
            raise ValueError("A model run must identify its actual model")
        return self


class Answer(StrictModel):
    decision: Literal["propose", "abstain"]
    reason: Nonempty
    proposal_input: dict[str, Any] | None = None

    @model_validator(mode="after")
    def decision_payload(self) -> Self:
        if (self.decision == "propose") != (self.proposal_input is not None):
            raise ValueError("Only propose decisions require proposal_input")
        return self


class Submission(StrictModel):
    schema_version: VersionOne
    suite_id: str
    suite_lock_sha256: Hash
    run: Run
    answers: dict[Identifier, Answer]


class Judgment(StrictModel):
    verdict: Literal["correct", "incorrect", "ambiguous"] | None = None
    confirmation_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)] | None = None
    note: str = ""


class Review(StrictModel):
    schema_version: VersionOne
    submission_sha256: Hash
    reviewer: str | None = None
    reviewer_kind: Literal["independent_user", "developer", "synthetic_test"] | None = None
    observed: bool = False
    judgments: dict[str, Judgment]

    @model_validator(mode="after")
    def measured_review(self) -> Self:
        measured = any(
            value.verdict is not None or value.confirmation_seconds is not None
            for value in self.judgments.values()
        )
        if measured and not (
            self.observed and (self.reviewer or "").strip() and self.reviewer_kind
        ):
            raise ValueError("Judgments/times require a declared observer and observed=true")
        return self


def identities(suite=SUITE):
    files = [p for p in suite.rglob("*") if p.is_file() and p != suite / "protocol-lock.json"]
    files += [
        ROOT / "tools/evaluate_mappings.py",
        ROOT / "tools/create_mapping_suite.py",
        ROOT / "tools/validate_mapping_controls.py",
    ]
    files += list((ROOT / "src/paperdelta").glob("*.py"))
    return {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()) for path in sorted(files)}


def load_suite(*, verify=True, suite=SUITE):
    manifest = parse_json((suite / "manifest.json").read_text("utf-8"))
    cases = {}
    for case in manifest["cases"]:
        name = case["id"]
        assert name not in cases and name.isalnum(), "Unique simple case IDs required"
        directory = suite / "cases" / name
        cases[name] = {
            "project": directory / "project",
            "request": directory / "request.md",
            "oracle": parse_json((directory / "oracle.json").read_text("utf-8")),
        }
    lock_path = suite / "protocol-lock.json"
    if verify:
        lock = parse_json(lock_path.read_text("utf-8"))
        if lock["identities"] != identities(suite):
            raise ValueError("Mapping suite changed; retain prior results and version a new suite")
        imported = Path(paperdelta.__file__).resolve().parent
        for path in (ROOT / "src/paperdelta").glob("*.py"):
            if (imported / path.name).read_bytes() != path.read_bytes():
                raise ValueError("Install the matching PaperDelta implementation before scoring")
    return manifest, cases


def contract(config: Config, name: str):
    metric = config.metrics[name]
    if isinstance(metric, DerivedMetric):
        return {"op": metric.op, "args": [contract(config, child) for child in metric.args]}
    value = metric.model_dump()
    source = config.sources[metric.source].model_dump()
    source["primary_key"] = sorted(source["primary_key"])
    value["source"] = source
    if value["expected_seeds"] is not None:
        value["expected_seeds"] = sorted(
            value["expected_seeds"], key=lambda v: (type(v).__name__, str(v))
        )
    return value


def expected_target(case):
    target = case["oracle"]["target"]
    text = (case["project"] / target["file"]).read_bytes().decode("utf-8")
    exact = target["prefix"] + target["literal"] + target["suffix"]
    assert text.count(exact) == 1, "The manually annotated target must be unique"
    start = text.index(exact) + len(target["prefix"])
    return {
        "file": target["file"],
        "byte_start": len(text[:start].encode("utf-8")),
        "byte_end": len(text[: start + len(target["literal"])].encode("utf-8")),
    }


def reference_contracts(case):
    values = []
    for raw in case["oracle"]["reference_inputs"]:
        proposal = ProposalInput.model_validate(raw)
        config = Config(
            schema_version=1,
            paper={"entry": "paper/main.tex"},
            **proposal.additions.model_dump(),
        )
        occurrence = next(iter(config.occurrences.values()))
        values.append(
            {
                "metric": contract(config, occurrence.metric),
                "display": occurrence.display.model_dump(),
            }
        )
    return values


def evaluate_answer(case, answer):
    expected = case["oracle"]["expected_decision"]
    if answer is None:
        return {"state": "missing", "candidates": []}
    if answer.decision == "abstain":
        return {
            "state": "expected_abstention" if expected == "abstain" else "missed_mapping",
            "reason": answer.reason,
            "candidates": [],
        }
    try:
        value = ProposalInput.model_validate(answer.proposal_input)
        if value.additions.claims or value.additions.figures or not value.additions.occurrences:
            raise ValueError("This suite requests numeric occurrences only")
        project = Project(case["project"])
        proposal = propose_bindings(project, value.additions.model_dump(), value.rationale)
        _, config, report = inspect_proposal(project, proposal)
    except (ValueError, PaperDeltaError) as error:
        additions = answer.proposal_input.get("additions", {})
        raw_occurrences = additions.get("occurrences", {}) if isinstance(additions, dict) else {}
        names = list(raw_occurrences) if isinstance(raw_occurrences, dict) else []
        return {
            "state": "invalid_proposal",
            "candidates": [
                {"binding": f"occurrences:{name}", "result": "invalid_proposal"} for name in names
            ]
            or [
                {
                    "binding": "proposal:unparsed",
                    "result": "invalid_proposal",
                    "candidate_count_unknown": True,
                }
            ],
            "error": getattr(error, "code", type(error).__name__),
            "message": str(error),
        }
    target = expected_target(case)
    references = reference_contracts(case)
    candidates = []
    seen_positions = set()
    for name in value.additions.occurrences:
        state = report["occurrences"][name]
        occurrence = config.occurrences[name]
        location = {key: state["location"][key] for key in target}
        signature = {
            "metric": contract(config, occurrence.metric),
            "display": occurrence.display.model_dump(),
        }
        position = fingerprint(location)
        if expected == "abstain":
            result = "proposal_despite_insufficient_evidence"
        elif location != target:
            result = "wrong_position"
        elif signature not in references:
            result = "reference_contract_mismatch"
        else:
            result = "reference_contract_match"
        candidates.append(
            {
                "binding": f"occurrences:{name}",
                "result": result,
                "core_status": state["status"],
                "paper_value": state["actual"],
                "expected_display": state["expected"],
                "location": location,
                "contract": signature,
                "duplicate_target": position in seen_positions,
            }
        )
        seen_positions.add(position)
    return {"state": "proposed", "reason": answer.reason, "candidates": candidates}


def score(submission_raw, manifest, cases, lock_hash, review_raw=None):
    submission = Submission.model_validate(parse_json(submission_raw.decode("utf-8")))
    if submission.suite_id != manifest["suite_id"] or submission.suite_lock_sha256 != lock_hash:
        raise ValueError("Submission belongs to another suite identity")
    if set(submission.answers) - set(cases):
        raise ValueError("Submission includes an unknown case ID")
    outcomes = {
        name: evaluate_answer(case, submission.answers.get(name)) for name, case in cases.items()
    }
    candidates = {
        f"{case_id}/{candidate['binding']}": candidate
        for case_id, result in outcomes.items()
        for candidate in result["candidates"]
    }
    digest = sha256(submission_raw)
    template = Review(
        schema_version=1,
        submission_sha256=digest,
        judgments={name: Judgment() for name in candidates},
    )
    review = (
        template
        if review_raw is None
        else Review.model_validate(parse_json(review_raw.decode("utf-8")))
    )
    if review.submission_sha256 != digest:
        raise ValueError("Review is stale: submission bytes changed")
    if set(review.judgments) != set(candidates):
        raise ValueError("Review must list every candidate once, leaving unreviewed verdicts null")
    if any(
        candidate["result"] == "invalid_proposal" and review.judgments[name].verdict == "correct"
        for name, candidate in candidates.items()
    ):
        raise ValueError("A structurally invalid proposal cannot be scored as correct")
    counts = Counter(value.verdict for value in review.judgments.values())
    complete = (
        bool(candidates)
        and counts[None] == 0
        and not any(v.get("candidate_count_unknown") for v in candidates.values())
    )
    genuine_declared = (
        submission.run.kind == "model"
        and review.observed
        and review.reviewer_kind in {"independent_user", "developer"}
    )
    measurements = {
        "basis": "Declared review observations, not independently authenticated",
        "reviewer_kind": review.reviewer_kind,
        "reviewed": len(candidates) - counts[None],
        "unreviewed": counts[None],
        "correct": counts["correct"],
        "incorrect": counts["incorrect"],
        "ambiguous": counts["ambiguous"],
        "candidate_precision": counts["correct"] / len(candidates)
        if complete and genuine_declared
        else None,
        "ambiguity_rate": counts["ambiguous"] / len(candidates)
        if complete and genuine_declared
        else None,
        "confirmation_seconds": {
            name: judgment.confirmation_seconds
            for name, judgment in review.judgments.items()
            if genuine_declared and judgment.confirmation_seconds is not None
        },
    }
    return {
        "evaluated_at": datetime.now(UTC).isoformat(),
        "suite_id": manifest["suite_id"],
        "suite_lock_sha256": lock_hash,
        "submission_sha256": digest,
        "run": submission.run.model_dump(),
        "case_count": len(cases),
        "reference_mappable_cases": sum(
            case["oracle"]["expected_decision"] == "map" for case in cases.values()
        ),
        "reference_abstention_cases": sum(
            case["oracle"]["expected_decision"] == "abstain" for case in cases.values()
        ),
        "reference_targets_matched": sum(
            any(c["result"] == "reference_contract_match" for c in outcome["candidates"])
            for outcome in outcomes.values()
        ),
        "case_states": dict(Counter(value["state"] for value in outcomes.values())),
        "candidate_records": len(candidates),
        "candidate_count_exact": not any(
            value.get("candidate_count_unknown") for value in candidates.values()
        ),
        "candidate_results": dict(Counter(value["result"] for value in candidates.values())),
        "human_measurements": measurements,
        "outcomes": outcomes,
        "scope": (
            "Synthetic numeric mappings. Reference matches are not measured model accuracy. "
            "Contract differences require adjudication; alternative valid formulations may exist. "
            "Known invalid candidates remain in the denominator; uncountable proposals disable "
            "precision. Abstentions and missing cases remain visible as coverage outcomes."
        ),
    }, template.model_dump()


def export_tasks(output, manifest, cases, lock_hash):
    output.mkdir(parents=True, exist_ok=False)
    for name, case in cases.items():
        destination = output / "cases" / name
        shutil.copytree(case["project"], destination)
        shutil.copyfile(case["request"], destination / "REQUEST.md")
    template = {
        "schema_version": 1,
        "suite_id": manifest["suite_id"],
        "suite_lock_sha256": lock_hash,
        "run": {
            "kind": "model",
            "label": "Fill with a unique run label",
            "model": "Fill with the actual model identifier",
            "context_protocol": (
                "Describe which files and tools the model saw; disclose answer access"
            ),
        },
        "answers": {},
    }
    for name, value in {
        "submission.template.json": template,
        "submission.schema.json": Submission.model_json_schema(),
        "proposal-input.schema.json": ProposalInput.model_json_schema(),
    }.items():
        (output / name).write_bytes(json_text(value).encode("utf-8"))
    (output / "INSTRUCTIONS.md").write_text(
        "# Saved mapping proposals\n\n"
        "Each cases/Cxx directory is an independent project. Read REQUEST.md and the files; "
        "you may use PaperDelta scan and proposal validation. Return one Answer object per case "
        "inside submission.answers. Use decision=propose with a proposal_input object, or "
        "decision=abstain with a reason and no proposal_input. Do not accept mappings or edit "
        "paper/config/data files. Save raw model output separately before any JSON-format repair; "
        "record repairs and failures in the run context. A missing answer counts as missing.\n\n"
        "This export excludes reference answers. Run in a separate workspace that does not "
        "contain the benchmark repository if you need answer separation. The export alone "
        "cannot prevent a host with wider filesystem access from reading the answers.\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("freeze")
    export = commands.add_parser("export")
    export.add_argument("--out", required=True)
    evaluate = commands.add_parser("score")
    evaluate.add_argument("--submission", required=True)
    evaluate.add_argument("--reviews")
    evaluate.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        manifest, cases = load_suite(verify=args.command != "freeze")
        if args.command == "freeze":
            for case in cases.values():
                expected_target(case)
                for raw in case["oracle"]["reference_inputs"]:
                    result = evaluate_answer(
                        case,
                        Answer(
                            decision="propose", reason="Reference validation", proposal_input=raw
                        ),
                    )
                    assert result["state"] == "proposed", result
                    assert len(result["candidates"]) == 1
                    candidate = result["candidates"][0]
                    assert candidate["result"] == "reference_contract_match", candidate
                    assert candidate["core_status"] == case["oracle"]["expected_reference_status"]
            with (SUITE / "protocol-lock.json").open("xb") as stream:
                stream.write(
                    json_text(
                        {"locked_at": datetime.now(UTC).isoformat(), "identities": identities()}
                    ).encode("utf-8")
                )
            print("Frozen mapping suite and scorer. No model evaluation has been run.")
            return 0
        output = Project(ROOT).path(args.out)
        lock_hash = sha256((SUITE / "protocol-lock.json").read_bytes())
        if args.command == "export":
            export_tasks(output, manifest, cases, lock_hash)
            print(f"Exported {len(cases)} tasks without reference answers.")
            return 0
        report, template = score(
            Path(args.submission).read_bytes(),
            manifest,
            cases,
            lock_hash,
            Path(args.reviews).read_bytes() if args.reviews else None,
        )
        output.mkdir(parents=True, exist_ok=False)
        (output / "report.json").write_bytes(json_text(report).encode("utf-8"))
        (output / "review.template.json").write_bytes(json_text(template).encode("utf-8"))
        print(json_text({key: value for key, value in report.items() if key != "outcomes"}))
        return 0
    except (ValueError, ValidationError, OSError, PaperDeltaError) as error:
        print(json.dumps({"error": type(error).__name__, "message": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
