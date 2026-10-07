"""Self-contained bilingual presentation, without changing the stored report."""

from __future__ import annotations

import json
from collections import defaultdict
from html import escape
from importlib.resources import files

from paperdelta.i18n import LANGUAGES, Message, catalog, current_language, msg
from paperdelta.locations import location_label
from paperdelta.storage import json_text, sha256


def esc(value) -> str:
    return escape(str(value), quote=True)


class Labels:
    """Only first-party messages enter the locale table; source text stays literal."""

    def __init__(self):
        self.language = current_language()
        self.values: dict[str, dict[str, str]] = {}
        self.identities: dict[tuple, str] = {}

    def register(self, message: Message) -> str:
        values = {language: message.render(language) for language in LANGUAGES}
        identity = tuple(values.items())
        if identity not in self.identities:
            key = f"m{len(self.values)}"
            self.identities[identity] = key
            self.values[key] = values
        return self.identities[identity]

    def text(self, value, tag="span") -> str:
        if not isinstance(value, Message):
            return esc(value)
        key = self.register(value)
        return f'<{tag} data-i18n="{key}">{esc(self.values[key][self.language])}</{tag}>'

    def label(self, key, **parameters) -> str:
        return self.text(msg(key, **parameters))

    def attr(self, attribute, key, **parameters) -> str:
        identity = self.register(msg(key, **parameters))
        return (
            f'data-i18n-{attribute}="{identity}" '
            f'{attribute}="{esc(self.values[identity][self.language])}"'
        )

    def enum(self, prefix, value) -> str:
        key = f"{prefix}.{value}"
        return self.label(key) if key in catalog("en") else esc(value)

    def value(self, value) -> str:
        return self.label("status.unknown") if value is None else esc(value)


def _subject_id(subject: str) -> str:
    return "subject-" + sha256(subject.encode("utf-8")).split(":")[1][:16]


def _priority(item):
    if item["severity"] == "unknown":
        return 0
    if item["rule"] == "CLAIM_FALSE":
        return 1
    return 3 if item["severity"] == "warning" else 2


def _action(item):
    rule = item["rule"]
    if item["subject"].startswith("provenance:"):
        return "actions.detail_review_producers"
    if item["subject"].startswith("fragment:"):
        return "actions.detail_update_fragments"
    if rule == "EXPORT_STALE":
        return "actions.detail_reexport_pdf"
    if rule == "PDF_EXTRACTION_CHANGED":
        return "html.action_anchor"
    if "ANCHOR" in rule or rule in {"OUTSIDE_PAPER", "MISSING_PAPER"}:
        return "html.action_anchor"
    if rule == "CLAIM_FALSE":
        return "html.next_claim"
    if rule == "VALUE_MISMATCH":
        if item.get("location", {}).get("format") in {"docx", "pdf", "markdown", "quarto"}:
            return "document.manual_update"
        return "html.action_numeric"
    if rule in {"FIGURE_CHANGED", "PROVENANCE_UNKNOWN", "FIGURE_RECORD"}:
        return "html.action_figure"
    if rule in {"INCOMPLETE_COVERAGE", "UNSUPPORTED_MACRO", "DYNAMIC_TEX", "NO_BINDINGS"}:
        return "html.action_coverage"
    return "html.action_evidence"


