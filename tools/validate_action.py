"""Exercise the trusted action against a fresh, deliberately untrusted paper Git checkout."""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from paperdelta.analysis import check_project
from paperdelta.snapshots import create_snapshot
from paperdelta.storage import Project, json_text, sha256

ROOT = Path(__file__).resolve().parents[1]


def prepare(output):
    output.mkdir(parents=True, exist_ok=False)
    paper = output / "paper"
    shutil.copytree(
        ROOT / "examples/research-paper",
        paper,
        ignore=lambda _, names: [n for n in names if n in {"build", ".paperdelta"}],
    )
    store = Project(paper)
    originals = {
        p.relative_to(paper).as_posix(): sha256(p.read_bytes()) for p in paper.rglob("*.tex")
    }
    snapshot = create_snapshot(store, "submitted-v1", check_project(paper))
    hooks = output / "empty-hooks"
    hooks.mkdir()

    def git(*arguments):
        return subprocess.check_output(
            [
                "git",
                "-C",
                str(paper),
                "-c",
                "core.autocrlf=false",
                "-c",
                "core.hooksPath=" + str(hooks),
                "-c",
                "commit.gpgsign=false",
                "-c",
                "user.name=PaperDelta fixture",
                "-c",
                "user.email=fixture@example.invalid",
                *arguments,
            ],
            text=True,
            encoding="utf-8",
            stderr=subprocess.PIPE,
        ).strip()

    git("init", "-q")
    git("add", ".")
    git("commit", "-q", "-m", "Original authored paper and checked snapshot")
    base = git("rev-parse", "HEAD")
    changed = store.read("results/metrics.csv")
    for before, after in ((b"0.839", b"0.807"), (b"0.841", b"0.809"), (b"0.843", b"0.811")):
        changed = changed.replace(before, after)
    store.write("results/metrics.csv", changed)
    sentinel = "EXECUTED_PAPER_CODE"
    trap = (
        "from pathlib import Path\n"
        f"Path({str(paper / sentinel)!r}).write_text('Paper code was executed')\n"
        "raise RuntimeError('Never install or import the paper checkout')\n"
    ).encode()
    for name in ("sitecustomize.py", "setup.py", "paperdelta.py"):
        store.write(name, trap)
    value = {
        "project": paper.relative_to(ROOT).as_posix(),
        "base": base,
        "original_tex_hashes": originals,
        "config_hash": sha256(store.read("paperdelta.yaml")),
        "snapshot_hash": sha256(store.read(snapshot)),
        "sentinel": sentinel,
    }
    (output / "fixture.json").write_text(json_text(value), encoding="utf-8", newline="\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"project={value['project']}\nbase={base}\n")
    return value


def verify(output, language, code):
    value = json.loads((output / "fixture.json").read_text("utf-8"))
    paper = ROOT / value["project"]
    store = Project(paper)
    report_dir = paper / "build" / ("action-" + language)
    report = json.loads((report_dir / "report.json").read_text("utf-8"))
    context = json.loads((report_dir / "ci-context.json").read_text("utf-8"))
    sarif = json.loads((report_dir / "report.sarif").read_text("utf-8"))
    assert code == report["exit_code"] == 1
    assert context["configuration"]["status"] == "unchanged"
    assert context["baseline_status"] == "read_from_target_commit"
    assert context["finding_changes"]["counts"]["added_failures"] == 5
    assert report["coverage"]["mismatch"] == 5
    assert sarif["runs"][0]["results"]
    assert sha256(store.read("paperdelta.yaml")) == value["config_hash"]
    assert sha256(store.read(".paperdelta/baselines/submitted-v1.json")) == value["snapshot_hash"]
    assert all(
        sha256(store.read(name)) == digest for name, digest in value["original_tex_hashes"].items()
    )
    assert not (paper / value["sentinel"]).exists()
    summary = (report_dir / "ci-summary.md").read_text("utf-8")
    assert ("新报告的失败" if language == "zh-CN" else "Newly reported failures") in summary
    result = {
        "status": "passed",
        "language": language,
        "expected_exit_code": code,
        "fresh_paper_git_repository": True,
        "paper_code_executed": False,
        "only_evidence_changed": True,
        "new_failures": 5,
        "original_inputs_preserved": True,
        "sarif_written": True,
    }
    (output / ("verification-" + language + ".json")).write_text(
        json_text(result), encoding="utf-8", newline="\n"
    )
    return result


def local(output):
    fixture = prepare(output)
    temporary = output / "runner-temp"
    temporary.mkdir()
    environment = {
        **os.environ,
        "GITHUB_WORKSPACE": str(ROOT),
        "RUNNER_TEMP": str(temporary),
        "GITHUB_ENV": str(output / "github-env"),
        "GITHUB_OUTPUT": str(output / "github-output"),
        "GITHUB_STEP_SUMMARY": str(output / "summary.md"),
        "PYTHONUTF8": "1",
    }
    command = [sys.executable, "-I", "-X", "utf8", str(ROOT / "tools/action_check.py")]
    with (output / "install.log").open("w", encoding="utf-8") as log:
        subprocess.run(
            command + ["--install"],
            cwd=temporary,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=240,
        )
    for line in (output / "github-env").read_text("utf-8").splitlines():
        key, value = line.split("=", 1)
        environment[key] = value
    results = []
    for language in ("en", "zh-CN"):
        values = {
            "PROJECT": fixture["project"],
            "BASE": fixture["base"],
            "SNAPSHOT": "submitted-v1",
            "CONFIG": "paperdelta.yaml",
            "REPORT": "build/action-" + language,
            "LANG": language,
        }
        environment.update({"PAPERDELTA_ACTION_" + key: value for key, value in values.items()})
        with (output / (language + ".log")).open("w", encoding="utf-8") as log:
            checked = subprocess.run(
                command,
                cwd=temporary,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=120,
            )
        results.append(verify(output, language, checked.returncode))
    return {
        "status": "passed",
        "scope": "Local action entry point; remote composite run is separate.",
        "cases": results,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["prepare", "verify", "local"])
    parser.add_argument("--out", required=True)
    parser.add_argument("--lang", choices=["en", "zh-CN"], default="en")
    parser.add_argument("--exit-code", type=int, default=1)
    args = parser.parse_args()
    output = Project(ROOT).path(args.out)
    if args.mode == "prepare":
        result = prepare(output)
    elif args.mode == "verify":
        result = verify(output, args.lang, args.exit_code)
    else:
        result = local(output)
        (output / "evidence.json").write_text(json_text(result), encoding="utf-8", newline="\n")
    print(json_text(result))


if __name__ == "__main__":
    main()
