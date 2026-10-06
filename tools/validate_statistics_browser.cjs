/* Real browser checks: explicit conventions, full compounds, language and templates. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { spawn, execFileSync } = require('node:child_process');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..'), python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || path.join(root, 'build', 'statistics-browser-' + Date.now()));
assert(out.startsWith(path.join(root, 'build') + path.sep) && !fs.existsSync(out));
fs.mkdirSync(out, { recursive: true });
const results = [];
const py = (args) => execFileSync(python, ['-X', 'utf8', ...args], { cwd: root, encoding: 'utf8', windowsHide: true });
const hash = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
async function start(directory, language) {
  const child = spawn(python, ['-X','utf8','-m','paperdelta','--lang',language,'-C',directory,'studio','--no-open'], { cwd: root, windowsHide: true });
  let output = '';
  const url = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { child.kill(); reject(new Error(output)); }, 45000);
    child.stdout.on('data', (data) => { output += data; const match = output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/); if (match) { clearTimeout(timer); resolve(match[0]); } });
    child.stderr.on('data', (data) => { output += data; });
    child.on('exit', (code) => { clearTimeout(timer); reject(new Error(code + ': ' + output)); });
  });
  return { child, url };
}
async function ready(page) {
  await page.waitForFunction(() => !document.body.hasAttribute('aria-busy'));
  if (await page.locator('#error').isVisible()) throw new Error(await page.locator('#error').textContent());
}
async function act(page, selector, method='click', value) { await page.locator(selector)[method](value); await ready(page); }
async function runCase(browser, kind, language, batch=false) {
  const directory = path.join(out, `${kind}-${language}${batch ? '-batch' : ''}`);
  const annotation = JSON.parse(py(['tools/studio_statistics_fixture.py','--out',path.relative(root,directory),'--kind',kind]));
  const inputs = Object.fromEntries([annotation.paper,annotation.source].map((file) => [file,hash(path.join(directory,file))]));
  const context = await browser.newContext({ viewport: { width: 1280, height: 950 } });
  const page = await context.newPage(), errors = [], remote = [];
  page.setDefaultTimeout(45000);
  const { child, url } = await start(directory, language);
  page.on('pageerror', (error) => errors.push(String(error)));
  page.on('console', (message) => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('request', (request) => { if (!request.url().startsWith(new URL(url).origin) && !request.url().startsWith('blob:') && !request.url().startsWith('data:')) remote.push(request.url()); });
  try {
    await page.goto(url); await page.locator('#workspace').waitFor({ state:'visible' }); await ready(page);
    const form = batch ? '#batch-form' : '#metric-form';
    if (batch) {
      await act(page,'nav [data-step=batch]');
      await act(page,'#batch-fields input[data-column=accuracy]','check');
      await act(page,'#batch-groups input[data-column=model]','check');
    } else {
      await act(page,'#add-metric > summary');
      await act(page,`${form} [name=source]`,'selectOption','runs');
      await act(page,`${form} [name=name]`,'fill','accuracy');
      await act(page,`${form} [name=field]`,'fill','accuracy');
      await act(page,'#selectors input[type=checkbox][data-column=model]','check');
      await act(page,'#selectors .selector-row:has(input[data-column=model]) input[type=text]','fill','method');
    }
    await act(page,`${form} [name=unit]`,'selectOption','percent');
    await act(page,`${form} [name=reduce]`,'selectOption','statistics');
    await act(page,`${form} [name=expected_count]`,'fill','5');
    await act(page,`${form} [name=expected_seeds]`,'fill','1\n2\n3\n4\n5');
    assert.equal(await page.locator(`${form} [name=stats_ddof]`).inputValue(),'');
    await act(page,`${form} [name=stats_ddof]`,'selectOption','1');
    await act(page,`${form} [name=stats_unit]`,'fill','independent experimental seed');
    await act(page,`${form} [name=stats_ci]`,'selectOption','student_t');
    await act(page,`${form} [name=stats_level]`,'fill','0.95');
    assert(!(await page.locator(`${form} [name=stats_assumption]`).isChecked()));
    await act(page,`${form} [name=stats_assumption]`,'check');
    await act(page,'#language','selectOption',language==='en'?'zh-CN':'en');
    assert.equal(await page.locator(`${form} [name=stats_level]`).inputValue(),'0.95');
    assert.equal(await page.locator(`${form} [name=expected_seeds]`).inputValue(),'1\n2\n3\n4\n5');
    assert(await page.locator(`${form} [name=stats_assumption]`).isChecked());
    await act(page,'#language','selectOption',language);
    if (batch) {
      await act(page,`${form} [name=display_kind]`,'selectOption','decimal');
      await act(page,`${form} [name=places]`,'fill','2');
      await act(page,`${form} [name=percent_symbol]`,'uncheck');
      await act(page,`${form} [name=stats_component]`,'selectOption','mean_sd');
      await act(page,`${form} [name=stats_show_n]`,'check');
    }
    await page.locator(form).screenshot({ path:path.join(out,`contract-${kind}-${language}${batch?'-batch':''}.png`) });
    await act(page,`${form} button[type=submit]`);
    if (batch) {
      await act(page,'.batch-choice button');
      for (const id of annotation.mean_sd) await act(page,`#batch-locations input[data-batch-candidate="${id}"]`,'check');
      await act(page,'nav [data-step=batch]');
      await act(page,'#batch-templates summary');
      await act(page,'#template-save-form [name=name]','fill','seed_statistics');
      await act(page,'#template-save-form button');
      await act(page,`${form} [name=stats_level]`,'fill','0.90');
      await act(page,'#template-load');
      assert.equal(await page.locator(`${form} [name=stats_level]`).inputValue(),'0.95');
      assert.equal(await page.locator(`${form} [name=stats_component]`).inputValue(),'mean_sd');
      page.once('dialog',(dialog)=>dialog.accept());
      await act(page,`${form} button[type=submit]`);
      await act(page,'.batch-choice button');
      for (const id of annotation.mean_sd) await act(page,`#batch-locations input[data-batch-candidate="${id}"]`,'check');
      await act(page,'#batch-rationale','fill','All five seeds and the complete mean/SD/n expression.');
      await act(page,'#batch-stage');
    } else {
      await act(page,'nav [data-step=locations]');
      await act(page,'#locations-form [name=metric]','selectOption','accuracy');
      for (const [component,ids] of [['mean_sd',annotation.mean_sd],['ci',annotation.ci],['confidence_level',annotation.confidence_level]]) {
        await act(page,'nav [data-step=locations]');
        await act(page,'#locations-form [name=prefix]','fill',component);
        await act(page,'#locations-form [name=display_kind]','selectOption',component==='confidence_level'?'percent':'decimal');
        await act(page,'#locations-form [name=places]','fill',component==='confidence_level'?'0':'2');
        await act(page,'#locations-form [name=percent_symbol]',component==='confidence_level'?'check':'uncheck');
        await act(page,'#locations-form [name=stats_component]','selectOption',component);
        if(component!=='confidence_level') await act(page,'#locations-form [name=stats_show_n]',component==='mean_sd'?'check':'uncheck');
        for (const id of ids) await act(page,`#candidates [data-candidate="${id}"] input`,'check');
        await act(page,'#language','selectOption',language==='en'?'zh-CN':'en');
        assert.equal(await page.locator('#locations-form [name=stats_component]').inputValue(),component);
        for (const id of ids) assert(await page.locator(`#candidates [data-candidate="${id}"] input`).isChecked());
        await act(page,'#language','selectOption',language);
        await act(page,'#locations-form [name=rationale]','fill','The explicit complete five-seed result with declared statistics.');
        await act(page,'#locations-form button[type=submit]');
      }
    }
    await act(page,'#preview');
    assert.equal(await page.locator('#review-items .preview-card').count(),batch?1:3);
    for (const checkbox of await page.locator('#review-items input[type=checkbox]').all()) { await checkbox.check(); await ready(page); }
    await act(page,'#attest','check'); await act(page,'#accept');
    const report = JSON.parse(py(['-m','paperdelta','-C',directory,'check','--format','json']));
    assert.equal(report.report_schema_version,['md','qmd'].includes(kind)?8:6); assert.equal(report.coverage.pass,batch?1:3);
    const result = Object.values(report.metrics)[0]; assert.equal(result.statistics.n,5); assert.equal(result.statistics.confidence_interval.level,'0.95');
    assert(Object.values(report.occurrences).some((item)=>item.actual.includes('1.58') && item.actual.includes('n = 5')));
    assert.deepEqual(Object.fromEntries(Object.keys(inputs).map((file)=>[file,hash(path.join(directory,file))])),inputs);
    await page.setViewportSize({width:390,height:844});
    await act(page,'nav [data-step=locations]');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2));
    assert.deepEqual(errors,[]); assert.deepEqual(remote,[]);
    results.push({kind,language,batch,status:'passed',bindings:batch?1:3,inputs,errors,remote_requests:remote});
  } catch (error) {
    await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});
    fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({kind,language,batch,error:String(error),errors,completed:results,invalid:await page.locator('input:invalid,select:invalid').evaluateAll((items)=>items.map((item)=>({form:item.form.id,name:item.name,disabled:item.disabled,message:item.validationMessage}))).catch(()=>[])},null,2));
    throw error;
  } finally { await context.close(); child.kill(); }
}
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
  try {
    for(const kind of (process.env.PAPERDELTA_DOCUMENT_FORMATS || 'tex,docx,pdf,md,qmd').split(',')) for(const language of ['en','zh-CN']) await runCase(browser,kind,language);
    for(const kind of (process.env.PAPERDELTA_BATCH_FORMATS || 'tex,md,qmd').split(',')) for(const language of ['en','zh-CN']) await runCase(browser,kind,language,true);
    fs.writeFileSync(path.join(out,'evidence.json'),JSON.stringify({status:'passed',cases:results},null,2)+'\n');
    console.log(JSON.stringify({status:'passed',cases:results.length}));
  } finally { await browser.close(); }
})().catch((error)=>{console.error(error.stack||error);process.exitCode=1;});
