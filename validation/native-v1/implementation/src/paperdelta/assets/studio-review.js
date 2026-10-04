/* Ongoing review UI. All user content is rendered as text, never HTML. */
window.createPaperDeltaReview = function (ctx) {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const { t, node, api, task, update, download, pageButtons } = ctx;
  let detail, mode, declarations = [], editing, controls = [], broken = [], repairChoice;
  let maintenanceId, repairId, rebuildId, selectedClaim, polling = false, recoveryId, rebuildRecord;
  let impactOffset = 0;
  function button(label, action, className = 'secondary small') {
    const item = node('button', label, className); item.type = 'button';
    item.onclick = () => task(action); return item;
  }
  function status(value) { return node('span', t(value || 'unknown'), 'status status-' + (value || 'unknown')); }
  function compact(value) { return value == null ? '—' : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value); }
  function currentReport() { return detail?.report; }
  async function load() { detail = await api('review'); paintReport(); }
  function setMode(value) {
    mode = value; paintMode();
    if (mode === 'review' && !detail) task(load);
  }
  function paintMode() {
    if (!mode) mode = ctx.state()?.coverage?.confirmed ? 'review' : 'binding';
    $('review-workspace').hidden = mode !== 'review';
    $('binding-workspace').hidden = mode !== 'binding';
    for (const element of document.querySelectorAll('[data-mode]')) {
      element.classList.toggle('active', element.dataset.mode === mode);
      element.setAttribute('aria-pressed', String(element.dataset.mode === mode));
    }
  }
  function paintCounts(container, counts) {
    container.replaceChildren();
    for (const key of ['confirmed', 'pass', 'mismatch', 'unknown']) {
      const cell = node('div', undefined, 'count'); cell.append(node('strong', counts?.[key] ?? 0), node('span', t(key))); container.append(cell);
    }
  }
  function paintReport() {
    if (!detail) return;
    const report = detail.report, summary = detail.summary;
    $('review-workspace').dataset.generation = String(summary.generation);
    $('review-workspace').dataset.reviewState = summary.state;
    $('watch-state').textContent = t(summary.state === 'pending' ? 'watch_pending' : 'watch_current');
    $('watch-state').className = 'status ' + (summary.state === 'pending' ? 'status-unknown' : 'status-pass');
    const changed = summary.changed_paths || [];
    $('watch-details').hidden = !changed.length;
    $('watch-changes').textContent = t('rechecked_files', { count: changed.length });
    $('watch-paths').replaceChildren(...changed.map((path) => node('li', path)));
    paintCounts($('ongoing-counts'), summary.counts);
    const selected = summary.baseline || '';
    $('baseline-select').replaceChildren(new Option(t('no_baseline'), ''));
    for (const snapshot of detail.snapshots) {
      const option = new Option(snapshot.name + (snapshot.error ? ' · ' + snapshot.error : ''), snapshot.name);
      option.disabled = !!snapshot.error; $('baseline-select').append(option);
    }
    $('baseline-select').value = selected;
    $('review-actions').replaceChildren();
    for (const action of report?.actions || []) $('review-actions').append(node('span', t('action_' + action.kind) + ' · ' + action.subjects.length, 'draft-chip'));
    $('impact-groups').replaceChildren();
    const query = $('impact-search').value.toLowerCase();
    const groups = (report?.impact_groups || []).filter((group) => [group.metric, ...group.sources, ...group.occurrences, ...group.claims, ...group.figures].some((value) => value.toLowerCase().includes(query)));
    if (impactOffset >= groups.length) impactOffset = 0;
    for (const group of groups.slice(impactOffset, impactOffset + 20)) {
      const card = node('article', undefined, 'impact-card'), metric = report.metrics[group.metric];
      const change = report.changes.find((item) => item.metric === group.metric);
      card.append(node('h3', group.metric), node('p', group.sources.join(' · '), 'muted'));
      const values = node('div', undefined, 'preview-values');
      if (change) values.append(node('span', t('previous_value') + ': ' + compact(change.before)), node('span', '→'));
      values.append(node('strong', t('current_value') + ': ' + compact(metric?.value)), node('span', t(metric?.unit || 'unknown')));
      card.append(values);
      if (change) card.append(node('p', t('change_' + change.kind), 'muted'));
      for (const section of ['occurrences', 'claims', 'figures']) for (const name of group[section]) {
        const item = report[section][name], row = node('div', undefined, 'impact-row');
        const position = detail.positions?.[section + ':' + name];
        row.append(status(item.status), node('strong', name));
        row.append(node('span', position?.label || item.location?.file || item.path || '', 'muted'));
        if (item.actual != null || item.expected != null) row.append(node('span', compact(item.actual) + ' → ' + compact(item.expected)));
        if (item.location?.text) row.append(node('p', position?.context || item.location.context || item.location.text, 'context-text'));
        card.append(row);
      }
      const evidence = node('details'), heading = node('summary', t('inspect_evidence'));
      evidence.append(heading, ctx.metricDetails(metric?.status === 'ok' ? { result: metric, definition: metric.definition } : { error: true, message: t('unknown') })); card.append(evidence);
      $('impact-groups').append(card);
    }
    if (!groups.length) $('impact-groups').append(node('p', t('no_impacts'), 'empty'));
    pageButtons($('impact-pages'), impactOffset, groups.length, 20, (offset) => { impactOffset = offset; paintReport(); });
    $('ongoing-diagnostics').replaceChildren();
    for (const item of report?.diagnostics || []) $('ongoing-diagnostics').append(node('p', item.subject + ' · ' + item.message, 'issue'));
    $('removed-bindings').replaceChildren();
    for (const [group, names] of Object.entries(report?.removed_bindings || {})) if (names.length) $('removed-bindings').append(node('p', t('removed_since_snapshot') + ': ' + group + ' · ' + names.join(', '), 'issue'));
    paintClaims();
  }
  function paintClaims() {
    $('claim-list').replaceChildren();
    for (const [name, claim] of Object.entries(currentReport()?.claims || {})) {
      const card = node('div', undefined, 'source-card');
      card.append(node('strong', name), status(claim.status), node('p', claim.location?.text || '', 'context-text'));
      card.append(node('p', t('review_' + claim.review), 'muted'));
      if (claim.state_fingerprint) card.append(button(t('record_claim_review'), async () => {
        selectedClaim = { name, state: claim.state_fingerprint };
        $('claim-review-name').textContent = name; $('claim-review-form').hidden = false;
        $('claim-attest').checked = false; $('claim-note').value = '';
        $('claim-review-form').scrollIntoView({ block: 'center' });
      }));
      $('claim-list').append(card);
    }
    if (!Object.keys(currentReport()?.claims || {}).length) $('claim-list').append(node('p', t('no_claims'), 'muted'));
  }
  async function loadDeclarations() {
    declarations = (await api('declarations')).items; paintDeclarations();
  }
  function paintDeclarations() {
    const query = $('declaration-search').value.toLowerCase(); $('declaration-list').replaceChildren();
    for (const item of declarations.filter((entry) => [entry.id, entry.definition.file, entry.definition.path].join(' ').toLowerCase().includes(query))) {
      const row = node('div', undefined, 'declaration-row');
      row.append(node('span', item.id));
      if (item.state?.status) row.append(status(item.state.status));
      else row.append(node('span', t(item.group), 'muted'));
      row.append(button(t('edit_declaration'), async () => edit(item)));
      $('declaration-list').append(row);
    }
  }
  function edit(item) {
    editing = item; controls = []; $('declaration-fields').replaceChildren();
    $('declaration-form').hidden = false; $('declaration-name').textContent = item.id;
    $('remove-declaration').checked = false; $('declaration-reason').value = '';
    $('declaration-form').querySelector('button[type=submit]').disabled = false;
    $('remove-dependents').hidden = true; $('dependent-choices').replaceChildren();
    for (const identity of item.dependents) {
      const label = node('label', undefined, 'check'), checkbox = node('input');
      checkbox.type = 'checkbox'; checkbox.value = identity;
      checkbox.onchange = validateRemoval;
      label.append(checkbox, node('span', identity)); $('dependent-choices').append(label);
    }
    for (const field of item.fields) {
      const label = node('label'), key = field.path.join('.'), last = field.path.at(-1);
      const caption = node('span'); label.append(caption);
      const choices = field.kind === 'string' ? ({
        unit: ['scalar', 'fraction', 'percent', 'percentage_point', 'count', 'ratio'],
        reduce: ['unique', 'mean', 'sum', 'count'],
        format: ['csv', 'json', 'tsv', 'xlsx', 'records'],
        op: ['difference', 'ratio', 'percentage_point_difference', 'relative_change_percent'],
        'display.kind': ['decimal', 'percent', 'integer', 'scientific'],
        'predicate.op': ['greater_than', 'greater_equal', 'less_than', 'less_equal', 'equal', 'best_in_set'],
        'predicate.direction': ['maximize', 'minimize'],
        'predicate.right.unit': ['scalar', 'fraction', 'percent', 'percentage_point', 'count', 'ratio'],
      }[key] || (field.path[0] === 'columns' ? ['string', 'integer', 'decimal'] : null)) : null;
      const control = node(choices ? 'select' : field.kind === 'json' ? 'textarea' : 'input');
      if (choices) for (const value of choices) control.append(new Option(t(value), value));
      control.dataset.field = key;
      if (field.kind === 'boolean') { control.type = 'checkbox'; control.checked = JSON.parse(field.json); label.className = 'check'; }
      else {
        control.value = field.kind === 'string' ? JSON.parse(field.json) : field.json.trim();
        if (field.kind === 'number') control.inputMode = 'decimal';
        if (field.kind === 'json') { control.rows = last === 'anchor' ? 5 : 2; label.className = 'advanced-field'; }
      }
      label.append(control); controls.push({ field, control, caption, choices }); $('declaration-fields').append(label);
    }
    localizeFields();
    $('declaration-form').scrollIntoView({ block: 'start' });
  }
  function localizeFields() {
    for (const { field, control, caption, choices } of controls) {
      caption.textContent = field.path.map((part) => t('field_' + part) === 'field_' + part ? part : t('field_' + part)).join(' · ');
      control.setAttribute('aria-label', caption.textContent);
      if (choices) for (const option of control.options) option.textContent = t(option.value);
    }
  }
  function validateRemoval() {
    $('declaration-form').querySelector('button[type=submit]').disabled = $('remove-declaration').checked && !!$('dependent-choices').querySelector('input:not(:checked)');
  }
  async function localize() {
    localizeFields(); paintDeclarations();
    if (ctx.state()?.initialized) await load();
  }
  function paintMaintenance(state) {
    const preview = state.maintenance;
    if (preview?.proposal_id !== maintenanceId) { maintenanceId = preview?.proposal_id; $('maintenance-attest').checked = false; }
    $('maintenance-preview').replaceChildren(); $('maintenance-confirm').hidden = !preview;
    $('accept-maintenance').disabled = !preview || state.stale || !$('maintenance-attest').checked;
    if (!preview) return;
    const title = node('h3', t('affected_declarations')); $('maintenance-preview').append(title, node('p', preview.affected.join(', ')));
    $('maintenance-preview').append(node('p', t('coverage_change', { before: preview.coverage_before.confirmed, after: preview.coverage_after.confirmed }), 'notice warning'));
    for (const change of preview.changes) {
      const card = node('article', undefined, 'preview-card');
      card.append(node('h4', change.id), node('p', change.rationale));
      const columns = node('div', undefined, 'two-columns');
      const before = node('div'), after = node('div');
      before.append(node('strong', t('before')), node('pre', compact(change.before)));
      after.append(node('strong', t(change.operation === 'remove' ? 'remove_declaration' : 'after')), node('pre', compact(change.after)));
      columns.append(before, after); card.append(columns); $('maintenance-preview').append(card);
    }
    for (const item of preview.states) {
      $('maintenance-preview').append(node('p', item.id + ': ' + (item.before?.status ? t(item.before.status) : '—') + ' → ' + (item.after?.status ? t(item.after.status) : t('removed')), 'muted'));
    }
    for (const item of preview.preview.diagnostics) $('maintenance-preview').append(node('p', item.message, 'issue'));
  }
  async function scanRepairs() {
    broken = (await api('repair-scan')).broken;
    $('repair-binding').replaceChildren(...broken.map((item) => new Option(item.binding, item.binding)));
    $('repair-work').hidden = !broken.length;
    if (!broken.length) { $('repair-preview').replaceChildren(node('p', t('no_repairs'), 'muted')); return; }
    selectRepair(); await findRepairs(0);
  }
  function selectRepair() {
    const item = broken.find((row) => row.binding === $('repair-binding').value); if (!item) return;
    repairChoice = null; $('repair-page').hidden = true;
    $('repair-old').textContent = item.previous_location?.text || compact(item.old_definition.anchor);
    const claim = item.binding.startsWith('claims:'); $('repair-numeric').hidden = claim; $('repair-claim').hidden = !claim;
    $('repair-file').value = item.old_definition.file; $('repair-wording').value = item.old_definition.anchor.exact || '';
  }
  async function showRepairPage(candidate) {
    if (candidate.format !== 'pdf') return;
    const page = (await api('page', { file: candidate.file, page: candidate.locator.page })).preview.pages[0];
    const box = $('repair-page'); box.replaceChildren(); box.hidden = false;
    if (!page.image) { box.append(node('p', page.message || t('page_unavailable'))); return; }
    box.append(node('p', candidate.label));
    const wrapper = node('div', undefined, 'paper-page'), image = node('img');
    image.src = page.image; image.alt = candidate.label; wrapper.append(image);
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'), [x0, y0, x1, y1] = page.page_box.map(Number);
    svg.setAttribute('viewBox', [x0, y0, x1 - x0, y1 - y0].join(' '));
    for (const bounds of candidate.locator.boxes || [candidate.locator.bbox].filter(Boolean)) {
      const [a, b, c, d] = bounds.map(Number), rect = document.createElementNS(svg.namespaceURI, 'rect');
      for (const [key, value] of Object.entries({ x: a, y: b, width: c - a, height: d - b })) rect.setAttribute(key, value);
      svg.append(rect);
    }
    wrapper.append(svg); box.append(wrapper);
  }
  async function findRepairs(offset = 0) {
    if ($('repair-binding').value.startsWith('claims:')) return;
    const page = await api('candidates', { query: $('repair-query').value, offset, limit: 30 });
    $('repair-candidates').replaceChildren();
    for (const candidate of page.items) {
      const label = node('label', undefined, 'check repair-candidate'), radio = node('input'); radio.type = 'radio'; radio.name = 'repair-position'; radio.value = candidate.candidate_id;
      radio.checked = repairChoice?.candidate_id === candidate.candidate_id;
      radio.onchange = () => { repairChoice = candidate; if (candidate.format === 'pdf') task(() => showRepairPage(candidate)); };
      label.append(radio, node('span', candidate.label + '\n' + candidate.context_before + candidate.text + candidate.context_after));
      $('repair-candidates').append(label);
    }
    pageButtons($('repair-pages'), page.offset, page.total, page.limit, (next) => task(() => findRepairs(next)));
  }
  function paintRepair(state) {
    const preview = state.repair;
    if (preview?.repair_id !== repairId) { repairId = preview?.repair_id; $('repair-attest').checked = false; }
    $('repair-confirm').hidden = !preview;
    $('accept-repair').disabled = !preview || state.stale || !$('repair-attest').checked;
    if (!preview) return;
    $('repair-preview').replaceChildren();
    for (const change of preview.changes) {
      const card = node('article', undefined, 'preview-card');
      card.append(node('h3', change.binding), node('p', change.previous_location?.text || compact(change.before.anchor)),
        node('p', '→ ' + change.current_context, 'context-text'), node('p', change.rationale));
      $('repair-preview').append(card);
    }
  }
  function paintRecovery(state) {
    const saved = state.recovery, active = state.additions && Object.values(state.additions).some((items) => Object.keys(items).length);
    $('recovery-banner').hidden = !saved?.available || (active && !state.stale);
    recoveryId = saved?.record_id;
    if (!saved?.available) return;
    $('recovery-description').textContent = saved.message || [saved.saved_at, t('recovery_hint'), ...(saved.changed_paths || [])].join('\n');
    $('restore-local').disabled = !!saved.error || !!saved.changed_paths?.length;
    $('discard-recovery').disabled = !saved.record_id;
    $('open-rebuild').disabled = !!saved.error;
    const preview = state.rebuild;
    if (preview?.proposal_id !== rebuildId) { rebuildId = preview?.proposal_id; $('rebuild-attest').checked = false; }
    $('rebuild-confirm').hidden = !preview;
    $('accept-rebuild').disabled = !preview || !$('rebuild-attest').checked;
    $('rebuild-preview').replaceChildren();
    if (preview) {
      $('rebuild-preview').append(node('h3', t('preview_rebuild')), node('p', preview.selected.join(', ')));
      for (const [name, metric] of Object.entries(preview.preview.metrics)) $('rebuild-preview').append(node('p', name + ': ' + compact(metric.value) + ' · ' + (metric.unit ? t(metric.unit) : metric.status)));
      for (const [name, item] of Object.entries(preview.additions.occurrences)) $('rebuild-preview').append(node('p', name + ' → ' + item.metric + ' · ' + item.file));
      for (const item of preview.preview.diagnostics) $('rebuild-preview').append(node('p', item.message, 'issue'));
    }
  }
  function render(state) {
    paintMode(); paintRecovery(state); paintMaintenance(state); paintRepair(state); paintReport();
  }
  async function poll() {
    if (polling || ctx.busy() || !ctx.state()?.initialized || document.visibilityState === 'hidden') return;
    polling = true;
    try {
      const result = await api('poll'); if (ctx.busy()) return;
      if (result.revision !== ctx.state().revision || (result.stale && !ctx.state().stale)) update((await api('state')).state);
      if (!detail || result.review.generation !== detail.summary.generation || result.review.state !== detail.summary.state) await load();
    } catch (_) { $('watch-state').textContent = t('watch_disconnected'); }
    finally { polling = false; }
  }
  for (const element of document.querySelectorAll('[data-mode]')) element.onclick = () => setMode(element.dataset.mode);
  $('impact-search').oninput = () => { impactOffset = 0; paintReport(); };
  $('snapshot-form').onsubmit = (event) => { event.preventDefault(); task(async () => { detail = await api('snapshot-create', { name: event.target.elements.name.value }); paintReport(); }); };
  $('baseline-select').onchange = () => task(async () => { detail = await api('baseline', { name: $('baseline-select').value || null }); paintReport(); });
  $('load-declarations').onclick = () => task(loadDeclarations);
  $('declaration-search').oninput = paintDeclarations;
  $('remove-declaration').onchange = () => {
    for (const item of controls) item.control.disabled = $('remove-declaration').checked;
    $('remove-dependents').hidden = !$('remove-declaration').checked || !editing.dependents.length;
    validateRemoval();
  };
  $('declaration-form').onsubmit = (event) => {
    event.preventDefault(); task(async () => {
      const common = { group: editing.group, name: editing.name, rationale: $('declaration-reason').value };
      if ($('remove-declaration').checked) {
        const identities = [editing.id, ...[...$('dependent-choices').querySelectorAll('input:checked')].map((item) => item.value)];
        const edits = identities.map((identity) => {
          const [group, name] = identity.split(':'); return { group, name, rationale: common.rationale, operation: 'remove' };
        });
        update((await api('maintenance-preview', { edits })).state);
      }
      else {
        const fields = controls.map(({ field, control }) => ({ path: field.path, value_json: field.kind === 'boolean' ? JSON.stringify(control.checked) : field.kind === 'string' ? JSON.stringify(control.value) : control.value }));
        update((await api('maintenance-fields', { ...common, fields })).state);
      }
    });
  };
  $('maintenance-attest').onchange = () => paintMaintenance(ctx.state());
  $('accept-maintenance').onclick = () => task(async () => {
    update((await api('maintenance-accept', { proposal_id: maintenanceId })).state);
    $('declaration-form').hidden = true; await loadDeclarations(); await load();
  });
  $('scan-repairs').onclick = () => task(scanRepairs);
  $('repair-binding').onchange = () => task(async () => { selectRepair(); await findRepairs(); });
  $('repair-search-form').onsubmit = (event) => { event.preventDefault(); task(() => findRepairs()); };
  $('repair-form').onsubmit = (event) => {
    event.preventDefault(); task(async () => {
      const binding = $('repair-binding').value, selection = { binding, rationale: $('repair-reason').value };
      if (binding.startsWith('claims:')) { selection.file = $('repair-file').value; selection.anchor = { exact: $('repair-wording').value }; }
      else { if (!repairChoice) throw new Error(t('choose_locations')); selection.candidate_id = repairChoice.candidate_id; }
      update((await api('repair-preview', { selections: [selection] })).state);
    });
  };
  $('repair-attest').onchange = () => paintRepair(ctx.state());
  $('accept-repair').onclick = () => task(async () => {
    update((await api('repair-accept', { repair_id: repairId, selected: ctx.state().repair.changes.map((item) => item.binding) })).state);
    $('repair-preview').replaceChildren(); await scanRepairs(); await load();
  });
  $('claim-review-form').onsubmit = (event) => {
    event.preventDefault(); task(async () => {
      detail = await api('claim-review', { claim: selectedClaim.name, state: selectedClaim.state, reviewer: $('claim-reviewer').value, note: $('claim-note').value, attest: $('claim-attest').checked });
      $('claim-review-form').hidden = true; paintReport();
    });
  };
  $('restore-local').onclick = () => task(async () => { update((await api('recovery-restore')).state); setMode('binding'); });
  $('open-rebuild').onclick = () => task(async () => {
    const result = await api('recovery-items'); rebuildRecord = result.record_id;
    $('rebuild-work').hidden = false; $('rebuild-items').replaceChildren();
    for (const item of result.items) {
      const label = node('label', undefined, 'check'), checkbox = node('input'); checkbox.type = 'checkbox'; checkbox.value = item.id;
      label.append(checkbox, node('span', item.id)); $('rebuild-items').append(label);
      const details = node('details'); details.append(node('summary', t('before')), node('pre', item.definition_json)); $('rebuild-items').append(details);
    }
  });
  $('preview-rebuild').onclick = () => task(async () => {
    const selected = [...$('rebuild-items').querySelectorAll('input:checked')].map((item) => item.value);
    update((await api('recovery-preview', { record_id: rebuildRecord, selected })).state);
  });
  $('rebuild-attest').onchange = () => paintRecovery(ctx.state());
  $('accept-rebuild').onclick = () => task(async () => {
    update((await api('recovery-rebuild', { proposal_id: rebuildId })).state); $('rebuild-work').hidden = true; setMode('binding');
  });
  $('export-recovery').onclick = () => task(async () => { download((await api('recovery-export')).json, 'paperdelta-recovery.json', 'application/json'); });
  $('discard-recovery').onclick = () => task(async () => {
    if (confirm(t('discard_recovery_confirm'))) update((await api('recovery-discard', { record_id: recoveryId })).state);
  });
  const timer = setInterval(poll, 2000);
  window.addEventListener('pagehide', () => clearInterval(timer), { once: true });
  return { render, load, poll, setMode, localize };
};
