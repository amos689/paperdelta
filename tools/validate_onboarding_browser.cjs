/* Same 24-metric input as the preserved v0.6/v0.8 traces; actual UI actions only. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn, execFileSync } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..'), python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || path.join(root, 'build', 'onboarding-' + Date.now()));
assert(out.startsWith(path.join(root, 'build') + path.sep) && !fs.existsSync(out));
fs.mkdirSync(out, { recursive: true });
const results = [];
const reuseMode = process.argv.includes('--reuse');
const definitionsMode = process.argv.includes('--definitions') || reuseMode;
const digest = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
async function start(directory, language) {
  const child = spawn(python, ['-X', 'utf8', '-m', 'paperdelta', '--lang', language, '-C', directory, 'studio', '--no-open'], { cwd: root, windowsHide: true });
  let output = '';
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { child.kill(); reject(new Error('Startup: ' + output)); }, 45000);
    child.stdout.on('data', (data) => { output += data; const match = output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/); if (match) { clearTimeout(timer); resolve(match[0]); } });
    child.stderr.on('data', (data) => { output += data; });
    child.on('exit', (code) => { clearTimeout(timer); reject(new Error('Studio exited ' + code + ': ' + output)); });
  });
  return { child, url };
}
async function runCase(browser, kind, language) {
  const name = (reuseMode ? 'reuse-' : definitionsMode ? 'definitions-' : '') + kind + '-' + language, directory = path.join(out, name);
  execFileSync(python, ['-X', 'utf8', 'tools/studio_batch_fixture.py', '--out', path.relative(root, directory), '--document', kind], { cwd: root, windowsHide: true, encoding: 'utf8' });
  const expected = JSON.parse(fs.readFileSync(path.join(directory, 'browser-annotations.json'), 'utf8'));
  if (definitionsMode) {
    const manuscript = path.join(directory, 'paper.tex');
    const text = fs.readFileSync(manuscript, 'utf8').replace(/^001 &/m, 'Ours &').replace(/^1 &/m, 'Baseline &');
    assert(text.includes('Ours &') && text.includes('Baseline &'));
    fs.writeFileSync(manuscript, text);
  }
  const inputs = Object.fromEntries(['paper.' + kind, 'results.csv'].map((file) => [file, digest(path.join(directory, file))]));
  assert.equal(inputs['results.csv'], 'e1dac8b7b21d667ee6b8eb7cc3501533159e7eff79338d17fb27ede3cde0f6fa');
  if (kind === 'tex' && !definitionsMode) assert.equal(inputs['paper.tex'], '755727490a05041dff6a554cb46308d59b89d665ed3ae2700432ee6767b053e1');
  const before = fs.readFileSync(path.join(directory, 'paperdelta.yaml'));
  const { child, url } = await start(directory, language);
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage(), errors = [], remote = [], actions = [];
  page.setDefaultTimeout(45000);
  page.on('pageerror', (error) => errors.push(String(error)));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('request', (request) => { if (![new URL(url).origin, 'data:', 'blob:'].some((prefix) => request.url().startsWith(prefix))) remote.push(request.url()); });
  async function ready() {
    await page.waitForFunction(() => !document.body.hasAttribute('aria-busy'));
    if (await page.locator('#error').isVisible()) throw new Error(await page.locator('#error').textContent());
  }
  async function action(selector, method = 'click', value) {
    const control = page.locator(selector);
    if (method === 'check' && await control.isChecked()) return;
    if (['fill', 'selectOption'].includes(method) && await control.inputValue() === value) return;
    actions.push({ control: selector, action: method, ...(value === undefined ? {} : { value }) });
    await control[method](value); await ready();
  }
  try {
    await page.goto(url); await page.locator('#workspace').waitFor({ state: 'visible' }); await ready();
    const version = await page.locator('#version').textContent();
    assert.equal(await page.locator('nav.steps [data-step]').count(), 3);
    await action('#add-source summary');
    await action('#source-path-form [name=path]', 'fill', 'results.csv');
    await action('#source-path-form button');
    await action('#source-form [name=name]', 'fill', 'results');
    await action('#source-advice-show');
    assert.equal(await page.locator('#source-advice input:checked').count(), 0);
    await action('#source-advice input[type=radio][value="0"]', 'check');
    await action('#source-advice button');
    assert.equal(await page.locator('#column-types select[data-column=model]').inputValue(), 'string');
    assert.deepEqual(await page.locator('#column-types input:checked').evaluateAll((items) => items.map((item) => item.dataset.column)), ['model', 'split', 'seed']);
    await action('#source-form button[type=submit]');
    await action('nav [data-step=batch]');
    for (const column of expected.request.fields) await action(`#batch-fields input[data-column="${column}"]`, 'check');
    await action('#batch-groups input[data-column=model]', 'check');
    await action('#batch-filters [data-column=split] input[type=checkbox]', 'check');
    await action('#batch-filters [data-column=split] input[type=text]', 'fill', 'test');
    await action('#batch-form [name=reduce]', 'selectOption', 'mean');
    await action('#batch-form [name=expected_count]', 'fill', '3');
    await action('#batch-form [name=expected_seeds]', 'fill', '1\n2\n3');
    let savedDefinition, reusedCatalog = false, reuseStart, reuseActions;
    if (definitionsMode) {
      await action('#experiment-aliases summary');
      for (const [index, [value, label]] of [['001', 'Ours'], ['1', 'Baseline']].entries()) {
        await action('#experiment-alias-add');
        for (const [key, input] of Object.entries({ column: 'model', value, label, rationale: 'The experiment log explicitly identifies this model label.' })) await action(`#experiment-alias-rows .alias-row:nth-child(${index + 1}) input[data-alias-field=${key}]`, 'fill', input);
      }
      await action('#language', 'selectOption', language === 'en' ? 'zh-CN' : 'en');
      assert.equal(await page.locator('#experiment-alias-rows .alias-row:first-child input[data-alias-field=value]').inputValue(), '001');
      await action('#language', 'selectOption', language);
      await action('#experiment-definitions summary');
      await action('#experiment-definition-form [name=name]', 'fill', 'reviewed_test_results');
      await action('#experiment-definition-form [name=rationale]', 'fill', 'Reviewed four fraction metrics, test split, mean over seeds 1–3, and each explicit model label.');
      await action('#experiment-definition-form button');
      assert(!fs.existsSync(path.join(directory, '.paperdelta', 'experiments')));
      assert(await page.locator('#experiment-definition-save').isDisabled());
      await action('#experiment-definition-attest', 'check'); await action('#experiment-definition-save');
      savedDefinition = await page.locator('#experiment-definition-select').inputValue();
      assert(savedDefinition.startsWith('sha256:'));
      const saved = JSON.parse(fs.readFileSync(path.join(directory, '.paperdelta', 'experiments', savedDefinition.slice(7) + '.json'), 'utf8'));
      assert.equal(saved.request.aliases[0].value, '001'); assert.equal(saved.request.aliases[1].value, '1');
      await action('#batch-form [name=unit]', 'selectOption', 'scalar');
      assert(await page.locator('#experiment-reference').isHidden());
      if (reuseMode) reuseStart = actions.length;
      if (reuseMode && await page.locator('#experiment-definition-review').count()) {
        await action('#experiment-definition-review'); reusedCatalog = true;
      } else await action('#experiment-definition-load');
      assert.equal(await page.locator('#batch-form [name=unit]').inputValue(), 'fraction');
      assert((await page.locator('#experiment-reference').textContent()).includes(savedDefinition));
      assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), before);
    }
    if (!reusedCatalog) await action('#batch-form button[type=submit]');
    await action('#batch-joint-toggle', 'check');
    if (reuseMode) reuseActions = actions.slice(reuseStart);
    assert.equal(await page.locator('#batch-joint input:checked').count(), 0);
    for (let index = 0; index < expected.targets.length; index++) {
      const target = expected.targets[index];
      if (index === 20) await action('#batch-joint-pages button:last-child');
      const card = `.joint-choice[data-choice="${target.choice_id}"]`;
      assert((await page.locator(card).textContent()).includes(target.model));
      assert((await page.locator(card).textContent()).includes(target.field));
      assert(await page.locator(card + ' details[open] table').first().isVisible());
      const candidateSelector = definitionsMode ? `${card} input[data-joint-candidate]` : `${card} input[data-joint-candidate="${target.candidate_id}"]`;
      if (definitionsMode) {
        assert.equal(await page.locator(candidateSelector).count(), 1);
        if (['001', '1'].includes(target.model)) assert((await page.locator(card + ' .candidate').textContent()).includes(target.model === '001' ? 'Ours' : 'Baseline'));
      }
      await action(candidateSelector, 'check');
      if (index === 1) {
        await page.locator(card).screenshot({ path: path.join(out, name + '-joint.png') });
        await action('#language', 'selectOption', language === 'en' ? 'zh-CN' : 'en');
        assert(await page.locator(candidateSelector).isChecked());
        assert.equal(await page.locator('#batch-form [name=expected_seeds]').inputValue(), '1\n2\n3');
        await action('#language', 'selectOption', language);
        await page.setViewportSize({ width: 390, height: 844 });
        await page.locator(card).scrollIntoViewIfNeeded();
        assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
        await page.locator(card).screenshot({ path: path.join(out, name + '-mobile.png') });
        await page.setViewportSize({ width: 1440, height: 1000 });
      }
    }
    assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), before);
    await action('#batch-rationale', 'fill', 'Reviewed explicit model and result column, test split, fraction unit, mean of seeds 1–3, and each original position.');
    await action('#batch-stage'); await action('#preview');
    assert.equal(await page.locator('#review-items input:checked').count(), 0);
    assert.equal(await page.locator('#review-items input[type=checkbox]').count(), 24);
    await action('#select-reviewed');
    assert.equal(await page.locator('#review-items input:checked').count(), 24);
    await action('#attest', 'check'); await action('#accept');
    const report = JSON.parse(execFileSync(python, ['-X', 'utf8', '-m', 'paperdelta', '-C', directory, 'check', '--format', 'json'], { cwd: root, encoding: 'utf8', windowsHide: true }));
    assert.equal(report.coverage.pass, 24); assert.equal(report.coverage.confirmed, 24);
    if (!definitionsMode) assert(actions.length <= 60, 'Non-no-op actions: ' + actions.length);
    if (definitionsMode) {
      const reviews = path.join(directory, '.paperdelta', 'binding-reviews');
      const record = JSON.parse(fs.readFileSync(path.join(reviews, fs.readdirSync(reviews)[0]), 'utf8'));
      assert.equal(record.config_after_sha256, 'sha256:' + digest(path.join(directory, 'paperdelta.yaml')));
      assert.equal(Object.keys(record.rationale).length, 24);
      assert(Object.values(record.rationale).every(value => value.includes(savedDefinition)));
    }
    for (const [file, hash] of Object.entries(inputs)) assert.equal(digest(path.join(directory, file)), hash);
    assert.deepEqual(errors, []); assert.deepEqual(remote, []);
    results.push({ name, status: 'passed', version, input_sha256: inputs, non_no_op_actions: actions.length, actions, checked_metrics: 24, explicit_positions: 24, language_switch_preserves_fields: true, manuscripts_and_data_unchanged: true, ...(savedDefinition ? { reviewed_shared_definition: savedDefinition } : {}), ...(reuseMode ? {reuse_actions: reuseActions, reuse_action_count: reuseActions.length} : {}), errors, remote });
  } finally {
    fs.writeFileSync(path.join(out, name + '-actions.json'), JSON.stringify(actions, null, 2) + '\n');
    await context.close(); child.kill();
  }
}
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  try {
    for (const kind of definitionsMode ? ['tex'] : ['tex', 'docx', 'pdf']) for (const language of ['en', 'zh-CN']) await runCase(browser, kind, language);
    fs.writeFileSync(path.join(out, 'evidence.json'), JSON.stringify({ status: 'passed', scope: 'Developer-operated browser action count, not a human usability study. Same unchanged fixture; equal values never establish identity.', cases: results }, null, 2) + '\n');
    console.log(JSON.stringify({ status: 'passed', cases: results.map(({ name, non_no_op_actions }) => ({ name, non_no_op_actions })) }));
  } finally { await browser.close(); }
})().catch((error) => { fs.writeFileSync(path.join(out, 'failure.json'), JSON.stringify({ message: String(error), completed: results }, null, 2)); console.error(error); process.exitCode = 1; });
