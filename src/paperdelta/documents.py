"""Document discovery shared by checks, bindings, scope and agent tools.

Native document adapters retain their own positions. A text offset in an adapter's
read model is never a byte offset into a DOCX or PDF file.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import Protocol

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.incremental import reuse
from paperdelta.latex import PaperIndex as LatexIndex
from paperdelta.models import Anchor, Paper
from paperdelta.storage import Project, sha256


class LocatedText(Protocol):
    file: str
    start: int
    end: int
    text: str

    def to_dict(self) -> dict: ...


class Document(Protocol):
    percent_token: str
    file: str
    text: str
    hash: str
    issues: list[dict]
    graphics: list[str]
    priority_regions: list[tuple[int, int, str]]

    def span(self, start: int, end: int) -> LocatedText: ...
    def locate(self, anchor: Anchor) -> LocatedText: ...
    def numbers(self) -> list[LocatedText]: ...
    def checkable(self, start: int, end: int) -> bool: ...
    def validate_numeric_span(self, span: LocatedText) -> None: ...


def document_format(entry: str) -> str:
    suffix = Path(entry).suffix.lower()
    if suffix == ".tex":
        return "latex"
    if suffix == ".docx":
        return "docx"
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".md", ".qmd"}:
        return "markdown" if suffix == ".md" else "quarto"
    raise PaperDeltaError("DOCUMENT_FORMAT", msg("document.format", file=entry))


class PaperIndex:
    def __init__(self, project: Project, paper: Paper):
        self.project, self.paper = project, paper
        self.format = document_format(paper.entry)
        self.documents, self.issues, self.exports = {}, [], {}
        self.members, self.origins = {}, {}
        for manuscript in [paper, *paper.companions]:
            format = document_format(manuscript.entry)
            file = project.relative(project.path(manuscript.entry))
            if format == "latex":
                index = LatexIndex(project, manuscript)
                documents, issues = index.documents, index.issues
            else:
                if manuscript.macros:
                    raise PaperDeltaError("DOCUMENT_MACROS", msg("document.macros"))
                raw = project.read(file)
                document = reuse(
                    project,
                    "document",
                    [file, format, sha256(raw), manuscript.pdf_regions],
                    partial(_parse_document, file, raw, format, manuscript.pdf_regions),
                )
                documents, issues = {file: document}, document.issues
            for name, document in documents.items():
                if name in self.documents:
                    raise PaperDeltaError("DOCUMENT_DUPLICATE", msg("document.duplicate"))
                self.documents[name] = document
                self.origins[name] = file
            self.members[file] = set(documents)
            self.issues.extend(issues)
            if manuscript.export_of is not None:
                self.exports[file] = project.relative(project.path(manuscript.export_of))
        if paper.companions:
            self.format = "multiple"

    def document(self, file: str) -> Document:
        relative = self.project.relative(self.project.path(file))
        if relative not in self.documents:
            code = "UNREACHABLE_TEX" if self.format == "latex" else "UNREACHABLE_DOCUMENT"
            key = "error.UNREACHABLE_TEX" if self.format == "latex" else "document.unreachable"
            raise PaperDeltaError(code, msg(key, file=file))
        return self.documents[relative]


def _parse_document(file, raw, format, regions):
    if format == "docx":
        from paperdelta.docx_document import DocxDocument

        return DocxDocument(file, raw)
    if format == "pdf":
        from paperdelta.pdf_document import PdfDocument

        return PdfDocument(file, raw, regions)
    from paperdelta.markdown_document import MarkdownDocument

    return MarkdownDocument(file, raw, format)
