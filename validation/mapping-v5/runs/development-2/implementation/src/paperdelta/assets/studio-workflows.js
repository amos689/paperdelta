/* Reviewed declarations and generated fragments. No project code execution. */
window.createPaperDeltaWorkflows = function (ctx) {
  'use strict';
  const { t, node, api, task, update, notice } = ctx;
  const $ = id => document.getElementById(id);
  const field = (form, name) => $(form).elements.namedItem(name);
  const lines = text => text.split(/\r?\n/).map(s => s.trim()).filter(Boolean);
  let options, proposal, proposalAction, savedNotebook;
  function invalidate() {
    proposal = null; $('workflow-preview').hidden = true;
    $('workflow-attest').checked = false; $('workflow-accept').disabled = true;
  }
  function paint() {
    if (!options) return;
    const selected = new Set([...$('fragment-bindings').querySelectorAll('input:checked')].map(el => el.value));
    $('fragment-bindings').replaceChildren();
    for (const item of options.bindings) {
      const label = node('label', undefined, 'check'), input = node('input');
      input.type = 'checkbox'; input.value = item.name; input.checked = selected.has(item.name);
      input.onchange = invalidate;
      label.append(input, node('span', item.name + ' · ' + item.metric + ' · ' + item.file));
      $('fragment-bindings').append(label);
    }
    $('workflow-states').replaceChildren();
    for (const [group, values] of Object.entries({ provenance: options.provenance, fragments: options.fragments })) {
      for (const [name, state] of Object.entries(values)) {
        const card = node('article', undefined, 'impact-card');
        card.dataset.subject = group + ':' + name;
        card.append(node('h3', name), node('span', t(state.status === 'pass' ? 'workflow_unchanged' : state.status), 'status status-' + state.status));
        card.append(node('p', state.source || state.path || state.record));
        if (state.method) card.append(node('p', t('producer_' + state.method)));
        if (state.notice) card.append(node('p', state.notice, 'muted'));
        if (state.changed_paths?.length) card.append(node('p', t('workflow_changed') + ': ' + state.changed_paths.join(', ')));
        if (state.outputs?.length) card.append(node('p', t('producer_outputs') + ': ' + state.outputs.join(', ')));
        for (const cell of state.cells || []) card.append(node('p', cell.id + ' · ' + t('producer_code') + ': ' + t(cell.code_changed ? 'change_changed' : 'change_unchanged') + ' · ' + t('producer_saved_outputs') + ': ' + t(cell.outputs_changed ? 'change_changed' : 'change_unchanged')));
        $('workflow-states').append(card);
      }
    }
    $('workflow-revisions').replaceChildren();
    for (const item of options.revisions) {
      const card = node('article', undefined, 'impact-card'); card.dataset.subject = item.subject;
      card.append(node('h3', item.subject), node('span', t(item.status), 'status status-' + item.status));
      card.append(node('p', item.position || item.files.join(', ')), node('p', item.instruction));
      if (item.expected != null) card.append(node('p', String(item.actual) + ' → ' + item.expected));
      $('workflow-revisions').append(card);
    }
    if (!options.revisions.length) $('workflow-revisions').append(node('p', t('workflow_empty'), 'muted'));
  }
  async function load() { options = await api('workflow-options'); paint(); }
  function showPreview(result, action) {
    invalidate(); proposal = result.proposal; proposalAction = action;
    const box = $('workflow-preview-body'); box.replaceChildren();
    box.append(node('h4', proposal.name), node('p', proposal.record.spec.source || proposal.record.spec.path));
    if (action === 'fragment') {
      box.append(node('pre', proposal.content));
      for (const item of proposal.record.values) box.append(node('p', item.occurrence + ' · ' + item.metric + ' → ' + item.rendered));
    } else {
      box.append(node('p', t('producer_declared')));
      box.append(node('p', proposal.record.rationale));
      box.append(node('p', t('producer_inputs') + ': ' + proposal.record.spec.inputs.join(', ')));
      box.append(node('p', t('producer_outputs') + ': ' + proposal.record.spec.outputs.join(', ')));
      for (const cell of proposal.record.cells) box.append(node('p', cell.id + ' · ' + t('producer_status_' + cell.status)));
    }
    const details = node('details'); details.append(node('summary', t('workflow_identities')), node('pre', JSON.stringify(proposal.record, null, 2))); box.append(details);
    $('workflow-preview').hidden = false;
  }
  $('workflow-load').onclick = () => task(load);
  function paintCells() {
    if (!savedNotebook) return;
    const selected = new Set([...$('producer-cells').querySelectorAll('input:checked')].map(el => el.value));
    $('producer-cells').replaceChildren(node('p', t('producer_declared'), 'muted'));
    for (const cell of savedNotebook.cells.filter(cell => cell.cell_type === 'code')) {
      const card = node('div', undefined, 'source-card'), label = node('label', undefined, 'check'), input = node('input');
      input.type = 'checkbox'; input.value = cell.id; input.checked = selected.has(cell.id); input.onchange = invalidate;
      label.append(input, node('span', cell.id + ' · ' + t('producer_status_' + cell.status)));
      const detail = node('details'); detail.append(node('summary', t('producer_code')), node('pre', cell.source));
      card.append(label, detail); $('producer-cells').append(card);
    }
  }
  $('producer-inspect').onclick = () => task(async () => {
    invalidate();
    savedNotebook = await api('producer-notebook', { path: field('producer-form', 'source').value });
    paintCells();
  });
  for (const form of ['producer-form', 'fragment-form']) $(form).addEventListener('input', invalidate);
  field('producer-form', 'source').addEventListener('input', () => { savedNotebook = null; $('producer-cells').replaceChildren(); });
  field('producer-form', 'kind').onchange = () => { invalidate(); $('producer-inspect').hidden = field('producer-form', 'kind').value !== 'notebook'; $('producer-cells').hidden = $('producer-inspect').hidden; };
  $('producer-form').onsubmit = event => {
    event.preventDefault(); task(async () => {
      const val = name => field('producer-form', name).value;
      const spec = {kind: val('kind'), source: val('source'), inputs: lines(val('inputs')), outputs: lines(val('outputs')),
        cells: val('kind') === 'notebook' ? [...$('producer-cells').querySelectorAll('input:checked')].map(el => el.value) : []};
      showPreview(await api('producer-preview', {name: val('name'), spec, rationale: val('rationale'), replace: field('producer-form','replace').checked}), 'producer');
    });
  };
  $('fragment-form').onsubmit = event => {
    event.preventDefault(); task(async () => {
      const val = name => field('fragment-form', name).value;
      const spec = {format: val('format'), path: val('path'), layout: val('layout'), language: ctx.language(),
        occurrences: [...$('fragment-bindings').querySelectorAll('input:checked')].map(el => el.value)};
      showPreview(await api('fragment-preview', {name: val('name'), spec, replace: field('fragment-form','replace').checked}), 'fragment');
    });
  };
  $('workflow-attest').onchange = () => { $('workflow-accept').disabled = !proposal || !$('workflow-attest').checked; };
  $('workflow-accept').onclick = () => task(async () => {
    if (!proposal || !$('workflow-attest').checked) return;
    const result = await api(proposalAction + '-accept', {proposal_id: proposal.proposal_id, attest: true});
    update(result.state); invalidate(); await load(); notice(t('workflow_accepted'));
  });
  return {load, localize: async () => { invalidate(); paintCells(); if (options) await load(); }};
};
