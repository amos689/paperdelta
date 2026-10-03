import re
import subprocess
import sys
from pathlib import Path

import pytest

from paperdelta.storage import Project, parse_json


@pytest.mark.parametrize("language", ["en", "zh-CN"])
def test_published_quickstart_inputs_run_through_real_cli(tmp_path, language):
    name = "docs/quickstart.md" if language == "en" else "docs/zh-CN/quickstart.md"
    text = (Path(__file__).resolve().parents[1] / name).read_text(encoding="utf-8")
    store = Project(tmp_path)
    for fence_language, path in (
        ("tex", "paper/main.tex"),
        ("csv", "results/metrics.csv"),
        ("json", "mapping-input.json"),
    ):
        content = re.findall(r"```" + fence_language + r"\n(.*?)\n```", text, flags=re.DOTALL)[0]
        store.write(path, (content + "\n").encode("utf-8"))

    def command(*arguments):
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "paperdelta",
                "--lang",
                language,
                "-C",
                str(tmp_path),
                *arguments,
            ],
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        return result.stdout

    command("init", "--paper", "paper/main.tex", "--data", "results/metrics.csv")
    command("propose", "--input", "mapping-input.json", "--out", "proposal.json")
    preview = parse_json(command("bind", "--proposal", "proposal.json"))
    assert preview["status"] == "proposed" and preview["preview"]["coverage"]["pass"] == 1
    command("bind", "--proposal", "proposal.json", "--accept", "occurrences:abstract_accuracy")
    checked = parse_json(command("check", "--format", "json"))
    assert checked["metrics"]["ours"]["value"] == "0.841"
    assert checked["coverage"]["confirmed"] == 1
    schema = parse_json(command("schema", "proposal-input"))
    assert set(schema["required"]) == {"additions", "rationale"}
