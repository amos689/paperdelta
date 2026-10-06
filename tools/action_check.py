"""Entry point for the pinned composite action, never imported from a paper checkout."""

import json
import os
import re
import subprocess
import sys
import uuid
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def message(en, zh):
    return zh if os.environ.get("PAPERDELTA_ACTION_LANG") == "zh-CN" else en


def fail_output():
    if os.environ.get("GITHUB_OUTPUT"):
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8", newline="\n") as stream:
            stream.write("exit-code=2\n")


def main():
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True)
    temporary = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
    if sys.argv[1:] == ["--install"]:
        environment = temporary / ("paperdelta-action-" + uuid.uuid4().hex)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        venv.EnvBuilder(with_pip=True).create(environment)
        subprocess.run(
            [str(python), "-I", "-m", "pip", "install", str(ROOT) + "[docx,pdf]"],
            check=True,
            cwd=temporary,
        )
        (environment / "action-source.json").write_text(
            json.dumps({"source": str(ROOT)}), encoding="utf-8"
        )
        with Path(os.environ["GITHUB_ENV"]).open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(f"PAPERDELTA_ACTION_ENV={environment}\n")
        return 0
    environment = Path(os.environ["PAPERDELTA_ACTION_ENV"]).resolve(strict=True)
    if not environment.is_relative_to(temporary) or json.loads(
        (environment / "action-source.json").read_text("utf-8")
    ) != {"source": str(ROOT)}:
        raise RuntimeError(
            message(
                "The environment must belong to this selected action",
                "运行环境必须属于选定的 Action",
            )
        )
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if sys.argv[1:] or not python.is_file():
        raise RuntimeError(
            message("Install the trusted action before checking", "检查前必须安装可信的 Action")
        )
    values = {
        key: os.environ["PAPERDELTA_ACTION_" + key]
        for key in ("PROJECT", "BASE", "SNAPSHOT", "CONFIG", "REPORT", "LANG")
    }
    if any(re.search(r"[\x00-\x1f\x7f]", value) for value in values.values()):
        raise ValueError(
            message(
                "Action inputs cannot contain control characters", "Action 输入不能包含控制字符"
            )
        )
    if values["LANG"] not in {"en", "zh-CN"}:
        raise ValueError(
            message("Action language must be en or zh-CN", "Action 语言必须为 en 或 zh-CN")
        )
    project = (workspace / values["PROJECT"]).resolve(strict=True)
    if not project.is_relative_to(workspace):
        raise ValueError(
            message(
                "The paper checkout must stay inside the workflow workspace",
                "论文目录必须位于工作流工作区内",
            )
        )
    report = (project / values["REPORT"]).resolve()
    if not report.is_relative_to(project):
        raise ValueError(
            message("Reports must stay inside the paper checkout", "报告必须保存在论文目录内")
        )
    arguments = [
        str(python),
        "-I",
        "-X",
        "utf8",
        str(ROOT / "tools/ci_check.py"),
        "--project",
        str(project),
        "--base-commit",
        values["BASE"],
        "--snapshot",
        values["SNAPSHOT"],
        "--config",
        values["CONFIG"],
        "--report",
        report.relative_to(project).as_posix(),
        "--lang",
        values["LANG"],
    ]
    code = subprocess.run(arguments, cwd=temporary, check=False).returncode
    if code not in {0, 1, 2}:
        code = 2
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(f"exit-code={code}\nreport-path={report.relative_to(workspace).as_posix()}\n")
    return code


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        try:
            fail_output()
        except OSError:
            pass
        print(f"PaperDelta action: {error}", file=sys.stderr)
        raise SystemExit(2) from error