def _evidence(report, group, state, refs, labels):
    t = labels.label
    parts = []
    if group == "figure":
        parts.append(
            f"<p>{t('html.record_method')}: "
            f"{labels.enum('status', state.get('record_method', 'unknown'))}</p>"
            f"<p>{t('html.changed_dependencies')}</p><ul>"
            + "".join(
                f"<li><code>{esc(path)}</code></li>" for path in state.get("changed_paths", [])
            )
            + "</ul>"
        )
    for ref in refs:
        metric = report["metrics"].get(ref, {})
        parts.append(
            f"<h4>{esc(ref)} <small>{labels.value(metric.get('value'))} "
            f"{labels.enum('unit', metric.get('unit', ''))}</small></h4>"
        )
        if "message" in metric:
            parts.append(f"<p>{labels.text(metric['message'])}</p>")
        definition = metric.get("definition", {})
        if metric.get("statistics"):
            summary = metric["statistics"]
            rows = [
                "<dt>"
                + t("statistics.component_" + key)
                + "</dt><dd>"
                + esc(summary[key])
                + "</dd>"
                for key in ("mean", "sd", "se", "n")
            ]
            for key, value in [
                ("statistics.guide_ddof", summary["ddof"]),
                ("statistics.guide_unit", summary["unit_of_analysis"]),
                ("statistics.precision", summary["precision_digits"]),
            ]:
                rows.append("<dt>" + t(key) + "</dt><dd>" + esc(value) + "</dd>")
            interval = summary.get("confidence_interval")
            if interval:
                rows.append(
                    "<dt>"
                    + t("statistics.student_t")
                    + " · "
                    + esc(interval["level"])
                    + "</dt><dd>"
                    + esc(f"[{interval['lower']}, {interval['upper']}]")
                    + "</dd>"
                )
                rows.append("<dt>" + t("statistics.assumption") + "</dt>")
            parts.append(
                '<div class="statistics-summary"><dl>'
                + "".join(rows)
                + "</dl><p>"
                + t("statistics.no_significance")
                + "</p></div>"
            )
        if "op" in definition:
            parts.append(
                f"<p>{t('html.calculation')}: <code>{esc(definition['op'])}"
                f"({esc(', '.join(definition['args']))})</code></p>"
            )
        for source in metric.get("evidence", []):
            parts.append(
                f"<p><code>{esc(source['path'])}</code> · "
                + t("html.records", reduce=msg("reduce." + source["reduce"]), count=source["count"])
                + "</p>"
            )
            where = "; ".join(f"{key}={value}" for key, value in source["where"].items())
            parts.append(
                f"<p>{t('html.field')}: <code>{esc(source['field'])}</code> · "
                + (esc(where) if where else t("html.pointer"))
                + "</p>"
            )
            rows = []
            if source.get("provenance"):
                origin = source["provenance"]
                parts.append(
                    f"<details><summary>{t('html.provenance')}</summary>"
                    f"<p>{esc(origin['provider'])} · {esc(origin['origin'])}</p>"
                    f"<p>{esc(origin['created_at'])}</p><p><code>{esc(origin['export_id'])}</code></p>"
                    f"<p>{t('html.precision_' + origin['precision'])}</p>"
                    f"<pre>{esc(json_text(origin['selection']))}</pre></details>"
                )
            for index, record in enumerate(source["records"][:10]):
                identity = "; ".join(
                    f"{key}={value}" for key, value in record.get("key", {}).items()
                )
                identity = (
                    esc(identity) if identity else t("html.item", index=record.get("index", index))
                )
                location = source["locations"][index] if index < len(source["locations"]) else {}
                if "cell" in location:
                    location = esc(f"{location['sheet']}!{location['cell']}")
                elif "line" in location:
                    location = t("html.line", line=location["line"])
                else:
                    location = esc(location.get("pointer", source["field"]))
                rows.append(
                    f"<tr><td>{identity}</td><td>{esc(record['value'])}</td><td>{location}</td></tr>"
                )
            parts.append(
                f"<table><thead><tr><th>{t('html.identity')}</th><th>{t('html.value')}</th>"
                f"<th>{t('html.location')}</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"
            )
            if source["count"] > 10:
                parts.append(f"<p>{t('html.record_limit', count=source['count'])}</p>")
    return "".join(parts)


