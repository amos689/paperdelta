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


def run_logged(command, output, index, env, *, timeout=180):
    """Keep partial output and an explicit failure record even on a timeout."""
    started = time.monotonic()
    timed_out = False
    try:
        result = subprocess.run(
            command,
            cwd=output,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
        )
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as exc:
        # TimeoutExpired may contain bytes even when text=True was requested.
        def decoded(value):
            return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value

        stdout, stderr, code = decoded(exc.stdout) or "", decoded(exc.stderr) or "", 124
        stderr += f"\nTimed out after {timeout} seconds; this command was not retried.\n"
        timed_out = True
    log = (stdout + "\n" + stderr).replace(str(ROOT), "<checkout>")
    (output / f"command-{index:02d}.log").write_text(log, encoding="utf-8", newline="\n")
    return (
        {
            "exit_code": code,
            "timed_out": timed_out,
            "seconds": round(time.monotonic() - started, 3),
        },
        stdout,
        log,
    )


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
    receipt = {
        "status": "running",
        "tool": None,
        "host": platform.system(),
        "architecture": platform.machine(),
        "python": platform.python_version(),
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "runs": records,
    }

    def save():
        (output / "evidence.json").write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

    save()

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
        record, stdout, log = run_logged(command, output, len(records), env)
        records.append({"extras": extras, "arguments": arguments, **record})
        if record["exit_code"] != expected:
            receipt["status"] = "failed"
        save()
        assert record["exit_code"] == expected, log
        return stdout

    version = run(False, ["--version"]).strip()
    receipt["tool"] = version
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
    receipt["status"] = "passed"
    save()
    print(json.dumps({"status": "passed", "runs": len(records), "host": receipt["host"]}))


if __name__ == "__main__":
    main()
