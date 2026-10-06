"""A read-only revision list joining declared dependencies to manuscript locations."""

from paperdelta.i18n import msg
from paperdelta.locations import location_label


def revision_list(report):
    changed_metrics = {item["metric"] for item in report["changes"] if item["kind"] != "unchanged"}
    items = []

    def add(subject, kind, state, metrics=(), files=(), action=None):
        status = state["status"]
        if status == "pass" and not changed_metrics.intersection(metrics):
            return
        action = (
            "verify_unknown"
            if status == "unknown"
            else "review_refreshed"
            if status == "pass"
            else action or "update_" + kind
        )
        location = state.get("location")
        items.append(
            {
                "subject": subject,
                "kind": kind,
                "status": status,
                "action": action,
                "instruction": msg("revisions." + action),
                "metrics": sorted(metrics),
                "files": sorted(set(files)),
                "position": location_label(location) if location else None,
                "actual": state.get("actual"),
                "expected": state.get("expected"),
                "changed_paths": state.get("changed_paths", []),
            }
        )

    for name, state in report["occurrences"].items():
        location = state.get("location", {})
        kind = state.get("usage") or (
            "table" if location.get("locator", {}).get("table") else "prose"
        )
        add(
            "occurrence:" + name,
            kind,
            state,
            [state["metric"]],
            [location["file"]] if location else [],
            "review_claims" if state.get("suggestion", {}).get("blocked_by") else None,
        )
    for name, state in report["claims"].items():
        add(
            "claim:" + name,
            "claim",
            state,
            state.get("metrics", []),
            [state["location"]["file"]] if state.get("location") else [],
            "review_claims",
        )
    for name, state in report["figures"].items():
        metrics = {group["metric"] for group in report["impact_groups"] if name in group["figures"]}
        add("figure:" + name, "figure", state, metrics, [state["path"]])
    for name, state in report.get("provenance", {}).items():
        outputs = set(state.get("outputs", []))
        metrics = {
            name
            for name, metric in report["metrics"].items()
            if any(item["path"] in outputs for item in metric.get("evidence", []))
        }
        add(
            "provenance:" + name,
            "notebook" if state.get("kind") == "notebook" else "export",
            state,
            metrics,
            state.get("outputs", []),
        )
    for name, state in report.get("fragments", {}).items():
        add(
            "fragment:" + name,
            "fragment",
            state,
            state.get("metrics", []),
            [state["path"]] if state.get("path") else [],
        )
    for index, state in enumerate(report.get("exports", [])):
        if state["status"] == "aligned":
            continue
        add(
            "export:" + str(index),
            "export",
            {**state, "status": "unknown" if state["status"] == "unknown" else "mismatch"},
            [state["metric"]] if state["metric"] else [],
            [state["file"]],
        )
    return sorted(
        items,
        key=lambda item: (
            item["status"] != "unknown",
            item["status"] == "pass",
            item["kind"],
            item["subject"],
        ),
    )
