/* Batch choices remain explicit. Templates carry raw selector text, never positions. */
window.createPaperDeltaBatch = function (ctx) {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const field = (name) => $('batch-form').elements.namedItem(name);
  const { t, node, api, task, update, download, pageButtons, metricDetails, notice } = ctx;
  let catalog, locations, active, joint, sourceSignature, templates = [], sourceDefinitions = {}, formDirty = false;
  let choiceOffset = 0, locationOffset = 0, searchTimer, locationTimer;
  const selections = new Map();
  let definitionRef = null, definitionPreview = null;
  const val = (name) => field(name).value;
  const stats = window.PaperDeltaStatistics;
  stats.mountContract($('batch-form')); stats.mountDisplay($('batch-form'));
  function options(select, values, translate = false) {
    const previous = select.value; select.replaceChildren();
    for (const value of values) select.add(new Option(translate ? t(value) : value, value));
    if (values.includes(previous)) select.value = previous;
  }
  function checked(container) { return [...$(container).querySelectorAll('input:checked')].map((item) => item.dataset.column); }
  function filters() {
    return Object.fromEntries([...$('batch-filters').querySelectorAll('.selector-row')]
      .filter((row) => row.querySelector('[type=checkbox]').checked)
      .map((row) => [row.dataset.column, row.querySelector('[type=text]').value]));
  }
  function aliases() {
    return [...$('experiment-alias-rows').children].map(row => Object.fromEntries([...row.querySelectorAll('input')].map(input => [input.dataset.aliasField, input.value])));
  }
  function paintAliases(values) {
    $('experiment-alias-rows').replaceChildren();
    for (const value of values) {
      const row = node('div', undefined, 'alias-row');
      for (const key of ['column', 'value', 'label', 'rationale']) {
        const label = node('label'), input = node('input'); input.type = 'text'; input.required = true;
        input.maxLength = { column: 200, value: 1000, label: 500, rationale: 4000 }[key];
        input.dataset.aliasField = key; input.value = value[key] || '';
        label.append(node('span', t('experiment_alias_' + key)), input); row.append(label);
      }
      const remove = node('button', t('experiment_alias_remove'), 'secondary small'); remove.type = 'button';
      remove.onclick = () => { row.remove(); dirty(); }; row.append(remove); $('experiment-alias-rows').append(row);
    }
  }
  function paintReference() {
    $('experiment-reference').hidden = !definitionRef;
    $('experiment-reference').textContent = definitionRef ? t('experiment_reference', { id: definitionRef }) : '';
  }
  function dirty() {
    formDirty = true; definitionRef = definitionPreview = null;
    $('experiment-definition-preview').hidden = true; $('experiment-definition-attest').checked = false;
    paintReference(); paintCounts(); paintJoint();
  }
  function choiceName(choice) {
    const definition = choice.definition;
    return definition.field + ' · ' + Object.entries(definition.where).map(([key, value]) => `${key}=${value}`).join(' · ');
  }
  function sourceControls(preserve = false) {
    const oldFields = preserve ? checked('batch-fields') : [], oldGroups = preserve ? checked('batch-groups') : [];
    const oldFilters = preserve ? filters() : {};
    const source = sourceDefinitions[val('source')];
    for (const id of ['batch-fields', 'batch-groups', 'batch-filters']) $(id).replaceChildren();
    for (const [column, kind] of Object.entries(source?.columns || {})) {
      for (const [id, chosen] of [['batch-fields', oldFields], ['batch-groups', oldGroups]]) {
        if (id === 'batch-fields' && kind === 'string') continue;
        const label = node('label', undefined, 'check'), input = node('input');
        input.type = 'checkbox'; input.dataset.column = column; input.checked = chosen.includes(column);
        label.append(input, node('span', column + ' · ' + t(kind))); $(id).append(label);
      }
      const row = node('div', undefined, 'selector-row'); row.dataset.column = column;
      const label = node('label', undefined, 'check'), enabled = node('input'), value = node('input');
      enabled.type = 'checkbox'; enabled.checked = Object.hasOwn(oldFilters, column);
      label.append(enabled, node('span', column)); value.type = 'text'; value.value = oldFilters[column] ?? '';
      value.setAttribute('aria-label', t('selector_value', { column }));
      row.append(label, value); $('batch-filters').append(row);
    }
  }
  function request() {
    const seeds = val('expected_seeds').split('\n').filter((value) => value !== '');
    return {
      source: val('source'), fields: checked('batch-fields'), group_by: checked('batch-groups'), where: filters(),
      unit: val('unit'), reduce: val('reduce'), expected_count: Number(val('expected_count')),
      seed_column: val('seed_column'), expected_seeds: seeds.length ? seeds : null,
      statistics: stats.contract($('batch-form')),
      display: { kind: val('display_kind'), places: Number(val('places')), percent_symbol: field('percent_symbol').checked, statistics: stats.display($('batch-form')) },
      aliases: aliases(), experiment_definition: definitionRef,
    };
  }
  function applyRequest(value) {
    field('source').value = value.source; sourceControls();
    for (const [id, values] of [['batch-fields', value.fields], ['batch-groups', value.group_by]]) {
      for (const item of $(id).querySelectorAll('input')) item.checked = values.includes(item.dataset.column);
    }
    for (const row of $('batch-filters').children) {
      row.querySelector('[type=checkbox]').checked = Object.hasOwn(value.where, row.dataset.column);
      row.querySelector('[type=text]').value = value.where[row.dataset.column] ?? '';
    }
    for (const name of ['unit', 'reduce', 'expected_count', 'seed_column']) field(name).value = value[name];
    field('expected_seeds').value = (value.expected_seeds || []).join('\n');
    field('display_kind').value = value.display.kind; field('places').value = value.display.places;
    field('percent_symbol').checked = value.display.percent_symbol;
    stats.apply($('batch-form'), value.statistics, value.display.statistics);
    paintAliases(value.aliases || []); definitionRef = value.experiment_definition || null; paintReference();
    definitionPreview = null; $('experiment-definition-preview').hidden = true;
    formDirty = true; paintCounts(); notice(t('template_loaded'));
  }
  function paintCounts() {
    const count = [...selections.values()].reduce((sum, ids) => sum + ids.size, 0);
    $('batch-selected').textContent = t('batch_selected', { count, metrics: selections.size });
    $('batch-stage').disabled = !catalog || !count || formDirty || ctx.state()?.stale || !$('batch-rationale').value.trim();
    $('template-save-form').querySelector('button').disabled = !catalog || formDirty || ctx.state()?.stale;
    $('batch-catalog').hidden = !catalog;
  }
  async function loadChoices(offset = 0) {
    if (!catalog) return;
    choiceOffset = offset;
    catalog = await api('batch-choices', { catalog_id: catalog.catalog_id, query: $('batch-search').value, offset });
    paintChoices();
    if ($('batch-joint-toggle').checked) await loadJoint(offset);
  }
  async function loadJoint(offset = 0) {
    if (!catalog) return;
    joint = await api('batch-review', { catalog_id: catalog.catalog_id, query: $('batch-search').value, offset });
    paintJoint();
  }
  function choose(choice, candidate, checked) {
    const ids = selections.get(choice.choice_id) || new Set();
    if (checked) ids.add(candidate.candidate_id); else ids.delete(candidate.candidate_id);
    if (ids.size) selections.set(choice.choice_id, ids); else selections.delete(choice.choice_id);
    paintCounts(); paintChoices(); paintJoint(); paintLocations();
  }
  function paintJoint() {
    const enabled = $('batch-joint-toggle').checked;
    $('batch-joint').hidden = $('batch-joint-pages').hidden = !enabled;
    $('batch-catalog').querySelector('.two-columns').hidden = enabled;
    $('batch-joint').replaceChildren();
    if (!enabled || !joint) return;
    for (const choice of joint.items) {
      const card = node('article', undefined, 'joint-choice'); card.dataset.choice = choice.choice_id;
      card.append(node('h3', choiceName(choice)));
      const columns = node('div', undefined, 'joint-columns'), evidence = node('div'), candidates = node('div');
      evidence.append(node('h4', t('batch_joint_evidence')));
      if (choice.result) evidence.append(metricDetails({ result: choice.result, definition: choice.definition }), node('p', t('batch_evidence_limit'), 'muted'));
      else evidence.append(node('p', choice.message, 'issue'));
      evidence.append(node('p', t('experiment_guard', { count: choice.definition.expected_count ?? '—', seed_column: choice.definition.seed_column || 'seed', seeds: (choice.definition.expected_seeds || []).join(', ') || '—' }), 'muted'));
      candidates.append(node('h4', t('batch_joint_positions')), node('p', t('batch_joint_count', { shown: choice.locations.length, matches: choice.context_match_count, total: choice.location_count }), 'muted'));
      for (const candidate of choice.locations) {
        const location = node('div', undefined, 'candidate'), label = node('label', undefined, 'check candidate-top'), check = node('input');
        check.type = 'checkbox'; check.dataset.jointCandidate = candidate.candidate_id;
        check.checked = selections.get(choice.choice_id)?.has(candidate.candidate_id) || false;
        check.disabled = choice.status !== 'ready' || formDirty || ctx.state()?.stale || [...selections].some(([key, ids]) => key !== choice.choice_id && ids.has(candidate.candidate_id));
        check.onchange = () => choose(choice, candidate, check.checked);
        label.append(check, node('span', candidate.label)); location.append(label);
        if (candidate.column_header) location.append(node('p', t('batch_column', { column: candidate.column_header }), 'muted'));
        const context = node('p', undefined, 'candidate-context');
        context.append(node('span', candidate.context_before), node('mark', candidate.text), node('span', candidate.context_after)); location.append(context);
        location.append(node('p', t('batch_matched', { matched: candidate.suggestion.matched_identity.join(', ') || '—', missing: candidate.suggestion.missing_identity.join(', ') || '—' }), 'muted'));
        if (candidate.suggestion.aliases) for (const alias of candidate.suggestion.aliases) location.append(node('p', t('experiment_alias_match', { column: alias.column, value: alias.value, label: alias.label }), 'muted'));
        if (candidate.format === 'pdf') {
          const page = node('button', t('original_page'), 'secondary small'); page.type = 'button';
          page.onclick = () => task(async () => { await showPage(candidate); $('batch-native-page').scrollIntoView({ block: 'start' }); }); location.append(page);
        }
        candidates.append(location);
      }
      const all = node('button', t('batch_joint_all'), 'secondary'); all.type = 'button';
      all.onclick = () => task(async () => {
        active = choice; $('batch-location-search').value = ''; $('batch-joint-toggle').checked = false;
        await loadLocations(); paintJoint(); paintChoices(); $('batch-choice-evidence').scrollIntoView({ block: 'start' });
      });
      candidates.append(all); columns.append(evidence, candidates); card.append(columns); $('batch-joint').append(card);
    }
    if (!joint.items.length) $('batch-joint').append(node('p', t('batch_no_results'), 'empty'));
    pageButtons($('batch-joint-pages'), joint.offset, joint.total, joint.limit, (offset) => task(() => loadChoices(offset)));
  }
  function paintChoices() {
    $('batch-choices').replaceChildren();
    if (!catalog) return;
    for (const choice of catalog.items) {
      const card = node('article', undefined, 'batch-choice'); card.dataset.choice = choice.choice_id;
      card.classList.toggle('active', active?.choice_id === choice.choice_id);
      const button = node('button', choiceName(choice), 'secondary'); button.type = 'button';
      button.onclick = () => task(async () => {
        active = choice; $('batch-location-search').value = ''; $('batch-native-page').hidden = true;
        await loadLocations(0); paintChoices();
      });
      card.append(button, node('p', choice.status === 'ready' ? `${choice.result.value} · ${t(choice.definition.unit)}` : choice.message, 'muted'));
      const count = selections.get(choice.choice_id)?.size || 0;
      if (count) card.append(node('span', t('batch_position_count', { count }), 'badge'));
      $('batch-choices').append(card);
    }
    if (!catalog.items.length) $('batch-choices').append(node('p', t('batch_no_results'), 'empty'));
    pageButtons($('batch-choice-pages'), catalog.offset, catalog.total, catalog.limit, (offset) => task(() => loadChoices(offset)));
    paintCounts();
  }
  async function showPage(candidate) {
    const page = (await api('page', { file: candidate.file, page: candidate.locator.page })).preview.pages[0];
    const box = $('batch-native-page'); box.replaceChildren(); box.hidden = false;
    if (!page?.image) { box.append(node('p', page?.message || t('page_unavailable'))); return; }
    const wrapper = node('div', undefined, 'paper-page'), image = node('img');
    image.src = page.image; image.alt = candidate.label; wrapper.append(image);
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    const [x0, y0, x1, y1] = page.page_box.map(Number);
    svg.setAttribute('viewBox', [x0, y0, x1 - x0, y1 - y0].join(' '));
    const rect = document.createElementNS(svg.namespaceURI, 'rect'), [x, y, right, bottom] = candidate.locator.bbox.map(Number);
    for (const [key, value] of Object.entries({ x, y, width: right - x, height: bottom - y })) rect.setAttribute(key, value);
    svg.append(rect); wrapper.append(svg); box.append(node('p', candidate.label), wrapper);
  }
  async function loadLocations(offset = 0) {
    if (!catalog || !active) return;
    locationOffset = offset;
    locations = await api('batch-locations', { catalog_id: catalog.catalog_id, choice_id: active.choice_id, query: $('batch-location-search').value, offset });
    paintLocations();
  }
  function paintLocations() {
    $('batch-locations').replaceChildren(); $('batch-choice-evidence').replaceChildren();
    if (!locations || !active) return;
    $('batch-choice-evidence').append(node('h3', choiceName(active)));
    if (active.result) $('batch-choice-evidence').append(metricDetails({ result: active.result, definition: active.definition }), node('p', t('batch_evidence_limit'), 'muted'));
    for (const candidate of locations.items) {
      const card = node('article', undefined, 'candidate'), label = node('label', undefined, 'check candidate-top'), check = node('input');
      check.type = 'checkbox'; check.dataset.batchCandidate = candidate.candidate_id;
      check.checked = selections.get(active.choice_id)?.has(candidate.candidate_id) || false;
      check.disabled = active.status !== 'ready' || [...selections].some(([key, ids]) => key !== active.choice_id && ids.has(candidate.candidate_id));
      check.onchange = () => {
        const ids = selections.get(active.choice_id) || new Set();
        if (check.checked) ids.add(candidate.candidate_id); else ids.delete(candidate.candidate_id);
        if (ids.size) selections.set(active.choice_id, ids); else selections.delete(active.choice_id);
        paintCounts(); paintChoices();
      };
      label.append(check, node('span', candidate.label)); card.append(label);
      if (candidate.column_header) card.append(node('p', t('batch_column', { column: candidate.column_header }), 'muted'));
      const context = node('p', undefined, 'candidate-context');
      context.append(node('span', candidate.context_before), node('mark', candidate.text), node('span', candidate.context_after)); card.append(context);
      if (candidate.suggestion) card.append(node('p', t('batch_matched', { matched: candidate.suggestion.matched_identity.join(', ') || '—', missing: candidate.suggestion.missing_identity.join(', ') || '—' }), 'muted'));
      if (candidate.suggestion?.aliases) for (const alias of candidate.suggestion.aliases) card.append(node('p', t('experiment_alias_match', { column: alias.column, value: alias.value, label: alias.label }), 'muted'));
      if (candidate.format === 'pdf') {
        const button = node('button', t('original_page'), 'secondary small'); button.type = 'button';
        button.onclick = () => task(() => showPage(candidate)); card.append(button);
      }
      $('batch-locations').append(card);
    }
    pageButtons($('batch-location-pages'), locations.offset, locations.total, locations.limit, (offset) => task(() => loadLocations(offset)));
  }
  async function loadTemplates() {
    const response = await api('template-list'); templates = response.templates;
    options($('template-select'), templates.map((item) => item.name));
    $('template-errors').replaceChildren(...response.errors.map((item) => node('p', item.name + ': ' + item.message, 'issue')));
    if (response.limited) $('template-errors').append(node('p', t('template_limit'), 'issue'));
    $('template-load').disabled = $('template-export').disabled = !templates.length;
  }
  function render(next) {
    if (!next.initialized) return;
    if (catalog && (next.batch_id !== catalog.catalog_id || next.stale)) {
      catalog = locations = active = joint = null; selections.clear(); $('batch-native-page').hidden = true;
      $('batch-choices').replaceChildren(); $('batch-locations').replaceChildren(); $('batch-choice-evidence').replaceChildren();
      paintJoint();
    }
    if (next.stale) { paintCounts(); return; }
    sourceDefinitions = next.sources || {};
    const sources = Object.entries(next.sources || {}).filter(([, source]) => source.format !== 'json');
    const signature = JSON.stringify(sources);
    if (signature !== sourceSignature) {
      const before = val('source'); options(field('source'), sources.map(([name]) => name));
      sourceControls(before === val('source')); sourceSignature = signature;
    }
    paintCounts();
  }
  async function localize() {
    for (const [name, values] of [['unit', ['fraction', 'percent', 'scalar', 'percentage_point', 'count', 'ratio']], ['reduce', ['unique', 'mean', 'sum', 'count', 'statistics']], ['display_kind', ['percent', 'decimal', 'integer', 'scientific']]]) options(field(name), values, true);
    sourceControls(true);
    paintAliases(aliases()); paintReference();
    if (catalog) {
      await loadChoices(choiceOffset);
      if (active) { active = catalog.items.find((item) => item.choice_id === active.choice_id) || active; await loadLocations(locationOffset); }
    }
    if ($('batch-templates').open) await loadTemplates();
    if ($('experiment-definitions').open) await loadDefinitions();
    if (!$('experiment-advice-view').hidden) await inspectExperimentAdvice();
    paintCounts();
  }
  field('source').onchange = () => { sourceControls(); dirty(); $('experiment-advice-view').hidden = true; };
  $('batch-form').oninput = dirty;
  $('experiment-alias-add').onclick = () => { paintAliases([...aliases(), {}]); dirty(); };
  async function inspectExperimentAdvice() {
    const source = sourceDefinitions[val('source')]; if (!source) return;
    const advice = await api('source-advice', { path: source.path, sheet: source.sheet, cell_range: source.cell_range });
    const box = $('experiment-advice-view'); box.replaceChildren(); box.hidden = false;
    box.append(node('p', advice.notice || advice.reason));
    if (!advice.available) return;
    const experiment = advice.experiment;
    box.append(node('p', experiment.reason), node('p', t('experiment_advice_summary', { groups: experiment.group_by.join(', ') || '—', fields: experiment.result_fields.join(', ') || '—', repeats: experiment.repeat_columns.join(', ') || '—' })));
    for (const conflict of advice.conflicts) box.append(node('p', conflict, 'issue'));
    const apply = node('button', t('experiment_advice_apply'), 'secondary'); apply.type = 'button'; apply.disabled = !advice.complete;
    apply.onclick = () => {
      for (const [id, chosen] of [['batch-fields', experiment.result_fields], ['batch-groups', experiment.group_by]]) for (const input of $(id).querySelectorAll('input')) input.checked = chosen.includes(input.dataset.column);
      for (const row of $('batch-filters').children) { const value = experiment.constant_identity[row.dataset.column]; row.querySelector('[type=checkbox]').checked = value !== undefined; row.querySelector('[type=text]').value = value ?? ''; }
      if (experiment.repeat_columns.length === 1) field('seed_column').value = experiment.repeat_columns[0];
      dirty(); notice(t('experiment_advice_review'));
    };
    box.append(apply);
  }
  $('experiment-advice').onclick = () => task(inspectExperimentAdvice);
  async function loadDefinitions() {
    const result = await api('experiment-list');
    const previous = $('experiment-definition-select').value; $('experiment-definition-select').replaceChildren();
    for (const value of result.items) $('experiment-definition-select').add(new Option(value.name + ' · ' + value.definition_id.slice(7, 19), value.definition_id));
    if (result.items.some(value => value.definition_id === previous)) $('experiment-definition-select').value = previous;
    $('experiment-definition-load').disabled = !result.items.length;
    $('experiment-definition-errors').replaceChildren(...result.errors.map(item => node('p', item.file + ': ' + item.message, 'issue')));
  }
  $('experiment-definitions').ontoggle = () => { if ($('experiment-definitions').open && ctx.state()?.initialized) task(loadDefinitions); };
  $('experiment-definition-load').onclick = () => task(async () => {
    const loaded = await api('experiment-load', { definition_id: $('experiment-definition-select').value, source: val('source') });
    applyRequest(loaded.request); notice(loaded.notice);
  });
  $('experiment-definition-form').oninput = () => { definitionPreview = null; $('experiment-definition-preview').hidden = true; };
  $('experiment-definition-form').onsubmit = event => {
    event.preventDefault(); task(async () => {
      const form = $('experiment-definition-form');
      definitionPreview = await api('experiment-preview', { name: form.elements.namedItem('name').value, rationale: form.elements.namedItem('rationale').value, request: request() });
      $('experiment-definition-content').textContent = JSON.stringify(definitionPreview.definition, null, 2);
      $('experiment-definition-preview').hidden = false; $('experiment-definition-attest').checked = false; $('experiment-definition-save').disabled = true;
    });
  };
  $('experiment-definition-attest').onchange = () => { $('experiment-definition-save').disabled = !definitionPreview || !$('experiment-definition-attest').checked; };
  $('experiment-definition-save').onclick = () => task(async () => {
    if (!definitionPreview || !$('experiment-definition-attest').checked) return;
    const result = await api('experiment-accept', { preview_id: definitionPreview.preview_id });
    definitionRef = result.definition_id; definitionPreview = null; formDirty = true;
    $('experiment-definition-preview').hidden = true; paintReference(); paintCounts(); await loadDefinitions(); notice(result.notice);
  });
  $('batch-form').onsubmit = (event) => {
    event.preventDefault(); task(async () => {
      if (selections.size && !confirm(t('batch_replace'))) return;
      const result = await api('batch-catalog', request()); update(result.state);
      catalog = result.batch; locations = active = joint = null; selections.clear(); formDirty = false;
      $('batch-search').value = ''; choiceOffset = locationOffset = 0;
      paintChoices(); paintLocations(); notice(t('batch_generated'));
      ctx.setStep('review');
      if ($('batch-joint-toggle').checked) await loadJoint();
    });
  };
  $('batch-stage').onclick = () => task(async () => {
    const selected = [...selections].map(([choice_id, ids]) => ({ choice_id, candidate_ids: [...ids], rationale: $('batch-rationale').value }));
    const result = await api('batch-stage', { catalog_id: catalog.catalog_id, selections: selected });
    update(result.state); ctx.setStep('review'); notice(t('batch_staged'));
  });
  $('batch-rationale').oninput = paintCounts;
  $('batch-joint-toggle').onchange = () => task(async () => { if ($('batch-joint-toggle').checked) await loadJoint(choiceOffset); else paintJoint(); });
  $('batch-search').oninput = () => { clearTimeout(searchTimer); searchTimer = setTimeout(() => task(() => loadChoices(0)), 180); };
  $('batch-location-search').oninput = () => { clearTimeout(locationTimer); locationTimer = setTimeout(() => task(() => loadLocations(0)), 180); };
  $('batch-templates').ontoggle = () => { if ($('batch-templates').open && ctx.state()?.initialized) task(loadTemplates); };
  $('template-save-form').onsubmit = (event) => { event.preventDefault(); task(async () => {
    await api('template-save', { catalog_id: catalog.catalog_id, name: $('template-save-form').elements.namedItem('name').value });
    await loadTemplates(); notice(t('template_saved'));
  }); };
  $('template-load').onclick = () => task(async () => applyRequest((await api('template-load', { name: $('template-select').value, source: val('source') })).request));
  $('template-export').onclick = () => task(async () => download((await api('template-export', { name: $('template-select').value })).json, 'paperdelta-template.json', 'application/json'));
  $('template-import').onclick = () => $('template-file').click();
  $('template-file').onchange = () => task(async () => {
    const file = $('template-file').files[0]; $('template-file').value = ''; if (!file) return;
    if (file.size > 65536) throw new Error(t('template_limit'));
    applyRequest((await api('template-import', { value_json: await file.text(), source: val('source') })).request);
  });
  $('proposal-import').onclick = () => $('proposal-file').click();
  $('proposal-file').onchange = () => task(async () => {
    const file = $('proposal-file').files[0]; $('proposal-file').value = ''; if (!file) return;
    if (file.size > 850000) throw new Error(t('draft_limit'));
    update((await api('proposal-import', { value_json: await file.text() })).state);
    ctx.setStep('review'); notice(t('proposal_loaded'));
  });
  return { render, localize };
};
