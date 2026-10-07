/* Shared explicit statistical controls; decimal levels remain strings. */
window.PaperDeltaStatistics = (() => {
  'use strict';
  const field = (form, name) => form.elements.namedItem(name);
  const compounds = new Set(['mean_sd', 'mean_se', 'ci', 'mean_ci']);
  function enabled(box, active) {
    box.hidden = !active;
    for (const input of box.querySelectorAll('input,select')) input.disabled = !active;
  }
  function mountContract(form) {
    const box = document.createElement('fieldset'); box.className = 'statistics-contract';
    box.innerHTML = `<legend data-i18n="stats_contract"></legend><p data-i18n="stats_contract_hint"></p>
      <label><span data-i18n="stats_ddof"></span><select name="stats_ddof" required><option value="" data-i18n="choose"></option><option value="1" data-i18n="stats_sample_sd"></option><option value="0" data-i18n="stats_population_sd"></option></select></label>
      <label><span data-i18n="stats_unit"></span><input name="stats_unit" required maxlength="200"></label>
      <label><span data-i18n="stats_ci"></span><select name="stats_ci"><option value="none" data-i18n="stats_no_ci"></option><option value="student_t" data-i18n="stats_student_t"></option></select></label>
      <div class="statistics-ci"><label><span data-i18n="stats_level"></span><input name="stats_level" type="text" inputmode="decimal" pattern="0\\.[0-9]{1,6}" required placeholder="0.95"></label>
      <label class="check"><input name="stats_assumption" type="checkbox" required><span data-i18n="stats_assumption"></span></label></div>`;
    form.insertBefore(box, form.querySelector('button[type=submit]'));
    const refresh = () => {
      const active = field(form, 'reduce').value === 'statistics';
      enabled(box, active); enabled(box.querySelector('.statistics-ci'), active && field(form, 'stats_ci').value === 'student_t');
      if (active) form.querySelector('details')?.setAttribute('open', '');
      if (form.querySelector('.statistics-display')) setDisplayActive(form, active);
    };
    field(form, 'reduce').addEventListener('change', refresh);
    field(form, 'stats_ci').addEventListener('change', refresh);
    form._statisticsRefresh = refresh; refresh();
  }
  function mountDisplay(form) {
    const box = document.createElement('fieldset'); box.className = 'statistics-display';
    box.innerHTML = `<legend data-i18n="stats_display"></legend><p data-i18n="stats_display_hint"></p>
      <label><span data-i18n="stats_component"></span><select name="stats_component" required><option value="" data-i18n="choose"></option>${['mean','sd','se','n','ci_lower','ci_upper','confidence_level','mean_sd','mean_se','ci','mean_ci'].map((key) => `<option value="${key}" data-i18n="stats_component_${key}"></option>`).join('')}</select></label>
      <div class="statistics-compound"><p data-i18n="stats_selection"></p><label class="check"><input name="stats_show_n" type="checkbox"><span data-i18n="stats_show_n"></span></label>
      <label><span data-i18n="stats_spread_places"></span><input name="stats_spread_places" type="number" min="0" max="15"></label></div>`;
    form.insertBefore(box, form.querySelector('button[type=submit]'));
    field(form, 'stats_component').addEventListener('change', () => setDisplayActive(form, form.dataset.statisticalDisplay === 'true'));
    setDisplayActive(form, false);
  }
  function setDisplayActive(form, active) {
    form.dataset.statisticalDisplay = String(active);
    const box = form.querySelector('.statistics-display');
    if (!box) return;
    enabled(box, active);
    enabled(box.querySelector('.statistics-compound'), active && compounds.has(field(form, 'stats_component').value));
  }
  function contract(form) {
    if (field(form, 'reduce').value !== 'statistics') return null;
    const ci = field(form, 'stats_ci').value === 'student_t';
    return {
      ddof: Number(field(form, 'stats_ddof').value), unit_of_analysis: field(form, 'stats_unit').value,
      confidence_interval: ci ? { method: 'student_t', level: field(form, 'stats_level').value, assumption: field(form, 'stats_assumption').checked ? 'independent_normal_observations' : '' } : null,
    };
  }
  function display(form) {
    if (form.dataset.statisticalDisplay !== 'true') return null;
    const component = field(form, 'stats_component').value, compound = compounds.has(component);
    const places = field(form, 'stats_spread_places').value;
    return { component, show_n: compound && field(form, 'stats_show_n').checked, spread_places: compound && places !== '' ? Number(places) : null };
  }
  function apply(form, value, formatting) {
    field(form, 'stats_ddof').value = value?.ddof ?? '';
    field(form, 'stats_unit').value = value?.unit_of_analysis ?? '';
    field(form, 'stats_ci').value = value?.confidence_interval?.method ?? 'none';
    field(form, 'stats_level').value = value?.confidence_interval?.level ?? '';
    field(form, 'stats_assumption').checked = value?.confidence_interval?.assumption === 'independent_normal_observations';
    field(form, 'stats_component').value = formatting?.component ?? '';
    field(form, 'stats_show_n').checked = formatting?.show_n ?? false;
    field(form, 'stats_spread_places').value = formatting?.spread_places ?? '';
    form._statisticsRefresh();
  }
  function summary(value, t, node) {
    const box = node('details', undefined, 'statistics-summary');
    box.append(node('summary', t('stats_summary')));
    const list = node('dl');
    for (const key of ['mean','sd','se','n']) list.append(node('dt', t('stats_component_' + key)), node('dd', String(value[key])));
    for (const [key, raw] of [['stats_ddof', value.ddof], ['stats_unit', value.unit_of_analysis], ['stats_precision', value.precision_digits]]) list.append(node('dt', t(key)), node('dd', String(raw)));
    if (value.confidence_interval) {
      const ci = value.confidence_interval;
      list.append(node('dt', t('stats_student_t') + ' · ' + ci.level), node('dd', `[${ci.lower}, ${ci.upper}]`));
      box.append(node('p', t('stats_assumption')));
    }
    box.append(list, node('p', t('stats_no_significance'))); return box;
  }
  return { mountContract, mountDisplay, setDisplayActive, contract, display, apply, summary, compounds };
})();
