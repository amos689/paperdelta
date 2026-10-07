"""Annotated copies at verified native positions; originals never change."""

from __future__ import annotations

import copy
import io
import posixpath
import re
from zipfile import ZIP_DEFLATED, ZipFile

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
COMMENTS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"


def error(key):
    return PaperDeltaError("ANNOTATION_" + key.upper(), msg("annotation." + key))


def _xml(raw):
    from lxml import etree

    if re.search(rb"<!\s*(?:DOCTYPE|ENTITY)", raw, re.I):
        raise error("structure")
    root = etree.fromstring(
        raw, etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False)
    )
    if root.getroottree().docinfo.doctype:
        raise error("structure")
    return root


def _run_text(run):
    output = []
    for node in run:
        if node.tag == f"{{{W}}}t":
            output.append(node.text or "")
        elif node.tag in {f"{{{W}}}tab", f"{{{W}}}br", f"{{{W}}}cr"}:
            output.append("\t" if node.tag.endswith("}tab") else "\n")
        elif node.tag in {
            f"{{{W}}}footnoteReference",
            f"{{{W}}}endnoteReference",
            f"{{{W}}}footnoteRef",
            f"{{{W}}}endnoteRef",
        }:
            output.append("\ufffc")
        elif node.tag not in {f"{{{W}}}rPr", f"{{{W}}}commentReference"}:
            raise error("structure")
    return "".join(output)


def _runs(paragraph):
    position = 0
    for run in paragraph.iter(f"{{{W}}}r"):
        text = _run_text(run)
        yield run, position, position + len(text), text
        position += len(text)


def _split(paragraph, offset):
    """Split a direct run at a text boundary, preserving every run property."""
    from lxml import etree

    for run, start, end, _ in _runs(paragraph):
        if not start < offset < end:
            continue
        if run.getparent() is not paragraph:
            raise error("structure")
        left = etree.Element(run.tag, dict(run.attrib))
        right = etree.Element(run.tag, dict(run.attrib))
        used, boundary = 0, offset - start
        for child in run:
            if child.tag == f"{{{W}}}rPr":
                left.append(copy.deepcopy(child))
                right.append(copy.deepcopy(child))
                continue
            length = (
                len(child.text or "")
                if child.tag == f"{{{W}}}t"
                else (0 if child.tag == f"{{{W}}}commentReference" else 1)
            )
            if used + length <= boundary:
                left.append(copy.deepcopy(child))
            elif used >= boundary:
                right.append(copy.deepcopy(child))
            elif child.tag == f"{{{W}}}t":
                for target, text in (
                    (left, child.text[: boundary - used]),
                    (right, child.text[boundary - used :]),
                ):
                    part = copy.deepcopy(child)
                    part.text = text
                    part.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                    target.append(part)
            else:
                raise error("structure")
            used += length
        index = paragraph.index(run)
        paragraph.remove(run)
        paragraph.insert(index, left)
        paragraph.insert(index + 1, right)
        return


def _anchor(paragraph, offset, text, identity):
    from lxml import etree

    end = offset + len(text)
    before = "".join(item[3] for item in _runs(paragraph))
    if offset < 0 or before[offset:end] != text:
        raise error("position")
    _split(paragraph, end)
    _split(paragraph, offset)
    runs = [r for r, a, b, _ in _runs(paragraph) if offset <= a < b <= end]
    if not runs or any(run.getparent() is not paragraph for run in runs):
        raise error("structure")
    if "".join(_run_text(run) for run in runs) != text:
        raise error("position")
    attributes = {f"{{{W}}}id": str(identity)}
    runs[0].addprevious(etree.Element(f"{{{W}}}commentRangeStart", attributes))
    stop = etree.Element(f"{{{W}}}commentRangeEnd", attributes)
    runs[-1].addnext(stop)
    reference = etree.Element(f"{{{W}}}r")
    properties = etree.SubElement(reference, f"{{{W}}}rPr")
    etree.SubElement(properties, f"{{{W}}}rStyle", {f"{{{W}}}val": "CommentReference"})
    etree.SubElement(reference, f"{{{W}}}commentReference", attributes)
    stop.addnext(reference)
    assert "".join(item[3] for item in _runs(paragraph)) == before


