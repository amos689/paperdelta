"""Validate a built wheel in two fresh local environments and retain host evidence.

This installs dependencies from the configured package index. It does not change
system Python. --require-system Darwin makes a macOS run refuse another host.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import venv
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def host_info():
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "macos_version": platform.mac_ver()[0] or None,
        "rosetta_translated": None,
    }
    if info["system"] == "Darwin":
        probe = subprocess.run(
            ["/usr/sbin/sysctl", "-in", "sysctl.proc_translated"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        # Keep denied/absent probes distinct from a confirmed native process.
        info["rosetta_probe"] = {
            "exit_code": probe.returncode,
            "stdout": probe.stdout.strip(),
            "stderr": probe.stderr.strip(),
        }
        if probe.returncode == 0 and probe.stdout.strip() in {"0", "1"}:
            info["rosetta_translated"] = probe.stdout.strip() == "1"
    return info


def main():
    # This bootstrap may be invoked before installation using macOS system Python.
    if sys.version_info < (3, 11):  # noqa: UP036
        print("Python 3.11 or newer is required. Install a current Python from python.org.")
        return 2
    import tomllib

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--require-system", choices=["Darwin", "Linux", "Windows"])
    parser.add_argument("--expected-arch", choices=["arm64", "x86_64", "AMD64"])
    args = parser.parse_args()
    host = host_info()
    if args.require_system and host["system"] != args.require_system:
        parser.error(f"Requires {args.require_system}; actual host is {host['system']}")
    if args.expected_arch and host["machine"] != args.expected_arch:
        parser.error(f"Expected {args.expected_arch}; actual interpreter is {host['machine']}")
    if host["rosetta_translated"]:
        parser.error("Use a native Python interpreter; this process is running under Rosetta")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    filename = f"paperdelta-{project['version']}-py3-none-any.whl"
    wheel = (args.wheel or ROOT / "install" / filename).resolve()
    if not wheel.is_relative_to(ROOT) or not wheel.is_file() or wheel.name != filename:
        parser.error("Use the matching wheel inside this checkout or the transfer ZIP's install/")
    output = (ROOT / args.out).resolve()
    if not output.is_relative_to(ROOT) or output.exists():
        parser.error("Choose a new output directory inside this checkout")
    output.mkdir(parents=True)
    env = {**os.environ, "PYTHONUTF8": "1", "PIP_DISABLE_PIP_VERSION_CHECK": "1"}
    env.pop("PYTHONPATH", None)
    evidence = {
        "started_at": datetime.now(UTC).isoformat(),
        "host": host,
        "wheel": {"name": wheel.name, "sha256": sha256(wheel.read_bytes()).hexdigest()},
        "commands": [],
        "status": "running",
        "scope": "Actual installed-wheel execution on the recorded host, not independent users.",
    }

    def save():
        (output / "evidence.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )

    def command(label, arguments, timeout=600):
        args_text = [str(arg) for arg in arguments]
        print(f"Running {label}", flush=True)
        started = time.monotonic()
        with (output / f"{label}.log").open("w", encoding="utf-8") as log:
            try:
                result = subprocess.run(
                    args_text,
                    cwd=ROOT,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    check=False,
                )
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
                log.write(f"\nTimed out after {timeout} seconds.\n")
        evidence["commands"].append(
            {
                "step": label,
                "args": [arg.replace(str(ROOT), "<checkout>") for arg in args_text],
                "exit_code": code,
                "seconds": round(time.monotonic() - started, 3),
            }
        )
        save()
        if code:
            raise RuntimeError(f"{label} failed with exit {code}; see {label}.log")

    save()
    try:
        interpreters = {}
        for name in ("core", "full"):
            directory = output / f"venv-{name}"
            venv.EnvBuilder(with_pip=True).create(directory)
            python = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            interpreters[name] = python
            target = str(wheel) + ("[dev,mcp]" if name == "full" else "")
            command(f"install-{name}", [python, "-I", "-m", "pip", "install", target])
            if name == "core":
                command(
                    "core-smoke",
                    [
                        python,
                        "-X",
                        "utf8",
                        "tools/package_smoke.py",
                        "--out",
                        (output / "core-smoke.json").relative_to(ROOT),
                    ],
                )
        python = interpreters["full"]
        command("lint", [python, "-m", "ruff", "check", "src", "tests", "tools"])
        command("format", [python, "-m", "ruff", "format", "--check", "src", "tests", "tools"])
        command(
            "tests",
            [
                python,
                "-X",
                "utf8",
                "tools/validate_python_matrix.py",
                "--python",
                python,
                "--out",
                (output / "suite").relative_to(ROOT),
            ],
        )
        suite = json.loads((output / "suite/evidence.json").read_text("utf-8"))
        evidence["suite"] = suite
        # Native Mac/Linux claims require the POSIX filesystem/PTY cases to run.
        if host["system"] in {"Darwin", "Linux"}:
            if any(result.get("tests", {}).get("skipped", 1) for result in suite["results"]):
                raise RuntimeError("Native POSIX acceptance requires zero skipped tests")
        for name, script in (("examples", "validate_examples.py"), ("ci-demo", "demo_ci.py")):
            command(
                name,
                [
                    python,
                    "-X",
                    "utf8",
                    f"tools/{script}",
                    "--out",
                    (output / name).relative_to(ROOT),
                ],
            )
        evidence["status"] = "passed"
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        evidence["status"] = "failed"
        evidence["error"] = f"{type(error).__name__}: {error}"
    finally:
        evidence["finished_at"] = datetime.now(UTC).isoformat()
        save()
    print(
        json.dumps(
            {
                "status": evidence["status"],
                "host": host,
                "evidence": (output / "evidence.json").relative_to(ROOT).as_posix(),
                "error": evidence.get("error"),
            },
            indent=2,
        )
    )
    return int(evidence["status"] != "passed")


if __name__ == "__main__":
    raise SystemExit(main())
