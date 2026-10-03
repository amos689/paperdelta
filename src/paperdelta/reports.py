"""Portable reports rendered entirely from the checker's evidence model."""

from __future__ import annotations

from html import escape

from paperdelta.errors import PaperDeltaError
from paperdelta.i18n import msg, tr, translated
from paperdelta.storage import Project, json_text


def text_report(report: dict) -> str:
    counts = report["coverage"]
    lines = [
        tr("report.title"),
        tr(
            "report.counts",
            confirmed=counts["confirmed"],
            passed=counts["pass"],
            mismatch=counts["mismatch"],
            unknown=counts["unknown"],
        ),
        tr(
            "report.coverage",
            unbound=len(counts["unbound_numbers"]),
            unsupported=len(counts["unsupported"]),
        ),
        tr("report.figures", count=len(counts["unregistered_figures"])),
    ]
    for item in report["diagnostics"]:
        location = item.get("location", {})
        where = f"{location['file']}:{location['line']}" if location else item["subject"]
        severity = tr("status." + item["severity"]).upper()
        lines.append(f"{severity} {where} [{item['rule']}] {translated(item['message'])}")
    if report["baseline"]:
        lines.append(
            tr("report.baseline", count=len(report["changes"]), name=report["baseline"]["name"])
        )
    else:
        lines.append(tr("report.no_baseline"))
    for name, state in report["claims"].items():
        lines.append(
            tr(
                "report.review",
                name=name,
                review=tr("status." + state.get("review", "unreviewed")),
                status=tr("status." + state["status"]),
            )
        )
    return "\n".join(lines) + "\n"


def markdown_report(report: dict) -> str:
    # Indented output avoids letting source text close a Markdown fence.
    output = (
        "# "
        + tr("report.markdown_title")
        + "\n\n"
        + "\n".join("    " + line for line in text_report(report).splitlines())
    )
    output += "\n\n## " + tr("report.changes") + "\n\n"
    for change in report["changes"]:
        output += "    " + json_text(change).replace("\n", "\n    ").rstrip() + "\n\n"
    output += "\n## " + tr("report.impacts") + "\n\n"
    for group in report["impact_groups"]:
        output += "    " + json_text(group).replace("\n", "\n    ").rstrip() + "\n\n"
    return output + "\n" + tr("report.scope") + "\n"


