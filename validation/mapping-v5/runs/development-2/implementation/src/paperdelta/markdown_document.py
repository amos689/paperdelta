"""Bounded static Markdown/Quarto reading with positions in the original UTF-8 source.

Only literal source text is checked. Code, renderer-dependent constructs and
non-contiguous numeric displays remain unverified. Nothing is rendered or executed.
"""

from __future__ import annotations

import bisect
import re
import unicodedata
from dataclasses import dataclass, replace
from functools import cached_property
from importlib.metadata import version

from markdown_it import MarkdownIt
from markdown_it.rules_inline.state_inline import StateInline

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.native_document import NUMBER_PATTERN, Block, NativeDocument, NativeSpan
from paperdelta.storage import fingerprint

LIMIT = 4 * 1024 * 1024


@dataclass(frozen=True)
class MarkdownSpan(NativeSpan):
    byte_start: int
    byte_end: int
    line: int
    column: int


class MarkdownDocument(NativeDocument):
    def __init__(self, file, raw, format="markdown"):
        if len(raw) > LIMIT:
            raise PaperDeltaError("DOCUMENT_LIMIT", msg("document.limit", file=file))
        super().__init__(
            file, raw, format, f"paperdelta-markdown/1 markdown-it-py/{version('markdown-it-py')}"
        )
        try:
            self.text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PaperDeltaError("ENCODING", msg("error.ENCODING", file=file)) from exc
        self.byte_offsets = [0]
        for char in self.text:
            self.byte_offsets.append(self.byte_offsets[-1] + len(char.encode("utf-8")))
        # Only CR/LF are Markdown newlines; other Unicode separators stay literal.
        self.lines = re.findall(r"[^\r\n]*(?:\r\n|\r|\n|$)", self.text)
        if self.lines and not self.lines[-1]:
            self.lines.pop()
        if len(self.lines) > 20000 or any(len(line) > 65536 for line in self.lines):
            raise PaperDeltaError("DOCUMENT_LIMIT", msg("document.limit", file=file))
        self.line_starts = [0]
        for line in self.lines:
            self.line_starts.append(self.line_starts[-1] + len(line))
        self._blocked, self._masks, self._contexts = [], [], {}
        self._problems = set()
        self.native_table_metadata = {}
        self.md = MarkdownIt("commonmark", {"html": True, "maxNesting": 20}).enable("table")
        self._inline_state = None
        self._unsafe_html = False
        self._install_inline_observer()
        try:
            self._read()
        except (ValueError, RecursionError, IndexError):
            # A failed secondary/inline parse must not leave a partly checked file.
            self.blocks, self.native_tables = [], []
            self.priority_regions, self.table_regions = [], []
            self._problem("PARSE", 0)
            self._block(0, len(self.text), "parse", supported=False)
        if self._unsafe_html:
            # HTML containers/CSS can affect paragraphs outside an HTML token's
            # CommonMark block map. Never offer their apparently literal numbers.
            self.blocks = [replace(block, supported=False) for block in self.blocks]
            self.native_tables, self.table_regions, self.priority_regions = [], [], []
        self.blocks.sort(key=lambda b: b.start)
        self._block_starts = [b.start for b in self.blocks]
        merged = []
        for a, b in sorted(self._blocked):
            if a >= b:
                continue
            if merged and a <= merged[-1][1]:
                merged[-1] = merged[-1][0], max(b, merged[-1][1])
            else:
                merged.append((a, b))
        self._blocked = merged
        self._blocked_starts = [a for a, _ in merged]
        view = list(self.text)
        for a, b in self._masks:
            view[a:b] = " " * (b - a)
        self.numeric_view = "".join(view)
        tokens = list(NUMBER_PATTERN.finditer(self.numeric_view))
        starts = [t.start() for t in tokens]
        for index, block in enumerate(self.blocks):
            masked, previous = [], block.start
            for token in tokens[
                bisect.bisect_left(starts, block.start) : bisect.bisect_left(starts, block.end)
            ]:
                if token.end() <= block.end:
                    masked.extend((self.text[previous : token.start()], "<number>"))
                    previous = token.end()
            masked.append(self.text[previous : block.end])
            self.blocks[index] = replace(
                block,
                identity=fingerprint(
                    {
                        "adapter": f"{format}/1",
                        "context": self._contexts[(block.start, block.end)],
                        "text": "".join(masked),
                    }
                ),
            )

        # Parsing is complete. Drop observer closures and their parser state;
        # only the immutable source read model is needed for later checks.
        self.md = self._inline_state = None
        self.environment = {}

    def _problem(self, reason, start):
        line = bisect.bisect_right(self.line_starts, start)
        if (reason, line) not in self._problems:
            self._problems.add((reason, line))
            code = "MARKDOWN_" + reason
            self.issues.append(
                {
                    "code": code,
                    "file": self.file,
                    "message": msg("markdown." + code, file=self.file, line=line),
                }
            )

    def _block(self, a, b, kind, section=(), *, supported=True, cell=None):
        if a >= b:
            return
        if len(self.blocks) >= 10000:
            raise PaperDeltaError("DOCUMENT_LIMIT", msg("document.limit", file=self.file))
        locator = {"section": list(section), **(cell or {})}
        self.blocks.append(Block(a, b, "", locator, supported))
        self._contexts[(a, b)] = {"kind": kind, "section": list(section)}
        if "abstract" in {s.strip().casefold() for s in section} or "摘要" in section:
            self.priority_regions.append((a, b, "abstract"))

    def _line_bounds(self, start, end):
        return self.line_starts[start], self.line_starts[min(end, len(self.lines))]

    def _read(self):
        if any(
            unicodedata.category(char) in {"Cc", "Cf"}
            and char not in "\t\r\n"
            and not (index == 0 and char == "\ufeff")
            for index, char in enumerate(self.text)
        ):
            self._problem("ENCODING", 0)
            self._block(0, len(self.text), "controls", supported=False)
            return
        # Mask metadata without changing line identities before the block parser runs.
        parse_lines = [line.rstrip("\r\n") for line in self.lines]
        if parse_lines:
            parse_lines[0] = parse_lines[0].removeprefix("\ufeff")
        if parse_lines and parse_lines[0] == "---":
            close = next(
                (i for i, line in enumerate(parse_lines[1:], 1) if line in {"---", "..."}),
                len(parse_lines) - 1,
            )
            a, b = self._line_bounds(0, close + 1)
            self._problem("METADATA", a)
            self._block(a, b, "metadata", supported=False)
            parse_lines[: close + 1] = [""] * (close + 1)
        source = "\n".join(parse_lines)
        environment, tokens = {}, []
        try:
            self.md.block.parse(source, self.md, environment, tokens)
        except (ValueError, RecursionError, IndexError):
            self._problem("PARSE", 0)
            self.blocks = []
            self._block(0, len(self.text), "parse", supported=False)
            return
        fenced_lines = {
            n
            for token in tokens
            if token.type in {"fence", "code_block"}
            for n in range(*token.map)
        }

        # Strip only container prefixes for detecting unsupported block syntax.
        # Source locations still refer to the complete unchanged original lines.
        def container_text(line):
            return re.sub(r"^(?:(?:\s*>\s?)|(?:\s*(?:[-+*]|\d+[.)])\s+))*", "", line).lstrip()

        # Pandoc/Quarto fenced divs may hide or generate content. Do not interpret them.
        div_start, depth = None, 0
        div_ranges = []
        for n, line in enumerate(parse_lines):
            if n in fenced_lines:
                continue
            match = re.match(r"^:{3,}(.*)$", container_text(line))
            if not match:
                continue
            if match[1].strip() or depth == 0:
                if depth == 0:
                    div_start = n
                depth += 1
            else:
                depth -= 1
                if not depth:
                    div_ranges.append((div_start, n + 1))
        if depth:
            div_ranges.append((div_start, len(parse_lines)))
        ranges = [(first, last, "DYNAMIC") for first, last in div_ranges]
        math_start, math_close = None, None
        for n, line in enumerate(parse_lines):
            if n in fenced_lines or any(first <= n < last for first, last in div_ranges):
                continue
            content = container_text(line).strip()
            if math_start is not None:
                if math_close in content:
                    ranges.append((math_start, n + 1, "DYNAMIC"))
                    math_start, math_close = None, None
                continue
            closing = None
            if content.startswith("$$"):
                closing = "$$"
                if closing in content[2:]:
                    ranges.append((n, n + 1, "DYNAMIC"))
                    continue
            elif content.startswith(r"\["):
                closing = r"\]"
            else:
                match = re.match(r"\\begin\{([A-Za-z*]+)\}", content)
                if match:
                    closing = r"\end{" + match[1] + "}"
            if closing:
                if closing != "$$" and closing in content:
                    ranges.append((n, n + 1, "DYNAMIC"))
                else:
                    math_start, math_close = n, closing
        if math_start is not None:
            ranges.append((math_start, len(parse_lines), "DYNAMIC"))
        # Grid/simple Pandoc tables have no supported column/row model here.
        # Retain their whole contiguous source area as unknown instead of prose.
        for n, line in enumerate(parse_lines):
            if n in fenced_lines:
                continue
            content = container_text(line)
            if re.fullmatch(r"(?:\+[=:-]{2,})+\+\s*|(?:-{2,}\s+)+-{2,}\s*", content):
                first, last = n, n + 1
                while first and parse_lines[first - 1].strip():
                    first -= 1
                while last < len(parse_lines) and parse_lines[last].strip():
                    last += 1
                ranges.append((first, last, "TABLE"))
        # Union overlapping ranges so a source block has one unambiguous position.
        merged = []
        for first, last, reason in sorted(ranges):
            if merged and first < merged[-1][1]:
                prior = merged[-1]
                merged[-1] = (prior[0], max(prior[1], last), prior[2])
            else:
                merged.append((first, last, reason))
        for first, last, reason in merged:
            a, b = self._line_bounds(first, last)
            self._problem(reason, a)
            self._block(a, b, "unsupported", supported=False)
            parse_lines[first:last] = [""] * (last - first)
        if merged:
            environment, tokens = {}, []
            self.md.block.parse("\n".join(parse_lines), self.md, environment, tokens)
        self.environment = environment
        section, table_number, index = [], 0, 0
        while index < len(tokens):
            token = tokens[index]
            if token.type == "table_open":
                last = next(
                    i for i in range(index + 1, len(tokens)) if tokens[i].type == "table_close"
                )
                table_number += 1
                self._table(token, table_number, section)
                index = last + 1
                continue
            if token.type == "heading_open" and index + 1 < len(tokens):
                title = re.sub(r"[*_`]+", "", tokens[index + 1].content).strip()
                level = int(token.tag[1:])
                section = section[: level - 1] + [title]
            if token.type in {"fence", "code_block", "html_block"}:
                a, b = self._line_bounds(*token.map)
                if token.type == "html_block" and not token.content.lstrip().startswith("<!--"):
                    self._unsafe_html = True
                reason = (
                    "HTML"
                    if token.type == "html_block"
                    else "DYNAMIC"
                    if token.info.strip().startswith("{")
                    else "CODE"
                )
                self._problem(reason, a)
                self._block(a, b, token.type, section, supported=False)
            elif token.type == "inline":
                mapping = self._inline_map(token)
                a, b = self._line_bounds(*token.map)
                if mapping is None:
                    self._problem("POSITION", a)
                    self._block(a, b, "unmapped", section, supported=False)
                elif mapping:
                    supported = self._inline(token.content, mapping)
                    self._block(mapping[0], mapping[-1] + 1, "prose", section, supported=supported)
            index += 1

    def _inline_map(self, token):
        parts = token.content.split("\n")
        first, last = token.map
        if len(parts) == last - first - 1 and re.fullmatch(
            r" {0,3}(?:=+|-+)\s*", self.lines[last - 1].rstrip("\r\n")
        ):
            last -= 1  # Setext heading underline is not part of its inline content.
        if len(parts) != last - first:
            return None
        mapping = []
        for offset, content in enumerate(parts):
            n = first + offset
            raw = self.lines[n].rstrip("\r\n")
            body = raw.rstrip()
            # Heading closing hashes are delimiters, not visible text.
            if re.match(r"^\ufeff? {0,3}#{1,6}(?:\s|$)", raw):
                body = re.sub(r"\s+#+\s*$", "", body)
            if body.endswith(content.rstrip()):
                start = len(body) - len(content.rstrip())
                if raw[start : start + len(content)] != content:
                    return None
            else:
                return None
            mapping.extend(self.line_starts[n] + start + i for i in range(len(content)))
            if offset + 1 < len(parts):
                mapping.append(self.line_starts[n] + len(raw))
        return mapping

    def _install_inline_observer(self):
        for name, rule in zip(
            self.md.inline.ruler.get_active_rules(), self.md.inline.ruler.getRules(""), strict=True
        ):

            def observed(state, silent, _name=name, _rule=rule):
                start = state.pos
                active = state is self._inline_state and not silent
                label_end = (
                    self.md.helpers.parseLinkLabel(state, start, True)
                    if active and _name == "link" and state.src[start : start + 1] == "["
                    else -1
                )
                accepted = _rule(state, silent)
                if accepted and active:
                    if _name == "html_inline" and not state.src[start : state.pos].startswith(
                        "<!--"
                    ):
                        self._unsafe_html = True
                    if _name == "link":
                        self._inline_blocked.extend(((start, start + 1), (label_end, state.pos)))
                    elif _name == "emphasis":
                        self._inline_masks.append((start, state.pos))
                    elif _name in {
                        "backticks",
                        "image",
                        "autolink",
                        "html_inline",
                        "entity",
                        "escape",
                    }:
                        self._inline_blocked.append((start, state.pos))
                        reason = {
                            "backticks": "CODE",
                            "image": "IMAGE",
                            "html_inline": "HTML",
                            "entity": "ENCODING",
                            "escape": "ENCODING",
                            "autolink": "REFERENCE",
                        }.get(_name)
                        if reason:
                            self._inline_reasons.add(reason)
                return accepted

            self.md.inline.ruler.at(name, observed)

    def _inline(self, content, mapping):
        if len(content) > 65536:
            self._problem("POSITION", mapping[0])
            return False
        self._inline_blocked, self._inline_masks, self._inline_reasons = [], [], set()
        state = StateInline(content, self.md, self.environment, [])
        self._inline_state = state
        self.md.inline.tokenize(state)
        for rule in self.md.inline.ruler2.getRules(""):
            rule(state)
        self._inline_state = None
        if re.search(r"\{\{[<%]|\{[^}]*\}|\[\^|(?<!\\)[$^~]|\\[([]", content):
            self._inline_reasons.add("DYNAMIC")
        # Citations and cross-reference labels are renderer inputs, not numeric results.
        if re.search(r"(?<!\w)@[\w:.+-]+", content):
            self._inline_reasons.add("REFERENCE")
        if any(
            t.type
            not in {
                "text",
                "softbreak",
                "hardbreak",
                "em_open",
                "em_close",
                "strong_open",
                "strong_close",
                "link_open",
                "link_close",
                "code_inline",
                "image",
                "html_inline",
            }
            for t in state.tokens
        ):
            self._inline_reasons.add("PARSE")
        for a, b in self._inline_blocked:
            if not 0 <= a <= b <= len(mapping):
                self._inline_reasons.add("POSITION")
                continue
            if a < b:
                self._blocked.append((mapping[a], mapping[b - 1] + 1))
        for a, b in self._inline_masks:
            if a < b:
                self._masks.append((mapping[a], mapping[b - 1] + 1))
        # Detect numbers split by formatting, such as **8**4. They have no single
        # literal source interval with the rendered value and must not become 8 or 4.
        visible = "".join(
            t.content if t.type == "text" else "\n" if t.type in {"softbreak", "hardbreak"} else ""
            for t in state.tokens
        )
        if any(
            unicodedata.category(char).startswith("M")
            for token in NUMBER_PATTERN.finditer(visible)
            for char in visible[max(0, token.start() - 1) : token.start()]
            + visible[token.end() : token.end() + 1]
        ):
            self._inline_reasons.add("ENCODING")
        view = list(content)
        for a, b in self._inline_masks + self._inline_blocked:
            view[a:b] = " " * (b - a)
        if re.search(r"(?:https?://|www\.)\S+", "".join(view), re.I):
            self._inline_reasons.add("REFERENCE")
        if [m[0] for m in NUMBER_PATTERN.finditer("".join(view))] != [
            m[0] for m in NUMBER_PATTERN.finditer(visible)
        ]:
            self._inline_reasons.add("ENCODING")
        for reason in sorted(self._inline_reasons):
            self._problem(reason, mapping[0])
        return not self._inline_reasons

    def _table(self, token, number, section):
        a, b = self._line_bounds(*token.map)
        first, last = token.map
        rows = []
        supported = token.level == 0
        for n in [first, *range(first + 2, last)]:
            raw = self.lines[n].rstrip("\r\n")
            separators = [m.start() for m in re.finditer(r"(?<!\\)\|", raw)]
            bounds = [(-1), *separators, len(raw)]
            cells = [(x + 1, y) for x, y in zip(bounds[:-1], bounds[1:], strict=True)]
            if cells and not raw[cells[0][0] : cells[0][1]].strip():
                cells.pop(0)
            if cells and not raw[cells[-1][0] : cells[-1][1]].strip():
                cells.pop()
            if not 2 <= len(cells) <= 100 or (rows and len(cells) != len(rows[0])):
                supported = False
            rows.append([(self.line_starts[n] + x, self.line_starts[n] + y) for x, y in cells])
        if sum(map(len, rows)) > 10000 or not supported:
            self._problem("TABLE", a)
            self._block(a, b, "table", section, supported=False)
            return
        beginning = len(self.blocks)
        for row_number, row in enumerate(rows, 1):
            for cell_number, (low, high) in enumerate(row, 1):
                text = self.text[low:high]
                left = len(text) - len(text.lstrip())
                right = len(text.rstrip())
                mapping = list(range(low + left, low + right))
                good = not mapping or self._inline(self.text[low + left : low + right], mapping)
                supported &= good
                self._block(
                    low,
                    high,
                    "cell",
                    section,
                    supported=good,
                    cell={"table": number, "row": row_number, "cell": cell_number},
                )
        if not supported:
            self._problem("TABLE", a)
            self.blocks[beginning:] = [
                replace(block, supported=False) for block in self.blocks[beginning:]
            ]
            return
        self.native_tables.append(rows)
        self.table_regions.append((a, b))
        self.priority_regions.append((a, b, "table"))
        previous = next((line.strip() for line in reversed(self.lines[:first]) if line.strip()), "")
        self.native_table_metadata[id(rows)] = {
            "header_rows": 1,
            "caption": previous if re.match(r"^(?:Table\s+\S+|表\s*\S+)", previous, re.I) else None,
        }

    @cached_property
    def _tokens(self):
        return list(NUMBER_PATTERN.finditer(self.numeric_view))

    def checkable(self, start, end):
        if not super().checkable(start, end):
            return False
        index = bisect.bisect_left(self._blocked_starts, end) - 1
        return index < 0 or self._blocked[index][1] <= start

    def span(self, start, end):
        base = super().span(start, end)
        row = bisect.bisect_right(self.line_starts, start) - 1
        return MarkdownSpan(
            **vars(base),
            byte_start=self.byte_offsets[start],
            byte_end=self.byte_offsets[end],
            line=row + 1,
            column=start - self.line_starts[row] + 1,
        )
