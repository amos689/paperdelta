// Optional browser QA: install playwright separately; core users do not need Node.
const { chromium } = require(process.env.PAPERDELTA_PLAYWRIGHT || 'playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async () => {
  if (!process.argv[2]) throw new Error('Pass the comparison-reversed report.html path');
  const output = path.resolve(process.argv[3] || 'build/browser-qa');
  const withFigure = process.argv.includes('--with-figure');
  const expectedFindings = withFigure ? 6 : 5;
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({ executablePath: process.env.PAPERDELTA_BROWSER_EXECUTABLE || undefined, headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1365, height: 1000 } });
    const errors = [];
    const externalRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => {
      if (/^https?:/.test(request.url())) externalRequests.push(request.url());
    });
    await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);
    const count = () => page.locator('#findings article:visible').count();
    if (await count() !== expectedFindings) throw new Error(`Expected ${expectedFindings} findings`);
    await page.selectOption('#file', 'paper/abstract.tex');
    if (await count() !== 1) throw new Error('File filter failed');
    await page.selectOption('#file', '');
    await page.selectOption('#rule', 'CLAIM_FALSE');
    if (await count() !== 1) throw new Error('Rule filter failed');
    await page.selectOption('#rule', '');
    await page.selectOption('#source', 'results/metrics.csv');
    if (await count() !== expectedFindings) throw new Error('Source filter failed');
    await page.selectOption('#impact', 'baseline');
    if (await count() !== (withFigure ? 3 : 2)) throw new Error('Dependency group filter failed');
    await page.selectOption('#impact', 'ours');
    if (await count() !== expectedFindings) throw new Error('Root result filter failed');
    await page.selectOption('#impact', '');
    await page.selectOption('#source', '');
    await page.fill('#search', 'no-such-text');
    if (await count() !== 0) throw new Error('Text filter failed');
    await page.fill('#search', '');
    await page.selectOption('#file', 'paper/abstract.tex');
    await page.selectOption('#source', 'results/metrics.csv');
    await page.fill('#search', '80.9');
    const selectedCard = page.locator('#findings article:visible');
    await selectedCard.locator('details summary').click();
    for (const locale of ['zh-CN', 'en', 'zh-CN']) {
      await page.selectOption('#language', locale);
      if (await page.locator('html').getAttribute('lang') !== locale) throw new Error('Document language failed');
      if (await count() !== 1) throw new Error('Language switch changed filtered findings');
      if (await page.inputValue('#search') !== '80.9' || await page.inputValue('#file') !== 'paper/abstract.tex'
          || await page.inputValue('#source') !== 'results/metrics.csv') throw new Error('Language switch reset filters');
      if (!await selectedCard.locator('details').evaluate(node => node.open)) throw new Error('Language switch collapsed evidence');
      const expected = locale === 'zh-CN' ? '筛选检查发现' : 'Filter findings';
      if (await page.locator('#search').getAttribute('aria-label') !== expected) throw new Error('Accessible label not translated');
    }
    // Both language strings remain searchable, regardless of the current UI.
    await page.fill('#search', 'Compare the source records');
    if (await count() !== 1) throw new Error('English search in Chinese view failed');
    await page.selectOption('#language', 'en');
    await page.fill('#search', '对照来源记录');
    if (await count() !== 1) throw new Error('Chinese search in English view failed');
    await page.click('#clear-filters');
    if (await count() !== expectedFindings) throw new Error('Clear filters failed');
    await page.selectOption('#rule', 'VALUE_MISMATCH');
    await page.locator('[data-finding-link]').first().click();
    if (await count() !== expectedFindings) throw new Error('Evidence navigation did not reveal findings');
    await page.selectOption('#language', 'en');
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(output, 'report-preview.png') });
    await page.locator('#findings details').first().evaluate(node => { node.open = true; });
    if (await page.locator('#findings details').first().locator('table').count() < 1) throw new Error('Missing evidence table');
    await page.screenshot({ path: path.join(output, 'desktop.png'), fullPage: true });
    await page.selectOption('#language', 'zh-CN');
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(output, 'report-preview.zh-CN.png') });
    await page.screenshot({ path: path.join(output, 'desktop.zh-CN.png'), fullPage: true });
    await page.setViewportSize({ width: 375, height: 812 });
    const size = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: innerWidth }));
    if (size.scroll > size.viewport) throw new Error(`Horizontal overflow: ${JSON.stringify(size)}`);
    await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
    await page.selectOption('#language', 'en');
    const englishSize = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: innerWidth }));
    if (englishSize.scroll > englishSize.viewport) throw new Error('English mobile horizontal overflow');
    await page.screenshot({ path: path.join(output, 'mobile.en.png'), fullPage: true });
    const staticPage = await browser.newPage({ javaScriptEnabled: false });
    await staticPage.goto(pathToFileURL(path.resolve(process.argv[2])).href);
    if (!await staticPage.locator('noscript').isVisible() || await staticPage.locator('#findings article').count() !== expectedFindings)
      throw new Error('Static report fallback failed');
    await staticPage.close();
    if (errors.length) throw new Error(errors.join('\n'));
    if (externalRequests.length) throw new Error('Report requested external resources');
    const result = { checked_at: new Date().toISOString(), browser: await browser.version(), viewport_desktop: [1365, 1000], viewport_mobile: [375, 812], findings: expectedFindings, figure_included: withFigure, filters: ['file', 'rule', 'source', 'result-dependencies', 'text'], source_details_expansion: true, languages: ['en', 'zh-CN'], language_switch_preserves_state: true, bilingual_search: true, evidence_navigation: true, no_javascript_readable: true, external_requests: externalRequests, mobile_horizontal_overflow: false, javascript_errors: errors, scope: 'Headless Chrome on this Windows host; not a multi-platform CI run.' };
    await fs.writeFile(path.join(output, 'evidence.json'), JSON.stringify(result, null, 2) + '\n');
    process.stdout.write(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error => { process.stderr.write(String(error)); process.exitCode = 1; });
