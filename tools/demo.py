"""Build a repeatable offline demonstration in a new project-local output directory."""

import argparse
import json
from pathlib import Path
from shutil import copytree
from time import perf_counter

from paperdelta.analysis import check_project
from paperdelta.patches import apply_patch, create_patch, preview_patch, recover_transaction
from paperdelta.reports import write_reports
from paperdelta.snapshots import create_snapshot, read_snapshot
from paperdelta.storage import Project, json_text


def add_figure(project, repository):
    assets = repository / "examples/figure-support"
    for original, target in {
        "plot_accuracy.py": "scripts/plot_accuracy.py",
        "figure.tex": "paper/figure.tex",
        "accuracy.pdf": "paper/figures/accuracy.pdf",
        "accuracy.record.json": "paper/figures/accuracy.record.json",
    }.items():
        project.write(target, (assets / original).read_bytes())
    main, _ = project.text("paper/main.tex")
    main = main.replace(r"\usepackage{booktabs}", "\\usepackage{booktabs}\n\\usepackage{graphicx}")
    main = main.replace(r"\input{appendix}", "\\input{figure}\n\\input{appendix}")
    project.write("paper/main.tex", main.encode("utf-8"))
    project.write(
        "paperdelta.yaml",
        project.read("paperdelta.yaml")
        + b"\nfigures:\n  accuracy: {path: paper/figures/accuracy.pdf, "
        b"record: paper/figures/accuracy.record.json}\n",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="build/demo")
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    output = Project(repository).path(args.out)
    if output.exists():
        raise SystemExit("Choose a new --out directory; existing demonstrations are preserved.")
    started = perf_counter()
    source = repository / "examples/research-paper"
    results = {}
    for case, values in (
        ("comparison-reversed", ("0.807", "0.809", "0.811")),
        ("numeric-update", ("0.843", "0.845", "0.847")),
    ):
        root = output / case
        copytree(
            source,
            root,
            ignore=lambda _, names: [name for name in names if name in {".paperdelta", "build"}],
        )
        project = Project(root)
        if case == "comparison-reversed":
            add_figure(project, repository)
        before = check_project(root)
        assert before["exit_code"] == 0
        create_snapshot(project, "before", before)
        write_reports(project, "before", before)
        original_tex = {
            file: project.read(file) for file in before["input_hashes"] if file.endswith(".tex")
        }
        csv_path = "results/metrics.csv"
        text, _ = project.text(csv_path)
        lines = text.splitlines()
        for index, new in enumerate(values, start=1):
            cells = lines[index].split(",")
            assert cells[1] == "Ours" and cells[3] == str(index)
            cells[-1] = new
            lines[index] = ",".join(cells)
        text = "\n".join(lines) + "\n"
        project.write(csv_path, text.encode("utf-8"))
        baseline = read_snapshot(project, "before")
        changed = check_project(root, baseline=baseline)
        assert changed["exit_code"] == 1
        write_reports(project, "review", changed)
        case_result = {
            "before": before["coverage"],
            "changed": changed["coverage"],
            "changes": changed["changes"],
            "report": (root / "review/report.html").relative_to(repository).as_posix(),
        }
        if case == "numeric-update":
            patch = create_patch(project, changed)
            project.write("changes.pdpatch.json", json_text(patch).encode("utf-8"))
            project.write("changes.diff", preview_patch(project, patch).encode("utf-8"))
            applied = apply_patch(project, patch)
            assert applied["report"]["exit_code"] == 0
            write_reports(project, "after", applied["report"])
            recover_transaction(project, applied["transaction_id"], write=True)
            assert all(project.read(file) == raw for file, raw in original_tex.items())
            case_result["patch_changes"] = len(patch["changes"])
            case_result["applied_exit_code"] = applied["report"]["exit_code"]
            case_result["restored_byte_exactly"] = True
        else:
            assert changed["claims"]["main_comparison"]["status"] == "mismatch"
            assert changed["figures"]["accuracy"]["provenance"] == "dependency_changed"
            assert all(
                item["suggestion"]["blocked_by"]
                for item in changed["occurrences"].values()
                if "suggestion" in item
            )
        results[case] = case_result
    results["elapsed_seconds"] = round(perf_counter() - started, 3)
    results["scope"] = (
        "Original synthetic fixtures; not real-paper accuracy or user onboarding evaluation."
    )
    (output / "evidence.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json_text(results), end="")


if __name__ == "__main__":
    main()