def word_copy(document, entries):
    """Keep every unrelated OPC part's original uncompressed bytes."""
    from lxml import etree

    with ZipFile(io.BytesIO(document.raw)) as source:
        if any(name.startswith("_xmlsignatures/") for name in source.namelist()):
            raise error("signed")
        body = _xml(source.read("word/document.xml"))
        relation_path = "word/_rels/document.xml.rels"
        relations = (
            _xml(source.read(relation_path))
            if relation_path in source.namelist()
            else etree.Element(f"{{{R}}}Relationships", nsmap={None: R})
        )
        linked = [r for r in relations if r.get("Type") == COMMENTS]
        if len(linked) > 1:
            raise error("structure")
        if linked:
            target = linked[0].get("Target", "")
            comments_path = (
                posixpath.normpath("word/" + target) if not target.startswith("/") else target[1:]
            )
            if linked[0].get("TargetMode") == "External" or comments_path not in source.namelist():
                raise error("structure")
            comments = _xml(source.read(comments_path))
            if comments.tag != f"{{{W}}}comments":
                raise error("structure")
        else:
            comments_path = "word/paperdelta-comments.xml"
            if comments_path in source.namelist():
                raise error("structure")
            comments = etree.Element(f"{{{W}}}comments", nsmap={"w": W})
            ids = {r.get("Id") for r in relations}
            number = 1
            while f"rIdPaperDelta{number}" in ids:
                number += 1
            etree.SubElement(
                relations,
                f"{{{R}}}Relationship",
                {
                    "Id": f"rIdPaperDelta{number}",
                    "Type": COMMENTS,
                    "Target": comments_path.removeprefix("word/"),
                },
            )
        existing = [
            node.get(f"{{{W}}}id")
            for root in (body, comments)
            for node in root.iter()
            if node.tag
            in {
                f"{{{W}}}comment",
                f"{{{W}}}commentRangeStart",
                f"{{{W}}}commentRangeEnd",
                f"{{{W}}}commentReference",
            }
        ]
        if any(value is None or not value.isdecimal() or len(value) > 9 for value in existing):
            raise error("structure")
        identity = max(map(int, existing), default=-1) + 1
        for entry in entries:
            location = entry["location"]["locator"]
            if location["part"] != "word/document.xml" or "note_id" in location:
                raise error("part")
            path = document.paragraph_paths.get((location["part"], None, location["paragraph"]))
            paragraph = body.find(path) if path is not None else None
            if paragraph is None:
                raise error("position")
            _anchor(paragraph, location["offset"], entry["actual"], identity)
            comment = etree.SubElement(
                comments,
                f"{{{W}}}comment",
                {
                    f"{{{W}}}id": str(identity),
                    f"{{{W}}}author": "PaperDelta",
                    f"{{{W}}}initials": "PD",
                },
            )
            for line in entry["note"].splitlines():
                run = etree.SubElement(etree.SubElement(comment, f"{{{W}}}p"), f"{{{W}}}r")
                etree.SubElement(run, f"{{{W}}}t").text = line
            identity += 1
        types = _xml(source.read("[Content_Types].xml"))
        if not any(item.get("PartName") == "/" + comments_path for item in types):
            etree.SubElement(
                types,
                f"{{{CT}}}Override",
                {
                    "PartName": "/" + comments_path,
                    "ContentType": (
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.comments+xml"
                    ),
                },
            )
        changed = {
            "word/document.xml": body,
            comments_path: comments,
            relation_path: relations,
            "[Content_Types].xml": types,
        }
        output = io.BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as dest:
            for item in source.infolist():
                if item.filename not in changed:
                    dest.writestr(item, source.read(item.filename))
            for name, root in changed.items():
                dest.writestr(name, etree.tostring(root, encoding="UTF-8", xml_declaration=True))
        return output.getvalue()


def pdf_copy(document, entries):
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.annotations import Highlight
        from pypdf.generic import ArrayObject, FloatObject, NameObject, TextStringObject
    except ImportError as exc:
        raise PaperDeltaError(
            "DOCUMENT_DEPENDENCY", msg("document.dependency", extra="pdf")
        ) from exc

    reader = PdfReader(io.BytesIO(document.raw))
    if reader.is_encrypted or "/Perms" in reader.root_object:
        raise error("signed")
    writer = PdfWriter(clone_from=reader)
    for entry in entries:
        location = entry["location"]["locator"]
        number = location["page"]
        page = reader.pages[number - 1]
        geometry = document.geometries[number]
        a, b, c, d = geometry.box(tuple(map(float, location["bbox"])), inverse=True)
        height = float(page.mediabox.top) - float(page.mediabox.bottom)
        bottom, top = height - d, height - b
        annotation = Highlight(
            rect=(a, bottom, c, top),
            quad_points=ArrayObject(
                [FloatObject(x) for x in (a, top, c, top, a, bottom, c, bottom)]
            ),
            highlight_color="FFD166",
        )
        annotation[NameObject("/Contents")] = TextStringObject(entry["note"])
        annotation[NameObject("/T")] = TextStringObject("PaperDelta")
        writer.add_annotation(number - 1, annotation)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()
