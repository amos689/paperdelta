import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from paperdelta.analysis import check_project
from paperdelta.config import config_text, load_config
from paperdelta.errors import PaperDeltaError
from paperdelta.reviews import record_review
from paperdelta.snapshots import create_snapshot
from paperdelta.storage import Project, json_text, parse_json
from tools.ci_check import ci_summary, run_ci


@pytest.fixture
def git_repo(project):
    if shutil.which("git") is None:
        pytest.skip("This integration uses an actual Git repository")
    hooks = project / "empty-hooks"
    hooks.mkdir()

    def git(*args):
        return subprocess.run(
            [
                "git",
                "-C",
                str(project),
                "-c",
                f"core.hooksPath={hooks}",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "user.name=PaperDelta fixture",
                "-c",
                "user.email=fixture@example.invalid",
                *args,
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout.strip()

    git("init", "-q")
    return git


def _commit_baseline(project, git, name="submitted-v1"):
    path = create_snapshot(Project(project), name, check_project(project))
    git("add", "--", ".")
    git("commit", "-q", "-m", "Original fixture and submitted snapshot")
    return git("rev-parse", "HEAD"), path


def test_ci_uses_target_snapshot_even_if_pr_replaces_same_named_file(
    project, change_results, git_repo
):
    store = Project(project)
    base, path = _commit_baseline(project, git_repo)
    change_results(project)
    # Simulate a PR replacing its own baseline. CI must read the target object instead.
    proposed = parse_json(store.text(path)[0])
    proposed["report"] = check_project(project)
    store.write(path, json_text(proposed).encode())
    result = run_ci(project, base, "submitted-v1", "build/ci")
    assert result["context"]["baseline_status"] == "read_from_target_commit"
    assert result["report"]["exit_code"] == 1
    ours = next(c for c in result["report"]["changes"] if c["metric"] == "ours")
    assert ours["before"] == "0.841" and ours["after"] == "0.809"
    assert len(result["report"]["occurrences"]) == 5
    assert (project / "build/ci/report.html").is_file()
    assert store.text(path)[0] == json_text(proposed)
    changed = {item["path"]: item for item in result["context"]["policy_changes"]}
    assert changed[path]["kind"] == "baseline"
    assert changed[path]["change"] == "modified"
    assert changed[path]["target_hash"] == result["context"]["snapshot_hash"]
    assert changed[path]["current_hash"] != result["context"]["snapshot_hash"]
    assert result["context"]["configuration"]["status"] == "unchanged"
    assert "Repository declaration changes" in (project / "build/ci/ci-summary.md").read_text()

    missing = run_ci(project, base, "absent-on-target", "build/no-baseline")
    assert missing["context"]["baseline_status"] == "unavailable"
    assert missing["report"]["baseline"] is None
    assert missing["report"]["exit_code"] == 1


@pytest.mark.parametrize("change", ["formatting", "bindings", "rules"])
def test_ci_separates_configuration_semantics_from_file_changes(project, git_repo, change):
    base, _ = _commit_baseline(project, git_repo)
    path = project / "paperdelta.yaml"
    config, _ = load_config(Project(project))
    if change == "formatting":
        path.write_bytes(path.read_bytes() + b"\n# A formatting-only change.\n")
    else:
        if change == "bindings":
            del config.occurrences["table_accuracy"]
            del config.claims["main_comparison"]
        else:
            config.rounding = "half_even"
        path.write_text(config_text(config), encoding="utf-8")
    result = run_ci(project, base, "submitted-v1", "build/ci")
    assert result["report"]["exit_code"] == 0
    context = result["context"]
    assert [(c["path"], c["change"]) for c in context["policy_changes"]] == [
        ("paperdelta.yaml", "modified")
    ]
    semantic = context["configuration"]
    assert semantic["status"] == ("unchanged" if change == "formatting" else "changed")
    if change == "bindings":
        assert {(s["section"], tuple(s["removed"])) for s in semantic["sections"]} == {
            ("occurrences", ("table_accuracy",)),
            ("claims", ("main_comparison",)),
        }
    if change == "rules":
        assert semantic["settings"] == ["rounding"]
    assert (project / "build/ci/ci-context.json").is_file()


def test_ci_lists_added_and_deleted_snapshots_and_review_declarations(project, git_repo):
    store = Project(project)
    old_snapshot = create_snapshot(store, "obsolete", check_project(project))
    state = check_project(project)["claims"]["main_comparison"]["state_fingerprint"]
    old_review = record_review(
        store,
        "main_comparison",
        state,
        "Automated fixture",
        "Old synthetic declaration",
        attest_reviewed=True,
    )
    base, _ = _commit_baseline(project, git_repo)
    (project / old_snapshot).unlink()
    (project / old_review).unlink()
    new_snapshot = create_snapshot(store, "new-draft", check_project(project))
    new_review = record_review(
        store,
        "main_comparison",
        state,
        "Automated fixture",
        "New synthetic declaration",
        attest_reviewed=True,
    )
    result = run_ci(project, base, "submitted-v1", "build/ci")
    assert result["report"]["exit_code"] == 0
    changes = {c["path"]: (c["kind"], c["change"]) for c in result["context"]["policy_changes"]}
    assert changes == {
        old_snapshot: ("baseline", "removed"),
        new_snapshot: ("baseline", "added"),
        old_review: ("review_record", "removed"),
        new_review: ("review_record", "added"),
    }


def test_ci_unreadable_target_config_does_not_claim_semantic_equivalence(project, git_repo):
    path = project / "paperdelta.yaml"
    original = path.read_bytes()
    create_snapshot(Project(project), "submitted-v1", check_project(project))
    path.write_text("schema_version: 1\nschema_version: 1\n", encoding="utf-8")
    git_repo("add", "--", ".")
    git_repo("commit", "-q", "-m", "Synthetic invalid historical config")
    base = git_repo("rev-parse", "HEAD")
    path.write_bytes(original)
    result = run_ci(project, base, "submitted-v1", "build/ci")
    assert result["report"]["exit_code"] == 0
    assert result["context"]["configuration"]["status"] == "unavailable"
    assert "target" in result["context"]["configuration"]["reason"]


def test_ci_output_cannot_replace_a_snapshot(project, git_repo):
    base, path = _commit_baseline(project, git_repo, name="report")
    original = (project / path).read_bytes()
    with pytest.raises(PaperDeltaError) as error:
        run_ci(project, base, "report", ".paperdelta/baselines")
    assert error.value.code == "CI_OUTPUT"
    assert (project / path).read_bytes() == original
    assert not (project / ".paperdelta/baselines/report.html").exists()


def _ci_cli(project, base, *extra, env=None):
    tool = Path(__file__).resolve().parents[1] / "tools/ci_check.py"
    return subprocess.run(
        [
            sys.executable,
            "-I",
            str(tool),
            "--project",
            str(project),
            "--base-commit",
            base,
            "--snapshot",
            "submitted-v1",
            *extra,
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def test_ci_cli_preserves_exit_and_appends_summary_without_importing_paper_code(
    project, change_results, git_repo, tmp_path
):
    base, _ = _commit_baseline(project, git_repo)
    change_results(project)
    sentinel = project / "paper-code-executed"
    for name in ("paperdelta.py", "yaml.py"):
        (project / name).write_text(
            "from pathlib import Path\nPath('paper-code-executed').write_text('bad')\n"
            "raise RuntimeError('paper code must not run')\n",
            encoding="utf-8",
        )
    summary = tmp_path / "job-summary.md"
    summary.write_text("Earlier step.\n", encoding="utf-8")
    env = {**os.environ, "GITHUB_STEP_SUMMARY": str(summary), "PYTHONPATH": str(project)}
    result = _ci_cli(project, base, env=env)
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)["report"]["exit_code"] == 1
    assert not sentinel.exists()
    rendered = summary.read_text(encoding="utf-8")
    assert rendered.startswith("Earlier step.")
    assert "Current check exit code: **1**." in rendered
    assert "read_from_target_commit" in rendered and "VALUE_MISMATCH" in rendered
    assert (project / "build/paperdelta/report.html").is_file()


def test_ci_invalid_base_and_unsafe_summary_keep_errors_and_inputs(project, git_repo, tmp_path):
    base, _ = _commit_baseline(project, git_repo)
    summary = tmp_path / "job-summary.md"
    result = _ci_cli(project, "not-a-commit", "--summary-file", str(summary))
    assert result.returncode == 2 and json.loads(result.stdout)["code"] == "CI_BASE"
    assert "CI incomplete" in summary.read_text(encoding="utf-8")
    config = project / "paperdelta.yaml"
    before = config.read_bytes()
    result = _ci_cli(project, base, "--summary-file", str(config))
    assert result.returncode == 2 and json.loads(result.stdout)["code"] == "CI_OUTPUT"
    assert config.read_bytes() == before


def test_ci_summary_renders_untrusted_labels_as_text(project, git_repo):
    base, _ = _commit_baseline(project, git_repo)
    result = run_ci(project, base, "submitted-v1", "build/ci")
    result["context"]["policy_changes"] = [
        {
            "kind": "baseline",
            "path": "|<img src=x onerror=alert(1)>\n# injected\u202e",
            "change": "added",
            "target_hash": None,
            "current_hash": "sha256:fixture",
        }
    ]
    rendered = ci_summary(result)
    assert "<img" not in rendered and "&lt;img" in rendered
    assert "&#124;" in rendered and "\n# injected" not in rendered
    assert "\u202e" not in rendered and "\\u202e" in rendered
