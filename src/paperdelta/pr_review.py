"""Explicit finding transitions; removing coverage never resolves a failed check."""

GROUPS = {
    "occurrences": "occurrence",
    "claims": "claim",
    "figures": "figure",
    "provenance": "provenance",
    "fragments": "fragment",
}


def review_delta(report, baseline, configuration, *, same_baseline_contract=False):
    old = baseline["report"] if baseline else None
    buckets = {
        name: []
        for name in (
            "added_failures",
            "resolved_failures",
            "unverified",
            "removed_bindings",
            "unchanged_failures",
            "changed_contracts",
            "current_failures_without_baseline",
        )
    }
    modified = {
        f"{GROUPS[section['section']]}:{name}"
        for section in configuration.get("sections", [])
        if section["section"] in GROUPS
        for name in section["changed"]
    }
    dependency_changed = bool(configuration.get("settings")) or any(
        section["section"] in {"sources", "metrics"}
        and any(section[key] for key in ("added", "removed", "changed"))
        for section in configuration.get("sections", [])
    )
    for group, prefix in GROUPS.items():
        before = old.get(group, {}) if old else {}
        current = report.get(group, {})
        for name in sorted(before.keys() | current.keys()):
            left, right = before.get(name), current.get(name)
            subject = f"{prefix}:{name}"
            item = {
                "subject": subject,
                "before": left["status"] if left else None,
                "after": right["status"] if right else None,
            }
            if right is None:
                buckets["removed_bindings"].append(item)
                continue
            if right["status"] == "unknown":
                buckets["unverified"].append(item)
                continue
            changed = bool(
                left
                and (
                    not same_baseline_contract
                    or dependency_changed
                    or subject in modified
                    or configuration["status"] == "unavailable"
                )
            )
            if changed:
                buckets["changed_contracts"].append(item)
            if right["status"] == "mismatch":
                if old is None:
                    bucket = "current_failures_without_baseline"
                elif left and left["status"] == "mismatch":
                    bucket = "unchanged_failures"
                else:
                    bucket = "added_failures"
                buckets[bucket].append(item)
            elif left and left["status"] == "mismatch" and not changed:
                buckets["resolved_failures"].append(item)
    # Target configuration removals must be visible even if the selected snapshot is absent/older.
    removed = {item["subject"] for item in buckets["removed_bindings"]}
    for section in configuration.get("sections", []):
        if section["section"] not in GROUPS:
            continue
        for name in section["removed"]:
            subject = f"{GROUPS[section['section']]}:{name}"
            if subject not in removed:
                buckets["removed_bindings"].append(
                    {"subject": subject, "before": None, "after": None}
                )
                removed.add(subject)
    return {
        "comparison": "target_commit_snapshot" if old else "unavailable",
        "snapshot_name": baseline["name"] if baseline else None,
        "same_baseline_contract": same_baseline_contract,
        "counts": {key: len(value) for key, value in buckets.items()},
        **buckets,
    }
