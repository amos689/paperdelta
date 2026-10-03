"""Reproduce the parser choice on small, original LaTeX scenarios."""

from __future__ import annotations

import json
import platform
import time
from importlib.metadata import version
from pathlib import Path

from TexSoup import TexSoup

from paperdelta.latex import PaperIndex, TexDocument
from paperdelta.models import Anchor, Paper
from paperdelta.storage import Project


def main() -> None:
    cases = {
        "plain": ("The result is 84.1 percent.\n", Anchor(prefix="is ", suffix=" percent."), {}),
        "unicode_crlf": (
            "\ufeff实验结果：84.1\\%\r\n",
            Anchor(prefix="实验结果：", suffix=r"\%"),
            {},
        ),
        "custom_macro": (
            r"Result: \score{84.1}.",
            Anchor(prefix=r"\score{", suffix="}"),
            {"score": 1},
        ),
        "nested_format": (
            r"Result: \textbf{\emph{84.1}}.",
            Anchor(prefix=r"\emph{", suffix="}"),
            {},
        ),
    }
    results = []
    for name, (source, anchor, macros) in cases.items():
        started = time.perf_counter()
        document = TexDocument("case.tex", source.encode("utf-8"), macros)
        span = document.locate(anchor)
        elapsed = time.perf_counter() - started
        byte_roundtrip = document.raw[span.byte_start : span.byte_end].decode("utf-8")
        soup = TexSoup(source)
        positioned = [
            {"text": str(item), "position": getattr(item, "position", None)}
            for item in soup.contents
        ]
        results.append(
            {
                "case": name,
                "pylatexenc_target": span.text,
                "byte_roundtrip": byte_roundtrip == span.text == "84.1",
                "seconds": elapsed,
                "texsoup_top_level": positioned,
            }
        )
        assert byte_roundtrip == span.text == "84.1"
    root = Path(__file__).resolve().parents[1]
    paper = PaperIndex(
        Project(root / "examples/research-paper"),
        Paper(
            entry="paper/main.tex",
            macros={"score": 1},
        ),
    )
    output = {
        "python": platform.python_version(),
        "versions": {name: version(name) for name in ["pylatexenc", "TexSoup"]},
        "cases": results,
        "included_files": list(paper.documents),
        "candidate_values": {
            name: [span.text for span in doc.numbers()] for name, doc in paper.documents.items()
        },
        "selection": "pylatexenc: typed node spans and explicit macro specifications",
        "limitations": (
            "Small authored cases; not a real-paper coverage benchmark. "
            "Both parsers parsed all four cases."
        ),
    }
    target = root / "docs/evidence/parser-spike.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
