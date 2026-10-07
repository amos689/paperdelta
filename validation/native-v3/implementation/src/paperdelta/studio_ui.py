"""Static workbench shell. Project content is rendered with DOM text nodes."""

PAGE = """<!doctype html>
<html lang="{{LANG}}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light"><title>PaperDelta Studio</title>
<link rel="icon" href="data:,"><link rel="stylesheet" href="/studio.css">
<script src="/studio-statistics.js" defer></script><script src="/studio-review.js" defer></script><script src="/studio-annotations.js" defer></script><script src="/studio-revisions.js" defer></script><script src="/studio-batch.js" defer></script><script src="/studio-workflows.js" defer></script><script src="/studio.js" defer></script></head><body>
<header><div class="brand"><span class="brand-mark" aria-hidden="true">Δ</span>
<div><strong>PaperDelta<span class="dot">.</span></strong><span data-i18n="workbench"></span></div></div>
<div class="header-right"><span id="project" class="project"></span><button id="diagnostic-preview" class="secondary" data-i18n="diagnostic_preview"></button>
<label class="language"><span data-i18n="language"></span>
<select id="language"><option value="en">English</option><option value="zh-CN">简体中文</option></select></label></div></header>
<main><div class="intro"><div><p class="eyebrow" data-i18n="eyebrow"></p>
<h1 data-i18n="title"></h1><p data-i18n="subtitle"></p></div>
<span class="local-pill" data-i18n="local"></span></div>
<div id="message" role="status" aria-live="polite" hidden></div>
<div id="error" role="alert" hidden></div>
<details id="diagnostic-panel" class="panel" hidden><summary data-i18n="diagnostic_title"></summary><p id="diagnostic-notice" data-i18n="diagnostic_notice"></p><pre id="diagnostic-content"></pre>
<label class="check"><input id="diagnostic-attest" type="checkbox"><span data-i18n="diagnostic_attest"></span></label><button id="diagnostic-export" disabled data-i18n="diagnostic_export"></button></details>
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
<details id="bundle-panel" class="panel"><summary data-i18n="bundle_title"></summary>
<p data-i18n="bundle_notice"></p><label><span data-i18n="bundle_baseline"></span><input id="bundle-baseline" maxlength="80" placeholder="submitted-v1"></label>
<button id="bundle-open" class="secondary" data-i18n="bundle_choose"></button>
<div id="bundle-work" hidden><fieldset><legend data-i18n="bundle_reports"></legend>
<label class="check"><input type="checkbox" data-bundle-report="html" checked>HTML</label><label class="check"><input type="checkbox" data-bundle-report="json" checked>JSON</label>
<label class="check"><input type="checkbox" data-bundle-report="md">Markdown</label><label class="check"><input type="checkbox" data-bundle-report="sarif">SARIF</label></fieldset>
<h3 data-i18n="bundle_inputs"></h3><div class="tools"><button id="bundle-all" class="secondary" data-i18n="bundle_all"></button><button id="bundle-clear" class="secondary" data-i18n="bundle_clear"></button></div>
<div id="bundle-inputs"></div><button id="bundle-preview" data-i18n="bundle_preview"></button>
<div id="bundle-preview-content" hidden><p id="bundle-replay-status"></p><div id="bundle-scope"></div><div id="bundle-files"></div>
<label class="check attest"><input id="bundle-attest" type="checkbox"><span data-i18n="bundle_attest"></span></label><button id="bundle-export" disabled data-i18n="bundle_export"></button></div></div></details>
<section id="recovery-banner" class="notice warning" hidden><strong data-i18n="recovery_title"></strong><p id="recovery-description"></p>
<div class="tools"><button id="restore-local" data-i18n="restore_local"></button><button id="open-rebuild" class="secondary" data-i18n="rebuild_draft"></button><button id="export-recovery" class="secondary" data-i18n="export_recovery"></button><button id="discard-recovery" class="secondary" data-i18n="discard_recovery"></button></div>
<div id="rebuild-work" hidden><p data-i18n="rebuild_hint"></p><div id="rebuild-items"></div><button id="preview-rebuild" data-i18n="preview_rebuild"></button></div>
<div id="rebuild-preview"></div><div id="rebuild-confirm" hidden><label class="check attest"><input id="rebuild-attest" type="checkbox"><span data-i18n="rebuild_attest"></span></label><button id="accept-rebuild" data-i18n="accept_rebuild" disabled></button></div></section>
<div id="review-workspace" hidden>
<details id="workflow-panel" class="panel"><summary data-i18n="workflow_title"></summary><p data-i18n="workflow_notice"></p>
<button id="workflow-load" class="secondary" data-i18n="workflow_load"></button>
<div id="workflow-states"></div><h3 data-i18n="revision_title"></h3><div id="workflow-revisions"></div>
<details id="producer-panel"><summary data-i18n="producer_title"></summary><form id="producer-form">
<div class="form-grid"><label><span data-i18n="workflow_name"></span><input name="name" required maxlength="100" placeholder="training"></label>
<label><span data-i18n="producer_kind"></span><select name="kind"><option value="notebook">Notebook</option><option value="quarto">Quarto</option></select></label>
<label><span data-i18n="producer_source"></span><input name="source" required placeholder="analysis.ipynb"></label></div>
<button id="producer-inspect" type="button" class="secondary" data-i18n="producer_inspect"></button><div id="producer-cells"></div>
<label><span data-i18n="producer_inputs"></span><textarea name="inputs" rows="2" placeholder="data/observations.csv"></textarea></label>
<label><span data-i18n="producer_outputs"></span><textarea name="outputs" rows="2" required placeholder="results/metrics.csv"></textarea></label>
<label><span data-i18n="rationale"></span><textarea name="rationale" required maxlength="4000"></textarea></label>
<label class="check"><input name="replace" type="checkbox"><span data-i18n="workflow_replace"></span></label><button type="submit" data-i18n="workflow_preview"></button></form></details>
<details id="fragment-panel"><summary data-i18n="fragment_title"></summary><form id="fragment-form"><p data-i18n="fragment_hint"></p>
<div class="form-grid"><label><span data-i18n="workflow_name"></span><input name="name" required maxlength="100" placeholder="result-table"></label>
<label><span data-i18n="fragment_format"></span><select name="format"><option value="latex">LaTeX</option><option value="markdown">Markdown</option></select></label>
<label><span data-i18n="fragment_layout"></span><select name="layout"><option value="table" data-i18n="fragment_table"></option><option value="value" data-i18n="fragment_value"></option></select></label>
<label><span data-i18n="fragment_path"></span><input name="path" required placeholder="generated/results.tex"></label></div>
<fieldset><legend data-i18n="fragment_bindings"></legend><div id="fragment-bindings"></div></fieldset>
<label class="check"><input name="replace" type="checkbox"><span data-i18n="workflow_replace"></span></label><button type="submit" data-i18n="workflow_preview"></button></form></details>
<section id="workflow-preview" hidden><h3 data-i18n="workflow_preview_title"></h3><div id="workflow-preview-body"></div>
<label class="check attest"><input id="workflow-attest" type="checkbox"><span data-i18n="workflow_attest"></span></label><button id="workflow-accept" disabled data-i18n="workflow_accept"></button></section></details>
<section class="panel"><div class="section-heading"><div><p class="eyebrow" data-i18n="review_eyebrow"></p><h2 data-i18n="ongoing_title"></h2></div><span id="watch-state" role="status"></span></div>
<details id="watch-details"><summary id="watch-changes"></summary><ul id="watch-paths" class="muted"></ul></details><div id="ongoing-counts" class="counts"></div>
<div class="snapshot-controls"><label><span data-i18n="compare_snapshot"></span><select id="baseline-select"></select></label>
<form id="snapshot-form"><label><span data-i18n="snapshot_name"></span><input name="name" required maxlength="80" pattern="[A-Za-z0-9](?:[A-Za-z0-9_.]|-){0,79}" placeholder="submitted-v1"></label><button type="submit" data-i18n="create_snapshot"></button></form></div>
<p class="muted" data-i18n="snapshot_hint"></p><div id="review-actions" class="chips"></div></section>
<section id="revision-board" class="panel"><div class="section-heading"><h2 data-i18n="revision_board_title"></h2><span id="revision-total" class="muted"></span></div><p data-i18n="revision_board_hint"></p>
<p id="revision-coverage" class="notice"></p><button id="revision-coverage-report" class="secondary small" data-i18n="revision_coverage_report"></button>
<div class="form-grid"><label><span data-i18n="search"></span><input id="revision-search" type="search"></label><label><span data-i18n="revision_status_filter"></span><select id="revision-filter"><option value="" data-i18n="revision_all_states"></option><option value="mismatch" data-i18n="mismatch"></option><option value="unknown" data-i18n="unknown"></option><option value="pass" data-i18n="pass"></option></select></label></div>
<p id="revision-pending" class="notice warning" hidden></p><div class="revision-layout"><div><div id="revision-tasks"></div><div id="revision-pages" class="pagination"></div></div><article id="revision-detail" aria-live="polite"></article></div>
<div class="revision-tools"><span id="revision-selection"></span><button id="revision-clear" class="secondary" disabled data-i18n="clear_selection"></button><button id="revision-preview-button" disabled data-i18n="revision_preview"></button></div>
<section id="revision-preview" hidden><h3 data-i18n="revision_preview_title"></h3><p id="revision-preview-files" class="muted"></p><pre id="revision-diff"></pre><label class="check attest"><input id="revision-attest" type="checkbox"><span data-i18n="revision_attest"></span></label><button id="revision-apply" disabled data-i18n="revision_apply"></button></section>
<section id="annotation-panel" hidden><h3 data-i18n="annotation_title"></h3><p data-i18n="annotation_hint"></p><div class="revision-tools"><span id="annotation-selected"></span><button id="annotation-clear" class="secondary" disabled data-i18n="clear_selection"></button><button id="annotation-preview-button" disabled data-i18n="annotation_preview"></button></div>
<section id="annotation-preview" hidden><p id="annotation-notice" class="notice"></p><pre id="annotation-files"></pre><div id="annotation-entries"></div><label class="check attest"><input id="annotation-attest" type="checkbox"><span data-i18n="annotation_attest"></span></label><button id="annotation-download" disabled data-i18n="annotation_download"></button></section></section>
<details id="revision-history"><summary data-i18n="revision_history"></summary><p data-i18n="revision_history_hint"></p><button id="revision-history-load" class="secondary" data-i18n="revision_load_history"></button><p id="revision-history-empty" class="muted" hidden data-i18n="revision_no_history"></p><label><span data-i18n="revision_transaction"></span><select id="revision-transaction"></select></label><button id="revision-recovery-button" class="secondary" disabled data-i18n="revision_recovery_preview"></button>
<section id="revision-recovery-preview" hidden><h3 data-i18n="revision_recovery_preview"></h3><p id="revision-recovery-files" class="muted"></p><pre id="revision-recovery-diff"></pre><label class="check attest"><input id="revision-recovery-attest" type="checkbox"><span data-i18n="revision_recovery_attest"></span></label><button id="revision-recover" disabled data-i18n="revision_recover"></button></section></details></section>
<details id="advanced-impacts" class="panel"><summary data-i18n="impact_title"></summary><label><span data-i18n="search"></span><input id="impact-search" type="search"></label><div id="impact-groups"></div><div id="impact-pages" class="pagination"></div><div id="ongoing-diagnostics"></div><div id="removed-bindings"></div></details>
<details id="advanced-review" class="panel"><summary data-i18n="revision_advanced"></summary>
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
</details></div><div id="binding-workspace">
<div class="toolbar"><div id="counts" class="counts"></div><div class="tools">
<button id="refresh" class="secondary" data-i18n="refresh"></button>
<button id="undo" class="secondary" data-i18n="undo"></button>
<button id="save-draft" class="secondary" data-i18n="save_draft"></button>
<button id="load-draft" class="secondary" data-i18n="load_draft"></button>
<input id="draft-file" type="file" accept=".json,application/json" hidden>
<button id="download-report" class="secondary" data-i18n="download_report"></button></div></div>
<div id="receipt" class="notice success" hidden></div>
<nav class="steps" aria-label="Workflow">
<button data-step="evidence" class="active"><span>01</span><span data-i18n="stage_inputs"></span></button>
<button data-step="batch"><span>02</span><span data-i18n="stage_experiments"></span></button>
<button data-step="review"><span>03</span><span data-i18n="stage_joint"></span><span id="staged-count" class="badge">0</span></button></nav>
<nav class="tools"><button data-step="locations" class="secondary small" data-i18n="advanced_locations"></button></nav>
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
<div id="column-types"></div><button id="source-advice-show" type="button" class="secondary" data-i18n="source_advice_show"></button><div id="source-advice" hidden></div><button type="submit" data-i18n="stage_source"></button></form></details>
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
<button class="next" data-step="batch" data-i18n="to_experiments"></button></section>
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
<details><summary data-i18n="table_identity_title"></summary><p data-i18n="table_identity_hint"></p>
<label class="check"><input name="use_table_identity" type="checkbox"><span data-i18n="table_identity_use"></span></label>
<label><span data-i18n="table_header_rows"></span><input name="table_header_rows" type="number" min="1" max="20" value="1"></label>
<label><span data-i18n="table_row_prefix"></span><textarea name="table_row_prefix" rows="2" maxlength="4000"></textarea></label></details>
<label><span data-i18n="rationale"></span><textarea name="rationale" required maxlength="4000" rows="3" data-placeholder="rationale_hint"></textarea></label>
<button type="submit" data-i18n="stage_locations"></button></form></section>
<section id="pdf-panel" class="panel" hidden><div class="section-heading"><h2 data-i18n="original_page"></h2><button id="pdf-zoom" class="secondary" data-i18n="zoom"></button></div>
<p id="pdf-caption" class="muted"></p><div id="pdf-view" tabindex="0"><div id="pdf-page"></div></div><p data-i18n="pdf_hint" class="muted"></p></section></div></div>
<button class="next" data-step="review" data-i18n="to_review"></button></section>
<section id="step-batch" class="step" hidden>
<section class="panel"><h2 data-i18n="batch_title"></h2><p data-i18n="batch_hint"></p>
<section id="experiment-reuse" class="reuse-strip"><h3 data-i18n="experiment_reuse_title"></h3><p data-i18n="experiment_reuse_hint"></p>
<div class="form-row"><label><span data-i18n="experiment_definitions"></span><select id="experiment-definition-select"></select></label><div class="tools"><button id="experiment-definition-load" class="secondary" disabled data-i18n="experiment_definition_load"></button><button id="experiment-definition-review" disabled data-i18n="experiment_reuse_review"></button></div></div><div id="experiment-definition-errors"></div><p id="experiment-reuse-empty" class="muted" data-i18n="experiment_reuse_empty"></p></section>
<form id="batch-form"><label><span data-i18n="source"></span><select name="source" required></select></label>
<button id="experiment-advice" type="button" class="secondary" data-i18n="experiment_advice"></button><div id="experiment-advice-view" hidden></div>
<div class="two-columns"><fieldset><legend data-i18n="batch_fields"></legend><div id="batch-fields"></div></fieldset>
<fieldset><legend data-i18n="batch_groups"></legend><div id="batch-groups"></div></fieldset></div>
<fieldset><legend data-i18n="selector"></legend><p data-i18n="selector_hint"></p><div id="batch-filters"></div></fieldset>
<div class="form-row"><label><span data-i18n="unit"></span><select name="unit"></select></label><label><span data-i18n="aggregation"></span><select name="reduce"></select></label></div>
<div class="form-row"><label><span data-i18n="expected_count"></span><input name="expected_count" type="number" min="1" max="10000" value="1" required></label><label><span data-i18n="seed_column"></span><input name="seed_column" value="seed"></label></div>
<label><span data-i18n="expected_seeds"></span><textarea name="expected_seeds" rows="2"></textarea></label>
<div class="form-row"><label><span data-i18n="display"></span><select name="display_kind"></select></label><label><span data-i18n="places"></span><input name="places" type="number" min="0" max="15" value="1" required></label></div>
<label class="check"><input name="percent_symbol" type="checkbox" checked><span data-i18n="percent_symbol"></span></label>
<details id="experiment-aliases"><summary data-i18n="experiment_aliases"></summary><p data-i18n="experiment_alias_hint"></p><div id="experiment-alias-rows"></div><button id="experiment-alias-add" type="button" class="secondary" data-i18n="experiment_alias_add"></button></details>
<p id="experiment-reference" class="muted" hidden></p>
<button type="submit" data-i18n="batch_generate"></button></form>
<details id="experiment-definitions"><summary data-i18n="experiment_definitions"></summary><p data-i18n="experiment_definition_hint"></p>
<form id="experiment-definition-form"><label><span data-i18n="template_name_label"></span><input name="name" required pattern="[A-Za-z](?:[A-Za-z0-9_.]|-){0,99}" placeholder="test_results_v1"></label><label><span data-i18n="rationale"></span><textarea name="rationale" required maxlength="4000"></textarea></label><button type="submit" data-i18n="experiment_definition_preview"></button></form>
<div id="experiment-definition-preview" hidden><pre id="experiment-definition-content"></pre><label class="check attest"><input id="experiment-definition-attest" type="checkbox"><span data-i18n="experiment_definition_attest"></span></label><button id="experiment-definition-save" disabled data-i18n="experiment_definition_save"></button></div></details>
<details id="batch-templates"><summary data-i18n="template_title"></summary><p data-i18n="template_hint"></p>
<div class="form-row"><label><span data-i18n="template_title"></span><select id="template-select"></select></label><div class="tools"><button id="template-load" class="secondary" data-i18n="template_load"></button><button id="template-export" class="secondary" data-i18n="template_export"></button></div></div>
<form id="template-save-form"><label><span data-i18n="template_name_label"></span><input name="name" required pattern="[A-Za-z](?:[A-Za-z0-9_.]|-){0,99}" placeholder="test_accuracy_v1"></label><button type="submit" data-i18n="template_save"></button></form>
<button id="template-import" class="secondary" data-i18n="template_import"></button><input id="template-file" type="file" accept=".json,application/json" hidden><div id="template-errors"></div></details></section>
</section><section id="step-review" class="step" hidden>
<section id="batch-catalog" class="panel" hidden><h2 data-i18n="batch_choose"></h2><p data-i18n="batch_positions_hint"></p>
<label class="check"><input id="batch-joint-toggle" type="checkbox"><span data-i18n="batch_joint_toggle"></span></label>
<div id="batch-joint" hidden></div><div id="batch-joint-pages" class="pagination" hidden></div>
<label><span data-i18n="batch_search"></span><input id="batch-search" type="search"></label>
<div class="two-columns"><div><div id="batch-choices"></div><div id="batch-choice-pages" class="pagination"></div></div>
<div><div id="batch-choice-evidence"></div><label><span data-i18n="search"></span><input id="batch-location-search" type="search"></label><div id="batch-locations"></div><div id="batch-location-pages" class="pagination"></div></div></div><div id="batch-native-page" class="repair-page" hidden></div>
<p id="batch-selected" role="status"></p><label><span data-i18n="batch_rationale"></span><textarea id="batch-rationale" rows="3" maxlength="4000"></textarea></label>
<button id="batch-stage" data-i18n="batch_stage" disabled></button></section>
<section class="panel"><div class="section-heading"><div><h2 data-i18n="review_title"></h2><p data-i18n="review_hint"></p></div><div class="tools"><button id="proposal-import" class="secondary" data-i18n="proposal_import"></button><input id="proposal-file" type="file" accept=".json,application/json" hidden><button id="preview" data-i18n="preview"></button></div></div>
<div id="draft-summary"></div><div id="review-items"></div><div id="review-diagnostics"></div>
<div id="accept-controls" hidden><button id="select-reviewed" class="secondary" data-i18n="select_reviewed"></button><button id="clear-reviewed" class="secondary" data-i18n="clear_selection"></button><label class="check attest"><input id="attest" type="checkbox"><span data-i18n="attest"></span></label><button id="accept" data-i18n="accept" disabled></button><p class="muted" data-i18n="accept_hint"></p></div></section></section>
</div></div></main><footer><span>PaperDelta <span id="version"></span></span><span data-i18n="footer"></span></footer>
</body></html>"""
