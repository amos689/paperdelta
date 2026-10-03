"""Run the current implementation on previously seen frozen corpus scenarios.

This creates a new protocol/result, never updates the historical active study or locks.
"""

import argparse
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from evaluate_corpus import CORPUS, ROOT, run_case, verify_implementation, verify_sources

from paperdelta import __version__
from paperdelta.storage import json_text, sha256


def read(path):
    return json.loads(path.read_text("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        parser.error("Use a new output directory inside this checkout")
    original = read(ROOT / "docs/evidence/corpus-interactive-v2.json")
    lock = read(CORPUS / "protocol-interactive-v2.json")
    for name, identity in lock["identities"].items():
        if name.startswith("tests/corpus/"):
            assert sha256((ROOT / name).read_bytes()) == identity, name
    manifest = read(CORPUS / "manifest.json")
    annotations = read(CORPUS / "annotations.json")["bindings"]
    scenarios = read(CORPUS / "scenarios.json")["cases"]
    verify_sources(manifest, annotations)
    verify_implementation()
    files = [
        p
        for p in (ROOT / "src/paperdelta").rglob("*")
        if p.is_file() and p.suffix in {".py", ".json", ".css", ".js"}
    ] + [Path(__file__), ROOT / "tools/evaluate_corpus.py"]
    protocol = {
        "study_id": "bilingual-guides-v3",
        "kind": "regression_on_previously_seen_papers",
        "prepared_at": datetime.now(UTC).isoformat(),
        "original_lock_sha256": sha256((CORPUS / "protocol-interactive-v2.json").read_bytes()),
        "implementation": {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in files},
        "inputs": {n: h for n, h in lock["identities"].items() if n.startswith("tests/corpus/")},
    }
    output.mkdir(parents=True)
    (output / "protocol.json").write_text(json_text(protocol), "utf-8")
    outcomes = []
    start = perf_counter()
    for paper in manifest["papers"]:
        binding = next(item for item in annotations if item["paper"] == paper["id"])
        for scenario in scenarios:
            try:
                result = run_case(output, paper, binding, scenario)
            except Exception as exc:
                result = {
                    "paper": paper["id"],
                    "case": scenario["id"],
                    "actual": "crash",
                    "matched": False,
                    "exception": f"{type(exc).__name__}: {exc}",
                }
            outcomes.append(result)
        print(
            paper["id"],
            sum(r["matched"] for r in outcomes if r["paper"] == paper["id"]),
            flush=True,
        )
    summary = {
        "checked_at": datetime.now(UTC).isoformat(),
        "tool_version": __version__,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "study": protocol,
        "cases": len(outcomes),
        "matched": sum(r["matched"] for r in outcomes),
        "outcomes": outcomes,
        "matches_a2_outcomes": outcomes == original["outcomes"],
        "seconds": round(perf_counter() - start, 3),
        "scope": (
            "Same previously seen licensed text and synthetic evidence; "
            "no new held-out samples or human/model accuracy claim."
        ),
    }
    (output / "evidence.json").write_text(json_text(summary), "utf-8")
    print(json_text({k: v for k, v in summary.items() if k not in {"study", "outcomes"}}))
    return int(not summary["matches_a2_outcomes"])


if __name__ == "__main__":
    sys.exit(main())
