"""Advance an edited declaration only when it uses newer layout identities."""


def upgrade_layout_schema(value):
    if any(
        (item.get("anchor", {}).get("table") or {}).get("header_rows") is not None
        or (item.get("anchor", {}).get("table") or {}).get("caption") is not None
        for group in ("occurrences", "claims", "coverage_exclusions")
        for item in value.get(group, {}).values()
    ):
        value["schema_version"] = max(7, value["schema_version"])
