"""Conservative LaTeX source indexing with byte-exact, unique anchors."""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from pylatexenc.latexwalker import (
    LatexCommentNode,
    LatexEnvironmentNode,
    LatexGroupNode,
    LatexMacroNode,
    LatexWalker,
    LatexWalkerParseError,
    get_default_latex_context_db,
)
from pylatexenc.macrospec import MacroSpec

from paperdelta.errors import PaperDeltaError, error_message
from paperdelta.i18n import msg
from paperdelta.metrics import NUMBER_PATTERN
from paperdelta.models import Anchor, Paper
from paperdelta.storage import Project, sha256

IGNORED_MACROS = {
    "label",
    "ref",
    "eqref",
    "pageref",
    "autoref",
    "cref",
    "Cref",
    "cite",
    "citep",
    "citet",
    "citealp",
    "citealt",
    "citeauthor",
    "citeyear",
    "citeyearpar",
    "bibliography",
    "bibliographystyle",
    "includegraphics",
    "documentclass",
    "usepackage",
    "newcommand",
    "renewcommand",
    "providecommand",
    "DeclareRobustCommand",
    "def",
    "let",
    "hspace",
    "vspace",
    "rule",
    "setlength",
    "url",
    "input",
    "include",
    "verb",
    "lstinline",
}
IGNORED_ENVIRONMENTS = {"verbatim", "Verbatim", "lstlisting", "minted", "comment"}
LAYOUT_MACROS = {
    "toprule",
    "midrule",
    "bottomrule",
    "hline",
    "cline",
    "cmidrule",
    "addlinespace",
    "centering",
    "maketitle",
    "tableofcontents",
    "appendix",
    "noindent",
    "small",
    "scriptsize",
    "footnotesize",
    "normalsize",
    "hfill",
    "vfill",
    "quad",
    "qquad",
    "rowcolor",
    "cellcolor",
    "%",
    "&",
    "_",
    "#",
    "$",
    "{",
    "}",
    " ",
    "!",
    ",",
    ";",
    ":",
    "/",
    "\\",
}
STRUCTURAL_MACROS = {"def", "let", "catcode", "csname", "expandafter", "directlua", "scantokens"}


@dataclass(frozen=True)
class Span:
    file: str
    start: int
    end: int
    byte_start: int
    byte_end: int
    line: int
    column: int
    text: str

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "start": self.start,
            "end": self.end,
            "byte_start": self.byte_start,
            "byte_end": self.byte_end,
            "line": self.line,
            "column": self.column,
            "text": self.text,
        }


