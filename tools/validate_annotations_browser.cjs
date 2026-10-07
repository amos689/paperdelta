/* Actual bilingual preview, selection retention and native copy downloads. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawn, execFileSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..'), python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || 'build/annotations-browser-' + Date.now());
assert(out.startsWith(path.join(root, 'build') + path.sep) && !fs.existsSync(out));
fs.mkdirSync(out, {recursive: true});
const py = args => execFileSync(python, ['-X', 'utf8', ...args], {cwd: root, encoding: 'utf8', windowsHide: true});
const digest = raw => crypto.createHash('sha256').update(raw).digest('hex');
async function start(directory, language) {
  const child = spawn(python, ['-X', 'utf8', '-m', 'paperdelta', '--lang', language, '-C', directory, 'studio', '--no-open'], {cwd: root, windowsHide: true});
  let output = '';
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => {child.kill(); reject(new Error('Studio startup: ' + output));}, 45000);
    child.stdout.on('data', data => {output += data; const match = output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/); if (match) {clearTimeout(timer); resolve(match[0]);}});
    child.stderr.on('data', data => {output += data;});
    child.on('error', error => {clearTimeout(timer); reject(error);});
    child.on('exit', code => {clearTimeout(timer); reject(new Error('Studio exit ' + code + ': ' + output));});
  });
  return {child, url};
}
async function runCase(browser, format, language) {
  const name = format + '-' + language, directory = path.join(out, name);
  py(['-m', 'paperdelta', '-C', out, 'demo', '--document', format, '--out', name]);
  const report = JSON.parse(fs.readFileSync(path.join(directory, 'review/report.json'), 'utf8'));
  const originals = Object.fromEntries(Object.keys(report.input_hashes).filter(p => fs.existsSync(path.join(directory, p))).map(p => [p, fs.readFileSync(path.join(directory, p))]));
  const server = await start(directory, language);
  const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
  const page = await context.newPage(), errors = [], remote = [], steps = [];
  page.setDefaultTimeout(45000);
  page.on('pageerror', error => errors.push(String(error)));
  page.on('request', request => {if (!request.url().startsWith(new URL(server.url).origin) && !/^(data|blob):/.test(request.url())) remote.push(request.url());});
  async function ready() {
    await page.waitForFunction(() => !document.body.hasAttribute('aria-busy'));
    if (await page.locator('#error').isVisible()) throw new Error(await page.locator('#error').textContent());
  }
  async function act(selector, method = 'click', value) {await page.locator(selector)[method](value); await ready(); steps.push({selector, method});}
  try {
    await page.goto(server.url); await page.locator('#revision-board').waitFor({state: 'visible'}); await ready();
    const version = await page.locator('#version').textContent();
    await act('#revision-search', 'fill', 'abstract_accuracy');
    assert.equal(await page.locator('[data-numeric-patch]').count(), 0);
    await act('[data-native-annotation][value=abstract_accuracy]', 'check');
    await act('#annotation-preview-button');
    assert(await page.locator('#annotation-download').isDisabled());
    assert.match(await page.locator('#annotation-entries').innerText(), /84\.1/);
    assert.match(await page.locator('#annotation-entries').innerText(), /80\.9/);
    assert.match(await page.locator('#annotation-entries').innerText(), /claim:main_comparison/);
    await act('#annotation-attest', 'check');
    await act('#language', 'selectOption', language === 'en' ? 'zh-CN' : 'en');
    assert(await page.locator('#annotation-preview').isHidden());
    assert(await page.locator('#annotation-download').isDisabled());
    assert(await page.locator('[data-native-annotation][value=abstract_accuracy]').isChecked());
    assert.equal(await page.locator('#revision-search').inputValue(), 'abstract_accuracy');
    await act('#language', 'selectOption', language);
    await act('#annotation-preview-button');
    const before = await page.locator('#review-workspace').getAttribute('data-generation');
    const data = path.join(directory, 'results/metrics.csv');
    fs.writeFileSync(data, Buffer.concat([originals['results/metrics.csv'], Buffer.from('\n')]));
    await page.waitForFunction(generation => {
      const panel = document.getElementById('review-workspace');
      return panel.dataset.generation !== generation && panel.dataset.reviewState === 'current' && !document.body.hasAttribute('aria-busy');
    }, before);
    await ready(); assert(await page.locator('#annotation-preview').isHidden());
    assert(await page.locator('[data-native-annotation][value=abstract_accuracy]').isChecked());
    await act('#annotation-preview-button');
    await page.locator('#annotation-preview').screenshot({path: path.join(out, name + '-preview.png')});
    await act('#annotation-attest', 'check');
    const downloading = page.waitForEvent('download'); await act('#annotation-download');
    const download = await downloading, archive = path.join(out, name + '.zip'); await download.saveAs(archive);
    assert(await page.locator('#annotation-preview').isHidden());
    const manifest = JSON.parse(py(['-c', 'import sys,hashlib,json; from zipfile import ZipFile; z=ZipFile(sys.argv[1]); m=json.loads(z.read("review.json")); assert all("sha256:"+hashlib.sha256(z.read(n)).hexdigest()==h for n,h in m["copies_sha256"].items()); print(json.dumps(m))', archive]));
    assert.equal(manifest.language, language); assert.equal(manifest.entries.length, 1);
    assert.equal(manifest.entries[0].occurrence, 'abstract_accuracy');
    assert(manifest.copies[0].path.endsWith('.review.' + format));
    assert(manifest.entries[0].note.includes(language === 'en' ? 'Expected display' : '预期显示'));
    for (const [file, raw] of Object.entries(originals)) {
      assert.deepEqual(fs.readFileSync(path.join(directory, file)), file === 'results/metrics.csv' ? Buffer.concat([raw, Buffer.from('\n')]) : raw);
    }
    await page.setViewportSize({width: 390, height: 844});
    await act('#annotation-preview-button');
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2));
    await page.locator('#annotation-preview').screenshot({path: path.join(out, name + '-mobile.png')});
    assert.deepEqual(errors, []); assert.deepEqual(remote, []);
    return {format, language, version, status: 'passed', source_sha256: Object.fromEntries(Object.entries(originals).map(([p,raw]) => [p, digest(raw)])),
      archive_sha256: digest(fs.readFileSync(archive)), manifest, input_change_clears_preview: true, language_retains_selection: true,
      explicit_confirmation: true, originals_unchanged: true, narrow_viewport: true, errors, remote_requests: remote, steps};
  } catch (error) {
    await page.screenshot({path: path.join(out, name + '-failure.png'), fullPage: true}).catch(() => {});
    fs.writeFileSync(path.join(out, name + '-failure.json'), JSON.stringify({error: String(error), stack: error.stack, errors, remote, steps}, null, 2) + '\n');
    throw error;
  } finally {await context.close(); if (server.child.exitCode === null) await new Promise(resolve => {server.child.once('close', resolve); server.child.kill();});}
}
(async () => {
  const browser = await chromium.launch({headless: true, ...(process.env.BROWSER_EXECUTABLE ? {executablePath: process.env.BROWSER_EXECUTABLE} : {})}), cases = [];
  try {
    for (const format of ['docx', 'pdf']) for (const language of ['en', 'zh-CN']) {
      cases.push(await runCase(browser, format, language)); process.stdout.write(format + '-' + language + ' passed\n');
    }
    fs.writeFileSync(path.join(out, 'evidence.json'), JSON.stringify({status: 'passed', cases,
      scope: 'Authored browser flows; original files are unchanged and every copy is explicitly reviewed. Not independent usability evidence.'}, null, 2) + '\n');
  } finally {await browser.close();}
})().catch(error => {console.error(error); process.exitCode = 1;});