def _coverage(counts, labels):
    t = labels.label
    blocks = []
    for name, title in (
        ("unbound_numbers", "unbound"),
        ("unsupported", "unsupported"),
        ("unregistered_figures", "unregistered"),
        ("outside_scope_numbers", "outside_scope"),
    ):
        groups = defaultdict(list)
        for item in counts.get(name, []):
            groups[(item["file"], item.get("code", ""))].append(item)
        contents = []
        for (file, code), items in sorted(groups.items()):
            contents.append(
                f'<details class="coverage-group"><summary><code>{esc(file)} {esc(code)}</code> · '
                f"{t('html.occurrences', count=len(items))}</summary>"
            )
            if name == "unsupported":
                messages = {}
                for item in items:
                    identity = str(item["message"])
                    if identity not in messages:
                        messages[identity] = [item["message"], 0]
                    messages[identity][1] += 1
                contents.append(
                    "<ul>"
                    + "".join(
                        f"<li>{labels.text(message)} · {t('html.occurrences', count=count)}</li>"
                        for message, count in messages.values()
                    )
                    + "</ul>"
                )
            elif name in {"unbound_numbers", "outside_scope_numbers"}:
                contents.append(
                    "<ul>"
                    + "".join(
                        f"<li><code>{labels.text(location_label(item))}</code> · "
                        f"<code>{esc(item['text'])}</code></li>"
                        for item in items
                    )
                    + "</ul>"
                )
            else:
                for item in items:
                    reason = (
                        "html.not_registered"
                        if item["reason"] == "not registered"
                        else "html.missing_ambiguous"
                    )
                    contents.append(
                        f"<p>{t('html.reference')}: <code>{esc(item['reference'])}</code><br>"
                        f"{t('html.resolved')}: <code>{esc(', '.join(item['resolved']))}</code><br>"
                        f"{t('html.reason')}: {t(reason)}</p>"
                    )
            contents.append("</details>")
        blocks.append(
            f'<details id="coverage-{name}"><summary>{t("html." + title, count=len(counts.get(name, [])))}</summary>'
            + ("".join(contents) or f"<p>{t('html.empty')}</p>")
            + "</details>"
        )
    exclusions = counts.get("exclusions", [])
    blocks.append(
        f'<details id="coverage-exclusions"><summary>{t("html.exclusions", count=len(exclusions))}</summary><ul>'
        + "".join(
            f"<li><code>{esc(item['id'])}</code> · {t('scope.exclusion_' + item['status'])} · {esc(item['reason'])}"
            + (
                f" · <code>{labels.text(location_label(item['location']))} · {esc(item['location']['text'])}</code>"
                if item.get("location")
                else ""
            )
            + "</li>"
            for item in exclusions
        )
        + "</ul></details>"
    )
    if counts.get("review_scope"):
        blocks.insert(
            0,
            f"<p>{t('report.selected_scope', value=json.dumps(counts['review_scope'], ensure_ascii=False))}</p>",
        )
    return "".join(blocks)


def _pdf_pages(previews, labels):
    if not previews or not previews["pages"]:
        return ""
    t = labels.label
    parts = [
        f'<section id="pdf-pages"><h2>{t("pdf.preview_title")}</h2><p>{t("pdf.preview_note")}</p>'
    ]
    for page in previews["pages"]:
        title = t("pdf.page_label", file=page["file"], page=page["page"])
        if "image" not in page:
            parts.append(f"<p><b>{title}</b> · {labels.text(page['message'])}</p>")
            continue
        x0, y0, x1, y1 = page["page_box"]
        boxes = []
        for box in page["boxes"]:
            left, top, right, bottom = box["bbox"]
            boxes.append(
                f'<rect id="{esc(box["id"])}" class="pdf-box {esc(box["status"])}" x="{left}" y="{top}" width="{right - left}" height="{bottom - top}"><title>{esc(box["text"])}</title></rect>'
            )
        parts.append(
            f'<details class="pdf-page" open><summary>{title}</summary>'
            f'<div class="pdf-controls"><button type="button" data-pdf-zoom="2" disabled>{t("pdf.zoom_in")}</button><button type="button" data-pdf-zoom="1" disabled>{t("pdf.zoom_fit")}</button></div>'
            f'<div class="pdf-viewport"><div class="pdf-canvas" style="aspect-ratio:{x1 - x0}/{y1 - y0}"><img src="{esc(page["image"])}" {labels.attr("alt", "pdf.preview_alt", file=page["file"], page=page["page"])} loading="lazy">'
            f'<svg viewBox="{x0} {y0} {x1 - x0} {y1 - y0}" aria-hidden="true">{"".join(boxes)}</svg></div></div>'
            f'<p class="scope">{t("pdf.preview_hash")} <code>{esc(page["hash"])}</code></p></details>'
        )
    if previews["omitted"]:
        parts.append(f"<p>{t('pdf.preview_omitted', count=previews['omitted'])}</p>")
    return "".join(parts) + "</section>"


