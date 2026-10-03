"""Replay a frozen historical study in a new workspace using its exact archived code.

No model inference, downloads, original record edits or binding acceptance occurs.
The corpus mode requires the separately licensed evaluation materials to be present.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVES = ROOT / "evaluations/implementations"


def read(path):
    return json.loads(path.read_text("utf-8"))


def digest(path):
    return "sha256:" + sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("study", choices=["corpus-a2", "mapping-v1", "staged-v2", "staged-v3"])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        parser.error("Choose a new output directory inside this checkout")
    implementation = args.study if args.study.startswith("staged-") else "a2"
    record = read(ARCHIVES / "registry.json")["implementations"][implementation]
    archive = ARCHIVES / implementation
    for name, expected in record["identities"].items():
        source = (archive / name).resolve()
        if not source.is_relative_to(archive) or digest(source) != expected:
            raise ValueError(f"Changed historical implementation: {name}")
    if args.study == "corpus-a2" and not (ROOT / "tests/corpus/manifest.json").is_file():
        parser.error("Unpack the matching licensed evaluation bundle first")
    workspace = output / "workspace"
    workspace.mkdir(parents=True)
    for name in record["identities"]:
        target = workspace / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive / name, target)
    shutil.copytree(ROOT / "evaluations/mapping-v1", workspace / "evaluations/mapping-v1")
    original = None
    if args.study == "corpus-a2":
        shutil.copytree(ROOT / "tests/corpus", workspace / "tests/corpus")
        command = ["tools/evaluate_corpus.py", "--split", "all", "--out", "build/results"]
        result_path = workspace / "build/results/evidence.json"
        original = read(ROOT / "docs/evidence/corpus-interactive-v2.json")
    elif args.study == "mapping-v1":
        command = ["tools/validate_mapping_controls.py", "--out", "build/results"]
        result_path = workspace / "build/results/evidence.json"
        original = read(ROOT / "docs/evidence/mapping-controls/evidence.json")
    else:
        relative = f"docs/evidence/local-model-{args.study}"
        shutil.copytree(
            ROOT / relative,
            workspace / relative,
            ignore=lambda _directory, names: [name for name in names if name == "score.json"],
        )
        original = read(ROOT / relative / "score.json")
        shutil.copyfile(ROOT / relative / "score.json", output / "original-score.json")
        command = ["-m", "tools.evaluate_staged_mappings", "score", "--directory", relative]
        result_path = workspace / relative / "score.json"
    environment = {**os.environ, "PYTHONPATH": str(workspace / "src"), "PYTHONUTF8": "1"}
    completed = subprocess.run(
        [sys.executable, "-X", "utf8", *command],
        cwd=workspace,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
        check=False,
    )
    (output / "stdout.log").write_text(completed.stdout, "utf-8")
    (output / "stderr.log").write_text(completed.stderr, "utf-8")
    replay = read(result_path) if result_path.is_file() else None
    if args.study == "corpus-a2":
        matched = (
            completed.returncode == 1 and replay and replay["outcomes"] == original["outcomes"]
        )
    elif args.study == "mapping-v1":
        matched = (
            completed.returncode == 0 and replay and replay["controls"] == original["controls"]
        )
    else:
        expected = {key: value for key, value in original.items() if key != "scored_at"}
        actual = {key: value for key, value in (replay or {}).items() if key != "scored_at"}
        matched = completed.returncode == 0 and actual == expected
    evidence = {
        "checked_at": datetime.now(UTC).isoformat(),
        "study": args.study,
        "implementation": record,
        "child_exit_code": completed.returncode,
        "matches_original_record": bool(matched),
        "result_sha256": digest(result_path) if replay else None,
        "model_calls": 0,
        "scope": (
            "Historical replay/rescoring with exact archived implementation; "
            "not new model or held-out evidence."
        ),
    }
    (output / "replay.json").write_text(json.dumps(evidence, indent=2) + "\n", "utf-8")
    print(json.dumps({k: v for k, v in evidence.items() if k != "implementation"}, indent=2))
    return int(not matched)


if __name__ == "__main__":
    raise SystemExit(main())
