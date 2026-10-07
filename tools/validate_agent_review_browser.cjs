/* Real imported-proposal review across five formats and both languages. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn, execFileSync } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..'), python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || path.join(root, 'build', 'agent-review-' + Date.now()));
assert(out.startsWith(path.join(root, 'build') + path.sep) && !fs.existsSync(out));
fs.mkdirSync(out, { recursive: true });
const results = [];
const hash = (file) => 'sha256:' + crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
async function start(directory, language) {
  const child = spawn(python, ['-X', 'utf8', '-m', 'paperdelta', '--lang', language, '-C', directory, 'studio', '--no-open'], { cwd: root, windowsHide: true, env: process.env });
  let output = '';
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { child.kill(); reject(new Error('Startup timeout: ' + output)); }, 45000);
    child.stdout.on('data', (data) => { output += data; const match = output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/); if (match) { clearTimeout(timer); resolve(match[0]); } });
    child.stderr.on('data', (data) => { output += data; });
    child.on('exit', (code) => { clearTimeout(timer); reject(new Error('Studio exit: ' + code + ' ' + output)); });
  });
  return { child, url };
}
async function ready(page, allowError = false) {
  await page.waitForFunction(() => !document.body.hasAttribute('aria-busy'));
  if (!allowError && await page.locator('#error').isVisible()) throw new Error(await page.locator('#error').textContent());
}
async function runCase(browser, kind, language) {
  const name = kind + '-' + language, directory = path.join(out, name);
  const fixture = JSON.parse(execFileSync(python, ['-X', 'utf8', '-m', 'tools.agent_review_fixture', '--out', directory, '--document', kind], { cwd: root, encoding: 'utf8', windowsHide: true }));
  const before = fs.readFileSync(path.join(directory, 'paperdelta.yaml'));
  const context = await browser.newContext({ viewport: { width: 1360, height: 1000 } });
  const page = await context.newPage(), errors = [], remote = [];
  page.setDefaultTimeout(45000);
  page.on('pageerror', error => errors.push(String(error)));
  page.on('request', request => { if (!request.url().startsWith('http://127.0.0.1:')) remote.push(request.url()); });
  const { child, url } = await start(directory, language);
  try {
    await page.goto(url); await page.locator('#workspace').waitFor(); await ready(page);
    await page.locator('#open-binding').click(); await ready(page);
    await page.locator('nav [data-step=review]').click(); await ready(page);
    await page.locator('#proposal-file').setInputFiles(path.join(directory, 'proposal.json'));
    await page.locator('[data-proposal-evidence]').waitFor(); await ready(page);
    assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), before);
    const card = page.locator('[data-proposal-evidence]');
    const content = await card.textContent();
    assert(content.includes('results.csv') && content.includes('001') && content.includes('selected'));
    assert(content.includes(fixture.input_sha256['results.csv']));
    assert(content.includes(language === 'en' ? 'Showing 10 of 12 records' : '显示 12 条记录中的 10 条'));
    assert(content.includes(language === 'en' ? 'stale paper value' : '过期数值'));
    const originalContext = await page.locator('#review-items .candidate-context').textContent();
    assert(originalContext.includes('The mean accuracy is') && originalContext.includes('for model 001.'));
    if (kind === 'docx') assert(originalContext.includes('Maple / 001 / selected / test'));
    assert.equal(await page.locator('#review-items input:checked').count(), 0);
    await page.locator('#review-items input[data-binding="occurrences:result"]').check();
    await page.locator('#attest').check(); assert.equal(await page.locator('#accept').isDisabled(), false);
    await page.locator('#language').selectOption(language === 'en' ? 'zh-CN' : 'en'); await ready(page);
    assert.equal(await page.locator('#review-items input[data-binding="occurrences:result"]').isChecked(), true);
    assert.equal(await page.locator('#attest').isChecked(), false);
    assert.equal(await page.locator('#accept').isDisabled(), true);
    assert((await card.textContent()).includes(language === 'en' ? '声明的来源单位' : 'Declared source unit'));
    await page.locator('#language').selectOption(language); await ready(page);
    await page.locator('[data-complete-evidence="accuracy"] > summary').click();
    assert((await page.locator('[data-complete-evidence="accuracy"]').textContent()).includes('012'));
    await page.screenshot({ path: path.join(out, name + '.png'), fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.screenshot({ path: path.join(out, name + '-mobile.png'), fullPage: true });
    await page.setViewportSize({ width: 1360, height: 1000 });
    await page.locator('#attest').check(); await page.locator('#accept').click(); await ready(page);
    await page.locator('#receipt').waitFor();
    const config = JSON.parse(execFileSync(python, ['-X', 'utf8', '-c', 'import json,sys,yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1],encoding="utf-8"))))', path.join(directory, 'paperdelta.yaml')], { encoding: 'utf8', windowsHide: true }));
    assert.deepEqual(Object.keys(config.occurrences), ['result']);
    assert.equal(config.metrics.accuracy.unit, 'fraction');
    assert.equal(config.metrics.accuracy.where.model, '001');
    for (const [file, original] of Object.entries(fixture.input_sha256)) assert.equal(hash(path.join(directory, file)), original);
    const accepted = fs.readFileSync(path.join(directory, 'paperdelta.yaml'));
    await page.locator('#proposal-file').setInputFiles(path.join(directory, 'stale-proposal.json')); await ready(page, true);
    await page.locator('#error').waitFor();
    assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), accepted);
    assert.equal(await page.locator('#accept').isDisabled(), true);
    assert.deepEqual(errors, []); assert.deepEqual(remote, []);
    results.push({ format: kind, language, original_inputs_unchanged: true, original_context_visible: true, declared_identity_and_hash_visible: true, truncation_and_complete_evidence_visible: true, language_keeps_selection_clears_confirmation: true, explicit_acceptance_only: true, stale_import_rejected: true, mobile_no_overflow: true, browser_errors: errors, remote_requests: remote });
    console.log(name + ' passed');
  } catch (error) {
    await page.screenshot({ path: path.join(out, name + '-failure.png'), fullPage: true }); throw error;
  } finally { await context.close(); child.kill(); }
}
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  try { for (const kind of ['latex', 'markdown', 'quarto', 'docx', 'pdf']) for (const language of ['en', 'zh-CN']) await runCase(browser, kind, language); }
  finally { await browser.close(); fs.writeFileSync(path.join(out, 'evidence.json'), JSON.stringify({ suite: 'agent-evidence-review', results, scope: 'Machine browser acceptance on original authored inputs; no model inference or human measurements.' }, null, 2) + '\n'); }
})().catch(error => { console.error(error); process.exitCode = 1; });
