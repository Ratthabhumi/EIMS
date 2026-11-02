// Prepared acceptance test; no injected JWT or Authorization header.
// Requires the actual Dashboard+BFF and isolated login/DB harness to be running.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
function runtimeConfig(env){
 const url=new URL(env.EIMS_TEST_BROWSER_BASE_URL);
 assert(url.protocol==='https:'&&!url.username&&!url.password&&url.pathname==='/'&&!url.search&&!url.hash,
  'Supply an explicitly approved HTTPS origin without credentials/path/query');
 assert(env.EIMS_TEST_IGNORE_TLS_ERRORS!=='1','TLS verification bypass is forbidden');
 return {base:url.origin,options:{viewport:{width:1400,height:1000},ignoreHTTPSErrors:false}};
}
module.exports={runtimeConfig};
const password='synthetic-test-password-only';
if(require.main===module)(async()=>{
 let browser;const report={status:'FAIL',boundary:'Actual browser login, no injected bearer',checks:[]};
 try{
  const {base,options}=runtimeConfig(process.env);
  const {chromium,request}=require(process.env.EIMS_PLAYWRIGHT_MODULE||'playwright');
  browser=await chromium.launch({channel:'msedge',headless:true});
  const owner=await browser.newContext(options),other=await browser.newContext(options);
  let bearerRequests=0;owner.on('request',r=>{if(r.headers().authorization)bearerRequests++});
  async function signIn(context,username){
   const page=await context.newPage();await page.goto(base+'/analyzer');
   await page.getByLabel('Username / ชื่อผู้ใช้').fill(username);await page.getByLabel('Password / รหัสผ่าน').fill(password);
   const response=page.waitForResponse(r=>r.url().endsWith('/api/session/login')&&r.request().method()==='POST');
   await page.getByRole('button',{name:'Sign in / เข้าสู่ระบบ',exact:true}).click();
   const r=await response;assert.equal(r.status(),200);assert.deepEqual(await r.json(),{authenticated:true});
   return page;
  }
  const page=await signIn(owner,'synthetic-browser-review');
  await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();
  const cookies=await owner.cookies();const cookie=cookies.find(c=>c.name==='eims_session');
  assert(cookie&&cookie.httpOnly&&cookie.secure&&cookie.sameSite==='Strict');
  assert(!(await page.evaluate(()=>document.cookie)).includes('eims_session'));
  assert(!(await page.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}))).includes(cookie.value));
  report.checks.push('Real login; HttpOnly Secure SameSite cookie; no JWT in DOM/storage');
  // Exercise both user input modes before the existing bundle/History/logout flow.
  for (const language of ['en','th']) for (const cid of ['fort_config','esxi_tracker','win_policy']) for (const mode of ['Paste Text','File Upload']) {
    await page.reload();
    await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();
    await page.getByRole('button',{name:mode,exact:true}).click();
    for(const select of await page.locator('select').all()) if(await select.locator('option[value="en"]').count()) await select.selectOption(language);
    const file=path.resolve('evaluation/analyzer/gold/cases',cid,'input.txt');
    if(mode==='Paste Text') await page.getByPlaceholder('Paste raw Event Viewer log text...').fill(fs.readFileSync(file,'utf8'));
    else await page.locator('input[type=file]:not([multiple])').setInputFiles(file);
    const pending=page.waitForResponse(r=>r.url().includes('/api/eims/api/v1/analyze')&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Analyze Log',exact:true}).click();
    const response=await pending;assert.equal(response.status(),200);const result=await response.json();
    assert(result.historyId);await page.getByRole('heading',{name:'Diagnostic Report',exact:true}).waitFor();
    if(cid==='fort_config'){assert.equal(result.eventId,'0100044547');assert.equal(result.eventMetadata.isCritical,false);}
    if(cid==='esxi_tracker'){assert.equal(result.eventMetadata.level,'Error');assert.equal(result.eventMetadata.isCritical,true);}
    if(cid==='win_policy'){assert.equal(result.eventId,'1129');assert.equal(result.eventMetadata.timestamp,'');assert.equal(result.eventMetadata.diagnosticCode,'WINDOWS-GROUP-POLICY-CONNECTIVITY');}
    await page.locator('details summary').first().click();assert(await page.locator('mark').first().isVisible());
    const historyResponse=await owner.request.get(base+'/api/eims/api/v1/history');assert.equal(historyResponse.status(),200);
    const restored=(await historyResponse.json()).find(r=>r.id===result.historyId);
    assert(restored);assert.deepEqual(restored.solutionSummary,result.solutionSummary);
    report.checks.push(`${language} ${cid} ${mode}: rendered result, source context and persisted History`);
  }
  await page.reload();await page.getByRole('button',{name:'File Upload',exact:true}).click();
  await page.locator('input[type=file]:not([multiple])').setInputFiles({name:'invalid.txt',mimeType:'text/plain',buffer:Buffer.from([255,254,255])});
  const invalidUpload=page.waitForResponse(r=>r.url().includes('/api/eims/api/v1/analyze')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Analyze Log',exact:true}).click();assert.equal((await invalidUpload).status(),400);
  await page.getByText(/Unable to extract log text/).waitFor();
  assert.equal(await page.getByRole('heading',{name:'Diagnostic Report',exact:true}).count(),0);
  report.checks.push('Invalid attachment produces an error, not Analysis complete');
  await page.reload();
  await page.getByRole('button',{name:'Evidence Bundle',exact:true}).click();
  for(const select of await page.locator('select').all())if(await select.locator('option[value="en"]').count())await select.selectOption('en');
  const root=path.resolve('evaluation/analyzer/results/20261025-controlled-demo-after');
  await page.locator('input[type=file][multiple]').setInputFiles([path.join(root,'a-veeam.txt'),path.join(root,'b-vmware.txt')]);
  const upload=page.waitForResponse(r=>r.url().includes('/api/eims/api/v1/analyze/bundle')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Analyze Log',exact:true}).click();const r=await upload;assert.equal(r.status(),200);const saved=await r.json();
  const evidence=saved.solutionSummary.evidenceItems;
  assert(evidence.length>0);
  for(const item of evidence){
   assert(['a-veeam.txt','b-vmware.txt'].includes(item.sourceFile));
   const lines=fs.readFileSync(path.join(root,item.sourceFile),'utf8').split(/\r?\n/);
   assert.equal(item.message,lines[item.lineNumber-1].trim().slice(0,500));
  }
  const summary=page.locator('details summary').first();await summary.waitFor();await summary.focus();await page.keyboard.press('Enter');
  assert(await page.locator('mark').first().isVisible());
  fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:'test-results/secure-source-light.png'});
  await page.getByRole('button',{name:'Back to finding',exact:true}).first().click();assert(await summary.evaluate(e=>document.activeElement===e));
  await page.reload();await page.getByText('Analyzed Log',{exact:true}).first().click();await page.locator('details summary').first().click();
  assert(await page.locator('mark').first().isVisible());await page.evaluate(()=>document.documentElement.classList.add('dark'));await page.screenshot({path:'test-results/secure-history-dark.png'});
  const rows=await (await owner.request.get(base+'/api/eims/api/v1/history')).json();const row=rows.find(x=>x.id===saved.historyId);
  assert.equal(row.username,'synthetic-browser-review');assert.deepEqual(row.solutionSummary,saved.solutionSummary);report.checks.push('Upload, evidence, light/dark, reload and owned PostgreSQL History');
  const otherPage=await signIn(other,'synthetic-browser-other');await otherPage.getByText('Signed in: synthetic-browser-other',{exact:true}).waitFor();
  const otherRows=await (await other.request.get(base+'/api/eims/api/v1/history')).json();assert(!otherRows.some(x=>x.id===saved.historyId));
  const forbidden=await otherPage.evaluate(async id=>(await fetch('/api/eims/api/v1/analyze/followup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({historyId:id,question:'What is observed?',language:'en'})})).status,saved.historyId);assert.equal(forbidden,404);report.checks.push('Second actual-login user cannot list or follow up owner History');
  // Two authenticated history entries make back/forward a real navigation test.
  await page.goto(base+'/analyzer?acceptance=before-logout');
  await page.goto(base+'/analyzer?acceptance=logout');
  await page.getByRole('button',{name:'Sign out / ออกจากระบบ',exact:true}).click();
  await page.getByLabel('Username / ชื่อผู้ใช้').waitFor();assert.equal((await owner.request.get(base+'/api/eims/api/v1/history')).status(),401);report.checks.push('Logout clears session and protected access fails');
  // Replay only the cookie issued by the real login, via an isolated HTTP
  // client. Never inject tokens into browser storage or log cookie contents.
  const replay=await request.newContext({ignoreHTTPSErrors:false,extraHTTPHeaders:{Cookie:`${cookie.name}=${cookie.value}`}});
  try{
   for(const endpoint of ['/api/eims/api/v1/auth/session','/api/eims/api/v1/history'])
    assert.equal((await replay.get(base+endpoint,{maxRedirects:0})).status(),401);
  }finally{await replay.dispose()}
  report.checks.push('Real login-issued cookie rejected after server logout');
  for(const navigate of [()=>page.goBack(),()=>page.goForward(),()=>page.reload()]){
   await navigate();await page.getByLabel('Username / ชื่อผู้ใช้').waitFor();
   assert.equal(await page.getByText('Signed in: synthetic-browser-review',{exact:true}).count(),0);
   assert.equal(await page.locator('details summary').count(),0);
   assert.equal((await owner.request.get(base+'/api/eims/api/v1/history')).status(),401);
  }
  report.checks.push('Back/forward/reload after logout: no retained evidence UI and protected API denied');
  const expiry=await browser.newContext(options);const short=await signIn(expiry,'synthetic-expiry');await new Promise(r=>setTimeout(r,3500));await short.reload();
  await short.getByLabel('Username / ชื่อผู้ใช้').waitFor();assert.equal((await expiry.request.get(base+'/api/eims/api/v1/history')).status(),401);
  await short.close();const again=await signIn(expiry,'synthetic-expiry');await again.close();report.checks.push('Real login-issued expiry and reauthentication');
  assert.equal(bearerRequests,0);report.checks.push('Zero manually injected browser Authorization headers');report.status='PASS';
 }catch(error){report.error=String(error);process.exitCode=1}finally{
  if(browser)await browser.close();fs.mkdirSync('test-results',{recursive:true});fs.writeFileSync('test-results/secure-browser-acceptance.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }
})();
