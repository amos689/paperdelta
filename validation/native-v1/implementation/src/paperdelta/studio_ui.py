"""Static workbench shell. Project content is rendered with DOM text nodes."""

PAGE = """<!doctype html>
<html lang="{{LANG}}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light"><title>PaperDelta Studio</title>
<link rel="icon" href="data:,"><link rel="stylesheet" href="/studio.css">
<script src="/studio-statistics.js" defer></script><script src="/studio-review.js" defer></script><script src="/studio-batch.js" defer></script><script src="/studio.js" defer></script></head><body>
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
<nav class="workspace-tabs" aria-label="Studio"><button id="open-review" data-mode="review" data-i18n="ongoing_review"></button><button id="open-binding" data-mode="binding" data-i18n="add_bindings"></button></nav>
<section id="recovery-banner" class="notice warning" hidden><strong data-i18n="recovery_title"></strong><p id="recovery-description"></p>
<div class="tools"><button id="restore-local" data-i18n="restore_local"></button><button id="open-rebuild" class="secondary" data-i18n="rebuild_draft"></button><button id="export-recovery" class="secondary" data-i18n="export_recovery"></button><button id="discard-recovery" class="secondary" data-i18n="discard_recovery"></button></div>
<div id="rebuild-work" hidden><p data-i18n="rebuild_hint"></p><div id="rebuild-items"></div><button id="preview-rebuild" data-i18n="preview_rebuild"></button></div>
<div id="rebuild-preview"></div><div id="rebuild-confirm" hidden><label class="check attest"><input id="rebuild-attest" type="checkbox"><span data-i18n="rebuild_attest"></span></label><button id="accept-rebuild" data-i18n="accept_rebuild" disabled></button></div></section>
<div id="review-workspace" hidden>
<section class="panel"><div class="section-heading"><div><p class="eyebrow" data-i18n="review_eyebrow"></p><h2 data-i18n="ongoing_title"></h2></div><span id="watch-state" role="status"></span></div>
<details id="watch-details"><summary id="watch-changes"></summary><ul id="watch-paths" class="muted"></ul></details><div id="ongoing-counts" class="counts"></div>
<div class="snapshot-controls"><label><span data-i18n="compare_snapshot"></span><select id="baseline-select"></select></label>
<form id="snapshot-form"><label><span data-i18n="snapshot_name"></span><input name="name" required maxlength="80" pattern="[A-Za-z0-9](?:[A-Za-z0-9_.]|-){0,79}" placeholder="submitted-v1"></label><button type="submit" data-i18n="create_snapshot"></button></form></div>
<p class="muted" data-i18n="snapshot_hint"></p><div id="review-actions" class="chips"></div></section>
<section class="panel"><h2 data-i18n="impact_title"></h2><label><span data-i18n="search"></span><input id="impact-search" type="search"></label><div id="impact-groups"></div><div id="impact-pages" class="pagination"></div><div id="ongoing-diagnostics"></div><div id="removed-bindings"></div></section>
<section class="panel"><div class="section-heading"><h2 data-i18n="manage_title"></h2><button id="load-declarations" class="secondary" data-i18n="load_declarations"></button></div>
<p data-i18n="manage_hint"></p><label><span data-i18n="search"></span><input id="declaration-search" type="search"></label><div id="declaration-list"></div>
<form id="declaration-form" hidden><h3 id="declaration-name"></h3><div id="declaration-fields" class="form-grid"></div>
<label class="check"><input id="remove-declaration" type="checkbox"><span data-i18n="remove_declaration"></span></label>
<fieldset id="remove-dependents" hidden><legend data-i18n="dependent_declarations"></legend><p data-i18n="dependent_removal_hint"></p><div id="dependent-choices"></div></fieldset>
<label><span data-i18n="rationale"></span><textarea id="declaration-reason" required maxlength="4000"></textarea></label>
<button type="submit" data-i18n="preview_maintenance"></button></form>
<div id="maintenance-preview"></div><div id="maintenance-confirm" hidden><label class="check attest"><input id="maintenance-attest" type="checkbox"><span data-i18n="maintenance_attest"></span></label><button id="accept-maintenance" data-i18n="accept_maintenance" disabled></button></div></section>
<section class="panel"><div class="section-heading"><h2 data-i18n="repair_title"></h2><button id="scan-repairs" class="secondary" data-i18n="scan_repairs"></button></div><p data-i18n="repair_hint"></p>
<div id="repair-work" hidden><label><span data-i18n="broken_binding"></span><select id="repair-binding"></select></label><pre id="repair-old"></pre>
<div id="repair-numeric"><form id="repair-search-form"><label><span data-i18n="search"></span><input id="repair-query" type="search"></label><button type="submit" class="secondary" data-i18n="search_locations"></button></form><div id="repair-candidates"></div><div id="repair-pages" class="pagination"></div><div id="repair-page" class="repair-page" hidden></div></div>
<div id="repair-claim" hidden><label><span data-i18n="file"></span><input id="repair-file"></label><label><span data-i18n="claim_wording"></span><textarea id="repair-wording"></textarea></label></div>
<form id="repair-form"><label><span data-i18n="rationale"></span><textarea id="repair-reason" required maxlength="4000"></textarea></label><button type="submit" data-i18n="preview_repair"></button></form></div>
<div id="repair-preview"></div><div id="repair-confirm" hidden><label class="check attest"><input id="repair-attest" type="checkbox"><span data-i18n="repair_attest"></span></label><button id="accept-repair" data-i18n="accept_repair" disabled></button></div></section>
<section class="panel"><h2 data-i18n="claim_review_title"></h2><p data-i18n="claim_review_hint"></p><div id="claim-list"></div>
<form id="claim-review-form" hidden><h3 id="claim-review-name"></h3><label><span data-i18n="reviewer"></span><input id="claim-reviewer" required maxlength="200"></label><label><span data-i18n="review_note"></span><textarea id="claim-note" required maxlength="4000"></textarea></label>
<label class="check attest"><input id="claim-attest" type="checkbox" required><span data-i18n="claim_attest"></span></label><button type="submit" data-i18n="record_claim_review"></button></form></section>
</div><div id="binding-workspace">
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
<button data-step="batch"><span>03</span><span data-i18n="batch_title"></span></button>
<button data-step="review"><span>04</span><span data-i18n="step_review"></span><span id="staged-count" class="badge">0</span></button></nav>
<section id="step-evidence" class="step"><div class="two-columns">
<section class="panel"><div class="section-heading"><h2 data-i18n="sources"></h2><span class="eyebrow" data-i18n="source_first"></span></div>
<div id="source-list"></div><details id="add-source"><summary data-i18n="add_source"></summary>
<form id="source-path-form"><label><span data-i18n="source_path"></span><input name="path" list="data-files" required placeholder="results/metrics.csv"></label>
<datalist id="data-files"></datalist><button type="submit" class="secondary" data-i18n="inspect_source"></button></form>
<form id="sheet-form" hidden><p data-i18n="xlsx_hint"></p><div class="form-row"><label><span data-i18n="worksheet"></span><select name="sheet" required></select></label><label><span data-i18n="cell_range"></span><input name="cell_range" required placeholder="A1:F20" pattern="[A-Z]{1,3}[1-9][0-9]*:[A-Z]{1,3}[1-9][0-9]*"></label></div><button type="submit" class="secondary" data-i18n="inspect_source"></button></form>
<form id="source-form" hidden><h3 id="source-title"></h3><p data-i18n="source_types_hint"></p>
<div id="source-sample"></div><div id="source-pages" class="pagination"></div>
<div id="source-provenance"></div>
<label><span data-i18n="source_name"></span><input name="name" required pattern="[A-Za-z](?:[A-Za-z0-9_.]|-){0,99}" placeholder="experiment"></label>
<div id="column-types"></div><button type="submit" data-i18n="stage_source"></button></form></details>
</section><section class="panel"><h2 data-i18n="metrics"></h2><label><span data-i18n="search"></span><input id="metric-search" type="search"></label><div id="metric-list"></div><div id="metric-pages" class="pagination"></div>
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
<section id="step-batch" class="step" hidden>
<section class="panel"><h2 data-i18n="batch_title"></h2><p data-i18n="batch_hint"></p>
<form id="batch-form"><label><span data-i18n="source"></span><select name="source" required></select></label>
<div class="two-columns"><fieldset><legend data-i18n="batch_fields"></legend><div id="batch-fields"></div></fieldset>
<fieldset><legend data-i18n="batch_groups"></legend><div id="batch-groups"></div></fieldset></div>
<fieldset><legend data-i18n="selector"></legend><p data-i18n="selector_hint"></p><div id="batch-filters"></div></fieldset>
<div class="form-row"><label><span data-i18n="unit"></span><select name="unit"></select></label><label><span data-i18n="aggregation"></span><select name="reduce"></select></label></div>
<div class="form-row"><label><span data-i18n="expected_count"></span><input name="expected_count" type="number" min="1" max="10000" value="1" required></label><label><span data-i18n="seed_column"></span><input name="seed_column" value="seed"></label></div>
<label><span data-i18n="expected_seeds"></span><textarea name="expected_seeds" rows="2"></textarea></label>
<div class="form-row"><label><span data-i18n="display"></span><select name="display_kind"></select></label><label><span data-i18n="places"></span><input name="places" type="number" min="0" max="15" value="1" required></label></div>
<label class="check"><input name="percent_symbol" type="checkbox" checked><span data-i18n="percent_symbol"></span></label>
<button type="submit" data-i18n="batch_generate"></button></form>
<details id="batch-templates"><summary data-i18n="template_title"></summary><p data-i18n="template_hint"></p>
<div class="form-row"><label><span data-i18n="template_title"></span><select id="template-select"></select></label><div class="tools"><button id="template-load" class="secondary" data-i18n="template_load"></button><button id="template-export" class="secondary" data-i18n="template_export"></button></div></div>
<form id="template-save-form"><label><span data-i18n="template_name_label"></span><input name="name" required pattern="[A-Za-z](?:[A-Za-z0-9_.]|-){0,99}" placeholder="test_accuracy_v1"></label><button type="submit" data-i18n="template_save"></button></form>
<button id="template-import" class="secondary" data-i18n="template_import"></button><input id="template-file" type="file" accept=".json,application/json" hidden><div id="template-errors"></div></details></section>
<section id="batch-catalog" class="panel" hidden><h2 data-i18n="batch_choose"></h2><p data-i18n="batch_positions_hint"></p>
<div class="two-columns"><div><label><span data-i18n="batch_search"></span><input id="batch-search" type="search"></label><div id="batch-choices"></div><div id="batch-choice-pages" class="pagination"></div></div>
<div><div id="batch-choice-evidence"></div><label><span data-i18n="search"></span><input id="batch-location-search" type="search"></label><div id="batch-locations"></div><div id="batch-location-pages" class="pagination"></div><div id="batch-native-page" class="repair-page" hidden></div></div></div>
<p id="batch-selected" role="status"></p><label><span data-i18n="batch_rationale"></span><textarea id="batch-rationale" rows="3" maxlength="4000"></textarea></label>
<button id="batch-stage" data-i18n="batch_stage" disabled></button></section></section>
<section id="step-review" class="step" hidden><section class="panel"><div class="section-heading"><div><h2 data-i18n="review_title"></h2><p data-i18n="review_hint"></p></div><div class="tools"><button id="proposal-import" class="secondary" data-i18n="proposal_import"></button><input id="proposal-file" type="file" accept=".json,application/json" hidden><button id="preview" data-i18n="preview"></button></div></div>
<div id="draft-summary"></div><div id="review-items"></div><div id="review-diagnostics"></div>
<div id="accept-controls" hidden><label class="check attest"><input id="attest" type="checkbox"><span data-i18n="attest"></span></label><button id="accept" data-i18n="accept" disabled></button><p class="muted" data-i18n="accept_hint"></p></div></section></section>
</div></div></main><footer><span>PaperDelta <span id="version"></span></span><span data-i18n="footer"></span></footer>
</body></html>"""
