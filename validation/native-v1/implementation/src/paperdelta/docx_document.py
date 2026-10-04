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
            f"paperdelta-docx/2;python-docx/{docx.__version__};lxml/{etree.LXML_VERSION[0]}.{etree.LXML_VERSION[1]}.{etree.LXML_VERSION[2]}",
        )
        self.paragraph_count = 0
        self.table_count = 0
        self.section: list[str] = []
        self.field_depth = 0
        self.styles = {}
        self.style_nodes = {}
        self.defaults = []
        self.part = "word/document.xml"
        self.note_id = None
        self.notes = {}
        self.visible_notes = set()
        self.native_table_metadata = {}
        self.uses_layout_v2 = False
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
                linked_notes, seen_notes = set(), set()
                if "word/_rels/document.xml.rels" in archive.namelist():
                    relations = xml("word/_rels/document.xml.rels")
                    for relation in relations:
                        for kind in ("footnote", "endnote"):
                            if (
                                relation.get("Type")
                                == "http://schemas.openxmlformats.org/officeDocument/2006/relationships/"
                                + kind
                                + "s"
                            ):
                                if kind in seen_notes:
                                    raise ValueError("duplicate note relationship")
                                seen_notes.add(kind)
                                if relation.get("TargetMode") == "External" or relation.get(
                                    "Target"
                                ) not in {kind + "s.xml", "/word/" + kind + "s.xml"}:
                                    self.issue(
                                        "DOCX_UNSUPPORTED_PART", part=kind + "s relationship"
                                    )
                                else:
                                    linked_notes.add(kind)
                for kind in sorted(linked_notes):
                    name = f"word/{kind}s.xml"
                    if name not in archive.namelist():
                        continue
                    part = xml(name)
                    if part.tag != tag(kind + "s"):
                        raise ValueError("note part root")
                    for note in part.findall("w:" + kind, NS):
                        if note.get(tag("type"), "normal") != "normal":
                            continue
                        identity = note.get(tag("id"), "")
                        if not identity.isdecimal() or len(identity) > 9:
                            raise ValueError("note identity")
                        key = kind, int(identity)
                        if key in self.notes:
                            raise ValueError("duplicate note identity")
                        self.notes[key] = note
                root = xml("word/document.xml")
                body = root.find("w:body", NS)
                if root.tag != tag("document") or body is None:
                    raise ValueError("document body")
                referenced = {
                    (kind, int(reference.get(tag("id"))))
                    for kind in ("footnote", "endnote")
                    for reference in body.iter(tag(kind + "Reference"))
                    if reference.get(tag("id"), "").isdecimal()
                    and len(reference.get(tag("id"))) <= 9
                }
                self.notes = {key: note for key, note in self.notes.items() if key in referenced}
                for child in body:
                    if child.tag == tag("p"):
                        self._paragraph(child)
                    elif child.tag == tag("tbl"):
                        self._table(child)
                    elif child.tag != tag("sectPr"):
                        self._unsupported_container(child)
                if self.field_depth:
                    self.issue("DOCX_FIELD_BALANCE")
                    self.blocks = [
                        type(b)(b.start, b.end, b.identity, b.locator, False) for b in self.blocks
                    ]
                    self.field_depth = 0
                    self.visible_notes.clear()
                self.notes = {
                    key: note for key, note in self.notes.items() if key in self.visible_notes
                }
                self.uses_layout_v2 |= bool(self.notes)
                # Note bodies have independent original-part/ID/paragraph locations.
                for (kind, identity), note in self.notes.items():
                    self.part, self.note_id = f"word/{kind}s.xml", identity
                    self.paragraph_count, self.section, self.field_depth = 0, [], 0
                    for child in note:
                        if child.tag == tag("p"):
                            self._paragraph(child)
                        else:
                            self._unsupported_container(child)
                    if self.field_depth:
                        self.issue("DOCX_FIELD_BALANCE")
                        self.blocks = [
                            type(b)(b.start, b.end, b.identity, b.locator, False)
                            if b.locator.get("part") == self.part
                            and b.locator.get("note_id") == identity
                            else b
                            for b in self.blocks
                        ]
                self.part, self.note_id = "word/document.xml", None
                for entry in entries:
                    if re.fullmatch(
                        r"word/(?:header\d+|footer\d+|comments|footnotes|endnotes)\.xml",
                        entry.filename,
                    ) and entry.filename not in {f"word/{kind}s.xml" for kind in linked_notes}:
                        part = xml(entry.filename)
                        if any((node.text or "").strip() for node in part.iter(tag("t"))):
                            self.issue("DOCX_UNSUPPORTED_PART", part=entry.filename)
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
        reference_tags = {
            tag(n) for n in ("footnoteReference", "endnoteReference", "footnoteRef", "endnoteRef")
        }
        marker_runs = {
            run
            for run in node.iter(tag("r"))
            if any(child.tag in reference_tags for child in run)
            and not any((child.text or "").strip() for child in run.iter(tag("t")))
            and not any(
                child.tag in {tag("drawing"), tag("object"), tag("pict")} for child in run.iter()
            )
        }
        inherited = list(self.defaults)
        for identity, marker_style in [
            (style_id or "Normal", False),
            *[
                (
                    item.get(tag("val")),
                    any(parent in marker_runs for parent in item.iterancestors()),
                )
                for item in node.iter(tag("rStyle"))
            ],
        ]:
            seen = set()
            while identity in self.style_nodes:
                if identity in seen or len(seen) >= 40:
                    self.issue("DOCX_UNSUPPORTED_STRUCTURE", kind="style-inheritance")
                    forced = True
                    break
                seen.add(identity)
                definition = self.style_nodes[identity]
                inherited.extend(
                    item
                    for item in definition.iter()
                    if not (marker_style and item.tag == tag("vertAlign"))
                )
                parent = definition.find("w:basedOn", NS)
                identity = parent.get(tag("val")) if parent is not None else None
        text = "".join(
            item.text or ""
            if item.tag in {tag("t"), tag("delText")}
            else "\t"
            if item.tag == tag("tab") and item.getparent().tag == tag("r")
            else "\n"
            if item.tag in {tag("br"), tag("cr")}
            else "\ufffc"
            if item.tag in reference_tags
            else ""
            for item in node.iter()
        )
        kinds = set()
        tags = {item.tag for item in node.iter()}
        formatting = [
            *[
                item
                for item in node.iter()
                if not (
                    item.tag == tag("vertAlign")
                    and any(parent in marker_runs for parent in item.iterancestors())
                )
            ],
            *inherited,
        ]
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
        for kind in ("footnote", "endnote"):
            for reference in node.iter(tag(kind + "Reference")):
                identity = reference.get(tag("id"), "")
                if (
                    not identity.isdecimal()
                    or len(identity) > 9
                    or (kind, int(identity)) not in self.notes
                ):
                    kinds.add("note-reference")
            if tag(kind + "Ref") in tags and self.part != f"word/{kind}s.xml":
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
            "part": self.part,
            "paragraph": ordinal,
            "style": style,
            "section": list(self.section),
            **(cell or {}),
            **({"note_id": self.note_id} if self.note_id is not None else {}),
        }
        block = self.add_block(
            text,
            locator,
            supported=not (forced or kinds),
            identity_context={
                "part": locator["part"],
                "section": self.section,
                "style": style,
                **({"note_id": self.note_id} if self.note_id is not None else {}),
            },
        )
        for kind in sorted(kinds):
            self.issue(
                "DOCX_UNSUPPORTED_PARAGRAPH", paragraph=ordinal, kind=msg("document.kind." + kind)
            )
        if block.supported and self.part == "word/document.xml":
            for kind in ("footnote", "endnote"):
                self.visible_notes.update(
                    (kind, int(ref.get(tag("id")))) for ref in node.iter(tag(kind + "Reference"))
                )
        if style.casefold() in {"abstract", "摘要"} or any(
            s.strip().casefold() in {"abstract", "摘要"} for s in self.section
        ):
            self.priority_regions.append((block.start, block.end, "abstract"))
        return block

    def _table(self, table):
        from paperdelta.word_tables import table_grid

        self.table_count += 1
        ordinal = self.table_count
        try:
            physical, logical = table_grid(table)
        except (ValueError, TypeError):
            self.issue("DOCX_COMPLEX_TABLE", table=ordinal)
            for paragraph in table.iter(tag("p")):
                self._paragraph(paragraph, forced=True)
            return
        caption = next(
            (
                self.text[b.start : b.end]
                for b in reversed(self.blocks)
                if self.text[b.start : b.end].strip()
            ),
            "",
        )
        caption = (
            caption
            if len(caption) <= 2000
            and re.match(r"(?:S?\d+\s*Table|Table\s*S?\d+|表\s*\d+)", caption, re.I)
            else None
        )
        start, owners = len(self.text), {}
        self.uses_layout_v2 |= any(
            cell.span != 1 or cell.owner != (row_index, cell.column)
            for row_index, row in enumerate(physical, 1)
            for cell in row
        )
        for row_index, row in enumerate(physical, 1):
            for cell in row:
                if cell.span > 1:
                    from paperdelta.native_document import NUMBER_PATTERN

                    if any(NUMBER_PATTERN.search(p.text or "") for p in cell.node.iter(tag("t"))):
                        self.issue("DOCX_MERGED_VALUE", table=ordinal, row=row_index)
                low = len(self.text)
                for child in cell.node:
                    if child.tag == tag("p"):
                        self._paragraph(
                            child,
                            cell={
                                "table": ordinal,
                                "row": row_index,
                                "cell": cell.column,
                                **({"column_span": cell.span} if cell.span != 1 else {}),
                            },
                            forced=cell.span > 1,
                        )
                    elif child.tag != tag("tcPr"):
                        self._unsupported_container(child)
                if cell.owner == (row_index, cell.column):
                    owners[cell.owner] = (low, len(self.text))
        cells = [[owners[owner] for owner in row] for row in logical]
        self.native_tables.append(cells)
        self.native_table_metadata[id(cells)] = {"caption": caption}
        self.table_regions.append((start, len(self.text)))
        self.priority_regions.append((start, len(self.text), "table"))
