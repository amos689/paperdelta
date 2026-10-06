"""Bounded, read-only SpreadsheetML values with explicit sheet/range selection.

Read stored numeric lexemes directly: a floating-point conversion would invent a
second rounding step. Formula caches, dates, merged cells and macros are outside
this static-table contract. Nothing evaluates formulas or opens external links.
"""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
import zlib
from dataclasses import dataclass
from pathlib import PurePosixPath
from xml.etree import ElementTree as ET

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
MAX_XML_BYTES = 32 * 1024 * 1024
MAX_CELLS = 1_000_000
MAX_ROWS = 100_000
DATE_FORMATS = {*range(14, 23), *range(27, 37), *range(45, 48), *range(50, 59)}


def _error(key="structure", **values):
    return PaperDeltaError("XLSX_" + key.upper(), msg("xlsx." + key, **values))


def coordinate(value):
    match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,6})", value)
    if not match:
        raise _error("range")
    column = 0
    for letter in match[1]:
        column = column * 26 + ord(letter) - 64
    row = int(match[2])
    if column > 16384 or row > 1048576:
        raise _error("range")
    return column, row


def address(column, row):
    letters = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters + str(row)


def bounds(value, *, table=False):
    parts = value.split(":")
    if len(parts) not in {1, 2}:
        raise _error("range")
    left, top = coordinate(parts[0])
    right, bottom = coordinate(parts[-1])
    if left > right or top > bottom:
        raise _error("range")
    if table and (
        len(parts) != 2
        or top == bottom
        or bottom - top > MAX_ROWS
        or (right - left + 1) * (bottom - top + 1) > MAX_CELLS
    ):
        raise _error("range")
    return left, top, right, bottom


