/* Native layout review in the real bilingual Studio and offline report. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawn, spawnSync, execFileSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || path.join(root, 'build', 'layout-browser-' + Date.now()));
assert(out.startsWith(path.join(root, 'build') + path.sep) && !fs.existsSync(out));
fs.mkdirSync(out, {recursive:true});
const results = [];
const hash = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
async function ready(page) {
  await page.waitForFunction(() => !document.body.hasAttribute('aria-busy'));
  if(await page.locator('#error').isVisible()) throw new Error(await page.locator('#error').textContent());
}
async function act(page, selector, method='click', value) {await page.locator(selector)[method](value);await ready(page);}
async function start(directory, language) {
  const child=spawn(python,['-X','utf8','-m','paperdelta','--lang',language,'-C',directory,'studio','--no-open'],{cwd:root,windowsHide:true});
  let output='';
  const url=await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{child.kill();reject(new Error(output));},45000);
    child.stdout.on('data',(data)=>{output+=data;const m=output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/);if(m){clearTimeout(timer);resolve(m[0]);}});
    child.stderr.on('data',(data)=>{output+=data;});
    child.on('exit',(code)=>{clearTimeout(timer);reject(new Error(code+': '+output));});
  });
  return {child,url};
}
function check(directory, language) {
  const run=spawnSync(python,['-X','utf8','-m','paperdelta','--lang',language,'-C',directory,'check','--format','json','--report','review'],{cwd:root,encoding:'utf8',windowsHide:true});
  assert([0,1,2].includes(run.status),run.stderr);return JSON.parse(run.stdout);
}
async function runCase(browser, kind, language) {
  const directory=path.join(out,kind+'-'+language);
  const label=JSON.parse(execFileSync(python,['-X','utf8','tools/studio_layout_fixture.py','--out',path.relative(root,directory),'--kind',kind],{cwd:root,encoding:'utf8',windowsHide:true}));
  const before=hash(path.join(directory,label.paper));
  const context=await browser.newContext({viewport:{width:1280,height:950}});
  const page=await context.newPage(), errors=[],remote=[];
  page.setDefaultTimeout(45000);
  const {child,url}=await start(directory,language);
  page.on('pageerror',(e)=>errors.push(String(e)));
  page.on('request',(r)=>{if(!r.url().startsWith(new URL(url).origin)&&!r.url().startsWith('data:')&&!r.url().startsWith('blob:'))remote.push(r.url());});
  try {
    await page.goto(url);await page.locator('#workspace').waitFor({state:'visible'});await ready(page);
    await act(page,'nav [data-step=locations]');
    await act(page,'#locations-form [name=metric]','selectOption','score');
    await act(page,`#candidates [data-candidate="${label.candidate}"] input`,'check');
    await act(page,'#locations-form [name=display_kind]','selectOption','decimal');
    await act(page,'#locations-form [name=places]','fill','1');
    await act(page,'#locations-form [name=percent_symbol]','uncheck');
    await act(page,'#locations-form [name=prefix]','fill','result');
    await act(page,'#locations-form [name=rationale]','fill','Reviewed original cell or note and declared result identity.');
    await act(page,'#language','selectOption',language==='en'?'zh-CN':'en');
    assert(await page.locator(`#candidates [data-candidate="${label.candidate}"] input`).isChecked());
    await act(page,'#language','selectOption',language);
    if(kind==='docx-note') assert((await page.locator('#candidates').textContent()).includes(language==='en'?'footnote ID 7':'脚注 ID 7'));
    if(kind.startsWith('pdf')) {
      await page.locator('#pdf-page img').waitFor({state:'visible'});
      assert.equal(await page.locator('#pdf-page rect.selected').count(),1);
    }
    await page.screenshot({path:path.join(out,kind+'-'+language+'.png'),fullPage:true});
    await act(page,'#locations-form button[type=submit]');await act(page,'#preview');
    assert.equal(await page.locator('#review-items input[type=checkbox]').count(),1);
    await act(page,'#review-items input[type=checkbox]','check');await act(page,'#attest','check');await act(page,'#accept');
    const report=check(directory,language);assert.equal(report.coverage.pass,1);
    const location=Object.values(report.occurrences)[0].location;
    if(kind==='docx-note')assert.equal(location.locator.note_id,7);
    if(kind==='docx-table')assert.equal(report.report_schema_version,9);
    assert.equal(hash(path.join(directory,label.paper)),before);
    fs.writeFileSync(path.join(directory,'results.csv'),`id,score\nresult,${label.changed}\n`);
    const changed=check(directory,language);assert.equal(changed.coverage.mismatch,1);
    assert.deepEqual(Object.values(changed.occurrences)[0].location,location);
    const offline=await context.newPage();await offline.goto('file:///'+path.join(directory,'review','report.html').replaceAll('\\','/'));
    if(kind.startsWith('pdf')){
      await offline.locator('#pdf-pages').scrollIntoViewIfNeeded();
      await offline.waitForFunction(()=>[...document.querySelectorAll('.pdf-canvas img')].every(i=>i.complete&&i.naturalWidth>0));
      assert((await offline.locator('.pdf-canvas').boundingBox()).height>100);
    }
    await offline.screenshot({path:path.join(out,'report-'+kind+'-'+language+'.png'),fullPage:true});
    if(kind==='docx-note')assert((await offline.locator('body').textContent()).includes(language==='en'?'footnote ID 7':'脚注 ID 7'));
    await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2));
    assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
    results.push({kind,language,status:'passed',source_sha256:before,locator:location.locator,changed_evidence:'mismatch',errors,remote_requests:remote});
  } catch(error) {
    await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});
    fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({kind,language,error:String(error),completed:results,errors},null,2));throw error;
  } finally {await context.close();child.kill();}
}
(async()=>{const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
  try {for(const kind of ['docx-table','docx-note','pdf-rotated','pdf-merged'])for(const language of ['en','zh-CN'])await runCase(browser,kind,language);
    fs.writeFileSync(path.join(out,'evidence.json'),JSON.stringify({status:'passed',cases:results},null,2)+'\n');console.log(JSON.stringify({status:'passed',cases:results.length}));
  }finally{await browser.close();}
})().catch(e=>{console.error(e.stack||e);process.exitCode=1;});
