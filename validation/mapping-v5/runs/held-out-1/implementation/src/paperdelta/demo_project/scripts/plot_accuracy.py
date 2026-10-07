"""Original example plotting script. Run explicitly; PaperDelta never invokes it."""

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, required=True)
    arguments = parser.parse_args()
    root = arguments.project.resolve()
    data = root / "results/metrics.csv"
    script = root / "scripts/plot_accuracy.py"
    output = root / "paper/figures/accuracy.pdf"
    with data.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    names, means = ["Baseline", "Ours"], []
    for name in names:
        selected = [
            row
            for row in rows
            if row["dataset"] == "Data-A" and row["split"] == "test" and row["model"] == name
        ]
        assert sorted(row["seed"] for row in selected) == ["1", "2", "3"]
        mean = sum((Decimal(row["accuracy"]) for row in selected), Decimal(0)) / len(selected)
        means.append(mean * 100)
    fig, axis = plt.subplots(figsize=(5.8, 3.8), layout="constrained")
    bars = axis.bar(
        names, [float(value) for value in means], color=["#748796", "#238a81"], width=0.55
    )
    axis.set_ylim(0, 100)
    axis.set_ylabel("Data-A test accuracy (%)")
    axis.set_title("Mean of three declared seeds", loc="left", pad=18)
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", alpha=0.16)
    axis.set_axisbelow(True)
    axis.bar_label(bars, labels=[f"{value:.1f}%" for value in means], padding=6)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output,
        metadata={
            "CreationDate": None,
            "ModDate": None,
            "Title": "PaperDelta original synthetic accuracy example",
        },
    )
    fig.savefig(output.with_suffix(".png"), dpi=160)
    plt.close(fig)

    def identity(path):
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    record = {
        "schema_version": 1,
        "path": "paper/figures/accuracy.pdf",
        "output_hash": identity(output),
        "inputs": {"results/metrics.csv": identity(data)},
        "script": {"path": "scripts/plot_accuracy.py", "hash": identity(script)},
        "recorded_at": datetime.now(UTC).isoformat(),
        "method": "imported",
    }
    output.with_suffix(".record.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