def _exports(report, labels):
    if not report.get("exports"):
        return ""
    t = labels.label
    rows = "".join(
        f"<li>{t('pdf.export_line', file=item['file'], source=item['source'], metric=item['metric'] or '—', status=msg('pdf.export_' + item['status']))}</li>"
        for item in report["exports"]
    )
    return f'<section id="exports"><h2>{t("pdf.exports_title")}</h2><p>{t("pdf.exports_note")}</p><ul>{rows}</ul></section>'


def _workflow(report, labels):
    from paperdelta.revisions import revision_list

    t = labels.label
    sections = []
    for name, state in report.get("provenance", {}).items():
        cells = "".join(
            "<li>"
            + t(
                "workflow.cell",
                id=cell["id"],
                code=msg("status.changed" if cell["code_changed"] else "status.unchanged"),
                outputs=msg("status.changed" if cell["outputs_changed"] else "status.unchanged"),
                count=msg(
                    "status.changed" if cell["execution_count_changed"] else "status.unchanged"
                ),
            )
            + "</li>"
            for cell in state.get("cells", [])
        )
        sections.append(
            "<article class=impact><h3>"
            + esc(name)
            + " · "
            + (
                t("workflow.unchanged")
                if state["status"] == "pass"
                else labels.enum("status", state["status"])
            )
            + "</h3><p>"
            + labels.enum("workflow", state.get("method", "declared"))
            + "</p><p><code>"
            + esc(state.get("source") or state["record"])
            + "</code></p><p>"
            + t(
                "workflow.io",
                inputs=", ".join(state.get("inputs", [])),
                outputs=", ".join(state.get("outputs", [])),
            )
            + "</p><p>"
            + t(
                "provenance.observed"
                if state.get("method") == "observed_command"
                else "provenance.declared"
            )
            + "</p><ul>"
            + cells
            + "</ul>"
            + (
                "<pre>" + esc("\n".join(state["observed_command"])) + "</pre>"
                if state.get("observed_command")
                else ""
            )
            + "</article>"
        )
    workflow = (
        "<section id=workflow><h2>"
        + t("workflow.title")
        + "</h2>"
        + "".join(sections)
        + "</section>"
        if sections
        else ""
    )
    revisions = []
    for item in revision_list(report):
        revisions.append(
            "<article class=impact><h3>"
            + labels.enum("revisions", item["kind"])
            + " · "
            + esc(item["subject"])
            + "</h3><p>"
            + labels.enum("status", item["status"])
            + " · "
            + labels.text(item["position"] or ", ".join(item["files"]))
            + "</p><p>"
            + t("revisions." + item["action"])
            + "</p>"
            + (
                "<p>"
                + labels.value(item["actual"])
                + " → "
                + labels.value(item["expected"])
                + "</p>"
                if item["expected"] is not None
                else ""
            )
            + (
                "<p><code>" + esc(", ".join(item["changed_paths"])) + "</code></p>"
                if item["changed_paths"]
                else ""
            )
            + "</article>"
        )
    return (
        workflow
        + "<section id=revision-list><h2>"
        + t("revisions.title")
        + "</h2><p>"
        + t("revisions.notice")
        + "</p>"
        + ("".join(revisions) or "<p>" + t("workflow.empty") + "</p>")
        + "</section>"
    )


