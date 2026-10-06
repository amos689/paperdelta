/* Real-browser acceptance. Set PAPERDELTA_PYTHON, PLAYWRIGHT_MODULE,
 * BROWSER_EXECUTABLE as needed. Run: node tools/validate_studio_browser.cjs build/out
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, execFileSync } = require("node:child_process");
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const root = path.resolve(__dirname, "..");
const python = process.env.PAPERDELTA_PYTHON || "python";
const out = path.resolve(process.argv[2] || path.join(root, "build", "studio-browser-" + Date.now()));
assert(out.startsWith(path.join(root, "build") + path.sep), "Keep new evidence inside build/");
assert(!fs.existsSync(out), "Use a new evidence directory");
fs.mkdirSync(out, { recursive: true });
const fixtureScript = [
  "import sys",
  "from pathlib import Path",
  "root=Path(sys.argv[1]); kind=sys.argv[2]",
  "root.mkdir(parents=True,exist_ok=False)",
  'paper=root/("paper."+kind)',
  'if kind=="tex":',
  '    paper.write_bytes(b"Abstract score: 84.1\\\\%.\\nSecond result: 84.1\\\\%.\\nMarkup: <img src=x onerror=alert(1)>.\\n")',
  'elif kind in {"md", "qmd"}:',
  '    paper.write_bytes(b"# Abstract\\n\\nAbstract score: **84.1%**.\\n\\n| Model | Score |\\n| --- | --- |\\n| 001 | 84.1% |\\n")',
  'elif kind=="docx":',
  "    from docx import Document",
  "    doc=Document()",
  '    doc.add_paragraph("Abstract score: 84.1%.")',
  '    doc.add_paragraph("Second result: 84.1%.")',
  '    doc.add_paragraph("Markup: <img src=x onerror=alert(1)>.")',
  "    doc.save(paper)",
  "else:",
  "    from reportlab.pdfgen.canvas import Canvas",
  "    canvas=Canvas(str(paper),invariant=True)",
  '    canvas.drawString(60,740,"Abstract score: 84.1%.")',
  '    canvas.drawString(60,700,"Second result: 84.1%.")',
  "    canvas.save()",
  '(root/"results.csv").write_bytes(b"model,split,setting,seed,score\\n001,test,0.12345678901234567890123456789,1,0.840\\n001,test,0.12345678901234567890123456789,2,0.842\\n001,train,0.12345678901234567890123456789,1,0.950\\n")',
].join("\n");
async function start(directory, lang) {
  const child = spawn(python, ["-X", "utf8", "-m", "paperdelta", "--lang", lang, "-C", directory, "studio", "--no-open"], { cwd: root, windowsHide: true });
  let output = "";
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("Server startup timeout: " + output)), 30000);
    child.stdout.on("data", (data) => { output += data.toString(); const match = output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/); if (match) { clearTimeout(timer); resolve(match[0]); } });
    child.stderr.on("data", (data) => { output += data.toString(); });
    child.on("exit", (code) => { clearTimeout(timer); reject(new Error("Server exited: " + code + " " + output)); });
  });
  return { child, url };
}
async function ready(page) {
  await page.waitForFunction(() => !document.body.hasAttribute("aria-busy"));
  if (await page.locator("#error").isVisible()) throw new Error(await page.locator("#error").textContent());
}
async function click(page, selector) { await page.locator(selector).click(); await ready(page); }
(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  const results = [];
  try {
    for (const kind of (process.env.PAPERDELTA_DOCUMENT_FORMATS || "tex,docx,pdf,md,qmd").split(',')) for (const lang of ["en", "zh-CN"]) {
      const name = kind + "-" + lang, directory = path.join(out, name);
      execFileSync(python, ["-X", "utf8", "-c", fixtureScript, directory, kind], { windowsHide: true });
      const { child, url } = await start(directory, lang);
      const context = await browser.newContext({ viewport: { width: 1440, height: 1050 }, acceptDownloads: true });
      const page = await context.newPage(), errors = [], remote = [];
      page.on("pageerror", (err) => errors.push(String(err)));
      page.on("console", (msg) => { if (msg.type() === "error") errors.push(msg.text()); });
      page.on("request", (request) => { if (!request.url().startsWith(new URL(url).origin) && !request.url().startsWith("data:") && !request.url().startsWith("blob:")) remote.push(request.url()); });
      try {
        await page.goto(url); await page.locator("#setup").waitFor({ state: "visible" }); await ready(page);
        await page.locator("#setup-form [name=paper]").fill("paper." + kind);
        await page.locator("#setup-form [name=data]").fill("results.csv");
        await click(page, "#setup-form button[type=submit]");
        const originalConfig = fs.readFileSync(path.join(directory, "paperdelta.yaml"));
        const originalPaper = fs.readFileSync(path.join(directory, "paper." + kind));
        const originalData = fs.readFileSync(path.join(directory, "results.csv"));
        await click(page, "#add-source summary");
        await page.locator("#source-path-form [name=path]").fill("results.csv");
        await click(page, "#source-path-form button");
        assert((await page.locator("#source-sample").textContent()).includes("001"));
        assert((await page.locator("#source-sample").textContent()).includes("0.12345678901234567890123456789"));
        await page.locator("#source-form [name=name]").fill("experiment");
        for (const col of ["model", "split", "seed"]) await page.locator('#column-types input[data-column="' + col + '"]').check();
        for (const [col, type] of [["setting", "decimal"], ["seed", "integer"], ["score", "decimal"]]) await page.locator('#column-types select[data-column="' + col + '"]').selectOption(type);
        await click(page, "#source-form button[type=submit]");
        await page.locator("#metric-form [name=name]").fill("ours");
        await page.locator("#metric-form [name=source]").selectOption("experiment");
        await page.locator("#metric-form [name=field]").fill("score");
        for (const [column, value] of [["model", "001"], ["split", "test"], ["setting", "0.12345678901234567890123456789"]]) {
          const row = page.locator(".selector-row").filter({ has: page.locator('input[data-column="' + column + '"]') });
          await row.locator("input[type=checkbox]").check(); await row.locator("input[type=text]").fill(value);
        }
        await page.locator("#language").selectOption(lang === "en" ? "zh-CN" : "en"); await ready(page);
        assert.equal(await page.locator("#selectors input:checked").count(), 3);
        assert.equal(await page.locator('.selector-row:has(input[data-column="setting"]) input[type=text]').inputValue(), "0.12345678901234567890123456789");
        await page.locator("#language").selectOption(lang); await ready(page);
        await page.locator("#metric-form [name=reduce]").selectOption("mean");
        await page.locator("#metric-form [name=unit]").selectOption("fraction");
        await page.locator("#metric-form [name=expected_count]").fill("2");
        await click(page, "#metric-form button[type=submit]");
        assert((await page.locator("#metric-list").textContent()).includes("0.841"));
        await page.screenshot({ path: path.join(out, name + "-evidence.png"), fullPage: true });
        await click(page, 'nav [data-step=locations]');
        const boxes = page.locator('.candidate:has(mark:text-is("84.1")) input[type=checkbox]');
        await boxes.first().waitFor({ state: "visible" });
        assert.equal(await boxes.count(), 2);
        await boxes.nth(0).check(); await ready(page);
        await boxes.nth(1).check(); await ready(page);
        if (kind === "pdf") {
          await page.locator("#pdf-page img").waitFor({ state: "visible" });
          assert.equal(await page.locator("#pdf-page rect.selected").count(), 2);
          const rect = page.locator("#pdf-page rect").first();
          await rect.focus(); await page.keyboard.press("Space");
          assert.equal(await page.locator("#pdf-page rect.selected").count(), 1);
          await page.keyboard.press("Space");
          assert.equal(await page.locator("#pdf-page rect.selected").count(), 2);
          await click(page, "#pdf-zoom");
          assert(await page.locator("#pdf-view").evaluate((el) => el.classList.contains("zoomed")));
        }
        await page.locator("#locations-form [name=metric]").selectOption("ours");
        await page.locator("#locations-form [name=prefix]").fill("accuracy");
        await page.locator("#locations-form [name=rationale]").fill("Model 001, test split, exact setting and two seeds; mean accuracy.");
        await page.screenshot({ path: path.join(out, name + "-locations.png"), fullPage: true });
        const beforeDownload = page.waitForEvent("download"); await click(page, "#save-draft");
        const draft = await beforeDownload, draftPath = path.join(out, name + "-draft.json"); await draft.saveAs(draftPath);
        assert(fs.readFileSync(draftPath, "utf8").includes("0.12345678901234567890123456789"));
        await page.locator("#draft-file").setInputFiles(draftPath); await ready(page);
        await click(page, "#locations-form button[type=submit]");
        assert.deepEqual(fs.readFileSync(path.join(directory, "paperdelta.yaml")), originalConfig);
        await click(page, "#preview");
        assert.equal(await page.locator("#review-items input").count(), 2);
        assert.equal(await page.locator("#review-items input:checked").count(), 0);
        assert(await page.locator("#accept").isDisabled());
        await page.locator("#review-items input").first().check(); await page.locator("#attest").check();
        await page.screenshot({ path: path.join(out, name + "-review.png"), fullPage: true });
        await page.locator("#language").selectOption(lang === "en" ? "zh-CN" : "en"); await ready(page);
        assert.equal(await page.locator("#review-items input:checked").count(), 1);
        assert(await page.locator("#attest").isChecked());
        await page.locator("#language").selectOption(lang); await ready(page);
        await click(page, "#accept");
        assert(await page.locator("#receipt").isVisible());
        const report = JSON.parse(execFileSync(python, ["-X", "utf8", "-m", "paperdelta", "-C", directory, "check", "--format", "json"], { encoding: "utf8", windowsHide: true }));
        assert.equal(report.coverage.confirmed, 1); assert.equal(report.coverage.pass, 1);
        if (['md','qmd'].includes(kind)) {
          assert.equal(report.report_schema_version, 9);
          const location = Object.values(report.occurrences)[0].location;
          assert.equal(location.format, kind === 'md' ? 'markdown' : 'quarto');
          assert.equal(originalPaper.subarray(location.byte_start, location.byte_end).toString('utf8'), location.text);
        }
        assert.deepEqual(fs.readFileSync(path.join(directory, "paper." + kind)), originalPaper);
        assert.deepEqual(fs.readFileSync(path.join(directory, "results.csv")), originalData);
        const reportDownload = page.waitForEvent("download"); await click(page, "#download-report");
        const html = await reportDownload; await html.saveAs(path.join(out, name + "-report.html"));
        await page.setViewportSize({ width: 390, height: 844 }); await click(page, 'nav [data-step=locations]');
        await page.screenshot({ path: path.join(out, name + "-mobile.png"), fullPage: true });
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, name + " horizontal overflow");
        assert.deepEqual(errors, [], name + " browser errors"); assert.deepEqual(remote, [], name + " remote requests");
        // A preview is never authority after an experiment file changes.
        await page.locator('.candidate:has(mark:text-is("84.1")) input').first().check(); await ready(page);
        await page.locator("#locations-form [name=prefix]").fill("remaining");
        await click(page, "#locations-form button[type=submit]"); await click(page, "#preview");
        await page.locator("#review-items input").first().check(); await page.locator("#attest").check();
        const acceptedConfig = fs.readFileSync(path.join(directory, "paperdelta.yaml"));
        fs.writeFileSync(path.join(directory, "results.csv"), originalData.toString().replace("0.840", "0.900"));
        await page.locator("#accept").click();
        await page.waitForFunction(() => !document.body.hasAttribute("aria-busy"));
        assert(await page.locator("#error").isVisible()); assert(await page.locator("#stale").isVisible());
        assert(await page.locator("#accept").isDisabled());
        assert.deepEqual(fs.readFileSync(path.join(directory, "paperdelta.yaml")), acceptedConfig);
        assert(errors.every((item) => item.includes("409")), name + " unexpected browser error");
        results.push({ document: kind, language: lang, accepted: 1, exact_decimal_preserved: true, original_files_unchanged_before_test_edit: true, desktop_and_mobile: true, stale_acceptance_refused: true, browser_errors_before_test_edit: [], expected_conflict_console_messages: errors.length, remote_requests: remote });
        console.log(name + " passed");
      } finally { await context.close(); child.kill(); }
    }
  } finally { await browser.close(); fs.writeFileSync(path.join(out, "evidence.json"), JSON.stringify({ results }, null, 2) + "\n"); }
})().catch((error) => { console.error(error); process.exitCode = 1; });
