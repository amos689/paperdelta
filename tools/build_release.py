"""Build the MIT Python distributions and a separate licensed evaluation bundle."""

import argparse
import json
import os
import subprocess
import sys
import tomllib
import zipfile
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    output = (ROOT / args.out).resolve()
    assert output.is_relative_to(ROOT) and not output.exists(), "Choose a new local directory"
    output.mkdir(parents=True)
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    env = {**os.environ, "PYTHONUTF8": "1"}
    built = subprocess.run(
        [sys.executable, "-X", "utf8", "-m", "build", "--outdir", str(output)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    log = (built.stdout + built.stderr).replace(str(ROOT), "<checkout>")
    (output / "build.log").write_text(log, encoding="utf-8")
    if built.returncode:
        print(log[-5000:])
        return built.returncode
    files = {
        p.relative_to(ROOT).as_posix() for p in (ROOT / "tests/corpus").rglob("*") if p.is_file()
    }
    files.update(
        p.relative_to(ROOT).as_posix() for p in (ROOT / "docs/evidence").glob("corpus*.json")
    )
    files.update(
        p.relative_to(ROOT).as_posix()
        for study in ("native-v1", "native-v2", "native-v3", "mapping-v4", "mapping-v5")
        for p in (ROOT / "validation" / study).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    )
    files.update(
        {
            "LICENSE",
            "THIRD_PARTY_NOTICES.md",
            "THIRD_PARTY_NOTICES.zh-CN.md",
            "docs/evaluation.md",
            "docs/zh-CN/evaluation.md",
            "docs/v1.1.md",
            "docs/zh-CN/v1.1.md",
            "docs/v1.3.md",
            "docs/zh-CN/v1.3.md",
            "docs/v1.4.md",
            "docs/zh-CN/v1.4.md",
            "docs/v1.8.md",
            "docs/zh-CN/v1.8.md",
        }
    )
    manifest = {
        "bundle_schema_version": 1,
        "paperdelta_version": project["version"],
        "active_study": json.loads((ROOT / "tests/corpus/active-study.json").read_text("utf-8")),
        "license_expression": "MIT AND CC-BY-4.0 AND CC-BY-SA-4.0",
        "meaning": "An aggregate of separately licensed files; not relicensing the original code.",
        "files": {
            name: {
                "sha256": sha256((ROOT / name).read_bytes()).hexdigest(),
                "bytes": (ROOT / name).stat().st_size,
            }
            for name in sorted(files)
        },
    }
    target = output / f"paperdelta-evaluation-{project['version']}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(files):
            bundle.write(ROOT / name, name)
        bundle.writestr("evaluation-bundle.json", json.dumps(manifest, indent=2) + "\n")
        bundle.writestr(
            "EVALUATION_README.md",
            "# PaperDelta evaluation materials\n\n[简体中文](EVALUATION_README.zh-CN.md)\n\n"
            "Read THIRD_PARTY_NOTICES.md before reusing paper sources. Each work retains "
            "its license and author notices; PaperDelta's MIT license covers its original code.\n\n"
            "The Python wheel and source distribution exclude this corpus. To reproduce "
            "the evaluation, unpack this bundle at the root of the matching PaperDelta "
            f"{project['version']} source checkout, preserving the directories. "
            "Run `python tools/replay_study.py corpus-a2 --out build/corpus-replay`. "
            "Use a fresh output directory. Do not replace the recorded first held-out results.\n\n"
            "The preserved a2 run is a regression on already observed papers. "
            "tests/corpus/active-study.json identifies its lock and the preserved "
            "original implementation; see tests/corpus/README.md for historical replay.\n\n"
            "The protocol lock checks the exact core, evaluator and input identities. "
            "The papers are paired with controlled synthetic evidence, not reproduced "
            "original experiments. See docs/evaluation.md for failures and limits.\n\n"
            "Native Word/PDF study: read validation/native-v1/README.md and run "
            "`python tools/replay_native.py --out build/native-replay` with the documented "
            "dependencies. The frozen implementation and first held-out failures are retained; "
            "replays are regressions on already seen inputs.\n\n"
            "The new 1.3 study is separate: validation/native-v2/README.md, with "
            "`python tools/replay_native_v2.py --out build/native-v2-replay`. "
            "It preserves twenty original files, independently selected positions, "
            "the frozen implementation, baseline, development history "
            "and first held-out results.\n\n"
            "The separate 1.8 native-v3 study retains twelve new licensed originals, "
            "whole-value gold, the public 1.7 baseline and all four outcomes. Read "
            "validation/native-v3/README.md for the frozen replay and limitations.\n",
        )
        bundle.writestr(
            "EVALUATION_README.zh-CN.md",
            "# PaperDelta 评测材料\n\n[English](EVALUATION_README.md)\n\n"
            "复用论文前阅读 THIRD_PARTY_NOTICES.zh-CN.md。每篇保留原许可和作者声明，"
            "PaperDelta 的 MIT 许可只覆盖原创代码。Python wheel/源码包排除此论文语料。\n\n"
            f"将本包按原路径解压到匹配的 PaperDelta {project['version']} 源码根目录。运行 "
            "`python tools/replay_study.py corpus-a2 --out build/corpus-replay`，使用新输出目录。"
            "重放通过归档实现验证原协议，保留首次留出失败，不把已见论文称作新留出样本。\n\n"
            "tests/corpus/active-study.json 标识保存的 a2 协议及更早原实现。锁核验源码、"
            "评测器和输入身份。论文配的是合成证据，不是复现原实验。"
            "失败及限制见 docs/zh-CN/evaluation.md；各发行版验收另行记录。\n\n"
            "原生 Word/PDF 试验见 validation/native-v1/README.zh-CN.md。按文档安装依赖后运行 "
            "`python tools/replay_native.py --out build/native-replay`。"
            "冻结实现和首次留出失败均保留，"
            "重放属于已见输入的回归验证。\n\n"
            "1.3 的新试验独立保存在 validation/native-v2/README.zh-CN.md，运行 "
            "`python tools/replay_native_v2.py --out build/native-v2-replay` 重放。"
            "保留二十份原文件、独立定位、冻结实现、基线、开发历史和首次留出结果。\n\n"
            "1.8 的 native-v3 试验独立保留十二份新许可原件、完整数值标注、公开 1.7 基线"
            "及四类结果。冻结重放与限制见 validation/native-v3/README.zh-CN.md。\n",
        )
    print(
        json.dumps(
            {
                "artifacts": [p.relative_to(ROOT).as_posix() for p in sorted(output.iterdir())],
                "evaluation_files": len(files),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
