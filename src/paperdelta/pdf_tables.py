"""Complete only ruled table geometry; never infer columns from equal values."""

from __future__ import annotations


def cell_grid(cells):
    """Map closed cell rectangles to a gap-free, non-overlapping logical grid."""
    xs, ys = sorted({v for c in cells for v in c[::2]}), sorted({v for c in cells for v in c[1::2]})
    if not 2 < len(xs) <= 101 or not 2 < len(ys) <= 10001:
        raise ValueError("table grid limit")
    if (len(xs) - 1) * (len(ys) - 1) > 10000:
        raise ValueError("table cell limit")
    grid = [[None for _ in xs[:-1]] for _ in ys[:-1]]
    owners = []
    for bounds in cells:
        x0, x1, y0, y1 = (
            xs.index(bounds[0]),
            xs.index(bounds[2]),
            ys.index(bounds[1]),
            ys.index(bounds[3]),
        )
        owner = len(owners)
        owners.append((bounds, y0 + 1, x0 + 1, x1 - x0))
        for y in range(y0, y1):
            for x in range(x0, x1):
                if grid[y][x] is not None:
                    raise ValueError("overlapping table cells")
                grid[y][x] = owner
    if any(owner is None for row in grid for owner in row):
        raise ValueError("incomplete table grid")
    return owners, grid


def ruled_tables(page):
    """Open outer borders require the same drawn endpoint at EVERY row boundary."""
    from pdfplumber.table import Table

    finder = page.debug_tablefinder({"vertical_strategy": "lines", "horizontal_strategy": "lines"})
    tables = []
    for table in finder.tables:
        cells = list(table.cells)
        left, top, right, bottom = table.bbox
        rows = table.rows
        if rows and all(all(c is not None for c in row.cells) for row in rows):
            boundaries = sorted({v for c in cells for v in c[1::2]})
            ends = []
            for y in boundaries:
                lines = [
                    e
                    for e in finder.edges
                    if e["orientation"] == "h"
                    and abs(e["top"] - y) <= 1
                    and e["x0"] <= left + 1
                    and e["x1"] >= right - 1
                ]
                if len(lines) != 1:
                    ends = []
                    break
                ends.append((lines[0]["x0"], lines[0]["x1"]))
            for side in (0, 1):
                if not ends or max(e[side] for e in ends) - min(e[side] for e in ends) > 1:
                    continue
                edge = sum(e[side] for e in ends) / len(ends)
                low, high = (edge, left) if side == 0 else (right, edge)
                if high - low < 5 or any(
                    e["orientation"] == "v"
                    and low + 1 < e["x0"] < high - 1
                    and e["top"] < bottom
                    and e["bottom"] > top
                    for e in finder.edges
                ):
                    continue
                cells.extend(
                    (low, a, high, b) for a, b in zip(boundaries[:-1], boundaries[1:], strict=True)
                )
        tables.append(Table(page, cells))
    return tables