def html_report(report: dict) -> str:
    def esc(value) -> str:
        return escape(str(value), quote=True)

    counts = report["coverage"]
    summary = "".join(
        f'<div class="stat {name}"><strong>{counts[name]}</strong><span>{name}</span></div>'
        for name in ("confirmed", "pass", "mismatch", "unknown")
    )
    cards = []
    subject_groups = {}
    for impact in report["impact_groups"]:
        for group, prefix in (
            ("occurrences", "occurrence"),
            ("claims", "claim"),
            ("figures", "figure"),
        ):
            for name in impact[group]:
                subject_groups.setdefault(f"{prefix}:{name}", []).append(impact["metric"])
    files, sources, rules = set(), set(), set()
    for item in report["diagnostics"]:
        location = item.get("location", {})
        where = f"{location['file']}:{location['line']}" if location else item["subject"]
        group, _, name = item["subject"].partition(":")
        collection = {"occurrence": "occurrences", "claim": "claims", "figure": "figures"}.get(
            group
        )
        state = report.get(collection, {}).get(name, {}) if collection else {}
        refs = state.get("metrics", [state["metric"]] if "metric" in state else [])
        file = location.get("file", state.get("path", ""))
        selected_sources = sorted(
            {
                source["path"]
                for ref in refs
                for source in report["metrics"].get(ref, {}).get("evidence", [])
            }
            | set(state.get("dependencies", []))
        )
        files.add(file)
        sources.update(selected_sources)
        rules.add(item["rule"])
        evidence = []
        if group == "figure":
            evidence.append(f"<p>Record method: {esc(state.get('record_method', 'unknown'))}</p>")
            evidence.append(
                "<p>Changed declared dependencies:</p><ul>"
                + "".join(
                    f"<li><code>{esc(path)}</code></li>" for path in state.get("changed_paths", [])
                )
                + "</ul>"
            )
        for ref in refs:
            metric = report["metrics"].get(ref, {})
            evidence.append(
                f"<h4>{esc(ref)} <small>{esc(metric.get('value', 'unknown'))} "
                f"{esc(metric.get('unit', ''))}</small></h4>"
            )
            definition = metric.get("definition", {})
            if "op" in definition:
                evidence.append(
                    f"<p>Calculation: <code>{esc(definition['op'])}({esc(', '.join(definition['args']))})</code></p>"
                )
            for source in metric.get("evidence", []):
                evidence.append(
                    f"<p><code>{esc(source['path'])}</code> · "
                    f"{esc(source['reduce'])} of {source['count']} records</p>"
                )
                where_text = "; ".join(f"{key}={value}" for key, value in source["where"].items())
                evidence.append(
                    f"<p>Field: <code>{esc(source['field'])}</code> · {esc(where_text or 'JSON Pointer selection')}</p>"
                )
                rows = []
                for index, record in enumerate(source["records"][:10]):
                    identity = "; ".join(
                        f"{key}={value}" for key, value in record.get("key", {}).items()
                    )
                    if not identity:
                        identity = f"item {record.get('index', index)}"
                    record_location = (
                        source["locations"][index] if index < len(source["locations"]) else {}
                    )
                    evidence_location = (
                        f"line {record_location['line']}"
                        if "line" in record_location
                        else source["field"]
                    )
                    rows.append(
                        f"<tr><td>{esc(identity)}</td><td>{esc(record['value'])}</td><td>{esc(evidence_location)}</td></tr>"
                    )
                evidence.append(
                    "<table><thead><tr><th>Record identity</th><th>Value</th><th>Location</th></tr></thead>"
                    f"<tbody>{''.join(rows)}</tbody></table>"
                )
                if source["count"] > 10:
                    evidence.append(
                        f"<p>Showing 10 of {source['count']} records. The JSON report contains all selected evidence.</p>"
                    )
        suggestion = state.get("suggestion")
        patch = ""
        if suggestion:
            patch = f'<div class="diff"><del>{esc(state["actual"])}</del> → <ins>{esc(suggestion["replacement"])}</ins></div>'
            if suggestion["blocked_by"]:
                patch += (
                    '<p class="warning">Review the related claim before applying numeric fixes: '
                    + esc(", ".join(suggestion["blocked_by"]))
                    + "</p>"
                )
        cards.append(
            f'<article data-level="{esc(item["severity"])}" data-file="{esc(file)}" '
            f'data-rule="{esc(item["rule"])}" data-sources="{esc(json_text(selected_sources))}" '
            f'data-impacts="{esc(json_text(subject_groups.get(item["subject"], [])))}"><div class="meta">'
            f"<b>{esc(item['severity'])}</b> · {esc(item['rule'])} · {esc(where)}</div>"
            f"<h3>{esc(item['message'])}</h3>"
            + (f"<blockquote>{esc(location['text'])}</blockquote>" if location else "")
            + patch
            + (
                f"<details><summary>Show evidence</summary>{''.join(evidence)}</details>"
                if evidence
                else ""
            )
            + "</article>"
        )
    changes = "".join(
        f"<tr><td>{esc(item['metric'])}</td><td>{esc(item['kind'])}</td>"
        f"<td>{esc(item['before'])}</td><td>{esc(item['after'])}</td>"
        f"<td>{esc(item['unit'])}</td></tr>"
        for item in report["changes"]
    )
    baseline = (
        esc(report["baseline"]["name"])
        if report["baseline"]
        else "none — historical impact unavailable"
    )
    unbound = esc(json_text(counts["unbound_numbers"]))
    unsupported = esc(json_text(counts["unsupported"]))
    unregistered = esc(json_text(counts["unregistered_figures"]))
    impact_cards = []
    for group in report["impact_groups"]:
        state = report["metrics"][group["metric"]]
        locations = []
        for name in group["occurrences"]:
            item = report["occurrences"][name]
            location = item.get("location", {})
            locations.append(
                f"<li><code>{esc(location.get('file', name))}:{esc(location.get('line', '?'))}</code> · "
                f"{esc(item.get('actual', 'unknown'))} → {esc(item.get('expected', 'unknown'))} "
                f"<b>{esc(item['status'])}</b></li>"
            )
        for name in group["claims"]:
            item = report["claims"][name]
            locations.append(
                f"<li>Claim <code>{esc(name)}</code> · {esc(item['status'])} · "
                f"review: <b>{esc(item.get('review', 'unreviewed'))}</b></li>"
            )
        for name in group["figures"]:
            item = report["figures"][name]
            locations.append(
                f"<li>Figure <code>{esc(item['path'])}</code> · {esc(item['provenance'])}</li>"
            )
        impact_cards.append(
            f'<div class="impact"><h3>{esc(group["metric"])} '
            f"<small>{esc(state.get('value', 'unknown'))} {esc(state.get('unit', ''))}</small></h3>"
            f"<p>{esc(', '.join(group['sources']))} · history: {esc(group['change'])}</p>"
            f"<ul>{''.join(locations)}</ul></div>"
        )

    def options(values):
        return "".join(
            f'<option value="{esc(value)}">{esc(value)}</option>'
            for value in sorted(values)
            if value
        )

    body = f"""<header><span class="eyebrow">RESEARCH CHANGE REVIEW</span>
<h1>PaperDelta<span class="dot">.</span></h1>
<p>See where a result is used. Review what changed.</p></header>
<section class="stats">{summary}</section>
<p class="scope">Consistency with supplied results · baseline: {baseline}<br>
{len(counts["unbound_numbers"])} unbound numeric candidates · {len(counts["unsupported"])} unsupported regions · {len(counts["unregistered_figures"])} unregistered figure references</p>
<section><h2>Result changes</h2><table><thead><tr><th>Metric</th><th>Change</th><th>Before</th><th>After</th><th>Unit</th></tr></thead>
<tbody>{changes or '<tr><td colspan="5">No historical metric changes available.</td></tr>'}</tbody></table></section>
<section><h2>Where each result is used</h2><div class="impacts">{"".join(impact_cards) or "<p>No resolved impact groups.</p>"}</div></section>
<section><h2>Findings <span id="visible-count"></span></h2>
<div class="filters"><input id="search" type="search" aria-label="Filter findings" placeholder="Search findings, files, or evidence…">
<select id="level" aria-label="Severity"><option value="all">All severities</option><option>error</option><option>unknown</option><option>warning</option></select></div>
<div class="filters secondary"><select id="file" aria-label="File"><option value="">All files</option>{options(files)}</select>
<select id="source" aria-label="Source"><option value="">All sources</option>{options(sources)}</select>
<select id="rule" aria-label="Rule"><option value="">All rules</option>{options(rules)}</select>
<select id="impact" aria-label="Result"><option value="">All results</option>{options(group["metric"] for group in report["impact_groups"])}</select></div>
<div id="findings">{"".join(cards) or '<p class="empty">All confirmed bindings match the supplied evidence.</p>'}</div></section>
<section><h2>Coverage</h2><details><summary>Unbound numeric candidates ({len(counts["unbound_numbers"])})</summary><pre>{unbound}</pre></details>
<details><summary>Unsupported regions ({len(counts["unsupported"])})</summary><pre>{unsupported}</pre></details>
<details><summary>Unregistered figure references ({len(counts["unregistered_figures"])})</summary><pre>{unregistered}</pre></details></section>
<footer>Generated locally by PaperDelta {esc(report["tool_version"])}. No external resources.<br>
Checks declared bindings; does not certify scientific correctness or execution provenance.</footer>"""
    return (
        """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>PaperDelta review</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<style>
:root{font-family:Inter,Segoe UI,system-ui,sans-serif;color:#182b35;background:#f5f7f8;font-size:16px}
*{box-sizing:border-box}body{margin:0 auto;max-width:1080px;padding:48px 28px}header{border-bottom:1px solid #d4dfe3;padding-bottom:28px}
.eyebrow{letter-spacing:.18em;font-size:11px;font-weight:700;color:#287e79}h1{font-size:50px;letter-spacing:-2px;margin:10px 0}.dot{color:#2c9a8f}
header p,.scope,footer{color:#5d707a;line-height:1.7}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin:28px 0 12px}
.stat{background:white;border:1px solid #dce5e7;border-radius:10px;padding:20px}.stat strong{display:block;font-size:32px}.stat span{text-transform:capitalize;color:#657881}
.mismatch strong{color:#ba493c}.unknown strong{color:#a07215}.pass strong{color:#20836d}section{margin:30px 0}h2{font-size:20px}h3{font-size:16px;line-height:1.5}h4 small{font-weight:400}
table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{text-align:left;padding:12px;border-bottom:1px solid #e0e7e9}th{color:#637985;background:#edf2f4}
.filters{display:flex;gap:10px;margin-bottom:16px}input,select{font:inherit;padding:11px;border:1px solid #cad8dd;border-radius:7px;background:white}input{flex:1;min-width:0}
.secondary{flex-wrap:wrap}.secondary select{flex:1;min-width:160px;max-width:100%}.impacts{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));gap:16px}.impact{background:#fff;border:1px solid #d9e4e7;border-radius:9px;padding:18px}.impact h3{margin-top:0}.impact p,.impact li{font-size:13px;color:#536872;line-height:1.7;overflow-wrap:anywhere}.impact ul{padding-left:18px}.impact small{font-weight:400}
article{border:1px solid #d9e4e7;border-left:4px solid #ba493c;border-radius:9px;background:white;padding:20px;margin:14px 0}article[data-level=unknown]{border-left-color:#ba861f}article[data-level=warning]{border-left-color:#72838d}
.meta{font-size:12px;color:#637985;overflow-wrap:anywhere}.meta b{text-transform:uppercase}blockquote{margin:12px 0;padding:10px 14px;background:#f6f8f9;border-left:2px solid #bdcdd3;white-space:pre-wrap}
.diff{font-family:ui-monospace,Consolas,monospace;padding:12px 0}del{color:#a33d36}ins{color:#08725c;text-decoration:none;background:#e3f5ec}.warning{color:#926318;font-size:13px}
details{margin:12px 0}summary{cursor:pointer;color:#256c76}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px;background:#eff4f6;padding:14px;border-radius:6px}code{overflow-wrap:anywhere}
footer{font-size:12px;border-top:1px solid #d7e2e6;padding-top:20px}.empty{background:#e4f4ed;padding:20px;border-radius:8px}[hidden]{display:none!important}
@media(max-width:650px){body{padding:24px 16px}.stats{grid-template-columns:repeat(2,1fr)}h1{font-size:40px}table{display:block;overflow-x:auto}}
</style></head><body>"""
        + body
        + """<script>
const search=document.querySelector('#search'),level=document.querySelector('#level'),cards=[...document.querySelectorAll('#findings article')];
const file=document.querySelector('#file'),source=document.querySelector('#source'),rule=document.querySelector('#rule'),impact=document.querySelector('#impact');
function filter(){const query=search.value.toLowerCase();let count=0;for(const card of cards){const visible=(level.value==='all'||card.dataset.level===level.value)&&(!file.value||card.dataset.file===file.value)&&(!rule.value||card.dataset.rule===rule.value)&&(!source.value||JSON.parse(card.dataset.sources).includes(source.value))&&(!impact.value||JSON.parse(card.dataset.impacts).includes(impact.value))&&card.textContent.toLowerCase().includes(query);card.hidden=!visible;if(visible)count++;}document.querySelector('#visible-count').textContent='('+count+')';}
search.addEventListener('input',filter);for(const select of [level,file,source,rule,impact])select.addEventListener('change',filter);filter();
</script></body></html>"""
    )


def write_reports(project: Project, directory: str, report: dict) -> None:
    outputs = {
        "report.json": json_text(report),
        "report.md": markdown_report(report),
        "report.html": html_report(report),
    }
    protected = {project.path(name) for name in report["input_hashes"]}
    for name in outputs:
        if project.path(f"{directory}/{name}") in protected:
            raise PaperDeltaError("REPORT_OVERWRITE", msg("error.REPORT_OVERWRITE"))
    for name, content in outputs.items():
        project.write(f"{directory}/{name}", content.encode("utf-8"))
