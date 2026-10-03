"""Generate and time the declared 20-TeX / 10 MB CSV / 500-binding workload."""

from __future__ import annotations

import argparse
import cProfile
import json
import math
import platform
import pstats
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from time import perf_counter

from paperdelta.analysis import check_project
from paperdelta.storage import Project, json_text, sha256

ROOT = Path(__file__).resolve().parents[1]


def letters(index):
    return "".join(chr(65 + index // divisor % 26) for divisor in [676, 26, 1])


def generate(root):
    root.mkdir(parents=True, exist_ok=False)
    project = Project(root)
    config = {
        "schema_version": 1,
        "paper": {"entry": "paper/main.tex"},
        "sources": {
            "results": {
                "path": "results.csv",
                "format": "csv",
                "primary_key": ["dataset", "model", "split", "seed"],
                "columns": {
                    "dataset": "string",
                    "model": "string",
                    "split": "string",
                    "seed": "integer",
                    "accuracy": "decimal",
                    "loss": "decimal",
                    "run_id": "string",
                    "timestamp": "string",
                },
            }
        },
        "metrics": {},
        "occurrences": {},
    }
    header = b"dataset,model,split,seed,accuracy,loss,run_id,timestamp\n"
    rows = [header]
    tex = [[] for _ in range(20)]
    for index in range(500):
        code = letters(index)
        name = "result_" + code
        value = Decimal("0.5000") + Decimal(index) / 10000
        for seed in [1, 2, 3]:
            observation = value + Decimal(seed - 2) / 10000
            rows.append(
                f"benchmark-A,model-{code},test,{seed},{observation},0.1234,run-{code}-{seed},2026-01-01T00:00:00Z\n".encode()
            )
        config["metrics"][name] = {
            "source": "results",
            "field": "accuracy",
            "where": {"dataset": "benchmark-A", "model": f"model-{code}", "split": "test"},
            "reduce": "mean",
            "expected_seeds": [1, 2, 3],
            "unit": "fraction",
        }
        file_index = index // 25
        path = "paper/main.tex" if file_index == 0 else f"paper/part-{file_index:02}.tex"
        prefix = f"Accuracy for model {code}: "
        tex[file_index].append(f"{prefix}{value} in fraction units.\n")
        config["occurrences"][name] = {
            "file": path,
            "metric": name,
            "anchor": {"prefix": prefix, "suffix": " in fraction units."},
            "display": {"kind": "decimal", "places": 4},
        }
    byte_count = sum(map(len, rows))
    background = 0
    while byte_count < 10_000_000:
        raw = (
            f"other-dataset,model-background,train,{background},0.4321,1.2345,"
            f"background-run-{background},2026-01-01T00:00:00Z\n"
        ).encode()
        rows.append(raw)
        byte_count += len(raw)
        background += 1
    project.write("results.csv", b"".join(rows))
    project.write("paperdelta.yaml", json_text(config).encode())
    tex[0].insert(0, "\\documentclass{article}\n\\begin{document}\n")
    tex[0].extend(f"\\input{{part-{n:02}}}\n" for n in range(1, 20))
    tex[0].append("\\end{document}\n")
    for n, lines in enumerate(tex):
        project.write(
            "paper/main.tex" if n == 0 else f"paper/part-{n:02}.tex", "".join(lines).encode()
        )
    return {
        "tex_files": 20,
        "bindings": 500,
        "distinct_metrics": 500,
        "csv_bytes": byte_count,
        "csv_records": len(rows) - 1,
        "selected_records": 1500,
        "background_records": background,
    }


def check_timed(root):
    started = perf_counter()
    report = check_project(root)
    elapsed = perf_counter() - started
    if report["exit_code"] != 0 or report["coverage"]["pass"] != 500:
        raise ValueError(
            f"Benchmark must be correct before timed results count: {report['coverage']}"
        )
    return elapsed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="build/performance")
    parser.add_argument("--warm-runs", type=int, default=20)
    parser.add_argument(
        "--hardware", default="unspecified; supply --hardware for a publishable result"
    )
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--worker")
    args = parser.parse_args()
    if args.worker:
        print(check_timed(Path(args.worker)))
        return
    if not 1 <= args.warm_runs <= 100:
        raise ValueError("Choose 1–100 warm runs")
    output = Project(ROOT).path(args.out)
    output.mkdir(parents=True, exist_ok=False)
    root = output / "论文 benchmark"
    workload = generate(root)
    fresh = subprocess.run(
        [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "--worker", str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    fresh_seconds = float(fresh.stdout.strip())
    print(f"Fresh process core check: {fresh_seconds:.3f}s", flush=True)
    timings = []
    for index in range(args.warm_runs):
        elapsed = check_timed(root)
        timings.append(elapsed)
        print(f"Warm check {index + 1}: {elapsed:.3f}s", flush=True)
    if args.profile:
        profiler = cProfile.Profile()
        profiler.runcall(check_timed, root)
        with (output / "profile.txt").open("w", encoding="utf-8") as stream:
            pstats.Stats(profiler, stream=stream).sort_stats("cumulative").print_stats(40)
    p95 = sorted(timings)[math.ceil(0.95 * len(timings)) - 1]
    evidence = {
        "checked_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "hardware": args.hardware,
        "workload": workload,
        "fresh_process_core_seconds": fresh_seconds,
        "warm_core_seconds": timings,
        "warm_p95_seconds_nearest_rank": p95,
        "target_seconds": 3,
        "target_met": p95 < 3,
        "sample_sufficient_for_target": len(timings) >= 20,
        "protocol": (
            "Fresh process excludes interpreter/import startup. Warm runs create a new checker "
            "and reread/reparse all inputs; OS file cache is not flushed. No model, report "
            "rendering, or experimental training is timed. Nearest-rank empirical P95; "
            "not a statistical guarantee."
        ),
        "input_hashes": {
            p.relative_to(root).as_posix(): sha256(p.read_bytes())
            for p in root.rglob("*")
            if p.is_file()
        },
        "implementation": {
            p.relative_to(ROOT).as_posix(): sha256(p.read_bytes())
            for p in (ROOT / "src/paperdelta").rglob("*")
            if p.is_file() and p.suffix in {".py", ".json", ".css", ".js"}
        },
    }
    (output / "evidence.json").write_text(json_text(evidence), encoding="utf-8")
    print(
        json.dumps(
            {
                k: v
                for k, v in evidence.items()
                if k not in {"input_hashes", "implementation", "warm_core_seconds"}
            }
        )
    )


if __name__ == "__main__":
    main()
