// Prepared acceptance test; no injected JWT or Authorization header.
// Requires the actual Dashboard+BFF and isolated login/DB harness to be running.
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const resultsDir=path.resolve(process.env.EIMS_TEST_RESULTS_DIR || path.resolve(__dirname,'../test-results'));
function runtimeConfig(env){
 const url=new URL(env.EIMS_TEST_BROWSER_BASE_URL);
 assert(url.protocol==='https:'&&!url.username&&!url.password&&url.pathname==='/'&&!url.search&&!url.hash,
  'Supply an explicitly approved HTTPS origin without credentials/path/query');
 assert(env.EIMS_TEST_IGNORE_TLS_ERRORS!=='1','TLS verification bypass is forbidden');
 return {base:url.origin,options:{viewport:{width:1400,height:1000},ignoreHTTPSErrors:false,acceptDownloads:true}};
}
async function runAcceptance(browserOverride){
 const loginCredential=process.env.EIMS_TEST_LOGIN_CREDENTIAL;
 if(!loginCredential) throw Error('Synthetic browser credential is required via process environment');
 let browser=browserOverride;const ownsBrowser=!browserOverride;const report={status:'FAIL',boundary:'Actual browser login, no injected bearer',checks:[]};
  let stage='startup';
  const authDebugEvents=[];
  const runtimeDebugEvents=[];
  const requestCorrelation=[];
  let progressTimer=null;
 try{
  fs.mkdirSync(resultsDir,{recursive:true});
  progressTimer=setInterval(()=>{
    const progress={stage,checksCompleted:report.checks.length,lastCheck:report.checks.at(-1)||null,updatedAt:new Date().toISOString()};
    fs.writeFileSync(path.join(resultsDir,'progress.json'),JSON.stringify(progress,null,2));
    console.log('[EIMS_ACCEPTANCE] '+JSON.stringify(progress));
  },15000);
  progressTimer.unref();
  const {base,options}=runtimeConfig(process.env);
  if(!browser){const {chromium}=require(process.env.EIMS_PLAYWRIGHT_MODULE||'playwright');browser=await chromium.launch({channel:'msedge',headless:true});}
  const owner=await browser.newContext(options),other=await browser.newContext(options);
  let bearerRequests=0;owner.on('request',r=>{if(r.headers().authorization)bearerRequests++});
  async function signIn(context,username){
    stage='signIn:'+username+':initial-session';
    const page=await context.newPage();
    page.on('console',message=>{if(message.type()==='error')runtimeDebugEvents.push('CONSOLE_ERROR '+message.text().slice(0,300));});
    page.on('pageerror',error=>runtimeDebugEvents.push('PAGEERROR '+error.message.slice(0,300)));
    const navigationStarted=new WeakMap();
    page.on('request',r=>{if(r.isNavigationRequest())navigationStarted.set(r,Date.now());});
    page.on('requestfailed',r=>{try{const u=new URL(r.url());if(u.pathname.startsWith('/api/')||r.isNavigationRequest()){const started=navigationStarted.get(r);runtimeDebugEvents.push((r.isNavigationRequest()?'NAVFAIL ':'REQFAIL ')+r.method()+' '+u.pathname+' '+(started?`${Date.now()-started}ms `:'')+(r.failure()?.errorText||''));}}catch{}});
    page.on('response',r=>{try{const u=new URL(r.url());if(r.request().isNavigationRequest()){const started=navigationStarted.get(r.request());runtimeDebugEvents.push('NAVHTTP '+r.status()+' '+r.request().method()+' '+u.pathname+(started?` ${Date.now()-started}ms`:''));}if(u.pathname.startsWith('/api/')){const headers=r.headers();if(headers['x-request-id'])requestCorrelation.push({requestId:headers['x-request-id'],method:r.request().method(),path:u.pathname,status:r.status()});if(r.status()>=400||u.pathname.endsWith('/api/v1/auth/session')||u.pathname.endsWith('/api/v1/health'))runtimeDebugEvents.push('HTTP '+r.status()+' '+r.request().method()+' '+u.pathname);}}catch{}});
    page.on('framenavigated',frame=>{if(frame===page.mainFrame())try{runtimeDebugEvents.push('NAV '+new URL(frame.url()).pathname);}catch{}});
    if(username==='synthetic-browser-other'){
     const record=(kind,url,status)=>{try{const p=new URL(url).pathname;if(p.includes('/auth/session')||p.endsWith('/api/session/login'))authDebugEvents.push(kind+(status===undefined?'':' '+status)+' '+p)}catch{}};
     page.on('request',r=>record('REQ',r.url()));
     page.on('response',r=>record('RES',r.url(),r.status()));
     page.on('requestfailed',r=>record('FAIL',r.url()));
    }page.setDefaultTimeout(20000);page.setDefaultNavigationTimeout(60000);
   // DOMContentLoaded can precede React hydration. The first auth-session probe
   // is emitted by AnalyzerSession's mount effect, so await it before clicking.
   const initialSession=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/api/v1/auth/session')&&r.request().method()==='GET',{timeout:30000});
   await page.goto(base+'/analyzer',{waitUntil:'domcontentloaded'});
    await initialSession;
    stage='signIn:'+username+':form';
   const usernameField=page.locator('input[name="username"]');await usernameField.waitFor({state:"visible"});await usernameField.fill(username);const passwordField=page.locator('input[name="password"]');await passwordField.waitFor({state:"visible"});await page.waitForFunction(()=>{const e=document.querySelector('input[name="password"]');return e&&!e.disabled&&!e.readOnly&&e.getClientRects().length>0;});await passwordField.fill(loginCredential);
   stage='signIn:'+username+':login-response';
    const response=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/api/session/login')&&r.request().method()==='POST',{timeout:60000});
   await page.getByRole('button',{name:/^Sign in\b/}).click();
   const r=await response;stage='signIn:'+username+':authenticated-ui';assert.equal(r.status(),200);const loginBody=await Promise.race([r.body().catch(()=>null),new Promise(resolve=>setTimeout(()=>resolve(null),10000))]);if(loginBody===null){if(!report.warnings)report.warnings=[];if(!report.warnings.includes("Login POST body did not finish within 10s or was no longer available; cookie and authenticated-session checks remain authoritative."))report.warnings.push("Login POST body did not finish within 10s or was no longer available; cookie and authenticated-session checks remain authoritative.");}else assert.deepEqual(JSON.parse(loginBody.toString()),{authenticated:true});await page.getByText("Signed in: "+username,{exact:true}).waitFor();
   return page;
  }
  const page=await signIn(owner,'synthetic-browser-review');
  stage='owner:health-proxy';
  const health=await page.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/health',{credentials:'include',cache:'no-store'});return {status:r.status,body:await r.json(),attempts:1};});
  assert.equal(health.status,200);
  assert.equal(health.body.status,'HEALTHY');
  assert.deepEqual(Object.keys(health.body.components).sort(),['minio_object_storage_tier','postgresql_pgbouncer_tier','redis_volatile_lru_tier']);
  assert.equal(health.body.components.postgresql_pgbouncer_tier,'UP');
  assert.equal(health.body.components.redis_volatile_lru_tier,'UP');
  assert.equal(health.body.components.minio_object_storage_tier,'UP');
  report.checks.push('Healthy synthetic runtime: PostgreSQL, Redis and MinIO report UP through BFF');
  stage='owner:analyzer-cases';
  await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();
  const cookies=await owner.cookies();const cookie=cookies.find(c=>c.name==='eims_session');
  assert(cookie&&cookie.httpOnly&&cookie.secure&&cookie.sameSite==='Strict');
  assert(!(await page.evaluate(()=>document.cookie)).includes('eims_session'));
  assert(!(await page.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}))).includes(cookie.value));
  report.checks.push('Real login; HttpOnly Secure SameSite cookie; no JWT in DOM/storage');
  stage='owner:concurrent-http-analyzer';
  const concurrent=await page.evaluate(async()=>{
    const jobs=Array.from({length:4},(_,index)=>{
      const form=new FormData();
      form.set('text',`Event ID: 4624\nSource: EIMS synthetic concurrency\nRecord: ${index}\nLogon Type: 3\nStatus: 0x0`);
      form.set('language','en');
      return fetch('/api/eims/api/v1/analyze/',{method:'POST',body:form,credentials:'include'}).then(async response=>({
        status:response.status,requestId:response.headers.get('x-request-id'),body:await response.json().catch(()=>null)
      }));
    });
    return Promise.all(jobs);
  });
  assert.equal(concurrent.length,4);
  for(const item of concurrent){assert.equal(item.status,200);assert(item.body&&item.body.historyId);assert(item.requestId);}
  const diagnosticsResult=await page.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/__test__/diagnostics',{credentials:'include',cache:'no-store'});return {status:r.status,body:await r.json()};});
  assert.equal(diagnosticsResult.status,200);
  const diagnostics=diagnosticsResult.body;
  assert.equal(diagnostics.database,'eims_regression_test_20261115');
  assert.equal(diagnostics.database_user,'eims_test');
  assert.equal(diagnostics.pool.size,2);
  assert.equal(diagnostics.pool.checked_out_after,0);
  assert.equal(diagnostics.pg_stat_activity.active,1);
  const recoveredHealth=await page.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/health',{credentials:'include',cache:'no-store'});return {status:r.status,body:await r.json()};});
  assert.equal(recoveredHealth.status,200);
  assert.equal(recoveredHealth.body.status,'HEALTHY');
  report.concurrentWorkload={requests:4,statuses:concurrent.map(x=>x.status),requestIds:concurrent.map(x=>x.requestId),database:diagnostics.database,databaseUser:diagnostics.database_user,pool:diagnostics.pool,pgStatActivity:diagnostics.pg_stat_activity,healthAfter:'HEALTHY'};
  report.checks.push('Four concurrent Analyzer HTTP requests; PostgreSQL pg_stat_activity and SQLAlchemy pool checkout return to zero; Health recovers');
  // Exercise both user input modes before the existing bundle/History/logout flow.
  stage='owner:analyzer-cases';
  for (const language of ['en','th']) for (const cid of ['fort_config','esxi_tracker','win_policy']) for (const mode of ['Paste Text','File Upload']) {
    stage=`owner:case:${language}:${cid}:${mode}`;
    await page.reload({waitUntil:'commit'});
    await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();
    await page.getByRole('button',{name:mode,exact:true}).click();
    const languageSelect=page.locator('select').first();
    await languageSelect.waitFor({state:'visible'});
    await page.waitForFunction(()=>{const s=document.querySelector('select');return !!s&&!s.disabled&&s.getClientRects().length>0;});
    await languageSelect.selectOption(language);
    const file=path.resolve(__dirname,'../evaluation/analyzer/gold/cases',cid,'input.txt');
    if(mode==='Paste Text') await page.getByPlaceholder('Paste raw Event Viewer log text...').fill(fs.readFileSync(file,'utf8'));
    else await page.locator('input[type=file]:not([multiple])').setInputFiles(file);
    const pending=page.waitForResponse(r=>r.url().includes('/api/eims/api/v1/analyze')&&r.request().method()==='POST'&&(r.status()<300||r.status()>=400));
    await page.getByRole('button',{name:'Analyze Log',exact:true}).click();
    const response=await pending;assert.equal(response.status(),200);const result=await response.json();
    assert(result.historyId);await page.getByRole('heading',{name:'Diagnostic Report',exact:true}).waitFor();
    if(cid==='fort_config'){assert.equal(result.eventId,'0100044547');assert.equal(result.eventMetadata.isCritical,false);}
    if(cid==='esxi_tracker'){assert.equal(result.eventMetadata.level,'Error');assert.equal(result.eventMetadata.isCritical,true);}
    if(cid==='win_policy'){assert.equal(result.eventId,'1129');assert.equal(result.eventMetadata.timestamp,'');assert.equal(result.eventMetadata.diagnosticCode,'WINDOWS-GROUP-POLICY-CONNECTIVITY');}
    const analyzerModal=page.locator('div.fixed.inset-0').filter({has:page.getByRole('heading',{name:'Diagnostic Report',exact:true})});
    const persistedEvidence=result.solutionSummary?.evidenceItems||[];
    if(persistedEvidence.length>0){
      const sourceSummary=analyzerModal.locator('details summary').first();
      await sourceSummary.waitFor({state:'visible'});
      await sourceSummary.focus();await page.keyboard.press('Enter');
      await analyzerModal.locator('details[open] mark').first().waitFor({state:'visible',timeout:10000});
    }else{
      assert.equal(await analyzerModal.locator('details summary').count(),0,'No source disclosure should be fabricated when the analyzer persisted no evidence items');
    }
    const historyRows=await page.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/history',{credentials:'include'});if(!r.ok)throw new Error('owner history '+r.status);return r.json()});
     const restored=historyRows.find(r=>r.id===result.historyId);
    assert(restored);assert.deepEqual(restored.solutionSummary,result.solutionSummary);
    report.checks.push(`${language} ${cid} ${mode}: rendered result and persisted History; source disclosure rendered only for persisted evidence`);
  }
  await page.reload({waitUntil:'commit'});await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();await page.getByRole('button',{name:'File Upload',exact:true}).click();
  await page.locator('input[type=file]:not([multiple])').setInputFiles({name:'invalid.txt',mimeType:'text/plain',buffer:Buffer.from([255,254,255])});
  const invalidUpload=page.waitForResponse(r=>r.url().includes('/api/eims/api/v1/analyze')&&r.request().method()==='POST'&&(r.status()<300||r.status()>=400));
  await page.getByRole('button',{name:'Analyze Log',exact:true}).click();assert.equal((await invalidUpload).status(),400);
  await page.getByText(/Unable to extract log text/).waitFor();
  assert.equal(await page.getByRole('heading',{name:'Diagnostic Report',exact:true}).count(),0);
  report.checks.push('Invalid attachment produces an error, not Analysis complete');
  await page.reload({waitUntil:'commit'});await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();
   await page.getByRole('button',{name:'Evidence Bundle',exact:true}).click();
  const root=path.resolve(__dirname,'../evaluation/analyzer/results/20261025-controlled-demo-after');
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
  await liveModal.getByText('a-veeam.txt',{exact:true}).first().waitFor();
  await liveModal.getByText(/b-vmware\.txt:1/).first().waitFor();
  const summary=liveModal.locator('details summary').first();await summary.waitFor({state:'visible'});await summary.focus();await page.keyboard.press('Enter');
  await liveModal.locator('details[open] mark').first().waitFor({state:'visible',timeout:10000});
  fs.mkdirSync(resultsDir,{recursive:true});await page.screenshot({path:path.join(resultsDir,'secure-source-light.png')});

  const liveMdWait=page.waitForEvent('download',{timeout:30000});
  await liveModal.getByRole('button',{name:'Export MD',exact:true}).click();
  const liveMdDownload=await liveMdWait;
  assert(liveMdDownload.suggestedFilename().endsWith('.md'));
  const liveMdPath=path.join(resultsDir,'secure-live-report.md');
  await liveMdDownload.saveAs(liveMdPath);
  const liveMdContent=fs.readFileSync(liveMdPath,'utf8');
  assert(liveMdContent.startsWith('# AI Diagnostic Report'));
  assert(liveMdContent.includes('a-veeam.txt')&&liveMdContent.includes('b-vmware.txt'));
  assert(/[\u0E00-\u0E7F]/.test(liveMdContent),'Thai text missing from live Markdown export');
  report.checks.push('Live Thai Markdown: actual browser download, content and source evidence');
  const livePdfWait=page.waitForEvent('download',{timeout:60000});
  const livePdfButton=liveModal.getByRole('button',{name:'Export PDF',exact:true});
  await livePdfButton.waitFor({state:'visible'});assert(await livePdfButton.isEnabled());
  // The handler creates a Blob download; avoid Playwright's unrelated navigation wait for the blob URL.
  await livePdfButton.evaluate(button=>button.click());
  const livePdfDownload=await livePdfWait;
  assert(livePdfDownload.suggestedFilename().endsWith('.pdf'));
  const livePdfPath=path.join(resultsDir,'secure-live-report.pdf');
  await livePdfDownload.saveAs(livePdfPath);
  const livePdf=fs.readFileSync(livePdfPath);
  assert.equal(livePdf.subarray(0,5).toString('ascii'),'%PDF-');
  const livePdfText=livePdf.toString('latin1');
  const livePdfPages=(livePdfText.match(/\/Type\s*\/Page\b/g)||[]).length;
  assert(livePdfPages>=1&&livePdfPages<=8,'Live PDF page count outside expected range: '+livePdfPages);
  assert(livePdfText.includes('/Subtype /Image'),'Expected rasterized report image in PDF');
  assert(livePdf.length>10000,'Live PDF unexpectedly small');
  report.checks.push('Live Thai PDF: valid download, raster content and bounded pagination');

  // The run is in Thai (the Thai Markdown assertion above proves it), so the control is localized; scope to the opened evidence block.
  const liveBack=liveModal.locator('details[open]').first().getByRole('button',{name:'กลับไปที่หลักฐาน',exact:true});
  await liveBack.click();
  await liveModal.locator('details[open]').waitFor({state:'detached'});
  await summary.press('Enter');
  await liveModal.locator('details[open] mark').first().waitFor({state:'visible',timeout:10000});
  await page.reload({waitUntil:'commit'});await page.getByText('Analyzed Log',{exact:true}).first().click();
  const historyModal=page.locator('div.fixed.inset-0').filter({has:page.getByRole('heading',{name:/Analysis Record Details/})});
  await historyModal.getByText('a-veeam.txt',{exact:true}).first().waitFor();
  await historyModal.getByText(/b-vmware\.txt:1/).first().waitFor();
