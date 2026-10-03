"""Create two local Git scenarios and retain their complete CI review artifacts."""

import argparse
import shutil
import subprocess
from pathlib import Path

from ci_check import run_ci

from paperdelta.analysis import check_project
from paperdelta.config import config_text, load_config
from paperdelta.snapshots import create_snapshot
from paperdelta.storage import Project, json_text, parse_json, sha256


def make_case(source, root, weaken_declarations):
    shutil.copytree(
        source,
        root,
        ignore=lambda _, names: [n for n in names if n in {"build", ".paperdelta"}],
    )
    project = Project(root)
    originals = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*.tex")}
    hooks = root / "empty-hooks"
    hooks.mkdir()

    def git(*arguments):
        return subprocess.check_output(
            [
                "git",
                "-C",
                str(root),
                "-c",
                f"core.hooksPath={hooks}",
                "-c",
                "core.autocrlf=false",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "user.name=PaperDelta synthetic fixture",
                "-c",
                "user.email=fixture@example.invalid",
                *arguments,
            ],
            text=True,
            encoding="utf-8",
            stderr=subprocess.PIPE,
        ).strip()

    git("init", "-q")
    snapshot = create_snapshot(project, "submitted-v1", check_project(root))
    git("add", "--", ".")
    git("commit", "-q", "-m", "Synthetic paper before experiment update")
    target = git("rev-parse", "HEAD")
    source_path = "results/metrics.csv"
    changed = project.read(source_path)
    for old, new in ((b"0.839", b"0.807"), (b"0.841", b"0.809"), (b"0.843", b"0.811")):
        changed = changed.replace(old, new)
    project.write(source_path, changed)
    if weaken_declarations:
        config, _ = load_config(project)
        config.occurrences = {"table_baseline": config.occurrences["table_baseline"]}
        config.claims = {}
        project.write("paperdelta.yaml", config_text(config).encode("utf-8"))
        replacement = parse_json(project.text(snapshot)[0])
        replacement["report"] = check_project(root)
        project.write(snapshot, json_text(replacement).encode("utf-8"))
    result = run_ci(root, target, "submitted-v1", "build/review")
    expected = 0 if weaken_declarations else 1
    assert result["report"]["exit_code"] == expected
    assert result["context"]["baseline_status"] == "read_from_target_commit"
    assert {name: project.read(name) for name in originals} == originals
    assert len(result["context"]["policy_changes"]) == (2 if weaken_declarations else 0)
    ours = next(change for change in result["report"]["changes"] if change["metric"] == "ours")
    assert ours["before"] == "0.841" and ours["after"] == "0.809"
    if weaken_declarations:
        assert result["report"]["coverage"]["confirmed"] == 1
        assert result["report"]["removed_bindings"]["occurrences"] == [
            "abstract_accuracy",
            "appendix_accuracy",
            "gain_text",
            "table_accuracy",
        ]
        assert result["report"]["removed_bindings"]["claims"] == ["main_comparison"]
    else:
        assert result["report"]["coverage"]["mismatch"] == 5
    return {
        "target_commit": target,
        "check_exit": expected,
        "confirmed": result["report"]["coverage"]["confirmed"],
        "mismatch": result["report"]["coverage"]["mismatch"],
        "policy_changes": result["context"]["policy_changes"],
        "configuration": result["context"]["configuration"],
        "all_tex_bytes_unchanged": True,
        "original_tex_hashes": {name: sha256(raw) for name, raw in originals.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    output = Project(repository).path(args.out)
    if output.exists():
        parser.error("Choose a new output directory")
    if shutil.which("git") is None:
        parser.error("Git is required for this local CI example")
    source = repository / "examples/research-paper"
    results = {
        name: make_case(source, output / name, weakening)
        for name, weakening in (("data-only", False), ("changed-declarations", True))
    }
    evidence = {
        "cases": results,
        "model_runs": 0,
        "independent_participants": 0,
        "scope": "Synthetic local Git scenarios, not a remote GitHub workflow execution.",
    }
    (output / "evidence.json").write_text(json_text(evidence), encoding="utf-8")
    print(json_text(evidence), end="")


if __name__ == "__main__":
    main()
