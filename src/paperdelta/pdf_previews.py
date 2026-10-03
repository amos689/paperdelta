"""Bounded, offline previews rendered from the exact PDF bytes used by a report."""

from __future__ import annotations

import base64
import io

from paperdelta.i18n import msg
from paperdelta.pdf_document import coordinate
from paperdelta.storage import fingerprint, sha256


def position_id(location):
    return (
        "pdf-span-"
        + fingerprint({"file": location["file"], "locator": location["locator"]}).split(":")[1][:20]
    )


def pdf_previews(
    project, report, *, max_pages=12, max_pixels=12_000_000, max_bytes=8 * 1024 * 1024
):
    pages, seen = {}, set()
    records = [(item.get("location"), item["severity"]) for item in report["diagnostics"]]
    for group in ("occurrences", "claims"):
        records.extend((item.get("location"), item["status"]) for item in report[group].values())
    records.extend((item, "unbound") for item in report["coverage"]["unbound_numbers"])
    for location, status in records:
        if not location or location.get("format") != "pdf":
            continue
        identity = position_id(location)
        if identity in seen:
            continue
        seen.add(identity)
        key = (location["file"], location["locator"]["page"])
        if key not in pages:
            pages[key] = {
                "file": key[0],
                "page": key[1],
                "page_box": location["locator"]["page_box"],
                "boxes": [],
            }
        # Extremely large scans still get a report without unbounded SVG nodes.
        if len(pages[key]["boxes"]) < 500:
            pages[key]["boxes"].append(
                {
                    "id": identity,
                    "bbox": location["locator"]["bbox"],
                    "text": location["text"],
                    "status": status,
                }
            )
    if not pages:
        return {"pages": [], "omitted": 0}
    selected = list(pages.values())[:max_pages]
    output = {"pages": selected, "omitted": max(0, len(pages) - len(selected))}
    try:
        import pdfplumber
    except ImportError:
        for page in selected:
            page["message"] = msg("pdf.preview_unavailable")
        return output
    pixel_count = byte_count = 0
    for file in dict.fromkeys(page["file"] for page in selected):
        group = [page for page in selected if page["file"] == file]
        try:
            raw = project.read(file)
            if sha256(raw) != report["input_hashes"].get(file):
                for page in group:
                    page["message"] = msg("pdf.preview_changed")
                continue
            with pdfplumber.open(io.BytesIO(raw)) as pdf:
                for item in group:
                    page = pdf.pages[item["page"] - 1]
                    if (
                        [coordinate(v) for v in page.bbox] != item["page_box"]
                        or page.rotation
                        or tuple(page.cropbox) != tuple(page.mediabox)
                    ):
                        item["message"] = msg("pdf.preview_unavailable")
                        continue
                    scale = min(1.5, 1200 / page.width, 1600 / page.height)
                    pixels = (int(page.width * scale) + 1) * (int(page.height * scale) + 1)
                    if pixel_count + pixels > max_pixels:
                        item["message"] = msg("pdf.preview_limit")
                        continue
                    image = page.to_image(resolution=72 * scale, antialias=True).original
                    buffer = io.BytesIO()
                    image.save(buffer, format="PNG", optimize=True)
                    image.close()
                    data = buffer.getvalue()
                    if byte_count + len(data) > max_bytes:
                        item["message"] = msg("pdf.preview_limit")
                        continue
                    byte_count += len(data)
                    pixel_count += pixels
                    item["image"] = "data:image/png;base64," + base64.b64encode(data).decode(
                        "ascii"
                    )
                    item["hash"] = report["input_hashes"][file]
                    page.close()
        except Exception:
            # Rendering availability never changes numerical checking results.
            for page in group:
                if "image" not in page:
                    page["message"] = msg("pdf.preview_unavailable")
    return output
