// Prepared acceptance test; no injected JWT or Authorization header.
// Requires the actual Dashboard+BFF and isolated login/DB harness to be running.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
function runtimeConfig(env){
 const url=new URL(env.EIMS_TEST_BROWSER_BASE_URL);
 assert(url.protocol==='https:'&&!url.username&&!url.password&&url.pathname==='/'&&!url.search&&!url.hash,
  'Supply an explicitly approved HTTPS origin without credentials/path/query');
 assert(env.EIMS_TEST_IGNORE_TLS_ERRORS!=='1','TLS verification bypass is forbidden');
 return {base:url.origin,options:{viewport:{width:1400,height:1000},ignoreHTTPSErrors:false,acceptDownloads:true}};
}
module.exports={runtimeConfig};
const password='synthetic-test-password-only';
if(require.main===module)(async()=>{
 let browser;const report={status:'FAIL',boundary:'Actual browser login, no injected bearer',checks:[]};
  let stage='startup';
  const authDebugEvents=[];
 try{
  const {base,options}=runtimeConfig(process.env);
  const {chromium,request}=require(process.env.EIMS_PLAYWRIGHT_MODULE||'playwright');
  browser=await chromium.launch({channel:'msedge',headless:true});
  const owner=await browser.newContext(options),other=await browser.newContext(options);
  let bearerRequests=0;owner.on('request',r=>{if(r.headers().authorization)bearerRequests++});
  async function signIn(context,username){
    stage='signIn:'+username+':initial-session';
    const page=await context.newPage();
    if(username==='synthetic-browser-other'){
     const record=(kind,url,status)=>{try{const p=new URL(url).pathname;if(p.includes('/auth/session')||p.endsWith('/api/session/login'))authDebugEvents.push(kind+(status===undefined?'':' '+status)+' '+p)}catch{}};
     page.on('request',r=>record('REQ',r.url()));
     page.on('response',r=>record('RES',r.url(),r.status()));
     page.on('requestfailed',r=>record('FAIL',r.url()));
    }page.setDefaultTimeout(12000);page.setDefaultNavigationTimeout(15000);
   // DOMContentLoaded can precede React hydration. The first auth-session probe
   // is emitted by AnalyzerSession's mount effect, so await it before clicking.
   const initialSession=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/api/v1/auth/session')&&r.request().method()==='GET',{timeout:30000});
   await page.goto(base+'/analyzer',{waitUntil:'domcontentloaded'});
    await initialSession;
    stage='signIn:'+username+':form';
   const usernameField=page.locator('input[name="username"]');await usernameField.waitFor({state:"visible"});await usernameField.fill(username);const passwordField=page.locator('input[name="password"]');await passwordField.waitFor({state:"visible"});await page.waitForFunction(()=>{const e=document.querySelector('input[name="password"]');return e&&!e.disabled&&!e.readOnly&&e.getClientRects().length>0;});await passwordField.fill(password);
   stage='signIn:'+username+':login-response';
    const response=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/api/session/login')&&r.request().method()==='POST',{timeout:15000});
   await page.getByRole('button',{name:/^Sign in\b/}).click();
   const r=await response;stage='signIn:'+username+':authenticated-ui';assert.equal(r.status(),200);const loginBody=await Promise.race([r.body(),new Promise(resolve=>setTimeout(()=>resolve(null),2500))]);if(loginBody===null){if(!report.warnings)report.warnings=[];if(!report.warnings.includes("Login POST body did not finish within 2.5s; cookie and authenticated-session checks remain authoritative."))report.warnings.push("Login POST body did not finish within 2.5s; cookie and authenticated-session checks remain authoritative.");}else assert.deepEqual(JSON.parse(loginBody.toString()),{authenticated:true});await page.getByText("Signed in: "+username,{exact:true}).waitFor();
   return page;
  }
  const page=await signIn(owner,'synthetic-browser-review');
  stage='owner:health-proxy';
  const health=await page.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/health',{credentials:'include'});return {status:r.status,body:await r.json()}});
  assert.equal(health.status,503);
  assert.equal(health.body.status,'DEGRADED');
  assert.equal(health.body.components.postgresql_pgbouncer_tier,'UP');
  assert.equal(health.body.components.redis_volatile_lru_tier,'DOWN');
  assert.equal(health.body.components.minio_object_storage_tier,'DOWN');
  report.checks.push('Degraded synthetic Health 503 passes through BFF with truthful PostgreSQL/Redis/MinIO status');
  stage='owner:analyzer-cases';
  await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();
  const cookies=await owner.cookies();const cookie=cookies.find(c=>c.name==='eims_session');
  assert(cookie&&cookie.httpOnly&&cookie.secure&&cookie.sameSite==='Strict');
  assert(!(await page.evaluate(()=>document.cookie)).includes('eims_session'));
  assert(!(await page.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}))).includes(cookie.value));
  report.checks.push('Real login; HttpOnly Secure SameSite cookie; no JWT in DOM/storage');
  // Exercise both user input modes before the existing bundle/History/logout flow.
  for (const language of ['en','th']) for (const cid of ['fort_config','esxi_tracker','win_policy']) for (const mode of ['Paste Text','File Upload']) {
    await page.reload({waitUntil:'domcontentloaded'});
    await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();
    await page.getByRole('button',{name:mode,exact:true}).click();
    for(const select of await page.locator('select').all()) if(await select.locator('option[value="en"]').count()) await select.selectOption(language);
    const file=path.resolve('evaluation/analyzer/gold/cases',cid,'input.txt');
    if(mode==='Paste Text') await page.getByPlaceholder('Paste raw Event Viewer log text...').fill(fs.readFileSync(file,'utf8'));
    else await page.locator('input[type=file]:not([multiple])').setInputFiles(file);
    const pending=page.waitForResponse(r=>r.url().includes('/api/eims/api/v1/analyze')&&r.request().method()==='POST'&&(r.status()<300||r.status()>=400));
    await page.getByRole('button',{name:'Analyze Log',exact:true}).click();
    const response=await pending;assert.equal(response.status(),200);const result=await response.json();
    assert(result.historyId);await page.getByRole('heading',{name:'Diagnostic Report',exact:true}).waitFor();
    if(cid==='fort_config'){assert.equal(result.eventId,'0100044547');assert.equal(result.eventMetadata.isCritical,false);}
    if(cid==='esxi_tracker'){assert.equal(result.eventMetadata.level,'Error');assert.equal(result.eventMetadata.isCritical,true);}
    if(cid==='win_policy'){assert.equal(result.eventId,'1129');assert.equal(result.eventMetadata.timestamp,'');assert.equal(result.eventMetadata.diagnosticCode,'WINDOWS-GROUP-POLICY-CONNECTIVITY');}
    await page.locator('details summary').first().click();assert(await page.locator('mark').first().isVisible());
    const historyRows=await page.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/history',{credentials:'include'});if(!r.ok)throw new Error('owner history '+r.status);return r.json()});
     const restored=historyRows.find(r=>r.id===result.historyId);
    assert(restored);assert.deepEqual(restored.solutionSummary,result.solutionSummary);
    report.checks.push(`${language} ${cid} ${mode}: rendered result, source context and persisted History`);
  }
  await page.reload({waitUntil:'domcontentloaded'});await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();await page.getByRole('button',{name:'File Upload',exact:true}).click();
  await page.locator('input[type=file]:not([multiple])').setInputFiles({name:'invalid.txt',mimeType:'text/plain',buffer:Buffer.from([255,254,255])});
  const invalidUpload=page.waitForResponse(r=>r.url().includes('/api/eims/api/v1/analyze')&&r.request().method()==='POST'&&(r.status()<300||r.status()>=400));
  await page.getByRole('button',{name:'Analyze Log',exact:true}).click();assert.equal((await invalidUpload).status(),400);
  await page.getByText(/Unable to extract log text/).waitFor();
  assert.equal(await page.getByRole('heading',{name:'Diagnostic Report',exact:true}).count(),0);
  report.checks.push('Invalid attachment produces an error, not Analysis complete');
  await page.reload({waitUntil:'domcontentloaded'});await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();
   await page.getByRole('button',{name:'Evidence Bundle',exact:true}).click();
  const root=path.resolve('evaluation/analyzer/results/20261025-controlled-demo-after');
  await page.locator('input[type=file][multiple]').setInputFiles([path.join(root,'a-veeam.txt'),path.join(root,'b-vmware.txt')]);
  const upload=page.waitForResponse(r=>r.url().includes('/api/eims/api/v1/analyze/bundle')&&r.request().method()==='POST'&&(r.status()<300||r.status()>=400));
  await page.getByRole('button',{name:'Analyze Log',exact:true}).click();const r=await upload;assert.equal(r.status(),200);const saved=await r.json();
  const evidence=saved.solutionSummary.evidenceItems;
  assert(evidence.length>0);
  for(const item of evidence){
   assert(['a-veeam.txt','b-vmware.txt'].includes(item.sourceFile));
   const lines=fs.readFileSync(path.join(root,item.sourceFile),'utf8').split(/\r?\n/);
   assert.equal(item.message,lines[item.lineNumber-1].trim().slice(0,500));
  }
  await page.getByRole('heading',{name:'Diagnostic Report',exact:true}).waitFor();
  const liveModal=page.locator('div.fixed.inset-0').filter({has:page.getByRole('heading',{name:'Diagnostic Report',exact:true})});
  await liveModal.getByText(/a-veeam\.txt/).waitFor();
  await liveModal.getByText(/b-vmware\.txt/).waitFor();
  const summary=page.locator('details summary').first();await summary.waitFor();await summary.focus();await page.keyboard.press('Enter');
  assert(await page.locator('mark').first().isVisible());
  fs.mkdirSync('test-results',{recursive:true});await page.screenshot({path:'test-results/secure-source-light.png'});

  const liveMdWait=page.waitForEvent('download',{timeout:30000});
  await liveModal.getByRole('button',{name:'Export MD',exact:true}).click();
  const liveMdDownload=await liveMdWait;
  assert(liveMdDownload.suggestedFilename().endsWith('.md'));
  const liveMdPath=path.resolve('test-results/secure-live-report.md');
  await liveMdDownload.saveAs(liveMdPath);
  const liveMdContent=fs.readFileSync(liveMdPath,'utf8');
  assert(liveMdContent.startsWith('# AI Diagnostic Report'));
  assert(liveMdContent.includes('a-veeam.txt')&&liveMdContent.includes('b-vmware.txt'));
  assert(/[\u0E00-\u0E7F]/.test(liveMdContent),'Thai text missing from live Markdown export');
  report.checks.push('Live Thai Markdown: actual browser download, content and source evidence');
  const livePdfWait=page.waitForEvent('download',{timeout:60000});
  await liveModal.getByRole('button',{name:'Export PDF',exact:true}).click();
  const livePdfDownload=await livePdfWait;
  assert(livePdfDownload.suggestedFilename().endsWith('.pdf'));
  const livePdfPath=path.resolve('test-results/secure-live-report.pdf');
  await livePdfDownload.saveAs(livePdfPath);
  const livePdf=fs.readFileSync(livePdfPath);
  assert.equal(livePdf.subarray(0,5).toString('ascii'),'%PDF-');
  const livePdfText=livePdf.toString('latin1');
  const livePdfPages=(livePdfText.match(/\/Type\s*\/Page\b/g)||[]).length;
  assert(livePdfPages>=1&&livePdfPages<=8,'Live PDF page count outside expected range: '+livePdfPages);
  assert(livePdfText.includes('/Subtype /Image'),'Expected rasterized report image in PDF');
  assert(livePdf.length>10000,'Live PDF unexpectedly small');
  report.checks.push('Live Thai PDF: valid download, raster content and bounded pagination');

  await page.getByRole('button',{name:'Back to finding',exact:true}).first().click();assert(await summary.evaluate(e=>document.activeElement===e));
  await page.reload({waitUntil:'domcontentloaded'});await page.getByText('Analyzed Log',{exact:true}).first().click();
  const historyModal=page.locator('div.fixed.inset-0').filter({has:page.getByRole('heading',{name:/Analysis Record Details/})});
  await historyModal.getByText(/a-veeam\.txt/).waitFor();
  await historyModal.getByText(/b-vmware\.txt/).waitFor();
  await page.locator('details summary').first().click();
  assert(await page.locator('mark').first().isVisible());await page.evaluate(()=>document.documentElement.classList.add('dark'));await page.screenshot({path:'test-results/secure-history-dark.png'});
  const rows=await page.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/history',{credentials:'include'});if(!r.ok)throw new Error('owner history '+r.status);return r.json()});assert.equal(rows[0].id,saved.historyId,'Newest History row should be the bundle under test');const row=rows.find(x=>x.id===saved.historyId);
  assert.equal(row.username,'synthetic-browser-review');assert.deepEqual(row.solutionSummary,saved.solutionSummary);

  const historyMdWait=page.waitForEvent('download',{timeout:30000});
  await historyModal.getByRole('button',{name:'Export MD',exact:true}).click();
  const historyMdDownload=await historyMdWait;
  assert(historyMdDownload.suggestedFilename().endsWith('.md'));
  const historyMdPath=path.resolve('test-results/secure-history-report.md');
  await historyMdDownload.saveAs(historyMdPath);
  const historyMdContent=fs.readFileSync(historyMdPath,'utf8');
  assert(historyMdContent.startsWith('# AI Diagnostic Report'));
  assert(historyMdContent.includes('a-veeam.txt')&&historyMdContent.includes('b-vmware.txt'));
  assert(/[\u0E00-\u0E7F]/.test(historyMdContent),'Thai text missing from History Markdown export');
  report.checks.push('History Thai Markdown: actual browser download and saved evidence');
  const historyPdfWait=page.waitForEvent('download',{timeout:60000});
  await historyModal.getByRole('button',{name:'Export PDF',exact:true}).click();
  const historyPdfDownload=await historyPdfWait;
  assert(historyPdfDownload.suggestedFilename().endsWith('.pdf'));
  const historyPdfPath=path.resolve('test-results/secure-history-report.pdf');
  await historyPdfDownload.saveAs(historyPdfPath);
  const historyPdf=fs.readFileSync(historyPdfPath);
  assert.equal(historyPdf.subarray(0,5).toString('ascii'),'%PDF-');
  const historyPdfText=historyPdf.toString('latin1');
  const historyPdfPages=(historyPdfText.match(/\/Type\s*\/Page\b/g)||[]).length;
  assert(historyPdfPages>=1&&historyPdfPages<=8,'History PDF page count outside expected range: '+historyPdfPages);
  assert(historyPdfText.includes('/Subtype /Image'),'Expected rasterized History image in PDF');
  assert(historyPdf.length>10000,'History PDF unexpectedly small');
  report.checks.push('History Thai PDF: valid download, raster content and bounded pagination');

  report.checks.push('Upload, evidence, light/dark, reload and owned PostgreSQL History');
  stage='other-user:sign-in';
  const otherPage=await signIn(other,'synthetic-browser-other');
  stage='other-user:history';await otherPage.getByText('Signed in: synthetic-browser-other',{exact:true}).waitFor();
  const otherRows=await otherPage.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/history',{credentials:'include'});if(!r.ok)throw new Error('other history '+r.status);return r.json()});assert(!otherRows.some(x=>x.id===saved.historyId));
  stage='other-user:followup';
  const forbidden=await otherPage.evaluate(async id=>(await fetch('/api/eims/api/v1/analyze/followup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({historyId:id,question:'What is observed?',language:'en'})})).status,saved.historyId);assert.equal(forbidden,404);report.checks.push('Second actual-login user cannot list or follow up owner History');
  // Two authenticated history entries make back/forward a real navigation test.
  await page.goto(base+'/analyzer?acceptance=before-logout',{waitUntil:'domcontentloaded'});
  await page.goto(base+'/analyzer?acceptance=logout',{waitUntil:'domcontentloaded'});
  await page.getByRole('button',{name:/^Sign out\b/}).click();
  await page.locator('input[name="username"]').waitFor();assert.equal(await page.evaluate(async()=> (await fetch('/api/eims/api/v1/history',{credentials:'include'})).status),401);report.checks.push('Logout clears session and protected access fails');
  // Replay only the cookie issued by the real login, via an isolated HTTP
  // client. Never inject tokens into browser storage or log cookie contents.
  const replayContext=await browser.newContext(options);await replayContext.addCookies([cookie]);const replayPage=await replayContext.newPage();await replayPage.goto(base+'/analyzer',{waitUntil:'domcontentloaded'});
   try{
    for(const endpoint of ['/api/eims/api/v1/auth/session','/api/eims/api/v1/history']){
     const status=await replayPage.evaluate(async url=>(await fetch(url,{credentials:'include'})).status,endpoint);
     assert.equal(status,401);
    }
   }finally{await replayContext.close()}
  report.checks.push('Real login-issued cookie rejected after server logout');
  for(const navigate of [()=>page.goBack(),()=>page.goForward(),()=>page.reload()]){
   await navigate();await page.locator('input[name="username"]').waitFor();
   assert.equal(await page.getByText('Signed in: synthetic-browser-review',{exact:true}).count(),0);
   assert.equal(await page.locator('details summary').count(),0);
   assert.equal(await page.evaluate(async()=> (await fetch('/api/eims/api/v1/history',{credentials:'include'})).status),401);
  }
  report.checks.push('Back/forward/reload after logout: no retained evidence UI and protected API denied');
  const expiry=await browser.newContext(options);const short=await signIn(expiry,'synthetic-expiry');await new Promise(r=>setTimeout(r,3500));await short.reload({waitUntil:'domcontentloaded'});
  await short.locator('input[name="username"]').waitFor();assert.equal(await short.evaluate(async()=> (await fetch('/api/eims/api/v1/history',{credentials:'include'})).status),401);
  await short.close();const again=await signIn(expiry,'synthetic-expiry');await again.close();report.checks.push('Real login-issued expiry and reauthentication');
  assert.equal(bearerRequests,0);report.checks.push('Zero manually injected browser Authorization headers');report.status='PASS';
 }catch(error){report.failedStage=stage;report.error=String(error);report.debugAuthEvents=authDebugEvents;process.exitCode=1}finally{
  if(browser)await browser.close();fs.mkdirSync('test-results',{recursive:true});fs.writeFileSync('test-results/secure-browser-acceptance.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }
})();