class TexDocument:
    percent_token = r"\%"

    def __init__(self, file: str, raw: bytes, macros: dict[str, int] | None = None):
        self.file = file
        self.raw = raw
        self.hash = sha256(raw)
        try:
            # Keep the BOM in the position map; never normalize line endings.
            self.text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PaperDeltaError("ENCODING", msg("error.ENCODING", file=file)) from exc
        self.byte_offsets = [0]
        for char in self.text:
            self.byte_offsets.append(self.byte_offsets[-1] + len(char.encode("utf-8")))
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", self.text)]
        self.blocked: list[tuple[int, int, str]] = []
        self.issues: list[dict] = []
        self.includes: list[tuple[str, int]] = []
        self.graphics: list[str] = []
        self.priority_regions: list[tuple[int, int, str]] = []
        self.table_regions: list[tuple[int, int]] = []
        self.context = get_default_latex_context_db()
        self.context.add_context_category(
            "paperdelta-standard",
            macros=[MacroSpec("caption", "[{"), MacroSpec("captionof", "{{")],
            prepend=True,
        )
        self.explicit_macros = macros or {}
        if macros:
            self.context.add_context_category(
                "paperdelta",
                macros=[MacroSpec(name, "{" * count) for name, count in macros.items()],
                prepend=True,
            )
        try:
            nodes, _, _ = LatexWalker(
                self.text,
                latex_context=self.context,
                tolerant_parsing=False,
            ).get_latex_nodes()
            document_nodes = [
                node
                for node in nodes
                if isinstance(node, LatexEnvironmentNode) and node.environmentname == "document"
            ]
            if document_nodes:
                document = document_nodes[0]
                children = document.nodelist or []
                body_start = children[0].pos if children else document.pos
                body_end = children[-1].pos + children[-1].len if children else body_start
                self.blocked.extend(
                    [(0, body_start, "preamble"), (body_end, len(self.text), "trailer")]
                )
                self._walk(children)
            else:
                self._walk(nodes)
        except (LatexWalkerParseError, ValueError, RecursionError) as exc:
            self.blocked.append((0, len(self.text), "parse-error"))
            self.issues.append({"code": "LATEX_PARSE", "file": file, "message": error_message(exc)})

    def _walk(self, nodes: list) -> None:
        for index, node in enumerate(nodes):
            start, end = node.pos, node.pos + node.len
            if isinstance(node, LatexCommentNode):
                self.blocked.append((start, end, "comment"))
                continue
            if (
                isinstance(node, LatexEnvironmentNode)
                and node.environmentname in IGNORED_ENVIRONMENTS
            ):
                self.blocked.append((start, end, "literal-environment"))
                continue
            if isinstance(node, LatexEnvironmentNode):
                if node.environmentname in {"tabular", "tabular*", "longtable"} and node.nodelist:
                    self.table_regions.append(
                        (node.nodelist[0].pos, node.nodelist[-1].pos + node.nodelist[-1].len)
                    )
                if node.environmentname == "abstract":
                    self.priority_regions.append((start, end, "abstract"))
                elif node.environmentname in {
                    "table",
                    "table*",
                    "tabular",
                    "tabular*",
                    "longtable",
                }:
                    self.priority_regions.append((start, end, "table"))
            if isinstance(node, LatexMacroNode):
                name = node.macroname
                if name.startswith("if") or name in STRUCTURAL_MACROS | {
                    "else",
                    "fi",
                    "loop",
                    "repeat",
                }:
                    # Static source inspection cannot know which content this TeX renders.
                    self.blocked.append((0, len(self.text), "dynamic-tex"))
                    self.issues.append(
                        {
                            "code": "DYNAMIC_TEX",
                            "file": self.file,
                            "message": msg("notice.latex", name=name),
                        }
                    )
                    continue
                if name in ("input", "include", "includegraphics"):
                    args = [arg for arg in (node.nodeargd.argnlist if node.nodeargd else []) if arg]
                    if args:
                        argument = args[-1]
                        target = self.text[argument.pos : argument.pos + argument.len]
                        target = target[1:-1] if isinstance(argument, LatexGroupNode) else target
                        if re.search(r"[\\{}#%$]", target) or not target.strip():
                            self.issues.append(
                                {
                                    "code": "DYNAMIC_PATH",
                                    "file": self.file,
                                    "message": msg("notice.latex.4", name=name, target=target),
                                }
                            )
                        elif name == "includegraphics":
                            self.graphics.append(target.strip())
                        else:
                            self.includes.append((target.strip(), start))
                    else:
                        self.issues.append(
                            {
                                "code": "DYNAMIC_PATH",
                                "file": self.file,
                                "message": msg("notice.latex.3", name=name),
                            }
                        )
                if name in IGNORED_MACROS:
                    self.blocked.append((start, end, "structural-macro"))
                    continue
                if self.context.get_macro_spec(name) is None and name not in LAYOUT_MACROS:
                    # pylatexenc leaves unknown arguments as subsequent sibling groups.
                    last = end
                    for following in nodes[index + 1 :]:
                        if (
                            isinstance(following, LatexGroupNode)
                            and not self.text[last : following.pos].strip()
                        ):
                            last = following.pos + following.len
                        else:
                            break
                    self.blocked.append((start, last, "unknown-macro"))
                    self.issues.append(
                        {
                            "code": "UNSUPPORTED_MACRO",
                            "file": self.file,
                            "message": (msg("notice.latex.2", name=name)),
                        }
                    )
                    continue
            # Environment arguments contain layout dimensions, not reportable results.
            if isinstance(node, LatexEnvironmentNode) and node.nodeargd:
                for arg in node.nodeargd.argnlist:
                    if arg is not None:
                        self.blocked.append((arg.pos, arg.pos + arg.len, "environment-argument"))
            elif getattr(node, "nodeargd", None):
                for arg in node.nodeargd.argnlist:
                    if arg is not None:
                        self._walk([arg])
            if getattr(node, "nodelist", None):
                self._walk(node.nodelist)

    def checkable(self, start: int, end: int) -> bool:
        return not any(start < high and end > low for low, high, _ in self.blocked)

    def span(self, start: int, end: int) -> Span:
        row = bisect.bisect_right(self.line_starts, start) - 1
        return Span(
            self.file,
            start,
            end,
            self.byte_offsets[start],
            self.byte_offsets[end],
            row + 1,
            start - self.line_starts[row] + 1,
            self.text[start:end],
        )

    def locate(self, anchor: Anchor) -> Span:
        if anchor.block is not None:
            raise PaperDeltaError("DOCUMENT_ANCHOR_FORMAT", msg("document.anchor_format"))
        if anchor.table is not None:
            from paperdelta.tables import locate_cell

            return locate_cell(self, anchor.table)
        candidates: list[tuple[int, int]] = []
        if anchor.exact is not None:
            for match in re.finditer(re.escape(anchor.exact), self.text):
                candidates.append(match.span())
        else:
            assert anchor.prefix is not None and anchor.suffix is not None
            for match in re.finditer(re.escape(anchor.prefix), self.text):
                start = match.end()
                end = self.text.find(anchor.suffix, start)
                if 0 <= end - start <= 1000:
                    candidates.append((start, end))
        if not candidates:
            raise PaperDeltaError("ANCHOR_MISSING", msg("error.ANCHOR_MISSING", value1=self.file))
        # Ambiguity is not resolved by silently discarding a matching commented-out copy.
        if len(candidates) != 1:
            raise PaperDeltaError(
                "ANCHOR_AMBIGUOUS",
                msg("error.ANCHOR_AMBIGUOUS", value1=len(candidates), value2=self.file),
            )
        start, end = candidates[0]
        if start == end or not self.checkable(start, end):
            raise PaperDeltaError(
                "UNSUPPORTED_SPAN", msg("error.UNSUPPORTED_SPAN", value1=self.file)
            )
        return self.span(start, end)

    @cached_property
    def _number_spans(self) -> tuple[Span, ...]:
        # A document belongs to one immutable input read. A subsequent check
        # creates a new document; no result is cached across file changes.
        return tuple(
            self.span(*match.span())
            for match in NUMBER_PATTERN.finditer(self.text)
            if self.checkable(*match.span())
        )

    def numbers(self) -> list[Span]:
        return list(self._number_spans)

    def validate_numeric_span(self, span: Span) -> None:
        overlapping = [
            token for token in self.numbers() if token.start < span.end and token.end > span.start
        ]
        if len(overlapping) != 1:
            raise PaperDeltaError("NUMERIC_ANCHOR", msg("error.NUMERIC_ANCHOR"))
        token = overlapping[0]
        if token.start < span.start or token.end > span.end:
            raise PaperDeltaError("PARTIAL_NUMBER", msg("error.PARTIAL_NUMBER"))


