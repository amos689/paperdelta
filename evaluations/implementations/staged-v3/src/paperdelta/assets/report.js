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
    for (const attribute of ['aria-label', 'placeholder', 'label']) {
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
  filter();
})();
