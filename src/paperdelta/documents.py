"""Document discovery shared by checks, bindings, scope and agent tools.

Native document adapters retain their own positions. A text offset in an adapter's
read model is never a byte offset into a DOCX or PDF file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.latex import PaperIndex as LatexIndex
from paperdelta.models import Anchor, Paper
from paperdelta.storage import Project


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
    raise PaperDeltaError("DOCUMENT_FORMAT", msg("document.format", file=entry))


class PaperIndex:
    def __init__(self, project: Project, paper: Paper):
        self.project, self.paper = project, paper
        self.format = document_format(paper.entry)
        if self.format == "latex":
            index = LatexIndex(project, paper)
            self.documents, self.issues = index.documents, index.issues
        else:
            if paper.macros:
                raise PaperDeltaError("DOCUMENT_MACROS", msg("document.macros"))
            from paperdelta.docx_document import DocxDocument

            file = project.relative(project.path(paper.entry))
            document = DocxDocument(file, project.read(file))
            self.documents = {file: document}
            self.issues = document.issues

    def document(self, file: str) -> Document:
        relative = self.project.relative(self.project.path(file))
        if relative not in self.documents:
            code = "UNREACHABLE_TEX" if self.format == "latex" else "UNREACHABLE_DOCUMENT"
            key = "error.UNREACHABLE_TEX" if self.format == "latex" else "document.unreachable"
            raise PaperDeltaError(code, msg(key, file=file))
        return self.documents[relative]
