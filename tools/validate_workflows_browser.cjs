/* Real bilingual browser review of saved-state fixtures; execution is tested separately. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createHash} = require('node:crypto');
const {spawn, execFileSync} = require('node:child_process');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..'), python = process.env.PAPERDELTA_PYTHON || 'python';
const out = path.resolve(process.argv[2] || path.join(root, 'build', 'workflows-' + Date.now()));
assert(out.startsWith(path.join(root, 'build') + path.sep) && !fs.existsSync(out));
fs.mkdirSync(out, {recursive:true});
const cases = [];
const delayedReview = process.argv.includes('--delayed-review');
const py = args => execFileSync(python, ['-X','utf8',...args], {cwd:root,encoding:'utf8',windowsHide:true});
async function start(directory, language) {
  const child = spawn(python,['-X','utf8','-m','paperdelta','--lang',language,'-C',directory,'studio','--no-open'],{cwd:root,windowsHide:true});
  let output='';
  const url = await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>{child.kill();reject(new Error(output));},45000);
    child.stdout.on('data', data=>{output+=data;const match=output.match(/http:\/\/127\.0\.0\.1:\d+\/#[A-Za-z0-9_-]+/);if(match){clearTimeout(timer);resolve(match[0]);}});
    child.stderr.on('data',data=>{output+=data;});
    child.on('exit',code=>{clearTimeout(timer);reject(new Error(code+': '+output));});
  });
  return {child,url};
}
async function runCase(browser, format, language) {
  const name=format+'-'+language, directory=path.join(out,name);
  py(['tools/workflow_fixture.py','--out',directory,'--saved']);
  const inputs=['analysis.ipynb','observations.csv','results/metrics.csv','paper.qmd','rendered.html'];
  const originals=Object.fromEntries(inputs.map(file=>[file,fs.readFileSync(path.join(directory,file))]));
  const {child,url}=await start(directory,language);
  const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
  page.setDefaultTimeout(45000);
  const errors=[],remote=[];
  let holdReview=false, releaseReview, heldReview, receiveHeldReview;
  const held = new Promise(resolve=>{receiveHeldReview=resolve;});
  if(delayedReview)await page.route('**/api',async route=>{
    const request=route.request();
    if(!holdReview || request.postDataJSON()?.action!=='review')return route.continue();
    const response=await route.fetch();
    const detail=await response.json();
    // An earlier poll may overlap the final fragment acceptance. Delay only
    // the real report that includes that write, never an unrelated old poll.
    if(!detail.report?.fragments.results)return route.fulfill({response});
    holdReview=false;
    heldReview=detail;
    const gate=new Promise(resolve=>{releaseReview=resolve;});
    receiveHeldReview();
    await gate;
    await route.fulfill({response});
  });
  page.on('pageerror',error=>errors.push(String(error)));
  page.on('request',request=>{if(!request.url().startsWith(new URL(url).origin)) remote.push(request.url());});
  async function ready(){await page.waitForFunction(()=>!document.body.hasAttribute('aria-busy'));if(await page.locator('#error').isVisible()) throw new Error(await page.locator('#error').textContent());}
  async function act(selector,method='click',value){await page.locator(selector)[method](value);await ready();}
  async function fill(form,name,value){await act('#'+form+' [name="'+name+'"]','fill',value);}
  async function accept(){assert(await page.locator('#workflow-accept').isDisabled());await act('#workflow-attest','check');await act('#workflow-accept');}
  try {
    await page.goto(url);await page.locator('#workspace').waitFor({state:'visible'});await ready();
    await act('#workflow-panel > summary');await act('#workflow-load');
    await act('#producer-panel > summary');
    await fill('producer-form','name','training');await fill('producer-form','source','analysis.ipynb');
    await act('#producer-inspect');await act('#producer-cells input[value=metrics]','check');
    await fill('producer-form','inputs','observations.csv');await fill('producer-form','outputs','results/metrics.csv');
    await fill('producer-form','rationale','Reviewed selected cell and declared inputs/outputs.');
    await act('#producer-form button[type=submit]');
    assert(await page.locator('#workflow-preview').isVisible());
    await act('#language','selectOption',language==='en'?'zh-CN':'en');
    assert(await page.locator('#producer-cells input[value=metrics]').isChecked());
    assert.equal(await page.locator('#producer-form [name=rationale]').inputValue(),'Reviewed selected cell and declared inputs/outputs.');
    assert(await page.locator('#workflow-preview').isHidden());
    await act('#language','selectOption',language);
    await act('#producer-form button[type=submit]');await accept();
    assert(await page.locator('[data-subject="provenance:training"] .status-pass').count());
    await fill('producer-form','name','render');await act('#producer-form [name=kind]','selectOption','quarto');
    await fill('producer-form','source','paper.qmd');await fill('producer-form','inputs','results/metrics.csv');
    await fill('producer-form','outputs','rendered.html');await act('#producer-form button[type=submit]');await accept();
    await act('#producer-panel > summary');await act('#fragment-panel > summary');
    await fill('fragment-form','name','results');await act('#fragment-form [name=format]','selectOption',format);
    const generated='generated/results.'+(format==='latex'?'tex':'md');
    await fill('fragment-form','path',generated);
    await act('#fragment-bindings input[value=table_accuracy]','check');await act('#fragment-bindings input[value=table_baseline]','check');
    await act('#fragment-form button[type=submit]');
    assert.match(await page.locator('#workflow-preview-body').innerText(),/84\.1/);
    assert(!fs.existsSync(path.join(directory,generated)));
    await act('#language','selectOption',language==='en'?'zh-CN':'en');
    assert.equal(await page.locator('#fragment-bindings input:checked').count(),2);
    assert.equal(await page.locator('#fragment-form [name=path]').inputValue(),generated);
    await act('#language','selectOption',language);
    await act('#fragment-form button[type=submit]');
    await page.locator('#workflow-preview').screenshot({path:path.join(out,name+'-preview.png')});
    holdReview=delayedReview;
    await accept();assert.match(fs.readFileSync(path.join(directory,generated),'utf8'),/84\.1/);
    for(const file of inputs)assert.deepEqual(fs.readFileSync(path.join(directory,file)),originals[file]);
    assert(!fs.existsSync(path.join(directory,'.paperdelta/example-executions.log')));
    if(delayedReview)await Promise.race([held,new Promise((_,reject)=>{const timer=setTimeout(()=>reject(new Error('No real background review response to delay')),15000);timer.unref();})]);
    const generation=Number(await page.locator('#review-workspace').getAttribute('data-generation'));
    const csv=path.join(directory,'results/metrics.csv');
    const changed=fs.readFileSync(csv,'utf8').replace('0.839','0.807').replace('0.841','0.809').replace('0.843','0.811');
    const expectedHash='sha256:'+createHash('sha256').update(changed).digest('hex');
    const currentReview=page.waitForResponse(async response=>{
      if(response.request().postDataJSON()?.action!=='review' || !response.ok())return false;
      const detail=await response.json();
      return detail.report?.input_hashes['results/metrics.csv']===expectedHash && detail.summary.state==='current';
    });
    fs.writeFileSync(csv,changed);
    let generationOnlyWouldFinishEarly=false;
    if(delayedReview){
      assert(heldReview.summary.generation>generation);
      assert.notEqual(heldReview.report.input_hashes['results/metrics.csv'],expectedHash);
      releaseReview();
      await page.waitForFunction(before=>Number(document.querySelector('#review-workspace').dataset.generation)>before && document.querySelector('#review-workspace').dataset.reviewState==='current',generation);
      generationOnlyWouldFinishEarly=true;
    }
    const checked=await (await currentReview).json();
    await page.waitForFunction(checkedGeneration=>Number(document.querySelector('#review-workspace').dataset.generation)>=checkedGeneration && document.querySelector('#review-workspace').dataset.reviewState==='current',checked.summary.generation);
    await act('#workflow-load');
    for(const subject of ['provenance:training','provenance:render','fragments:results'])assert(await page.locator('#workflow-states [data-subject="'+subject+'"] .status-mismatch').count());
    assert.match(await page.locator('#workflow-revisions').innerText(),/80\.9/);
    await page.locator('#workflow-states').screenshot({path:path.join(out,name+'-changed.png')});
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2));
    assert.deepEqual(errors,[]);assert.deepEqual(remote,[]);
    cases.push({name,status:'passed',format,language,language_switch_preserved_fields_and_selection:true,explicit_acceptance:true,declared_only:true,no_project_execution:true,source_files_preserved_before_authored_change:true,changed_evidence_marks_notebook_render_and_fragment_stale:true,checked_input_sha256:expectedHash,delayed_real_review:delayedReview,generation_only_would_finish_early:generationOnlyWouldFinishEarly,remote_requests:remote});
  } catch(error) {
    await page.screenshot({path:path.join(out,name+'-failure.png'),fullPage:true}).catch(()=>{});
    fs.writeFileSync(path.join(out,'failure.json'),JSON.stringify({name,error:String(error),errors,cases},null,2));throw error;
  } finally {releaseReview?.();await context.close();child.kill();}
}
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE?{executablePath:process.env.BROWSER_EXECUTABLE}:{})});
  try{for(const format of ['latex','markdown'])for(const language of ['en','zh-CN'])await runCase(browser,format,language);
    fs.writeFileSync(path.join(out,'evidence.json'),JSON.stringify({status:'passed',scope:'Four authored saved-state browser workflows; actual Jupyter execution and Quarto rendering are measured separately. Not independent usability or scientific validity.',cases},null,2)+'\n');
    console.log(JSON.stringify({status:'passed',cases:cases.length}));
  }finally{await browser.close();}
})().catch(error=>{console.error(error.stack||error);process.exitCode=1;});
