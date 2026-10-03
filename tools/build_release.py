"""Build the MIT Python distributions and a separate licensed evaluation bundle."""

import argparse
import json
import os
import subprocess
import sys
import tomllib
import zipfile
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    assert output.is_relative_to(ROOT) and not output.exists(), "Choose a new local directory"
    output.mkdir(parents=True)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    env = {**os.environ, "PYTHONUTF8": "1"}
    built = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "build", "--outdir", str(output)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log = (built.stdout + built.stderr).replace(str(ROOT), "<checkout>")
    (output / "build.log").write_text(log, encoding="utf-8")
    if built.returncode:
        print(log[-5000:])
        return built.returncode
    files = {
        p.relative_to(ROOT).as_posix() for p in (ROOT / "tests/corpus").rglob("*") if p.is_file()
    }
    files.update(
        p.relative_to(ROOT).as_posix() for p in (ROOT / "docs/evidence").glob("corpus*.json")
    )
    files.update({"LICENSE", "THIRD_PARTY_NOTICES.md", "docs/evaluation.md"})
    manifest = {
        "bundle_schema_version": 1,
        "paperdelta_version": project["version"],
        "active_study": json.loads((ROOT / "tests/corpus/active-study.json").read_text("utf-8")),
        "license_expression": "MIT AND CC-BY-4.0 AND CC-BY-SA-4.0",
        "meaning": "An aggregate of separately licensed files; not relicensing the original code.",
        "files": {
            name: {
                "sha256": sha256((ROOT / name).read_bytes()).hexdigest(),
                "bytes": (ROOT / name).stat().st_size,
            }
            for name in sorted(files)
        },
    }
    target = output / f"paperdelta-evaluation-{project['version']}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(files):
            bundle.write(ROOT / name, name)
        bundle.writestr("evaluation-bundle.json", json.dumps(manifest, indent=2) + "\n")
        bundle.writestr(
            "EVALUATION_README.md",
            "# PaperDelta evaluation materials\n\n"
            "Read THIRD_PARTY_NOTICES.md before reusing paper sources. Each work retains "
            "its license and author notices; PaperDelta's MIT license covers its original code.\n\n"
            "The Python wheel and source distribution exclude this corpus. To reproduce "
            "the evaluation, unpack this bundle at the root of the matching PaperDelta "
            f"{project['version']} source checkout, preserving the directories. "
            "Run `python tools/evaluate_corpus.py --split all --out build/corpus-replay`. "
            "Use a fresh output directory. Do not replace the recorded first held-out results.\n\n"
            "The current run is a regression on already observed papers. "
            "tests/corpus/active-study.json identifies its lock and the preserved "
            "original implementation; see tests/corpus/README.md for historical replay.\n\n"
            "The protocol lock checks the exact core, evaluator and input identities. "
            "The papers are paired with controlled synthetic evidence, not reproduced "
            "original experiments. See docs/evaluation.md for failures and limits.\n",
        )
    print(
        json.dumps(
            {
                "artifacts": [p.relative_to(ROOT).as_posix() for p in sorted(output.iterdir())],
                "evaluation_files": len(files),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
