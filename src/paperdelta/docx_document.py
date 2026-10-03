"""Bounded OOXML inspection. No Word process, page estimation or document writes."""

from __future__ import annotations

import io
import re
import zipfile
import zlib

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg
from paperdelta.native_document import NativeDocument

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
M = "http://schemas.openxmlformats.org/officeDocument/2006/math"
NS = {"w": W}


def tag(name):
    return f"{{{W}}}{name}"


class DocxDocument(NativeDocument):
    def __init__(self, file, raw):
        try:
            import docx
            from lxml import etree
        except ImportError as exc:
            raise PaperDeltaError(
                "DOCUMENT_DEPENDENCY", msg("document.dependency", extra="docx")
            ) from exc
        super().__init__(
            file,
            raw,
            "docx",
            f"paperdelta-docx/1;python-docx/{docx.__version__};lxml/{etree.LXML_VERSION[0]}.{etree.LXML_VERSION[1]}.{etree.LXML_VERSION[2]}",
        )
        self.paragraph_count = 0
        self.table_count = 0
        self.section: list[str] = []
        self.field_depth = 0
        self.styles = {}
        self.style_nodes = {}
        self.defaults = []
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                entries = archive.infolist()
                if (
                    len(raw) > 32 * 1024 * 1024
                    or len(entries) > 2000
                    or len({i.filename for i in entries}) != len(entries)
                    or sum(i.file_size for i in entries) > 64 * 1024 * 1024
                    or any(i.file_size > 16 * 1024 * 1024 or i.flag_bits & 1 for i in entries)
                ):
                    raise ValueError("package limits")

                def xml(name):
                    data = archive.read(name)
                    if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)", data, re.I):
                        raise ValueError("XML declarations")
                    parser = etree.XMLParser(
                        resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False
                    )
                    root = etree.fromstring(data, parser)
                    if root.getroottree().docinfo.doctype:
                        raise ValueError("XML declarations")
                    return root

                if "word/styles.xml" in archive.namelist():
                    styles = xml("word/styles.xml")
                    defaults = styles.find("w:docDefaults", NS)
                    self.defaults = list(defaults.iter()) if defaults is not None else []
                    for style in styles.findall("w:style", NS):
                        name = style.find("w:name", NS)
                        self.style_nodes[style.get(tag("styleId"))] = style
                        self.styles[style.get(tag("styleId"))] = (
                            name.get(tag("val"), "") if name is not None else ""
                        )
                root = xml("word/document.xml")
                body = root.find("w:body", NS)
                if root.tag != tag("document") or body is None:
                    raise ValueError("document body")
                for child in body:
                    if child.tag == tag("p"):
                        self._paragraph(child)
                    elif child.tag == tag("tbl"):
                        self._table(child)
                    elif child.tag != tag("sectPr"):
                        self._unsupported_container(child)
                for entry in entries:
                    if re.fullmatch(
                        r"word/(?:header\d+|footer\d+|footnotes|endnotes|comments)\.xml",
                        entry.filename,
                    ):
                        part = xml(entry.filename)
                        if any((node.text or "").strip() for node in part.iter(tag("t"))):
                            self.issue("DOCX_UNSUPPORTED_PART", part=entry.filename)
                if self.field_depth:
                    self.issue("DOCX_FIELD_BALANCE")
                    self.blocks = [
                        type(b)(b.start, b.end, b.identity, b.locator, False) for b in self.blocks
                    ]
        except (
            zipfile.BadZipFile,
            KeyError,
            ValueError,
            RuntimeError,
            OSError,
            etree.XMLSyntaxError,
            zlib.error,
        ) as exc:
            raise PaperDeltaError("DOCX_PARSE", msg("document.DOCX_PARSE", file=file)) from exc

    def _unsupported_container(self, node):
        self.issue("DOCX_UNSUPPORTED_STRUCTURE", kind=node.tag.rsplit("}", 1)[-1])
        for paragraph in node.iter(tag("p")):
            # Nested textbox paragraphs belong to their containing paragraph.
            if not any(parent.tag == tag("p") for parent in paragraph.iterancestors()):
                self._paragraph(paragraph, forced=True)

    def _paragraph(self, node, *, cell=None, forced=False):
        self.paragraph_count += 1
        ordinal = self.paragraph_count
        style_node = node.find("w:pPr/w:pStyle", NS)
        style_id = style_node.get(tag("val"), "") if style_node is not None else ""
        style = self.styles.get(style_id, style_id)
        inherited = list(self.defaults)
        for identity in [
            style_id or "Normal",
            *[item.get(tag("val")) for item in node.iter(tag("rStyle"))],
        ]:
            seen = set()
            while identity in self.style_nodes:
                if identity in seen or len(seen) >= 40:
                    self.issue("DOCX_UNSUPPORTED_STRUCTURE", kind="style-inheritance")
                    forced = True
                    break
                seen.add(identity)
                definition = self.style_nodes[identity]
                inherited.extend(definition.iter())
                parent = definition.find("w:basedOn", NS)
                identity = parent.get(tag("val")) if parent is not None else None
        text = "".join(
            item.text or ""
            if item.tag in {tag("t"), tag("delText")}
            else "\t"
            if item.tag == tag("tab") and item.getparent().tag == tag("r")
            else "\n"
            if item.tag in {tag("br"), tag("cr")}
            else ""
            for item in node.iter()
        )
        kinds = set()
        tags = {item.tag for item in node.iter()}
        formatting = [*node.iter(), *inherited]
        if tags & {
            tag(n)
            for n in ("ins", "del", "moveFrom", "moveTo", "rPrChange", "pPrChange", "delText")
        }:
            kinds.add("revision")
        if tags & {tag(n) for n in ("fldSimple", "fldChar", "instrText")} or self.field_depth:
            kinds.add("field")
        for item in node.iter(tag("fldChar")):
            value = item.get(tag("fldCharType"))
            if value == "begin":
                self.field_depth += 1
            elif value == "end":
                if self.field_depth == 0:
                    kinds.add("field")
                    self.issue("DOCX_FIELD_BALANCE")
                self.field_depth = max(0, self.field_depth - 1)
        if any(t.startswith(f"{{{M}}}") for t in tags):
            kinds.add("equation")
        if tags & {tag(n) for n in ("txbxContent", "pict", "drawing", "object")}:
            kinds.add("drawing")
        if tags & {tag(n) for n in ("sdt", "sym", "altChunk", "subDoc")} or any(
            item.tag in {tag("vanish"), tag("webHidden")}
            and item.get(tag("val"), "1") not in {"0", "false", "off"}
            for item in formatting
        ):
            kinds.add("special-content")
        if any(item.tag == tag("numPr") for item in formatting):
            kinds.add("numbering")
        if any(
            item.tag == tag("vertAlign") and item.get(tag("val")) != "baseline"
            for item in formatting
        ):
            kinds.add("equation")
        if tags & {tag(n) for n in ("footnoteReference", "endnoteReference")}:
            kinds.add("note-reference")
        heading = re.fullmatch(r"(?:heading|标题)\s*([1-9])", style, re.I)
        outline = node.find("w:pPr/w:outlineLvl", NS)
        if outline is None:
            outline = next((item for item in inherited if item.tag == tag("outlineLvl")), None)
        if heading or (
            outline is not None
            and outline.get(tag("val"), "9").isdigit()
            and int(outline.get(tag("val"), "9")) < 9
        ):
            level = int(heading[1]) if heading else int(outline.get(tag("val"))) + 1
            self.section = self.section[: level - 1] + [text]
        locator = {
            "part": "word/document.xml",
            "paragraph": ordinal,
            "style": style,
            "section": list(self.section),
            **(cell or {}),
        }
        block = self.add_block(
            text,
            locator,
            supported=not (forced or kinds),
            identity_context={"part": locator["part"], "section": self.section, "style": style},
        )
        for kind in sorted(kinds):
            self.issue(
                "DOCX_UNSUPPORTED_PARAGRAPH", paragraph=ordinal, kind=msg("document.kind." + kind)
            )
        if style.casefold() in {"abstract", "摘要"} or any(
            s.strip().casefold() in {"abstract", "摘要"} for s in self.section
        ):
            self.priority_regions.append((block.start, block.end, "abstract"))
        return block

    def _table(self, table):
        self.table_count += 1
        ordinal = self.table_count
        rows = table.findall("w:tr", NS)
        grid = table.findall("w:tblGrid/w:gridCol", NS)
        complex_tags = {
            tag(n)
            for n in (
                "gridSpan",
                "vMerge",
                "hMerge",
                "gridBefore",
                "gridAfter",
                "ins",
                "del",
                "sdt",
                "tblPrChange",
                "trPrChange",
                "tcPrChange",
            )
        }
        complex_table = (
            any(item.tag in complex_tags for item in table.iter())
            or len(list(table.iter(tag("tbl")))) != 1
            or not grid
            or not rows
            or any(len(row.findall("w:tc", NS)) != len(grid) for row in rows)
        )
        if complex_table:
            self.issue("DOCX_COMPLEX_TABLE", table=ordinal)
            for paragraph in table.iter(tag("p")):
                self._paragraph(paragraph, forced=True)
            return
        start = len(self.text)
        cells = []
        for row_index, row in enumerate(rows, 1):
            current = []
            for col, cell in enumerate(row.findall("w:tc", NS), 1):
                low = len(self.text)
                for child in cell:
                    if child.tag == tag("p"):
                        self._paragraph(
                            child, cell={"table": ordinal, "row": row_index, "cell": col}
                        )
                    elif child.tag != tag("tcPr"):
                        self._unsupported_container(child)
                current.append((low, len(self.text)))
            cells.append(current)
        self.native_tables.append(cells)
        self.table_regions.append((start, len(self.text)))
        self.priority_regions.append((start, len(self.text), "table"))
