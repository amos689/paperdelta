"""Materialize and run the preserved original implementation in a new scratch tree.

This uses the caller's installed dependencies, so it is an implementation replay,
not an exact recreation of the earlier software environment or a new held-out run.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    assert output.is_relative_to(ROOT) and not output.exists(), "Choose a new local directory"
    corpus = ROOT / "tests/corpus"
    study = json.loads((corpus / "active-study.json").read_text("utf-8"))
    history = (ROOT / study["previous_implementation"]).resolve()
    assert history.is_relative_to(corpus.resolve())
    original = ROOT / study["previous_protocol"]
    lock = json.loads(original.read_text("utf-8"))
    assert (history / "tests/corpus/protocol-lock.json").read_bytes() == original.read_bytes()
    for name, identity in lock["identities"].items():
        source = (history / name).resolve()
        assert source.is_relative_to(history)
        assert "sha256:" + sha256(source.read_bytes()).hexdigest() == identity, name
    shutil.copytree(history, output, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copytree(corpus / "papers", output / "tests/corpus/papers")
    env = {**os.environ, "PYTHONPATH": str(output / "src"), "PYTHONUTF8": "1"}
    completed = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "tools/evaluate_corpus.py",
            "--split",
            "all",
            "--out",
            "build/replay",
        ],
        cwd=output,
        env=env,
        check=False,
    )
    print("Historical replay only; original first-evaluation records remain unchanged.")
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
