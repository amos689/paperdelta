"""Exercise complete, locally configured CLI update workflows on one owned paper.

Run with PaperDelta's development Python. Reference CLIs must already be
installed in --reference-env. No installation/setup time or human work is timed.
Every run requires a new project-local --out directory and preserves its files.
"""

import argparse
import difflib
import json
import os
import platform
import shutil
import subprocess
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter

import yaml

from paperdelta.storage import Project

REPOSITORY = Path(__file__).resolve().parents[1]
GAIN = "Our method improves by 3.1 percentage points over Baseline."
COMPARISON = "Our method outperforms Baseline on Data-A."


def paper_bytes(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in (root / "paper").glob("*.tex")}


def edit(root, path, old, new):
    target = root / path
    source = target.read_text(encoding="utf-8")
    assert source.count(old) == 1, (path, old)
    target.write_text(source.replace(old, new), encoding="utf-8", newline="\n")


def add_reference_macros(root, tool):
    if tool == "calkit":
        replacements = [
            ("paper/abstract.tex", r"84.1\%", r"\qa[ours-percent.answer]"),
            ("paper/results.tex", "Ours & 84.1", r"Ours & \qa[ours-bare.answer]"),
            ("paper/results.tex", "Baseline & 81.0", r"Baseline & \qa[baseline-bare.answer]"),
            ("paper/results.tex", GAIN, r"\qa[gain.answer]"),
            ("paper/results.tex", COMPARISON, r"\qa[comparison.answer]"),
            ("paper/appendix.tex", r"\score{84.1}", r"\score{\qa[ours-bare.answer]}"),
        ]
    else:
        replacements = [
            ("paper/abstract.tex", r"84.1\%", r"\SciVal{\OursPercent}{84.1\%}"),
            ("paper/results.tex", "Ours & 84.1", r"Ours & \SciVal{\OursBare}{84.1}"),
            ("paper/results.tex", "Baseline & 81.0", r"Baseline & \SciVal{\BaselineBare}{81.0}"),
            ("paper/results.tex", GAIN, r"\SciText{\GainSentence}{" + GAIN + "}"),
            ("paper/results.tex", COMPARISON, r"\SciText{\Comparison}{" + COMPARISON + "}"),
            ("paper/appendix.tex", r"\score{84.1}", r"\score{\SciVal{\OursBare}{84.1}}"),
        ]
    edit(
        root,
        "paper/main.tex",
        r"\begin{document}",
        "\\input{../generated/values}\n" + r"\begin{document}",
    )
    for path, old, new in replacements:
        edit(root, path, old, new)
    return len(replacements)


def calkit_config():
    specs = [
        ("ours-percent", "{ours:.1%}", ["ours"]),
        ("ours-bare", "{ours:.1%}", ["ours"]),
        ("baseline-bare", "{baseline:.1%}", ["baseline"]),
        (
            "gain",
            {
                "if gain > 0": "Our method improves by {gain:.1f} percentage points over Baseline.",
                "else": "Our method changes by {gain:.1f} percentage points relative to Baseline.",
            },
            ["gain"],
        ),
        (
            "comparison",
            {
                "if ours > baseline": COMPARISON,
                "else": "Our method does not outperform Baseline on Data-A.",
            },
            ["ours", "baseline"],
        ),
    ]
    # A distinct percent-number evidence field keeps the original table style.
    specs[1] = ("ours-bare", "{ours_percent:.1f}", ["ours_percent"])
    specs[2] = ("baseline-bare", "{baseline_percent:.1f}", ["baseline_percent"])
    questions = [
        {
            "name": name,
            "question": f"What is the declared {name} result on Data-A test seeds 1/2/3?",
            "answer": answer,
            "evidence": [
                {"kind": "value", "path": "generated/results.json", "key": key, "name": key}
                for key in keys
            ],
        }
        for name, answer, keys in specs
    ]
    return {
        "questions": questions,
        "pipeline": {
            "stages": {
                "export": {
                    "kind": "command",
                    "environment": "_system",
                    "command": "python export_values.py --format calkit",
                    "inputs": ["export_values.py", "results/metrics.csv"],
                    "outputs": ["generated/results.json"],
                },
                "qa": {
                    "kind": "questions-to-latex",
                    "outputs": ["generated/values.tex"],
                    "command_name": "qa",
                },
            }
        },
    }


