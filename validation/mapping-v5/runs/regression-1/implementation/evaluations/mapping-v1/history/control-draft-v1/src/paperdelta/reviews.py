"""Explicit author attestations kept separate from checks and snapshots."""

from __future__ import annotations

from datetime import UTC, datetime

from paperdelta.errors import PaperDeltaError
from paperdelta.records import ReviewRecord, validate_record
from paperdelta.storage import Project, fingerprint, json_text, parse_json, sha256


def attach_reviews(project: Project, report: dict) -> None:
    records = []
    for index, path in enumerate(sorted(project.path(".paperdelta/reviews").glob("*.json"))):
        if index >= 1000:
            raise PaperDeltaError("REVIEW_LIMIT", "More than 1000 local review records")
        relative = project.relative(path)
        text, raw = project.text(relative, 64 * 1024)
        report["input_hashes"][relative] = sha256(raw)
        value = parse_json(text)
        record = validate_record(ReviewRecord, value, "REVIEW_SCHEMA")
        body = record.model_dump(exclude={"record_id"})
        if record.record_id != fingerprint(body):
            raise PaperDeltaError("REVIEW_IDENTITY", f"Damaged review record: {relative}")
        records.append(record.model_dump())
    for name, state in report["claims"].items():
        history = [record for record in records if record["claim"] == name]
        matches = [
            record
            for record in history
            if record["state_fingerprint"] == state.get("state_fingerprint")
        ]
        state["review"] = "reviewed" if matches else "superseded" if history else "unreviewed"
        state["review_records"] = sorted(history, key=lambda item: item["created_at"])
        state["matching_reviews"] = [record["record_id"] for record in matches]


def record_review(
    project: Project,
    claim: str,
    state: str,
    reviewer: str,
    note: str,
    *,
    config_path: str = "paperdelta.yaml",
    attest_reviewed: bool = False,
) -> str:
    if not attest_reviewed:
        raise PaperDeltaError("REVIEW_ATTESTATION", "Explicit author attestation is required")
    # Imported here so the check pipeline can also read records without a cycle.
    from paperdelta.analysis import check_project

    report = check_project(project.root, config_path)
    current = report["claims"].get(claim)
    if current is None or current.get("state_fingerprint") is None:
        raise PaperDeltaError("CLAIM_UNAVAILABLE", "Claim or its evidence cannot be resolved")
    if current["state_fingerprint"] != state:
        raise PaperDeltaError("STALE_REVIEW", "Claim or selected evidence changed; review again")
    body = {
        "review_schema_version": 1,
        "claim": claim,
        "state_fingerprint": state,
        "reviewer": reviewer,
        "note": note,
        "created_at": datetime.now(UTC).isoformat(),
        "assertion": "I reviewed this claim and its selected evidence",
    }
    record = validate_record(
        ReviewRecord, {**body, "record_id": fingerprint(body)}, "REVIEW_SCHEMA"
    )
    path = f".paperdelta/reviews/{record.record_id.removeprefix('sha256:')}.json"
    project.write(path, json_text(record.model_dump()).encode("utf-8"), exclusive=True)
    return path
