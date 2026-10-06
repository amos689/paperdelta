"""Read-only text models with format-specific positions and shared reviewed anchors."""

from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from functools import cached_property

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.metrics import NUMBER
from paperdelta.models import Anchor
from paperdelta.storage import fingerprint, sha256

NUMBER_PATTERN = re.compile(rf"(?<![A-Za-z0-9_.]){NUMBER}(?![A-Za-z0-9_]|\.\d)")


@dataclass(frozen=True)
class Block:
    start: int
    end: int
    identity: str
    locator: dict
    supported: bool


@dataclass(frozen=True)
class NativeSpan:
    file: str
    start: int
    end: int
    text: str
    format: str
    parser: str
    locator: dict
    context: str

    def to_dict(self) -> dict:
        return dict(vars(self))


class NativeDocument:
    percent_token = "%"

    def __init__(self, file: str, raw: bytes, format: str, parser: str):
        self.file, self.raw, self.hash = file, raw, sha256(raw)
        self.format, self.parser = format, parser
        self.text = ""
        self.blocks: list[Block] = []
        self._block_starts: list[int] = []
        self.issues: list[dict] = []
        self.graphics: list[str] = []
        self.priority_regions: list[tuple[int, int, str]] = []
        self.table_regions: list[tuple[int, int]] = []
        self.native_tables: list[list[list[tuple[int, int]]]] = []

    def add_block(self, text, locator, *, supported=True, identity_context=None):
        if len(self.blocks) >= 10000 or len(self.text) + len(text) > 4 * 1024 * 1024:
            raise PaperDeltaError("DOCUMENT_LIMIT", msg("document.limit", file=self.file))
        start = len(self.text)
        self.text += text + "\n"
        block = Block(
            start,
            start + len(text),
            fingerprint(
                {
                    "adapter": f"{self.format}/1",
                    "context": identity_context,
                    "text": NUMBER_PATTERN.sub("<number>", text),
                }
            ),
            locator,
            supported,
        )
        self.blocks.append(block)
        self._block_starts.append(start)
        return block

    def issue(self, code, **params):
        action = "native.read_original"
        if code.startswith("PDF_"):
            action = "native.pdf_region" if code == "PDF_COMPLEX_TABLE" else "native.pdf_original"
        elif code == "DOCX_COMPLEX_TABLE":
            action = "native.word_grid"
        self.issues.append(
            {
                "code": code,
                "file": self.file,
                "message": msg(f"document.{code}", **params),
                "stage": "ambiguous"
                if code in {"PDF_COMPLEX_TABLE", "PDF_UNRELIABLE_TEXT"}
                else "extraction",
                "action": msg(action),
                "location_hint": {
                    k: v for k, v in params.items() if k in {"page", "paragraph", "table", "row"}
                },
            }
        )

    def block_at(self, start, end):
        index = bisect_right(self._block_starts, start) - 1
        if index >= 0:
            block = self.blocks[index]
            if block.start <= start < end <= block.end:
                return block
        return None

    def checkable(self, start, end):
        block = self.block_at(start, end)
        return block is not None and block.supported

    def span(self, start, end):
        block = self.block_at(start, end)
        if block is None:
            raise PaperDeltaError("UNSUPPORTED_SPAN", msg("document.span", file=self.file))
        context = self.text[max(block.start, start - 180) : min(block.end, end + 180)]
        if block.locator.get("table") is not None:
            for rows in self.native_tables:
                row = next(
                    (row for row in rows if any(a <= start < end <= b for a, b in row)), None
                )
                if row is not None:
                    # Display a source-text table excerpt; the bound text/locator remain exact.
                    selected = [rows[0], row] if row is not rows[0] else [row]
                    context = "\n".join(
                        " | ".join(" ".join(self.text[a:b].split()) for a, b in cells)
                        for cells in selected
                    )[:2000]
                    break
        return NativeSpan(
            self.file,
            start,
            end,
            self.text[start:end],
            self.format,
            self.parser,
            {**block.locator, "block": block.identity, "offset": start - block.start},
            context,
        )

    @cached_property
    def _tokens(self):
        return list(NUMBER_PATTERN.finditer(self.text))

    @cached_property
    def _token_starts(self):
        return [item.start() for item in self._tokens]

    def _numeric_boundary(self, position):
        index = bisect_left(self._token_starts, position) - 1
        return index < 0 or not self._tokens[index].start() < position < self._tokens[index].end()

    @cached_property
    def _numbers(self):
        return [
            self.span(m.start(), m.end())
            for m in self._tokens
            if self.checkable(m.start(), m.end())
        ]

    def numbers(self):
        return list(self._numbers)

    @cached_property
    def _number_starts(self):
        return [span.start for span in self._numbers]

    def numbers_in(self, start, end):
        first, last = bisect_left(self._number_starts, start), bisect_left(self._number_starts, end)
        return [span for span in self._numbers[first:last] if span.end <= end]

    def validate_numeric_span(self, span):
        found = [m for m in self._tokens if m.start() < span.end and span.start < m.end()]
        if (
            not self.checkable(span.start, span.end)
            or len(found) != 1
            or found[0].start() != span.start
            or found[0].end() > span.end
            or self.text[found[0].end() : span.end] not in ("", self.percent_token)
        ):
            raise PaperDeltaError("NUMERIC_SPAN", msg("document.number", file=self.file))

    def locate(self, anchor: Anchor):
        if self.format != "pdf" and anchor.parser is not None:
            raise PaperDeltaError("DOCUMENT_ANCHOR_FORMAT", msg("pdf.anchor_format"))
        if anchor.table is not None:
            from paperdelta.tables import locate_cell

            return locate_cell(self, anchor.table)
        blocks = self.blocks
        if anchor.block is not None:
            blocks = [b for b in blocks if b.identity == anchor.block]
            if len(blocks) != 1:
                self._anchor_error(len(blocks))
        found = []
        attempts = 0
        # Include unsupported blocks in ambiguity counting. Never choose a convenient copy.
        for block in blocks:
            text = self.text[block.start : block.end]
            if anchor.exact is not None:
                for match in re.finditer(re.escape(anchor.exact), text):
                    found.append((block.start + match.start(), block.start + match.end()))
                    if len(found) > 1:
                        self._anchor_error(len(found))
            else:
                prefix, suffix = anchor.prefix, anchor.suffix
                left = [m.end() for m in re.finditer(re.escape(prefix), text)] if prefix else [0]
                right = (
                    [m.start() for m in re.finditer(re.escape(suffix), text)]
                    if suffix
                    else [len(text)]
                )
                for a in left:
                    for b in right[bisect_right(right, a) : bisect_right(right, a + 1000)]:
                        attempts += 1
                        if attempts > 10000:
                            raise PaperDeltaError(
                                "DOCUMENT_LIMIT", msg("document.anchor_limit", file=self.file)
                            )
                        start, end = block.start + a, block.start + b
                        if (
                            anchor.numeric_only
                            and re.fullmatch(
                                rf"{NUMBER}(?:{re.escape(self.percent_token)})?",
                                self.text[start:end],
                            )
                            is None
                        ):
                            continue
                        # A decimal point inside a numeric token is not a sentence boundary.
                        if self._numeric_boundary(start) and self._numeric_boundary(end):
                            found.append((start, end))
                            if len(found) > 1:
                                self._anchor_error(len(found))
        if len(found) != 1:
            self._anchor_error(len(found))
        start, end = found[0]
        if not self.checkable(start, end):
            raise PaperDeltaError("UNSUPPORTED_SPAN", msg("document.span", file=self.file))
        return self.span(start, end)

    def _anchor_error(self, count):
        code = "ANCHOR_AMBIGUOUS" if count else "ANCHOR_MISSING"
        raise PaperDeltaError(code, msg("document.anchor_count", file=self.file, count=count))

    def anchor_for_span(self, span, identity_values=(), display=None):
        if display is None:
            self.validate_numeric_span(span)
        else:
            from paperdelta.statistical_display import validate_span

            validate_span(self, span, display)
        from paperdelta.tables import anchor_for_cell

        statistical = (
            display.statistics
            if display and display.statistics and display.statistics.compound
            else None
        )
        table_anchor = anchor_for_cell(self, span, identity_values, statistical)
        if table_anchor is not None:
            return table_anchor
        block = self.block_at(span.start, span.end)
        # Table identities must come from explicit row labels and headers, not row order.
        if "table" in block.locator:
            raise PaperDeltaError("BUILDER_ANCHOR", msg("document.anchor", file=self.file))
        numbers = self.numbers()
        low = max([block.start, *[n.end for n in numbers if block.start <= n.end <= span.start]])
        high = min([block.end, *[n.start for n in numbers if span.end <= n.start <= block.end]])
        anchor = Anchor(
            block=block.identity,
            prefix=self.text[low : span.start],
            suffix=self.text[span.end : high],
            parser=self.parser if self.format == "pdf" else None,
        )
        try:
            found = self.locate(anchor)
        except PaperDeltaError as error:
            if error.code != "ANCHOR_AMBIGUOUS" or statistical is not None:
                raise
            # The same suffix can follow a single number or an entire intervening
            # phrase. Declare the numeric-only interval explicitly; the original
            # block identity and both literal boundaries still have to match.
            anchor = anchor.model_copy(update={"numeric_only": True})
            found = self.locate(anchor)
        if (found.start, found.end) != (span.start, span.end):
            raise PaperDeltaError("BUILDER_ANCHOR", msg("document.anchor", file=self.file))
        return anchor

    def location_context(self, item):
        from paperdelta.tables import _numbers, _row_values

        for rows in self.native_tables:
            for row in rows:
                for col, (a, b) in enumerate(row):
                    if a <= item["start"] and item["end"] <= b:
                        values = _row_values(self, row)
                        values[col] = "[value]"
                        headers = []
                        for header in rows:
                            if any(_numbers(self, cell) for cell in header):
                                break
                            headers.append(_row_values(self, header)[col])
                        return {
                            "kind": "table",
                            "row": " | ".join(values)[:2000],
                            "column_header": " | ".join(headers)[-500:],
                        }
        block = self.block_at(item["start"], item["end"])
        return {
            "kind": "text",
            "row": self.text[block.start : block.end][:2000],
            "column_header": "",
        }
