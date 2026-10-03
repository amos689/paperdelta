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
    page.on('pageerror', error => errors.push(error.message));
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
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(output, 'report-preview.png') });
    await page.locator('#findings details summary').first().click();
    if (await page.locator('#findings details').first().locator('table').count() < 1) throw new Error('Missing evidence table');
    await page.screenshot({ path: path.join(output, 'desktop.png'), fullPage: true });
    await page.setViewportSize({ width: 375, height: 812 });
    const size = await page.evaluate(() => ({ scroll: document.documentElement.scrollWidth, viewport: innerWidth }));
    if (size.scroll > size.viewport) throw new Error(`Horizontal overflow: ${JSON.stringify(size)}`);
    await page.screenshot({ path: path.join(output, 'mobile.png'), fullPage: true });
    if (errors.length) throw new Error(errors.join('\n'));
    const result = { checked_at: new Date().toISOString(), browser: await browser.version(), viewport_desktop: [1365, 1000], viewport_mobile: [375, 812], findings: expectedFindings, figure_included: withFigure, filters: ['file', 'rule', 'source', 'result-dependencies', 'text'], source_details_expansion: true, mobile_horizontal_overflow: false, javascript_errors: errors, scope: 'Headless Chrome on this Windows host; not a multi-platform CI run.' };
    await fs.writeFile(path.join(output, 'evidence.json'), JSON.stringify(result, null, 2) + '\n');
    process.stdout.write(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error => { process.stderr.write(String(error)); process.exitCode = 1; });
