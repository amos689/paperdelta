/* Actual bilingual selection, preview, download and isolated replay on five formats. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn, execFileSync } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..'), python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || path.join(root, 'build', 'review-bundle-' + Date.now()));
assert(out.startsWith(path.join(root, 'build') + path.sep) && !fs.existsSync(out));
fs.mkdirSync(out, { recursive: true });
const results = [];
const digest = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const py = (args) => execFileSync(python, ['-X', 'utf8', ...args], { cwd: root, encoding: 'utf8', windowsHide: true });
async function start(directory, language) {
  const child = spawn(python, ['-X', 'utf8', '-m', 'paperdelta', '--lang', language, '-C', directory, 'studio', '--no-open'], { cwd: root, windowsHide: true });
  let output = '';
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { child.kill(); reject(new Error(output)); }, 45000);
    child.stdout.on('data', (data) => { output += data; const match = output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/); if (match) { clearTimeout(timer); resolve(match[0]); } });
    child.stderr.on('data', (data) => { output += data; });
    child.on('exit', (code) => { clearTimeout(timer); reject(new Error(code + ': ' + output)); });
  });
  return { child, url };
}
async function runCase(browser, kind, language) {
  const name = kind + '-' + language, directory = path.join(out, name);
  py(['-m', 'paperdelta', '--lang', language, 'demo', '--document', kind, '--scenario', 'changed', '--out', path.relative(root, directory), '--format', 'json']);
  const originalConfig = fs.readFileSync(path.join(directory, 'paperdelta.yaml'));
  const { child, url } = await start(directory, language);
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  const page = await context.newPage(), errors = [], remote = [];
  page.setDefaultTimeout(45000);
  page.on('pageerror', (error) => errors.push(String(error)));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('request', (request) => { if (![new URL(url).origin, 'data:', 'blob:'].some((prefix) => request.url().startsWith(prefix))) remote.push(request.url()); });
  async function ready() {
    await page.waitForFunction(() => !document.body.hasAttribute('aria-busy'));
    if (await page.locator('#error').isVisible()) throw new Error(await page.locator('#error').textContent());
  }
  async function act(selector, method = 'click', value) { await page.locator(selector)[method](value); await ready(); }
  try {
    await page.goto(url); await page.locator('#workspace').waitFor({ state: 'visible' }); await ready();
    await act('#bundle-panel > summary');
    await act('#bundle-baseline', 'fill', 'before');
    await act('#bundle-open');
    assert.equal(await page.locator('[data-bundle-input]:checked').count(), 0);
    const paths = await page.locator('[data-bundle-input]').evaluateAll((items) => items.map((item) => item.dataset.bundleInput));
    assert(paths.includes('.paperdelta/baselines/before.json'));
    const inputHashes = Object.fromEntries(paths.map((file) => [file, digest(path.join(directory, file))]));
    await act('#bundle-preview');
    assert(await page.locator('#bundle-export').isDisabled());
    assert(await page.locator('#bundle-files details').count() >= 3);
    await act('#bundle-attest', 'check');
    assert(!await page.locator('#bundle-export').isDisabled());
    await act('#bundle-all');
    assert(await page.locator('#bundle-export').isDisabled());
    assert.equal(await page.locator('[data-bundle-input]:checked').count(), paths.length);
    await act('[data-bundle-report=sarif]', 'check');
    await act('#bundle-preview');
    await act('#language', 'selectOption', language === 'en' ? 'zh-CN' : 'en');
    assert.equal(await page.locator('[data-bundle-input]:checked').count(), paths.length);
    assert.equal(await page.locator('#bundle-baseline').inputValue(), 'before');
    assert(await page.locator('#bundle-export').isDisabled());
    await act('#language', 'selectOption', language);
    assert.equal(await page.locator('[data-bundle-input]:checked').count(), paths.length);
    await act('#bundle-attest', 'check');
    await page.locator('#bundle-panel').screenshot({ path: path.join(out, name + '-preview.png') });
    const downloadPromise = page.waitForEvent('download');
    await act('#bundle-export');
    const download = await downloadPromise, archive = path.join(directory, 'review-export.zip');
    await download.saveAs(archive);
    const inspected = JSON.parse(py(['-m', 'paperdelta', '-C', directory, 'bundle', 'inspect', 'review-export.zip']));
    assert.equal(inspected.plan.language, language); assert(inspected.plan.replayable);
    assert.deepEqual(Object.keys(inspected.plan.required_inputs).sort(), paths.sort());
    const replayPath = path.join(out, name + '-replay.json');
    py(['-c', 'import sys; from pathlib import Path; from paperdelta.review_bundle import replay_bundle; from paperdelta.storage import Project,json_text; p=Project(sys.argv[1]); r=replay_bundle(p,p.read("review-export.zip",160*1024*1024),"isolated-replay"); Path(sys.argv[2]).write_text(json_text(r),encoding="utf-8"); assert r["same_result"] and r["check_exit_code"]==1 and not r["executed_project_code"]', directory, replayPath]);
    const replay = JSON.parse(fs.readFileSync(replayPath, 'utf8'));
    assert.deepEqual(replay.scope, inspected.plan.scope);
    assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), originalConfig);
    assert.deepEqual(Object.fromEntries(paths.map((file) => [file, digest(path.join(directory, file))])), inputHashes);
    await page.setViewportSize({ width: 390, height: 844 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2));
    assert.deepEqual(errors, []); assert.deepEqual(remote, []);
    results.push({ name, status: 'passed', checked_inputs: paths.length, scope: replay.scope, input_sha256: inputHashes, archive_sha256: digest(archive), language_switch_preserved_selection: true, replayed_same_result: true, no_project_execution: true, remote_requests: remote });
  } catch (error) {
    await page.screenshot({ path: path.join(out, name + '-failure.png'), fullPage: true }).catch(() => {});
    fs.writeFileSync(path.join(out, 'failure.json'), JSON.stringify({ name, error: String(error), errors, completed: results }, null, 2));
    throw error;
  } finally { await context.close(); child.kill(); }
}
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  try {
    for (const kind of ['latex', 'docx', 'pdf', 'markdown', 'quarto']) for (const language of ['en', 'zh-CN']) await runCase(browser, kind, language);
    fs.writeFileSync(path.join(out, 'evidence.json'), JSON.stringify({ status: 'passed', scope: 'Developer-operated browser workflows and exact-input replay, not human usability or scientific validation.', cases: results }, null, 2) + '\n');
    console.log(JSON.stringify({ status: 'passed', cases: results.length }));
  } finally { await browser.close(); }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
