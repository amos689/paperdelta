"""Replay the preserved native v1 implementation without replacing first-run evidence."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    assert output.is_relative_to(ROOT / "build") and not output.exists()
    corpus = ROOT / "validation/native-v1"
    lock = json.loads((corpus / "implementation-lock.json").read_text("utf-8"))
    for name, digest in lock["files"].items():
        assert hashlib.sha256((corpus / "implementation" / name).read_bytes()).hexdigest() == digest
    checkout = output / "checkout"
    shutil.copytree(corpus / "implementation", checkout)
    shutil.copytree(
        corpus,
        checkout / "validation/native-v1",
        ignore=shutil.ignore_patterns("implementation", "__pycache__"),
    )
    launcher = output / "run.py"
    launcher.write_text(
        "import runpy, sys\nfrom pathlib import Path\n"
        "root = Path(__file__).resolve().parent / 'checkout'\n"
        "sys.path.insert(0, str(root / 'src'))\n"
        "sys.argv = ['evaluate_native.py', '--split', 'all', '--out', 'build/regression']\n"
        "runpy.run_path(str(root / 'tools/evaluate_native.py'), run_name='__main__')\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, "-I", "-X", "utf8", str(launcher)],
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )
    if result.returncode:
        return result.returncode
    scores = json.loads((checkout / "build/regression/results.json").read_text("utf-8"))
    assert scores["matches_implementation_lock"]
    expected = {
        "development": json.loads((corpus / "results/development-v1.1.json").read_text("utf-8")),
        "held-out": json.loads((corpus / "results/held-out-first.json").read_text("utf-8")),
    }
    # Record dependency differences; never describe a new environment as the original run.
    receipt = {
        "scope": "Frozen code regression on previously observed native documents",
        "matches_implementation_lock": True,
        "counts": scores["counts"],
        "dependencies": scores["dependencies"],
        "same_dependencies_as_first_run": scores["dependencies"]
        == expected["held-out"]["dependencies"],
        "outcomes_match": all(
            {r["id"]: r["outcome"] for r in scores["results"] if r["split"] == split}
            == {r["id"]: r["outcome"] for r in original["results"]}
            for split, original in expected.items()
        ),
    }
    (output / "evidence.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    return int(not receipt["outcomes_match"])


if __name__ == "__main__":
    raise SystemExit(main())
