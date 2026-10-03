// A guided recording of actual generated reports, with presentation captions.
const { chromium } = require(process.env.PAPERDELTA_PLAYWRIGHT || 'playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

(async () => {
  const demo = path.resolve(process.argv[2] || 'build/demo');
  const output = path.resolve(process.argv[3] || 'build/recorded-demo');
  await fs.mkdir(output, { recursive: false });
  const browser = await chromium.launch({
    executablePath: process.env.PAPERDELTA_BROWSER_EXECUTABLE || undefined,
    headless: true,
  });
  const steps = [];
  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 900 },
      recordVideo: { dir: output, size: { width: 1280, height: 900 } },
    });
    const page = await context.newPage();
    const video = page.video();
    const caption = async (title, explanation, seconds) => {
      await page.evaluate(({ title, explanation }) => {
        document.getElementById('tour-caption')?.remove();
        const panel = document.createElement('aside');
        panel.id = 'tour-caption';
        Object.assign(panel.style, {
          position: 'fixed', bottom: '16px', left: '24px', right: '24px',
          padding: '16px 22px', background: '#122338', color: '#fff',
          borderRadius: '12px', zIndex: '999', boxShadow: '0 6px 25px #0003',
          fontFamily: 'system-ui', fontSize: '17px', lineHeight: '1.6',
        });
        const heading = document.createElement('strong');
        heading.textContent = title;
        panel.append(heading, document.createElement('br'), document.createTextNode(explanation));
        document.body.append(panel);
      }, { title, explanation });
      steps.push({ title, explanation, seconds });
      await page.waitForTimeout(seconds * 1000);
    };
    const open = async relative => {
      await page.goto(pathToFileURL(path.join(demo, relative)).href);
      await page.evaluate(() => window.scrollTo(0, 0));
    };
    await open('comparison-reversed/before/report.html');
    await caption('1. A paper before the experiment update',
      'Seven declared checks agree with the supplied evidence. Ours: 84.1%; baseline: 81.0%.', 6);
    await open('comparison-reversed/review/report.html');
    if (await page.locator('#findings article:visible').count() !== 6) throw new Error('Changed report must have six findings');
    await caption('2. Change the CSV; leave every LaTeX file untouched',
      'Ours falls to 80.9%. Four numeric references, one comparison and a recorded figure need attention.', 7);
    await page.selectOption('#file', 'paper/abstract.tex');
    await page.locator('#findings article:visible details summary').first().click();
    await page.locator('#findings article:visible').first().scrollIntoViewIfNeeded();
    await caption('3. Inspect the original source rows',
      'The abstract still says 84.1%. The report shows the selected test records and their mean.', 8);
    await page.selectOption('#file', '');
    await page.selectOption('#rule', 'CLAIM_FALSE');
    await page.locator('#findings article:visible').first().scrollIntoViewIfNeeded();
    await caption('4. The comparison also changed',
      '80.9% no longer beats 81.0%. Related numeric patches wait for the author to review the claim.', 8);
    await page.selectOption('#rule', 'FIGURE_CHANGED');
    await page.locator('#findings article:visible').first().scrollIntoViewIfNeeded();
    await caption('5. The figure has changed inputs',
      'Its recorded CSV identity differs. Re-run the plot explicitly; hashes do not prove visual correctness.', 8);
    await open('numeric-update/after/report.html');
    await caption('6. A separate numeric-only update: 84.1% to 84.5%',
      'Four guarded replacements across three files recheck successfully. The demo then restores the original bytes.', 7);
    await context.close();
    await video.saveAs(path.join(output, 'paperdelta-demo.webm'));
    await fs.writeFile(path.join(output, 'recording.json'), JSON.stringify({
      recorded_at: new Date().toISOString(), browser: await browser.version(),
      source: path.relative(path.resolve(__dirname, '..'), demo).split(path.sep).join('/'),
      captions: steps, planned_caption_seconds: 44,
      scope: 'Actual local HTML reports; captions are presentation annotations. Synthetic demonstration, not a user trial.',
    }, null, 2) + '\n');
    process.stdout.write(path.join(output, 'paperdelta-demo.webm'));
  } finally {
    await browser.close();
  }
})().catch(error => { process.stderr.write(error.stack); process.exitCode = 1; });
