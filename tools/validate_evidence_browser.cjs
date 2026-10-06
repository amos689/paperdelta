/* Actual bilingual native evidence setup, source contracts, batch acceptance and offline reports. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn, execFileSync } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || path.join(root, 'build', 'evidence-browser-' + Date.now()));
assert(out.startsWith(path.join(root, 'build') + path.sep) && !fs.existsSync(out));
fs.mkdirSync(out, { recursive: true });
const results = [];
function py(args) { return execFileSync(python, ['-X', 'utf8', ...args], { cwd: root, encoding: 'utf8', windowsHide: true }); }
function hash(file) { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }
async function start(directory, lang) {
  const child = spawn(python, ['-X', 'utf8', '-m', 'paperdelta', '--lang', lang, '-C', directory, 'studio', '--no-open'], { cwd: root, windowsHide: true });
  let output = '';
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { child.kill(); reject(new Error(output)); }, 45000);
    child.stdout.on('data', (data) => { output += data; const match = output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/); if (match) { clearTimeout(timer); resolve(match[0]); } });
    child.stderr.on('data', (data) => { output += data; });
    child.on('exit', (code) => { clearTimeout(timer); reject(new Error(code + ': ' + output)); });
  });
  return { child, url };
}
async function ready(page) {
  await page.waitForFunction(() => !document.body.hasAttribute('aria-busy'));
  if (await page.locator('#error').isVisible()) throw new Error(await page.locator('#error').textContent());
}
async function act(page, selector, method = 'click', value) {
  await page.locator(selector)[method](value); await ready(page);
}
async function runCase(browser, kind, language) {
  const directory = path.join(out, `${kind}-${language}`);
  const annotation = JSON.parse(py(['tools/studio_evidence_fixture.py', '--out', path.relative(root, directory), '--kind', kind]));
  const before = Object.fromEntries(['paper.tex', annotation.source.path].map((file) => [file, hash(path.join(directory, file))]));
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage(), errors = [], remote = [];
  page.setDefaultTimeout(45000);
  const { child, url } = await start(directory, language);
  page.on('pageerror', (error) => errors.push(String(error)));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('request', (request) => { if (!request.url().startsWith(new URL(url).origin) && !request.url().startsWith('blob:') && !request.url().startsWith('data:')) remote.push(request.url()); });
  try {
    await page.goto(url); await page.locator('#workspace').waitFor({ state: 'visible' }); await ready(page);
    await act(page, '#add-source summary');
    await act(page, '#source-path-form [name=path]', 'fill', annotation.source.path);
    await act(page, '#source-path-form button');
    if (kind === 'xlsx') {
      assert(await page.locator('#sheet-form').isVisible());
      assert.equal(await page.locator('#sheet-form [name=sheet]').inputValue(), '');
      assert(!(await page.locator('#source-form').isVisible()));
      await act(page, '#sheet-form [name=sheet]', 'selectOption', annotation.source.sheet);
      await act(page, '#sheet-form [name=cell_range]', 'fill', annotation.source.cell_range);
      await act(page, '#language', 'selectOption', language === 'en' ? 'zh-CN' : 'en');
      assert.equal(await page.locator('#sheet-form [name=cell_range]').inputValue(), annotation.source.cell_range);
      await act(page, '#language', 'selectOption', language);
      await act(page, '#sheet-form button');
    }
    assert((await page.locator('#source-sample').textContent()).includes('001'));
    assert((await page.locator('#source-sample').textContent()).includes('0.80000000000000000000000000001'));
    if (kind !== 'records') {
      await act(page, '#column-types input[data-column=model]', 'check');
      await act(page, '#column-types select[data-column=seed]', 'selectOption', 'integer');
      await act(page, '#column-types select[data-column=accuracy]', 'selectOption', 'decimal');
    } else {
      assert(await page.locator('#column-types input[data-column=model]').isChecked());
      assert(await page.locator('#column-types select[data-column=accuracy]').isDisabled());
      await act(page, '#source-provenance summary');
      assert((await page.locator('#source-provenance').textContent()).includes('results.tsv'));
    }
    await act(page, '#source-form [name=name]', 'fill', 'results');
    await act(page, '#language', 'selectOption', language === 'en' ? 'zh-CN' : 'en');
    assert.equal(await page.locator('#source-form [name=name]').inputValue(), 'results');
    assert.equal(await page.locator('#column-types select[data-column=accuracy]').inputValue(), 'decimal');
    await act(page, '#language', 'selectOption', language);
    if (kind === 'records' && (await page.locator('#source-provenance details').getAttribute('open')) === null) await act(page, '#source-provenance summary');
    await page.locator('#source-form').scrollIntoViewIfNeeded();
    await page.locator('#add-source').screenshot({ path: path.join(out, `${kind}-${language}.png`) });
    await act(page, '#source-form button[type=submit]');
    await act(page, 'nav [data-step=batch]');
    await act(page, '#batch-fields input[data-column=accuracy]', 'check');
    await act(page, '#batch-groups input[data-column=model]', 'check');
    await act(page, '#batch-form [name=unit]', 'selectOption', 'fraction');
    await act(page, '#batch-form [name=reduce]', 'selectOption', 'unique');
    await act(page, '#batch-form [name=expected_count]', 'fill', '1');
    await act(page, '#batch-form [name=display_kind]', 'selectOption', 'percent');
    await act(page, '#batch-form button[type=submit]');
    for (const target of annotation.targets) {
      await act(page, `.batch-choice[data-choice="${target.choice_id}"] button`);
      assert.equal(await page.locator('#batch-locations input:checked').count(), 0);
      await act(page, `#batch-locations input[data-batch-candidate="${target.candidate_id}"]`, 'check');
    }
    await act(page, '#batch-rationale', 'fill', 'Model IDs 001 and 1 have distinct result rows, explicit seeds and accuracy columns.');
    await act(page, '#batch-stage');
    await act(page, '#preview');
    assert.equal(await page.locator('#review-items input:checked').count(), 0);
    const boxes = page.locator('#review-items input[type=checkbox]');
    assert.equal(await boxes.count(), 2);
    for (let i = 0; i < 2; i++) { await boxes.nth(i).check(); await ready(page); }
    await act(page, '#attest', 'check'); await act(page, '#accept');
    assert(await page.locator('#receipt').isVisible());
    const report = JSON.parse(py(['-m', 'paperdelta', '-C', directory, 'check', '--format', 'json', '--report', 'report']));
    assert.equal(report.report_schema_version, 9); assert.equal(report.coverage.pass, 2);
    assert(Object.values(report.metrics).some((metric) => metric.value === '0.80000000000000000000000000001'));
    assert.deepEqual(Object.fromEntries(Object.keys(before).map((file) => [file, hash(path.join(directory, file))])), before);
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    assert.deepEqual(errors, []); assert.deepEqual(remote, []);
    results.push({ kind, language, status: 'passed', schema: 5, accepted: 2, inputs: before, remote_requests: remote, errors });
  } finally { child.kill(); await context.close(); }
}
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  try {
    for (const kind of ['tsv', 'xlsx', 'records']) for (const language of ['en', 'zh-CN']) await runCase(browser, kind, language);
    fs.writeFileSync(path.join(out, 'evidence.json'), JSON.stringify({ status: 'passed', cases: results }, null, 2) + '\n');
    console.log(JSON.stringify({ status: 'passed', cases: results.length, evidence: path.join(out, 'evidence.json') }));
  } catch (error) {
    fs.writeFileSync(path.join(out, 'failure.json'), JSON.stringify({ error: String(error), stack: error.stack, cases: results }, null, 2));
    throw error;
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
