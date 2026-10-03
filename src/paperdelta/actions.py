"""A deterministic review queue; actions describe work without performing it."""


def review_actions(report):
    groups = {}

    def add(kind, subject, finding=None):
        item = groups.setdefault(kind, {"kind": kind, "subjects": [], "findings": []})
        if subject not in item["subjects"]:
            item["subjects"].append(subject)
        if finding and finding not in item["findings"]:
            item["findings"].append(finding)

    for finding in report["diagnostics"]:
        rule, subject = finding["rule"], finding["subject"]
        group, _, name = subject.partition(":")
        if rule == "WATCH_PENDING":
            kind = "wait_for_check"
        elif rule == "VALUE_MISMATCH":
            state = report["occurrences"][name]
            kind = (
                "review_claims"
                if state.get("suggestion", {}).get("blocked_by")
                else "update_numbers"
            )
        elif group == "claim" and rule == "CLAIM_FALSE":
            kind = "review_claims"
        elif group == "figure":
            kind = "update_figures"
        elif rule.startswith("ANCHOR_") or rule in {
            "UNREACHABLE_TEX",
            "NUMERIC_ANCHOR",
            "UNSUPPORTED_SPAN",
        }:
            kind = "repair_bindings"
        elif rule.startswith("EXCLUSION_"):
            kind = "review_exclusions"
        elif rule in {"NO_BINDINGS", "INCOMPLETE_COVERAGE"}:
            kind = "complete_coverage"
        else:
            kind = "resolve_evidence"
        add(kind, subject, finding["id"])
    coverage = report["coverage"]
    if coverage["unbound_numbers"] or coverage["unregistered_figures"]:
        add("complete_coverage", "project")
    order = (
        "wait_for_check",
        "resolve_evidence",
        "repair_bindings",
        "review_exclusions",
        "review_claims",
        "update_numbers",
        "update_figures",
        "complete_coverage",
    )
    return [groups[kind] for kind in order if kind in groups]
