"""Fresh, shared proposal evidence for agents, the CLI and Studio.

Resolving a declared selector is a structural fact. The declaration's scientific
meaning and its rationale remain assertions for the author to review.
"""

from __future__ import annotations

from copy import deepcopy

from paperdelta import builder
from paperdelta.batch import _location_context
from paperdelta.documents import PaperIndex
from paperdelta.i18n import msg
from paperdelta.locations import location_label
from paperdelta.models import DerivedMetric, SourceMetric
from paperdelta.onboarding import inspect_proposal
from paperdelta.sources import EvidenceStore


def _metric_names(config, names):
    result = []

    def visit(name):
        if name in result:
            return
        result.append(name)
        definition = config.metrics[name]
        if isinstance(definition, DerivedMetric):
            for dependency in definition.args:
                visit(dependency)

    for name in names:
        visit(name)
    return result


def _metrics(config, results, hashes, names, row_limit):
    cards = {}
    for name in _metric_names(config, names):
        definition = config.metrics[name]
        result = deepcopy(results[name])
        evidence = result.pop("evidence", [])
        for item in evidence:
            source = config.sources[item["source"]]
            item["source_contract"] = source.model_dump()
            item["sha256"] = hashes.get(item["path"])
            for key in ("records", "locations"):
                values = item.get(key, [])
                item[key + "_total"] = len(values)
                item[key] = values[:row_limit]
            item["truncated"] = any(
                item[key + "_total"] > len(item[key]) for key in ("records", "locations")
            )
            item["inspect"] = {
                "path": item["path"],
                "source": item["source"],
                "field": item["field"],
                "selectors": deepcopy(item.get("where", {})),
                "sheet": source.sheet,
                "cell_range": source.cell_range,
                "full_report_pointer": f"/preview/metrics/{name}/evidence",
            }
        card = {
            "name": name,
            "declared_contract": definition.model_dump(),
            "computed": {
                key: result[key]
                for key in (
                    "status",
                    "value",
                    "unit",
                    "statistics",
                    "fingerprint",
                    "error",
                    "message",
                )
                if key in result
            },
            "evidence": evidence,
            "verification": "evaluated_under_declared_contract",
        }
        if isinstance(definition, SourceMetric):
            source = config.sources[definition.source]
            card["declared_identity"] = {
                "source": definition.source,
                "path": source.path,
                "sha256": hashes.get(source.path),
                "format": source.format,
                "columns": deepcopy(source.columns),
                "primary_key": list(source.primary_key),
                "selectors": deepcopy(definition.where),
                "expected_count": definition.expected_count,
                "seed_column": definition.seed_column,
                "expected_seeds": deepcopy(definition.expected_seeds),
                "field": definition.field,
                "unit": definition.unit,
                "reduce": definition.reduce,
                "sheet": source.sheet,
                "cell_range": source.cell_range,
            }
            card["notices"] = (
                [msg("proposal_review.count_unknown")] if definition.expected_count is None else []
            )
        else:
            card["derivation"] = {"operation": definition.op, "arguments": list(definition.args)}
        cards[name] = card
    return cards


def _base(hashes, row_limit):
    if type(row_limit) is not int or not 1 <= row_limit <= 100:
        raise ValueError("row_limit must be an integer from 1 to 100")
    return {
        "review_schema_version": 1,
        "input_hashes": dict(hashes),
        "evidence_row_limit": row_limit,
        "verification_scope": msg("proposal_review.scope"),
        "identity_status": "requires_author_review",
        "rationale_status": "unverified_assertion",
        "requires_confirmation": True,
        "full_evidence": {
            "proposal_json_required": True,
            "cli_arguments": [
                "paperdelta",
                "bind",
                "--proposal",
                "<saved-proposal.json>",
                "--format",
                "json",
            ],
            "notice": msg("proposal_review.full_evidence"),
        },
    }


def from_checked(project, proposal, config, report, *, row_limit=10):
    """Build a view from a freshly inspected proposal, then recheck input bytes."""
    review = _base(report["input_hashes"], row_limit)
    paper = PaperIndex(project, config.paper)
    bindings = []
    for binding, rationale in proposal.rationale.items():
        group, name = binding.split(":", 1)
        entry = report[group][name]
        definition = getattr(proposal.additions, group)[name].model_dump()
        location = entry.get("location")
        references = entry.get("metrics", [entry["metric"]] if "metric" in entry else [])
        names = _metric_names(config, references)
        subjects = {f"{group[:-1]}:{name}", *(f"metric:{metric}" for metric in names)}
        context = {}
        if location:
            document = paper.document(location["file"])
            context = {
                "before": document.text[max(0, location["start"] - 160) : location["start"]],
                "text": location["text"],
                "after": document.text[location["end"] : location["end"] + 160],
                **_location_context(document, location),
            }
        bindings.append(
            {
                "binding": binding,
                "group": group,
                "location": deepcopy(location),
                "label": location_label(location) if location else definition.get("path", name),
                "manuscript_sha256": report["input_hashes"].get(
                    location["file"] if location else definition.get("path")
                ),
                "context": context,
                "declared_binding": definition,
                "asserted_rationale": rationale,
                "rationale_status": "unverified_assertion",
                "identity_status": "requires_author_review",
                "deterministic_result": deepcopy(entry),
                "metrics": _metrics(
                    config, report["metrics"], report["input_hashes"], names, row_limit
                ),
                "conflicts": [
                    deepcopy(item) for item in report["diagnostics"] if item["subject"] in subjects
                ],
                "notices": [msg("proposal_review.identity")]
                + ([msg("proposal_review.mismatch")] if entry["status"] == "mismatch" else []),
            }
        )
    review.update(
        proposal_id=proposal.proposal_id,
        bindings=bindings,
        coverage=deepcopy(report["coverage"]),
        diagnostics=deepcopy(report["diagnostics"]),
        exit_code=report["exit_code"],
    )
    builder._unchanged(project, report["input_hashes"])
    return review


def inspect_review(project, value, *, row_limit=10):
    parsed, config, report = inspect_proposal(project, value)
    return from_checked(project, parsed, config, report, row_limit=row_limit)


def draft_review(project, value, *, row_limit=5):
    draft, config = builder.resume_draft(project, value)
    if draft.additions.occurrences or draft.additions.claims or draft.additions.figures:
        return inspect_review(project, builder.finalize_draft(project, value), row_limit=row_limit)
    review = _base(draft.input_hashes, row_limit)
    store = EvidenceStore(project, config)
    names = _metric_names(config, draft.additions.metrics)
    results = {name: store.resolve(name).to_dict() for name in names}
    hashes = {**draft.input_hashes, **store.hashes}
    review.update(
        draft_id=draft.draft_id,
        bindings=[],
        metrics=_metrics(config, results, hashes, names, row_limit),
    )
    builder._unchanged(project, hashes)
    return review
