/* Real browser workflows and optional comparison with the published 0.6 runtime. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn, execFileSync } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || path.join(root, 'build', 'batch-browser-' + Date.now()));
assert(out.startsWith(path.join(root, 'build') + path.sep) && !fs.existsSync(out));
fs.mkdirSync(out, { recursive: true });
const results = [], effort = [], actions = [];
let countActions = false;
function fixture(directory, kind, provider) {
  const args = ['-X', 'utf8', 'tools/studio_batch_fixture.py', '--out', path.relative(root, directory), '--document', kind];
  if (provider) args.push('--proposal', provider);
  return JSON.parse(execFileSync(python, args, { cwd: root, encoding: 'utf8', windowsHide: true }));
}
function hash(file) { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }
async function start(directory, lang, runtime) {
  const child = spawn(python, ['-X', 'utf8', '-m', 'paperdelta', '--lang', lang, '-C', directory, 'studio', '--no-open'], {
    cwd: root, windowsHide: true, env: { ...process.env, ...(runtime ? { PYTHONPATH: runtime } : {}) },
  });
  let output = '';
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { child.kill(); reject(new Error('Studio startup timed out: ' + output)); }, 45000);
    child.stdout.on('data', (data) => { output += data; const match = output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/); if (match) { clearTimeout(timer); resolve(match[0]); } });
    child.stderr.on('data', (data) => { output += data; });
    child.on('exit', (code) => { clearTimeout(timer); reject(new Error('Studio exited: ' + code + ' ' + output)); });
  });
  return { child, url };
}
async function ready(page) {
  await page.waitForFunction(() => !document.body.hasAttribute('aria-busy'));
  if (await page.locator('#error').isVisible()) throw new Error(await page.locator('#error').textContent());
}
async function action(page, selector, method = 'click', value) {
  if (countActions) {
    const control = page.locator(selector);
    if (method === 'check' && await control.isChecked()) return;
    if (['fill', 'selectOption'].includes(method) && await control.inputValue() === value) return;
  }
  if (countActions) actions.push({ control: selector, action: method, ...(value === undefined ? {} : { value }) });
  await page.locator(selector)[method](value); await ready(page);
}
async function source(page, annotation) {
  await action(page, '#add-source summary');
  await action(page, '#source-path-form [name=path]', 'fill', 'results.csv');
  await action(page, '#source-path-form button');
  await action(page, '#source-form [name=name]', 'fill', 'results');
  for (const key of ['model', 'split', 'seed']) await action(page, `#column-types input[data-column="${key}"]`, 'check');
  for (const [key, kind] of Object.entries(annotation.source)) if (kind !== 'string') await action(page, `#column-types select[data-column="${key}"]`, 'selectOption', kind);
  await action(page, '#source-form button[type=submit]');
}
async function configureBatch(page, annotation) {
  await action(page, 'nav [data-step=batch]');
  for (const field of annotation.request.fields) await action(page, `#batch-fields input[data-column="${field}"]`, 'check');
  await action(page, '#batch-groups input[data-column=model]', 'check');
  await action(page, '#batch-filters [data-column=split] input[type=checkbox]', 'check');
  await action(page, '#batch-filters [data-column=split] input[type=text]', 'fill', 'test');
  await action(page, '#batch-form [name=reduce]', 'selectOption', 'mean');
  await action(page, '#batch-form [name=expected_count]', 'fill', '3');
  await action(page, '#batch-form [name=expected_seeds]', 'fill', '1\n2\n3');
  await action(page, '#batch-form button[type=submit]');
  await page.locator('.batch-choice').first().waitFor();
  assert.equal(await page.locator('#batch-locations input:checked').count(), 0);
}
async function chooseBatch(page, annotation, languageCheck = false, onChoice = async () => {}) {
  for (let index = 0; index < annotation.targets.length; index++) {
    const target = annotation.targets[index];
    if (index === 20) await action(page, '#batch-choice-pages button:last-child');
    await action(page, `.batch-choice[data-choice="${target.choice_id}"] button`);
    await action(page, `#batch-locations input[data-batch-candidate="${target.candidate_id}"]`, 'check');
    await onChoice(index);
    if (languageCheck && index === 1) {
      const lang = await page.locator('#language').inputValue();
      await action(page, '#language', 'selectOption', lang === 'en' ? 'zh-CN' : 'en');
      assert(await page.locator(`#batch-locations input[data-batch-candidate="${target.candidate_id}"]`).isChecked());
      assert(await page.locator('#batch-fields input[data-column=accuracy]').isChecked());
      assert.equal(await page.locator('#batch-form [name=expected_seeds]').inputValue(), '1\n2\n3');
      await action(page, '#language', 'selectOption', lang);
    }
  }
  await action(page, '#batch-rationale', 'fill', 'Each selected result cell uses its explicit model, result column, test split and seeds 1–3.');
  await action(page, '#batch-stage');
  await action(page, '#preview');
}
async function acceptSubset(page, size) {
  const boxes = page.locator('#review-items input[type=checkbox]');
  assert.equal(await boxes.filter({ visible: true }).count(), await boxes.count());
  assert.equal(await page.locator('#review-items input:checked').count(), 0);
  for (let index = 0; index < size; index++) {
    const binding = await boxes.nth(index).getAttribute('data-binding');
    await action(page, `#review-items input[data-binding="${binding}"]`, 'check');
  }
  await action(page, '#attest', 'check'); await action(page, '#accept');
  assert(await page.locator('#receipt').isVisible());
}
function checkedProject(directory, expected) {
  const report = JSON.parse(execFileSync(python, ['-X', 'utf8', '-m', 'paperdelta', '-C', directory, 'check', '--format', 'json'], { cwd: root, encoding: 'utf8', windowsHide: true }));
  assert.equal(report.coverage.pass, expected); assert.equal(report.coverage.confirmed, expected);
  return report;
}
async function runCase(browser, kind, language, performanceOnly = false, baselineRuntime) {
  const name = performanceOnly ? (baselineRuntime ? 'effort-v06' : 'effort-current') : `${kind}-${language}`;
  const directory = path.join(out, name); fixture(directory, kind);
  const annotation = JSON.parse(fs.readFileSync(path.join(directory, 'browser-annotations.json'), 'utf8'));
  const inputs = Object.fromEntries(['paper.' + kind, 'results.csv'].map((file) => [file, hash(path.join(directory, file))]));
  const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, acceptDownloads: true });
  const page = await context.newPage(), errors = [], remote = [];
  page.setDefaultTimeout(45000);
  const { child, url } = await start(directory, language, baselineRuntime);
  page.on('pageerror', (error) => errors.push(String(error)));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('request', (request) => { if (!request.url().startsWith(new URL(url).origin) && !request.url().startsWith('blob:') && !request.url().startsWith('data:')) remote.push(request.url()); });
  const frames = [];
  async function capture(step, selector, duration = 4000) {
    if (!process.argv.includes('--record') || performanceOnly || kind !== 'tex') return;
    const directory = path.join(out, 'recording', language); fs.mkdirSync(directory, { recursive: true });
    await page.setViewportSize({ width: 1100, height: 820 });
    await page.locator(selector).first().scrollIntoViewIfNeeded();
    const file = String(frames.length).padStart(3, '0') + '.png';
    await page.screenshot({ path: path.join(directory, file) });
    frames.push({ file, duration, step });
    fs.writeFileSync(path.join(directory, 'frames.json'), JSON.stringify({ size: [1100, 820], source: 'Actual Studio batch workflow. Screen holds are paced for reading; no speed claim.', frames }, null, 2) + '\n');
    await page.setViewportSize({ width: 1440, height: 1050 });
  }
  try {
    await page.goto(url); await page.locator('#workspace').waitFor({ state: 'visible' }); await ready(page);
    const version = await page.locator('#version').textContent();
    const currentVersion = fs.readFileSync(path.join(root, 'pyproject.toml'), 'utf8').match(/^version = "([^"]+)"/m)[1];
    assert.equal(version, baselineRuntime ? '0.6.0' : currentVersion);
    countActions = performanceOnly; actions.length = 0;
    await source(page, annotation);
    if (baselineRuntime) {
      for (let index = 0; index < annotation.targets.length; index++) {
        const target = annotation.targets[index];
        await action(page, 'nav [data-step=evidence]');
        if ((await page.locator('#add-metric').getAttribute('open')) === null) await action(page, '#add-metric > summary');
        if ((await page.locator('#metric-form [name=source]').inputValue()) !== 'results') await action(page, '#metric-form [name=source]', 'selectOption', 'results');
        await action(page, '#metric-form [name=name]', 'fill', 'metric_' + index);
        await action(page, '#metric-form [name=field]', 'fill', target.field);
        for (const [column, value] of [['model', target.model], ['split', 'test']]) {
          await action(page, `#selectors input[type=checkbox][data-column="${column}"]`, 'check');
          await action(page, `#selectors .selector-row:has(input[data-column="${column}"]) input[type=text]`, 'fill', value);
        }
        await action(page, '#metric-form [name=reduce]', 'selectOption', 'mean');
        await action(page, '#metric-form [name=expected_count]', 'fill', '3');
        const seedDetails = page.locator('#metric-form details');
        if ((await seedDetails.getAttribute('open')) === null) await action(page, '#metric-form details summary');
        await action(page, '#metric-form [name=expected_seeds]', 'fill', '1\n2\n3');
        await action(page, '#metric-form button[type=submit]');
        await action(page, 'nav [data-step=locations]');
        await action(page, `#candidates [data-candidate="${target.candidate_id}"] input`, 'check');
        await action(page, '#locations-form [name=prefix]', 'fill', 'result_' + index);
        await action(page, '#locations-form [name=rationale]', 'fill', 'The explicit model and result column, test split and seeds 1–3.');
        await action(page, '#locations-form button[type=submit]');
      }
      await action(page, '#preview'); await acceptSubset(page, annotation.targets.length);
    } else {
      await configureBatch(page, annotation);
      if (!performanceOnly) {
        const before = fs.readFileSync(path.join(directory, 'paperdelta.yaml'));
        await action(page, '#batch-templates summary');
        await action(page, '#template-save-form [name=name]', 'fill', 'test_results');
        await action(page, '#template-save-form button');
        const event = page.waitForEvent('download'); await action(page, '#template-export');
        const download = await event; const file = path.join(out, name + '-template.json'); await download.saveAs(file);
        const template = JSON.parse(fs.readFileSync(file, 'utf8'));
        assert.equal(template.source_contract.columns.model, 'string'); assert.equal(template.request.unit, 'fraction');
        await action(page, '#batch-form [name=unit]', 'selectOption', 'scalar');
        await action(page, '#template-load'); assert.equal(await page.locator('#batch-form [name=unit]').inputValue(), 'fraction');
        await action(page, '#batch-form [name=unit]', 'selectOption', 'scalar');
        await page.locator('#template-file').setInputFiles(file); await ready(page);
        assert.equal(await page.locator('#batch-form [name=unit]').inputValue(), 'fraction');
        assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), before);
        await action(page, '#batch-form button[type=submit]');
        await action(page, '#batch-templates summary');
      }
      await capture('shared-experiment-identity-and-result-groups', '#batch-choices', 4000);
      await chooseBatch(page, annotation, !performanceOnly, async (index) => {
        if (index === 0) {
          assert((await page.locator(`#batch-locations article:has(input[data-batch-candidate="${annotation.targets[0].candidate_id}"])`).textContent()).includes(annotation.targets[0].field));
          await capture('inspect-selected-model-and-result-column', '#batch-choice-evidence', 5000);
          if (!performanceOnly && kind === 'pdf') {
            const candidate = page.locator(`#batch-locations article:has(input[data-batch-candidate="${annotation.targets[0].candidate_id}"])`);
            await candidate.locator('button').click(); await ready(page);
            await page.locator('#batch-native-page img').waitFor();
            const viewbox = await page.locator('#batch-native-page svg').getAttribute('viewBox');
            assert(!viewbox.includes('NaN') && !viewbox.includes('undefined'));
            assert(Number(await page.locator('#batch-native-page rect').getAttribute('width')) > 0);
            await page.locator('#batch-native-page').screenshot({ path: path.join(out, name + '-original-page.png') });
          }
        }
        if (index === annotation.targets.length - 1) await capture('explicit-selections-across-pages', '#batch-selected');
      });
      if (!performanceOnly) {
        await page.locator('#review-items').scrollIntoViewIfNeeded();
        await page.screenshot({ path: path.join(out, name + '-review.png') });
        await page.locator('#review-items .preview-card').first().screenshot({ path: path.join(out, name + '-first-binding.png') });
        await capture('review-locations-evidence-and-binding-definitions', '#review-items .preview-card', 5000);
      }
      await acceptSubset(page, performanceOnly ? annotation.targets.length : 12);
      await capture('accept-only-reviewed-subset', '#receipt');
      if (!performanceOnly) {
        checkedProject(directory, 12);
        for (const [provider, count] of [['cli', 6], ['mcp', 6]]) {
          const proposal = fixture(directory, kind, provider), before = fs.readFileSync(path.join(directory, 'paperdelta.yaml'));
          await action(page, 'nav [data-step=review]');
          await page.locator('#proposal-file').setInputFiles(path.join(directory, proposal.path)); await ready(page);
          await page.locator('#review-items input').first().waitFor();
          assert.deepEqual(fs.readFileSync(path.join(directory, 'paperdelta.yaml')), before);
          await acceptSubset(page, count);
        }
        await action(page, 'nav [data-step=batch]');
        await page.setViewportSize({ width: 390, height: 844 });
        await page.screenshot({ path: path.join(out, name + '-mobile.png'), fullPage: true });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      }
    }
    const recorded = [...actions]; countActions = false;
    checkedProject(directory, annotation.targets.length);
    for (const [file, original] of Object.entries(inputs)) assert.equal(hash(path.join(directory, file)), original);
    assert.deepEqual(errors, []); assert.deepEqual(remote, []);
    if (performanceOnly) effort.push({ version, inputs_sha256: inputs, metrics: annotation.targets.length, actions: recorded, action_count: recorded.length });
    else results.push({ document: kind, language, batch_metrics: annotation.targets.length, explicit_subset_acceptance: true, template_reuse: true, template_file_import: true, pdf_original_page_preview: kind === 'pdf' ? true : null, cli_proposal_import: true, mcp_proposal_import: true, language_preserves_choices: true, cross_page_choices: true, manuscript_and_data_unchanged: true, mobile_no_overflow: true, browser_errors: errors, remote_requests: remote });
    console.log(name + ' passed');
  } catch (error) { await page.screenshot({ path: path.join(out, name + '-failure.png'), fullPage: true }); throw error; }
  finally { await context.close(); child.kill(); }
}
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  try {
    if (!process.argv.includes('--effort-only')) {
      for (const kind of ['tex', 'docx', 'pdf']) for (const language of ['en', 'zh-CN']) await runCase(browser, kind, language);
    } else assert(process.env.PAPERDELTA_BASELINE_RUNTIME, '--effort-only requires the verified baseline runtime');
    if (process.env.PAPERDELTA_BASELINE_RUNTIME) {
      await runCase(browser, 'tex', 'en', true, process.env.PAPERDELTA_BASELINE_RUNTIME);
      await runCase(browser, 'tex', 'en', true);
      assert.deepEqual(effort[0].inputs_sha256, effort[1].inputs_sha256);
      assert(effort[1].action_count <= effort[0].action_count * 0.5, 'At least 50% fewer recorded setup interactions on identical inputs');
    }
  } finally {
    await browser.close(); fs.writeFileSync(path.join(out, 'evidence.json'), JSON.stringify({ suite: 'studio-batch', results, effort, scope: 'Recorded machine browser workflows. Actions include filling, selecting, checking and clicking; they do not measure human time or error rates.' }, null, 2) + '\n');
  }
})().catch((error) => { console.error(error); process.exitCode = 1; });
