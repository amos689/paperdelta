"""Measure identical full/incremental reports, including cold costs and invalidation."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import io
import json
import math
import platform
import statistics
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from benchmark import generate, letters

from paperdelta import __version__, builder
from paperdelta.analysis import check_project
from paperdelta.config import config_text, load_config
from paperdelta.pdf_document import PdfDocument
from paperdelta.storage import Project, json_text


def comparable(report, *, previous_version=False):
    value = deepcopy(report)
    value.pop("created_at", None)
    if previous_version:
        value.pop("tool_version", None)
    return json_text(value)


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def memory():
    if sys.platform == "win32":
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (name, ctypes.c_size_t)
                for name in (
                    "PeakWorkingSetSize",
                    "WorkingSetSize",
                    "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage",
                    "PagefileUsage",
                    "PeakPagefileUsage",
                )
            ]

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        api = ctypes.WinDLL("psapi", use_last_error=True).GetProcessMemoryInfo
        api.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        result = Counters()
        result.cb = ctypes.sizeof(result)
        if not api(kernel.GetCurrentProcess(), ctypes.byref(result), result.cb):
            raise ctypes.WinError(ctypes.get_last_error())
        return {"rss_bytes": result.WorkingSetSize, "peak_rss_bytes": result.PeakWorkingSetSize}
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {"rss_bytes": None, "peak_rss_bytes": peak if sys.platform == "darwin" else peak * 1024}


def summary(values):
    return {
        "samples_seconds": values,
        "median_seconds": statistics.median(values),
        "p95_seconds": sorted(values)[math.ceil(len(values) * 0.95) - 1],
    }


def pdf_fixture(root):
    from reportlab.pdfgen.canvas import Canvas

    root.mkdir(parents=True)
    output = io.BytesIO()
    canvas = Canvas(output, invariant=True)
    for page in range(8):
        for row in range(40):
            label = letters(page * 40 + row)
            canvas.drawString(60, 760 - row * 17, f"Result {label}: 0.5000 in fraction units.")
        canvas.showPage()
    canvas.save()
    store = Project(root)
    store.write("paper.pdf", output.getvalue())
    store.write("data.json", b'{"score":0.5000}')
    document = PdfDocument("paper.pdf", output.getvalue())
    numbers = document.numbers()
    assert len(numbers) == 320
    config = {
        "schema_version": 4,
        "paper": {"entry": "paper.pdf"},
        "sources": {"data": {"format": "json", "path": "data.json"}},
        "metrics": {"score": {"source": "data", "field": "/score", "unit": "fraction"}},
        "occurrences": {
            "result_" + letters(index): {
                "file": "paper.pdf",
                "metric": "score",
                "anchor": builder.anchor_for_span(document, span).model_dump(),
                "display": {"kind": "decimal", "places": 4},
            }
            for index, span in enumerate(numbers)
        },
    }
    store.write("paperdelta.yaml", json_text(config).encode())
    return {"pages": 8, "bindings": 320, "pdf_bytes": len(output.getvalue())}


def timed(root, cache=None):
    started = perf_counter()
    report = check_project(root) if cache is None else check_project(root, cache=cache)
    return report, perf_counter() - started


def worker(root, runs):
    timings, reports = [], []
    for _ in range(runs):
        report, elapsed = timed(root)
        timings.append(elapsed)
        reports.append(digest(comparable(report, previous_version=True)))
    import paperdelta

    source = Path(paperdelta.__file__).parent
    return {
        "version": __version__,
        "python": platform.python_version(),
        "full_checks": summary(timings),
        "report_hashes_without_version_or_clock": reports,
        "loaded_source_files_sha256": {
            p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source.glob("*.py")
        },
    }


def measure(root, workload, runs, reference_python):
    from paperdelta.incremental import CheckCache

    reference = None
    if reference_python:
        completed = subprocess.run(
            [
                str(reference_python),
                "-X",
                "utf8",
                str(Path(__file__).resolve()),
                "--worker",
                str(root),
                "--runs",
                str(runs),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=900,
        )
        reference = json.loads(completed.stdout)
    before = memory()
    cache = CheckCache()
    cold, cold_seconds = timed(root, cache)
    assert cold["exit_code"] == 0 and cold["coverage"]["pass"] == workload["bindings"]
    identity = comparable(cold)
    if reference:
        expected = digest(comparable(cold, previous_version=True))
        assert reference["report_hashes_without_version_or_clock"] == [expected] * runs
    full_times, warm_times = [], []
    for index in range(runs):
        # Alternate measurement order to reduce systematic order effects.
        for incremental in [False, True] if index % 2 == 0 else [True, False]:
            report, elapsed = timed(root, cache if incremental else None)
            assert comparable(report) == identity
            (warm_times if incremental else full_times).append(elapsed)
    return {
        "workload": workload,
        "reference": reference,
        "cold_incremental_seconds": cold_seconds,
        "full": summary(full_times),
        "warm_incremental": summary(warm_times),
        "report_sha256_without_clock": digest(identity),
        "all_reports_equal": True,
        "cache": cache.stats(),
        "memory_before": before,
        "memory_after": memory(),
    }


def invalidation(root):
    from paperdelta.incremental import CheckCache

    cache, store = CheckCache(), Project(root)
    paths = ["paper/part-01.tex", "results.csv", "paperdelta.yaml"]
    originals = {path: store.read(path) for path in paths}
    results = []

    def compare(name):
        full, full_seconds = timed(root)
        incremental, incremental_seconds = timed(root, cache)
        assert comparable(full) == comparable(incremental), name
        results.append(
            {
                "case": name,
                "exit_code": full["exit_code"],
                "all_report_fields_equal": True,
                "full_seconds": full_seconds,
                "incremental_seconds": incremental_seconds,
                "report_sha256_without_clock": digest(comparable(full)),
                "cache": cache.stats(),
            }
        )

    try:
        compare("cold")
        compare("warm")
        store.write(paths[0], originals[paths[0]] + b"\n% Edited discussion.\n")
        compare("one_document_edited")
        store.write(paths[1], originals[paths[1]].replace(b"0.4999", b"0.4499", 1))
        compare("evidence_value_changed")
        store.path(paths[1]).unlink()
        compare("evidence_deleted")
        store.write(paths[1], originals[paths[1]])
        compare("evidence_restored")
        rows = originals[paths[1]].splitlines(keepends=True)
        store.write(paths[1], b"".join([rows[0], *reversed(rows[1:])]))
        compare("evidence_rows_reordered")
        config, _ = load_config(store)
        config.metrics["result_AAA"].where["split"] = "train"
        store.write(paths[2], config_text(config).encode())
        compare("config_selector_changed")
        cache.identity = "different-parser-generation"
        compare("parser_identity_changed")
        for path, raw in originals.items():
            store.write(path, raw)
        compare("all_inputs_restored")
    finally:
        for path, raw in originals.items():
            store.write(path, raw)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--reference-python", type=Path)
    parser.add_argument("--worker", type=Path)
    args = parser.parse_args()
    assert 1 <= args.runs <= 100
    if args.worker:
        print(json.dumps(worker(args.worker, args.runs)))
        return
    assert args.out is not None and not args.out.exists()
    output = args.out.resolve()
    output.mkdir(parents=True)
    root = output / "large-project"
    workload = generate(root)
    inputs = {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }
    result = {
        "version": __version__,
        "started_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "same_large_project_input_hashes": inputs,
        "large_project": measure(root, workload, args.runs, args.reference_python),
    }
    print("Large-project full/incremental reports agree.", flush=True)
    pdf = output / "pdf-project"
    result["pdf_project"] = measure(pdf, pdf_fixture(pdf), args.runs, args.reference_python)
    print("PDF full/incremental reports agree.", flush=True)
    result["invalidation"] = invalidation(root)
    assert all(
        hashlib.sha256((root / path).read_bytes()).hexdigest() == value
        for path, value in inputs.items()
    )
    result.update(
        status="passed",
        finished_at=datetime.now(UTC).isoformat(),
        protocol=(
            "Authored local workloads; cold reuse includes cache population. Full and warm "
            "checks alternate order. Interpreter startup, UI rendering and models are excluded; "
            "OS caches are not flushed. P95 is an empirical nearest rank, not a guarantee. "
            "Cached retained bytes are bounded; RSS includes live checks, libraries and allocator "
            "retention and has no 64 MiB promise. Existing report fields including positions and "
            "coverage agree after excluding only created_at; cross-version comparisons also "
            "exclude tool_version."
        ),
    )
    (output / "evidence.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "large": result["large_project"]["warm_incremental"]["p95_seconds"],
                "pdf": result["pdf_project"]["warm_incremental"]["p95_seconds"],
            }
        )
    )


if __name__ == "__main__":
    main()
