"""Static workbench shell. Project content is rendered with DOM text nodes."""

PAGE = """<!doctype html>
<html lang="{{LANG}}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light"><title>PaperDelta Studio</title>
<link rel="icon" href="data:,"><link rel="stylesheet" href="/studio.css">
<script src="/studio.js" defer></script></head><body>
<header><div class="brand"><span class="brand-mark" aria-hidden="true">Δ</span>
<div><strong>PaperDelta<span class="dot">.</span></strong><span data-i18n="workbench"></span></div></div>
<div class="header-right"><span id="project" class="project"></span>
<label class="language"><span data-i18n="language"></span>
<select id="language"><option value="en">English</option><option value="zh-CN">简体中文</option></select></label></div></header>
<main><div class="intro"><div><p class="eyebrow" data-i18n="eyebrow"></p>
<h1 data-i18n="title"></h1><p data-i18n="subtitle"></p></div>
<span class="local-pill" data-i18n="local"></span></div>
<div id="message" role="status" aria-live="polite" hidden></div>
<div id="error" role="alert" hidden></div>
<div id="stale" class="notice warning" hidden><strong data-i18n="changed"></strong>
<p data-i18n="refresh_hint"></p></div>
<section id="setup" class="panel" hidden><h2 data-i18n="setup_title"></h2>
<p data-i18n="setup_hint"></p><form id="setup-form">
<label><span data-i18n="paper_path"></span><input name="paper" list="paper-files" required placeholder="paper/main.tex"></label>
<datalist id="paper-files"></datalist>
<label><span data-i18n="data_paths"></span><textarea name="data" rows="3" placeholder="results/metrics.csv"></textarea></label>
<div id="discovered-files" class="chips"></div><p id="file-limit" hidden data-i18n="file_limit"></p>
<button type="submit" data-i18n="initialize"></button></form></section>
<div id="workspace" hidden>
<div class="toolbar"><div id="counts" class="counts"></div><div class="tools">
<button id="refresh" class="secondary" data-i18n="refresh"></button>
<button id="undo" class="secondary" data-i18n="undo"></button>
<button id="save-draft" class="secondary" data-i18n="save_draft"></button>
<button id="load-draft" class="secondary" data-i18n="load_draft"></button>
<input id="draft-file" type="file" accept=".json,application/json" hidden>
<button id="download-report" class="secondary" data-i18n="download_report"></button></div></div>
<div id="receipt" class="notice success" hidden></div>
<nav class="steps" aria-label="Workflow">
<button data-step="evidence" class="active"><span>01</span><span data-i18n="step_evidence"></span></button>
<button data-step="locations"><span>02</span><span data-i18n="step_locations"></span></button>
<button data-step="review"><span>03</span><span data-i18n="step_review"></span><span id="staged-count" class="badge">0</span></button></nav>
<section id="step-evidence" class="step"><div class="two-columns">
<section class="panel"><div class="section-heading"><h2 data-i18n="sources"></h2><span class="eyebrow" data-i18n="source_first"></span></div>
<div id="source-list"></div><details id="add-source"><summary data-i18n="add_source"></summary>
<form id="source-path-form"><label><span data-i18n="source_path"></span><input name="path" list="data-files" required placeholder="results/metrics.csv"></label>
<datalist id="data-files"></datalist><button type="submit" class="secondary" data-i18n="inspect_source"></button></form>
<form id="source-form" hidden><h3 id="source-title"></h3><p data-i18n="source_types_hint"></p>
<div id="source-sample"></div><div id="source-pages" class="pagination"></div>
<label><span data-i18n="source_name"></span><input name="name" required pattern="[A-Za-z](?:[A-Za-z0-9_.]|-){0,99}" placeholder="experiment"></label>
<div id="column-types"></div><button type="submit" data-i18n="stage_source"></button></form></details>
</section><section class="panel"><h2 data-i18n="metrics"></h2><div id="metric-list"></div>
<details id="add-metric"><summary data-i18n="add_metric"></summary><form id="metric-form">
<label><span data-i18n="metric_name"></span><input name="name" required pattern="[A-Za-z](?:[A-Za-z0-9_.]|-){0,99}" placeholder="ours_accuracy"></label>
<div class="form-row"><label><span data-i18n="source"></span><select name="source" required></select></label>
<label><span data-i18n="field"></span><input name="field" list="metric-fields" required placeholder="accuracy"></label></div><datalist id="metric-fields"></datalist>
<fieldset><legend data-i18n="selector"></legend><p data-i18n="selector_hint"></p><div id="selectors"></div></fieldset>
<div class="form-row"><label><span data-i18n="aggregation"></span><select name="reduce"></select></label>
<label><span data-i18n="unit"></span><select name="unit"></select></label></div>
<label><span data-i18n="expected_count"></span><input name="expected_count" type="number" min="1" max="10000" value="1" required></label>
<details><summary data-i18n="seed_check"></summary><label><span data-i18n="seed_column"></span><input name="seed_column" value="seed"></label>
<label><span data-i18n="expected_seeds"></span><textarea name="expected_seeds" rows="2"></textarea></label></details>
<button type="submit" data-i18n="stage_metric"></button></form></details>
<details id="add-derived"><summary data-i18n="add_derived"></summary><form id="derived-form">
<label><span data-i18n="metric_name"></span><input name="name" required pattern="[A-Za-z](?:[A-Za-z0-9_.]|-){0,99}" placeholder="gain"></label>
<label><span data-i18n="operation"></span><select name="operation"></select></label>
<div class="form-row"><label><span data-i18n="left"></span><select name="left" required></select></label><label><span data-i18n="right"></span><select name="right" required></select></label></div>
<button type="submit" data-i18n="stage_derived"></button></form></details></section></div>
<button class="next" data-step="locations" data-i18n="to_locations"></button></section>
<section id="step-locations" class="step" hidden>
<div class="binding-layout"><section class="panel candidates-panel"><div class="section-heading"><h2 data-i18n="paper_locations"></h2><span id="selection-count" class="badge"></span></div>
<div class="form-row"><label><span data-i18n="file"></span><select id="file-filter"></select></label>
<label><span data-i18n="search"></span><input id="search" type="search" data-placeholder="search_hint"></label></div>
<label class="check"><input id="show-bound" type="checkbox"><span data-i18n="show_bound"></span></label>
<button id="clear-selection" type="button" class="secondary small" data-i18n="clear_selection"></button>
<div id="candidates"></div><div id="candidate-pages" class="pagination"></div><p id="candidate-limit" class="muted" hidden></p>
<details id="unsupported"><summary data-i18n="unsupported"></summary><div id="unsupported-list"></div></details>
</section><div class="binding-side"><section class="panel"><h2 data-i18n="binding_title"></h2><p data-i18n="binding_hint"></p>
<form id="locations-form"><label><span data-i18n="metric"></span><select name="metric" required></select></label><div id="selected-metric"></div>
<label><span data-i18n="binding_name"></span><input name="prefix" required pattern="[A-Za-z](?:[A-Za-z0-9_.]|-){0,80}" placeholder="accuracy"></label>
<div class="form-row"><label><span data-i18n="display"></span><select name="display_kind"></select></label><label><span data-i18n="places"></span><input name="places" type="number" min="0" max="15" value="1" required></label></div>
<label class="check"><input name="percent_symbol" type="checkbox" checked><span data-i18n="percent_symbol"></span></label>
<label><span data-i18n="rationale"></span><textarea name="rationale" required maxlength="4000" rows="3" data-placeholder="rationale_hint"></textarea></label>
<button type="submit" data-i18n="stage_locations"></button></form></section>
<section id="pdf-panel" class="panel" hidden><div class="section-heading"><h2 data-i18n="original_page"></h2><button id="pdf-zoom" class="secondary" data-i18n="zoom"></button></div>
<p id="pdf-caption" class="muted"></p><div id="pdf-view" tabindex="0"><div id="pdf-page"></div></div><p data-i18n="pdf_hint" class="muted"></p></section></div></div>
<button class="next" data-step="review" data-i18n="to_review"></button></section>
<section id="step-review" class="step" hidden><section class="panel"><div class="section-heading"><div><h2 data-i18n="review_title"></h2><p data-i18n="review_hint"></p></div><button id="preview" data-i18n="preview"></button></div>
<div id="draft-summary"></div><div id="review-items"></div><div id="review-diagnostics"></div>
<div id="accept-controls" hidden><label class="check attest"><input id="attest" type="checkbox"><span data-i18n="attest"></span></label><button id="accept" data-i18n="accept" disabled></button><p class="muted" data-i18n="accept_hint"></p></div></section></section>
</div></main><footer><span>PaperDelta <span id="version"></span></span><span data-i18n="footer"></span></footer>
</body></html>"""
