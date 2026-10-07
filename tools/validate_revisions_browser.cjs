/* Actual bilingual browser review, selected edits and restart-safe recovery. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawn, spawnSync, execFileSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..'), python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || 'build/revisions-browser-' + Date.now());
assert(out.startsWith(path.join(root, 'build') + path.sep) && !fs.existsSync(out));
fs.mkdirSync(out, {recursive: true});
const py = args => execFileSync(python, ['-X', 'utf8', ...args], {cwd: root, encoding: 'utf8', windowsHide: true});
const baselineMode = process.argv.includes('--baseline');
const digest = raw => crypto.createHash('sha256').update(raw).digest('hex');
async function start(directory, language) {
  const child = spawn(python, ['-X', 'utf8', '-m', 'paperdelta', '--lang', language, '-C', directory, 'studio', '--no-open'], {cwd: root, windowsHide: true});
  let output = '';
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {child.kill(); reject(new Error('Studio startup timeout: ' + output));}, 45000);
    child.stdout.on('data', data => {output += data; const match = output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/); if (match) {clearTimeout(timer); resolve(match[0]);}});
    child.stderr.on('data', data => {output += data;});
    child.on('error', error => {clearTimeout(timer); reject(error);});
    child.on('exit', code => {clearTimeout(timer); reject(new Error('Studio exit ' + code + ': ' + output));});
  });
  return {child, url};
}
async function stop(server) {
  if (!server || server.child.exitCode !== null) return;
  await new Promise(resolve => {server.child.once('close', resolve); server.child.kill();});
}
async function runCase(browser, format, language) {
  const name = format + '-' + language, directory = path.join(out, name);
  py(['-m', 'paperdelta', '-C', out, 'demo', '--document', format, '--scenario', 'safe-update', '--out', name]);
  const text = ['latex', 'markdown', 'quarto'].includes(format);
  const initialReport = JSON.parse(fs.readFileSync(path.join(directory, 'review/report.json'), 'utf8'));
  const file = initialReport.occurrences.table_accuracy.location.file;
  const originalPapers = Object.fromEntries(Object.keys(initialReport.input_hashes).filter(file => /\.(tex|md|qmd|docx|pdf)$/.test(file)).map(file => [file, fs.readFileSync(path.join(directory, file))]));
  const source = path.join(directory, file), data = path.join(directory, 'results/metrics.csv');
  const original = fs.readFileSync(source), evidence = fs.readFileSync(data), config = fs.readFileSync(path.join(directory, 'paperdelta.yaml'));
  const inputSha256 = Object.fromEntries([...Object.entries(originalPapers), ['results/metrics.csv', evidence]].map(([name, raw]) => [name, digest(raw)]));
  let server, context, page;
  const errors = [], remote = [], steps = [];
  async function ready(allowError = false) {
    await page.waitForFunction(() => !document.body.hasAttribute('aria-busy'));
    if (!allowError && await page.locator('#error').isVisible()) throw new Error(await page.locator('#error').textContent());
  }
  async function act(selector, method = 'click', value) {await page.locator(selector)[method](value); await ready(); steps.push({selector, method});}
  async function connect() {
    server = await start(directory, language);
    context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    page = await context.newPage(); page.setDefaultTimeout(45000);
    page.on('pageerror', error => errors.push(String(error)));
    page.on('request', request => {if (!request.url().startsWith(new URL(server.url).origin)) remote.push(request.url());});
    await page.goto(server.url); await page.locator(baselineMode ? '#review-workspace' : '#revision-board').waitFor({state: 'visible'}); await ready();
  }
  async function waitChange(before) {
    await page.waitForFunction(previous => {
      const panel = document.getElementById('review-workspace');
      return panel.dataset.generation !== previous && panel.dataset.reviewState === 'current' && !document.body.hasAttribute('aria-busy');
    }, before);
    await ready();
  }
  try {
    await connect();
    const version = await page.locator('#version').textContent();
    if (baselineMode) {
      assert.equal(version, '1.6.0'); assert.equal(await page.locator('#revision-board').count(), 0);
      await act('#impact-search', 'fill', initialReport.occurrences.table_accuracy.metric);
      assert.match(await page.locator('#impact-groups').innerText(), /84\.1/);
      assert.match(await page.locator('#impact-groups').innerText(), /0\.845/);
      await act('#impact-groups > article > details > summary');
      await act('#impact-groups details details > summary');
      assert.match(await page.locator('#impact-groups').innerText(), /metrics\.csv/);
      const cli = (args, expectedExit = 0) => {
        const command = ['-X', 'utf8', '-m', 'paperdelta', '--lang', language, '-C', directory, ...args, '--format', 'json'];
        const result = spawnSync(python, command, {cwd: root, encoding: 'utf8', windowsHide: true});
        assert.equal(result.status, expectedExit, result.stdout + result.stderr);
        const body = JSON.parse(result.stdout);
        steps.push({interface: 'cli', command: args, exit_code: result.status});
        return body;
      };
      cli(['fix', '--report', 'review/report.json', '--only', 'table_accuracy', '--out', 'selected.pdpatch.json']);
      const preview = cli(['apply', 'selected.pdpatch.json', '--dry-run']); assert.match(preview.diff, /84\.5/);
      assert.deepEqual(fs.readFileSync(source), original);
      const applied = cli(['apply', 'selected.pdpatch.json', '--write'], 1);
      assert.equal(applied.report.occurrences.table_accuracy.status, 'pass');
      assert.equal(applied.report.occurrences.abstract_accuracy.status, 'mismatch');
      await page.locator('.impact-row').filter({hasText: 'table_accuracy'}).locator('.status-pass').waitFor();
      const written = fs.readFileSync(source); assert.notDeepEqual(written, original);
      cli(['recover', applied.transaction_id]); assert.deepEqual(fs.readFileSync(source), written);
      cli(['recover', applied.transaction_id, '--write']);
      await page.locator('.impact-row').filter({hasText: 'table_accuracy'}).locator('.status-mismatch').waitFor();
      for (const [file, raw] of Object.entries(originalPapers)) assert.deepEqual(fs.readFileSync(path.join(directory, file)), raw);
      assert.deepEqual(fs.readFileSync(data), evidence); assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), config);
      assert.deepEqual(errors, []); assert.deepEqual(remote, []);
      await page.locator('#impact-groups').screenshot({path: path.join(out, name + '-baseline.png')});
      return {name, format, language, version, status: 'passed', input_sha256: inputSha256,
        selected_numeric_apply: true, original_restored: true, required_interfaces: ['browser', 'cli'], steps, remote_requests: remote};
    }
    assert.equal(await page.locator('#advanced-review').getAttribute('open'), null);
    assert.equal(await page.locator('#revision-tasks input:checked').count(), 0);
    assert(await page.locator('#revision-coverage').isVisible());
    const coverage = initialReport.coverage;
    const warning = coverage.unbound_numbers.length + coverage.unsupported.length + coverage.unregistered_figures.length > 0;
    assert.equal(await page.locator('#revision-coverage').evaluate(element => element.classList.contains('warning')), warning);
    const downloadPromise = page.waitForEvent('download');
    await act('#revision-coverage-report');
    const download = await downloadPromise; await download.saveAs(path.join(out, name + '-coverage.html'));
    await act('#revision-search', 'fill', 'table_accuracy');
    await act('#revision-filter', 'selectOption', 'mismatch');
    await act('#revision-tasks [data-subject="occurrence:table_accuracy"] .revision-focus');
    assert.match(await page.locator('#revision-detail').innerText(), /84\.1/);
    assert.match(await page.locator('#revision-detail').innerText(), /84\.5/);
    assert((await page.locator('#revision-detail').innerText()).includes(initialReport.occurrences.table_accuracy.metric));
    if (text) {
      await act('#revision-tasks input[value=table_accuracy]', 'check');
      await act('#revision-preview-button');
      assert.match(await page.locator('#revision-diff').textContent(), /84\.5/);
      assert(await page.locator('#revision-apply').isDisabled());
      assert.deepEqual(fs.readFileSync(source), original);
      await act('#revision-attest', 'check');
      await act('#language', 'selectOption', language === 'en' ? 'zh-CN' : 'en');
      assert(await page.locator('#revision-preview').isHidden());
      assert(await page.locator('#revision-apply').isDisabled());
      assert(await page.locator('#revision-tasks input[value=table_accuracy]').isChecked());
      assert.equal(await page.locator('#revision-search').inputValue(), 'table_accuracy');
      assert.equal(await page.locator('#revision-filter').inputValue(), 'mismatch');
      await act('#language', 'selectOption', language);
      await act('#revision-preview-button');
      const before = await page.locator('#review-workspace').getAttribute('data-generation');
      fs.writeFileSync(data, Buffer.concat([evidence, Buffer.from('\n')]));
      await waitChange(before);
      assert(await page.locator('#revision-preview').isHidden());
      assert.deepEqual(fs.readFileSync(source), original);
      await act('#revision-preview-button');
      await page.locator('#revision-preview').screenshot({path: path.join(out, name + '-preview.png')});
      await act('#revision-attest', 'check'); await act('#revision-apply');
      const written = fs.readFileSync(source); assert.notDeepEqual(written, original);
      for (const [name, raw] of Object.entries(originalPapers)) if (name !== file) assert.deepEqual(fs.readFileSync(path.join(directory, name)), raw);
      assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), config);
      assert.deepEqual(fs.readFileSync(data), Buffer.concat([evidence, Buffer.from('\n')]));
      const report = JSON.parse(py(['-c', 'import sys; from paperdelta.analysis import check_project; from paperdelta.storage import json_text; print(json_text(check_project(sys.argv[1])))', directory]));
      assert.equal(report.occurrences.table_accuracy.status, 'pass');
      assert.equal(report.occurrences.abstract_accuracy.status, 'mismatch');
      await act('#revision-history > summary');
      const id = await page.locator('#revision-transaction option').nth(1).getAttribute('value');
      assert.match(id, /^[a-f0-9]{32}$/);
      await context.close(); context = null; await stop(server); server = null;
      await connect();
      await act('#revision-history > summary'); await act('#revision-history-load');
      await act('#revision-transaction', 'selectOption', id); await act('#revision-recovery-button');
      assert(await page.locator('#revision-recover').isDisabled());
      assert.deepEqual(fs.readFileSync(source), written);
      await act('#revision-recovery-attest', 'check');
      await act('#language', 'selectOption', language === 'en' ? 'zh-CN' : 'en');
      assert(await page.locator('#revision-recovery-preview').isHidden());
      assert.equal(await page.locator('#revision-transaction').inputValue(), id);
      await act('#language', 'selectOption', language);
      await act('#revision-recovery-button'); await act('#revision-recovery-attest', 'check'); await act('#revision-recover');
      assert.deepEqual(fs.readFileSync(source), original);
      // A newly false claim must remove related mechanical edits from the queue.
      const generation = await page.locator('#review-workspace').getAttribute('data-generation');
      fs.writeFileSync(data, evidence.toString('utf8').replaceAll('0.843', '0.807').replaceAll('0.845', '0.809').replaceAll('0.847', '0.811'));
      await waitChange(generation);
      await act('#revision-search', 'fill', 'abstract_accuracy');
      assert.equal(await page.locator('#revision-tasks input').count(), 0);
      await act('#revision-tasks [data-subject="occurrence:abstract_accuracy"] .revision-focus');
      assert.match(await page.locator('#revision-detail').textContent(), /main_comparison/);
      await act('#revision-detail > button');
      assert(await page.locator('#claim-review-form').isVisible());
      assert.deepEqual(fs.readFileSync(source), original);
    } else {
      assert.equal(await page.locator('#revision-tasks input').count(), 0);
      assert(await page.locator('#revision-preview-button').isDisabled());
      await act('#language', 'selectOption', language === 'en' ? 'zh-CN' : 'en');
      assert.equal(await page.locator('#revision-search').inputValue(), 'table_accuracy');
      await act('#language', 'selectOption', language);
      assert.deepEqual(fs.readFileSync(source), original);
    }
    await act('#revision-search', 'fill', '');
    await page.locator('#revision-board').screenshot({path: path.join(out, name + '-board.png')});
    await page.setViewportSize({width: 390, height: 844});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2));
    await page.locator('#revision-board').screenshot({path: path.join(out, name + '-mobile.png')});
    assert.deepEqual(errors, []); assert.deepEqual(remote, []);
    return {name, format, language, version, status: 'passed', input_sha256: inputSha256,
      required_interfaces: ['browser'], selected_numeric_apply: text, restart_recovery: text,
      changed_inputs_invalidate_preview: text, false_claim_blocks_patch: text,
      language_preserves_selection_and_clears_acceptance: true, original_native_unchanged: !text,
      narrow_viewport: true, remote_requests: remote, steps};
  } catch (error) {
    if (page && !page.isClosed()) await page.screenshot({path: path.join(out, name + '-failure.png'), fullPage: true}).catch(() => {});
    fs.writeFileSync(path.join(out, name + '-failure.json'), JSON.stringify({error: String(error), stack: error.stack, errors, remote, steps}, null, 2) + '\n');
    throw error;
  } finally {if (context) await context.close(); await stop(server);}
}
(async () => {
  const browser = await chromium.launch({headless: true, ...(process.env.BROWSER_EXECUTABLE ? {executablePath: process.env.BROWSER_EXECUTABLE} : {})});
  const cases = [];
  try {
    for (const format of baselineMode ? ['latex'] : ['latex', 'markdown', 'quarto', 'docx', 'pdf']) for (const language of ['en', 'zh-CN']) {
      cases.push(await runCase(browser, format, language)); process.stdout.write(format + '-' + language + ' passed\n');
    }
    fs.writeFileSync(path.join(out, 'evidence.json'), JSON.stringify({status: 'passed', cases,
      scope: 'Authored local browser workflows on five formats in both languages. Not independent human usability or a population accuracy measurement.'}, null, 2) + '\n');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
