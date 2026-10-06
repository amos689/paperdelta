"""Run the exact wheel through isolated uvx environments on the recorded host."""

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]["version"]
    default_wheel = ROOT / "build/release-candidate" / f"paperdelta-{version}-py3-none-any.whl"
    wheel, output = (args.wheel or default_wheel).resolve(), (ROOT / args.out).resolve()
    assert wheel.is_relative_to(ROOT) and wheel.is_file()
    assert output.is_relative_to(ROOT / "build") and not output.exists()
    output.mkdir(parents=True)
    uvx = shutil.which("uvx")
    assert uvx, "Install uv before running this optional isolated-tool validation"
    env = {**os.environ, "UV_CACHE_DIR": str(output / "cache"), "PYTHONUTF8": "1"}
    env.pop("PYTHONPATH", None)
    records = []

    def run(extras, arguments, expected=0):
        requirement = ("paperdelta[docx,pdf] @ " if extras else "paperdelta @ ") + wheel.as_uri()
        command = [
            uvx,
            "--isolated",
            "--python",
            sys.executable,
            "--from",
            requirement,
            "paperdelta",
            *arguments,
        ]
        start = time.monotonic()
        result = subprocess.run(
            command,
            cwd=output,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
        )
        index = len(records)
        log = (result.stdout + "\n" + result.stderr).replace(str(ROOT), "<checkout>")
        (output / f"command-{index:02d}.log").write_text(log, "utf-8")
        records.append(
            {
                "extras": extras,
                "arguments": arguments,
                "exit_code": result.returncode,
                "seconds": round(time.monotonic() - start, 3),
            }
        )
        assert result.returncode == expected, log
        return result.stdout

    version = run(False, ["--version"]).strip()
    for language in ("en", "zh-CN"):
        for kind in ("latex", "markdown", "quarto", "docx", "pdf"):
            name = f"{kind}-{language}"
            args = [
                "--lang",
                language,
                "demo",
                "--document",
                kind,
                "--out",
                name,
                "--format",
                "json",
            ]
            run(kind in {"docx", "pdf"}, args)
            report = json.loads((output / name / "review/report.json").read_text("utf-8"))
            assert report["coverage"]["mismatch"] > 0
        missing = json.loads(
            run(
                False,
                ["--lang", language, "-C", f"pdf-{language}", "scan", "--format", "json"],
                expected=2,
            )
        )
        assert "DOCUMENT_DEPENDENCY" in json.dumps(missing)
        assert "pdf" in json.dumps(missing)
    receipt = {
        "status": "passed",
        "tool": version,
        "host": platform.system(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "runs": records,
    }
    (output / "evidence.json").write_text(json.dumps(receipt, indent=2) + "\n", "utf-8")
    print(json.dumps({"status": "passed", "runs": len(records), "host": receipt["host"]}))


if __name__ == "__main__":
    main()