class PaperIndex:
    def __init__(self, project: Project, paper: Paper):
        self.project = project
        self.paper = paper
        self.documents: dict[str, TexDocument] = {}
        self.issues: list[dict] = []
        self._active: set[str] = set()
        self._visit(paper.entry)

    def _visit(self, file: str) -> None:
        path = self.project.path(file)
        file = self.project.relative(path)
        if file in self._active:
            raise PaperDeltaError("INCLUDE_CYCLE", msg("error.INCLUDE_CYCLE", file=file))
        if file in self.documents:
            return
        if len(self.documents) >= 200 or len(self._active) >= 40:
            raise PaperDeltaError("INCLUDE_LIMIT", msg("error.INCLUDE_LIMIT"))
        doc = TexDocument(file, self.project.read(file, 4 * 1024 * 1024), self.paper.macros)
        self.documents[file] = doc
        self.issues.extend(doc.issues)
        self._active.add(file)
        for target, _ in doc.includes:
            target = target if Path(target).suffix else target + ".tex"
            possible = {
                self.project.path((Path(self.paper.entry).parent / target).as_posix()),
                self.project.path((Path(file).parent / target).as_posix()),
            }
            existing = [item for item in possible if item.is_file()]
            if len(existing) != 1:
                raise PaperDeltaError(
                    "INCLUDE_PATH", msg("error.INCLUDE_PATH", target=target, file=file)
                )
            self._visit(self.project.relative(existing[0]))
        self._active.remove(file)

    def document(self, file: str) -> TexDocument:
        relative = self.project.relative(self.project.path(file))
        if relative not in self.documents:
            raise PaperDeltaError("UNREACHABLE_TEX", msg("error.UNREACHABLE_TEX", file=file))
        return self.documents[relative]
