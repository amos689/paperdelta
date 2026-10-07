"""Whole scientific values only when original run/glyph layout proves the exponent."""

import re
from statistics import median

MANTISSA = r"[+\-−]?(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)"
SCIENTIFIC = re.compile(rf"(?<![\w.]){MANTISSA}\s*×\s*10(?P<power>[+\-−]?[0-9]{{1,4}})(?![\w.])")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def canonical_scientific(text):
    mantissa, exponent = "".join(text.split()).replace("−", "-").split("×10")
    return mantissa + "e" + exponent


def word_scientific_ranges(paragraph, text, formatting):
    """Every non-baseline format must belong to a complete exponent, not a formula."""
    superscripts = [
        item
        for item in formatting
        if item.tag == W + "vertAlign" and item.get(W + "val") != "baseline"
    ]
    if not superscripts:
        return []
    matches = list(SCIENTIFIC.finditer(text))
    allowed = {i for match in matches for i in range(*match.span("power"))}
    positions, offset = {}, 0
    for item in paragraph.iter():
        if item.tag in {W + "t", W + "delText"}:
            positions[item] = set(range(offset, offset + len(item.text or "")))
            offset += len(item.text or "")
        elif item.tag in {
            W + n
            for n in (
                "tab",
                "br",
                "cr",
                "footnoteReference",
                "endnoteReference",
                "footnoteRef",
                "endnoteRef",
            )
        }:
            offset += 1
    covered = set()
    for item in superscripts:
        properties = item.getparent()
        run = properties.getparent() if properties is not None else None
        if (
            item.get(W + "val") != "superscript"
            or run is None
            or run.tag != W + "r"
            or paragraph not in run.iterancestors()
        ):
            return []
        indices = set().union(*(positions.get(node, set()) for node in run.iter(W + "t")))
        if not indices or not indices <= allowed:
            return []
        covered.update(indices)
    valid = [m for m in matches if set(range(*m.span("power"))) <= covered]
    if covered != {i for match in valid for i in range(*match.span("power"))}:
        return []
    return [match.span() for match in valid]


def pdf_scientific_glyphs(words):
    """Validate raised exponent glyphs against their adjacent baseline mantissa."""
    rows = []
    for word in sorted(words, key=lambda item: (item["bottom"], item["x0"])):
        row = next(
            (r for r in reversed(rows[-3:]) if abs(r[0]["bottom"] - word["bottom"]) <= 2), None
        )
        if row is None:
            rows.append([word])
        else:
            row.append(word)
    verified, powers, refused = set(), set(), set()
    groups = []
    for row in rows:
        text, glyphs = "", []
        for word in sorted(row, key=lambda item: item["x0"]):
            if text:
                text += " "
                glyphs.append(None)
            for char in word["chars"]:
                text += char["text"]
                glyphs.extend([char] * len(char["text"]))
        for match in SCIENTIFIC.finditer(text):
            base = [c for c in glyphs[match.start() : match.start("power")] if c]
            exponent = [c for c in glyphs[match.start("power") : match.end()] if c]
            chars = base + exponent
            size = median(c["size"] for c in base)
            bottom = median(c["bottom"] for c in base)
            ordered = sorted(chars, key=lambda c: c["x0"])
            valid = (
                3 <= size <= 128
                and all(len(c["text"]) == 1 and c["upright"] for c in chars)
                and all(
                    abs(c["size"] - size) <= size * 0.15 and abs(c["bottom"] - bottom) <= 1
                    for c in base
                )
                and all(
                    0.4 * size <= c["size"] <= 0.9 * size
                    and max(1, size * 0.15) <= bottom - c["bottom"] <= size * 0.8
                    for c in exponent
                )
                and all(
                    -0.1 <= b["x0"] - a["x1"] <= size * 0.8
                    for a, b in zip(ordered, ordered[1:], strict=False)
                )
            )
            if valid:
                groups.append(chars)
                verified.update(map(id, chars))
                powers.update(map(id, exponent))
            else:
                refused.update(map(id, chars))
    return verified, powers, refused, groups
