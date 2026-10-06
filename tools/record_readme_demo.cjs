// Record real local reports, with a separate presentation frame and paced captions.
// Requires Node Playwright and an installed PaperDelta Python environment.
// node tools/record_readme_demo.cjs build/readme-demo
// Then: python tools/encode_readme_demo.py build/readme-demo docs/assets/v1.3
const { chromium } = require(process.env.PAPERDELTA_PLAYWRIGHT || 'playwright');
const { execFileSync } = require('node:child_process');
const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const assert = require('node:assert/strict');

const copy = {
  en: {
    label: 'FROM EXPERIMENT TO PAPER', source: 'Actual local report · guided demo',
    steps: ['Before', 'Data changes', 'Evidence', 'Table', 'Claim', 'Stale PDF', 'Try it'],
    titles: ['Your paper matches the experiment.', 'The data changes. Your paper hasn’t.',
      'Follow the number back to its evidence.', 'The table repeats the old result.',
      'The conclusion needs review, too.', 'Updated source. Outdated PDF.',
      'One result changes. See what needs review.'],
    subtitles: ['7 declared checks agree with the supplied evidence.',
      '4 numeric references, 1 comparison and 1 figure now need attention.',
      'The abstract says 84.1%. Three selected CSV rows now average 80.9%.',
      'The same accepted metric also identifies the table entry that needs attention.',
      '80.9% no longer beats the 81.0% baseline. Review this before numeric edits.',
      'A second bundled example compares a corrected source with its stale PDF export.',
      'Run the bundled example and explore the report in your browser.'],
    metric: 'ACCURACY', unchanged: 'LaTeX unchanged', baseline: 'Before the change', stale: 'PDF unchanged',
    footer: 'Local · offline · no model key', file: 'review/report.html',
  },
  'zh-CN': {
    label: '从实验结果到论文表述', source: '实际本地报告 · 引导演示',
    steps: ['原始结果', '数据变化', '证据', '表格', '结论', '旧 PDF', '试用'],
    titles: ['论文与实验结果，原本一致。', '数据变了，论文还停在上一轮。',
      '从旧数字，追溯到真实来源。', '表格中，也保留着旧结果。',
      '需要复核的，还有比较结论。', '源码已更新，PDF 还停在上一轮。',
      '一个结果变化，看清哪些位置受影响。'],
    subtitles: ['7 项已声明检查与给定证据一致。',
      '4 处数值、1 项比较结论和 1 幅图表需要复核。',
      '摘要仍写着 84.1%，选中的三条 CSV 记录均值已是 80.9%。',
      '同一个已确认指标，也指向表格中需要复核的原始单元格。',
      '80.9% 不再优于 81.0% 的基线，关联数值修改需先等待结论复核。',
      '第二个内置示例，将已修正的源码与过时的 PDF 导出稿对照。',
      '运行自带示例，在浏览器中展开证据、查看完整报告。'],
    metric: '准确率', unchanged: 'LaTeX 未改动', baseline: '数据变化前', stale: 'PDF 未更新',
    footer: '本地运行 · 离线报告 · 无需模型密钥', file: 'review/report.html',
  },
};

const shell = `<!doctype html><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;width:960px;height:768px;padding:24px 28px;
background:#e9f2ef;color:#173f46;font-family:"Segoe UI","Microsoft YaHei",sans-serif}
.eyebrow{display:flex;justify-content:space-between;align-items:center;height:24px;font-size:11px;
letter-spacing:1.6px;font-weight:700}.brand{display:flex;gap:9px;align-items:center}
.brand img{width:28px;height:28px}.source{font-weight:400;letter-spacing:0;color:#55716f}
h1{font-size:30px;line-height:1.3;letter-spacing:-.6px;margin:15px 0 7px}
.subtitle{font-size:15px;margin:0;color:#466563;line-height:1.5}
.window{position:absolute;left:28px;right:28px;top:146px;height:535px;border:1px solid #b6ccc7;
border-radius:12px;overflow:hidden;box-shadow:0 12px 25px #204d4015;background:#f5f7f8}
.bar{height:35px;padding:0 15px;display:flex;align-items:center;gap:7px;background:#fff;
border-bottom:1px solid #dce6e1;font-size:11px;color:#61716b}.dot{width:7px;height:7px;border-radius:50%;
background:#c4d3ce}.address{margin-left:11px}.metric{margin-left:auto;display:flex;align-items:center;gap:9px;
font-size:12px;color:#52756b}.metric strong{font-size:15px;color:#174b40}.metric.changed strong{color:#9b4438}
#report{width:902px;height:499px;display:block;object-fit:cover;object-position:top}
.bottom{position:absolute;left:28px;right:28px;top:697px;display:flex;align-items:center;
justify-content:space-between;gap:14px}.steps{display:flex;gap:12px}.step{display:flex;align-items:center;
gap:5px;font-size:11px;color:#718880}.step b{border:1px solid #b3c9c0;border-radius:50%;width:20px;height:20px;
display:grid;place-items:center;font-size:10px;font-weight:600}.step.active{color:#135a46;font-weight:700}
.step.active b{background:#1d7760;color:#fff;border-color:#1d7760}.foot{font-size:11px;color:#52756b}
.command{font:15px Consolas,"SFMono-Regular",monospace;color:#e5f9ee;background:#153f3e;
padding:14px 20px;border-radius:8px;width:100%;margin:0}.command span{color:#97d5be}
.progress{position:absolute;bottom:0;left:0;right:0;height:4px;background:#cedfd6}
.progress i{display:block;height:100%;background:#268569;width:20%}
</style><div class="eyebrow"><div class="brand"><img id="mark"><span id="label"></span></div>
<span id="source" class="source"></span></div><h1 id="title"></h1><p id="subtitle" class="subtitle"></p>
<div class="window"><div class="bar"><i class="dot"></i><i class="dot"></i><i class="dot"></i>
<span class="address"></span><span class="metric"><span id="metric-label"></span><strong id="value"></strong>
<span id="file-state"></span></span></div><img id="report" alt=""></div>
<div class="bottom"><div class="steps"></div><span class="foot"></span></div>
<div class="progress"><i></i></div>`;

