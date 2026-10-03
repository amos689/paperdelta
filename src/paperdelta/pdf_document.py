"""Conservative text-PDF inspection with original page coordinates and glyph identity."""

from __future__ import annotations

import io
import math
import re
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.native_document import NativeDocument


def coordinate(value):
    if not math.isfinite(value):
        raise ValueError("nonfinite PDF coordinate")
    return Decimal(str(round(value, 4)))


def box_union(boxes):
    return [
        coordinate(min(b[0] for b in boxes)),
        coordinate(min(b[1] for b in boxes)),
        coordinate(max(b[2] for b in boxes)),
        coordinate(max(b[3] for b in boxes)),
    ]


def contained(box, outer):
    return outer[0] <= box[0] < box[2] <= outer[2] and outer[1] <= box[1] < box[3] <= outer[3]


def overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


class PdfDocument(NativeDocument):
    def __init__(self, file, raw, regions=()):
        try:
            import pdfminer
            import pdfplumber
        except ImportError as exc:
            raise PaperDeltaError(
                "DOCUMENT_DEPENDENCY", msg("document.dependency", extra="pdf")
            ) from exc
        super().__init__(
            file,
            raw,
            "pdf",
            f"paperdelta-pdf/1;pdfplumber/{pdfplumber.__version__};pdfminer/{pdfminer.__version__}",
        )
        self.char_boxes = []
        self.page_boxes = {}
        self.table_scopes = {}
        self.regions = list(regions)
        self.image_boxes = {}
        self.unreliable_pages = set()
        self._reported = set()
        self.dynamic = False
        try:
            if len(raw) > 32 * 1024 * 1024:
                raise ValueError("PDF size limit")
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                if len(pdf.pages) > 200:
                    raise ValueError("PDF page limit")
                if any(region.page > len(pdf.pages) for region in regions):
                    raise PaperDeltaError("PDF_REGION", msg("pdf.region_page", file=file))
                if any(
                    key in pdf.doc.catalog
                    for key in ("AcroForm", "OpenAction", "AA", "OCProperties")
                ):
                    self.issue("PDF_DYNAMIC_CONTENT")
                    self.dynamic = True
                for page in pdf.pages:
                    self._page(page)
                    page.close()
        except PaperDeltaError:
            raise
        except Exception as exc:
            raise PaperDeltaError("PDF_PARSE", msg("document.PDF_PARSE", file=file)) from exc

    def issue(self, code, **params):
        identity = (code, tuple(params.items()))
        if identity not in self._reported:
            self._reported.add(identity)
            super().issue(code, **params)

    def _page(self, page):
        number = page.page_number
        box = tuple(page.bbox)
        self.page_boxes[number] = [coordinate(v) for v in box]
        if (
            page.rotation
            or tuple(page.cropbox) != tuple(page.mediabox)
            or box[:2] != (0, 0)
            or not 0 < page.width <= 20000
            or not 0 < page.height <= 20000
        ):
            self.issue("PDF_PAGE_GEOMETRY", page=number)
            return
        if len(page.chars) > 100000:
            raise ValueError("PDF glyph limit")
        if not page.chars:
            self.issue("PDF_NO_TEXT", page=number)
            return
        if page.images:
            self.issue("PDF_IMAGE_CONTENT", page=number)
        self.image_boxes[number] = [self._word_box(item) for item in page.images]
        from pdfminer.pdftypes import resolve1

        streams = [resolve1(item).get_data() for item in page.page_obj.contents]
        resources = resolve1(page.page_obj.resources)
        states = resolve1(resources.get("ExtGState", {}))
        # Graphics state opacity and XObject form text are not represented by the
        # character API. Fail closed instead of treating an invisible layer as prose.
        complex_state = any(
            resolve1(state).get("ca", 1) != 1
            or resolve1(state).get("CA", 1) != 1
            or "SMask" in resolve1(state)
            for state in states.values()
        )
        forms = any(
            str(resolve1(obj).get("Subtype")) == "/'Form'"
            for obj in resolve1(resources.get("XObject", {})).values()
        )
        if forms:
            from pdfminer.layout import LTFigure

            areas = [
                (figure.x0, page.height - figure.y1, figure.x1, page.height - figure.y0)
                for figure in page.layout
                if isinstance(figure, LTFigure)
            ]
            if areas:
                self.image_boxes[number].extend(areas)
                self.issue("PDF_FORM_CONTENT", page=number)
        if (
            self.dynamic
            or complex_state
            or any(
                re.search(rb"\b[3-7](?:\.0*)?\s*(?:%[^\r\n]*\s+)*Tr\b|\bW\*?\s+n\b", stream)
                for stream in streams
            )
        ):
            self.unreliable_pages.add(number)
            self.issue("PDF_UNRELIABLE_TEXT", page=number)
        self.unsafe_chars = self._ambiguous_glyphs(page.chars)
        regions = [region for region in self.regions if region.page == number]
        if len(page.edges) > 10000:
            raise ValueError("PDF edge limit")
        ruled_tables = page.find_tables(
            {"vertical_strategy": "lines", "horizontal_strategy": "lines"}
        )
        for region in regions:
            if not contained([float(v) for v in region.bbox], box):
                raise PaperDeltaError(
                    "PDF_REGION", msg("pdf.region_bounds", name=region.name, page=number)
                )
            if any(
                overlaps(region.bbox, table.bbox)
                and (region.kind != "table" or not contained(table.bbox, region.bbox))
                for table in ruled_tables
            ):
                raise PaperDeltaError("PDF_REGION", msg("pdf.region_table", name=region.name))
        if any(overlaps(a.bbox, b.bbox) for i, a in enumerate(regions) for b in regions[i + 1 :]):
            raise PaperDeltaError("PDF_REGION", msg("pdf.region_overlap", page=number))
        words = page.extract_words(
            return_chars=True, expand_ligatures=False, x_tolerance=2, y_tolerance=3
        )
        excluded = []
        if regions:
            for region in regions:
                bounds = tuple(float(v) for v in region.bbox)
                selected = [word for word in words if contained(self._word_box(word), bounds)]
                excluded.append(bounds)
                if region.kind == "table":
                    self._tables(page.crop(bounds), selected, number, region.name, required=True)
                else:
                    self._lines(selected, number, region.name, priority=region.kind)
        # All remaining content is still inspected; selecting an ROI never hides other failures.
        remaining = [
            word for word in words if not any(contained(self._word_box(word), b) for b in excluded)
        ]
        tables = self._tables(page, remaining, number, None, required=False, exclude=excluded)
        self._lines(
            [
                word
                for word in remaining
                if not any(contained(self._word_box(word), b) for b in tables)
            ],
            number,
            None,
        )

    @staticmethod
    def _word_box(word):
        return word["x0"], word["top"], word["x1"], word["bottom"]

    @staticmethod
    def _ambiguous_glyphs(chars):
        """Adjacent raised/lowered digits and overprinted glyphs are not plain numbers."""
        buckets, unsafe = defaultdict(list), set()
        for char in chars:
            if char["text"].isspace():
                continue
            x, y = int(char["x0"] // 64), int(char["top"] // 64)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for other in buckets[x + dx, y + dy]:
                        vertical = min(char["bottom"], other["bottom"]) - max(
                            char["top"], other["top"]
                        )
                        gap = max(char["x0"], other["x0"]) - min(char["x1"], other["x1"])
                        raised = (
                            (any(c.isdigit() for c in char["text"] + other["text"]))
                            and vertical > 0
                            and gap <= 2
                            and abs(char["bottom"] - other["bottom"])
                            > max(1, 0.2 * min(char["size"], other["size"]))
                        )
                        duplicate = (
                            vertical > min(char["size"], other["size"]) * 0.7
                            and gap < -min(char["x1"] - char["x0"], other["x1"] - other["x0"]) * 0.5
                        )
                        if raised or duplicate:
                            unsafe.update((id(char), id(other)))
            bucket = buckets[x, y]
            if len(bucket) >= 1000:
                raise ValueError("PDF overlapping glyph limit")
            bucket.append(char)
        return unsafe

    def _tables(self, page, words, number, region, *, required, exclude=()):
        found = page.find_tables({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
        accepted = []
        for table in found:
            if any(overlaps(table.bbox, area) for area in exclude):
                continue
            rows = table.rows
            if (
                not rows
                or len(rows) < 2
                or len(rows[0].cells) < 2
                or any(
                    len(row.cells) != len(rows[0].cells) or any(cell is None for cell in row.cells)
                    for row in rows
                )
            ):
                self.issue("PDF_COMPLEX_TABLE", page=number)
                self._lines(
                    [word for word in words if contained(self._word_box(word), table.bbox)],
                    number,
                    region,
                    forced=True,
                )
                accepted.append(table.bbox)
                continue
            selected_words = [word for word in words if contained(self._word_box(word), table.bbox)]
            if any(
                sum(contained(self._word_box(word), cell) for row in rows for cell in row.cells)
                != 1
                for word in selected_words
            ):
                self.issue("PDF_COMPLEX_TABLE", page=number)
                self._lines(selected_words, number, region, forced=True)
                accepted.append(table.bbox)
                continue
            start, cells = len(self.text), []
            table_index = len(self.native_tables) + 1
            for row_index, row in enumerate(rows, 1):
                cell_ranges = []
                for column, bounds in enumerate(row.cells, 1):
                    low = len(self.text)
                    selected = [word for word in words if contained(self._word_box(word), bounds)]
                    self._lines(
                        selected,
                        number,
                        region,
                        cell={"table": table_index, "row": row_index, "cell": column},
                    )
                    cell_ranges.append((low, len(self.text)))
                cells.append(cell_ranges)
            self.native_tables.append(cells)
            self.table_scopes[id(cells)] = {"page": number, "region": region, "parser": self.parser}
            self.table_regions.append((start, len(self.text)))
            self.priority_regions.append((start, len(self.text), "table"))
            accepted.append(table.bbox)
        if required and not accepted:
            self.issue("PDF_COMPLEX_TABLE", page=number)
            # Keep the selected text visible but uncheckable.
            self._lines(words, number, region, forced=True)
        return accepted

    def _lines(self, words, page, region, *, cell=None, priority=None, forced=False):
        rows = []
        for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
            row = next(
                (r for r in reversed(rows[-3:]) if abs(r[0]["bottom"] - word["bottom"]) <= 3), None
            )
            if row is None:
                rows.append([word])
            else:
                row.append(word)
        for row in rows:
            chunks = []
            for word in sorted(row, key=lambda w: w["x0"]):
                if not chunks or word["x0"] - chunks[-1][-1]["x1"] > max(
                    18, 3 * (word["bottom"] - word["top"])
                ):
                    chunks.append([word])
                else:
                    chunks[-1].append(word)
            for chunk in chunks:
                chars, boxes = [], []
                supported = not forced and page not in self.unreliable_pages
                for i, word in enumerate(chunk):
                    if i:
                        chars.append(" ")
                        boxes.append(None)
                    for char in word["chars"]:
                        value = char["text"]
                        bounds = (char["x0"], char["top"], char["x1"], char["bottom"])
                        if (
                            len(value) != 1
                            or "(cid:" in value
                            or "\ufffd" in value
                            or not char["upright"]
                            or id(char) in self.unsafe_chars
                            or not 3 <= char["size"] <= 128
                            or char.get("non_stroking_color") in ((1,), (1, 1, 1), (0, 0, 0, 0))
                            or not contained(bounds, self.page_boxes[page])
                            or any(overlaps(bounds, image) for image in self.image_boxes[page])
                        ):
                            supported = False
                        chars.extend(value)
                        boxes.extend([bounds] * len(value))
                text = "".join(chars)
                if not text.strip():
                    continue
                if not supported:
                    self.issue("PDF_UNRELIABLE_TEXT", page=page)
                locator = {
                    "page": page,
                    "page_box": self.page_boxes[page],
                    "bbox": box_union([b for b in boxes if b]),
                    **(cell or {}),
                }
                if region is not None:
                    locator["region"] = region
                block = self.add_block(
                    text,
                    locator,
                    supported=supported,
                    identity_context={
                        "page": page,
                        "region": region,
                        "kind": "cell" if cell else "line",
                    },
                )
                self.char_boxes.extend([*boxes, None])
                if priority == "abstract":
                    self.priority_regions.append((block.start, block.end, "abstract"))

    def span(self, start, end):
        result = super().span(start, end)
        boxes = [box for box in self.char_boxes[start:end] if box]
        if not boxes:
            raise PaperDeltaError("PDF_POSITION", msg("pdf.position", file=self.file))
        return replace(result, locator={**result.locator, "bbox": box_union(boxes)})

    def locate(self, anchor):
        identity = anchor.table.parser if anchor.table is not None else anchor.parser
        if identity != self.parser:
            raise PaperDeltaError(
                "PDF_EXTRACTION_CHANGED", msg("pdf.extraction_changed", file=self.file)
            )
        return super().locate(anchor)
