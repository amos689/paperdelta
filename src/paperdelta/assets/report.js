'use strict';
(() => {
  const strings = JSON.parse(document.querySelector('#report-locales').textContent);
  const language = document.querySelector('#language');
  const search = document.querySelector('#search');
  const level = document.querySelector('#level');
  const selectors = ['file', 'source', 'rule', 'impact'].map(id => document.getElementById(id));
  const [file, source, rule, impact] = selectors;
  const cards = [...document.querySelectorAll('#findings article')];
  // Search both languages. Changing the language cannot remove a matching card
  // or reset a user's query, selections, focus, or open evidence panels.
  const index = new Map(cards.map(card => [card, (card.textContent + ' ' +
    [...card.querySelectorAll('[data-i18n]')].flatMap(node =>
      Object.values(strings[node.dataset.i18n])).join(' ')).toLowerCase()]));
  function filter() {
    const query = search.value.toLowerCase();
    let count = 0;
    for (const card of cards) {
      const visible = (level.value === 'all' || card.dataset.level === level.value)
        && (!file.value || card.dataset.file === file.value)
        && (!rule.value || card.dataset.rule === rule.value)
        && (!source.value || JSON.parse(card.dataset.sources).includes(source.value))
        && (!impact.value || JSON.parse(card.dataset.impacts).includes(impact.value))
        && index.get(card).includes(query);
      card.hidden = !visible;
      if (visible) count++;
    }
    document.querySelector('#visible-count').textContent = `(${count}/${cards.length})`;
    document.querySelector('#no-matches').hidden = count !== 0 || cards.length === 0;
  }
  function switchLanguage() {
    const selected = language.value;
    if (!['en', 'zh-CN'].includes(selected)) return;
    document.documentElement.lang = selected;
    for (const node of document.querySelectorAll('[data-i18n]')) {
      node.textContent = strings[node.dataset.i18n][selected];
    }
    for (const attribute of ['aria-label', 'placeholder', 'label', 'alt']) {
      for (const node of document.querySelectorAll(`[data-i18n-${attribute}]`)) {
        node.setAttribute(attribute, strings[node.getAttribute(`data-i18n-${attribute}`)][selected]);
      }
    }
  }
  function clearFilters() {
    search.value = '';
    level.value = 'all';
    for (const select of selectors) select.value = '';
    filter();
  }
  language.disabled = false;
  for (const button of document.querySelectorAll('[data-pdf-zoom]')) {
    button.disabled = false;
    button.addEventListener('click', () => {
      const canvas = button.closest('.pdf-page').querySelector('.pdf-canvas');
      const zoom = button.dataset.pdfZoom === '2' ? 2 : 1;
      canvas.style.width = `${zoom * 100}%`;
      canvas.style.maxWidth = zoom === 1 ? '900px' : 'none';
    });
  }
  for (const link of document.querySelectorAll('.pdf-jump')) {
    link.addEventListener('click', () => {
      const target = document.getElementById(link.hash.slice(1));
      if (target) target.closest('details').open = true;
    });
  }
  language.addEventListener('change', switchLanguage);
  search.addEventListener('input', filter);
  for (const select of [level, ...selectors]) select.addEventListener('change', filter);
  document.querySelector('#clear-filters').addEventListener('click', clearFilters);
  for (const link of document.querySelectorAll('[data-finding-link]')) {
    link.addEventListener('click', () => {
      clearFilters();
      const target = document.getElementById(link.hash.slice(1));
      const evidence = target && target.querySelector('details');
      if (evidence) evidence.open = true;
    });
  }
  // Persist only presentation state within this tab when a live report reloads.
  // Scientific inputs and verdicts always come from the newly generated report.
  if (document.querySelector('meta[name="paperdelta-live"]') || document.querySelector('#watch-status')) {
    const key = 'paperdelta-live:' + location.pathname;
    const fields = [language, search, level, ...selectors];
    const detailKey = node => node.id || (node.closest('article') || {}).id;
    try {
      const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
      if (saved && typeof saved === 'object') {
        for (const field of fields) {
          const value = saved.fields && saved.fields[field.id];
          if (typeof value !== 'string') continue;
          if (field.tagName !== 'SELECT' || [...field.options].some(option => option.value === value)) field.value = value;
        }
        for (const node of document.querySelectorAll('details')) {
          if (Array.isArray(saved.open) && saved.open.includes(detailKey(node))) node.open = true;
        }
        switchLanguage();
        if (typeof saved.focus === 'string') {
          const node = document.getElementById(saved.focus);
          if (node && fields.includes(node)) node.focus({preventScroll: true});
        }
        if (Number.isFinite(saved.scroll)) requestAnimationFrame(() => scrollTo(0, saved.scroll));
      }
    } catch (_) { /* Storage may be unavailable for local files. */ }
    window.addEventListener('pagehide', () => {
      try {
        sessionStorage.setItem(key, JSON.stringify({
          fields: Object.fromEntries(fields.map(field => [field.id, field.value])),
          open: [...document.querySelectorAll('details[open]')].map(detailKey).filter(Boolean),
          focus: document.activeElement && document.activeElement.id,
          scroll: scrollY
        }));
      } catch (_) { /* Reading the report never depends on persistent storage. */ }
    });
  }
  filter();
})();
