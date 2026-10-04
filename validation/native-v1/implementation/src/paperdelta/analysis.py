"""A single deterministic check pipeline for humans, CI and agents."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from paperdelta import __version__
from paperdelta.config import load_config
from paperdelta.documents import LocatedText, PaperIndex
from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.metrics import Quantity, comparable
from paperdelta.models import Config, Predicate, Threshold
from paperdelta.records import FigureRecord, Snapshot, StoredReport, validate_record
from paperdelta.reviews import attach_reviews
from paperdelta.sources import EvidenceStore
from paperdelta.statistical_display import matches, render_result, validate_span
from paperdelta.storage import Project, decimal_value, fingerprint, parse_json, sha256


def predicate_refs(predicate: Predicate) -> list[str]:
    refs = [predicate.left, *predicate.candidates]
    if isinstance(predicate.right, str):
        refs.append(predicate.right)
    return refs


def evaluate_predicate(predicate: Predicate, evidence: EvidenceStore) -> bool:
    left = evidence.resolve(predicate.left).quantity
    if predicate.op == "best_in_set":
        for ref in predicate.candidates:
            a, b = comparable(left, evidence.resolve(ref).quantity)
            if a == b and not predicate.allow_ties:
                return False
            if predicate.direction == "maximize" and a < b:
                return False
            if predicate.direction == "minimize" and a > b:
                return False
        return True
    right = predicate.right
    if isinstance(right, Threshold):
        right_quantity = Quantity(decimal_value(right.value), right.unit)
    else:
        assert isinstance(right, str)
        right_quantity = evidence.resolve(right).quantity
    a, b = comparable(left, right_quantity)
    return {
        "greater_than": a > b,
        "greater_equal": a >= b,
        "less_than": a < b,
        "less_equal": a <= b,
        "equal": a == b,
    }[predicate.op]


def _diagnostic(
    rule: str, subject: str, severity: str, message: str, span: LocatedText | None = None
) -> dict:
    result = {
        "id": f"{subject}/{rule}",
        "rule": rule,
        "subject": subject,
        "severity": severity,
        "message": message,
    }
    if span is not None:
        result["location"] = span.to_dict()
    return result


def empty_report(config_path: str) -> dict:
    return {
        "report_schema_version": 2,
        "tool_version": __version__,
        "ruleset_version": "1",
        "created_at": datetime.now(UTC).isoformat(),
        "config_path": config_path,
        "input_hashes": {},
        "metrics": {},
        "occurrences": {},
        "claims": {},
        "figures": {},
        "diagnostics": [],
        "changes": [],
        "impact_groups": [],
        "baseline": None,
        "coverage": {
            "confirmed": 0,
            "pass": 0,
            "mismatch": 0,
            "unknown": 0,
            "candidate_numbers": 0,
            "unbound_numbers": [],
            "unregistered_figures": [],
            "unsupported": [],
            "review_scope": None,
            "outside_scope_numbers": [],
            "exclusions": [],
        },
        "exit_code": 2,
    }


def check_project(
    root: Path | str, config_path: str = "paperdelta.yaml", baseline: dict | None = None
) -> dict:
    project = Project(root)
    try:
        config, config_hash = load_config(project, config_path)
    except PaperDeltaError as exc:
        report = empty_report(config_path)
        report["diagnostics"].append(_diagnostic(exc.code, "project", "unknown", str(exc)))
        _finish(report)
        validate_record(StoredReport, report, "REPORT_SCHEMA")
        return report
    return check_configuration(project, config, config_path, config_hash, baseline)


def check_configuration(
    project: Project,
    config: Config,
    config_path: str,
    config_hash: str,
    baseline: dict | None = None,
) -> dict:
    """Check a validated configuration in memory, including unaccepted proposal previews."""
    report = empty_report(config_path)
    try:
        report["input_hashes"][config_path] = config_hash
        # Preserve the identity of unchanged version-1 declarations after upgrading.
        report["config_fingerprint"] = fingerprint(
            config.model_dump(exclude={"review_scope", "coverage_exclusions"})
            if config.schema_version == 1
            else config
        )
        paper = PaperIndex(project, config.paper)
        if any(getattr(doc, "format", "latex") == "pdf" for doc in paper.documents.values()):
            report["report_schema_version"] = 4
        elif any(getattr(doc, "format", "latex") == "docx" for doc in paper.documents.values()):
            report["report_schema_version"] = 3
        if any(source.format not in {"csv", "json"} for source in config.sources.values()):
            report["report_schema_version"] = 5
        if any(getattr(metric, "statistics", None) for metric in config.metrics.values()):
            report["report_schema_version"] = 6
        if config.schema_version >= 7 or any(
            getattr(doc, "uses_layout_v2", False) for doc in paper.documents.values()
        ):
            report["report_schema_version"] = 7
        evidence = EvidenceStore(project, config)
        _check(config, paper, evidence, report)
        attach_reviews(project, report)
        if baseline is not None:
            _compare_baseline(report, baseline)
        _group_impacts(report)
        # Re-read identities once to detect files changing during the check itself.
        for path, expected in report["input_hashes"].items():
            if sha256(project.read(path)) != expected:
                raise PaperDeltaError("INPUT_CHANGED", msg("error.INPUT_CHANGED", path=path))
    except PaperDeltaError as exc:
        report["diagnostics"].append(_diagnostic(exc.code, "project", "unknown", str(exc)))
    _finish(report)
    validate_record(StoredReport, report, "REPORT_SCHEMA")
    return report


def _check(config: Config, paper: PaperIndex, evidence: EvidenceStore, report: dict) -> None:
    diagnostics = report["diagnostics"]
    report["coverage"]["unsupported"] = paper.issues
    for issue in paper.issues:
        severity = "warning" if issue["code"] == "UNSUPPORTED_MACRO" else "unknown"
        diagnostics.append(_diagnostic(issue["code"], issue["file"], severity, issue["message"]))
    for file, doc in paper.documents.items():
        report["input_hashes"][file] = doc.hash
    for name, definition in config.metrics.items():
        try:
            result = evidence.resolve(name)
            report["metrics"][name] = {
                "status": "ok",
                **result.to_dict(),
                "definition": definition.model_dump(),
                "definition_fingerprint": fingerprint(definition),
            }
        except PaperDeltaError as exc:
            report["metrics"][name] = {"status": "unknown", "error": exc.code, "message": str(exc)}
            diagnostics.append(_diagnostic(exc.code, f"metric:{name}", "unknown", str(exc)))
    report["input_hashes"].update(evidence.hashes)
    covered: dict[str, list[tuple[int, int]]] = {}
    for name, occurrence in config.occurrences.items():
        subject = f"occurrence:{name}"
        state: dict = {"metric": occurrence.metric, "status": "unknown"}
        report["occurrences"][name] = state
        span = None
        try:
            doc = paper.document(occurrence.file)
            span = doc.locate(occurrence.anchor)
            validate_span(doc, span, occurrence.display)
            state["location"] = span.to_dict()
            covered.setdefault(span.file, []).append((span.start, span.end))
            result = evidence.resolve(occurrence.metric)
            expected = render_result(result, occurrence.display, config.rounding)
            actual = span.text
            if getattr(doc, "format", "latex") != "latex":
                expected = expected.replace(r"\%", "%").replace(r"\pm", "±")
                # Keep LaTeX display parsing unchanged; normalize native percentages only here.
                actual = actual.replace("%", r"\%")
                comparable_expected = expected.replace("%", r"\%")
            else:
                comparable_expected = expected
            state.update(
                {
                    "expected": expected,
                    "actual": span.text,
                    "evidence_fingerprint": result.fingerprint,
                }
            )
            state["status"] = (
                "pass" if matches(actual, comparable_expected, occurrence.display) else "mismatch"
            )
            if state["status"] == "mismatch":
                diagnostics.append(
                    _diagnostic(
                        "VALUE_MISMATCH",
                        subject,
                        "error",
                        msg(
                            "diagnostic.VALUE_MISMATCH",
                            value1=span.text,
                            expected=expected,
                            value3=occurrence.metric,
                        ),
                        span,
                    )
                )
                state["suggestion"] = {"replacement": expected, "blocked_by": []}
        except PaperDeltaError as exc:
            state["error"] = exc.code
            diagnostics.append(_diagnostic(exc.code, subject, "unknown", str(exc), span))
    for name, claim in config.claims.items():
        subject = f"claim:{name}"
        state = {"status": "unknown", "metrics": predicate_refs(claim.predicate)}
        report["claims"][name] = state
        span = None
        try:
            span = paper.document(claim.file).locate(claim.anchor)
            state["location"] = span.to_dict()
            for ref in state["metrics"]:
                evidence.resolve(ref)
                evidence.check_scope(ref, claim.scope)
            holds = evaluate_predicate(claim.predicate, evidence)
            state["status"] = "pass" if holds else "mismatch"
            state["state_fingerprint"] = fingerprint(
                {
                    "claim": claim,
                    "text": " ".join(span.text.split()),
                    "evidence": {
                        ref: evidence.resolve(ref).fingerprint for ref in state["metrics"]
                    },
                    "ruleset": report["ruleset_version"],
                }
            )
            state["review"] = "unreviewed"
            if not holds:
                diagnostics.append(
                    _diagnostic(
                        "CLAIM_FALSE",
                        subject,
                        "error",
                        msg("diagnostic.CLAIM_FALSE"),
                        span,
                    )
                )
        except PaperDeltaError as exc:
            state["error"] = exc.code
            diagnostics.append(_diagnostic(exc.code, subject, "unknown", str(exc), span))
    _block_related_fixes(report)
    _check_exports(config, paper, report)
    _check_figures(config, evidence.project, report)
    registered = {paper.project.path(figure.path) for figure in config.figures.values()}
    for file, doc in paper.documents.items():
        for target in doc.graphics:
            bases = {Path(paper.origins[file]).parent / target, Path(file).parent / target}
            candidates = set()
            for base in bases:
                suffixes = (
                    [""] if base.suffix else [".pdf", ".png", ".jpg", ".jpeg", ".svg", ".eps"]
                )
                for suffix in suffixes:
                    path = paper.project.path(base.as_posix() + suffix)
                    if path.is_file():
                        candidates.add(path)
            if len(candidates) != 1 or not candidates.issubset(registered):
                report["coverage"]["unregistered_figures"].append(
                    {
                        "file": file,
                        "reference": target,
                        "resolved": [paper.project.relative(path) for path in sorted(candidates)],
                        "reason": "not registered"
                        if len(candidates) == 1
                        else "missing or ambiguous",
                    }
                )
    from paperdelta.coverage import apply_coverage

    apply_coverage(config, paper, report, covered)
    if config.require_complete_coverage and (
        report["coverage"]["unbound_numbers"]
        or paper.issues
        or report["coverage"]["unregistered_figures"]
    ):
        diagnostics.append(
            _diagnostic(
                "INCOMPLETE_COVERAGE",
                "project",
                "unknown",
                msg("diagnostic.INCOMPLETE_COVERAGE"),
            )
        )


def _check_exports(config, paper, report):
    """Compare only explicitly bound metrics across an explicitly declared export."""
    if not paper.exports:
        return
    states = report["occurrences"]
    report["exports"] = []
    for file, source in paper.exports.items():
        source_files = paper.members[source]
        source_items = {
            name: item
            for name, item in config.occurrences.items()
            if paper.project.relative(paper.project.path(item.file)) in source_files
        }
        export_items = {
            name: item
            for name, item in config.occurrences.items()
            if paper.project.relative(paper.project.path(item.file)) == file
        }
        metrics = sorted({item.metric for item in [*source_items.values(), *export_items.values()]})
        for metric in metrics or [None]:
            left = [name for name, item in source_items.items() if item.metric == metric]
            right = [name for name, item in export_items.items() if item.metric == metric]
            status = "unknown"
            if left and right and all(states[name]["status"] != "unknown" for name in left + right):
                source_current = all(states[name]["status"] == "pass" for name in left)
                export_current = all(states[name]["status"] == "pass" for name in right)
                status = (
                    "aligned"
                    if source_current and export_current
                    else "stale"
                    if source_current
                    else "source_outdated"
                )
            report["exports"].append(
                {
                    "file": file,
                    "source": source,
                    "metric": metric,
                    "status": status,
                    "source_bindings": left,
                    "export_bindings": right,
                }
            )
            if status == "stale":
                for name in right:
                    if states[name]["status"] != "mismatch":
                        continue
                    finding = _diagnostic(
                        "EXPORT_STALE",
                        f"occurrence:{name}",
                        "error",
                        msg("pdf.export_stale_finding", file=file, source=source, metric=metric),
                    )
                    finding["location"] = states[name]["location"]
                    report["diagnostics"].append(finding)
            elif status == "unknown":
                report["diagnostics"].append(
                    _diagnostic(
                        "EXPORT_UNCHECKED",
                        f"export:{file}:{metric or '-'}",
                        "unknown",
                        msg("pdf.export_unchecked", file=file, source=source, metric=metric or "—"),
                    )
                )


def _block_related_fixes(report: dict) -> None:
    def leaves(name: str) -> set[str]:
        dependencies = report["metrics"].get(name, {}).get("dependencies", [])
        if not dependencies:
            return {name}
        return set().union(*(leaves(ref) for ref in dependencies))

    for state in report["occurrences"].values():
        if "suggestion" not in state:
            continue
        for name, claim in report["claims"].items():
            if claim["status"] != "pass" and leaves(state["metric"]) & set().union(
                *(leaves(ref) for ref in claim["metrics"])
            ):
                state["suggestion"]["blocked_by"].append(f"claim:{name}")


def _check_figures(config: Config, project: Project, report: dict) -> None:
    for name, figure in config.figures.items():
        state = {"path": figure.path, "status": "unknown", "provenance": "unknown"}
        report["figures"][name] = state
        try:
            actual = sha256(project.read(figure.path))
            report["input_hashes"][figure.path] = actual
            if figure.record is None:
                raise PaperDeltaError("PROVENANCE_UNKNOWN", msg("error.PROVENANCE_UNKNOWN"))
            text, raw = project.text(figure.record, 1024 * 1024)
            report["input_hashes"][figure.record] = sha256(raw)
            record = validate_record(FigureRecord, parse_json(text), "FIGURE_RECORD").model_dump()
            if record["path"] != figure.path:
                raise PaperDeltaError("FIGURE_RECORD", msg("error.FIGURE_RECORD"))
            inputs, script = record["inputs"], record["script"]
            changed = []
            for path, expected in {**inputs, script["path"]: script["hash"]}.items():
                current = sha256(project.read(path))
                report["input_hashes"][path] = current
                if current != expected:
                    changed.append(path)
            if actual != record["output_hash"]:
                changed.append(figure.path)
            state.update(
                {
                    "status": "mismatch" if changed else "pass",
                    "changed_paths": changed,
                    "provenance": "dependency_changed" if changed else "unchanged_since_record",
                    "record_method": record["method"],
                    "dependencies": sorted({*inputs, script["path"]}),
                }
            )
            if changed:
                report["diagnostics"].append(
                    _diagnostic(
                        "FIGURE_CHANGED",
                        f"figure:{name}",
                        "error",
                        msg("diagnostic.FIGURE_CHANGED", changed=changed),
                    )
                )
        except PaperDeltaError as exc:
            state["error"] = exc.code
            report["diagnostics"].append(
                _diagnostic(exc.code, f"figure:{name}", "unknown", str(exc))
            )


def _compare_baseline(report: dict, baseline: dict) -> None:
    validate_record(Snapshot, baseline, "BASELINE_SCHEMA")
    previous = baseline["report"]
    report["baseline"] = {"name": baseline.get("name"), "created_at": baseline.get("created_at")}
    for name, state in report["metrics"].items():
        old = previous.get("metrics", {}).get(name)
        if old is None:
            kind = "added"
        elif state.get("status") != "ok" or old.get("status") != "ok":
            kind = "unavailable"
        elif state.get("definition_fingerprint") != old.get("definition_fingerprint"):
            kind = "definition_changed"
        elif state["fingerprint"] != old.get("fingerprint"):
            kind = "changed"
        else:
            kind = "unchanged"
        state["change"] = kind
        if kind != "unchanged":
            report["changes"].append(
                {
                    "metric": name,
                    "kind": kind,
                    "before": old.get("value") if old else None,
                    "after": state.get("value"),
                    "unit": state.get("unit"),
                    "occurrences": [
                        key for key, item in report["occurrences"].items() if item["metric"] == name
                    ],
                    "claims": [
                        key for key, item in report["claims"].items() if name in item["metrics"]
                    ],
                }
            )
    report["configuration_changed"] = report.get("config_fingerprint") != previous.get(
        "config_fingerprint"
    )
    report["removed_bindings"] = {
        group: sorted(set(previous.get(group, {})) - set(report[group]))
        for group in ("metrics", "occurrences", "claims", "figures")
    }


def _finish(report: dict) -> None:
    from paperdelta.actions import review_actions

    coverage = report["coverage"]
    for group in ("occurrences", "claims", "figures"):
        for state in report[group].values():
            coverage["confirmed"] += 1
            coverage[state["status"]] += 1
    if coverage["confirmed"] == 0:
        report["diagnostics"].append(
            _diagnostic(
                "NO_BINDINGS",
                "project",
                "unknown",
                msg("diagnostic.NO_BINDINGS"),
            )
        )
    severities = {finding["severity"] for finding in report["diagnostics"]}
    report["exit_code"] = 2 if "unknown" in severities else 1 if "error" in severities else 0
    report["actions"] = review_actions(report)


def _group_impacts(report: dict) -> None:
    def depends_on(metric: str, root: str) -> bool:
        return metric == root or any(
            depends_on(parent, root)
            for parent in report["metrics"].get(metric, {}).get("dependencies", [])
        )

    for root, metric in report["metrics"].items():
        if metric.get("dependencies"):
            continue
        metrics = [name for name in report["metrics"] if depends_on(name, root)]
        occurrences = [
            name for name, state in report["occurrences"].items() if state["metric"] in metrics
        ]
        claims = [
            name for name, state in report["claims"].items() if set(state["metrics"]) & set(metrics)
        ]
        paths = sorted({item["path"] for item in metric.get("evidence", [])})
        figures = [
            name
            for name, state in report["figures"].items()
            if set(state.get("dependencies", [])) & set(paths)
        ]
        if not any((occurrences, claims, figures)):
            continue
        report["impact_groups"].append(
            {
                "metric": root,
                "sources": paths,
                "metrics": metrics,
                "occurrences": occurrences,
                "claims": claims,
                "figures": figures,
                "change": metric.get("change", "unavailable"),
            }
        )
