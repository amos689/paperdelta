"""Literal table cells located by unchanged headers and explicit row identities."""

from __future__ import annotations

import re

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.models import Anchor, TableCellAnchor


def clean(text):
    text = re.sub(r"(?<!\\)%[^\n]*", "", text)
    text = re.sub(r"\\(?:toprule|midrule|bottomrule|hline)\b(?:\[[^\]]*\])?", "", text)
    text = re.sub(r"\\cline\{[0-9]+-[0-9]+\}", "", text)
    return " ".join(text.split())


def literal_tables(document):
    if hasattr(document, "native_tables"):
        yield from document.native_tables
        return
    for low, high in document.table_regions:
        text = document.text
        if re.search(
            r"\\(?:multicolumn|multirow|span|omit|endfirsthead|endhead)\b", text[low:high]
        ):
            continue
        rows, row, depth = [], [], 0
        cell_start, index = low, low
        while index < high:
            char = text[index]
            if char == "%":
                newline = text.find("\n", index, high)
                index = high if newline < 0 else newline + 1
                continue
            if char == "\\":
                if text[index : index + 2] == r"\\" and depth == 0:
                    row.append((cell_start, index))
                    rows.append(row)
                    row = []
                    index += 2
                    spacing = re.match(r"\*?(?:\[[^\]]*\])?", text[index:high])
                    index += len(spacing.group())
                    cell_start = index
                    continue
                index += 2
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            elif char == "&" and depth == 0:
                row.append((cell_start, index))
                cell_start = index + 1
            index += 1
        row.append((cell_start, high))
        if any(clean(text[a:b]) for a, b in row):
            rows.append(row)
        if depth == 0:
            yield rows


def _row_values(document, row):
    cleaner = (lambda text: " ".join(text.split())) if hasattr(document, "native_tables") else clean
    return [cleaner(document.text[a:b]) for a, b in row]


def _numbers(document, cell):
    if hasattr(document, "numbers_in"):
        return document.numbers_in(*cell)
    return [span for span in document.numbers() if cell[0] <= span.start and span.end <= cell[1]]


def _headers(document, rows, count=None):
    if count is not None:
        return [" & ".join(_row_values(document, row)) for row in rows[:count]]
    values = []
    for row in rows:
        if any(_numbers(document, cell) for cell in row):
            break
        values.append(" & ".join(_row_values(document, row)))
    return values


def _native_header_count(document, rows):
    """Propose a literal header boundary, retained explicitly in the accepted anchor."""
    from paperdelta.metrics import NUMBER, NUMBER_PATTERN

    count = 1
    for row in rows[1:20]:
        values = _row_values(document, row)
        # 95% CI contains letters after removing the number; a measured cell
        # such as < .001, 82%, or [1.2, 1.5] has only numeric punctuation.
        if any(
            _numbers(document, cell)
            and any(
                NUMBER_PATTERN.search(line)
                and not re.search(
                    r"[^\s<>=±+−\-.,%*\[\]()/]",
                    NUMBER_PATTERN.sub("", re.sub(rf"\(\s*n\s*=\s*{NUMBER}\s*\)", "", line)),
                )
                for line in document.text[cell[0] : cell[1]].splitlines()
            )
            for cell, text in zip(row, values, strict=True)
        ):
            break
        count += 1
    return count if count < len(rows) else len(_headers(document, rows)) or 1


def locate_cell(document, anchor):
    if getattr(document, "format", "latex") == "pdf" and anchor.parser != document.parser:
        raise PaperDeltaError(
            "PDF_EXTRACTION_CHANGED", msg("pdf.extraction_changed", file=document.file)
        )
    if (
        anchor.page is not None or anchor.region is not None or anchor.parser is not None
    ) and getattr(document, "format", "latex") != "pdf":
        raise PaperDeltaError("DOCUMENT_ANCHOR_FORMAT", msg("pdf.anchor_format"))
    found = []
    for rows in literal_tables(document):
        scope = getattr(document, "table_scopes", {}).get(id(rows), {})
        if (anchor.page is not None and scope.get("page") != anchor.page) or (
            anchor.region is not None and scope.get("region") != anchor.region
        ):
            continue
        metadata = getattr(document, "native_table_metadata", {}).get(id(rows), {})
        if anchor.caption is not None and metadata.get("caption") != anchor.caption:
            continue
        if _headers(document, rows, anchor.header_rows) != anchor.headers:
            continue
        for row in rows[anchor.header_rows or 0 :]:
            if (
                len(row) <= anchor.column
                or _row_values(document, row)[: len(anchor.row_prefix)] != anchor.row_prefix
            ):
                continue
            if anchor.statistical_display is not None:
                from paperdelta.statistical_display import cell_span

                try:
                    span = cell_span(
                        document,
                        row[anchor.column],
                        anchor.statistical_display,
                        anchor.percent_symbol,
                    )
                except PaperDeltaError:
                    continue
            else:
                spans = _numbers(document, row[anchor.column])
                if len(spans) != 1:
                    continue
                span = spans[0]
            if anchor.percent_symbol and anchor.statistical_display is None:
                if not document.text[span.end :].startswith(document.percent_token):
                    continue
                span = document.span(span.start, span.end + len(document.percent_token))
            if document.checkable(span.start, span.end):
                found.append(span)
    found = list({(span.start, span.end): span for span in found}.values())
    if len(found) != 1:
        code = "ANCHOR_AMBIGUOUS" if found else "ANCHOR_MISSING"
        raise PaperDeltaError(code, msg("table.anchor", file=document.file, count=len(found)))
    return found[0]


def anchor_for_cell(document, span, identity_values=(), statistical_display=None):
    if getattr(span, "locator", {}).get("column_span", 1) > 1:
        return None
    for rows in literal_tables(document):
        variants = [None]
        if hasattr(document, "native_tables"):
            count = _native_header_count(document, rows)
            variants = ([None] if count == len(_headers(document, rows)) else []) + [count]
        for header_count in variants:
            result = _anchor_in_table(
                document, rows, span, identity_values, statistical_display, header_count
            )
            if result is not None:
                return result
    return None


def _anchor_in_table(document, rows, span, identity_values, statistical_display, header_count):
    headers = _headers(document, rows, header_count)
    if not headers:
        return None
    for row in rows[header_count or 0 :]:
        column = next(
            (index for index, (a, b) in enumerate(row) if a <= span.start and span.end <= b),
            None,
        )
        if not column:
            continue
        prefix = []
        for index, cell in enumerate(row[:column]):
            if _numbers(document, cell) and not (
                index == 0 and _row_values(document, [cell])[0] in identity_values
            ):
                break
            prefix.append(_row_values(document, [cell])[0])
            if not any(prefix):
                continue
            anchor = TableCellAnchor(
                headers=headers,
                row_prefix=list(prefix),
                column=column,
                percent_symbol=document.percent_token in span.text
                if statistical_display
                else span.text.endswith(document.percent_token),
                statistical_display=statistical_display,
                **(
                    {
                        "header_rows": header_count,
                        "caption": getattr(document, "native_table_metadata", {})
                        .get(id(rows), {})
                        .get("caption"),
                    }
                    if header_count is not None
                    else {}
                ),
                **getattr(document, "table_scopes", {}).get(id(rows), {}),
            )
            try:
                located = locate_cell(document, anchor)
            except PaperDeltaError:
                continue
            if (located.start, located.end) == (span.start, span.end):
                return Anchor(table=anchor)
    return None
