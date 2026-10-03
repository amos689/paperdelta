from pathlib import Path
from shutil import copytree

import pytest


@pytest.fixture
def project(tmp_path):
    source = Path(__file__).resolve().parents[1] / "examples/research-paper"
    target = tmp_path / "论文 project"
    copytree(
        source, target, ignore=lambda _, names: [n for n in names if n in {"build", ".paperdelta"}]
    )
    return target


@pytest.fixture
def change_results():
    def change(root, old=("0.839", "0.841", "0.843"), new=("0.807", "0.809", "0.811")):
        path = root / "results/metrics.csv"
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, (before, after) in enumerate(zip(old, new, strict=True), start=1):
            assert lines[index].endswith(before)
            lines[index] = lines[index][: -len(before)] + after
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return change
