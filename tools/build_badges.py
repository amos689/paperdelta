"""Generate local README badges; use --check to detect stale project metadata."""

import argparse
import math
import re
import tomllib
import unicodedata
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def badge(label, value, color):
    def width(text):
        return (
            math.ceil(
                sum(11 if unicodedata.east_asian_width(c) in {"W", "F"} else 6.8 for c in text)
            )
            + 16
        )

    left, right = width(label), width(value)
    total = left + right
    title = escape(f"{label}: {value}", quote=True)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="22" '
        f'viewBox="0 0 {total} 22" role="img" aria-label="{title}">\n'
        f"  <title>{title}</title>\n"
        f'  <clipPath id="r"><rect width="{total}" height="22" rx="3"/></clipPath>\n'
        '  <g clip-path="url(#r)">\n'
        f'    <rect width="{total}" height="22" fill="#394d58"/>\n'
        f'    <rect x="{left}" width="{right}" height="22" fill="{color}"/>\n'
        "  </g>\n"
        '  <g fill="#fff" text-anchor="middle" '
        'font-family="Verdana, Geneva, DejaVu Sans, sans-serif" font-size="11">\n'
        f'    <text x="{left / 2:g}" y="15">{escape(label)}</text>\n'
        f'    <text x="{left + right / 2:g}" y="15">{escape(value)}</text>\n'
        "  </g>\n</svg>\n"
    )


def badge_files():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))["project"]
    python = project["requires-python"]
    assert re.fullmatch(r">=\d+\.\d+", python), "Review the Python badge for a new version range"
    pydantic = next(d for d in project["dependencies"] if d.startswith("pydantic>="))
    major = re.match(r"pydantic>=(\d+)\.", pydantic)[1]
    assert f"<{int(major) + 1}" in pydantic, "Review the Pydantic badge for a new version range"
    assert project["license"] == "MIT", "Review the license badge if licensing changes"
    definitions = {
        "release.svg": (
            "Alpha" if "a" in project["version"] else "release",
            project["version"],
            "#287e79",
        ),
        "python.svg": ("Python", python[2:] + "+", "#346c97"),
        "pydantic.svg": ("Pydantic", major + ".x", "#a83d65"),
        "license.en.svg": ("license", "MIT", "#526b73"),
        "license.zh-CN.svg": ("许可", "MIT", "#526b73"),
        "latex.en.svg": ("LaTeX", "static input", "#287e79"),
        "latex.zh-CN.svg": ("LaTeX", "静态输入", "#287e79"),
        "mcp.en.svg": ("MCP", "read-only", "#625778"),
        "mcp.zh-CN.svg": ("MCP", "只读", "#625778"),
        "platforms.en.svg": ("platforms", "Windows / Linux / macOS", "#526b73"),
        "platforms.zh-CN.svg": ("平台", "Windows / Linux / macOS", "#526b73"),
        "languages.en.svg": ("languages", "EN / 简体中文", "#287e79"),
        "languages.zh-CN.svg": ("语言", "English / 简体中文", "#287e79"),
    }
    return {"docs/assets/badges/" + name: badge(*values) for name, values in definitions.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = badge_files()
    for name, contents in files.items():
        target = ROOT / name
        if args.check:
            assert target.is_file() and target.read_text("utf-8") == contents, (
                f"Stale badge: {name}; run python tools/build_badges.py"
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents, encoding="utf-8", newline="\n")
    print(f"{'Verified' if args.check else 'Generated'} {len(files)} local README badges.")


if __name__ == "__main__":
    main()
