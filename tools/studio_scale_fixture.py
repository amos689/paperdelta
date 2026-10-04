"""Owned, deterministic projects for Studio browser scale measurements."""

import argparse
from pathlib import Path

from benchmark import generate, letters

from paperdelta.storage import Project, json_text


def candidates(root):
    root.mkdir(parents=True, exist_ok=False)
    project = Project(root)
    lines = [
        f"Repeated result {letters(index)} equals 1.0 in scalar units.\n" for index in range(5100)
    ]
    lines.append("Finalmarker repeats the same result: 1.0 in scalar units.\n")
    project.write("paper.tex", "".join(lines).encode())
    project.write("results.csv", b"experiment,score\nrepeated,1.0\n")
    project.write(
        "paperdelta.yaml",
        json_text(
            {
                "schema_version": 4,
                "paper": {"entry": "paper.tex"},
                "sources": {
                    "experiment": {
                        "format": "csv",
                        "path": "results.csv",
                        "primary_key": ["experiment"],
                        "columns": {"experiment": "string", "score": "decimal"},
                    }
                },
                "metrics": {
                    "repeated": {
                        "source": "experiment",
                        "field": "score",
                        "where": {"experiment": "repeated"},
                        "unit": "scalar",
                        "reduce": "unique",
                        "expected_count": 1,
                    }
                },
            }
        ).encode(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("kind", choices=["candidates", "metrics"])
    args = parser.parse_args()
    (candidates if args.kind == "candidates" else generate)(args.directory)
