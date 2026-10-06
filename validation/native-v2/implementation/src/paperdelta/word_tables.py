"""Map ordinary OOXML horizontal/vertical merges to their original cell owners."""

from __future__ import annotations

from dataclasses import dataclass

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


@dataclass(frozen=True)
class Cell:
    node: object
    column: int
    physical: int
    span: int
    owner: tuple[int, int]


def table_grid(table):
    """A continued cell must exactly cover its predecessor and contain no text."""
    width = len(table.findall(W + "tblGrid/" + W + "gridCol"))
    rows = table.findall(W + "tr")
    forbidden = {
        W + name
        for name in (
            "hMerge",
            "ins",
            "del",
            "sdt",
            "tblPrChange",
            "trPrChange",
            "tcPrChange",
        )
    }
    if (
        not 0 < width <= 100
        or not rows
        or len(rows) > 10000
        or len(list(table.iter(W + "tbl"))) != 1
        or any(node.tag in forbidden for node in table.iter())
    ):
        raise ValueError("unsupported table grid")
    previous = {}
    parsed, logical = [], []
    for row_index, row in enumerate(rows, 1):
        props = row.find(W + "trPr")
        omitted = []
        for edge in ("gridBefore", "gridAfter"):
            value = props.find(W + edge) if props is not None else None
            count = int(value.get(W + "val", "")) if value is not None else 0
            if not 0 <= count < width:
                raise ValueError("invalid omitted edge cells")
            omitted.append(count)
        before, after = omitted
        column, cells, owners, active = before + 1, [], [None] * before, {}
        for physical, node in enumerate(row.findall(W + "tc"), 1):
            props = node.find(W + "tcPr")
            span_node = props.find(W + "gridSpan") if props is not None else None
            span = int(span_node.get(W + "val", "")) if span_node is not None else 1
            if not 1 <= span <= width or column + span - 1 > width:
                raise ValueError("invalid horizontal merge")
            merge_node = props.find(W + "vMerge") if props is not None else None
            merge = merge_node.get(W + "val", "continue") if merge_node is not None else None
            owner = (row_index, column)
            if merge == "continue":
                preceding = previous.get(column)
                if (
                    preceding is None
                    or preceding[1:] != (column, span)
                    or any(previous.get(c) != preceding for c in range(column, column + span))
                    or any((item.text or "").strip() for item in node.iter(W + "t"))
                    or any(
                        item.tag
                        in {
                            W + name
                            for name in (
                                "drawing",
                                "object",
                                "pict",
                                "footnoteReference",
                                "endnoteReference",
                                "fldChar",
                                "fldSimple",
                                "sym",
                                "tab",
                                "br",
                            )
                        }
                        for item in node.iter()
                    )
                ):
                    raise ValueError("invalid vertical continuation")
                owner = preceding[0]
            elif merge not in (None, "restart"):
                raise ValueError("invalid vertical merge")
            if merge is not None:
                active.update({c: (owner, column, span) for c in range(column, column + span)})
            cells.append(Cell(node, column, physical, span, owner))
            owners.extend([owner] * span)
            column += span
        if column + after != width + 1 or not cells:
            raise ValueError("incomplete table row")
        owners.extend([None] * after)
        parsed.append(cells)
        logical.append(owners)
        previous = active
    return parsed, logical
