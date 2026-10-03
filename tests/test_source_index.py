"""Indexed selection must preserve exact typed semantics and source order."""

from decimal import Decimal
from random import Random

import pytest

from paperdelta.analysis import check_project
from paperdelta.sources import EvidenceStore


def test_indexed_selection_matches_exhaustive_predicates():
    rng = Random(70421)
    rows = [
        {
            "values": {
                "model": rng.choice(["ours", "baseline", "same-number"]),
                "split": rng.choice(["test", "train"]),
                "seed": rng.randrange(1, 6),
                "score": rng.choice(
                    [Decimal("0.0"), Decimal("-0"), Decimal("0.10"), Decimal("0.2")]
                ),
            },
            "line": n + 2,
        }
        for n in range(200)
    ]
    # The selector itself does not depend on filesystem state or configured metrics.
    store = EvidenceStore(None, None)
    predicates = [
        {},
        {"split": "test"},
        {"model": "missing"},
        {"score": Decimal("0.10000")},
        {"score": Decimal("-0")},
        {"seed": 3, "split": "train"},
        {"model": "ours", "score": Decimal("0.2"), "split": "test"},
    ]
    for where in predicates:
        expected = [
            row for row in rows if all(row["values"][key] == value for key, value in where.items())
        ]
        assert store._select_csv("sample", rows, where) == expected
    different_source = [{"values": {"split": "test"}, "line": 99}]
    assert store._select_csv("separate", different_source, {"split": "test"}) == different_source


@pytest.mark.parametrize("first,second", [("0.10", "0.100"), ("-0.0", "0")])
def test_decimal_primary_keys_reject_equivalent_values(tmp_path, first, second):
    (tmp_path / "data.csv").write_text(f"key,value\n{first},1\n{second},2\n")
    (tmp_path / "paper.tex").write_text("Value 1.")
    (tmp_path / "paperdelta.yaml").write_text(
        """schema_version: 1
paper: {entry: paper.tex}
sources:
  data: {path: data.csv, format: csv, primary_key: [key], columns: {key: decimal, value: decimal}}
metrics:
  value: {source: data, field: value, reduce: mean, unit: scalar}
occurrences:
  value: {file: paper.tex, anchor: {exact: '1'}, metric: value, display: {places: 0}}
"""
    )
    report = check_project(tmp_path)
    assert report["metrics"]["value"]["error"] == "DUPLICATE_RECORD"
    assert report["exit_code"] == 2
