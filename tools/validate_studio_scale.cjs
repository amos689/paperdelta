/* Real-browser candidate completeness, cross-page selection and measured UI load. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { performance } = require('node:perf_hooks');
const { spawn, execFileSync } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..'), python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || 'build/studio-scale');
if (fs.existsSync(out)) throw new Error('Use a new output directory.');
fs.mkdirSync(out, { recursive: true });
async function ready(page) {
  await page.waitForFunction(() => !document.body.hasAttribute('aria-busy'));
  if (await page.locator('#error').isVisible()) throw new Error(await page.locator('#error').innerText());
}
async function click(page, selector) { await page.locator(selector).click(); await ready(page); }
async function start(directory) {
  const child = spawn(python, ['-X', 'utf8', '-m', 'paperdelta', '-C', directory, 'studio', '--no-open'], { cwd: root, windowsHide: true });
  let output = '', errors = '';
  child.stderr.on('data', (chunk) => { errors += chunk.toString(); });
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { child.kill(); reject(new Error('Startup timed out: ' + errors)); }, 60000);
    child.stdout.on('data', (chunk) => {
      output += chunk.toString(); const match = output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/);
      if (match) { clearTimeout(timer); resolve(match[0]); }
    });
    child.on('error', (error) => { clearTimeout(timer); reject(error); });
    child.on('exit', (code) => { clearTimeout(timer); reject(new Error('Studio exited: ' + code + ' ' + errors)); });
  });
  return { child, url };
}
async function stop(child) {
  if (child.exitCode !== null) return;
  await new Promise((resolve) => { child.once('close', resolve); child.kill(); });
}
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  const results = [];
  try {
    for (const kind of ['candidates', 'metrics']) {
      const directory = path.join(out, kind);
      execFileSync(python, ['-X', 'utf8', path.join(root, 'tools/studio_scale_fixture.py'), directory, kind], { cwd: root, windowsHide: true });
      const startup = performance.now(), server = await start(directory);
      const serverMs = performance.now() - startup, context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
      const page = await context.newPage(), errors = [], remote = [];
      page.on('pageerror', (error) => errors.push(String(error)));
      page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
      page.on('request', (request) => { if (!request.url().startsWith(new URL(server.url).origin) && !/^(data:|blob:)/.test(request.url())) remote.push(request.url()); });
      try {
        const load = performance.now(); await page.goto(server.url);
        await page.locator('#workspace').waitFor({ state: 'visible' }); await ready(page);
        const firstViewMs = performance.now() - load;
        const record = { kind, server_start_ms: serverMs, first_view_ms: firstViewMs };
        if (kind === 'candidates') {
          await click(page, 'nav [data-step=locations]');
          await page.locator('.candidate input').first().waitFor({ state: 'visible' });
          assert((await page.locator('#candidate-pages').innerText()).includes('5101'));
          const firstId = await page.locator('.candidate').first().getAttribute('data-candidate');
          await page.locator('.candidate input').first().check();
          const next = performance.now(); await click(page, '#candidate-pages button:last-child');
          await page.waitForFunction((id) => {
            const candidate = document.querySelector('.candidate');
            return candidate && candidate.dataset.candidate !== id;
          }, firstId);
          record.next_page_ms = performance.now() - next;
          await page.locator('.candidate input').first().check();
          const search = performance.now(); await page.locator('#search').fill('Finalmarker');
          const final = page.locator('.candidate').filter({ has: page.locator('label span', { hasText: 'paper.tex:5101' }) });
          await final.waitFor({ state: 'visible' }); record.search_after_5000_ms = performance.now() - search;
          assert((await final.locator('label span').textContent()).includes('5101'));
          await final.locator('input').check();
          await page.locator('#language').selectOption('zh-CN'); await ready(page);
          assert((await page.locator('#selection-count').textContent()).includes('3'));
          assert(await final.locator('input').isChecked());
          await page.locator('#locations-form [name=metric]').selectOption('repeated');
          await page.locator('#locations-form [name=prefix]').fill('cross_page');
          await page.locator('#locations-form [name=display_kind]').selectOption('decimal');
          await page.locator('#locations-form [name=places]').fill('1');
          await page.locator('#locations-form [name=rationale]').fill('Three explicit uses of the same declared repeated result.');
          await click(page, '#locations-form button[type=submit]'); await click(page, '#preview');
          assert.equal(await page.locator('#review-items input').count(), 3);
          for (const checkbox of await page.locator('#review-items input').all()) await checkbox.check();
          await page.locator('#attest').check(); await click(page, '#accept');
          const config = fs.readFileSync(path.join(directory, 'paperdelta.yaml'), 'utf8');
          for (const suffix of ['_1', '_2', '_3']) assert(config.includes('cross_page' + suffix));
          Object.assign(record, { candidate_count: 5101, cross_page_acceptance: 3, language_switch_preserves_selection: true });
        } else {
          assert.equal(await page.locator('.impact-card').count(), 20);
          assert((await page.locator('#impact-pages').textContent()).includes('500'));
          const search = performance.now(); await page.locator('#impact-search').fill('result_ATF');
          assert.equal(await page.locator('.impact-card').count(), 1);
          record.impact_search_ms = performance.now() - search;
          await click(page, '#open-binding'); await click(page, 'nav [data-step=evidence]');
          assert.equal(await page.locator('#metric-list .metric-card').count(), 20);
          await page.locator('#metric-search').fill('result_ATF');
          assert.equal(await page.locator('#metric-list .metric-card').count(), 1);
          Object.assign(record, { metrics: 500, displayed_per_page: 20, all_metrics_searchable: true });
        }
        await page.screenshot({ path: path.join(out, kind + '.png'), fullPage: true });
        assert.deepEqual(errors, []); assert.deepEqual(remote, []);
        results.push({ ...record, browser_errors: errors, remote_requests: remote });
        process.stdout.write(kind + ' scale workflow passed\n');
      } catch (error) {
        await page.screenshot({ path: path.join(out, kind + '-failure.png'), fullPage: true }).catch(() => {});
        fs.writeFileSync(path.join(out, kind + '-errors.json'), JSON.stringify({ failure: String(error), errors, remote }, null, 2));
        throw error;
      } finally { await context.close(); await stop(server.child); }
    }
    fs.writeFileSync(path.join(out, 'evidence.json'), JSON.stringify({ suite: 'studio-scale', results, scope: 'Local Chrome browser wall time; includes DOM and local HTTP. Single samples, not a population latency guarantee.' }, null, 2) + '\n');
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
