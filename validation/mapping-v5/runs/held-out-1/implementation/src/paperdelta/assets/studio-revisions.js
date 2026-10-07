/* Joined revision workbench. Only server-held, freshly verified patches can write. */
window.createPaperDeltaRevisions = function (ctx) {
  'use strict';
  const {t, node, api, task, update, notice, pageButtons, metricDetails} = ctx;
  const $ = id => document.getElementById(id);
  const compact = value => value == null ? '—' : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
  const selected = new Set();
  let detail, identity, active, offset = 0, proposal, recovery, transactions;
  const annotations = window.createPaperDeltaAnnotations({...ctx, pending, staged});
  // Keep everyday tasks before optional export and generation workflows.
  $('review-workspace').append($('workflow-panel'));
  $('workspace').append($('bundle-panel'));
  function button(label, action, className = 'secondary small') {
    const item = node('button', label, className); item.type = 'button'; item.onclick = () => task(action); return item;
  }
  function invalidate() {
    annotations.invalidate();
    proposal = recovery = null;
    $('revision-preview').hidden = $('revision-recovery-preview').hidden = true;
    $('revision-attest').checked = $('revision-recovery-attest').checked = false;
    $('revision-apply').disabled = $('revision-recover').disabled = true;
  }
  function pending() { return detail?.summary.state !== 'current' || !!ctx.state()?.stale; }
  function staged() { return Object.values(ctx.state()?.additions || {}).some(items => Object.keys(items).length); }
  function paintSelection() {
    $('revision-selection').textContent = t('revision_selected', {count: selected.size});
    $('revision-preview-button').disabled = !selected.size || pending() || staged();
    $('revision-clear').disabled = !selected.size;
    for (const check of $('revision-tasks').querySelectorAll('input[data-numeric-patch]')) check.disabled = pending() || staged() || (!check.checked && selected.size >= 500);
    annotations.controls();
    $('revision-pending').hidden = !pending() && !staged();
    $('revision-pending').textContent = t(staged() ? 'finish_draft' : 'watch_pending');
  }
  function filtered() {
    const query = $('revision-search').value.trim().toLowerCase(), status = $('revision-filter').value;
    return (detail?.revision_tasks || []).filter(item => (!status || item.status === status) &&
      [item.subject, item.position, item.context, item.instruction, ...item.metrics, ...item.files].some(value => String(value || '').toLowerCase().includes(query)));
  }
  function paintList() {
    const focused = document.activeElement?.closest('.revision-task')?.dataset.subject;
    const focusCheckbox = document.activeElement?.type === 'checkbox';
    const items = filtered(), box = $('revision-tasks'); box.replaceChildren();
    if (offset >= items.length) offset = 0;
    if (!items.some(item => item.subject === active)) active = items[offset]?.subject;
    for (const item of items.slice(offset, offset + 20)) {
      const card = node('article', undefined, 'revision-task' + (item.subject === active ? ' active' : ''));
      card.dataset.subject = item.subject;
      const focus = node('button', item.subject.split(':').slice(1).join(':'), 'revision-focus');
      focus.type = 'button'; focus.setAttribute('aria-pressed', String(item.subject === active));
      focus.onclick = () => { active = item.subject; paintList(); paintDetail(); };
      card.append(focus, node('span', t(item.status), 'status status-' + item.status));
      card.append(node('p', t('revision_kind_' + item.kind) + ' · ' + (item.position || item.files.join(', ')), 'muted'));
      if (item.actual != null || item.expected != null) card.append(node('p', compact(item.actual) + ' → ' + compact(item.expected), 'revision-values'));
      if (item.patchable) {
        const label = node('label', undefined, 'check'), check = node('input');
        check.type = 'checkbox'; check.value = item.occurrence; check.checked = selected.has(item.occurrence); check.dataset.numericPatch = 'true';
        check.disabled = pending() || staged();
        check.onchange = () => {
          if (check.checked) selected.add(item.occurrence); else selected.delete(item.occurrence);
          invalidate(); paintSelection();
        };
        label.append(check, node('span', t('revision_select_patch'))); card.append(label);
      } else if (item.annotatable) card.append(annotations.choice(item));
      else card.append(node('p', item.patch_blocked_by?.length ? t('revision_claim_blocked') : item.instruction, 'muted'));
      box.append(card);
    }
    if (!items.length) box.append(node('p', t(detail?.revision_tasks.length ? 'revision_no_matches' : 'revision_empty'), 'empty'));
    $('revision-total').textContent = t('revision_count', {count: items.length});
    pageButtons($('revision-pages'), offset, items.length, 20, next => {offset = next; active = items[offset]?.subject; paintList(); paintDetail();});
    if (focused) [...box.children].find(item => item.dataset.subject === focused)?.querySelector(focusCheckbox ? 'input' : 'button')?.focus({preventScroll: true});
    paintSelection();
  }
  function paintDetail() {
    const item = detail?.revision_tasks.find(item => item.subject === active), box = $('revision-detail'); box.replaceChildren();
    if (!item) { delete box.dataset.subject; box.append(node('p', t('revision_choose'), 'empty')); return; }
    box.dataset.subject = item.subject;
    box.append(node('h3', item.subject.split(':').slice(1).join(':')), node('p', item.position || item.files.join(', '), 'muted'));
    if (item.context) box.append(node('h4', t('revision_original')), node('pre', item.context, 'revision-context'));
    if (item.actual != null || item.expected != null) {
      const values = node('div', undefined, 'preview-values');
      values.append(node('span', t('revision_written') + ': ' + compact(item.actual)), node('span', '→'), node('strong', t('revision_evidence_value') + ': ' + compact(item.expected)));
      box.append(values);
    }
    box.append(node('p', item.instruction, 'revision-instruction'));
    if (item.patch_reason) box.append(node('p', item.patch_reason, 'issue'));
    if (item.patch_blocked_by?.length) box.append(node('p', t('revision_blocked_by') + ': ' + item.patch_blocked_by.join(', '), 'issue'));
    if (item.changed_paths.length) box.append(node('p', t('workflow_changed') + ': ' + item.changed_paths.join(', ')));
    if (!item.patchable && /^(occurrence|claim):/.test(item.subject)) {
      const open = button(t(item.patch_blocked_by?.length || item.subject.startsWith('claim:') ? 'record_claim_review' : 'revision_resolve_location'), () => ctx.openTask(item));
      open.disabled = pending(); box.append(open);
    } else if (/^(fragment|provenance|figure|export):/.test(item.subject)) box.append(button(t('workflow_title'), ctx.openWorkflow));
    box.append(node('h4', t('revision_evidence')));
    for (const name of item.metrics) {
      const metric = detail.report.metrics[name], panel = node('section', undefined, 'revision-metric');
      panel.append(node('strong', name), metricDetails(metric?.status === 'ok' ? {result: metric, definition: metric.definition} : {error: true, message: t('unknown')}));
      box.append(panel);
    }
    if (!item.metrics.length) box.append(node('p', t('revision_no_metric'), 'muted'));
  }
  function paint(next) {
    const key = JSON.stringify([next.summary.generation, next.summary.state, ctx.state()?.revision, next.report?.input_hashes]);
    if (identity && identity !== key) invalidate();
    identity = key; detail = next; annotations.paint(next);
    const coverage = next.report.coverage;
    const counts = {unbound: coverage.unbound_numbers.length, unsupported: coverage.unsupported.length, figures: coverage.unregistered_figures.length};
    $('revision-coverage').textContent = t('revision_coverage', counts);
    $('revision-coverage').classList.toggle('warning', Object.values(counts).some(Boolean));
    const available = new Set(next.revision_tasks.filter(item => item.patchable).map(item => item.occurrence));
    for (const name of selected) if (!available.has(name)) selected.delete(name);
    paintList(); paintDetail();
  }
  function paintTransactions() {
    const old = $('revision-transaction').value;
    $('revision-transaction').replaceChildren(new Option(t('choose'), ''));
    for (const record of transactions || []) {
      const label = record.error ? record.id + ' · ' + record.error : record.created_at + ' · ' + t('revision_transaction_' + record.status) + ' · ' + record.files.join(', ');
      const option = new Option(label, record.id); option.disabled = !!record.error || record.status === 'reverted';
      $('revision-transaction').append(option);
    }
    if ([...$('revision-transaction').options].some(option => option.value === old && !option.disabled)) $('revision-transaction').value = old;
    $('revision-history-empty').hidden = !!transactions?.length;
    $('revision-recovery-button').disabled = !$('revision-transaction').value;
  }
  async function loadHistory() { transactions = (await api('patch-transactions')).transactions; paintTransactions(); }
  $('revision-coverage-report').onclick = () => $('download-report').click();
  $('revision-search').oninput = () => {offset = 0; paintList(); paintDetail();};
  $('revision-filter').onchange = () => {offset = 0; paintList(); paintDetail();};
  $('revision-clear').onclick = () => {selected.clear(); invalidate(); paintList();};
  $('revision-preview-button').onclick = () => task(async () => {
    invalidate(); proposal = await api('patch-preview', {occurrences: [...selected]});
    $('revision-diff').textContent = proposal.diff;
    $('revision-preview-files').textContent = [...new Set(proposal.patch.changes.map(item => item.file))].join(', ');
    $('revision-preview').hidden = false;
    $('revision-preview').scrollIntoView({block: 'center'});
  });
  $('revision-attest').onchange = () => {$('revision-apply').disabled = !proposal || !$('revision-attest').checked || pending();};
  $('revision-apply').onclick = () => task(async () => {
    if (!proposal || !$('revision-attest').checked) return;
    try {
      const result = await api('patch-apply', {preview_id: proposal.preview_id, attest: true});
      selected.clear(); invalidate(); update(result.state); await ctx.refresh(); await loadHistory();
      notice(t('revision_applied', {id: result.transaction_id, code: result.verification_exit_code}));
    } catch (error) {
      invalidate(); $('revision-history').open = true;
      try { await loadHistory(); } catch (_) { /* Keep the original write diagnostic. */ }
      throw error;
    }
  });
  $('revision-history-load').onclick = () => task(loadHistory);
  $('revision-transaction').onchange = () => {invalidate(); $('revision-recovery-button').disabled = !$('revision-transaction').value;};
  $('revision-recovery-button').onclick = () => task(async () => {
    invalidate(); recovery = await api('patch-recover-preview', {transaction_id: $('revision-transaction').value});
    $('revision-recovery-diff').textContent = recovery.diff || t('revision_already_original');
    $('revision-recovery-files').textContent = recovery.files.join(', ');
    $('revision-recovery-preview').hidden = false;
  });
  $('revision-recovery-attest').onchange = () => {$('revision-recover').disabled = !recovery || !$('revision-recovery-attest').checked;};
  $('revision-recover').onclick = () => task(async () => {
    if (!recovery || !$('revision-recovery-attest').checked) return;
    try {
      const result = await api('patch-recover', {preview_id: recovery.preview_id, attest: true});
      invalidate(); update(result.state); await ctx.refresh(); await loadHistory(); notice(t('revision_recovered', {id: result.transaction_id}));
    } catch (error) {invalidate(); throw error;}
  });
  return {paint, localize: () => {invalidate(); if (detail) {paintList(); paintDetail();} if (transactions) paintTransactions();}};
};