def change_data(root):
    path = root / "results/metrics.csv"
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, value in enumerate(("0.807", "0.809", "0.811"), 1):
        cells = lines[index].split(",")
        assert (cells[1], cells[2], cells[3]) == ("Ours", "test", str(index))
        cells[-1] = value
        lines[index] = ",".join(cells)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="build/reference-workflows")
    parser.add_argument("--reference-env", default=".venv-references")
    args = parser.parse_args()
    output = Project(REPOSITORY).path(args.out)
    if output.exists():
        raise SystemExit("Choose a new --out directory; previous runs are preserved.")
    output.mkdir(parents=True)
    reference = Path(args.reference_env).resolve()
    bin_dir = reference / ("Scripts" if os.name == "nt" else "bin")
    suffix = ".exe" if os.name == "nt" else ""
    binaries = {
        name: str(bin_dir / (name + suffix)) for name in ("python", "calkit", "scitexlintr")
    }
    pd_bin = REPOSITORY / (
        ".venv/Scripts/paperdelta.exe" if os.name == "nt" else ".venv/bin/paperdelta"
    )
    env = dict(os.environ)
    env.update(
        PATH=str(bin_dir) + os.pathsep + env.get("PATH", ""),
        PYTHONUTF8="1",
        DVC_NO_ANALYTICS="1",
        DO_NOT_TRACK="1",
        NO_COLOR="1",
    )
    commands = []

    def redact(text):
        return text.replace(str(REPOSITORY), "<checkout>").replace(
            REPOSITORY.as_posix(), "<checkout>"
        )

    def run(root, label, command, expected=(0,)):
        started = perf_counter()
        completed = subprocess.run(
            command,
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        record = {
            "tool": root.name,
            "label": label,
            "command": [redact(str(arg)) for arg in command],
            "exit_code": completed.returncode,
            "wall_seconds": round(perf_counter() - started, 4),
            "stdout": redact(completed.stdout),
            "stderr": redact(completed.stderr),
        }
        commands.append(record)
        (output / "commands.json").write_text(
            json.dumps(commands, indent=2) + "\n", encoding="utf-8"
        )
        print(f"{root.name}: {label}: exit {completed.returncode}", flush=True)
        assert completed.returncode in expected, record
        return completed

    results = {}
    for tool in ("paperdelta", "calkit", "scitexlintr"):
        root = output / tool
        shutil.copytree(
            REPOSITORY / "examples/research-paper",
            root,
            ignore=lambda _, names: [n for n in names if n in {"build", ".paperdelta"}],
        )
        original = paper_bytes(root)
        if tool != "paperdelta":
            (root / "paperdelta.yaml").unlink()
            shutil.copy2(REPOSITORY / "tools/reference_export.py", root / "export_values.py")
            sites = add_reference_macros(root, tool)
        else:
            sites = 0
        setup = paper_bytes(root)
        diff = "".join(
            "".join(
                difflib.unified_diff(
                    original[path].decode().splitlines(keepends=True),
                    setup[path].decode().splitlines(keepends=True),
                    fromfile=path,
                    tofile=path,
                )
            )
            for path in sorted(original)
        )
        (output / f"{tool}-setup.diff").write_text(diff, encoding="utf-8")
        results[tool] = {
            "rewritten_result_sites": sites,
            "rewritten_existing_tex_files": sum(original[p] != setup[p] for p in original),
            "preamble_include_added": tool != "paperdelta",
        }
        if tool == "paperdelta":
            cli = [str(pd_bin)]
            run(root, "before", [*cli, "check", "--report", "build/before", "--format", "json"])
            run(root, "snapshot", [*cli, "snapshot", "create", "before"])
            change_data(root)
            assert paper_bytes(root) == setup
            run(
                root,
                "changed",
                [
                    *cli,
                    "check",
                    "--baseline",
                    "before",
                    "--report",
                    "build/changed",
                    "--format",
                    "json",
                ],
                (1,),
            )
            report = json.loads((root / "build/changed/report.json").read_text(encoding="utf-8"))
            assert report["coverage"]["mismatch"] == 5
            assert report["claims"]["main_comparison"]["status"] == "mismatch"
            run(
                root,
                "guarded-fix",
                [*cli, "fix", "--report", "build/changed/report.json", "--out", "proposed.json"],
                (2,),
            )
            assert paper_bytes(root) == setup and not (root / "proposed.json").exists()
            results[tool].update(
                numeric_mismatches=4,
                false_comparisons=1,
                related_numeric_patch_withheld=True,
                source_unchanged_during_check=True,
            )
        elif tool == "calkit":
            cli = [binaries["calkit"]]
            # Explicit scratch Git root prevents initialization in the parent checkout.
            run(root, "git-init", ["git", "init", "-q"])
            run(root, "init", [*cli, "init", "--no-commit"])
            (root / "calkit.yaml").write_text(
                yaml.safe_dump(calkit_config(), sort_keys=False), encoding="utf-8"
            )
            run(root, "before-run", [*cli, "run"])
            before = (root / "generated/values.tex").read_text(encoding="utf-8")
            assert r"84.1\%" in before and COMPARISON.replace("-", "{-}") in before
            run(root, "before-evidence", [*cli, "check", "questions", "--json"])
            change_data(root)
            assert paper_bytes(root) == setup
            run(root, "stale-evidence", [*cli, "check", "questions", "--json"], (1,))
            run(root, "changed-run", [*cli, "run"])
            run(root, "after-evidence", [*cli, "check", "questions", "--json"])
            after = (root / "generated/values.tex").read_text(encoding="utf-8")
            assert r"80.9\%" in after and "does not outperform" in after
            assert "{-}0.1" in after
            assert paper_bytes(root) == setup
            results[tool].update(
                upstream_csv_change_detected=True,
                generated_values_changed=True,
                conditional_answer_reversed=True,
                declared_paper_template_unchanged=True,
            )
        else:
            cli = [
                binaries["scitexlintr"],
                "--manifest",
                "generated/manifest.json",
                "--rules",
                "snapshot-mismatch,unknown-value-id",
                *sorted(setup),
            ]
            exporter = [binaries["python"], "export_values.py", "--format", "scitexlintr"]
            run(root, "before-export", exporter)
            run(root, "before-lint", cli)
            change_data(root)
            assert paper_bytes(root) == setup
            run(root, "changed-export", exporter)
            changed = run(root, "changed-lint", cli, (1,))
            assert changed.stdout.count("[snapshot-mismatch]") == 5, changed.stdout
            run(root, "repair-and-relint", [*cli, "--write"])
            fixed = paper_bytes(root)
            assert b"80.9" in fixed["paper/abstract.tex"]
            assert b"does not outperform" in fixed["paper/results.tex"]
            results[tool].update(
                snapshot_mismatches=5,
                text_snapshot_included=True,
                after_repair_exit=0,
                changed_source_files=sum(fixed[p] != setup[p] for p in setup),
                condition_evaluated_by="owned exporter; scitexlintr checks its resulting manifest",
            )
        results[tool]["retained_inputs"] = {
            p.relative_to(root).as_posix(): sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*"))
            if p.is_file()
            and not any(
                part.startswith(".") or part == "build" for part in p.relative_to(root).parts
            )
        }
    versions = run(
        output,
        "reference-versions",
        [
            binaries["python"],
            "-c",
            "import json,importlib.metadata as m;"
            "print(json.dumps({n:m.version(n) for n in ['calkit-python','scitexlintr','dvc']}))",
        ],
    )
    evidence = {
        "checked_at": datetime.now(UTC).isoformat(),
        "platform": platform.platform(),
        "versions": json.loads(versions.stdout),
        "script_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "exporter_sha256": sha256(
            (REPOSITORY / "tools/reference_export.py").read_bytes()
        ).hexdigest(),
        "scenario": "Five numeric sites plus one comparison; Ours 84.1% -> 80.9%; Baseline 81.0%.",
        "results": results,
        "commands": commands,
        "limits": [
            "One developer-authored synthetic paper; not independent adoption evidence.",
            "CLI times exclude installation, configuration authoring, reading and confirmation.",
            "Reference tools use their own declared generated-value/template conventions.",
            "Calkit runs the exporter through DVC; scitexlintr uses an explicit exporter command.",
            "scitexlintr's text condition is authored in the exporter, not inferred by the linter.",
            "PaperDelta flags the invalid assertion and withholds related numeric writes.",
            "No model, participant, TeX compilation or figure behavior was measured in this run.",
            "No remote repositories or packages were published.",
        ],
    }
    (output / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"results": results, "evidence": str(output / "evidence.json")}, indent=2))


if __name__ == "__main__":
    main()
