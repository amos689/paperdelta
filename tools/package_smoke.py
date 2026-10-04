"""Run with a clean environment's Python after installing the built wheel."""

import argparse
import http.client
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
import threading
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
    assert importlib.util.find_spec("docx") is None, "Use a clean core-only environment"
    assert importlib.util.find_spec("pdfplumber") is None, "Use a clean core-only environment"
    scratch = repository / "build/package-smoke" / uuid.uuid4().hex
    shutil.copytree(
        repository / "examples/research-paper",
        scratch,
        ignore=lambda _, names: [name for name in names if name in {"build", ".paperdelta"}],
    )

    def command(*args, language="en"):
        return subprocess.run(
            [
                sys.executable,
                "-I",
                "-m",
                "paperdelta",
                "--lang",
                language,
                "-C",
                str(scratch),
                *args,
            ],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    before = command("check", "--format", "json", "--report", "build/review")
    assert before.returncode == 0, before.stderr
    chinese_before = command("check", "--format", "json", language="zh-CN")
    assert chinese_before.returncode == 0, chinese_before.stderr
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
    chinese_after = command(
        "check", "--format", "json", "--report", "build/changed-zh", language="zh-CN"
    )
    assert chinese_after.returncode == 1, chinese_after.stderr
    for english, chinese in ((before, chinese_before), (after, chinese_after)):
        left, right = json.loads(english.stdout), json.loads(chinese.stdout)
        left.pop("created_at")
        right.pop("created_at")
        assert left == right
    assert '<html lang="zh-CN"' in (scratch / "build/changed-zh/report.html").read_text("utf-8")
    for language in ("en", "zh-CN"):
        for kind in ("docx", "pdf"):
            result = command(
                "demo", "--document", kind, "--out", "missing-parser", language=language
            )
            assert result.returncode == 2 and "DOCUMENT_DEPENDENCY" in result.stderr
            assert not (scratch / "missing-parser").exists()
    chinese_optional = command("mcp", language="zh-CN")
    assert chinese_optional.returncode == 2 and "MCP_NOT_INSTALLED" in chinese_optional.stderr
    for language in ("en", "zh-CN"):
        demo = command(
            "demo", "--out", f"bundled-demo-{language}", "--format", "json", language=language
        )
        assert demo.returncode == 0, demo.stdout + demo.stderr
        demo_result = json.loads(demo.stdout)
        assert demo_result["check_exit_code"] == 1
        assert (scratch / demo_result["report"]).is_file()
    from paperdelta.storage import Project
    from paperdelta.studio_server import StudioServer

    with StudioServer(Project(scratch)) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            connection.request("GET", "/studio.js")
            response = connection.getresponse()
            assert response.status == 200 and b"draft-import" in response.read()
            connection.close()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            connection.request("GET", "/studio-review.js")
            response = connection.getresponse()
            assert response.status == 200 and b"recovery-rebuild" in response.read()
            connection.close()
            connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=10)
            connection.request(
                "POST",
                "/api",
                json.dumps({"action": "state", "language": "zh-CN"}),
                {
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + server.token,
                    "Origin": server.origin,
                },
            )
            response = connection.getresponse()
            state = json.loads(response.read())["state"]
            assert response.status == 200 and state["initialized"] and state["candidates"]
            connection.close()
        finally:
            server.shutdown()
            thread.join(timeout=5)
    runtime_files = [
        path
        for path in installed.parent.rglob("*")
        if path.is_file()
        and path.suffix in {".py", ".json", ".css", ".js", ".tex", ".yaml", ".csv", ".pdf", ".docx"}
    ]
    for path in runtime_files:
        relative = path.relative_to(installed.parent)
        assert path.read_bytes() == (repository / "src/paperdelta" / relative).read_bytes()
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
        "docx_installed": False,
        "optional_docx_error": "DOCUMENT_DEPENDENCY",
        "pdf_installed": False,
        "optional_pdf_error": "DOCUMENT_DEPENDENCY",
        "languages": ["en", "zh-CN"],
        "language_independent_stored_reports": True,
        "bundled_demo_without_extras": True,
        "installed_studio_http_and_assets_without_extras": True,
        "installed_sources_sha256": {
            path.relative_to(installed.parent).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in sorted(runtime_files)
        },
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
