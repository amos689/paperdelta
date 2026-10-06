"""Bounded, read-only source contract suggestions; never accept inferred identities."""

from __future__ import annotations

import itertools
import re

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.sources import typed_cell

MAX_ROWS = 10000
IDENTITY = {
    "id",
    "model",
    "method",
    "dataset",
    "split",
    "run",
    "checkpoint",
    "task",
    "group",
    "fold",
    "seed",
    "trial",
    "样本",
    "模型",
    "方法",
    "数据集",
    "划分",
    "种子",
}
REPEAT = {"seed", "trial", "fold", "种子"}


def _words(name):
    return set(re.split(r"[\s_\-./]+", name.casefold()))


def _type(name, values):
    present = [v for v in values if v is not None and v != ""]
    if not present:
        return "string", "empty"
    if any(re.match(r"[+\-]?0[0-9]", str(v)) for v in present):
        return "string", "leading_zero"
    if _words(name) & (IDENTITY - REPEAT):
        return "string", "identity_name"
    if len(present) != len(values):
        return "string", "missing"
    for kind in ("integer", "decimal"):
        try:
            for value in present:
                typed_cell(str(value), kind, name)
        except PaperDeltaError:
            continue
        return kind, "numeric"
    return "string", "text"


def profile_summary(summary):
    """Use complete rows for uniqueness; incomplete samples never suggest a key."""
    rows, names = summary.get("sample", []), summary.get("columns", [])
    complete = bool(rows) and len(rows) == summary.get("record_count") and len(rows) <= MAX_ROWS
    columns = {}
    declared = summary.get("column_types", {})
    for name in names:
        values = [row.get(name) for row in rows]
        kind, reason = _type(name, values)
        if summary.get("storage_kinds", {}).get(name) == ["number"]:
            kind, _ = _type("", values)
            reason = "native_numeric"
        if name in declared:
            kind, reason = declared[name], "declared"
        columns[name] = {
            "type": kind,
            "reason_code": reason,
            "reason": msg(f"advice.{reason}"),
            "examples": list(dict.fromkeys(str(v) for v in values if v is not None))[:3],
            "distinct_observed": len({str(v) for v in values if v is not None}),
            "missing_observed": sum(v is None or v == "" for v in values),
            "applicable": not (
                kind == "string" and "number" in summary.get("storage_kinds", {}).get(name, [])
            ),
        }
    candidates = [n for n in names if _words(n) & IDENTITY and not columns[n]["missing_observed"]]
    keys = []
    if complete and len(candidates) <= 12:
        groups = itertools.chain(
            [tuple(candidates)] if candidates else [],
            *(
                itertools.combinations(candidates, size)
                for size in range(1, min(3, len(candidates)) + 1)
            ),
        )
        seen = set()
        for key in itertools.islice(groups, 256):
            if key in seen:
                continue
            seen.add(key)
            try:
                identities = [
                    tuple(typed_cell(str(row[n]), columns[n]["type"], n) for n in key)
                    for row in rows
                ]
            except PaperDeltaError:
                continue
            if len(set(identities)) == len(rows):
                keys.append({"columns": list(key), "reason": msg("advice.key_unique")})
            if len(keys) == 6:
                break
    if complete and declared and summary.get("primary_key"):
        keys = [{"columns": summary["primary_key"], "reason": msg("advice.declared")}]
    conflicts = []
    if not complete:
        conflicts.append(msg("advice.incomplete"))
    elif not keys:
        conflicts.append(msg("advice.no_key"))
    if any(c["missing_observed"] for c in columns.values()):
        conflicts.append(msg("advice.missing"))
    if any(not c["applicable"] for c in columns.values()):
        conflicts.append(msg("advice.mixed_storage"))
    return {
        "columns": columns,
        "primary_keys": keys,
        "experiment": {
            "group_by": [
                n
                for n in candidates
                if not _words(n) & REPEAT and columns[n]["distinct_observed"] > 1
            ],
            "repeat_columns": [n for n in candidates if _words(n) & REPEAT],
            "constant_identity": {
                n: rows[0][n]
                for n in candidates
                if complete and columns[n]["distinct_observed"] == 1
            },
            "result_fields": [
                n
                for n in names
                if n not in candidates and columns[n]["type"] in {"integer", "decimal"}
            ],
            "unit": None,
            "reason": msg("advice.experiment"),
        },
        "rows_inspected": len(rows),
        "total_rows": summary.get("record_count", 0),
        "complete": complete,
        "can_apply": complete and all(c["applicable"] for c in columns.values()),
        "conflicts": conflicts,
        "requires_confirmation": True,
        "notice": msg("advice.notice"),
    }


def source_advice(project, path, *, sheet=None, cell_range=None):
    from paperdelta.onboarding import _source_summary

    summary, identity = _source_summary(
        project, path, sheet=sheet, cell_range=cell_range, limit=MAX_ROWS + 1
    )
    if summary.get("format") == "json" or summary.get("needs_selection"):
        return {
            "path": path,
            "input_hash": identity,
            "available": False,
            "reason": msg("advice.table_required"),
            "requires_confirmation": True,
        }
    return {"path": path, "input_hash": identity, "available": True, **profile_summary(summary)}
