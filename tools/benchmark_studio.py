"""Repeatable Studio state measurements, separate from browser rendering and checking."""

from __future__ import annotations

import argparse
import json
import math
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from benchmark import generate

from paperdelta import __version__
from paperdelta.storage import Project, json_text, sha256
from paperdelta.studio import StudioSession


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--samples", type=int, default=5)
    arguments = parser.parse_args()
    if not 1 <= arguments.samples <= 100:
        parser.error("samples must be between 1 and 100")
    arguments.out.mkdir(parents=True, exist_ok=False)
    root = arguments.project or arguments.out / "project"
    workload = generate(root) if arguments.project is None else {"reused_project": str(root)}
    project = Project(root)
    inputs = {
        project.relative(p): sha256(p.read_bytes())
        for p in root.rglob("*")
        if p.is_file() and ".paperdelta" not in p.relative_to(root).parts
    }
    start = perf_counter()
    session = StudioSession(project)
    startup = perf_counter() - start
    timings, sizes = [], []
    for _ in range(arguments.samples + 1):
        start = perf_counter()
        state = session.execute({"action": "state", "language": "en"})["state"]
        encoded = json_text(state).encode("utf-8")
        timings.append(perf_counter() - start)
        sizes.append(len(encoded))
        assert state["coverage"]["pass"] == 500 and not state["stale"]
    assert all(sha256(project.read(path)) == identity for path, identity in inputs.items())
    receipt = {
        "version": __version__,
        "measured_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "workload": workload,
        "input_hashes": inputs,
        "startup_seconds": startup,
        "first_state_seconds": timings[0],
        "state_seconds": timings,
        "state_p95_seconds": sorted(timings)[math.ceil(0.95 * len(timings)) - 1],
        "subsequent_state_seconds": timings[1:],
        "subsequent_state_p95_seconds": sorted(timings[1:])[
            math.ceil(0.95 * arguments.samples) - 1
        ],
        "state_bytes": sizes,
        "scope": (
            "Session state plus exact JSON serialization; warm OS cache, "
            "no browser, network or model time."
        ),
    }
    (arguments.out / "evidence.json").write_text(json.dumps(receipt, indent=2) + "\n", "utf-8")
    print(
        json.dumps(
            {key: receipt[key] for key in ("startup_seconds", "state_p95_seconds", "state_bytes")}
        )
    )


if __name__ == "__main__":
    main()