def _intersects(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def _text(element):
    pieces = [item.text or "" for item in element.findall(f"{{{NS}}}t")]
    pieces.extend(item.text or "" for item in element.findall(f"{{{NS}}}r/{{{NS}}}t"))
    # One replacement pass preserves escaped literal _xHHHH_ strings. Phonetic
    # guides are not concatenated to the actual cell text.
    value = re.sub(r"_x([0-9A-Fa-f]{4})_", lambda m: chr(int(m[1], 16)), "".join(pieces))
    try:
        return value.encode("utf-16-le", "surrogatepass").decode("utf-16-le")
    except UnicodeError as exc:
        raise _error() from exc


@dataclass(frozen=True)
class Cell:
    address: str
    kind: str
    value: str | None


@dataclass(frozen=True)
class StaticTable:
    sheet: str
    cell_range: str
    columns: list[str]
    rows: list[dict[str, Cell]]


class Workbook:
    def __init__(self, raw):
        try:
            self.archive = zipfile.ZipFile(io.BytesIO(raw))
            entries = self.archive.infolist()
            names = [item.filename for item in entries]
            if (
                len(names) != len(set(names))
                or len(names) > 5000
                or sum(item.file_size for item in entries) > 128 * 1024 * 1024
                or any(item.file_size > MAX_XML_BYTES or item.flag_bits & 1 for item in entries)
                or any(
                    "\\" in name
                    or PurePosixPath(name).is_absolute()
                    or ".." in PurePosixPath(name).parts
                    for name in names
                )
            ):
                raise _error()
            if any("vbaproject" in name.casefold() for name in names):
                raise _error("macros")
            workbook = self._xml("xl/workbook.xml")
            if workbook.tag != f"{{{NS}}}workbook":
                raise _error()
            relationships = self._xml("xl/_rels/workbook.xml.rels")
            relationships_by_id = {}
            for relationship in relationships.findall(f"{{{PACKAGE_REL}}}Relationship"):
                identity = relationship.get("Id")
                if not identity or identity in relationships_by_id:
                    raise _error()
                relationships_by_id[identity] = relationship
            self.sheets = {}
            seen_sheets = set()
            for sheet in workbook.findall(f"{{{NS}}}sheets/{{{NS}}}sheet"):
                name = sheet.get("name")
                relationship = relationships_by_id.get(sheet.get(f"{{{REL}}}id"))
                if not name or name.casefold() in seen_sheets:
                    raise _error()
                seen_sheets.add(name.casefold())
                if relationship is None or relationship.get("TargetMode", "Internal") != "Internal":
                    raise _error()
                if relationship.get("Type") == REL + "/chartsheet":
                    continue
                if relationship.get("Type") != REL + "/worksheet":
                    raise _error()
                target = relationship.get("Target", "")
                if not target or "\\" in target or ":" in target or "?" in target or "#" in target:
                    raise _error()
                target = posixpath.normpath(
                    target.lstrip("/") if target.startswith("/") else "xl/" + target
                )
                if target.startswith("../") or target not in names:
                    raise _error()
                self.sheets[name] = target
            if not self.sheets:
                raise _error()
            self.shared = []
            if "xl/sharedStrings.xml" in names:
                self.shared = [
                    _text(si) for si in self._xml("xl/sharedStrings.xml").findall(f"{{{NS}}}si")
                ]
            self.date_styles = set()
            self.style_count = 1
            if "xl/styles.xml" in names:
                styles = self._xml("xl/styles.xml")
                custom = {
                    int(item.attrib["numFmtId"]): item.attrib["formatCode"]
                    for item in styles.findall(f"{{{NS}}}numFmts/{{{NS}}}numFmt")
                }
                formats = styles.findall(f"{{{NS}}}cellXfs/{{{NS}}}xf")
                self.style_count = len(formats)
                for index, item in enumerate(formats):
                    kind = int(item.get("numFmtId", "0"))
                    if (
                        kind < 0
                        or (kind >= 164 and kind not in custom)
                        or (kind < 164 and kind not in {*range(23), *range(27, 59)})
                    ):
                        raise _error()
                    pattern = custom.get(kind, "")
                    # Quoted/escaped literals and non-time bracket annotations do
                    # not turn a numeric display format into a date convention.
                    pattern = re.sub(r'"[^"]*"|\\.|_.|\*.', "", pattern)
                    pattern = re.sub(r"\[(?![hms]+\])[^\]]*\]", "", pattern, flags=re.I)
                    if kind in DATE_FORMATS or re.search(r"[ymdhs]", pattern, re.I):
                        self.date_styles.add(index)
        except (
            zipfile.BadZipFile,
            OSError,
            KeyError,
            ValueError,
            ET.ParseError,
            RuntimeError,
            zlib.error,
        ) as exc:
            raise _error() from exc

    def _xml(self, name):
        try:
            info = self.archive.getinfo(name)
            if info.file_size > MAX_XML_BYTES:
                raise _error()
            raw = self.archive.read(name).decode("utf-8-sig")
            encoding = re.match(r"<\?xml\b[^?]*encoding=[\"\']([^\"\']+)", raw, re.I)
            if encoding and encoding[1].lower() not in {"utf-8", "utf8", "us-ascii"}:
                raise _error()
            if "<!DOCTYPE" in raw.upper() or "<!ENTITY" in raw.upper() or "\x00" in raw:
                raise _error()
            return ET.fromstring(raw)
        except (
            zipfile.BadZipFile,
            OSError,
            KeyError,
            ValueError,
            ET.ParseError,
            RuntimeError,
            zlib.error,
        ) as exc:
            raise _error() from exc

    def _cell(self, cell, sheet):
        label = cell.attrib["r"]
        kind = cell.get("t", "n")
        value = cell.findtext(f"{{{NS}}}v")
        if kind == "inlineStr":
            inline = cell.find(f"{{{NS}}}is")
            if inline is None:
                raise _error("cell", sheet=sheet, cell=label, kind=kind)
            return Cell(label, "string", _text(inline))
        if kind == "s":
            if (
                value is None
                or not re.fullmatch(r"0|[1-9][0-9]*", value)
                or int(value) >= len(self.shared)
            ):
                raise _error("cell", sheet=sheet, cell=label, kind=kind)
            return Cell(label, "string", self.shared[int(value)])
        if kind == "str":
            # Formula-string caches without a formula declaration are not static
            # text cells. A values-only export should use shared/inline strings.
            raise _error("cell", sheet=sheet, cell=label, kind=kind)
        if kind not in {"n"}:
            raise _error("cell", sheet=sheet, cell=label, kind=kind)
        style = cell.get("s", "0")
        if not re.fullmatch(r"0|[1-9][0-9]*", style) or int(style) >= self.style_count:
            raise _error()
        if int(style) in self.date_styles:
            raise _error("date", sheet=sheet, cell=label)
        return Cell(label, "number" if value is not None else "missing", value)

    def table(self, sheet, cell_range):
        if sheet not in self.sheets:
            raise _error("sheet", sheet=sheet, choices=", ".join(self.sheets))
        selected = bounds(cell_range, table=True)
        document = self._xml(self.sheets[sheet])
        if document.tag != f"{{{NS}}}worksheet":
            raise _error()
        for merged in document.findall(f"{{{NS}}}mergeCells/{{{NS}}}mergeCell"):
            reference = merged.get("ref", "")
            if _intersects(bounds(reference), selected):
                raise _error("merged", sheet=sheet, cell=reference)
        cells = {}
        for row in document.findall(f"{{{NS}}}sheetData/{{{NS}}}row"):
            for cell in row.findall(f"{{{NS}}}c"):
                label = cell.get("r", "")
                x, y = coordinate(label)
                formula = cell.find(f"{{{NS}}}f")
                if formula is not None:
                    affected = bounds(formula.get("ref", label))
                    if _intersects(affected, selected) or _intersects((x, y, x, y), selected):
                        raise _error("formula", sheet=sheet, cell=label)
                if selected[0] <= x <= selected[2] and selected[1] <= y <= selected[3]:
                    if (x, y) in cells:
                        raise _error()
                    try:
                        cells[x, y] = self._cell(cell, sheet)
                    except (KeyError, ValueError) as exc:
                        raise _error() from exc

        def at(column, row):
            return cells.get((column, row), Cell(address(column, row), "missing", None))

        left, top, right, bottom = selected
        headings = [at(column, top) for column in range(left, right + 1)]
        if any(
            cell.kind != "string" or not cell.value or not cell.value.strip() for cell in headings
        ):
            raise _error("header")
        names = [cell.value for cell in headings]
        if len(names) != len(set(names)):
            raise _error("header")
        rows = [
            {name: at(column, row) for column, name in enumerate(names, left)}
            for row in range(top + 1, bottom + 1)
        ]
        return StaticTable(sheet, cell_range, names, rows)


def read_xlsx(raw, sheet, cell_range):
    return Workbook(raw).table(sheet, cell_range)
