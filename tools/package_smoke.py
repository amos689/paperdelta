"""Run with a clean environment's Python after installing the built wheel."""

import argparse
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import paperdelta


def main():
    repository = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="docs/evidence/package-smoke.json")
    args = parser.parse_args()
    target = (repository / args.out).resolve()
    assert target.is_relative_to(repository), "Keep evidence in this checkout"
    installed = Path(paperdelta.__file__).resolve()
    assert installed.is_relative_to(Path(sys.prefix).resolve()), "Must test an installed wheel"
    assert importlib.util.find_spec("mcp") is None, "Use a clean environment without the MCP extra"
    scratch = repository / "build/package-smoke" / uuid.uuid4().hex
    shutil.copytree(
        repository / "examples/research-paper",
        scratch,
        ignore=lambda _, names: [name for name in names if name in {"build", ".paperdelta"}],
    )

    def command(*args):
        return subprocess.run(
            [sys.executable, "-I", "-m", "paperdelta", "-C", str(scratch), *args],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    before = command("check", "--format", "json", "--report", "build/review")
    assert before.returncode == 0, before.stderr
    data = scratch / "results/metrics.csv"
    text = data.read_text(encoding="utf-8")
    for old, new in (("0.839", "0.807"), ("0.841", "0.809"), ("0.843", "0.811")):
        text = text.replace(old, new)
    data.write_text(text, encoding="utf-8")
    after = command("check", "--format", "json", "--report", "build/changed")
    assert after.returncode == 1, after.stderr
    report = json.loads(after.stdout)
    assert report["coverage"]["mismatch"] == 5
    assert "Record identity" in (scratch / "build/changed/report.html").read_text(encoding="utf-8")
    optional = command("mcp")
    assert optional.returncode == 2 and "MCP_NOT_INSTALLED" in optional.stderr
    result = {
        "checked_at": datetime.now(UTC).isoformat(),
        "python": platform.python_version(),
        "platform": platform.system(),
        "version": paperdelta.__version__,
        "installed_wheel_used": True,
        "mcp_installed": False,
        "core_check_exit": before.returncode,
        "data_only_change_exit": after.returncode,
        "mismatches": 5,
        "html_report_written": True,
        "optional_mcp_error": "MCP_NOT_INSTALLED",
        "installed_sources_sha256": {
            path.name: sha256(path.read_bytes()).hexdigest()
            for path in sorted(installed.parent.glob("*.py"))
        },
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
