/* Reviewed native comment copies use a server-held plan and fresh input checks. */
window.createPaperDeltaAnnotations = function (ctx) {
  'use strict';
  const {t, node, api, task, download, notice, pending, staged} = ctx;
  const $ = id => document.getElementById(id), selected = new Set();
  let plan;
  function invalidate() {
    plan = null; $('annotation-preview').hidden = true;
    $('annotation-attest').checked = false; $('annotation-download').disabled = true;
  }
  function controls() {
    $('annotation-selected').textContent = t('annotation_selected', {count: selected.size});
    $('annotation-preview-button').disabled = !selected.size || pending() || staged();
    $('annotation-clear').disabled = !selected.size;
    for (const check of document.querySelectorAll('input[data-native-annotation]')) {
      check.checked = selected.has(check.value);
      check.disabled = pending() || staged() || (!check.checked && selected.size >= 500);
    }
  }
  function choice(item) {
    const label = node('label', undefined, 'check'), check = node('input');
    check.type = 'checkbox'; check.value = item.occurrence; check.dataset.nativeAnnotation = 'true';
    check.checked = selected.has(item.occurrence);
    check.disabled = pending() || staged() || (!check.checked && selected.size >= 500);
    check.onchange = () => {
      if (check.checked) selected.add(item.occurrence); else selected.delete(item.occurrence);
      invalidate(); controls();
    };
    label.append(check, node('span', t('annotation_select'))); return label;
  }
  $('annotation-clear').onclick = () => {selected.clear(); invalidate(); controls();};
  $('annotation-preview-button').onclick = () => task(async () => {
    invalidate(); plan = (await api('annotation-preview', {occurrences: [...selected]})).plan;
    const list = $('annotation-entries'); list.replaceChildren();
    $('annotation-notice').textContent = plan.notice;
    $('annotation-files').textContent = plan.copies.map(item => item.original + ' → ' + item.path).join('\n');
    for (const entry of plan.entries) {
      const card = node('article', undefined, 'revision-metric');
      card.append(node('h4', entry.occurrence), node('p', entry.position),
        node('pre', entry.location.context, 'revision-context'), node('pre', entry.note));
      list.append(card);
    }
    for (const refused of plan.refused) list.append(node('p', refused.occurrence + ': ' + refused.reason, 'issue'));
    if (!plan.entries.length) list.append(node('p', t('annotation_empty'), 'issue'));
    $('annotation-preview').hidden = false;
    $('annotation-preview').scrollIntoView({block: 'start'});
  });
  $('annotation-attest').onchange = () => {
    $('annotation-download').disabled = !plan?.copies.length || !$('annotation-attest').checked || pending() || staged();
  };
  $('annotation-download').onclick = () => task(async () => {
    if (!plan?.copies.length || !$('annotation-attest').checked) return;
    try {
      const result = await api('annotation-export', {preview_id: plan.preview_id, attest: true});
      download(Uint8Array.from(atob(result.base64), c => c.charCodeAt(0)), 'paperdelta-annotations.zip', 'application/zip');
      invalidate(); notice(t('annotation_downloaded'));
    } catch (error) {invalidate(); throw error;}
  });
  return {choice, invalidate, controls, paint: detail => {
    const available = new Set(detail.revision_tasks.filter(item => item.annotatable).map(item => item.occurrence));
    for (const name of selected) if (!available.has(name)) selected.delete(name);
    $('annotation-panel').hidden = !available.size;
    controls();
  }};
};
