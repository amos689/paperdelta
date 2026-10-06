/* Local UI: exact selectors stay strings; project content is always textContent. */
"use strict";
(async () => {
  const $ = (id) => document.getElementById(id);
  const field = (form, name) => $(form).elements.namedItem(name);
  const node = (tag, text, cls) => {
    const el = document.createElement(tag);
    if (text !== undefined) el.textContent = text;
    if (cls) el.className = cls;
    return el;
  };
  let language = document.documentElement.lang;
  let token = location.hash.slice(1);
  try {
    if (token) sessionStorage.setItem("paperdelta-session", token);
    else token = sessionStorage.getItem("paperdelta-session") || "";
    language = sessionStorage.getItem("paperdelta-language") || language;
  } catch (_) { /* Storage can be disabled; the fragment still works. */ }
  history.replaceState(null, "", location.pathname);
  const strings = await (await fetch("/strings.json")).json();
  if (!Object.hasOwn(strings, language)) language = "en";
  let state, busy = false, sourcePreview, sourcePath, sourceAdvice, pageIndex = 0, pdfPage, pdfKey;
  let activeStep = "evidence", previewIdentity;
  let reviewWorkbench, batchWorkbench, candidatePage, candidateKey, candidatePending, candidateRequest, candidateSequence = 0, searchTimer;
  let pdfCandidates = [];
  let metricOffset = 0;
  const selected = new Set(), accepted = new Set();
  const stats = window.PaperDeltaStatistics;
  stats.mountContract($("metric-form")); stats.mountDisplay($("locations-form"));
  const t = (key, params = {}) => (strings[language][key] || key).replace(/\{(\w+)\}/g, (_, k) => params[k] ?? "");
  const contextText = (text) => text.replaceAll('\uFFFC', t('note_marker'));
  const text = (value) => typeof value === "string" ? value : JSON.stringify(value, null, 2);
  function options(select, values, translate = false, blank) {
    const old = select.value;
    select.replaceChildren();
    if (blank !== undefined) select.add(new Option(blank, ""));
    for (const value of values) select.add(new Option(translate ? t(value) : value, value));
    if ([...select.options].some((item) => item.value === old)) select.value = old;
  }
  function localize() {
    document.documentElement.lang = language;
    $("language").value = language;
    document.title = t("workbench") + " · PaperDelta";
    document.querySelectorAll("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    document.querySelectorAll("[data-placeholder]").forEach((el) => { el.placeholder = t(el.dataset.placeholder); });
    document.querySelector("nav.steps").setAttribute("aria-label", t("workflow"));
    options(field("metric-form", "reduce"), ["unique", "mean", "sum", "count", "statistics"], true);
    options(field("metric-form", "unit"), ["fraction", "percent", "scalar", "percentage_point", "count", "ratio"], true);
    options(field("derived-form", "operation"), ["difference", "ratio", "percentage_point_difference", "relative_change_percent"], true);
    options(field("locations-form", "display_kind"), ["percent", "decimal", "integer", "scientific"], true);
    $("pdf-zoom").textContent = t($("pdf-view").classList.contains("zoomed") ? "fit" : "zoom");
    const sheetChoice = field("sheet-form", "sheet").querySelector('option[value=""]');
    if (sheetChoice) sheetChoice.textContent = t("choose");
  }
  function notice(message) { $("message").textContent = message; $("message").hidden = !message; }
  function error(err) { $("error").textContent = err.message || String(err); $("error").hidden = false; }
  async function api(action, payload = {}) {
    const response = await fetch("/api", {
      method: "POST", headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json" },
      body: JSON.stringify({ action, language, revision: state?.revision || null, payload }),
    });
    const result = await response.json();
    if (!response.ok) {
      const err = new Error(result.message || t("connection_error"));
      err.code = result.error;
      throw err;
    }
    return result;
  }
  async function task(work) {
    if (busy) return;
    busy = true;
    document.body.classList.add("busy");
    document.body.setAttribute("aria-busy", "true");
    $("error").hidden = true;
    try { await work(); }
    catch (err) {
      error(err instanceof TypeError ? new Error(t("connection_error")) : err);
      if (err.code?.startsWith("STALE_") || err.code === "STUDIO_REVISION") {
        try { update((await api("state")).state); } catch (_) { /* Keep the original diagnostic. */ }
      }
    } finally {
      // State changes start a candidate read. Finish that view before exposing
      // the next action; an obsolete response must never repopulate the list.
      while (candidateRequest) {
        const pending = candidateRequest; await pending;
        if (pending === candidateRequest) break;
      }
      busy = false; document.body.classList.remove("busy"); document.body.removeAttribute("aria-busy");
    }
  }
  function update(next) {
    if (state && next.revision !== state.revision) {
      if (next.input_identity !== state.input_identity) selected.clear();
      for (const candidate of next.candidates || []) if (candidate.bound.length) selected.delete(candidate.candidate_id);
      candidatePage = null; candidateKey = candidatePending = null; candidateSequence++;
      pdfKey = pdfPage = null; pdfCandidates = []; $("pdf-panel").hidden = true;
    }
    state = next;
    if (next.preview?.proposal_id !== previewIdentity) {
      previewIdentity = next.preview?.proposal_id; accepted.clear(); $("attest").checked = false;
    }
    render();
  }
  async function change(action, payload = {}) { update((await api(action, payload)).state); }
  function table(rows, columns, labels = {}) {
    const wrapper = node("div", undefined, "table-scroll"), tab = node("table");
    const head = node("tr");
    for (const col of columns) head.append(node("th", labels[col] || col));
    const thead = node("thead"); thead.append(head); tab.append(thead);
    const body = node("tbody");
    for (const row of rows) { const tr = node("tr"); for (const col of columns) tr.append(node("td", text(row[col] ?? ""))); body.append(tr); }
    tab.append(body); wrapper.append(tab); return wrapper;
  }
  function pageButtons(container, offset, total, size, callback) {
    container.replaceChildren();
    if (total <= size) return;
    const prev = node("button", t("previous"), "secondary small"), next = node("button", t("next"), "secondary small");
    prev.type = next.type = "button"; prev.disabled = offset === 0; next.disabled = offset + size >= total;
    prev.onclick = () => callback(Math.max(0, offset - size)); next.onclick = () => callback(offset + size);
    container.append(prev, node("span", t("page_count", { start: offset + 1, end: Math.min(offset + size, total), total })), next);
  }
  function metricDetails(item) {
    const box = node("div");
    if (item.error) { box.append(node("p", item.message, "issue")); return box; }
    box.append(node("p", item.result.value + " · " + t(item.result.unit), "metric-value"));
    const def = item.definition;
    if (item.result.statistics) box.append(stats.summary(item.result.statistics, t, node));
    box.append(node("p", def.op ? `${t(def.op)}: ${def.args.join(" → ")}` : `${def.source} · ${def.field} · ${t(def.reduce)}`));
    if (def.where && Object.keys(def.where).length) {
      const selectors = node("dl", undefined, "selector-summary");
      for (const [key, value] of Object.entries(def.where)) selectors.append(node("dt", key), node("dd", text(value)));
      box.append(selectors);
    }
    const details = node("details"); details.append(node("summary", t("evidence_rows")));
    for (const evidence of item.result.evidence || []) {
      details.append(node("p", evidence.path || evidence.source || ""));
      if (evidence.provenance) details.append(provenanceView(evidence.provenance));
      if (evidence.format && evidence.locations?.length) details.append(node("pre", text(evidence.locations)));
      const records = evidence.records || evidence.rows || [];
      if (records.length) {
        const view = node("div"), pages = node("div", undefined, "pagination");
        const show = (offset) => {
          const rows = records.slice(offset, offset + 50);
          view.replaceChildren(table(rows, [...new Set(rows.flatMap((row) => Object.keys(row)))], { key: t("record_key"), value: t("record_value"), line: t("record_line") }));
          pageButtons(pages, offset, records.length, 50, show);
        };
        show(0); details.append(view, pages);
      } else details.append(node("pre", text(evidence)));
    }
    box.append(details); return box;
  }
  function render() {
    $("version").textContent = state.version;
    $("project").textContent = state.project;
    $("setup").hidden = state.initialized;
    $("workspace").hidden = !state.initialized;
    reviewWorkbench?.render(state);
    batchWorkbench?.render(state);
    $("stale").hidden = !state.stale;
    $("undo").disabled = !state.can_undo || state.stale;
    for (const id of ["load-draft", "download-report", "preview"]) $(id).disabled = state.stale;
    $("save-draft").disabled = !state.initialized;
    for (const id of ["source-form", "metric-form", "derived-form", "locations-form"]) $(id).querySelector("button[type=submit]").disabled = state.stale;
    if (!state.initialized) {
      $("paper-files").replaceChildren(); $("discovered-files").replaceChildren();
      for (const path of state.files.paths) {
        if (/\.(tex|docx|pdf|md|qmd)$/i.test(path)) $("paper-files").append(new Option(path));
        else {
          const button = node("button", path); button.type = "button";
          button.onclick = () => { const f = field("setup-form", "data"); const lines = f.value.split("\n").filter(Boolean); if (!lines.includes(path)) lines.push(path); f.value = lines.join("\n"); };
          $("discovered-files").append(button);
        }
      }
      $("file-limit").hidden = !state.files.limited;
      return;
    }
    $("receipt").hidden = !state.receipt;
    if (state.receipt) $("receipt").textContent = t("saved", { count: state.receipt.bindings.length, backup: state.receipt.backup });
    if (state.stale) { $("accept").disabled = true; return; }
    $("counts").replaceChildren();
    for (const key of ["confirmed", "pass", "mismatch", "unknown"]) {
      const count = node("div", undefined, "count"); count.append(node("strong", state.coverage[key]), node("span", t(key))); $("counts").append(count);
    }
    const pending = node("div", undefined, "count");
    pending.append(node("strong", state.coverage.unbound_numbers.length), node("span", t("unbound"))); $("counts").append(pending);
    if (state.check_exit_code === 2) $("counts").append(node("span", t("check_incomplete"), "status status-unknown"));
    $("source-list").replaceChildren(); $("data-files").replaceChildren();
    for (const source of state.discovered_sources) $("data-files").append(new Option(source.path));
    for (const [name, source] of Object.entries(state.sources)) {
      const card = node("div", undefined, "source-card"); card.append(node("strong", name), node("p", source.path));
      if (source.primary_key.length) card.append(node("p", t("primary_key") + ": " + source.primary_key.join(" + ")));
      const view = node("button", t("inspect_source"), "link-button"); view.onclick = () => task(() => inspectSource(source.path, 0, { sheet: source.sheet, cell_range: source.cell_range })); card.append(view); $("source-list").append(card);
    }
    if (!Object.keys(state.sources).length) $("source-list").append(node("p", t("no_sources"), "empty"));
    renderMetrics();
    const sourceSelect = field("metric-form", "source"), previousSource = sourceSelect.value;
    options(sourceSelect, Object.keys(state.sources), false, t("choose"));
    if (previousSource !== sourceSelect.value || !$("selectors").children.length) renderSelectors();
    for (const [form, name] of [["derived-form", "left"], ["derived-form", "right"], ["locations-form", "metric"]]) options(field(form, name), Object.keys(state.metrics), false, t("choose"));
    options($("file-filter"), state.candidate_files || [...new Set(state.candidates.map((item) => item.file))], false, t("all_files"));
    renderCandidates(); renderSelectedMetric(); renderReview();
    $("unsupported-list").replaceChildren();
    for (const issue of state.unsupported) $("unsupported-list").append(node("p", `${issue.file} · ${issue.code}\n${issue.message}${issue.action ? "\n" + issue.action : ""}`, "issue"));
    if (!state.unsupported.length) $("unsupported-list").append(node("p", t("no_unsupported"), "muted"));
    $("candidate-limit").hidden = true;
    paintPdf();
  }
  function renderMetrics() {
    const query = $("metric-search").value.toLowerCase();
    const entries = Object.entries(state.metrics).filter(([name]) => name.toLowerCase().includes(query));
    if (metricOffset >= entries.length) metricOffset = 0;
    $("metric-list").replaceChildren();
    for (const [name, metric] of entries.slice(metricOffset, metricOffset + 20)) {
      const card = node("div", undefined, "metric-card"); card.append(node("strong", name), metricDetails(metric)); $("metric-list").append(card);
    }
    if (!entries.length) $("metric-list").append(node("p", t("no_metrics"), "empty"));
    pageButtons($("metric-pages"), metricOffset, entries.length, 20, (offset) => { metricOffset = offset; renderMetrics(); });
  }
  $("metric-search").oninput = () => { metricOffset = 0; renderMetrics(); };
  function setStep(step) {
    activeStep = step;
    for (const name of ["evidence", "locations", "batch", "review"]) $("step-" + name).hidden = name !== step;
    document.querySelectorAll("nav [data-step]").forEach((button) => {
      button.classList.toggle("active", button.dataset.step === step);
      button.setAttribute("aria-current", button.dataset.step === step ? "step" : "false");
    });
  }
  function renderSelectors(preserve = false) {
    const previous = new Map();
    if (preserve) for (const row of $("selectors").querySelectorAll(".selector-row")) {
      const check = row.querySelector("input[type=checkbox]");
      previous.set(check.dataset.column, [check.checked, row.querySelector("input[type=text]").value]);
    }
    const source = state?.sources?.[field("metric-form", "source").value];
    field("metric-form", "field").required = source?.format !== "json";
    field("metric-form", "field").placeholder = source?.format === "json" ? "/results/accuracy" : "accuracy";
    $("selectors").replaceChildren(); $("metric-fields").replaceChildren();
    if (!source) return;
    for (const [column, kind] of Object.entries(source.columns)) {
      if (kind !== "string") $("metric-fields").append(new Option(column));
      const row = node("div", undefined, "selector-row"), label = node("label", undefined, "check"), check = node("input"), value = node("input");
      check.type = "checkbox"; check.dataset.column = column; value.type = "text"; value.disabled = true;
      if (previous.has(column)) { [check.checked, value.value] = previous.get(column); value.disabled = !check.checked; }
      value.setAttribute("aria-label", t("selector_value", { column }));
      check.onchange = () => { value.disabled = !check.checked; if (check.checked) value.focus(); };
      label.append(check, node("span", column + " · " + t(kind))); row.append(label, value); $("selectors").append(row);
    }
    if (source.format === "json") $("selectors").append(node("p", t("json_pointer_hint"), "muted"));
  }
  async function inspectSource(path, offset = 0, selection = null) {
    selection ||= sourcePath === path ? { sheet: sourcePreview?.sheet, cell_range: sourcePreview?.cell_range } : {};
    const next = (await api("source-preview", { path, offset, ...selection })).source;
    const newPath = sourcePath !== path || sourcePreview?.sheet !== next.sheet || sourcePreview?.cell_range !== next.cell_range || sourcePreview?.hash !== next.hash;
    sourcePreview = next; sourcePath = path;
    $("add-source").open = true; $("source-form").hidden = !!next.needs_selection; $("source-title").textContent = path;
    field("source-path-form", "path").value = path;
    $("sheet-form").hidden = next.format !== "xlsx";
    if (next.format === "xlsx") {
      options(field("sheet-form", "sheet"), next.sheets, false, t("choose"));
      if (next.sheet) field("sheet-form", "sheet").value = next.sheet;
      if (next.cell_range) field("sheet-form", "cell_range").value = next.cell_range;
      else if (newPath) field("sheet-form", "cell_range").value = "";
    }
    renderSourceSample();
    if (newPath) {
      sourceAdvice = null; $("source-advice").hidden = true;
      $("column-types").replaceChildren();
      if (next.format !== "json") {
        $("column-types").append(node("p", t(next.format === "records" ? "export_contract" : "primary_key_hint"), "muted"));
        for (const column of next.columns) {
          const row = node("div", undefined, "check-row"), key = node("input"), label = node("label", column), select = node("select");
          key.type = "checkbox"; key.dataset.column = column; key.setAttribute("aria-label", t("key_column", { column }));
          select.dataset.column = column; select.setAttribute("aria-label", t("type_column", { column }));
          options(select, ["string", "integer", "decimal"], true); row.append(key, label, select); $("column-types").append(row);
          if (next.format === "records") {
            key.checked = next.primary_key.includes(column); key.disabled = true;
            select.value = next.column_types[column]; select.disabled = true;
          }
        }
      }
    }
  }
  function renderSourceSample() {
    if (!sourcePreview) return;
    $("source-sample").replaceChildren(table(sourcePreview.sample, sourcePreview.columns || ["pointer", "value"]));
    $("source-provenance").replaceChildren();
    if (sourcePreview.provenance) $("source-provenance").append(provenanceView(sourcePreview.provenance));
    pageButtons($("source-pages"), sourcePreview.offset || 0, sourcePreview.record_count || 0, 100, (offset) => task(() => inspectSource(sourcePath, offset)));
  }
  async function inspectSourceAdvice() {
    const selectedKey = $("source-advice").querySelector("input:checked")?.value;
    const advice = await api("source-advice", {path: sourcePath, sheet: sourcePreview.sheet, cell_range: sourcePreview.cell_range});
    if (advice.input_hash !== sourcePreview.hash) throw new Error(t("source_advice_stale"));
    sourceAdvice = advice;
    const box = $("source-advice"); box.replaceChildren(); box.hidden = false;
    box.append(node("h3", t("source_advice_show")), node("p", advice.notice || advice.reason));
    if (!advice.available) return;
    for (const [name, column] of Object.entries(advice.columns)) {
      const row = node("p"); row.append(node("strong", name + " · " + t(column.type)), node("span", " — " + column.reason)); box.append(row);
    }
    for (const message of advice.conflicts) box.append(node("p", message, "notice"));
    box.append(node("p", advice.experiment.reason, "muted"));
    for (const [index, key] of advice.primary_keys.entries()) {
      const label = node("label", undefined, "check"), input = node("input");
      input.type = "radio"; input.name = "advice-key"; input.value = String(index); input.checked = selectedKey === String(index);
      label.append(input, node("span", key.columns.join(" + ") + " — " + key.reason)); box.append(label);
    }
    const apply = node("button", t("source_advice_apply"), "secondary"); apply.type = "button";
    apply.disabled = !advice.can_apply || !advice.primary_keys.length || !box.querySelector("input:checked");
    box.querySelectorAll("input").forEach(input => input.onchange = () => {apply.disabled = !advice.can_apply;});
    apply.onclick = () => {
      const key = sourceAdvice.primary_keys[Number(box.querySelector("input:checked")?.value)];
      if (!key || sourceAdvice.input_hash !== sourcePreview.hash) return;
      $("column-types").querySelectorAll("select").forEach(select => {if (!select.disabled) select.value = sourceAdvice.columns[select.dataset.column].type;});
      $("column-types").querySelectorAll("input").forEach(input => {if (!input.disabled) input.checked = key.columns.includes(input.dataset.column);});
      notice(t("source_advice_applied"));
    };
    box.append(apply);
  }
  function provenanceView(origin) {
    const box = node("details"); box.append(node("summary", t("provenance")));
    box.append(node("p", `${origin.provider} · ${origin.origin}`), node("p", origin.created_at), node("p", t("precision_" + origin.precision)), node("pre", text(origin.selection)), node("code", origin.export_id));
    return box;
  }
  function toggleCandidate(item, checked) {
    if (state.stale || item.bound.length) return;
    if (checked && selected.size >= 200) { error(new Error(t("selection_limit"))); return; }
    if (checked) selected.add(item.candidate_id); else selected.delete(item.candidate_id);
    renderCandidates(); paintPdf();
  }
  function renderCandidates() {
    if (!state?.candidates || state.stale) return;
    const query = { query: $("search").value, file: $("file-filter").value || null, include_bound: $("show-bound").checked, offset: pageIndex * 30, limit: 30 };
    const key = JSON.stringify([state.revision, language, query]);
    if (candidateKey !== key) {
      if (candidatePending !== key) {
        candidatePending = key; const sequence = ++candidateSequence;
        $("candidates").replaceChildren(node("p", t("loading_locations"), "muted"));
        candidateRequest = api("candidates", query).then((result) => {
          if (sequence !== candidateSequence || result.revision !== state.revision) return;
          candidatePage = result; candidateKey = key; candidatePending = null; renderCandidates();
        }).catch(async (err) => {
          if (sequence !== candidateSequence) return;
          candidatePending = null;
          if (err.code?.startsWith("STALE_") || err.code === "STUDIO_REVISION") {
            const latest = await api("state");
            if (sequence === candidateSequence) update(latest.state);
          } else error(err);
        }).catch(error);
      }
      return;
    }
    const focused = document.activeElement?.closest(".candidate")?.dataset.candidate;
    const candidates = candidatePage.items;
    $("candidates").replaceChildren(); $("selection-count").textContent = t("selected_count", { count: selected.size });
    for (const item of candidates) {
      const card = node("article", undefined, "candidate" + (selected.has(item.candidate_id) ? " selected" : "") + (item.bound.length ? " bound" : ""));
      card.dataset.candidate = item.candidate_id;
      const top = node("div", undefined, "candidate-top"), label = node("label", undefined, "check"), checkbox = node("input");
      checkbox.type = "checkbox"; checkbox.checked = selected.has(item.candidate_id); checkbox.disabled = !!item.bound.length || state.stale;
      checkbox.onchange = () => { toggleCandidate(item, checkbox.checked); if (item.format === "pdf") task(() => showPdf(item)); };
      label.append(checkbox, node("span", item.label)); top.append(label);
      if (item.format === "pdf") { const show = node("button", t("view_page"), "link-button"); show.onclick = () => task(() => showPdf(item, true)); top.append(show); }
      const context = node("p", undefined, "candidate-context"); context.append(node("span", contextText(item.context_before)), node("mark", item.text), node("span", contextText(item.context_after)));
      if (item.bound.length) context.append(node("span", t("bound_to") + ": " + item.bound.join(", "), "binding-label"));
      card.append(top, context); $("candidates").append(card);
    }
    if (!candidates.length) $("candidates").append(node("p", t("no_locations"), "empty"));
    pageButtons($("candidate-pages"), candidatePage.offset, candidatePage.total, candidatePage.limit, (offset) => { pageIndex = offset / 30; renderCandidates(); $("candidates").scrollIntoView({ block: "start" }); });
    if (focused) for (const card of $("candidates").children) if (card.dataset.candidate === focused) card.querySelector("input")?.focus({ preventScroll: true });
  }
  function renderSelectedMetric() {
    $("selected-metric").replaceChildren();
    const metric = state?.metrics?.[field("locations-form", "metric").value];
    stats.setDisplayActive($("locations-form"), !!metric?.definition?.statistics);
    if (metric) $("selected-metric").append(metricDetails(metric));
  }
  async function showPdf(item, reveal = false) {
    const key = item.file + ":" + item.locator.page;
    if (pdfKey !== key) {
      const response = await api("page", { file: item.file, page: item.locator.page });
      pdfPage = response.preview.pages[0]; pdfCandidates = response.candidates; pdfKey = key;
    }
    $("pdf-panel").hidden = false; paintPdf();
    if (reveal) $("pdf-panel").scrollIntoView({ block: "start" });
  }
  function paintPdf() {
    if (!pdfPage || !state?.candidates || state.stale) return;
    const focused = document.activeElement?.dataset.pdfCandidate;
    const box = $("pdf-page"); box.replaceChildren();
    $("pdf-caption").textContent = pdfPage.file + " · " + t("page_number", { page: pdfPage.page });
    if (!pdfPage.image) { box.append(node("p", pdfPage.message || t("page_unavailable"), "muted")); return; }
    const image = node("img"); image.src = pdfPage.image; image.alt = t("page_alt", { file: pdfPage.file, page: pdfPage.page });
    box.append(image);
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    const [x0, y0, x1, y1] = pdfPage.page_box.map(Number); svg.setAttribute("viewBox", `${x0} ${y0} ${x1 - x0} ${y1 - y0}`);
    for (const item of pdfCandidates) {
      const rect = document.createElementNS(svg.namespaceURI, "rect"), [x, y, right, bottom] = item.locator.bbox.map(Number);
      rect.dataset.pdfCandidate = item.candidate_id;
      for (const [key, val] of Object.entries({ x, y, width: right - x, height: bottom - y, rx: 1, tabindex: item.bound.length ? -1 : 0, role: "checkbox", "aria-checked": selected.has(item.candidate_id), "aria-disabled": !!item.bound.length, "aria-label": item.text + " · " + item.label })) rect.setAttribute(key, val);
      rect.classList.toggle("selected", selected.has(item.candidate_id)); rect.classList.toggle("bound", !!item.bound.length);
      rect.onclick = () => toggleCandidate(item, !selected.has(item.candidate_id));
      rect.onkeydown = (event) => { if (event.key === " " || event.key === "Enter") { event.preventDefault(); toggleCandidate(item, !selected.has(item.candidate_id)); } };
      svg.append(rect);
    }
    box.append(svg);
    if (focused) for (const rect of svg.children) if (rect.dataset.pdfCandidate === focused) rect.focus({ preventScroll: true });
  }
  function renderReview() {
    const additions = state.additions;
    $("staged-count").textContent = ["occurrences", "claims", "figures"].reduce((total, group) => total + Object.keys(additions[group]).length, 0);
    $("draft-summary").replaceChildren(); $("review-items").replaceChildren(); $("review-diagnostics").replaceChildren();
    for (const group of ["sources", "metrics", "occurrences", "claims", "figures"]) for (const name of Object.keys(additions[group])) $("draft-summary").append(node("span", t(group) + ": " + name, "draft-chip"));
    const preview = state.preview; $("accept-controls").hidden = !preview;
    if (!preview) { $("review-items").append(node("p", t("preview_empty"), "empty")); return; }
    for (const item of preview.items) {
      const card = node("article", undefined, "preview-card"), label = node("label", undefined, "check"), checkbox = node("input");
      checkbox.type = "checkbox"; checkbox.checked = accepted.has(item.binding); checkbox.dataset.binding = item.binding;
      checkbox.onchange = () => { if (checkbox.checked) accepted.add(item.binding); else accepted.delete(item.binding); updateAccept(); };
      label.append(checkbox, node("span", item.binding)); card.append(label, node("p", item.label));
      const context = node("p", undefined, "candidate-context");
      context.append(node("span", contextText(item.context_before)), node("mark", item.candidate_text), node("span", contextText(item.context_after))); card.append(context);
      const values = node("div", undefined, "preview-values");
      if (item.group === "occurrences") values.append(node("code", item.actual ?? item.location?.text ?? ""), node("span", "→"), node("code", item.expected ?? ""));
      values.append(node("span", t(item.status), "status status-" + item.status));
      card.append(values, node("p", t("rationale") + ": " + item.rationale));
      if (item.definition_json) { const definition = node("details"); definition.append(node("summary", t("proposal_definition")), node("pre", item.definition_json)); card.append(definition); }
      const metric = state.metrics[item.metric]; if (metric) card.append(metricDetails(metric));
      $("review-items").append(card);
    }
    for (const issue of preview.diagnostics) $("review-diagnostics").append(node("p", `${issue.rule}: ${issue.message}`, "issue"));
    updateAccept();
  }
  function updateAccept() { $("accept").disabled = state?.stale || !state?.preview || !accepted.size || !$("attest").checked; }
  function download(contents, filename, mime) {
    const url = URL.createObjectURL(new Blob([contents], { type: mime })), link = node("a");
    link.href = url; link.download = filename; document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
  let diagnosticPreview = null;
  $("diagnostic-preview").onclick = () => task(async () => {
    diagnosticPreview = await api("diagnostic-preview");
    $("diagnostic-content").textContent = JSON.stringify(diagnosticPreview.files, null, 2);
    $("diagnostic-attest").checked = false; $("diagnostic-export").disabled = true;
    $("diagnostic-panel").hidden = false; $("diagnostic-panel").open = true;
  });
  $("diagnostic-attest").onchange = () => { $("diagnostic-export").disabled = !diagnosticPreview || !$("diagnostic-attest").checked; };
  $("diagnostic-export").onclick = () => task(async () => {
    if (!diagnosticPreview || !$("diagnostic-attest").checked) return;
    const result = await api("diagnostic-export", {preview_id: diagnosticPreview.preview_id});
    download(Uint8Array.from(atob(result.base64), (c) => c.charCodeAt(0)), "paperdelta-diagnostics.zip", "application/zip");
  });
  document.querySelectorAll("[data-step]").forEach((button) => { button.onclick = () => setStep(button.dataset.step); });
  $("setup-form").onsubmit = (event) => { event.preventDefault(); task(async () => { await change("initialize", { paper: field("setup-form", "paper").value.trim(), data: field("setup-form", "data").value.split("\n").map((v) => v.trim()).filter(Boolean) }); notice(t("initialized")); }); };
  $("source-path-form").onsubmit = (event) => { event.preventDefault(); task(() => inspectSource(field("source-path-form", "path").value.trim())); };
  $("source-advice-show").onclick = () => task(inspectSourceAdvice);
  $("sheet-form").onsubmit = (event) => { event.preventDefault(); task(() => inspectSource(sourcePath, 0, { sheet: field("sheet-form", "sheet").value, cell_range: field("sheet-form", "cell_range").value.trim() })); };
  $("source-form").onsubmit = (event) => {
    event.preventDefault(); task(async () => {
      const columns = Object.fromEntries([...$("column-types").querySelectorAll("select")].map((s) => [s.dataset.column, s.value]));
      const primary_key = [...$("column-types").querySelectorAll("input:checked")].map((i) => i.dataset.column);
      await change("source", { name: field("source-form", "name").value, path: sourcePath, format: sourcePreview.format, columns, primary_key, source_hash: sourcePreview.hash, sheet: sourcePreview.sheet, cell_range: sourcePreview.cell_range });
      $("add-source").open = false; $("add-metric").open = true; notice(t("source_staged"));
    });
  };
  field("metric-form", "source").onchange = () => renderSelectors();
  $("metric-form").onsubmit = (event) => {
    event.preventDefault(); task(async () => {
      const val = (name) => field("metric-form", name).value;
      const where = Object.fromEntries([...$("selectors").querySelectorAll(".selector-row")].filter((row) => row.querySelector("input[type=checkbox]").checked).map((row) => [row.querySelector("input[type=checkbox]").dataset.column, row.querySelector("input[type=text]").value]));
      const seeds = val("expected_seeds").split("\n").filter((v) => v !== "");
      await change("metric", { name: val("name"), source: val("source"), field: val("field"), unit: val("unit"), reduce: val("reduce"), where, expected_count: Number(val("expected_count")), seed_column: val("seed_column"), expected_seeds: seeds.length ? seeds : null, statistics: stats.contract($("metric-form")) });
      field("locations-form", "metric").value = val("name"); renderSelectedMetric(); $("add-metric").open = false; notice(t("metric_staged"));
    });
  };
  $("derived-form").onsubmit = (event) => { event.preventDefault(); task(async () => { const payload = Object.fromEntries(new FormData($("derived-form"))); await change("derived", payload); $("add-derived").open = false; notice(t("metric_staged")); }); };
  field("locations-form", "metric").onchange = renderSelectedMetric;
  $("locations-form").onsubmit = (event) => {
    event.preventDefault(); task(async () => {
      if (!selected.size) throw new Error(t("choose_locations"));
      const val = (name) => field("locations-form", name).value, ids = [...selected];
      const statistics = stats.display($("locations-form"));
      const names = stats.compounds.has(statistics?.component) ? [val("prefix")] : ids.map((_, i) => val("prefix") + (ids.length > 1 ? "_" + (i + 1) : ""));
      const table_identity = field("locations-form", "use_table_identity").checked ? {header_rows: Number(val("table_header_rows")), row_prefix: val("table_row_prefix").split("\n").map((s) => s.trim()).filter(Boolean)} : null;
      await change("locations", { metric: val("metric"), candidate_ids: ids, names, display_kind: val("display_kind"), places: Number(val("places")), percent_symbol: field("locations-form", "percent_symbol").checked, rationale: val("rationale"), statistics, table_identity });
      selected.clear(); renderCandidates(); notice(t("locations_staged", { count: names.length })); setStep("review");
    });
  };
  for (const id of ["file-filter", "show-bound"]) $(id).onchange = () => { pageIndex = 0; renderCandidates(); };
  $("search").oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => { pageIndex = 0; renderCandidates(); }, 180); };
  $("clear-selection").onclick = () => { selected.clear(); renderCandidates(); paintPdf(); };
  $("preview").onclick = () => task(async () => { await change("preview"); notice(t("preview_ready")); });
  $("attest").onchange = updateAccept;
  $("select-reviewed").onclick = () => {
    if (state?.stale || !state?.preview) return;
    for (const item of state.preview.items) accepted.add(item.binding);
    renderReview();
  };
  $("clear-reviewed").onclick = () => { accepted.clear(); renderReview(); };
  $("accept").onclick = () => task(async () => { await change("accept", { proposal_id: state.preview.proposal_id, selected: [...accepted] }); selected.clear(); pdfKey = pdfPage = null; $("pdf-panel").hidden = true; notice(t("accepted_notice")); });
  $("undo").onclick = () => task(async () => { await change("undo"); notice(t("undone")); });
  $("refresh").onclick = () => task(async () => {
    if (state.initialized && !confirm(t("refresh_confirm"))) return;
    await change("refresh"); selected.clear(); accepted.clear(); pdfKey = pdfPage = null; $("pdf-panel").hidden = true; render(); notice(t("refreshed"));
  });
  $("save-draft").onclick = () => task(async () => { download((await api("draft-export")).json, "paperdelta-draft.json", "application/json"); notice(t("draft_saved")); });
  $("load-draft").onclick = () => $("draft-file").click();
  $("draft-file").onchange = () => task(async () => {
    const file = $("draft-file").files[0]; $("draft-file").value = "";
    if (!file) return;
    if (file.size > 900000) throw new Error(t("draft_limit"));
    // Send raw JSON text, avoiding a parse/stringify roundtrip that rounds Decimal.
    const draftText = await file.text();
    const response = await fetch("/api", { method: "POST", headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json" }, body: `{"action":"draft-import","language":${JSON.stringify(language)},"revision":${JSON.stringify(state.revision)},"payload":{"draft":${draftText}}}` });
    const result = await response.json(); if (!response.ok) { const err = new Error(result.message); err.code = result.error; throw err; }
    update(result.state); notice(t("draft_loaded"));
  });
  $("download-report").onclick = () => task(async () => { download((await api("report")).html, "paperdelta-report.html", "text/html"); notice(t("report_saved")); });
  $("pdf-zoom").onclick = () => { const zoomed = $("pdf-view").classList.toggle("zoomed"); $("pdf-zoom").textContent = t(zoomed ? "fit" : "zoom"); };
  $("language").onchange = () => task(async () => {
    language = $("language").value; try { sessionStorage.setItem("paperdelta-language", language); } catch (_) { /* Optional preference. */ }
    localize(); notice(""); update((await api("state")).state); renderSelectors(true); renderSourceSample();
    $("column-types").querySelectorAll("select").forEach((s) => options(s, ["string", "integer", "decimal"], true));
    $("column-types").querySelectorAll("input").forEach((el) => el.setAttribute("aria-label", t("key_column", { column: el.dataset.column })));
    $("column-types").querySelectorAll("select").forEach((el) => el.setAttribute("aria-label", t("type_column", { column: el.dataset.column })));
    const keyHint = $("column-types").querySelector("p"); if (keyHint) keyHint.textContent = t(sourcePreview?.format === "records" ? "export_contract" : "primary_key_hint");
    if (sourceAdvice) await inspectSourceAdvice();
    await reviewWorkbench.localize();
    await batchWorkbench.localize();
  });
  window.addEventListener("beforeunload", (event) => {
    if (state?.additions && Object.values(state.additions).some((group) => Object.keys(group).length)) { event.preventDefault(); event.returnValue = ""; }
  });
  reviewWorkbench = window.createPaperDeltaReview({ t, node, api, task, update, download, pageButtons, metricDetails, state: () => state, busy: () => busy });
  batchWorkbench = window.createPaperDeltaBatch({ t, node, api, task, update, download, pageButtons, metricDetails, notice, setStep, state: () => state });
  localize(); setStep(activeStep);
  await batchWorkbench.localize();
  await task(async () => { update((await api("state")).state); if (state.initialized) await reviewWorkbench.load(); });
})();
