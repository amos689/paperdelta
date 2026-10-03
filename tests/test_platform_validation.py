"""Keep native-host evidence honest when macOS denies an optional sysctl probe."""

import importlib.util
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("code", "stdout", "stderr", "expected"),
    [
        (0, "0\n", "", False),
        (0, "1\n", "", True),
        (0, "", "", None),
        (1, "", "Operation not permitted\n", None),
    ],
)
def test_rosetta_probe_preserves_unknown(monkeypatch, code, stdout, stderr, expected):
    path = Path(__file__).resolve().parents[1] / "tools/validate_platform.py"
    spec = importlib.util.spec_from_file_location("validate_platform", path)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    monkeypatch.setattr(validator.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        validator.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, code, stdout, stderr),
    )
    info = validator.host_info()
    assert info["rosetta_translated"] is expected
    assert info["rosetta_probe"] == {
        "exit_code": code,
        "stdout": stdout.strip(),
        "stderr": stderr.strip(),
    }
