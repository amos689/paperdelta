// Optional live-report QA against generated local files; no network or model calls.
const { chromium } = require(process.env.PAPERDELTA_PLAYWRIGHT || 'playwright');
const { spawn } = require('node:child_process');
const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const fixture = String.raw`
import json, sys, time
from pathlib import Path
from paperdelta.demo import create_demo
from paperdelta.storage import Project
from paperdelta.watch import Watcher
root=Path(sys.argv[1])
create_demo(Project(root), "project")
project=Project(root/"project")
watcher=Watcher(project, directory="live", baseline="before", debounce=0.5)
def emit(report):
    print(json.dumps({"state":report["watch"]["state"], "generation":report["watch"]["generation"], "exit_code":report["exit_code"]}), flush=True)
emit(watcher.step())
for command in sys.stdin:
    command=command.strip()
    if command=="change":
        rows=project.read("results/metrics.csv").splitlines(keepends=True)
        for index,(old,new) in enumerate([(b"0.807",b"0.843"),(b"0.809",b"0.845"),(b"0.811",b"0.847")],start=1):
            rows[index]=rows[index].replace(old,new)
        project.write("results/metrics.csv",b"".join(rows))
        watcher.step()
        emit(watcher.previous)
    elif command=="settle":
        emit(watcher.step(time.monotonic()+1))
    elif command=="stop":
        emit(watcher.stop())
        break
`;

(async () => {
  const output = path.resolve(process.argv[2] || 'build/watch-browser-qa');
  await fs.mkdir(output, { recursive: true });
  const worker = spawn(process.env.PAPERDELTA_PYTHON || 'python', ['-X', 'utf8', '-c', fixture, output], { stdio: ['pipe', 'pipe', 'pipe'] });
  let pending = '', errors = '';
  const queue = [], listeners = [];
  worker.stderr.on('data', data => { errors += data; });
  worker.stdout.on('data', data => {
    pending += data;
    while (pending.includes('\n')) {
      const index = pending.indexOf('\n');
      const event = JSON.parse(pending.slice(0, index));
      pending = pending.slice(index + 1);
      if (listeners.length) listeners.shift()(event); else queue.push(event);
    }
  });
  const next = () => new Promise((resolve, reject) => {
    if (queue.length) { resolve(queue.shift()); return; }
    const timeout = setTimeout(() => reject(new Error(`Fixture timeout: ${errors}`)), 15000);
    listeners.push(value => { clearTimeout(timeout); resolve(value); });
  });
  const send = async command => { worker.stdin.write(command + '\n'); return next(); };
  let browser;
  try {
    const initial = await next();
    if (initial.state !== 'running' || initial.generation !== 1) throw new Error('Initial watch failed');
    browser = await chromium.launch({ executablePath: process.env.PAPERDELTA_BROWSER_EXECUTABLE || undefined, headless: true });
    const page = await browser.newPage({ viewport: { width: 1365, height: 1000 } });
    const browserErrors = [], network = [];
    page.on('pageerror', error => browserErrors.push(error.message));
    page.on('request', request => { if (/^https?:/.test(request.url())) network.push(request.url()); });
    await page.goto(pathToFileURL(path.join(output, 'project/live/report.html')).href);
    await page.selectOption('#language', 'zh-CN');
    await page.selectOption('#file', 'paper/abstract.tex');
    await page.selectOption('#rule', 'VALUE_MISMATCH');
    const card = page.locator('#findings article:visible');
    await card.locator('summary').click();
    await page.locator('#language').focus();
    const pendingEvent = await send('change');
    if (pendingEvent.state !== 'pending' || pendingEvent.exit_code !== 2) throw new Error('Stale success during pending check');
    await page.reload();
    if (!(await page.locator('#watch-status').textContent()).includes('等待')) throw new Error('Missing pending banner');
    await page.screenshot({ path: path.join(output, 'pending.zh-CN.png') });
    const settled = await send('settle');
    if (settled.state !== 'running' || settled.generation !== 2) throw new Error('Second check failed');
    // Wait for the report's own refresh, not an explicit Playwright reload.
    await page.waitForFunction(() => {
      const shown = [...document.querySelectorAll('#findings article')].find(node => !node.hidden);
      return shown && shown.textContent.includes('84.5');
    }, null, { timeout: 10000 });
    if (await page.locator('html').getAttribute('lang') !== 'zh-CN') throw new Error('Lost language');
    if (await page.inputValue('#file') !== 'paper/abstract.tex' || await page.inputValue('#rule') !== 'VALUE_MISMATCH') throw new Error('Lost filters');
    if (!await card.locator('details').evaluate(node => node.open)) throw new Error('Lost disclosure');
    if (await page.evaluate(() => document.activeElement.id) !== 'language') throw new Error('Lost focus');
    if (await card.count() !== 1 || !(await card.textContent()).includes('84.5')) throw new Error('Stale report content');
    await page.locator('#review-actions [data-finding-link]').first().click();
    if (await page.locator('#findings article:visible').count() !== 5) throw new Error('Queue navigation failed');
    const stopped = await send('stop');
    if (stopped.state !== 'stopped') throw new Error('Stop failed');
    await page.reload();
    if (await page.locator('meta[http-equiv="refresh"]').count()) throw new Error('Stopped report still refreshing');
    await page.screenshot({ path: path.join(output, 'stopped.zh-CN.png') });
    if (browserErrors.length || network.length) throw new Error(JSON.stringify({ browserErrors, network }));
    const result = { checked_at: new Date().toISOString(), browser: await browser.version(), pending_exit_code: 2,
      automatic_refresh_uses_new_values: true, retains_language_filters_disclosure_focus: true,
      queue_navigation: true, stopped_report_is_static: true, external_requests: network, errors: browserErrors,
      scope: 'Local Chrome report behavior; deterministic watcher driver, not a human trial.' };
    await fs.writeFile(path.join(output, 'evidence.json'), JSON.stringify(result, null, 2) + '\n');
    process.stdout.write(JSON.stringify(result));
  } finally { worker.kill(); if (browser) await browser.close(); }
})().catch(error => { process.stderr.write(String(error)); process.exitCode = 1; });
