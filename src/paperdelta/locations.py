"""Localized positions without inventing lines or pages for native documents."""

from paperdelta.i18n import msg


def location_label(location):
    if location.get("format") in {"markdown", "quarto"}:
        key = "markdown.cell_label" if location["locator"].get("table") else "markdown.line_label"
        return msg(key, **{**location, **location["locator"]})
    if location.get("format") == "pdf":
        value = location["locator"]
        key = "pdf.cell_label" if value.get("table") is not None else "pdf.page_label"
        return msg(key, file=location["file"], **value)
    if location.get("format") == "docx":
        value = location["locator"]
        if value.get("note_id") is not None:
            key = (
                "document.footnote_label"
                if value["part"].endswith("footnotes.xml")
                else "document.endnote_label"
            )
            return msg(key, file=location["file"], **value)
        key = (
            "document.cell_label" if value.get("table") is not None else "document.paragraph_label"
        )
        return msg(key, file=location["file"], **value)
    return msg("document.line_label", file=location["file"], line=location["line"])
