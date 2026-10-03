"""Check maintained bilingual page inventory, reciprocal navigation and local links."""

import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")


def local_links(path):
    text = re.sub(r"```.*?```", "", path.read_text("utf-8"), flags=re.DOTALL)
    for match in LINK.finditer(text):
        target = match[1].split(' "', 1)[0].strip("<>")
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        yield (path.parent / unquote(parsed.path)).resolve()


def check():
    manifest = json.loads((ROOT / "docs/translations.json").read_text("utf-8"))
    registered = set(manifest["aliases"])
    for pair in manifest["pairs"]:
        assert set(pair) == {"en", "zh-CN"}, pair
        paths = {language: ROOT / name for language, name in pair.items()}
        for language, path in paths.items():
            name = path.relative_to(ROOT).as_posix()
            assert name not in registered, f"Duplicate documentation entry: {name}"
            registered.add(name)
            assert path.is_file(), f"Missing counterpart: {name}"
            counterpart = paths["zh-CN" if language == "en" else "en"]
            assert counterpart.resolve() in set(local_links(path)), f"Missing switch: {name}"
    actual = {p.relative_to(ROOT).as_posix() for p in ROOT.glob("*.md")}
    actual.update(
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "docs").rglob("*.md")
        if "evidence" not in p.relative_to(ROOT / "docs").parts
    )
    actual.update(
        p.relative_to(ROOT).as_posix()
        for p in (ROOT / "examples").rglob("README*.md")
        if not {"build", ".paperdelta"}.intersection(p.relative_to(ROOT).parts)
    )
    assert actual == registered, {
        "unpaired": sorted(actual - registered),
        "missing": sorted(registered - actual),
    }
    links = 0
    for name in sorted(registered):
        for target in local_links(ROOT / name):
            assert target.is_relative_to(ROOT), f"Link escapes checkout: {name}"
            assert target.exists(), f"Broken link: {name} -> {target.relative_to(ROOT)}"
            links += 1
    return {"pairs": len(manifest["pairs"]), "pages": len(registered), "local_links": links}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
