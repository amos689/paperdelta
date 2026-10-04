/* Offline static-source/PDF review: explicit exports, bilingual state and original bytes. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {spawnSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || path.join(root, 'build', 'static-reports-' + Date.now()));
assert(out.startsWith(path.join(root, 'build') + path.sep) && !fs.existsSync(out));
fs.mkdirSync(out, {recursive:true});
const results = [];
function check(directory, language, expected) {
  const run = spawnSync(python, ['-X','utf8','-m','paperdelta','--lang',language,'-C',directory,'check','--format','json','--report','build/review'], {cwd:root,encoding:'utf8',windowsHide:true});
  assert.equal(run.status, expected, run.stdout + run.stderr);
  return JSON.parse(run.stdout);
}
(async()=>{
  const browser = await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
  try {
    for (const language of ['en','zh-CN']) {
      const directory = path.join(out, language);
      fs.cpSync(path.join(root,'examples/static-manuscript'), directory, {recursive:true,filter:(name)=>!['build','.paperdelta'].includes(path.basename(name))});
      const originalPDF = fs.readFileSync(path.join(directory,'export.pdf'));
      const baseline = check(directory,language,0);
      assert(baseline.exports.every(item=>item.status==='aligned'));
      const evidence = path.join(directory,'results/metrics.csv');
      fs.writeFileSync(evidence, fs.readFileSync(evidence,'utf8').replace('0.839','0.807').replace('0.841','0.809').replace('0.843','0.811'));
      for(const file of ['paper.qmd','appendix.md']) {
        const target=path.join(directory,file);
        fs.writeFileSync(target,fs.readFileSync(target,'utf8').replaceAll('84.1','80.9'));
      }
      const report=check(directory,language,1);
      assert.equal(report.exports.find(item=>item.metric==='accuracy').status,'stale');
      for(const binding of ['abstract_accuracy','table_accuracy','supplement_accuracy']) assert.equal(report.occurrences[binding].status,'pass');
      assert.equal(report.claims.main_comparison.status,'mismatch');
      const context=await browser.newContext({viewport:{width:1280,height:950}});
      const page=await context.newPage(),errors=[],remote=[];
      page.on('pageerror',error=>errors.push(String(error)));
      page.on('request',request=>{if(/^https?:/.test(request.url()))remote.push(request.url());});
      try {
        await page.goto(pathToFileURL(path.join(directory,'build/review/report.html')).href);
        assert((await page.locator('#exports').textContent()).includes('paper.qmd'));
        await page.selectOption('#file','paper.qmd');
        const count=await page.locator('#findings article:visible').count();assert(count>0);
        await page.selectOption('#language',language==='en'?'zh-CN':'en');
        assert.equal(await page.inputValue('#file'),'paper.qmd');
        assert.equal(await page.locator('#findings article:visible').count(),count);
        await page.selectOption('#language',language);await page.selectOption('#file','');
        await page.locator('#pdf-pages').scrollIntoViewIfNeeded();
        await page.waitForFunction(()=>[...document.querySelectorAll('.pdf-canvas img')].every(i=>i.complete&&i.naturalWidth>0));
        assert((await page.locator('.pdf-canvas').boundingBox()).height>100);
        await page.screenshot({path:path.join(out,'report-'+language+'.png'),fullPage:true});
        await page.setViewportSize({width:390,height:844});
        assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
        const staticPage=await browser.newPage({javaScriptEnabled:false});
        await staticPage.goto(pathToFileURL(path.join(directory,'build/review/report.html')).href);
        assert((await staticPage.locator('#exports').textContent()).includes('paper.qmd'));
        await staticPage.close();
        assert.deepEqual(fs.readFileSync(path.join(directory,'export.pdf')),originalPDF);
        assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
        results.push({language,status:'passed',source_bindings:3,exports:report.exports,language_preserves_filters:true,original_pdf_unchanged:true,offline:true,mobile_overflow:false,static_fallback:true,errors,remote_requests:remote});
      } finally {await context.close();}
    }
    fs.writeFileSync(path.join(out,'evidence.json'),JSON.stringify({status:'passed',cases:results},null,2)+'\n');
    console.log(JSON.stringify({status:'passed',cases:results.length}));
  } finally {await browser.close();}
})().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
