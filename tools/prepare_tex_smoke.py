"""Prepare original and patched, self-contained versions of the owned TeX fixture.

Only literal includes from our small original fixture are inlined. This does not
claim to compile third-party templates or validate figure generation.
"""

import argparse
import re
from pathlib import Path
from shutil import copytree

from paperdelta.analysis import check_project
from paperdelta.patches import apply_patch, create_patch
from paperdelta.storage import Project, json_text, sha256


def flatten(project, file):
    raw = project.read(file).decode("utf-8")

    def include(match):
        target = (Path(file).parent / (match[1] + ".tex")).as_posix()
        return flatten(project, target)

    return re.sub(r"\\input\{([A-Za-z]+)\}", include, raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="build/tex-smoke")
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    output = Project(repository).path(args.out)
    output.mkdir(parents=True, exist_ok=False)
    root = output / "project"
    copytree(
        repository / "examples/research-paper",
        root,
        ignore=lambda _, names: [name for name in names if name in {".paperdelta", "build"}],
    )
    project = Project(root)
    before = flatten(project, "paper/main.tex")
    (output / "before.tex").write_bytes(before.encode("utf-8"))
    path = "results/metrics.csv"
    text, _ = project.text(path)
    lines = text.splitlines()
    for index, value in enumerate(["0.843", "0.845", "0.847"], start=1):
        cells = lines[index].split(",")
        assert cells[1] == "Ours" and cells[3] == str(index)
        cells[-1] = value
        lines[index] = ",".join(cells)
    project.write(path, ("\n".join(lines) + "\n").encode())
    patch = create_patch(project, check_project(root))
    applied = apply_patch(project, patch)
    assert applied["report"]["exit_code"] == 0 and len(patch["changes"]) == 4
    after = flatten(project, "paper/main.tex")
    assert before != after
    (output / "after.tex").write_bytes(after.encode("utf-8"))
    (output / "inputs.json").write_text(
        json_text(
            {
                "before": sha256(before.encode()),
                "after": sha256(after.encode()),
                "patch_changes": len(patch["changes"]),
                "check_exit_code": applied["report"]["exit_code"],
                "compile_verified": False,
                "scope": (
                    "Compile before.tex and after.tex separately; flattened original fixture only."
                ),
            }
        ),
        encoding="utf-8",
    )
    print(output)


if __name__ == "__main__":
    main()