const historySummary=historyModal.locator('details summary').first();await historySummary.focus();await page.keyboard.press('Enter');await historyModal.locator('details[open] mark').first().waitFor({state:'visible',timeout:10000});await page.evaluate(()=>document.documentElement.classList.add('dark'));await page.screenshot({path:path.join(resultsDir,'secure-history-dark.png')});
  const rows=await page.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/history',{credentials:'include'});if(!r.ok)throw new Error('owner history '+r.status);return r.json()});assert.equal(rows[0].id,saved.historyId,'Newest History row should be the bundle under test');const row=rows.find(x=>x.id===saved.historyId);
  assert.equal(row.username,'synthetic-browser-review');assert.deepEqual(row.solutionSummary,saved.solutionSummary);

  const historyMdWait=page.waitForEvent('download',{timeout:30000});
  await historyModal.getByRole('button',{name:'Export MD',exact:true}).click();
  const historyMdDownload=await historyMdWait;
  assert(historyMdDownload.suggestedFilename().endsWith('.md'));
  const historyMdPath=path.join(resultsDir,'secure-history-report.md');
  await historyMdDownload.saveAs(historyMdPath);
  const historyMdContent=fs.readFileSync(historyMdPath,'utf8');
  assert(historyMdContent.startsWith('# AI Diagnostic Report'));
  assert(historyMdContent.includes('a-veeam.txt')&&historyMdContent.includes('b-vmware.txt'));
  assert(/[\u0E00-\u0E7F]/.test(historyMdContent),'Thai text missing from History Markdown export');
  report.checks.push('History Thai Markdown: actual browser download and saved evidence');
  const historyPdfWait=page.waitForEvent('download',{timeout:60000});
  const historyPdfButton=historyModal.getByRole('button',{name:'Export PDF',exact:true});
  await historyPdfButton.waitFor({state:'visible'});assert(await historyPdfButton.isEnabled());
  await historyPdfButton.evaluate(button=>button.click());
  const historyPdfDownload=await historyPdfWait;
  assert(historyPdfDownload.suggestedFilename().endsWith('.pdf'));
  const historyPdfPath=path.join(resultsDir,'secure-history-report.pdf');
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

  // Verified Knowledge lifecycle: a user proposes from a saved incident, an
  // independent admin reviews it, and the next exact-identity analysis reuses it.
  const knowledgeTitle=`Verified Group Policy connectivity recovery ${Date.now()}`;
  stage='knowledge:owner-proposal';
  await page.reload({waitUntil:'commit'});
  await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Paste Text',exact:true}).click();
  await page.locator('select').first().selectOption('en');
  const knowledgeInput=path.resolve(__dirname,'../evaluation/analyzer/gold/cases/win_policy/input.txt');
  await page.getByPlaceholder('Paste raw Event Viewer log text...').fill(fs.readFileSync(knowledgeInput,'utf8'));
  const knowledgeAnalysisResponse=page.waitForResponse(r=>r.url().includes('/api/eims/api/v1/analyze')&&r.request().method()==='POST'&&r.status()===200);
  await page.getByRole('button',{name:'Analyze Log',exact:true}).click();
  const knowledgeAnalysis=await knowledgeAnalysisResponse;assert.equal(knowledgeAnalysis.status(),200);
  const knowledgeResult=await knowledgeAnalysis.json();
  assert.equal(knowledgeResult.eventId,'1129');
  assert.equal(knowledgeResult.eventMetadata.sourceFamily,'windows_event');
  assert.equal(knowledgeResult.eventMetadata.diagnosticCode,'WINDOWS-GROUP-POLICY-CONNECTIVITY');
  await page.getByRole('heading',{name:'Diagnostic Report',exact:true}).waitFor();
  const proposalToggle=page.getByRole('button',{name:/Propose knowledge/});
  await proposalToggle.waitFor({state:'visible'});
  await proposalToggle.click();
  // Scope fields to the visible proposal form. Analyzer history can retain a
  // hidden copy of the same labels; an unscoped getByLabel may select that copy.
  const proposalForm=page.locator('form:visible').filter({hasText:'Root cause'});
  await proposalForm.waitFor({state:'visible'});
  await proposalForm.getByLabel('Knowledge title').fill(knowledgeTitle);
  await proposalForm.getByLabel('Resolution outcome').selectOption('resolved');
  const knowledgeRootCause='The Group Policy client could not reach its configured domain controller because the required network path was unavailable.';
  await proposalForm.getByLabel('Root cause').fill(knowledgeRootCause);
  await proposalForm.getByLabel('Resolution steps (one per line)').fill('Verify DNS resolution for the domain controller.\nRestore the required network path and validate SYSVOL access.\nRun gpupdate /force and confirm a successful policy refresh.');
  await proposalForm.getByLabel('Impact').fill('Computer policy refresh was delayed for the affected endpoint.');
  await proposalForm.getByLabel('Prevention / recurrence control').fill('Monitor domain controller DNS and SYSVOL reachability from managed endpoints.');
  await proposalForm.getByLabel(/Evidence notes/).fill('Synthetic Event ID 1129 source evidence identifies Group Policy connectivity failure.\nResolution was reproduced in the isolated acceptance environment.');
  await proposalForm.getByLabel(/HTTPS references/).fill('https://learn.microsoft.com/');
  await proposalForm.getByRole('button',{name:'Submit for review'}).click();
  await page.getByText(/Proposal saved as pending/).waitFor();
  const mine=await page.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/knowledge/proposals/mine',{credentials:'include'});return {status:r.status,body:await r.json()};});
  assert.equal(mine.status,200);const pendingKnowledge=mine.body.items.find(item=>item.sourceHistoryId===knowledgeResult.historyId);
  assert(pendingKnowledge);assert.equal(pendingKnowledge.status,'pending');
  const hiddenBeforeApproval=await page.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/knowledge/',{credentials:'include'});return {status:r.status,body:await r.json()};});
  assert.equal(hiddenBeforeApproval.status,200);assert(!hiddenBeforeApproval.body.items.some(item=>item.id===pendingKnowledge.id));
  report.checks.push('Engineer proposes curated root cause, resolution, impact, prevention and evidence; pending knowledge remains unpublished');

  stage='knowledge:independent-admin-review';
  const adminContext=await browser.newContext(options);
  const adminPage=await signIn(adminContext,'synthetic-browser-admin');
  await adminPage.goto(base+'/knowledge',{waitUntil:'domcontentloaded'});
  await adminPage.getByRole('heading',{name:'Independent review queue',exact:true}).waitFor();
  await adminPage.getByRole('heading',{name:'Official vendor source catalogue',exact:true}).waitFor();
  report.checks.push('Admin can open the database-backed official vendor source catalogue');
  await adminPage.getByText(knowledgeTitle,{exact:true}).waitFor();
  const knowledgeReviewNote='Independently checked the official diagnostic reference and reproduced the recovery steps in the isolated environment.';
  await adminPage.getByLabel('Review note (required for approval or rejection)').fill(knowledgeReviewNote);
  await adminPage.getByRole('button',{name:'Approve & publish',exact:true}).click();
  await adminPage.getByText('Knowledge approved and published for exact-identity reuse.',{exact:true}).waitFor();
  const approvedKnowledge=await adminPage.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/knowledge/?source_family=windows_event&diagnostic_identity=WINDOWS-GROUP-POLICY-CONNECTIVITY',{credentials:'include'});return {status:r.status,body:await r.json()};});
  assert.equal(approvedKnowledge.status,200);
  const approvedEntry=approvedKnowledge.body.items.find(item=>item.id===pendingKnowledge.id&&item.status==='approved');
  assert(approvedEntry);assert.equal(approvedEntry.reviewNote,knowledgeReviewNote);
  assert.equal(approvedEntry.sourceHistoryHash,pendingKnowledge.sourceHistoryHash);
  report.checks.push('Independent admin approval records reviewer rationale and preserves immutable source provenance');

  stage='knowledge:exact-identity-reuse';
  await page.reload({waitUntil:'commit'});
  await page.getByText('Signed in: synthetic-browser-review',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Paste Text',exact:true}).click();
  await page.locator('select').first().selectOption('en');
  await page.getByPlaceholder('Paste raw Event Viewer log text...').fill(fs.readFileSync(knowledgeInput,'utf8'));
  const reuseResponse=page.waitForResponse(r=>r.url().includes('/api/eims/api/v1/analyze')&&r.request().method()==='POST'&&r.status()===200);
  await page.getByRole('button',{name:'Analyze Log',exact:true}).click();
  const reused=await reuseResponse;assert.equal(reused.status(),200);const reusedResult=await reused.json();
  assert.equal(reusedResult.solutionSummary.overview,knowledgeRootCause);
  assert.equal(reusedResult.solutionSummary.confidence,'high');
  assert(reusedResult.solutionSummary.evidence.some(item=>item.includes('Approved knowledge entry')));
  report.checks.push('Secure Analyzer reuses only the approved exact-family, exact-diagnostic knowledge entry');

  // Exercise lifecycle state transitions in the real Admin browser context.
  stage='knowledge:lifecycle-revalidation';
  const approvedCard=adminPage.locator('article').filter({hasText:knowledgeTitle}).last();
  await approvedCard.getByLabel('Reason').fill('Vendor support matrix changed; applicability must be reconfirmed.');
  await approvedCard.getByLabel('Reviewer note / evidence').fill('Admin checked current vendor documentation and recorded the required evidence.');
  await approvedCard.getByRole('button',{name:'Require revalidation',exact:true}).click();
  await adminPage.getByText('Knowledge revalidation queue',{exact:true}).waitFor();
  const revalidationCard=adminPage.locator('article').filter({hasText:knowledgeTitle}).last();
  await revalidationCard.getByLabel('Review reason').fill('Supported build and prerequisites have been rechecked.');
  await revalidationCard.getByLabel('Reviewer note / evidence').fill('Controlled validation passed in the isolated acceptance environment.');
  await revalidationCard.getByRole('button',{name:'Revalidate & reactivate',exact:true}).click();
  const activeCard=adminPage.locator('article').filter({hasText:knowledgeTitle}).last();
  await activeCard.getByRole('button',{name:'Lifecycle audit history',exact:true}).click();
  await activeCard.getByText('active → revalidation_required',{exact:true}).waitFor();
  await activeCard.getByText('revalidation_required → active',{exact:true}).waitFor();
  report.checks.push('Admin lifecycle workflow: require revalidation, independently reactivate, and inspect append-only audit history');

  stage='other-user:sign-in';
  const otherPage=await signIn(other,'synthetic-browser-other');
  stage='other-user:history';await otherPage.getByText('Signed in: synthetic-browser-other',{exact:true}).waitFor();
  const otherRows=await otherPage.evaluate(async()=>{const r=await fetch('/api/eims/api/v1/history',{credentials:'include'});if(!r.ok)throw new Error('other history '+r.status);return r.json()});assert(!otherRows.some(x=>x.id===saved.historyId));
  await otherPage.goto(base+'/knowledge',{waitUntil:'domcontentloaded'});
  await otherPage.getByRole('heading',{name:'Approved knowledge',exact:true}).waitFor();
  await otherPage.getByText(knowledgeTitle,{exact:true}).waitFor();
  assert.equal(await otherPage.getByRole('heading',{name:'Independent review queue',exact:true}).count(),0);
  assert.equal(await otherPage.getByRole('heading',{name:'Official vendor source catalogue',exact:true}).count(),1);
  assert.equal(await otherPage.getByText('Reviewer lifecycle controls',{exact:true}).count(),0);
  assert.equal(await otherPage.getByRole('button',{name:'Verify source reference',exact:true}).count(),0);
  assert.equal(await otherPage.getByRole('heading',{name:'Knowledge revalidation queue',exact:true}).count(),0);
  report.checks.push('Engineer can read approved Knowledge and source catalogue but cannot see review queue or lifecycle controls');

  stage='knowledge:lifecycle-withdrawal';
  await activeCard.getByLabel('Reason').fill('The synthetic acceptance knowledge is being retired after the workflow check.');
  await activeCard.getByLabel('Reviewer note / evidence').fill('Withdrawal is intentional for this isolated test record; audit evidence must remain.');
  await activeCard.getByRole('button',{name:'Withdraw',exact:true}).click();
  await activeCard.waitFor({state:'detached'});
  report.checks.push('Admin can withdraw approved Knowledge without deleting its audit trail');
  await adminContext.close();

  stage='other-user:delete-history';
  const deniedDelete=await otherPage.evaluate(async id=>(await fetch(`/api/eims/api/v1/history/${id}`,{method:'DELETE',credentials:'include'})).status,saved.historyId);
  assert.equal(deniedDelete,404);
  const ownerStillHasHistory=await page.evaluate(async id=>{const r=await fetch('/api/eims/api/v1/history',{credentials:'include'});return {status:r.status,items:await r.json()};},saved.historyId);
  assert.equal(ownerStillHasHistory.status,200);
  assert(ownerStillHasHistory.items.some(item=>item.id===saved.historyId));
  report.checks.push('Second actual-login user cannot list or delete owner History; owner record remains intact');
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
  const expiry=await browser.newContext(options);
  const short=await signIn(expiry,'synthetic-expiry');
  const issuedCookie=(await expiry.cookies()).find(c=>c.name==='eims_session');
  assert(issuedCookie,'Expiry scenario must start from a real login-issued session cookie');
  const issuedPayload=JSON.parse(Buffer.from(issuedCookie.value.split('.')[1],'base64url').toString());
  assert(issuedPayload.exp>Date.now()/1000+30,'Expiry fixture must expire the server session before JWT exp');
  await new Promise(r=>setTimeout(r,3500));
  await short.reload({waitUntil:'domcontentloaded'});
  await short.locator('input[name="username"]').waitFor();
  assert.equal(await short.evaluate(async()=> (await fetch('/api/eims/api/v1/history',{credentials:'include'})).status),401);
  await short.close();
  const again=await signIn(expiry,'synthetic-expiry');
  await again.close();
  report.expiryBoundary='PostgreSQL session row expires after 2 seconds via disposable acceptance fixture; JWT exp remains unexpired. JWT-expiry boundary is not claimed by this browser test.';
  report.checks.push('Server-side PostgreSQL session expiry rejects a still-unexpired login JWT; reauthentication succeeds');
  const transient5xx=runtimeDebugEvents.filter(event=>/HTTP 50[23] /.test(event));assert.equal(transient5xx.length,0,'Transient API 502/503 during browser acceptance: '+transient5xx.join(' | '));report.checks.push('No transient API 502/503 across the authenticated browser journey');
  assert.equal(bearerRequests,0);report.checks.push('Zero manually injected browser Authorization headers');
  assert(requestCorrelation.length>0,'Browser responses must expose end-to-end request IDs');
  report.requestCorrelation=requestCorrelation;
  report.checks.push('Browser receives propagated request IDs for correlation across HTTPS proxy, BFF and backend');report.status='PASS';
 }catch(error){report.failedStage=stage;report.error=String(error);report.debugAuthEvents=authDebugEvents;report.debugRuntimeEvents=runtimeDebugEvents.slice(-80);report.requestCorrelation=requestCorrelation;}finally{
  if(progressTimer)clearInterval(progressTimer);
  if(ownsBrowser&&browser)await browser.close();fs.mkdirSync(resultsDir,{recursive:true});fs.writeFileSync(path.join(resultsDir,'progress.json'),JSON.stringify({stage,status:report.status,checksCompleted:report.checks.length,updatedAt:new Date().toISOString()},null,2));fs.writeFileSync(path.join(resultsDir,'secure-browser-acceptance.json'),JSON.stringify(report,null,2));
 }
  return report;
}

module.exports={runtimeConfig,runAcceptance};
if(require.main===module){runAcceptance().then(report=>{console.log(JSON.stringify(report));if(report.status!=='PASS')process.exitCode=1}).catch(error=>{console.error(error);process.exitCode=1});}