(async () => {
  const root = path.resolve(__dirname, '..');
  const output = path.resolve(process.argv[2] || 'build/readme-demo');
  const relative = path.relative(root, output);
  assert(relative && !relative.startsWith('..') && !path.isAbsolute(relative), 'Keep output in this checkout');
  await fs.mkdir(output, { recursive: false });
  const project = path.join(output, 'project');
  execFileSync(process.env.PAPERDELTA_PYTHON || 'python', ['-X', 'utf8', '-m', 'paperdelta',
    '-C', root, 'demo', '--out', path.relative(root, project), '--format', 'json'], { cwd: root });
  const read = name => fs.readFile(path.join(project, name, 'report.json'), 'utf8').then(JSON.parse);
  const before = await read('before'), after = await read('review');
  const pdfProject = path.join(output, 'pdf-project');
  execFileSync(process.env.PAPERDELTA_PYTHON || 'python', ['-X', 'utf8', '-m', 'paperdelta',
    '-C', root, 'demo', '--document', 'pdf', '--out', path.relative(root, pdfProject), '--format', 'json'], {cwd:root,windowsHide:true});
  const pdfReport = JSON.parse(await fs.readFile(path.join(pdfProject, 'review/report.json'), 'utf8'));
  assert(pdfReport.exports.some(item=>item.status==='stale'));
  assert.equal(before.coverage.pass, 7);
  assert.equal(after.coverage.mismatch, 6);
  assert.equal(before.metrics.ours.value, '0.841');
  assert.equal(after.metrics.ours.value, '0.809');
  const paperHashes = report => Object.fromEntries(Object.entries(report.input_hashes)
    .filter(([name]) => name.endsWith('.tex')));
  assert(Object.keys(paperHashes(before)).length > 0);
  assert.deepEqual(paperHashes(before), paperHashes(after), 'Only data may change in this story');
  const errors = [], requests = [], records = [];
  const browser = await chromium.launch({ executablePath: process.env.PAPERDELTA_BROWSER_EXECUTABLE || undefined,
    headless: true });
  try {
    for (const [language, words] of Object.entries(copy)) {
      const directory = path.join(output, language);
      await fs.mkdir(directory);
      const context = await browser.newContext({ viewport: { width: 902, height: 499 }, deviceScaleFactor: 1 });
      const report = await context.newPage();
      const stage = await context.newPage();
      await stage.setViewportSize({ width: 960, height: 768 });
      for (const page of [report, stage]) {
        page.on('pageerror', error => errors.push(error.message));
        page.on('request', request => { if (/^https?:/.test(request.url())) requests.push(request.url()); });
      }
      const html = path.join(directory, 'stage.html');
      await fs.writeFile(html, shell);
      await stage.goto(pathToFileURL(html).href);
      await stage.evaluate(({ words, mark, language }) => {
        document.documentElement.lang = language;
        document.querySelector('#mark').src = mark;
        for (const key of ['label', 'source']) document.getElementById(key).textContent = words[key];
        document.querySelector('.address').textContent = words.file;
        document.querySelector('#metric-label').textContent = words.metric;
        document.querySelector('.foot').textContent = words.footer;
        words.steps.forEach((text, index) => {
          const span = document.createElement('span'); span.className = 'step';
          const number = document.createElement('b'); number.textContent = index + 1;
          span.append(number, document.createTextNode(text)); document.querySelector('.steps').append(span);
        });
      }, { words, language, mark: pathToFileURL(path.join(root, 'docs/assets/brand/paperdelta-mark.svg')).href });
      await stage.evaluate(() => Promise.all([document.fonts.ready, document.querySelector('#mark').decode()]));
      const frames = [];
      const capture = async (step, duration, final = false) => {
        const png = await report.screenshot();
        await stage.evaluate(async ({ words, step, image, final, language }) => {
          document.querySelector('#title').textContent = words.titles[step];
          document.querySelector('#subtitle').textContent = words.subtitles[step];
          document.querySelector('#value').textContent = step === 0 ? '84.1%' : '84.1% → 80.9%';
          document.querySelector('#file-state').textContent = step === 0 ? words.baseline : step >= 5 ? words.stale : words.unchanged;
          document.querySelector('.metric').classList.toggle('changed', step > 0);
          document.querySelector('.address').textContent = step === 0 ? 'before/report.html' : words.file;
          document.querySelectorAll('.step').forEach((node, index) => node.classList.toggle('active', index === step));
          document.querySelector('.progress i').style.width = `${(step + 1) * 100 / words.steps.length}%`;
          const picture = document.querySelector('#report'); picture.src = image; await picture.decode();
          if (final) {
            const code = document.createElement('code'); code.className = 'command';
            code.textContent = '$ uvx paperdelta ' + (language === 'zh-CN' ? '--lang zh-CN ' : '')
              + 'demo --out paperdelta-demo --open';
            document.querySelector('.bottom').replaceChildren(code);
          }
          await document.fonts.ready;
        }, { words, step, image: 'data:image/png;base64,' + png.toString('base64'), final, language });
        const file = `${String(frames.length).padStart(3, '0')}.png`;
        await stage.screenshot({ path: path.join(directory, file) });
        frames.push({ file, duration, step: step + 1 });
      };
      const open = async name => {
        await report.goto(pathToFileURL(path.join(project, name, 'report.html')).href);
        await report.selectOption('#language', language);
        await report.evaluate(() => document.fonts.ready);
      };
      const scrollTo = async (locator, offset = 14) => {
        await locator.evaluate((node, offset) => window.scrollTo(0, node.getBoundingClientRect().top + scrollY - offset), offset);
      };
      await open('before');
      await capture(0, 2700);
      await open('review');
      assert.equal(await report.locator('#findings article').count(), 6);
      await capture(1, 3200);
      await report.selectOption('#file', 'paper/abstract.tex');
      const numeric = report.locator('#findings article:visible');
      assert.equal(await numeric.count(), 1);
      await scrollTo(numeric);
      await capture(2, 1600);
      await numeric.locator('details summary').click();
      const table = numeric.locator('table');
      assert.equal(await table.locator('tbody tr').count(), 3);
      assert((await numeric.textContent()).includes('80.9'));
      const start = await report.evaluate(() => scrollY);
      const end = await table.evaluate(node => Math.max(0, node.getBoundingClientRect().bottom + scrollY - innerHeight + 25));
      for (let frame = 1; frame <= 10; frame++) {
        const t = frame / 10, ease = t * t * (3 - 2 * t);
        await report.evaluate(y => scrollTo(0, y), start + (end - start) * ease);
        await capture(2, frame === 10 ? 3600 : 70);
      }
      await report.selectOption('#file', 'paper/results.tex');
      await report.selectOption('#rule', 'VALUE_MISMATCH');
      const tableResult = report.locator('#findings article:visible').filter({hasText:'84.1'});
      assert.equal(await tableResult.count(), 1);
      await scrollTo(tableResult);
      await capture(3, 3000);
      await report.selectOption('#file', '');
      await report.selectOption('#rule', 'CLAIM_FALSE');
      const claim = report.locator('#findings article:visible');
      assert.equal(await claim.count(), 1);
      assert((await claim.textContent()).includes('81.0') || (await claim.textContent()).includes('0.810'));
      await scrollTo(claim);
      await capture(4, 3800);
      await report.goto(pathToFileURL(path.join(pdfProject, 'review/report.html')).href);
      await report.selectOption('#language', language);
      await scrollTo(report.locator('#exports'));
      assert((await report.locator('#exports').textContent()).includes('source.tex'));
      await capture(5, 4200);
      await capture(6, 4200, true);
      await fs.writeFile(path.join(directory, 'frames.json'), JSON.stringify({ language, size: [960, 768], frames }, null, 2) + '\n');
      records.push({ language, frames: frames.length, duration_ms: frames.reduce((total, item) => total + item.duration, 0),
        numeric_source_rows: 3, findings: 6, stale_pdf_example:true });
      await context.close();
    }
    assert.deepEqual(errors, []);
    assert.deepEqual(requests, []);
    await fs.writeFile(path.join(output, 'recording.json'), JSON.stringify({
      browser: browser.version(), paperdelta: before.tool_version, records, paper_unchanged: true,
      external_requests: requests, errors, scope: 'Real generated reports and interactions; captions and playback timing are presentation annotations.',
    }, null, 2) + '\n');
    console.log(JSON.stringify({ output, records, paper_unchanged: true, errors }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
