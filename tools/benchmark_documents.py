"""Measure fresh-process checks, repeated in-process checks, and HTML rendering separately."""

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

from paperdelta import __version__
from paperdelta.analysis import check_project
from paperdelta.reports import html_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=5)
    args = parser.parse_args()
    if not 1 <= args.runs <= 30:
        parser.error("--runs must be between 1 and 30")
    project = args.project.resolve()
    root = Path(__file__).resolve().parents[1]
    target = args.out.resolve()
    if not target.is_relative_to(root / "build") or target.exists():
        parser.error("--out must be a new file under build/")
    timings = {"cold_process_check_ms": [], "warm_process_check_ms": [], "html_only_ms": []}
    code = "from paperdelta.analysis import check_project; import sys; check_project(sys.argv[1])"
    for _ in range(args.runs):
        started = time.perf_counter()
        subprocess.run(
            [sys.executable, "-I", "-c", code, str(project)], check=True, capture_output=True
        )
        timings["cold_process_check_ms"].append(1000 * (time.perf_counter() - started))
    report = check_project(project)
    for _ in range(args.runs):
        started = time.perf_counter()
        report = check_project(project)
        timings["warm_process_check_ms"].append(1000 * (time.perf_counter() - started))
    for _ in range(args.runs):
        started = time.perf_counter()
        html = html_report(report)
        timings["html_only_ms"].append(1000 * (time.perf_counter() - started))
    evidence = {
        "tool_version": __version__,
        "python": platform.python_version(),
        "system": platform.system(),
        "project": project.relative_to(root).as_posix()
        if project.is_relative_to(root)
        else "external",
        "input_hashes": report["input_hashes"],
        "check_exit_code": report["exit_code"],
        "candidate_numbers": report["coverage"]["candidate_numbers"],
        "html_bytes": len(html.encode()),
        "runs": args.runs,
        "timings": {
            name: {
                "samples": [round(v, 3) for v in values],
                "median": round(statistics.median(values), 3),
            }
            for name, values in timings.items()
        },
        "scope": (
            "Local wall time, no fixed cross-machine threshold. Warm checks still reread "
            "and reparse input; only process imports and OS caches are warm."
        ),
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: data["median"] for name, data in evidence["timings"].items()}))


if __name__ == "__main__":
    main()
