"""Owned fixture exporter for the comparison, not a PaperDelta runtime adapter.

Both reference workflows start from the same CSV used by PaperDelta. Calkit
receives JSON evidence; scitexlintr receives a manifest and generated macros.
The experiment's selection and conditional wording are explicitly authored here.
"""

import argparse
import csv
import json
from decimal import Decimal
from hashlib import sha256
from pathlib import Path


def read_values():
    path = Path("results/metrics.csv")
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    identities = [(r["dataset"], r["model"], r["split"], int(r["seed"])) for r in rows]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate experiment identity")
    values = {}
    for model in ("Ours", "Baseline"):
        selected = [
            r for r in rows if (r["dataset"], r["model"], r["split"]) == ("Data-A", model, "test")
        ]
        if sorted(int(r["seed"]) for r in selected) != [1, 2, 3]:
            raise ValueError("Expected exactly seeds 1, 2, 3")
        numbers = [Decimal(r["accuracy"]) for r in selected]
        if not all(n.is_finite() for n in numbers):
            raise ValueError("Nonfinite value")
        values[model.lower()] = sum(numbers) / 3
    values["gain"] = (values["ours"] - values["baseline"]) * 100
    values["ours_percent"] = values["ours"] * 100
    values["baseline_percent"] = values["baseline"] * 100
    return values, sha256(path.read_bytes()).hexdigest()


def export(kind):
    values, digest = read_values()
    output = Path("generated")
    output.mkdir(exist_ok=True)
    if kind == "calkit":
        # Exact decimal numeric JSON tokens; the receiving tool chooses its types.
        pairs = [f'"{key}": {value}' for key, value in values.items()]
        (output / "results.json").write_text("{" + ", ".join(pairs) + "}\n", encoding="utf-8")
        return
    relation = "outperforms" if values["ours"] > values["baseline"] else "does not outperform"
    gain = (
        f"Our method improves by {values['gain']:.1f} percentage points over Baseline."
        if values["gain"] > 0
        else f"Our method changes by {values['gain']:.1f} percentage points relative to Baseline."
    )
    entries = [
        {
            "id": "ours_percent",
            "value": float(values["ours"]),
            "unit": "percent",
            "precision": 1,
        },
        {"id": "ours_bare", "value": f"{values['ours'] * 100:.1f}"},
        {"id": "baseline_bare", "value": f"{values['baseline'] * 100:.1f}"},
        {"id": "gain_sentence", "value": gain},
        {"id": "comparison", "value": f"Our method {relation} Baseline on Data-A."},
    ]
    manifest = {
        "numbers": entries,
        "provenance": {
            "path": "results/metrics.csv",
            "sha256": digest,
            "selection": "Data-A, test, seeds 1/2/3, arithmetic means",
            "note": "Owned exporter; the linter does not execute or verify this calculation.",
        },
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    macros = {
        "OursPercent": f"{values['ours'] * 100:.1f}" + r"\%",
        "OursBare": entries[1]["value"],
        "BaselineBare": entries[2]["value"],
        "GainSentence": gain,
        "Comparison": entries[4]["value"],
    }
    lines = [
        r"\newcommand{\SciVal}[2]{#1}",
        r"\newcommand{\SciText}[2]{#1}",
        *(r"\newcommand{" + "\\" + key + "}{" + value + "}" for key, value in macros.items()),
    ]
    (output / "values.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["calkit", "scitexlintr"], required=True)
    export(parser.parse_args().format)