def html_report(report: dict, *, previews=None) -> str:
    labels = Labels()
    t = labels.label
    counts = report["coverage"]
    preview_ids = {
        box["id"]
        for page in (previews or {}).get("pages", [])
        if "image" in page
        for box in page["boxes"]
    }

    def pdf_link(location):
        if location.get("format") != "pdf":
            return ""
        from paperdelta.pdf_previews import position_id

        identity = position_id(location)
        return (
            f'<a class="pdf-jump" href="#{identity}">{t("pdf.open_page")}</a>'
            if identity in preview_ids
            else ""
        )

    watch = report.get("watch")
    live = bool(watch and watch["state"] != "stopped")
    subject_groups = defaultdict(list)
    for impact in report["impact_groups"]:
        for group, prefix in (
            ("occurrences", "occurrence"),
            ("claims", "claim"),
            ("figures", "figure"),
        ):
            for name in impact[group]:
                subject_groups[f"{prefix}:{name}"].append(impact["metric"])
    cards, first_subjects = [], set()
    file_names, sources, rules = set(), set(), set()
    for item in sorted(report["diagnostics"], key=_priority):
        location = item.get("location", {})
        where = location_label(location) if location else item["subject"]
        group, _, name = item["subject"].partition(":")
        collection = {
            "occurrence": "occurrences",
            "claim": "claims",
            "figure": "figures",
            "metric": "metrics",
        }.get(group)
        state = report.get(collection, {}).get(name, {}) if collection else {}
        refs = state.get("metrics", [state["metric"]] if "metric" in state else [])
        if group == "metric":
            refs = [name]
        file = location.get(
            "file",
            state.get(
                "path", item["subject"] if not collection and item["subject"] != "project" else ""
            ),
        )
        selected_sources = sorted(
            {
                source["path"]
                for ref in refs
                for source in report["metrics"].get(ref, {}).get("evidence", [])
            }
            | set(state.get("dependencies", []))
        )
        file_names.add(file)
        sources.update(selected_sources)
        rules.add(item["rule"])
        evidence = _evidence(report, group, state, refs, labels)
        suggestion = state.get("suggestion")
        patch = ""
        if suggestion:
            patch = f'<div class="diff"><del>{esc(state["actual"])}</del> → <ins>{esc(suggestion["replacement"])}</ins></div>'
            if suggestion["blocked_by"]:
                patch += f'<p class="warning">{t("html.blocked", claims=", ".join(suggestion["blocked_by"]))}</p>'
        action = "html.next_claim" if suggestion and suggestion["blocked_by"] else _action(item)
        anchor = ""
        if item["subject"] not in first_subjects:
            anchor = f' id="{_subject_id(item["subject"])}"'
            first_subjects.add(item["subject"])
        cards.append(
            f'<article{anchor} data-level="{esc(item["severity"])}" data-file="{esc(file)}" '
            f'data-rule="{esc(item["rule"])}" data-sources="{esc(json.dumps(selected_sources))}" '
            f'data-impacts="{esc(json.dumps(subject_groups[item["subject"]]))}"><div class="meta">'
            f"<b>{labels.enum('status', item['severity'])}</b> · {esc(item['rule'])} · {labels.text(where)}</div>"
            f"<h3>{labels.text(item['message'])}</h3>"
            + (
                "<blockquote>"
                + labels.label("document.note_marker").join(
                    esc(part) for part in location.get("context", location["text"]).split("\ufffc")
                )
                + "</blockquote>"
                if location
                else ""
            )
            + patch
            + pdf_link(location)
            + f'<p class="action">{t(action)}</p>'
            + (
                f"<details><summary>{t('html.evidence')}</summary>{evidence}</details>"
                if evidence
                else ""
            )
            + "</article>"
        )

    def location_link(subject, text):
        return (
            f'<a href="#{_subject_id(subject)}" data-finding-link>{text}</a>'
            if subject in first_subjects
            else text
        )

    impact_cards = []
    for group in report["impact_groups"]:
        state = report["metrics"][group["metric"]]
        locations = []
        for name in group["occurrences"]:
            item = report["occurrences"][name]
            location = item.get("location", {})
            text = (
                f"<code>{labels.text(location_label(location)) if location else esc(name)}</code> · "
                f"{labels.value(item.get('actual'))} → {labels.value(item.get('expected'))} "
                f"<b>{labels.enum('status', item['status'])}</b>" + pdf_link(location)
            )
            locations.append(f"<li>{location_link('occurrence:' + name, text)}</li>")
        for name in group["claims"]:
            item = report["claims"][name]
            text = (
                f"{t('html.claim')} <code>{esc(name)}</code> · {labels.enum('status', item['status'])} · "
                f"{t('html.review')}: <b>{labels.enum('status', item.get('review', 'unreviewed'))}</b>"
            )
            locations.append(f"<li>{location_link('claim:' + name, text)}</li>")
        for name in group["figures"]:
            item = report["figures"][name]
            text = f"{t('html.figure')} <code>{esc(item['path'])}</code> · {labels.enum('status', item['provenance'])}"
            locations.append(f"<li>{location_link('figure:' + name, text)}</li>")
        impact_cards.append(
            f'<div class="impact"><h3>{esc(group["metric"])} '
            f"<small>{labels.value(state.get('value'))} {labels.enum('unit', state.get('unit', ''))}</small></h3>"
            f"<p>{esc(', '.join(group['sources']))} · {t('html.history', change=msg('status.' + group['change']))}</p>"
            f"<ul>{''.join(locations)}</ul>"
            + (
                "<details><summary>"
                + t("studio.stats_summary")
                + "</summary>"
                + _evidence(report, "metric", state, [group["metric"]], labels)
                + "</details>"
                if state.get("statistics")
                else ""
            )
            + "</div>"
        )
    changes = "".join(
        f"<tr><td>{esc(item['metric'])}</td><td>{labels.enum('status', item['kind'])}</td>"
        f"<td>{labels.value(item['before'])}</td><td>{labels.value(item['after'])}</td>"
        f"<td>{labels.enum('unit', item['unit'])}</td></tr>"
        for item in report["changes"]
    )
    summary = "".join(
        f'<div class="stat {name}"><strong>{counts[name]}</strong>{labels.enum("status", name)}</div>'
        for name in ("confirmed", "pass", "mismatch", "unknown")
    )
    if any(item["severity"] == "unknown" for item in report["diagnostics"]):
        next_action = "html.next_unknown"
    elif any(item["rule"] == "CLAIM_FALSE" for item in report["diagnostics"]):
        next_action = "html.next_claim"
    elif any(item["severity"] == "error" for item in report["diagnostics"]):
        next_action = "html.next_mismatch"
    elif any(counts[name] for name in ("unbound_numbers", "unsupported", "unregistered_figures")):
        next_action = "html.next_coverage"
    else:
        next_action = "html.next_pass"

    def selector(name, values):
        options = "".join(
            f'<option value="{esc(value)}">{esc(value)}</option>'
            for value in sorted(values)
            if value
        )
        return (
            f'<select id="{name}" {labels.attr("aria-label", "html." + ("result" if name == "impact" else name))}>'
            f'<option value="" {labels.attr("label", "html.all_" + ("results" if name == "impact" else name + "s"))}></option>'
            f"{options}</select>"
        )

    baseline = report["baseline"]["name"] if report["baseline"] else msg("html.no_baseline")
    impacts_html = "".join(impact_cards) or f"<p>{t('html.no_impacts')}</p>"
    queue = (
        '<section id="review-actions"><h2>'
        + t("actions.title")
        + "</h2><ul>"
        + "".join(
            "<li><b>"
            + t("actions." + action["kind"])
            + "</b> · "
            + t("actions.count", count=len(action["subjects"]))
            + "<p>"
            + t("actions.detail_" + action["kind"])
            + "</p>"
            + (
                location_link(action["subjects"][0], t("actions.open"))
                if action["subjects"] and action["subjects"][0] in first_subjects
                else ""
            )
            + "</li>"
            for action in report.get("actions", [])
        )
        + "</ul></section>"
        if report.get("actions")
        else ""
    )
    watch_banner = (
        (
            '<aside class="next-action" id="watch-status">'
            + t(
                "watch.banner",
                state=msg("watch.state_" + watch["state"]),
                generation=watch["generation"],
            )
            + "<p>"
            + t("watch.live" if live else "watch.finished")
            + "</p></aside>"
        )
        if watch
        else ""
    )
    body = f"""<header><div class="topline">{t("html.eyebrow")}
<label class="language-control">{t("html.language")} <select id="language" disabled {labels.attr("aria-label", "html.language")}>
<option value="en" {"selected" if labels.language == "en" else ""}>English</option>
<option value="zh-CN" {"selected" if labels.language == "zh-CN" else ""}>简体中文</option></select></label></div>
<h1>PaperDelta<span class="dot">.</span></h1><p>{t("html.subtitle")}</p></header>
<noscript><p>{t("html.noscript")}</p></noscript>
{watch_banner}
<section class="stats">{summary}</section>
<p class="scope">{t("html.scope", baseline=baseline)}<br>
{t("html.coverage_counts", unbound=len(counts["unbound_numbers"]), unsupported=len(counts["unsupported"]), figures=len(counts["unregistered_figures"]))}</p>
<aside class="next-action"><b>{t("html.next")}</b><p>{t(next_action)}</p></aside>
{queue}
{_workflow(report, labels)}
{_exports(report, labels)}
<section><h2>{t("report.changes")}</h2><table><thead><tr>
{"".join(f"<th>{t('html.' + key)}</th>" for key in ("metric", "change", "before", "after", "unit"))}
</tr></thead><tbody>{changes or f'<tr><td colspan="5">{t("html.no_changes")}</td></tr>'}</tbody></table></section>
<section><h2>{t("html.uses")}</h2><div class="impacts">{impacts_html}</div></section>
<section><h2>{t("html.findings")} <span id="visible-count" aria-live="polite"></span></h2>
<div class="filters"><input id="search" type="search" {labels.attr("aria-label", "html.filter")} {labels.attr("placeholder", "html.search")}>
<select id="level" {labels.attr("aria-label", "html.level")}>
<option value="all" {labels.attr("label", "html.all_levels")}></option>
{"".join(f'<option value="{name}" {labels.attr("label", "status." + name)}></option>' for name in ("error", "unknown", "warning"))}</select></div>
<div class="filters secondary">{selector("file", file_names)}{selector("source", sources)}{selector("rule", rules)}
{selector("impact", (group["metric"] for group in report["impact_groups"]))}
<button id="clear-filters" type="button">{t("html.clear")}</button></div>
<div id="findings">{"".join(cards) or f'<p class="empty">{t("html.next_pass")}</p>'}</div>
<p id="no-matches" hidden>{t("html.no_matches")}</p></section>
<section><h2>{t("html.coverage")}</h2><p class="scope">{t("html.coverage_note")}</p>{_coverage(counts, labels)}</section>
{_pdf_pages(previews, labels)}
<footer>{t("html.footer", version=report["tool_version"])}<br>{t("html.limitations")}</footer>"""
    title = labels.text(msg("html.title"), tag="title")
    # Raw text elements must never see an injected closing script tag. The client
    # only assigns textContent and known attributes, never innerHTML or eval.
    locale_data = (
        json.dumps(labels.values, ensure_ascii=True)
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("&", r"\u0026")
    )
    assets = files("paperdelta").joinpath("assets")
    css = assets.joinpath("report.css").read_text("utf-8")
    script = assets.joinpath("report.js").read_text("utf-8")
    return (
        f'<!doctype html><html lang="{labels.language}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        + (
            '<meta name="paperdelta-live" content="3"><meta http-equiv="refresh" content="3">'
            if live
            else ""
        )
        + title
        + '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        + f"<style>{css}</style></head><body>{body}"
        + f'<script type="application/json" id="report-locales">{locale_data}</script>'
        + f"<script>{script}</script></body></html>"
    )
