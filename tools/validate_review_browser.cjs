/* Real browser: a second experiment, declaration edits, native repair and recovery. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { spawn, execFileSync } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..'), python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || 'build/studio-review-browser');
const recordDemo = process.argv.includes('--record');
if (fs.existsSync(out)) throw new Error('Use a new output directory.');
fs.mkdirSync(out, { recursive: true });
function fixture(directory, kind, revise = false) {
  execFileSync(python, ['-X', 'utf8', path.join(root, 'tools/review_browser_fixture.py'), directory, kind, ...(revise ? ['--revise'] : [])], { cwd: root, windowsHide: true, stdio: 'pipe' });
}
async function start(directory, lang) {
  const child = spawn(python, ['-X', 'utf8', '-m', 'paperdelta', '--lang', lang, '-C', directory, 'studio', '--no-open'], { cwd: root, windowsHide: true });
  let output = '';
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { child.kill(); reject(new Error('Studio startup timed out')); }, 30000);
    child.stdout.on('data', (chunk) => {
      output += chunk.toString(); const match = output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/);
      if (match) { clearTimeout(timer); resolve(match[0]); }
    });
    child.on('error', (error) => { clearTimeout(timer); reject(error); });
    child.on('exit', (code) => { clearTimeout(timer); if (code) reject(new Error('Studio exited: ' + code)); });
  });
  return { child, url };
}
async function stop(child) {
  if (child.exitCode !== null) return;
  await new Promise((resolve) => { child.once('close', resolve); child.kill(); });
}
async function ready(page) {
  await page.waitForFunction(() => !document.body.hasAttribute('aria-busy'));
  const message = page.locator('#error');
  if (await message.isVisible()) throw new Error(await message.innerText());
}
async function click(page, selector) { await page.locator(selector).click(); await ready(page); }
async function untilText(page, id, value) {
  await page.waitForFunction(({ id, value }) => document.getElementById(id).textContent.includes(value), { id, value }, { timeout: 30000 });
  await ready(page);
}
async function editDeclaration(page, id) {
  await click(page, '#load-declarations');
  const row = page.locator('.declaration-row').filter({ hasText: id });
  assert.equal(await row.count(), 1); await row.locator('button').click(); await ready(page);
}
async function saveMaintenance(page) {
  await click(page, '#declaration-form button[type=submit]');
  assert(await page.locator('#accept-maintenance').isDisabled());
  await page.locator('#maintenance-attest').check();
  await click(page, '#accept-maintenance');
}
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  const results = [];
  try {
    for (const kind of ['tex', 'docx', 'pdf']) for (const lang of ['en', 'zh-CN']) {
      const name = kind + '-' + lang, directory = path.join(out, name); fixture(directory, kind);
      let server = await start(directory, lang), context;
      const errors = [], remote = [], failedRequests = [];
      async function connect() {
        context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
        const page = await context.newPage();
        page.on('pageerror', (error) => errors.push(String(error)));
        page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
        page.on('response', async (response) => {
          if (response.status() < 400) return;
          failedRequests.push({ status: response.status(), request: response.request().postData(), body: await response.text().catch(() => '') });
        });
        page.on('request', (request) => {
          if (!request.url().startsWith(new URL(server.url).origin) && !request.url().startsWith('data:') && !request.url().startsWith('blob:')) remote.push(request.url());
        });
        await page.goto(server.url); await page.locator('#review-workspace').waitFor({ state: 'visible' }); await ready(page);
        await click(page, '#advanced-impacts > summary');
        await click(page, '#advanced-review > summary');
        return page;
      }
      let page;
      const frames = [];
      async function capture(step, selector, duration = 4000) {
        if (!recordDemo || kind !== 'tex') return;
        const directory = path.join(out, 'recording', lang); fs.mkdirSync(directory, { recursive: true });
        await page.setViewportSize({ width: 1100, height: 820 });
        await page.locator(selector).first().scrollIntoViewIfNeeded();
        const file = String(frames.length).padStart(3, '0') + '.png';
        await page.screenshot({ path: path.join(directory, file) });
        frames.push({ file, duration, step });
        fs.writeFileSync(path.join(directory, 'frames.json'), JSON.stringify({ size: [1100, 820], source: 'Actual Studio browser workflow; screen holds are paced for reading.', frames }, null, 2) + '\n');
        await page.setViewportSize({ width: 1440, height: 1000 });
      }
      try {
        page = await connect(); await untilText(page, 'impact-groups', '0.841');
        await page.locator('#snapshot-form [name=name]').fill('submitted-v1'); await click(page, '#snapshot-form button');
        const snapshot = fs.readFileSync(path.join(directory, '.paperdelta/baselines/submitted-v1.json'));
        await page.locator('#baseline-select').selectOption('submitted-v1'); await ready(page);
        await capture('snapshot-before-experiment', '#ongoing-counts');
        const originalPaper = fs.readFileSync(path.join(directory, 'paper.' + kind));
        const changedData = fs.readFileSync(path.join(directory, 'results.csv'), 'utf8').replace('0.840', '0.800').replace('0.842', '0.802');
        fs.writeFileSync(path.join(directory, 'results.csv'), changedData);
        await untilText(page, 'impact-groups', '0.801'); assert((await page.locator('#impact-groups').textContent()).includes('0.841'));
        await capture('changed-evidence-and-paper-impact', '#impact-groups', 5000);
        if (recordDemo && kind === 'tex') {
          await page.locator('#impact-groups > article > details > summary').click();
          await page.locator('#impact-groups details details > summary').click();
          await capture('inspect-exact-records', '#impact-groups details details', 5000);
          await page.locator('#impact-groups > article > details > summary').click();
        }
        await click(page, '#claim-list button');
        await page.locator('#claim-reviewer').fill('Fixture author'); await page.locator('#claim-note').fill('Reviewed the changed experiment and the failed comparison.');
        await page.locator('#claim-attest').check(); await click(page, '#claim-review-form button');
        assert(await page.locator('#claim-list .status-mismatch').isVisible());
        await editDeclaration(page, 'occurrences:abstract');
        await page.locator('[data-field="display.places"]').fill('2');
        await page.locator('#declaration-reason').fill('Show the accepted result with two decimal places.');
        const beforeEdit = fs.readFileSync(path.join(directory, 'paperdelta.yaml'));
        await click(page, '#declaration-form button[type=submit]');
        assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), beforeEdit);
        assert((await page.locator('#maintenance-preview').textContent()).includes('occurrences:abstract'));
        await capture('preview-declaration-change', '#maintenance-preview');
        await page.locator('#language').selectOption(lang === 'en' ? 'zh-CN' : 'en'); await ready(page);
        assert.equal(await page.locator('[data-field="display.places"]').inputValue(), '2');
        assert((await page.locator('[data-field="display.places"]').getAttribute('aria-label')).includes(lang === 'en' ? '小数位数' : 'Decimal places'));
        await page.locator('#language').selectOption(lang); await ready(page);
        await page.locator('#maintenance-attest').check(); await click(page, '#accept-maintenance');
        assert.deepEqual(fs.readFileSync(path.join(directory, 'paper.' + kind)), originalPaper);
        assert.equal(fs.readFileSync(path.join(directory, 'results.csv'), 'utf8'), changedData);
        await page.screenshot({ path: path.join(out, name + '-review.png'), fullPage: true });
        await capture('saved-declaration-with-original-files-unchanged', '#impact-groups');
        const previousGeneration = await page.locator('#review-workspace').getAttribute('data-generation');
        fixture(directory, kind, true); const revisedPaper = fs.readFileSync(path.join(directory, 'paper.' + kind));
        await page.waitForFunction((previous) => {
          const workspace = document.getElementById('review-workspace');
          return workspace.dataset.generation !== previous && workspace.dataset.reviewState === 'current';
        }, previousGeneration, { timeout: 30000 });
        await ready(page);
        await click(page, '#scan-repairs'); await page.locator('#repair-binding').selectOption('occurrences:abstract'); await ready(page);
        await page.locator('#repair-query').fill('Revised'); await click(page, '#repair-search-form button');
        await page.locator('#repair-candidates input').first().check(); await ready(page);
        if (kind === 'pdf') { await page.locator('#repair-page img').waitFor({ state: 'visible' }); assert.equal(await page.locator('#repair-page rect').count(), 1); }
        await page.locator('#repair-reason').fill('The same result was reworded without changing its identity.');
        await click(page, '#repair-form button'); assert(await page.locator('#accept-repair').isDisabled());
        await page.locator('#repair-attest').check(); await click(page, '#accept-repair');
        assert.deepEqual(fs.readFileSync(path.join(directory, 'paper.' + kind)), revisedPaper);
        await editDeclaration(page, 'occurrences:abstract'); await page.locator('#remove-declaration').check();
        await page.locator('#declaration-reason').fill('Replace this declaration after checking the newly worded result.');
        await saveMaintenance(page);
        assert((await page.locator('#removed-bindings').textContent()).includes('abstract'));
        const beforeRecovery = fs.readFileSync(path.join(directory, 'paperdelta.yaml'));
        await click(page, '#open-binding'); await click(page, 'nav [data-step=locations]');
        await page.locator('#candidates input').first().check(); await ready(page);
        await page.locator('#locations-form [name=metric]').selectOption('ours');
        await page.locator('#locations-form [name=prefix]').fill('recovered');
        await page.locator('#locations-form [name=rationale]').fill('The selected revised position still represents Model 001.');
        await click(page, '#locations-form button[type=submit]');
        await context.close(); context = null; await stop(server.child);
        server = await start(directory, lang); page = await connect();
        await page.locator('#recovery-banner').waitFor({ state: 'visible' }); await click(page, '#restore-local');
        assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), beforeRecovery);
        await click(page, 'nav [data-step=review]'); await click(page, '#preview');
        assert.equal(await page.locator('#review-items input').count(), 1);
        await page.locator('#review-items input').check(); await page.locator('#attest').check(); await click(page, '#accept');
        assert.deepEqual(fs.readFileSync(path.join(directory, 'paper.' + kind)), revisedPaper);
        assert.deepEqual(fs.readFileSync(path.join(directory, '.paperdelta/baselines/submitted-v1.json')), snapshot);
        await click(page, 'nav [data-step=evidence]'); await click(page, '#add-derived summary');
        await page.locator('#derived-form [name=name]').fill('draft_delta');
        await page.locator('#derived-form [name=operation]').selectOption('difference');
        await page.locator('#derived-form [name=left]').selectOption('ours'); await page.locator('#derived-form [name=right]').selectOption('ours');
        await click(page, '#derived-form button');
        const beforeRebuild = fs.readFileSync(path.join(directory, 'paperdelta.yaml'));
        fs.writeFileSync(path.join(directory, 'results.csv'), changedData.replace('0.800', '0.820'));
        await page.locator('#stale').waitFor({ state: 'visible', timeout: 30000 });
        await click(page, '#open-rebuild'); await page.locator('#rebuild-items input[value="metrics:draft_delta"]').check();
        await click(page, '#preview-rebuild'); assert(await page.locator('#accept-rebuild').isDisabled());
        await page.locator('#rebuild-attest').check(); await click(page, '#accept-rebuild');
        assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), beforeRebuild);
        assert((await page.locator('#metric-list').textContent()).includes('draft_delta'));
        assert(fs.readdirSync(path.join(directory, '.paperdelta/studio/archives')).length > 0);
        await click(page, '#open-review'); await page.setViewportSize({ width: 390, height: 844 });
        await page.screenshot({ path: path.join(out, name + '-mobile.png'), fullPage: true });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, name + ' overflow');
        await page.setViewportSize({ width: 1440, height: 1000 }); await click(page, '#open-binding');
        page.once('dialog', (dialog) => dialog.accept()); await click(page, '#refresh');
        await click(page, '#open-review'); await editDeclaration(page, 'metrics:ours');
        await page.locator('#remove-declaration').check();
        assert(await page.locator('#declaration-form button[type=submit]').isDisabled());
        assert.equal(await page.locator('#dependent-choices input').count(), 3);
        for (const checkbox of await page.locator('#dependent-choices input').all()) await checkbox.check();
        await page.locator('#declaration-reason').fill('Remove this metric and each explicitly selected dependent declaration.');
        const beforeGroupRemoval = fs.readFileSync(path.join(directory, 'paperdelta.yaml'));
        await click(page, '#declaration-form button[type=submit]');
        assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), beforeGroupRemoval);
        assert.equal(await page.locator('#maintenance-preview .preview-card').count(), 4);
        await page.locator('#maintenance-attest').check(); await click(page, '#accept-maintenance');
        assert.equal(await page.locator('#claim-list button').count(), 0);
        assert.deepEqual(fs.readFileSync(path.join(directory, 'paper.' + kind)), revisedPaper);
        assert.deepEqual(errors, [], name + ' browser errors'); assert.deepEqual(remote, [], name + ' remote requests');
        results.push({ document: kind, language: lang, snapshot_comparison: true, false_claim_review: true,
          declaration_preview_accept: true, native_visual_repair: true, dependency_aware_deletion: true,
          restart_recovery: true, changed_input_rebuild: true, original_manuscript_not_written: true,
          explicit_dependent_group_removal: true, desktop_mobile: true, browser_errors: errors, remote_requests: remote });
        process.stdout.write(name + ' ongoing review passed\n');
      } catch (error) {
        if (page && !page.isClosed()) await page.screenshot({ path: path.join(out, name + '-failure.png'), fullPage: true }).catch(() => {});
        fs.writeFileSync(path.join(out, name + '-errors.json'), JSON.stringify({ errors, remote, failedRequests, failure: String(error) }, null, 2));
        throw error;
      } finally {
        if (context) await context.close();
        await stop(server.child);
      }
    }
    fs.writeFileSync(path.join(out, 'evidence.json'), JSON.stringify({ suite: 'ongoing-review', flows: results }, null, 2) + '\n');
  } finally { await browser.close(); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
