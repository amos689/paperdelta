"""Test already installed project-local Python environments; do not install anything.

Pass --python repeatedly for independent environments with .[dev,mcp] installed.
Each run preserves stdout, stderr, JUnit and imported package/source identities.
"""

import argparse
import json
import platform
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSPECT = """
import json, sys, platform
from pathlib import Path
from importlib.metadata import version
import paperdelta
path = Path(paperdelta.__file__).resolve()
assert path.is_relative_to(Path(sys.prefix).resolve()), "Expected a noneditable installed package"
print(json.dumps({
    "python": platform.python_version(),
    "platform": platform.platform(),
    "implementation": platform.python_implementation(),
    "installed_package": True,
    "versions": {n: version(n) for n in [
        "paperdelta", "pydantic", "PyYAML", "pylatexenc", "mcp", "pytest"
    ]},
    "environment_path": str(Path(sys.prefix).resolve()),
    "package_path": str(path.parent)
}))
"""


def run_suite(command, timeout):
    try:
        return subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        # communicate() can return bytes on timeout even in text mode. Keep the
        # partial diagnostics and a failing receipt instead of losing both.
        def decoded(value):
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return value or ""

        return subprocess.CompletedProcess(
            command,
            124,
            decoded(exc.stdout),
            decoded(exc.stderr) + f"\nFull test suite timed out after {timeout} seconds.\n",
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", action="append", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--timeout-seconds", type=int, default=480)
    args = parser.parse_args()
    if not 1 <= args.timeout_seconds <= 1800:
        parser.error("--timeout-seconds must be between 1 and 1800")
    out = (ROOT / args.out).resolve()
    assert out.is_relative_to(ROOT) and not out.exists(), "Choose a new local output directory"
    out.mkdir(parents=True)
    records = []
    for executable in args.python:
        # POSIX venv executables symlink to the base Python: preserve the invoked path.
        executable = Path(executable).absolute()
        assert executable.parent.resolve().is_relative_to(ROOT), "Use a project-local environment"
        inspected = subprocess.run(
            [str(executable), "-I", "-X", "utf8", "-c", INSPECT],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            check=True,
        )
        record = json.loads(inspected.stdout)
        environment = Path(record.pop("environment_path"))
        assert environment.is_relative_to(ROOT), "Expected a project-local virtual environment"
        package = Path(record.pop("package_path"))
        sources = {}
        source_root = ROOT / "src/paperdelta"
        for original in sorted(source_root.rglob("*")):
            if not original.is_file() or original.suffix not in {".py", ".json", ".css", ".js"}:
                continue
            raw = original.read_bytes()
            relative = original.relative_to(source_root)
            assert (package / relative).read_bytes() == raw
            sources[relative.as_posix()] = sha256(raw).hexdigest()
        record["installed_sources_sha256"] = sources
        case = out / record["python"]
        case.mkdir()
        junit = case / "junit.xml"
        command = [
            str(executable),
            "-X",
            "utf8",
            "tools/run_tests.py",
            "-q",
            "--junitxml",
            str(junit),
        ]
        print(f"Python {record['python']}: full installed-package suite", flush=True)
        completed = run_suite(command, args.timeout_seconds)
        stdout = completed.stdout.replace(str(ROOT), "<checkout>")
        stderr = completed.stderr.replace(str(ROOT), "<checkout>")
        (case / "stdout.log").write_text(stdout, encoding="utf-8")
        (case / "stderr.log").write_text(stderr, encoding="utf-8")
        print(stdout[-900:], flush=True)
        record["exit_code"] = completed.returncode
        record["suite_timeout_seconds"] = args.timeout_seconds
        record["junit"] = junit.relative_to(ROOT).as_posix()
        if junit.exists():
            suites = ET.parse(junit).getroot().findall(".//testsuite")
            record["tests"] = {
                key: sum(int(s.get(key, "0")) for s in suites)
                for key in ("tests", "failures", "errors", "skipped")
            }
            record["seconds"] = sum(float(s.get("time", "0")) for s in suites)
        records.append(record)
        evidence = {
            "checked_at": datetime.now(UTC).isoformat(),
            "host": platform.platform(),
            "results": records,
            "system": platform.system(),
            "libc": list(platform.libc_ver()),
            "scope": (
                "Local installed-package runs on the recorded host; "
                "not remote CI or usability evidence."
            ),
        }
        (out / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return int(any(r["exit_code"] != 0 for r in records))


if __name__ == "__main__":
    raise SystemExit(main())
